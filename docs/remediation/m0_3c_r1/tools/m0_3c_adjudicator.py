#!/usr/bin/env python3
"""M0.3c-R1 nested OpenZeppelin submodule adjudication.

The scanner input is constructed from blobs owned directly by the pinned nested Git
tree. Gitlinks are recorded and excluded by provenance. Raw scanner output is
held only in a mode-0700 temporary directory and is deleted before publication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/security"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m0_3a_adjudicator as base
import m0_3c_context as execution_context

PARENT_PREFIX = "contracts/lib/openzeppelin-contracts-upgradeable"
PARENT_PIN = "aa677e9d28ed78fc427ec47ba2baef2030c58e7c"
TARGET_IN_PARENT = "lib/openzeppelin-contracts"
PREFIX = PARENT_PREFIX + "/" + TARGET_IN_PARENT
PIN = "fcbae5394ae8ad52d8e580a3477db99814b9d565"
CHILD_GITLINKS = {
    "lib/erc4626-tests": "232ff9ba8194e406967f52ecc5cb52ed764209e9",
    "lib/forge-std": "3b20d60d14b343ee4f908cb8079495c07f5e8981",
    "lib/halmos-cheatcodes": "7328abe100445fc53885c21d0e713b95293cf14c",
}
SCANNER_SHA256 = base.SCANNER_SHA256
ALLOWED = base.ALLOWED
DOMAINS = base.DOMAINS
PROOF_ROLES = {
    "expected_custom_error_assertion": "upstream_js_test",
    "ecdsa_public_key_der": "upstream_public_vector",
}
PROOFS = set(PROOF_ROLES)
RATIONALES = PROOFS | {
    "missing_or_stale_evidence",
    "credential_or_ambiguous_datum",
    "review_incomplete",
}
SEMANTIC_ORACLE_REL = "docs/remediation/m0_3c_r1/tools/m0_3c_semantic_oracle.py"
PINNED_PYTHON = Path("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python")
CONTEXT_MARKERS = {
    "20": ("/token/ERC20/", "/governance/"),
    "721": ("/token/ERC721/",),
    "1155": ("/token/ERC1155/",),
    "6909": ("/token/ERC6909/",),
    "1363": ("/token/ERC20/",),
    "2612": ("/token/ERC20/",),
    "3156": ("/token/ERC20/",),
    "2981": ("/token/common/",),
}
ATTESTATION_FIELDS = {
    "schema", "head", "parent_submodule_commit", "submodule_commit",
    "decisions_sha256", "source_manifest_sha256", "scanner_sha256",
    "scanner_version", "verifier", "records",
}
ATTESTATION_VERIFIER_FIELDS = {
    "name", "path", "sha256", "python_path", "python_sha256",
    "python_version", "cryptography_version", "cryptography_module_path",
    "cryptography_module_sha256",
}
ATTESTATION_RECORD_FIELDS = {
    "finding_id", "relative_path", "rule_id", "line_start", "line_end",
    "file_sha256", "source_object_id", "classification", "verdict", "context",
}
IDENTITY = set(base.IDENTITY) | {"parent_submodule", "parent_submodule_commit", "parent_submodule_head", "parent_submodule_clean"}
DECISION_FIELDS = set(base.DECISION_FIELDS) | {"parent_submodule", "parent_submodule_commit", "parent_submodule_head", "parent_submodule_clean"}


class AdjudicationError(base.AdjudicationError):
    pass


HASH_FIELDS = set(base.HASH_FIELDS) | {
    "parent_submodule_commit",
    "parent_submodule_head",
}

CONTEXT_FIELDS = {
    "kind", "assertion_target", "call_target", "invoked_operation",
    "error_name", "error_signature", "error_selector", "declaration_owner",
    "execution_targets", "reachability_chains",
}


def validate_context(value, classification):
    if classification == "ecdsa_public_key_der":
        if value != {"kind": "public_ec_der"}:
            raise AdjudicationError("semantic context mismatch")
        return value
    if classification != "expected_custom_error_assertion" or not isinstance(value, dict) or set(value) != CONTEXT_FIELDS:
        raise AdjudicationError("semantic context mismatch")
    if value["kind"] != "custom_error_execution":
        raise AdjudicationError("semantic context mismatch")
    for field in ("assertion_target", "call_target", "invoked_operation", "error_name", "error_signature"):
        if not isinstance(value[field], str) or not re.fullmatch(r"[A-Za-z0-9_.$(),]+", value[field]):
            raise AdjudicationError("semantic context field")
    if not re.fullmatch(r"[0-9a-f]{8}", value["error_selector"]):
        raise AdjudicationError("semantic selector")
    owner = value["declaration_owner"]
    if not isinstance(owner, dict) or set(owner) != {"name", "kind", "path", "source_sha256", "source_object_id"}:
        raise AdjudicationError("semantic owner")
    if owner["kind"] not in {"contract", "interface", "library"}:
        raise AdjudicationError("semantic owner")
    base.safe_path(owner["path"])
    if not re.fullmatch(r"[0-9a-f]{64}", owner["source_sha256"]) or not re.fullmatch(r"[0-9a-f]{40}", owner["source_object_id"]):
        raise AdjudicationError("semantic owner")
    targets = value["execution_targets"]
    chains = value["reachability_chains"]
    if not isinstance(targets, list) or not targets or not isinstance(chains, list) or len(chains) != len(targets):
        raise AdjudicationError("semantic reachability")
    artifacts = []
    target_order = []
    for target in targets:
        if not isinstance(target, dict) or set(target) != {"artifact", "caller_path", "caller_sha256", "caller_object_id"}:
            raise AdjudicationError("semantic target")
        base.safe_path(target["caller_path"])
        if not re.fullmatch(r"[$A-Za-z_][A-Za-z0-9_$]*", target["artifact"]) or not re.fullmatch(r"[0-9a-f]{64}", target["caller_sha256"]) or not re.fullmatch(r"[0-9a-f]{40}", target["caller_object_id"]):
            raise AdjudicationError("semantic target")
        artifacts.append(target["artifact"])
        target_order.append((target["caller_path"], target["artifact"]))
    if target_order != sorted(target_order) or len(set(target_order)) != len(target_order):
        raise AdjudicationError("semantic target ordering")
    chain_artifacts = []
    for chain in chains:
        if not isinstance(chain, dict) or set(chain) != {"artifact", "containers"} or not isinstance(chain["containers"], list) or not chain["containers"]:
            raise AdjudicationError("semantic chain")
        chain_artifacts.append(chain["artifact"])
        for node in chain["containers"]:
            if not isinstance(node, dict) or set(node) != {"name", "kind", "path"} or node["kind"] not in {"contract", "interface", "library"}:
                raise AdjudicationError("semantic chain")
            base.safe_path(node["path"])
        last = chain["containers"][-1]
        if last["name"] != owner["name"] or last["path"] != owner["path"] or last["kind"] != owner["kind"]:
            raise AdjudicationError("semantic chain owner")
    if chain_artifacts != sorted(artifacts):
        raise AdjudicationError("semantic chain ordering")
    return value


def sanitized(value, field=""):
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or re.sub(r"[^a-z]", "", key.lower()) in base.FORBIDDEN:
                raise AdjudicationError("forbidden evidence field")
            sanitized(child, key)
    elif isinstance(value, list):
        for child in value:
            sanitized(child, field)
    elif isinstance(value, str):
        if field in HASH_FIELDS:
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
                raise AdjudicationError("invalid digest")
        elif field in {"relative_path", "path", "submodule", "parent_submodule"}:
            base.safe_path(value)
            if re.search(r"[0-9a-fA-F]{32}|[A-Za-z0-9]{64}", value):
                raise AdjudicationError("unsafe long path value")
        elif field == "rule_id":
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value) or re.search(r"[a-z0-9]{24}", value):
                raise AdjudicationError("invalid rule")
        elif len(value) > 96 or not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", value):
            raise AdjudicationError("unsafe evidence text")
    elif value is not None and type(value) not in {bool, int}:
        raise AdjudicationError("unsafe evidence type")


def validate_record(record):
    sanitized(record)
    if not isinstance(record, dict) or set(record) != DECISION_FIELDS:
        raise AdjudicationError("record schema mismatch")
    if record["disposition"] not in ALLOWED or record["rationale"] not in RATIONALES:
        raise AdjudicationError("invalid disposition or rationale")
    if record["parent_submodule"] != PARENT_PREFIX or record["submodule"] != PREFIX or not record["relative_path"].startswith(PREFIX + "/"):
        raise AdjudicationError("outside nested tranche")
    if any(not re.fullmatch(r"[0-9a-f]{40}", record[key]) for key in ("head", "parent_submodule_commit", "parent_submodule_head", "submodule_commit", "submodule_head")):
        raise AdjudicationError("invalid commit")
    for key in ("finding_id", "file_sha256", "source_manifest_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", record[key]):
            raise AdjudicationError("invalid sha256")
    if type(record["submodule_clean"]) is not bool or type(record["parent_submodule_clean"]) is not bool:
        raise AdjudicationError("invalid clean state")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", record["rule_id"]):
        raise AdjudicationError("invalid rule")
    if (
        any(type(record[key]) is not int for key in ("line_start", "line_end"))
        or not 1 <= record["line_start"] <= record["line_end"]
    ):
        raise AdjudicationError("invalid line range")
    expected_id = base.stable_id(
        record["head"],
        record["submodule_commit"],
        record["relative_path"],
        record["rule_id"],
        record["line_start"],
        record["line_end"],
    )
    if record["finding_id"] != expected_id:
        raise AdjudicationError("identity mismatch")
    if record["file_role"] not in set(PROOF_ROLES.values()) | {"unreviewed"}:
        raise AdjudicationError("invalid role")
    if record["source_review"] not in PROOFS | {"not_proven", "credential_or_ambiguous_datum"}:
        raise AdjudicationError("invalid source proof")
    if (
        record["reviewer_status"] not in {"accepted", "pending_review", "rejected"}
        or record["reviewer"] not in {"codex_local_source_review", "pending"}
    ):
        raise AdjudicationError("invalid reviewer")
    reachability = record["reachability"]
    if (
        not isinstance(reachability, dict)
        or set(reachability) != DOMAINS
        or any(value not in {"absent", "reachable", "not_assessed"} for value in reachability.values())
    ):
        raise AdjudicationError("invalid reachability")
    refs = record["evidence_refs"]
    if not isinstance(refs, list):
        raise AdjudicationError("invalid references")
    for ref in refs:
        if (
            not isinstance(ref, dict)
            or set(ref) != {"path", "sha256"}
            or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])
        ):
            raise AdjudicationError("invalid reference")
    if record["disposition"] == "confirmed_noncredential_fixture":
        if (
            record["source_review"] not in PROOFS
            or record["rationale"] != record["source_review"]
            or record["file_role"] != PROOF_ROLES[record["source_review"]]
            or record["reviewer_status"] != "accepted"
            or record["reviewer"] == "pending"
            or not refs
            or not record["parent_submodule_clean"]
            or record["parent_submodule_head"] != record["parent_submodule_commit"]
            or not record["submodule_clean"]
            or record["submodule_head"] != record["submodule_commit"]
            or set(reachability.values()) != {"absent"}
        ):
            raise AdjudicationError("confirmed finding lacks accepted proof")
    if record["disposition"] == "potential_credential":
        if (
            record["rationale"] != "credential_or_ambiguous_datum"
            or record["source_review"] != "credential_or_ambiguous_datum"
            or not refs
        ):
            raise AdjudicationError("potential finding lacks blocker rationale")
    return record


def provenance(repo):
    repo = Path(repo)
    head = base.git(repo, "rev-parse", "HEAD").decode().strip()
    parent_tree = base.git(repo, "ls-tree", "HEAD", "--", PARENT_PREFIX).decode().split()
    parent_index = base.git(repo, "ls-files", "--stage", "--", PARENT_PREFIX).decode().split()
    if (
        len(parent_tree) != 4
        or parent_tree[:2] != ["160000", "commit"]
        or len(parent_index) != 4
        or parent_index[0] != "160000"
    ):
        raise AdjudicationError("missing parent gitlink")
    parent_commit = parent_tree[2]
    parent = repo / PARENT_PREFIX
    parent_head = base.git(parent, "rev-parse", "HEAD").decode().strip()
    parent_status = base.git(parent, "status", "--porcelain", "--untracked-files=all", "--ignored")
    parent_clean = not parent_status and parent_index[1] == parent_commit

    target_tree = base.git(parent, "ls-tree", parent_commit, "--", TARGET_IN_PARENT).decode().split()
    target_index = base.git(parent, "ls-files", "--stage", "--", TARGET_IN_PARENT).decode().split()
    if (
        len(target_tree) != 4
        or target_tree[:2] != ["160000", "commit"]
        or len(target_index) != 4
        or target_index[0] != "160000"
    ):
        raise AdjudicationError("missing target gitlink")
    target_commit = target_tree[2]
    target = repo / PREFIX
    target_head = base.git(target, "rev-parse", "HEAD").decode().strip()
    target_status = base.git(target, "status", "--porcelain", "--untracked-files=all", "--ignored")
    target_clean = not target_status and target_index[1] == target_commit
    return {
        "head": head,
        "parent_submodule": PARENT_PREFIX,
        "parent_submodule_commit": parent_commit,
        "parent_submodule_head": parent_head,
        "parent_submodule_clean": parent_clean,
        "submodule": PREFIX,
        "submodule_commit": target_commit,
        "submodule_head": target_head,
        "submodule_clean": target_clean,
    }


def direct_tree(repo, commit=PIN):
    """Return only blobs owned by the direct commit plus separately typed gitlinks."""
    submodule = Path(repo) / PREFIX
    raw = base.git(submodule, "ls-tree", "-r", "-z", commit)
    blobs = {}
    gitlinks = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode().split()
        name = raw_name.decode()
        base.safe_path(name)
        if object_type == "commit" and mode == "160000":
            gitlinks[name] = object_id
            continue
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise AdjudicationError("unsupported direct tree entry")
        blobs[name] = {"object_id": object_id, "mode": mode}
    if gitlinks != CHILD_GITLINKS:
        raise AdjudicationError("child gitlink provenance mismatch")
    return blobs, gitlinks


def pinned_blob(repo, commit, relative_path):
    base.safe_path(relative_path)
    return base.git(Path(repo) / PREFIX, "show", f"{commit}:{relative_path}")


def _strip_solidity_noncode(data):
    text = data.decode("utf-8")
    output = []
    index = 0
    state = "code"
    quote = ""
    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if character == "/" and following == "/":
                state = "line"
                output.extend("  ")
                index += 2
                continue
            if character == "/" and following == "*":
                state = "block"
                output.extend("  ")
                index += 2
                continue
            if character in {"'", '"'}:
                state = "string"
                quote = character
                output.append(" ")
                index += 1
                continue
            output.append(character)
            index += 1
        elif state == "line":
            output.append("\n" if character == "\n" else " ")
            if character == "\n":
                state = "code"
            index += 1
        elif state == "block":
            if character == "*" and following == "/":
                state = "code"
                output.extend("  ")
                index += 2
            else:
                output.append("\n" if character == "\n" else " ")
                index += 1
        else:
            if character == "\\":
                output.extend("  ")
                index += 2
            elif character == quote:
                state = "code"
                output.append(" ")
                index += 1
            else:
                output.append("\n" if character == "\n" else " ")
                index += 1
    if state in {"block", "string"}:
        raise AdjudicationError("unterminated Solidity token")
    return "".join(output)


def production_declarations(repo, commit=PIN):
    blobs, _ = direct_tree(repo, commit)
    pattern = re.compile(r"\berror\s+(ERC([0-9]+)[A-Za-z][A-Za-z0-9]*)\s*\(")
    declarations = {}
    for relative in blobs:
        if not relative.startswith("contracts/") or not relative.endswith(".sol"):
            continue
        data = pinned_blob(repo, commit, relative)
        for name, standard in pattern.findall(_strip_solidity_noncode(data)):
            declarations.setdefault(name, []).append((relative, standard))
    return declarations


def source_proof(repo, path, start, end, declared_errors=None):
    data = base.file_bytes(Path(repo), path)
    lines = data.decode("utf-8").splitlines()
    if start != end or not 1 <= start <= len(lines):
        return "not_proven", "unreviewed"
    line = lines[start - 1]
    # JavaScript assertions are never classified from a repository-wide error
    # name lookup. production_semantics() requires the exact execution chain.
    if path.startswith(PREFIX + "/test/") and path.endswith(".json"):
        match = re.fullmatch(r'\s*"keyDer"\s*:\s*"([0-9a-f]+)",?\s*', line)
        if match:
            document = json.loads(data)
            matching_groups = [
                group for group in document.get("testGroups", [])
                if group.get("keyDer") == match.group(1)
            ]
            if (
                document.get("algorithm") == "ECDSA"
                and matching_groups
                and all(
                    group.get("key", {}).get("type") == "EcPublicKey"
                    and group.get("type") == "EcdsaP1363Verify"
                    for group in matching_groups
                )
            ):
                process = subprocess.run(
                    ["openssl", "pkey", "-pubin", "-inform", "DER", "-noout"],
                    input=bytes.fromhex(match.group(1)),
                    capture_output=True,
                )
                if process.returncode == 0:
                    return "ecdsa_public_key_der", "upstream_public_vector"
    return "not_proven", "unreviewed"


_PRODUCTION_CONTEXT_CACHE = {}


def production_semantics(repo, report, commit, owned_blobs):
    """Resolve each proof from pinned bytes and exact execution context once."""
    key = (str(Path(repo).resolve()), commit, tuple(sorted((name, meta["object_id"]) for name, meta in owned_blobs.items())))
    cached = _PRODUCTION_CONTEXT_CACHE.get(key)
    if cached is None:
        pinned = {name: pinned_blob(repo, commit, name) for name in owned_blobs}
        nodes = execution_context.build_index(pinned)
        cached = (pinned, nodes)
        _PRODUCTION_CONTEXT_CACHE[key] = cached
    pinned, nodes = cached
    result = {}
    for item in report:
        observed = item.get("File")
        if not isinstance(observed, str):
            continue
        observed = observed[2:] if observed.startswith("./") else observed
        relative = observed[len(PREFIX) + 1:] if observed.startswith(PREFIX + "/") else observed
        canonical = PREFIX + "/" + relative
        start, end = item.get("StartLine"), item.get("EndLine")
        proof, role, context = "not_proven", "unreviewed", None
        if type(start) is int and type(end) is int and start == end and relative in pinned:
            if relative.startswith("test/") and relative.endswith((".test.js", ".behavior.js")):
                try:
                    context = execution_context.resolve_context(relative, pinned[relative], start, pinned, owned_blobs, nodes)
                    proof, role = "expected_custom_error_assertion", "upstream_js_test"
                except execution_context.ContextError:
                    pass
            elif relative.startswith("test/") and relative.endswith(".json"):
                proof, role = source_proof(repo, canonical, start, end)
                if proof == "ecdsa_public_key_der":
                    context = {"kind": "public_ec_der"}
        result[(canonical, start, end)] = (proof, role, context)
    return result


def build_records(
    report,
    *,
    head,
    commit,
    decisions=None,
    repo=None,
    state=None,
    manifest_sha256=None,
    owned_blobs=None,
    semantic_records=None,
    declared_errors=None,
):
    decisions = [] if decisions is None else decisions
    if not isinstance(decisions, list):
        raise AdjudicationError("decisions must be a list keyed by finding_id")
    by_id = {}
    for decision in decisions:
        sanitized(decision)
        if (
            not isinstance(decision, dict)
            or "finding_id" not in decision
            or decision["finding_id"] in by_id
        ):
            raise AdjudicationError("invalid or duplicate decision")
        if set(decision) - DECISION_FIELDS:
            raise AdjudicationError("unknown decision fields")
        by_id[decision["finding_id"]] = decision
    state = state or {
        "head": head,
        "parent_submodule": PARENT_PREFIX,
        "parent_submodule_commit": PARENT_PIN,
        "parent_submodule_head": PARENT_PIN,
        "parent_submodule_clean": False,
        "submodule": PREFIX,
        "submodule_commit": commit,
        "submodule_head": commit,
        "submodule_clean": False,
    }
    if owned_blobs is None and repo is not None:
        owned_blobs, _ = direct_tree(repo, commit)
    owned_blobs = owned_blobs or {}
    semantic_records = semantic_records or {}
    if repo is not None and declared_errors is None:
        declared_errors = production_declarations(repo, commit)
    try:
        resolved_semantics = production_semantics(repo, report, commit, owned_blobs) if repo is not None else {}
    except (execution_context.ContextError, OSError, subprocess.CalledProcessError, UnicodeError, ValueError):
        # An incomplete or synthetic tree never gains confirmation.
        resolved_semantics = {}
    records = []
    seen = set()
    for item in report:
        path = item.get("File")
        if not isinstance(path, str):
            raise AdjudicationError("missing path")
        if path.startswith("./"):
            path = path[2:]
        base.safe_path(path)
        if path.startswith(PREFIX + "/"):
            relative = path[len(PREFIX) + 1 :]
        else:
            relative = path
            path = PREFIX + "/" + relative
        base.safe_path(relative)
        if repo is not None and relative not in owned_blobs:
            raise AdjudicationError("finding is not owned by direct submodule provenance")
        rule = item.get("RuleID")
        start = item.get("StartLine")
        end = item.get("EndLine")
        if not isinstance(rule, str) or type(start) is not int or type(end) is not int:
            raise AdjudicationError("missing finding identity")
        identifier = base.stable_id(head, commit, path, rule, start, end)
        if identifier in seen:
            raise AdjudicationError("duplicate finding id")
        seen.add(identifier)
        file_hash = base.digest(base.file_bytes(repo, path)) if repo else "0" * 64
        record = dict(
            state,
            finding_id=identifier,
            relative_path=path,
            rule_id=rule,
            line_start=start,
            line_end=end,
            file_sha256=file_hash,
            source_manifest_sha256=manifest_sha256 or "0" * 64,
            file_role="unreviewed",
            source_review="not_proven",
            disposition="unresolved",
            rationale="missing_or_stale_evidence",
            evidence_refs=[],
            reachability={domain: "not_assessed" for domain in sorted(DOMAINS)},
            reviewer_status="pending_review",
            reviewer="pending",
        )
        decision = by_id.get(identifier)
        if decision is not None:
            complete = set(decision) == DECISION_FIELDS
            bound = complete and all(
                decision[key] == record[key]
                for key in IDENTITY | {"source_manifest_sha256"}
            )
            if bound:
                try:
                    if decision["source_review"] == "credential_or_ambiguous_datum":
                        decision = dict(
                            decision,
                            disposition="potential_credential",
                            rationale="credential_or_ambiguous_datum",
                        )
                    validate_record(decision)
                    references_ok = (
                        repo is not None
                        and base.references_valid(repo, decision["evidence_refs"])
                    )
                    proof, role, proof_context = resolved_semantics.get(
                        (path, start, end), ("not_proven", "unreviewed", None)
                    )
                    semantic = semantic_records.get(identifier)
                    semantic_ok = (
                        isinstance(semantic, dict)
                        and set(semantic) == ATTESTATION_RECORD_FIELDS
                        and semantic["finding_id"] == identifier
                        and semantic["relative_path"] == path
                        and semantic["rule_id"] == rule
                        and semantic["line_start"] == start
                        and semantic["line_end"] == end
                        and semantic["file_sha256"] == file_hash
                        and semantic["source_object_id"] == owned_blobs.get(relative, {}).get("object_id")
                        and semantic["classification"] == proof
                        and semantic["verdict"] == "confirmed_noncredential_fixture"
                        and semantic["context"] == proof_context
                    )
                    pinned = (
                        repo is not None
                        and state["parent_submodule_clean"]
                        and state["parent_submodule_head"] == state["parent_submodule_commit"]
                        and state["submodule_clean"]
                        and state["submodule_head"] == commit
                        and pinned_blob(repo, commit, relative)
                        == base.file_bytes(repo, path)
                    )
                    if (
                        decision["disposition"] == "potential_credential"
                        and references_ok
                        and pinned
                    ):
                        record = decision.copy()
                    elif (
                        references_ok
                        and pinned
                        and proof == decision["source_review"]
                        and role == decision["file_role"]
                        and rule == "generic-api-key"
                        and semantic_ok
                    ):
                        record = decision.copy()
                except (
                    AdjudicationError,
                    base.AdjudicationError,
                    OSError,
                    subprocess.CalledProcessError,
                    ValueError,
                ):
                    pass
        records.append(validate_record(record))
    if set(by_id) - seen:
        raise AdjudicationError("unknown decision id")
    return sorted(records, key=lambda item: item["finding_id"])


def approved_gate(records, approved, semantic_records=None):
    semantic_records = semantic_records or {}
    try:
        for record in records:
            validate_record(record)
        for record in records:
            semantic = semantic_records.get(record["finding_id"], {})
            validate_context(semantic.get("context"), record["source_review"])
    except (AdjudicationError, base.AdjudicationError, KeyError, TypeError):
        return False
    ids = {record["finding_id"] for record in records}
    return (
        bool(records)
        and len(ids) == len(records)
        and ids == set(semantic_records)
        and all(
            record["disposition"] == "confirmed_noncredential_fixture"
            and semantic_records[record["finding_id"]]["classification"] == record["source_review"]
            and semantic_records[record["finding_id"]]["verdict"] == "confirmed_noncredential_fixture"
            for record in records
        )
        and base.encoded(records) == base.encoded(approved)
    )


def validate_semantic_attestation(
    repo,
    scanner,
    decisions_path,
    decisions_sha256,
    manifest_sha256,
    state,
    blobs,
    attestation_path,
    attestation_sha256,
    legacy=False,
    attestation_bytes=None,
    decisions_bytes=None,
):
    repo = Path(repo).resolve()
    if not attestation_sha256 or not re.fullmatch(r"[0-9a-f]{64}", attestation_sha256):
        raise AdjudicationError("semantic attestation unavailable")
    if attestation_bytes is None:
        if not attestation_path:
            raise AdjudicationError("semantic attestation unavailable")
        path = Path(attestation_path)
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 524288:
            raise AdjudicationError("semantic attestation unavailable")
        raw = path.read_bytes()
    else:
        raw = bytes(attestation_bytes)
        if not raw or len(raw) > 524288:
            raise AdjudicationError("semantic attestation unavailable")
    if base.digest(raw) != attestation_sha256:
        raise AdjudicationError("semantic attestation digest mismatch")
    document = json.loads(raw, object_pairs_hook=base._pairs)
    record_fields = ATTESTATION_RECORD_FIELDS - ({"context"} if legacy else set())
    if not isinstance(document, dict) or set(document) != ATTESTATION_FIELDS:
        raise AdjudicationError("semantic attestation schema mismatch")
    if (
        document["schema"] != ("m0_3c_r5_semantic_attestation" if legacy else "m0_3c_r9_semantic_attestation")
        or document["head"] != state["head"]
        or document["parent_submodule_commit"] != state["parent_submodule_commit"]
        or document["submodule_commit"] != state["submodule_commit"]
        or document["decisions_sha256"] != decisions_sha256
        or document["source_manifest_sha256"] != manifest_sha256
        or document["scanner_sha256"] != SCANNER_SHA256
        or document["scanner_version"] != "8.30.1"
    ):
        raise AdjudicationError("semantic attestation binding mismatch")
    verifier = document["verifier"]
    if not isinstance(verifier, dict) or set(verifier) != ATTESTATION_VERIFIER_FIELDS:
        raise AdjudicationError("semantic verifier schema mismatch")
    oracle_path = repo / SEMANTIC_ORACLE_REL
    expected_oracle_sha = (
        "cffbba33f03c8b36a9b0238522360ed67638b6d273831ed9e4c88ee95d2a3677"
        if legacy else base.digest(oracle_path.read_bytes())
    )
    if (
        verifier["name"] != ("m0_3c_semantic_oracle_v1" if legacy else "m0_3c_semantic_oracle_v3")
        or verifier["path"] != SEMANTIC_ORACLE_REL
        or verifier["sha256"] != expected_oracle_sha
        or verifier["python_path"] != str(PINNED_PYTHON.resolve())
        or verifier["python_sha256"] != base.digest(PINNED_PYTHON.resolve().read_bytes())
    ):
        raise AdjudicationError("semantic verifier binding mismatch")
    probe = subprocess.run(
        [
            str(PINNED_PYTHON),
            "-c",
            (
                "import cryptography,hashlib,json,platform,pathlib;"
                "p=pathlib.Path(cryptography.__file__).resolve();"
                "print(json.dumps({'python_version':'Python '+platform.python_version(),"
                "'cryptography_version':cryptography.__version__,"
                "'cryptography_module_path':str(p),"
                "'cryptography_module_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},sort_keys=True))"
            ),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    observed_verifier = json.loads(probe.stdout, object_pairs_hook=base._pairs)
    for key in (
        "python_version",
        "cryptography_version",
        "cryptography_module_path",
        "cryptography_module_sha256",
    ):
        if verifier[key] != observed_verifier[key]:
            raise AdjudicationError("semantic dependency binding mismatch")
    decision_raw = bytes(decisions_bytes) if decisions_bytes is not None else Path(decisions_path).read_bytes()
    decision_document = json.loads(decision_raw, object_pairs_hook=base._pairs)
    decisions = decision_document["records"]
    decision_map = {record["finding_id"]: record for record in decisions}
    records = document["records"]
    if not isinstance(records, list) or len(records) != 158:
        raise AdjudicationError("semantic attestation record count mismatch")
    result = {}
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != record_fields
            or record.get("finding_id") in result
        ):
            raise AdjudicationError("semantic attestation record schema mismatch")
        identifier = record["finding_id"]
        decision = decision_map.get(identifier)
        relative = record["relative_path"]
        if (
            decision is None
            or relative != decision["relative_path"]
            or record["rule_id"] != decision["rule_id"]
            or record["line_start"] != decision["line_start"]
            or record["line_end"] != decision["line_end"]
            or record["file_sha256"] != decision["file_sha256"]
            or record["classification"] != decision["source_review"]
            or record["verdict"] != "confirmed_noncredential_fixture"
            or not relative.startswith(PREFIX + "/")
            or record["source_object_id"]
            != blobs.get(relative[len(PREFIX) + 1 :], {}).get("object_id")
        ):
            raise AdjudicationError("semantic attestation record binding mismatch")
        result[identifier] = record
    if set(result) != set(decision_map):
        raise AdjudicationError("semantic attestation exact set mismatch")
    if not legacy:
        report = [
            {"File": row["relative_path"], "RuleID": row["rule_id"], "StartLine": row["line_start"], "EndLine": row["line_end"]}
            for row in decisions
        ]
        expected_contexts = production_semantics(repo, report, state["submodule_commit"], blobs)
        for record in result.values():
            expected = expected_contexts[(record["relative_path"], record["line_start"], record["line_end"])][2]
            validate_context(record["context"], record["classification"])
            if record["context"] != expected:
                raise AdjudicationError("semantic execution context mismatch")
    return result


def _stage_direct_tree(repo, commit, destination, blobs):
    submodule = Path(repo) / PREFIX
    for relative, metadata in sorted(blobs.items()):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base.git(submodule, "show", f"{commit}:{relative}"))
        target.chmod(0o755 if metadata["mode"] == "100755" else 0o644)


def scan_direct_tree(repo, scanner, state):
    repo = Path(repo)
    scanner = Path(scanner)
    blobs, gitlinks = direct_tree(repo, state["submodule_commit"])
    raw_parent = None
    command = None
    scanner_exit = None
    report = None
    with tempfile.TemporaryDirectory(prefix="m03c-raw-") as temporary:
        os.chmod(temporary, 0o700)
        raw_parent = temporary
        staged = Path(temporary) / "source"
        staged.mkdir(mode=0o700)
        _stage_direct_tree(repo, state["submodule_commit"], staged, blobs)
        raw_path = Path(temporary) / "report.json"
        command = [
            str(scanner),
            "dir",
            ".",
            "--config",
            str(repo / ".gitleaks.toml"),
            "--redact=100",
            "--report-format",
            "json",
            "--report-path",
            str(raw_path),
            "--exit-code",
            "1",
            "--no-banner",
        ]
        process = subprocess.run(command, cwd=staged, capture_output=True)
        scanner_exit = process.returncode
        if scanner_exit not in {0, 1}:
            raise AdjudicationError("scanner failure")
        report = base.read_json(raw_path)
        if not isinstance(report, list) or bool(report) != (scanner_exit == 1):
            raise AdjudicationError("scanner result inconsistency")
    if raw_parent is None or Path(raw_parent).exists():
        raise AdjudicationError("raw report directory was not deleted")
    return report, blobs, gitlinks, command, scanner_exit


def publish(output, identities, records, metadata, decisions, manifest, blobs, gitlinks):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise AdjudicationError("output collision")
    for record in identities + records:
        validate_record(record)
    safe_decisions = []
    for decision in decisions:
        try:
            validate_record(decision)
            if decision in records:
                safe_decisions.append(decision)
        except (AdjudicationError, base.AdjudicationError):
            continue
    stage = Path(tempfile.mkdtemp(prefix=".m03c-publish-", dir=output.parent))
    try:
        totals = {
            disposition: sum(
                record["disposition"] == disposition for record in records
            )
            for disposition in sorted(ALLOWED)
        }
        domain_results = {
            domain: (
                "absent"
                if records and all(record["reachability"][domain] == "absent" for record in records)
                else "not_all_absent"
            )
            for domain in sorted(DOMAINS)
        }
        artifacts = {
            "findings.json": {
                "schema": "m0_3c_r1_findings",
                "records": identities,
            },
            "decisions.json": {
                "schema": "m0_3c_r1_decisions",
                "records": safe_decisions,
            },
            "ledger.json": {
                "schema": "m0_3c_r1_ledger",
                "records": records,
            },
            "summary.json": {
                "schema": "m0_3c_r1_summary",
                "disposition_totals": totals,
                "observed_count": len(records),
                "path_count": len({record["relative_path"] for record in records}),
            },
            "record.json": metadata,
            "reachability.json": {
                "schema": "m0_3c_r1_reachability",
                "source_manifest_sha256": metadata["source_manifest_sha256"],
                "domains": domain_results,
                "reviewed_path_count": len({record["relative_path"] for record in records}),
            },
            "source-manifest.json": manifest,
            "excluded-gitlinks.json": {
                "schema": "m0_3c_r1_excluded_gitlinks",
                "gitlinks": [
                    {"path": path, "commit": commit}
                    for path, commit in sorted(gitlinks.items())
                ],
            },
            "owned-blobs.json": {
                "schema": "m0_3c_r1_owned_blobs",
                "blobs": [
                    {
                        "path": path,
                        "object_id": details["object_id"],
                        "mode": details["mode"],
                    }
                    for path, details in sorted(blobs.items())
                ],
            },
        }
        for name, value in artifacts.items():
            (stage / name).write_bytes(base.encoded(value))
        (stage / "source-checksums.sha256").write_text(
            "".join(
                f"{base.digest((stage / name).read_bytes())}  {name}\n"
                for name in sorted(artifacts)
            ),
            encoding="utf-8",
        )
        os.rename(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def run_adjudication(
    repo,
    scanner,
    output,
    decisions_path=None,
    approved_sha256=None,
    semantic_attestation_path=None,
    semantic_attestation_sha256=None,
):
    repo = Path(repo).resolve()
    scanner = Path(scanner).resolve()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise AdjudicationError("invalid output destination")
    before = provenance(repo)
    if before["parent_submodule_commit"] != PARENT_PIN or before["parent_submodule_head"] != PARENT_PIN or not before["parent_submodule_clean"]:
        raise AdjudicationError("parent submodule is not at a clean pin")
    if before["submodule_commit"] != PIN or before["submodule_head"] != PIN or not before["submodule_clean"]:
        raise AdjudicationError("target submodule is not at a clean pin")
    if base.digest(scanner.read_bytes()) != SCANNER_SHA256:
        raise AdjudicationError("scanner digest mismatch")
    version = subprocess.run(
        [str(scanner), "version"], capture_output=True, check=True
    ).stdout.decode().strip()
    if version != "8.30.1":
        raise AdjudicationError("scanner version mismatch")
    manifest = base.source_manifest(repo)
    manifest_sha256 = base.digest(base.encoded(manifest))
    decision_bytes = Path(decisions_path).read_bytes() if decisions_path else b"[]"
    decision_document = json.loads(decision_bytes, object_pairs_hook=base._pairs)
    if isinstance(decision_document, dict):
        if (
            set(decision_document) != {"schema", "records"}
            or decision_document.get("schema") != "m0_3c_r1_decisions"
        ):
            raise AdjudicationError("invalid decisions document")
        decisions = decision_document["records"]
    else:
        decisions = decision_document
    if not isinstance(decisions, list):
        raise AdjudicationError("invalid decisions document")
    sanitized(decisions)
    if any(
        not isinstance(decision, dict)
        or "finding_id" not in decision
        or set(decision) - DECISION_FIELDS
        for decision in decisions
    ):
        raise AdjudicationError("invalid decision fields")
    if len({decision["finding_id"] for decision in decisions}) != len(decisions):
        raise AdjudicationError("duplicate decision")
    started = datetime.now(timezone.utc).isoformat()
    tick = time.monotonic()
    report, blobs, gitlinks, command, scanner_exit = scan_direct_tree(
        repo, scanner, before
    )
    current = provenance(repo)
    if before != current or manifest != base.source_manifest(repo):
        current["parent_submodule_clean"] = False
        current["submodule_clean"] = False
    semantic_records = {}
    semantic_valid = False
    if decisions_path:
        try:
            semantic_records = validate_semantic_attestation(
                repo,
                scanner,
                decisions_path,
                base.digest(decision_bytes),
                manifest_sha256,
                current,
                blobs,
                semantic_attestation_path,
                semantic_attestation_sha256,
            )
            semantic_valid = True
        except (
            AdjudicationError,
            base.AdjudicationError,
            OSError,
            subprocess.CalledProcessError,
            ValueError,
            KeyError,
            TypeError,
        ):
            semantic_records = {}
    declared_errors = production_declarations(repo, current["submodule_commit"])
    identities = build_records(
        report,
        head=current["head"],
        commit=current["submodule_commit"],
        repo=repo,
        state=current,
        manifest_sha256=manifest_sha256,
        owned_blobs=blobs,
        declared_errors=declared_errors,
    )
    known_ids = {record["finding_id"] for record in identities}
    selected = [
        decision for decision in decisions
        if decision.get("finding_id") in known_ids
    ]
    records = build_records(
        report,
        head=current["head"],
        commit=current["submodule_commit"],
        decisions=selected,
        repo=repo,
        state=current,
        manifest_sha256=manifest_sha256,
        owned_blobs=blobs,
        semantic_records=semantic_records,
        declared_errors=declared_errors,
    )
    after = provenance(repo)
    if after != current or manifest != base.source_manifest(repo):
        after["parent_submodule_clean"] = False
        after["submodule_clean"] = False
        current = after
        records = build_records(
            report,
            head=current["head"],
            commit=current["submodule_commit"],
            repo=repo,
            state=current,
            manifest_sha256=manifest_sha256,
            owned_blobs=blobs,
            semantic_records={},
            declared_errors=declared_errors,
        )
        semantic_valid = False
    del report
    passed = False
    if (
        approved_sha256
        and decisions_path
        and base.digest(decision_bytes) == approved_sha256
    ):
        passed = semantic_valid and approved_gate(records, decisions, semantic_records)
    metadata = {
        "schema": "m0_3c_r7_run",
        **current,
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "duration_milliseconds": int((time.monotonic() - tick) * 1000),
        "command": command,
        "scanner_version": version,
        "scanner_sha256": SCANNER_SHA256,
        "scanner_exit": scanner_exit,
        "adjudication_exit": 0 if passed else 1,
        "source_manifest_sha256": manifest_sha256,
        "raw_removed": True,
        "approved_decisions_sha256": approved_sha256,
        "independent_review": False,
        "input_decisions_sha256": base.digest(decision_bytes),
        "semantic_attestation_sha256": (
            semantic_attestation_sha256 if semantic_valid else None
        ),
        "semantic_attestation_valid": semantic_valid,
        "unknown_decision_count": len(decisions) - len(selected),
        "promotion_gates": "open",
        "direct_blob_count": len(blobs),
        "excluded_gitlink_count": len(gitlinks),
    }
    publish(output, identities, records, metadata, decisions, manifest, blobs, gitlinks)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("repo", "scanner", "output"):
        parser.add_argument("--" + argument, required=True)
    parser.add_argument("--decisions")
    parser.add_argument("--approved-sha256")
    parser.add_argument("--semantic-attestation")
    parser.add_argument("--semantic-attestation-sha256")
    args = parser.parse_args()
    try:
        return run_adjudication(
            args.repo,
            args.scanner,
            args.output,
            args.decisions,
            args.approved_sha256,
            args.semantic_attestation,
            args.semantic_attestation_sha256,
        )
    except Exception as exc:
        print("adjudication=failure type=" + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
