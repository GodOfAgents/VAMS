#!/usr/bin/env python3
"""M0.4-R1 exact current-tree vendor-baseline gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "m0.4-vendor-baseline-v1"
RESULT_SCHEMA = "m0.4-current-tree-result-v1"
PINNED_GITLEAKS_VERSION = "8.30.1"
PINNED_GITLEAKS_SHA256 = "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509"
PINNED_CONFIG_SHA256 = "2a8e3b8313a84bae9abdda78bd6d44738b8c85d772bd5669d53f8aad04caed8e"
PINNED_BASELINE_SHA256 = "3a4526acf33ab4adeff87da1553cb5e4493799c3696664c2d60a126a9aa086f4"
EXPECTED_COUNTS = {"first_party": 0, "m0_3a": 161, "m0_3b": 160, "m0_3c": 158, "vendor": 479}
EXPECTED_OWNERS = {
    "m0_3a": ("contracts/lib/openzeppelin-contracts", "239795bea728c8dca4deb6c66856dd58a6991112"),
    "m0_3b": ("contracts/lib/openzeppelin-contracts-upgradeable", "aa677e9d28ed78fc427ec47ba2baef2030c58e7c"),
    "m0_3c": (
        "contracts/lib/openzeppelin-contracts-upgradeable/lib/openzeppelin-contracts",
        "fcbae5394ae8ad52d8e580a3477db99814b9d565",
    ),
}
IDENTITY_FIELDS = ("scope", "owner_commit", "path", "rule", "start", "end", "file_sha256")


class GateError(RuntimeError):
    """Fail-closed gate error containing no scanner payload."""


@dataclass(frozen=True)
class OwnerState:
    scope: str
    path: str
    commit: str
    clean: bool


def run(args: list[str], cwd: Path, *, text: bool = True) -> subprocess.CompletedProcess[Any]:
    try:
        return subprocess.run(args, cwd=cwd, text=text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        raise GateError("required command unavailable") from exc


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError("duplicate JSON key")
        result[key] = value
    return result


def canonical_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or any(ord(char) < 32 for char in value):
        raise GateError("invalid path")
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or ":" in value.split("/", 1)[0]:
        raise GateError("absolute path")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise GateError("non-canonical path")
    normalized = posixpath.normpath(value)
    if normalized != value or normalized.startswith("../"):
        raise GateError("non-canonical path")
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def identity_digest(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json({key: record[key] for key in IDENTITY_FIELDS}))


def validate_hex(value: Any, length: int, label: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(char not in "0123456789abcdef" for char in value):
        raise GateError(f"invalid {label}")
    return value


def load_baseline(path: Path, *, expected_digest: str = PINNED_BASELINE_SHA256) -> tuple[dict[str, Any], str]:
    if not path.is_file() or path.is_symlink():
        raise GateError("baseline unavailable")
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    if digest != expected_digest:
        raise GateError("baseline digest mismatch")
    try:
        baseline = json.loads(raw, object_pairs_hook=strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError("malformed baseline") from exc
    validate_baseline(baseline)
    return baseline, digest


def validate_baseline(baseline: Any) -> None:
    if not isinstance(baseline, dict) or set(baseline) != {"schema", "scanner", "counts", "owners", "records", "reviewed_sources"}:
        raise GateError("invalid baseline document")
    if baseline["schema"] != SCHEMA or baseline["scanner"] != {"version": PINNED_GITLEAKS_VERSION, "sha256": PINNED_GITLEAKS_SHA256}:
        raise GateError("invalid baseline scanner contract")
    if baseline["counts"] != EXPECTED_COUNTS:
        raise GateError("invalid baseline counts")
    owners = baseline["owners"]
    if not isinstance(owners, list) or len(owners) != 3:
        raise GateError("invalid baseline owners")
    expected_owners = [
        {"scope": scope, "path": path, "commit": commit}
        for scope, (path, commit) in sorted(EXPECTED_OWNERS.items())
    ]
    if owners != expected_owners:
        raise GateError("invalid baseline owners")
    reviewed = baseline["reviewed_sources"]
    if not isinstance(reviewed, list) or len(reviewed) != 3:
        raise GateError("invalid reviewed source provenance")
    for item in reviewed:
        if not isinstance(item, dict) or set(item) != {"scope", "source", "sha256", "independent_review"}:
            raise GateError("invalid reviewed source provenance")
        if item["scope"] not in EXPECTED_OWNERS or not isinstance(item["source"], str) or not isinstance(item["independent_review"], str):
            raise GateError("invalid reviewed source provenance")
        validate_hex(item["sha256"], 64, "reviewed source hash")
    if {item["scope"] for item in reviewed} != set(EXPECTED_OWNERS):
        raise GateError("missing reviewed source provenance")
    records = baseline["records"]
    if not isinstance(records, list) or len(records) != EXPECTED_COUNTS["vendor"]:
        raise GateError("invalid baseline record count")
    identities: set[str] = set()
    tuples: set[tuple[Any, ...]] = set()
    counts = {scope: 0 for scope in EXPECTED_OWNERS}
    previous: tuple[Any, ...] | None = None
    for record in records:
        required = set(IDENTITY_FIELDS) | {"identity_sha256"}
        if not isinstance(record, dict) or set(record) != required:
            raise GateError("malformed baseline entry")
        scope = record["scope"]
        if scope not in EXPECTED_OWNERS:
            raise GateError("unknown baseline ownership")
        owner_path, owner_commit = EXPECTED_OWNERS[scope]
        if record["owner_commit"] != owner_commit:
            raise GateError("baseline owner commit mismatch")
        path = canonical_path(record["path"])
        if path != record["path"] or not path.startswith(owner_path + "/"):
            raise GateError("baseline ownership mismatch")
        if not isinstance(record["rule"], str) or not record["rule"]:
            raise GateError("invalid baseline rule")
        if type(record["start"]) is not int or type(record["end"]) is not int or record["start"] < 1 or record["end"] < record["start"]:
            raise GateError("invalid baseline line range")
        validate_hex(record["file_sha256"], 64, "file hash")
        validate_hex(record["identity_sha256"], 64, "identity hash")
        if record["identity_sha256"] != identity_digest(record):
            raise GateError("baseline identity digest mismatch")
        key = tuple(record[field] for field in IDENTITY_FIELDS)
        order_key = (scope, path, record["rule"], record["start"], record["end"], record["file_sha256"])
        if key in tuples or record["identity_sha256"] in identities:
            raise GateError("duplicate baseline entry")
        if previous is not None and order_key <= previous:
            raise GateError("baseline records are not strictly sorted")
        previous = order_key
        tuples.add(key)
        identities.add(record["identity_sha256"])
        counts[scope] += 1
    if counts != {scope: EXPECTED_COUNTS[scope] for scope in EXPECTED_OWNERS}:
        raise GateError("baseline scope count mismatch")


def parse_submodules(repo: Path) -> dict[str, str]:
    completed = run(["git", "submodule", "status", "--recursive"], repo)
    if completed.returncode != 0:
        raise GateError("recursive submodule inventory failed")
    result: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if not line:
            continue
        marker = line[0]
        fields = line[1:].strip().split()
        if marker != " " or len(fields) < 2:
            raise GateError("recursive submodule pin drift")
        commit = validate_hex(fields[0], 40, "submodule commit")
        path = canonical_path(fields[1])
        if path in result:
            raise GateError("duplicate recursive submodule")
        result[path] = commit
    return result


def verify_gitlink(repo: Path, owner_path: str, commit: str, submodules: dict[str, str], head: str) -> None:
    parents = [path for path in submodules if owner_path.startswith(path + "/")]
    if parents:
        parent = max(parents, key=len)
        tree_root = repo / Path(*parent.split("/"))
        treeish = submodules[parent]
        relative = owner_path[len(parent) + 1 :]
    else:
        tree_root = repo
        treeish = head
        relative = owner_path
    completed = run(["git", "ls-tree", treeish, "--", relative], tree_root)
    fields = completed.stdout.strip().split(None, 3)
    if completed.returncode != 0 or len(fields) != 4 or fields[:3] != ["160000", "commit", commit]:
        raise GateError("approved owner gitlink drift")


def verify_owners(repo: Path, submodules: dict[str, str], head: str) -> dict[str, OwnerState]:
    states: dict[str, OwnerState] = {}
    for scope, (owner_path, commit) in EXPECTED_OWNERS.items():
        if submodules.get(owner_path) != commit:
            raise GateError("approved owner pin drift")
        worktree = repo / Path(*owner_path.split("/"))
        actual = run(["git", "rev-parse", "HEAD"], worktree)
        status = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], worktree)
        clean = actual.returncode == 0 and actual.stdout.strip() == commit and status.returncode == 0 and status.stdout == ""
        if not clean:
            raise GateError("approved vendor worktree is dirty or detached from its pin")
        verify_gitlink(repo, owner_path, commit, submodules, head)
        states[scope] = OwnerState(scope, owner_path, commit, clean)
    return states


def owner_tree(repo: Path, state: OwnerState) -> tuple[dict[str, str], set[str]]:
    root = repo / Path(*state.path.split("/"))
    completed = run(["git", "ls-tree", "-rz", "--full-tree", state.commit], root, text=False)
    if completed.returncode != 0:
        raise GateError("owner tree enumeration failed")
    blobs: dict[str, str] = {}
    gitlinks: set[str] = set()
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            metadata, relative_raw = raw.split(b"\t", 1)
            mode, object_type, oid = metadata.decode("ascii").split()
            relative = canonical_path(relative_raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise GateError("invalid owner tree record") from exc
        full = f"{state.path}/{relative}"
        if mode == "160000" and object_type == "commit":
            gitlinks.add(full)
        elif object_type == "blob":
            blobs[full] = oid
    return blobs, gitlinks


def verify_baseline_blobs(repo: Path, baseline: dict[str, Any], states: dict[str, OwnerState]) -> dict[str, dict[str, str]]:
    trees: dict[str, dict[str, str]] = {}
    for scope, state in states.items():
        blobs, _ = owner_tree(repo, state)
        trees[scope] = blobs
    checked: set[tuple[str, str]] = set()
    for record in baseline["records"]:
        scope, path = record["scope"], record["path"]
        oid = trees[scope].get(path)
        if oid is None:
            raise GateError("baseline path is not directly owned by its Git tree")
        key = (scope, path)
        if key in checked:
            continue
        relative = path[len(states[scope].path) + 1 :]
        blob = run(["git", "show", f"{states[scope].commit}:{relative}"], repo / Path(*states[scope].path.split("/")), text=False)
        if blob.returncode != 0 or sha256_bytes(blob.stdout) != record["file_sha256"]:
            raise GateError("baseline file hash does not match pinned Git object")
        checked.add(key)
    return trees


def git_files(root: Path) -> list[str]:
    completed = run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], root, text=False)
    if completed.returncode != 0:
        raise GateError("source inventory failed")
    try:
        return [canonical_path(raw.decode("utf-8")) for raw in completed.stdout.split(b"\0") if raw]
    except UnicodeDecodeError as exc:
        raise GateError("non-UTF-8 source path") from exc


def collect_sources(repo: Path, submodules: dict[str, str]) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    roots = [("", repo)] + [(path, repo / Path(*path.split("/"))) for path in sorted(submodules)]
    for prefix, root in roots:
        for relative in git_files(root):
            full = f"{prefix}/{relative}" if prefix else relative
            if full in submodules:
                continue
            path = root / Path(*relative.split("/"))
            if path.is_symlink() or not path.is_file():
                raise GateError("source manifest contains a missing or symbolic file")
            if full in sources:
                raise GateError("duplicate source path")
            sources[full] = path
    return sources


def stage_sources(sources: dict[str, Path], destination: Path) -> tuple[dict[str, str], str]:
    hashes: dict[str, str] = {}
    manifest = hashlib.sha256()
    for relative, source in sorted(sources.items()):
        target = destination / Path(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        digest = sha256_file(target)
        hashes[relative] = digest
        manifest.update(f"{digest}  {relative}\n".encode("utf-8"))
    return hashes, manifest.hexdigest()


def resolve_scope(path: str, submodules: dict[str, str]) -> str:
    containing = [candidate for candidate in submodules if path.startswith(candidate + "/")]
    if not containing:
        return "first_party"
    owner_path = max(containing, key=len)
    for scope, (approved_path, _) in EXPECTED_OWNERS.items():
        if owner_path == approved_path:
            return scope
    return "unknown"


def sanitized_findings(
    findings: Any,
    source_hashes: dict[str, str],
    submodules: dict[str, str],
    owner_trees: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], int, int]:
    if not isinstance(findings, list):
        raise GateError("invalid scanner report")
    records: list[dict[str, Any]] = []
    first_party = 0
    unknown = 0
    for finding in findings:
        if not isinstance(finding, dict):
            raise GateError("invalid scanner finding")
        path = canonical_path(finding.get("File"))
        if path not in source_hashes:
            raise GateError("finding is absent from current-tree manifest")
        scope = resolve_scope(path, submodules)
        if scope == "first_party":
            first_party += 1
            continue
        if scope == "unknown":
            unknown += 1
            continue
        if path not in owner_trees[scope]:
            raise GateError("finding attributed through a child gitlink")
        rule = finding.get("RuleID")
        start, end = finding.get("StartLine"), finding.get("EndLine")
        if not isinstance(rule, str) or not rule or type(start) is not int or type(end) is not int or start < 1 or end < start:
            raise GateError("invalid sanitized scanner identity")
        record = {
            "scope": scope,
            "owner_commit": EXPECTED_OWNERS[scope][1],
            "path": path,
            "rule": rule,
            "start": start,
            "end": end,
            "file_sha256": source_hashes[path],
        }
        record["identity_sha256"] = identity_digest(record)
        records.append(record)
    return records, first_party, unknown


def reconcile(
    baseline: dict[str, Any],
    observed: list[dict[str, Any]],
    *,
    first_party: int,
    unknown: int,
    scanner_version: str,
    scanner_sha256: str,
    owner_states: dict[str, OwnerState],
) -> dict[str, int]:
    if scanner_version != PINNED_GITLEAKS_VERSION or scanner_sha256 != PINNED_GITLEAKS_SHA256:
        raise GateError("scanner version or hash drift")
    if first_party != 0:
        raise GateError("first-party finding detected")
    if unknown != 0:
        raise GateError("unknown vendor ownership detected")
    if set(owner_states) != set(EXPECTED_OWNERS) or any(
        not state.clean or (state.path, state.commit) != EXPECTED_OWNERS[scope]
        for scope, state in owner_states.items()
    ):
        raise GateError("owner state drift")
    expected = baseline["records"]
    expected_ids = [record["identity_sha256"] for record in expected]
    observed_ids = [record["identity_sha256"] for record in observed]
    if len(observed_ids) != len(set(observed_ids)):
        raise GateError("duplicate vendor identity")
    if set(observed_ids) != set(expected_ids) or len(observed) != len(expected):
        raise GateError("vendor identity set drift")
    expected_by_id = {record["identity_sha256"]: record for record in expected}
    for record in observed:
        if record != expected_by_id[record["identity_sha256"]]:
            raise GateError("vendor identity binding drift")
    counts = {scope: 0 for scope in EXPECTED_OWNERS}
    for record in observed:
        counts[record["scope"]] += 1
    if counts != {scope: EXPECTED_COUNTS[scope] for scope in EXPECTED_OWNERS}:
        raise GateError("vendor count drift")
    return {"first_party": first_party, **counts, "vendor": len(observed), "unknown": unknown}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", type=Path, default=Path("scripts/security/m0_4_vendor_baseline.json"))
    parser.add_argument("--gitleaks", type=Path, default=Path(os.environ.get("GITLEAKS_BIN", "gitleaks")))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    temp_root: Path | None = None
    try:
        repo = args.repo.resolve()
        baseline_path = args.baseline if args.baseline.is_absolute() else repo / args.baseline
        baseline, baseline_digest = load_baseline(baseline_path)
        head_result = run(["git", "rev-parse", "HEAD"], repo)
        if head_result.returncode != 0:
            raise GateError("superproject HEAD unavailable")
        head = validate_hex(head_result.stdout.strip(), 40, "superproject HEAD")
        submodules = parse_submodules(repo)
        owner_states = verify_owners(repo, submodules, head)
        owner_trees = verify_baseline_blobs(repo, baseline, owner_states)
        config = repo / ".gitleaks.toml"
        if not config.is_file() or config.is_symlink() or sha256_file(config) != PINNED_CONFIG_SHA256:
            raise GateError("Gitleaks configuration drift")
        scanner = args.gitleaks.resolve()
        if not scanner.is_file() or scanner.is_symlink():
            raise GateError("scanner unavailable")
        scanner_hash = sha256_file(scanner)
        version_result = run([str(scanner), "version"], repo)
        version = version_result.stdout.strip()
        if version_result.returncode != 0 or version != PINNED_GITLEAKS_VERSION or scanner_hash != PINNED_GITLEAKS_SHA256:
            raise GateError("scanner version or hash drift")
        sources = collect_sources(repo, submodules)
        temp_root = Path(tempfile.mkdtemp(prefix="vams-m0-4-"))
        staged = temp_root / "tree"
        staged.mkdir(mode=0o700)
        source_hashes, source_manifest_digest = stage_sources(sources, staged)
        report = temp_root / "raw-report.json"
        command = [
            str(scanner), "dir", ".", "--config", str(config), "--redact=100", "--report-format", "json",
            "--report-path", str(report), "--exit-code", "1", "--no-banner",
        ]
        scanned = run(command, staged)
        if scanned.returncode != 1 or not report.is_file():
            raise GateError("aggregate scanner result was not the required finding result")
        try:
            findings = json.loads(report.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GateError("invalid scanner report") from exc
        observed, first_party, unknown = sanitized_findings(findings, source_hashes, submodules, owner_trees)
        report.unlink()
        counts = reconcile(
            baseline,
            observed,
            first_party=first_party,
            unknown=unknown,
            scanner_version=version,
            scanner_sha256=scanner_hash,
            owner_states=owner_states,
        )
        result = {
            "schema": RESULT_SCHEMA,
            "status": "pass",
            "superproject_head": head,
            "source_manifest_sha256": source_manifest_digest,
            "source_count": len(sources),
            "recursive_submodules": [{"path": path, "commit": commit} for path, commit in sorted(submodules.items())],
            "scanner": {"version": version, "sha256": scanner_hash},
            "gitleaks_config_sha256": PINNED_CONFIG_SHA256,
            "baseline_sha256": baseline_digest,
            "counts": counts,
        }
        rendered = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
        if args.output:
            output = args.output if args.output.is_absolute() else repo / args.output
            if output.exists() or output.is_symlink():
                raise GateError("output already exists")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        sys.stdout.write(rendered)
        return 0
    except (GateError, OSError) as exc:
        print(f"m0.4_gate=fail reason={exc}", file=sys.stderr)
        return 1
    finally:
        if temp_root is not None and temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=False)


if __name__ == "__main__":
    raise SystemExit(main())
