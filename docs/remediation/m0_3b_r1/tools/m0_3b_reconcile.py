#!/usr/bin/env python3
"""Independent executable reconciliation for the M0.3b direct tranche.

This file deliberately does not import the adjudicator. It creates its scanner
input from direct-commit blobs, deletes the raw report, and emits only counts
and non-sensitive proof categories.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

PREFIX = "contracts/lib/openzeppelin-contracts-upgradeable"
PIN = "aa677e9d28ed78fc427ec47ba2baef2030c58e7c"
NESTED_PATH = "lib/openzeppelin-contracts"
NESTED_PIN = "fcbae5394ae8ad52d8e580a3477db99814b9d565"
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
    tree = git(repo, "ls-tree", "HEAD", "--", PREFIX).decode().split()
    index = git(repo, "ls-files", "--stage", "--", PREFIX).decode().split()
    if len(tree) != 4 or tree[:2] != ["160000", "commit"]:
        raise ReconciliationError("missing direct gitlink")
    if len(index) != 4 or index[0] != "160000" or index[1] != tree[2]:
        raise ReconciliationError("index gitlink mismatch")
    submodule = repo / PREFIX
    subhead = git(submodule, "rev-parse", "HEAD").decode().strip()
    dirty = git(submodule, "status", "--porcelain", "--untracked-files=all", "--ignored")
    if tree[2] != PIN or subhead != PIN or dirty:
        raise ReconciliationError("direct submodule is not at clean pin")
    return head, tree[2]


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
    if gitlinks.get(NESTED_PATH) != NESTED_PIN:
        raise ReconciliationError("nested provenance mismatch")
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


def erc7201(lines, index):
    if index < 1:
        return False
    comment = re.fullmatch(
        r'// keccak256\(abi\.encode\(uint256\(keccak256\("([A-Za-z0-9_.]+)"\)\) - 1\)\) & ~bytes32\(uint256\(0xff\)\)',
        lines[index - 1].strip(),
    )
    constant = re.fullmatch(
        r"bytes32 private constant [A-Za-z][A-Za-z0-9]*StorageLocation = 0x([0-9a-f]{64});",
        lines[index].strip(),
    )
    if not comment or not constant:
        return False
    from eth_hash.auto import keccak

    inner = int.from_bytes(keccak(comment.group(1).encode()), "big")
    outer = keccak(((inner - 1) % (1 << 256)).to_bytes(32, "big"))
    expected = int.from_bytes(outer, "big") & ~0xFF
    return constant.group(1) == f"{expected:064x}"


def classify(repo, path, line_number):
    data = (repo / path).read_bytes()
    lines = data.decode("utf-8").splitlines()
    if not 1 <= line_number <= len(lines):
        return "not_proven"
    line = lines[line_number - 1]
    if path.startswith(PREFIX + "/test/") and path.endswith((".test.js", ".behavior.js")):
        if re.fullmatch(
            r"\s*\.to\.be\.revertedWithCustomError\(this\.[A-Za-z][A-Za-z0-9]*, (['\x60])(ERC[0-9]+[A-Za-z]+)\1\)\s*",
            line,
        ):
            return "expected_custom_error_assertion"
    if path.startswith(PREFIX + "/test/") and path.endswith(".json"):
        key = re.fullmatch(r'\s*"keyDer"\s*:\s*"([0-9a-f]+)",?\s*', line)
        if key:
            document = json.loads(data)
            groups = [
                group for group in document.get("testGroups", [])
                if group.get("keyDer") == key.group(1)
            ]
            if (
                document.get("algorithm") == "ECDSA"
                and groups
                and all(
                    group.get("type") == "EcdsaP1363Verify"
                    and group.get("key", {}).get("type") == "EcPublicKey"
                    for group in groups
                )
            ):
                process = subprocess.run(
                    ["openssl", "pkey", "-pubin", "-inform", "DER", "-noout"],
                    input=bytes.fromhex(key.group(1)),
                    capture_output=True,
                )
                if process.returncode == 0:
                    return "ecdsa_public_key_der"
    if path.startswith(PREFIX + "/contracts/") and path.endswith(".sol"):
        if erc7201(lines, line_number - 1):
            return "erc7201_storage_slot_constant"
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
    head, commit = state(repo)
    blobs, gitlinks = tree(repo, commit)
    manifest_hash = digest(encoded(first_party_manifest(repo)))
    raw_parent = None
    with tempfile.TemporaryDirectory(prefix="m03b-independent-") as temporary:
        os.chmod(temporary, 0o700)
        raw_parent = temporary
        source = Path(temporary) / "source"
        source.mkdir(mode=0o700)
        for relative, (_, mode) in sorted(blobs.items()):
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git(repo / PREFIX, "show", f"{commit}:{relative}"))
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
            proof_counts[classify(repo, canonical, start)] += 1
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
        proof = classify(repo, canonical, line_number)
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
    expected_counts = {
        "ecdsa_public_key_der": 75,
        "erc7201_storage_slot_constant": 2,
        "expected_custom_error_assertion": 83,
    }
    if len(seen) != 160 or proof_counts != Counter(expected_counts):
        raise ReconciliationError("unexpected direct finding classes")
    return {
        "schema": "m0_3b_r1_independent_reconciliation",
        "scanner_exit": 1,
        "scanner_command": command,
        "scanner_cwd": scanner_cwd,
        "finding_count": len(seen),
        "path_count": len({path for path, _ in scanner_identities.values()}),
        "proof_counts": expected_counts,
        "direct_blob_count": len(blobs),
        "excluded_gitlink_count": len(gitlinks),
        "nested_openzeppelin_excluded": NESTED_PATH in gitlinks,
        "raw_removed": raw_removed,
        "head": head,
        "submodule_commit": commit,
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
                    "schema": "m0_3b_r1_independent_reconciliation",
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
