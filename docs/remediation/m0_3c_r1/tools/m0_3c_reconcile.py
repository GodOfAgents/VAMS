#!/usr/bin/env python3
"""Independent executable reconciliation for the M0.3c direct tranche.

This file deliberately does not import the adjudicator. It creates its scanner
input from direct-commit blobs, deletes the raw report, and emits only counts
and non-sensitive proof categories.
"""
from __future__ import annotations

import argparse
import cryptography
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

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
SCANNER_SHA256 = "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509"
DOMAINS = {
    "production_compilation",
    "deployment",
    "runtime",
    "gateway",
    "frontend",
    "credential_loading",
    "ci_execution",
}
FORBIDDEN = {
    "secret",
    "match",
    "fingerprint",
    "entropy",
    "raw",
    "rawmatch",
    "sourceline",
    "snippet",
    "value",
    "password",
    "token",
    "privatekey",
    "credential",
}


class ReconciliationError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ReconciliationError("duplicate JSON key")
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs)


def git(directory, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=directory,
        capture_output=True,
        check=True,
    ).stdout


def safe_path(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,220}", value):
        raise ReconciliationError("unsafe path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ReconciliationError("noncanonical path")
    return value


def reject_sensitive(value):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", key.lower()) if isinstance(key, str) else ""
            if not isinstance(key, str) or normalized in FORBIDDEN:
                raise ReconciliationError("forbidden durable field")
            reject_sensitive(child)
    elif isinstance(value, list):
        for child in value:
            reject_sensitive(child)
    elif isinstance(value, str) and len(value) > 220:
        raise ReconciliationError("unsafe durable string")
    elif value is not None and type(value) not in {str, bool, int}:
        raise ReconciliationError("unsafe durable type")


def stable_id(head, commit, path, rule, start, end):
    material = "|".join((head, commit, path, rule, str(start), str(end)))
    return digest(material.encode())


def state(repo):
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    parent_tree = git(repo, "ls-tree", "HEAD", "--", PARENT_PREFIX).decode().split()
    parent_index = git(repo, "ls-files", "--stage", "--", PARENT_PREFIX).decode().split()
    if len(parent_tree) != 4 or parent_tree[:2] != ["160000", "commit"]:
        raise ReconciliationError("missing parent gitlink")
    if len(parent_index) != 4 or parent_index[0] != "160000" or parent_index[1] != parent_tree[2]:
        raise ReconciliationError("parent index gitlink mismatch")
    parent = repo / PARENT_PREFIX
    parent_head = git(parent, "rev-parse", "HEAD").decode().strip()
    parent_dirty = git(parent, "status", "--porcelain", "--untracked-files=all", "--ignored")
    target_tree = git(parent, "ls-tree", parent_tree[2], "--", TARGET_IN_PARENT).decode().split()
    target_index = git(parent, "ls-files", "--stage", "--", TARGET_IN_PARENT).decode().split()
    if len(target_tree) != 4 or target_tree[:2] != ["160000", "commit"]:
        raise ReconciliationError("missing target gitlink")
    if len(target_index) != 4 or target_index[0] != "160000" or target_index[1] != target_tree[2]:
        raise ReconciliationError("target index gitlink mismatch")
    target = repo / PREFIX
    target_head = git(target, "rev-parse", "HEAD").decode().strip()
    target_dirty = git(target, "status", "--porcelain", "--untracked-files=all", "--ignored")
    if parent_tree[2] != PARENT_PIN or parent_head != PARENT_PIN or parent_dirty:
        raise ReconciliationError("parent submodule is not at clean pin")
    if target_tree[2] != PIN or target_head != PIN or target_dirty:
        raise ReconciliationError("target submodule is not at clean pin")
    return head, parent_tree[2], target_tree[2]


def tree(repo, commit):
    submodule = repo / PREFIX
    entries = git(submodule, "ls-tree", "-r", "-z", commit)
    blobs = {}
    gitlinks = {}
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode().split()
        name = safe_path(raw_name.decode())
        if mode == "160000" and object_type == "commit":
            gitlinks[name] = object_id
        elif object_type == "blob" and mode in {"100644", "100755"}:
            blobs[name] = (object_id, mode)
        else:
            raise ReconciliationError("unsupported tree object")
    if gitlinks != CHILD_GITLINKS:
        raise ReconciliationError("child provenance mismatch")
    return blobs, gitlinks


def first_party_manifest(repo):
    names = git(
        repo,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ).decode().split("\0")
    result = {}
    for name in sorted(set(names) - {""}):
        if (
            name.startswith(("docs/", "codex-skills/", ".codex/", "contracts/lib/"))
            or name.endswith(".md")
        ):
            continue
        path = repo / name
        if path.is_dir():
            continue
        result[name] = digest(path.read_bytes())
    return result


def reachability_references(repo, canonical_paths):
    surfaces = {
        "production_compilation": (
            "contracts/src",
            "contracts/foundry.toml",
            "contracts/remappings.txt",
        ),
        "deployment": ("contracts/script", "cdk-deployment"),
        "runtime": ("neuron",),
        "gateway": ("gateway",),
        "frontend": ("frontend-vite",),
        "credential_loading": (
            "gateway",
            "neuron",
            "contracts/script",
            "frontend-vite",
        ),
        "ci_execution": (".github/workflows",),
    }
    encoded_paths = [path.encode() for path in sorted(canonical_paths)]
    counts = {}
    for domain, roots in surfaces.items():
        names = git(
            repo,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            *roots,
        ).decode().split("\0")
        references = 0
        for name in sorted(set(names) - {""}):
            path = repo / name
            if not path.is_file() or PREFIX in name:
                continue
            data = path.read_bytes()
            references += sum(candidate in data for candidate in encoded_paths)
        counts[domain] = references
    if set(counts) != DOMAINS or any(counts.values()):
        raise ReconciliationError("reviewed fixture is reachable from a live surface")
    return counts


def strip_js_space(line):
    output, quote, escaped = [], None, False
    for character in line.strip():
        if quote:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
        elif character in {"'", '"', "\x60"}:
            quote = character
            output.append(character)
        elif not character.isspace():
            output.append(character)
    if quote is not None:
        raise ReconciliationError("unterminated JavaScript literal")
    return "".join(output)


def split_arguments(value):
    quote, escaped = None, False
    for index, character in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
        elif character in {"'", '"', "\x60"}:
            quote = character
        elif character == ",":
            return value[:index], value[index + 1 :]
    raise ReconciliationError("missing argument delimiter")


def expected_error_semantics(line, declared_errors):
    compact = strip_js_space(line)
    prefix = ".to.be.revertedWithCustomError("
    if not compact.startswith(prefix) or not compact.endswith(")"):
        return False
    first, second = split_arguments(compact[len(prefix) : -1])
    if re.fullmatch(r"this\.[A-Za-z_$][A-Za-z0-9_$]*", first) is None:
        return False
    if len(second) < 3 or second[0] not in {"'", '"', "\x60"} or second[-1] != second[0]:
        return False
    name = second[1:-1]
    return bool(
        re.fullmatch(r"ERC[0-9]+[A-Za-z][A-Za-z0-9]*", name)
        and name in declared_errors
    )


def public_der_semantics(data, line_number):
    lines = data.decode("utf-8").splitlines()
    if not 1 <= line_number <= len(lines):
        return False
    fragment = lines[line_number - 1].strip()
    if fragment.endswith(","):
        fragment = fragment[:-1]
    try:
        item = json.loads("{" + fragment + "}")
    except json.JSONDecodeError:
        return False
    if set(item) != {"keyDer"} or not isinstance(item["keyDer"], str):
        return False
    try:
        der = bytes.fromhex(item["keyDer"])
    except ValueError:
        return False
    document = json.loads(data)
    groups = [
        group for group in document.get("testGroups", [])
        if group.get("keyDer") == item["keyDer"]
    ]
    if (
        document.get("algorithm") != "ECDSA"
        or not groups
        or any(group.get("type") != "EcdsaP1363Verify" for group in groups)
        or any(group.get("key", {}).get("type") != "EcPublicKey" for group in groups)
    ):
        return False
    try:
        parsed = serialization.load_der_public_key(der)
    except (ValueError, TypeError):
        return False
    return isinstance(parsed, ec.EllipticCurvePublicKey)


def classify(data, path, line_number, declared_errors):
    lines = data.decode("utf-8").splitlines()
    if not 1 <= line_number <= len(lines):
        return "not_proven"
    if path.startswith(PREFIX + "/test/") and path.endswith((".test.js", ".behavior.js")):
        if expected_error_semantics(lines[line_number - 1], declared_errors):
            return "expected_custom_error_assertion"
    if path.startswith(PREFIX + "/test/") and path.endswith(".json"):
        if public_der_semantics(data, line_number):
            return "ecdsa_public_key_der"
    return "not_proven"


def run(repo, scanner, decisions_path):
    repo = Path(repo).resolve()
    scanner = Path(scanner).resolve()
    if digest(scanner.read_bytes()) != SCANNER_SHA256:
        raise ReconciliationError("scanner digest mismatch")
    version = subprocess.run(
        [str(scanner), "version"], capture_output=True, check=True
    ).stdout.decode().strip()
    if version != "8.30.1":
        raise ReconciliationError("scanner version mismatch")
    head, parent_commit, commit = state(repo)
    blobs, gitlinks = tree(repo, commit)
    target_bytes = {}
    manifest_hash = digest(encoded(first_party_manifest(repo)))
    raw_parent = None
    with tempfile.TemporaryDirectory(prefix="m03c-independent-") as temporary:
        os.chmod(temporary, 0o700)
        raw_parent = temporary
        source = Path(temporary) / "source"
        source.mkdir(mode=0o700)
        for relative, (_, mode) in sorted(blobs.items()):
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = git(repo / PREFIX, "show", f"{commit}:{relative}")
            target_bytes[relative] = data
            target.write_bytes(data)
            target.chmod(0o755 if mode == "100755" else 0o644)
        report_path = Path(temporary) / "report.json"
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
            str(report_path),
            "--exit-code",
            "1",
            "--no-banner",
        ]
        scanner_cwd = str(source)
        process = subprocess.run(command, cwd=source, capture_output=True)
        if process.returncode != 1:
            raise ReconciliationError("unexpected scanner exit")
        report = load(report_path)
        declared_errors = set()
        error_pattern = re.compile(rb"\berror\s+(ERC[0-9]+[A-Za-z][A-Za-z0-9]*)\s*\(")
        for owned_path, owned_data in target_bytes.items():
            if owned_path.startswith("contracts/") and owned_path.endswith(".sol"):
                declared_errors.update(item.decode() for item in error_pattern.findall(owned_data))
        scanner_identities = {}
        proof_counts = Counter()
        for finding in report:
            relative = finding.get("File")
            if isinstance(relative, str) and relative.startswith("./"):
                relative = relative[2:]
            safe_path(relative)
            if relative not in blobs:
                raise ReconciliationError("scanner finding outside direct blobs")
            canonical = PREFIX + "/" + relative
            rule = finding.get("RuleID")
            start = finding.get("StartLine")
            end = finding.get("EndLine")
            if rule != "generic-api-key" or type(start) is not int or start != end:
                raise ReconciliationError("unexpected scanner identity")
            identifier = stable_id(head, commit, canonical, rule, start, end)
            if identifier in scanner_identities:
                raise ReconciliationError("duplicate scanner identity")
            scanner_identities[identifier] = (canonical, start)
            proof_counts[classify(target_bytes[relative], canonical, start, declared_errors)] += 1
        del report
    raw_removed = raw_parent is not None and not Path(raw_parent).exists()
    if not raw_removed:
        raise ReconciliationError("raw report retained")
    document = load(decisions_path)
    decisions = document.get("records") if isinstance(document, dict) else document
    if not isinstance(decisions, list):
        raise ReconciliationError("invalid decisions")
    reject_sensitive(decisions)
    if len(decisions) != len(scanner_identities):
        raise ReconciliationError("decision count mismatch")
    seen = set()
    for decision in decisions:
        identifier = decision.get("finding_id")
        if identifier in seen or identifier not in scanner_identities:
            raise ReconciliationError("decision set mismatch")
        seen.add(identifier)
        canonical, line_number = scanner_identities[identifier]
        relative = canonical[len(PREFIX) + 1 :]
        expected = {
            "head": head,
            "parent_submodule": PARENT_PREFIX,
            "parent_submodule_commit": parent_commit,
            "parent_submodule_head": parent_commit,
            "parent_submodule_clean": True,
            "submodule": PREFIX,
            "submodule_commit": commit,
            "submodule_head": commit,
            "submodule_clean": True,
            "relative_path": canonical,
            "rule_id": "generic-api-key",
            "line_start": line_number,
            "line_end": line_number,
            "file_sha256": digest((repo / canonical).read_bytes()),
            "source_manifest_sha256": manifest_hash,
        }
        if any(decision.get(key) != value for key, value in expected.items()):
            raise ReconciliationError("decision binding mismatch")
        if git(repo / PREFIX, "show", f"{commit}:{relative}") != (repo / canonical).read_bytes():
            raise ReconciliationError("working source differs from pin")
        proof = classify(target_bytes[relative], canonical, line_number, declared_errors)
        if proof == "not_proven" or decision.get("source_review") != proof:
            raise ReconciliationError("source semantics mismatch")
        if decision.get("disposition") != "confirmed_noncredential_fixture":
            raise ReconciliationError("non-confirmed disposition")
        if decision.get("rationale") != proof:
            raise ReconciliationError("rationale mismatch")
        if decision.get("reviewer_status") != "accepted":
            raise ReconciliationError("review not accepted")
        if set(decision.get("reachability", {}).keys()) != DOMAINS:
            raise ReconciliationError("reachability schema mismatch")
        if set(decision["reachability"].values()) != {"absent"}:
            raise ReconciliationError("reachable or unassessed finding")
        refs = decision.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise ReconciliationError("missing evidence reference")
        for ref in refs:
            path = safe_path(ref.get("path"))
            if digest((repo / path).read_bytes()) != ref.get("sha256"):
                raise ReconciliationError("stale evidence reference")
    reviewed_paths = {path for path, _ in scanner_identities.values()}
    if any(
        not path.startswith(PREFIX + "/test/")
        or not path.endswith((".test.js", ".behavior.js", ".json"))
        for path in reviewed_paths
    ):
        raise ReconciliationError("finding lacks deterministic fixture role")
    reachability = reachability_references(repo, reviewed_paths)
    expected_counts = {
        "ecdsa_public_key_der": 75,
        "expected_custom_error_assertion": 83,
    }
    if len(seen) != 158 or proof_counts != Counter(expected_counts):
        raise ReconciliationError("unexpected direct finding classes")
    return {
        "schema": "m0_3c_r3_independent_reconciliation",
        "scanner_exit": 1,
        "scanner_command": command,
        "scanner_cwd": scanner_cwd,
        "finding_count": len(seen),
        "path_count": len({path for path, _ in scanner_identities.values()}),
        "proof_counts": expected_counts,
        "direct_blob_count": len(blobs),
        "excluded_gitlink_count": len(gitlinks),
        "child_gitlinks_excluded": gitlinks == CHILD_GITLINKS,
        "reachability_reference_counts": reachability,
        "raw_removed": raw_removed,
        "head": head,
        "parent_submodule_commit": parent_commit,
        "submodule_commit": commit,
        "semantic_oracles": {
            "javascript": "bounded_token_parser_v1",
            "der": "cryptography_load_der_public_key",
            "der_library_version": cryptography.__version__,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--scanner", required=True)
    parser.add_argument("--decisions", required=True)
    args = parser.parse_args()
    try:
        result = run(args.repo, args.scanner, args.decisions)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "m0_3c_r3_independent_reconciliation",
                    "status": "failure",
                    "type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
