#!/usr/bin/env python3
"""M0.3b-R1 direct upgradeable-submodule adjudication.

The scanner input is constructed from blobs owned by the pinned direct Git
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
import m0_3a_adjudicator as base

PREFIX = "contracts/lib/openzeppelin-contracts-upgradeable"
PIN = "aa677e9d28ed78fc427ec47ba2baef2030c58e7c"
NESTED_OPENZEPPELIN = "lib/openzeppelin-contracts"
NESTED_OPENZEPPELIN_PIN = "fcbae5394ae8ad52d8e580a3477db99814b9d565"
SCANNER_SHA256 = base.SCANNER_SHA256
ALLOWED = base.ALLOWED
DOMAINS = base.DOMAINS
PROOF_ROLES = {
    "expected_custom_error_assertion": "upstream_js_test",
    "ecdsa_public_key_der": "upstream_public_vector",
    "erc7201_storage_slot_constant": "upstream_storage_slot_constant",
}
PROOFS = set(PROOF_ROLES)
RATIONALES = PROOFS | {
    "missing_or_stale_evidence",
    "credential_or_ambiguous_datum",
    "review_incomplete",
}
IDENTITY = base.IDENTITY
DECISION_FIELDS = base.DECISION_FIELDS


class AdjudicationError(base.AdjudicationError):
    pass


def validate_record(record):
    base.sanitized(record)
    if not isinstance(record, dict) or set(record) != DECISION_FIELDS:
        raise AdjudicationError("record schema mismatch")
    if record["disposition"] not in ALLOWED or record["rationale"] not in RATIONALES:
        raise AdjudicationError("invalid disposition or rationale")
    if record["submodule"] != PREFIX or not record["relative_path"].startswith(PREFIX + "/"):
        raise AdjudicationError("outside direct tranche")
    if any(not re.fullmatch(r"[0-9a-f]{40}", record[key]) for key in ("head", "submodule_commit", "submodule_head")):
        raise AdjudicationError("invalid commit")
    for key in ("finding_id", "file_sha256", "source_manifest_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", record[key]):
            raise AdjudicationError("invalid sha256")
    if type(record["submodule_clean"]) is not bool:
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
    tree = base.git(repo, "ls-tree", "HEAD", "--", PREFIX).decode().split()
    index = base.git(repo, "ls-files", "--stage", "--", PREFIX).decode().split()
    if (
        len(tree) != 4
        or tree[:2] != ["160000", "commit"]
        or len(index) != 4
        or index[0] != "160000"
    ):
        raise AdjudicationError("missing direct gitlink")
    commit = tree[2]
    submodule = repo / PREFIX
    submodule_head = base.git(submodule, "rev-parse", "HEAD").decode().strip()
    status = base.git(
        submodule,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--ignored",
    )
    clean = not status and index[1] == commit
    return {
        "head": head,
        "submodule": PREFIX,
        "submodule_commit": commit,
        "submodule_head": submodule_head,
        "submodule_clean": clean,
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
    if gitlinks.get(NESTED_OPENZEPPELIN) != NESTED_OPENZEPPELIN_PIN:
        raise AdjudicationError("nested OpenZeppelin provenance mismatch")
    return blobs, gitlinks


def pinned_blob(repo, commit, relative_path):
    base.safe_path(relative_path)
    return base.git(Path(repo) / PREFIX, "show", f"{commit}:{relative_path}")


def _erc7201_proof(lines, index):
    if index < 1:
        return False
    comment = lines[index - 1].strip()
    line = lines[index].strip()
    comment_match = re.fullmatch(
        r'// keccak256\(abi\.encode\(uint256\(keccak256\("([A-Za-z0-9_.]+)"\)\) - 1\)\) & ~bytes32\(uint256\(0xff\)\)',
        comment,
    )
    constant_match = re.fullmatch(
        r"bytes32 private constant [A-Za-z][A-Za-z0-9]*StorageLocation = 0x([0-9a-f]{64});",
        line,
    )
    if not comment_match or not constant_match:
        return False
    try:
        from eth_hash.auto import keccak
    except ImportError as exc:
        raise AdjudicationError("keccak verifier unavailable") from exc
    namespace_hash = int.from_bytes(keccak(comment_match.group(1).encode()), "big")
    encoded_namespace = ((namespace_hash - 1) % (1 << 256)).to_bytes(32, "big")
    expected = int.from_bytes(keccak(encoded_namespace), "big") & ~0xFF
    return constant_match.group(1) == f"{expected:064x}"


def source_proof(repo, path, start, end):
    data = base.file_bytes(Path(repo), path)
    lines = data.decode("utf-8").splitlines()
    if start != end or not 1 <= start <= len(lines):
        return "not_proven", "unreviewed"
    line = lines[start - 1]
    if path.startswith(PREFIX + "/test/") and path.endswith((".test.js", ".behavior.js")):
        match = re.fullmatch(
            r"\s*\.to\.be\.revertedWithCustomError\(this\.[A-Za-z][A-Za-z0-9]*, (['\x60])(ERC[0-9]+[A-Za-z]+)\1\)\s*",
            line,
        )
        if match:
            return "expected_custom_error_assertion", "upstream_js_test"
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
    if path.startswith(PREFIX + "/contracts/") and path.endswith(".sol"):
        if _erc7201_proof(lines, start - 1):
            return "erc7201_storage_slot_constant", "upstream_storage_slot_constant"
    return "not_proven", "unreviewed"


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
):
    decisions = [] if decisions is None else decisions
    if not isinstance(decisions, list):
        raise AdjudicationError("decisions must be a list keyed by finding_id")
    by_id = {}
    for decision in decisions:
        base.sanitized(decision)
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
        "submodule": PREFIX,
        "submodule_commit": commit,
        "submodule_head": commit,
        "submodule_clean": False,
    }
    if owned_blobs is None and repo is not None:
        owned_blobs, _ = direct_tree(repo, commit)
    owned_blobs = owned_blobs or {}
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
                    proof, role = (
                        source_proof(repo, path, start, end)
                        if repo is not None
                        else ("not_proven", "unreviewed")
                    )
                    pinned = (
                        repo is not None
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


def approved_gate(records, approved):
    for record in records:
        validate_record(record)
    return (
        bool(records)
        and len({record["finding_id"] for record in records}) == len(records)
        and all(
            record["disposition"] == "confirmed_noncredential_fixture"
            for record in records
        )
        and base.encoded(records) == base.encoded(approved)
    )


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
    with tempfile.TemporaryDirectory(prefix="m03b-raw-") as temporary:
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


def publish(output, identities, records, metadata, decisions, manifest, gitlinks):
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
    stage = Path(tempfile.mkdtemp(prefix=".m03b-publish-", dir=output.parent))
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
                "schema": "m0_3b_r1_findings",
                "records": identities,
            },
            "decisions.json": {
                "schema": "m0_3b_r1_decisions",
                "records": safe_decisions,
            },
            "ledger.json": {
                "schema": "m0_3b_r1_ledger",
                "records": records,
            },
            "summary.json": {
                "schema": "m0_3b_r1_summary",
                "disposition_totals": totals,
                "observed_count": len(records),
                "path_count": len({record["relative_path"] for record in records}),
            },
            "record.json": metadata,
            "reachability.json": {
                "schema": "m0_3b_r1_reachability",
                "source_manifest_sha256": metadata["source_manifest_sha256"],
                "domains": domain_results,
                "reviewed_path_count": len({record["relative_path"] for record in records}),
            },
            "source-manifest.json": manifest,
            "excluded-gitlinks.json": {
                "schema": "m0_3b_r1_excluded_gitlinks",
                "gitlinks": [
                    {"path": path, "commit": commit}
                    for path, commit in sorted(gitlinks.items())
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


def run_adjudication(repo, scanner, output, decisions_path=None, approved_sha256=None):
    repo = Path(repo).resolve()
    scanner = Path(scanner).resolve()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise AdjudicationError("invalid output destination")
    before = provenance(repo)
    if before["submodule_commit"] != PIN:
        raise AdjudicationError("unexpected direct gitlink")
    if before["submodule_head"] != PIN or not before["submodule_clean"]:
        raise AdjudicationError("direct submodule is not at a clean pin")
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
            or decision_document.get("schema") != "m0_3b_r1_decisions"
        ):
            raise AdjudicationError("invalid decisions document")
        decisions = decision_document["records"]
    else:
        decisions = decision_document
    if not isinstance(decisions, list):
        raise AdjudicationError("invalid decisions document")
    base.sanitized(decisions)
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
        current["submodule_clean"] = False
    identities = build_records(
        report,
        head=current["head"],
        commit=current["submodule_commit"],
        repo=repo,
        state=current,
        manifest_sha256=manifest_sha256,
        owned_blobs=blobs,
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
    )
    after = provenance(repo)
    if after != current or manifest != base.source_manifest(repo):
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
        )
    del report
    passed = False
    if (
        approved_sha256
        and decisions_path
        and base.digest(decision_bytes) == approved_sha256
    ):
        passed = approved_gate(records, decisions)
    metadata = {
        "schema": "m0_3b_r1_run",
        **current,
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.monotonic() - tick, 6),
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
        "unknown_decision_count": len(decisions) - len(selected),
        "promotion_gates": "open",
        "direct_blob_count": len(blobs),
        "excluded_gitlink_count": len(gitlinks),
    }
    publish(output, identities, records, metadata, decisions, manifest, gitlinks)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("repo", "scanner", "output"):
        parser.add_argument("--" + argument, required=True)
    parser.add_argument("--decisions")
    parser.add_argument("--approved-sha256")
    args = parser.parse_args()
    try:
        return run_adjudication(
            args.repo,
            args.scanner,
            args.output,
            args.decisions,
            args.approved_sha256,
        )
    except Exception as exc:
        print("adjudication=failure type=" + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
