#!/usr/bin/env python3
"""Reproducible, redacted working-tree Gitleaks inventory for M0.1."""
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
import time
from dataclasses import dataclass
from pathlib import Path

PINNED_GITLEAKS = "8.30.1"
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", "venv", ".venv", "dist", "build", "out", "artifacts", "target", "raw-gate", "audit-evidence"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".pyd", ".py.class")


class InventoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Source:
    path: str
    absolute: Path
    category: str
    submodule: str | None = None
    submodule_commit: str | None = None


def run(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def canonical_rel(value: str) -> str:
    if not value or "\\" in value or any(ord(c) < 32 for c in value):
        raise InventoryError("invalid path")
    if value.startswith("/") or value.startswith("./") or ":" in value.split("/", 1)[0]:
        raise InventoryError("absolute path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise InventoryError("traversal or empty path")
    normalized = posixpath.normpath(value)
    if normalized != value or normalized.startswith("../"):
        raise InventoryError("non-canonical path")
    return normalized


def is_excluded(path: str) -> bool:
    value = canonical_rel(path)
    parts = value.split("/")
    return any(part in EXCLUDED_PARTS for part in parts) or value.endswith(EXCLUDED_SUFFIXES)


def parse_submodule_status(repo: Path) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    completed = run(["git", "submodule", "status", "--recursive"], repo)
    for line in completed.stdout.splitlines():
        if not line:
            continue
        marker = line[0]
        fields = line[1:].strip().split()
        if len(fields) < 2 or marker in "+-U":
            raise InventoryError("submodule is not initialized at pinned commit")
        commit, path = fields[0], fields[1]
        path = canonical_rel(path)
        if path in result:
            raise InventoryError("duplicate submodule")
        result[path] = (commit, path)
    return result


def validate_source(repo: Path, rel: str, *, category: str, submodule: str | None = None, submodule_commit: str | None = None) -> Source | None:
    rel = canonical_rel(rel)
    if is_excluded(rel):
        return None
    absolute = (repo / Path(*rel.split("/"))).resolve(strict=False)
    root = repo.resolve()
    try:
        absolute.relative_to(root)
    except ValueError as exc:
        raise InventoryError("symlink escapes checkout") from exc
    if not absolute.is_file() or absolute.is_symlink():
        raise InventoryError("source is not a regular file")
    return Source(rel, absolute, category, submodule, submodule_commit)


def collect_sources(repo: Path) -> tuple[list[Source], dict[str, int], dict[str, tuple[str, str]]]:
    tracked = run(["git", "ls-files", "-z"], repo).stdout.split("\0")
    untracked = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], repo).stdout.split("\0")
    submodules = parse_submodule_status(repo)
    values: dict[str, Source] = {}
    excluded = {"tracked": 0, "untracked": 0}
    for raw, category in [(x, "tracked") for x in tracked if x] + [(x, "untracked") for x in untracked if x]:
        if category == "tracked" and raw in submodules:
            continue
        source = validate_source(repo, raw, category=category)
        if source is None:
            excluded[category] += 1
            continue
        if source.path in values:
            raise InventoryError("duplicate source path")
        values[source.path] = source
    for subpath, (commit, _) in sorted(submodules.items()):
        subroot = (repo / Path(*subpath.split("/"))).resolve()
        for raw in run(["git", "-C", str(subroot), "ls-files", "-z"], repo).stdout.split("\0"):
            if not raw:
                continue
            rel = f"{subpath}/{raw}"
            if rel in submodules:
                continue
            source = validate_source(repo, rel, category="submodule", submodule=subpath, submodule_commit=commit)
            if source is None:
                excluded["submodule"] = excluded.get("submodule", 0) + 1
                continue
            if source.path in values:
                raise InventoryError("duplicate source path")
            values[source.path] = source
    return [values[k] for k in sorted(values)], excluded, submodules


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_ledger(findings: list[dict], sources: dict[str, Source]) -> list[dict]:
    counts: dict[tuple[str, str], int] = {}
    for finding in findings:
        path = str(finding.get("File", ""))
        path = canonical_rel(path)
        source = sources.get(path)
        if source is None:
            raise InventoryError("finding path absent from manifest")
        if finding.get("Secret") not in (None, "REDACTED"):
            raise InventoryError("unredacted secret")
        if finding.get("Match") not in (None,) and "REDACTED" not in str(finding.get("Match")):
            raise InventoryError("unredacted match")
        rule = finding.get("RuleID")
        if not isinstance(rule, str) or not rule:
            raise InventoryError("invalid rule")
        counts[(path, rule)] = counts.get((path, rule), 0) + 1
    ledger = []
    for (path, rule), count in sorted(counts.items()):
        source = sources[path]
        ledger.append({"relative_path": path, "rule_id": rule, "finding_count": count, "source_category": source.category, "submodule": source.submodule, "submodule_commit": source.submodule_commit})
    return ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gitleaks", type=Path, default=Path(os.environ.get("GITLEAKS_BIN", "gitleaks")))
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    output = args.output.resolve()
    started = time.time()
    temp_root: Path | None = None
    try:
        if output.exists() or output.is_symlink():
            raise InventoryError("output already exists")
        config = repo / ".gitleaks.toml"
        if not config.is_file() or config.is_symlink():
            raise InventoryError("configuration unavailable")
        try:
            version = run([str(args.gitleaks), "version"], repo).stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("gitleaks=unavailable", file=sys.stderr)
            return 2
        if version != PINNED_GITLEAKS:
            raise InventoryError("unsupported gitleaks version")
        sources, excluded, submodules = collect_sources(repo)
        temp_parent = output.parent
        temp_parent.mkdir(parents=True, exist_ok=True)
        temp_root = Path(tempfile.mkdtemp(prefix="m0_1_inventory.", dir=temp_parent))
        staged = temp_root / "input"
        staged.mkdir()
        manifest = temp_root / "source-manifest.txt"
        manifest.write_text("".join(s.path + "\n" for s in sources), encoding="utf-8")
        source_map: dict[str, Source] = {}
        for source in sources:
            destination = staged / Path(*source.path.split("/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source.absolute, destination)
            source_map[source.path] = source
        checksums = temp_root / "source-checksums.sha256"
        lines = [f"{sha256(staged / Path(*source.path.split('/')))}  input/{source.path}\n" for source in sources]
        checksums.write_text("".join(lines), encoding="utf-8")
        verified = subprocess.run(["sha256sum", "--check", "--strict", str(checksums)], cwd=temp_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if verified.returncode != 0:
            raise InventoryError("staged checksum verification failed")
        report = temp_root / "gitleaks-report.json"
        command = [str(args.gitleaks), "dir", ".", "--config", str(config), "--redact=100", "--report-format", "json", "--report-path", str(report), "--exit-code", "1", "--no-banner"]
        process = subprocess.run(command, cwd=staged, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not report.is_file():
            raise InventoryError("missing gitleaks report")
        findings = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(findings, list):
            raise InventoryError("invalid gitleaks report")
        ledger = build_ledger(findings, source_map)
        summary = [{"relative_path": x["relative_path"], "finding_count": x["finding_count"], "rule_ids": [x["rule_id"]], "source_category": x["source_category"], "submodule": x["submodule"], "submodule_commit": x["submodule_commit"]} for x in ledger]
        evidence = temp_root / "evidence"
        evidence.mkdir()
        shutil.copyfile(manifest, evidence / "source-manifest.txt")
        shutil.copyfile(checksums, evidence / "source-checksums.sha256")
        (evidence / "ledger.json").write_text(json.dumps(ledger, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        (evidence / "summary.json").write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        record = {"schema": "m0.1-gitleaks-working-tree", "repo": str(repo), "branch": run(["git", "branch", "--show-current"], repo).stdout.strip(), "head": run(["git", "rev-parse", "HEAD"], repo).stdout.strip(), "scanner_version": version, "scanner_path": str(args.gitleaks), "command": command, "source_count": len(sources), "excluded_counts": excluded, "finding_count": len(findings), "return_code": process.returncode, "stdout_size": len(process.stdout.encode()), "stdout_sha256": hashlib.sha256(process.stdout.encode()).hexdigest(), "stderr_size": len(process.stderr.encode()), "stderr_sha256": hashlib.sha256(process.stderr.encode()).hexdigest(), "submodules": [{"path": k, "commit": v[0]} for k, v in sorted(submodules.items())], "duration_seconds": round(time.time() - started, 6)}
        (evidence / "record.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(evidence, output)
        return 1 if findings else 0
    except (InventoryError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"inventory=failure reason={type(exc).__name__}", file=sys.stderr)
        return 2
    finally:
        if temp_root is not None and temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
