from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESULT = ROOT / "docs/remediation/m7_pytest_current_r2/RESULT.json"
EXCLUDED = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv"}

def source_inventory() -> tuple[list[dict[str, str]], str]:
    paths = {ROOT / "pytest.ini", ROOT / "conftest.py"}
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED for part in path.relative_to(ROOT).parts):
            continue
        if path.is_file() and not path.is_symlink():
            paths.add(path)
    rows = []
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(ROOT).as_posix()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"path": rel, "sha256": file_hash})
        digest.update(rel.encode("utf-8") + b"\0" + file_hash.encode("ascii") + b"\n")
    return rows, digest.hexdigest()

def run(args: list[str], env: dict[str, str]) -> dict[str, object]:
    command = [sys.executable, "-B", "-m", "pytest", *args]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    combined = completed.stdout + "\n" + completed.stderr
    summary = re.search(r"(?:(\d+) failed, )?(\d+) passed(?:, (\d+) failed)?(?:, (\d+) subtests passed)? in ([0-9.]+)s", combined)
    collected = re.search(r"(\d+) tests collected in ([0-9.]+)s", combined)
    return {
        "command": command,
        "exit_code": completed.returncode,
        "collected": int(collected.group(1)) if collected else None,
        "summary": {"passed": int(summary.group(2)), "failed": int(summary.group(3) or summary.group(1) or 0), "subtests_passed": int(summary.group(4) or 0), "duration_seconds": float(summary.group(5))} if summary else None,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "raw_output_retained": False,
    }

def main() -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl:/usr/bin:/bin"
    before_files, before_digest = source_inventory()
    collection = run(["--collect-only", "-q", "-p", "no:cacheprovider"], env)
    full = run(["-v", "--tb=short", "-p", "no:cacheprovider"], env)
    after_files, after_digest = source_inventory()
    before_map = {row["path"]: row["sha256"] for row in before_files}
    after_map = {row["path"]: row["sha256"] for row in after_files}
    changed_paths = [
        {"path": path, "before_sha256": before_map.get(path), "after_sha256": after_map.get(path)}
        for path in sorted(set(before_map) | set(after_map))
        if before_map.get(path) != after_map.get(path)
    ]
    result = {
        "schema": "m7-root-pytest-source-bound-v1",
        "python": sys.version.split()[0],
        "pytest_version": subprocess.run([sys.executable, "-B", "-m", "pytest", "--version"], cwd=ROOT, env=env, capture_output=True, text=True, check=True).stdout.strip(),
        "source_inventory": {"file_count_before": len(before_files), "sha256_before": before_digest, "file_count_after": len(after_files), "sha256_after": after_digest, "unchanged_during_run": before_digest == after_digest, "changed_paths": changed_paths},
        "collection": collection,
        "full_suite": full,
    }
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"collection_exit": collection["exit_code"], "collected": collection["collected"], "full_exit": full["exit_code"], "summary": full["summary"], "source_unchanged": before_digest == after_digest, "changed_paths": changed_paths, "result_path": str(RESULT)}, indent=2))
    return int(collection["exit_code"] != 0 or full["exit_code"] != 0 or before_digest != after_digest or full["summary"] is None)

if __name__ == "__main__":
    raise SystemExit(main())
