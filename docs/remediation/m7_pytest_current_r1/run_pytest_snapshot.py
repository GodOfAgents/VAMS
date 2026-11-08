from __future__ import annotations
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path("/home/GodOfAgents/code/VAMS-testnet")
EVIDENCE = ROOT / "docs/remediation/m7_pytest_current_r1"
RESULT = EVIDENCE / "RESULT.json"
RUN = EVIDENCE / "RUN.json"
ENVOY = Path("/home/GodOfAgents/vams-evidence/toolchains/envoy-1.39.1/envoy")
ENVOY_SHA256 = "002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8"
EXCLUDED = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv"}
DESIGN_TEST = "docs/remediation/m3_f05_design_r2/test_design.py"

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def source_inventory() -> tuple[list[dict[str, str]], str]:
    paths = {ROOT / "pytest.ini", ROOT / "conftest.py"}
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED for part in path.relative_to(ROOT).parts):
            continue
        if path.is_symlink():
            raise RuntimeError("Python source symlink in test inventory")
        if path.is_file():
            paths.add(path)
    rows = []
    state = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix()):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("non-regular pytest input")
        rel = path.relative_to(ROOT).as_posix()
        file_hash = digest(path.read_bytes())
        rows.append({"path": rel, "sha256": file_hash})
        state.update(rel.encode() + b"\0" + file_hash.encode("ascii") + b"\n")
    return rows, state.hexdigest()

def git_snapshot() -> dict[str, str]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
    raw = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                         cwd=ROOT, capture_output=True, check=True).stdout
    entries = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        path = item[3:] if len(item) >= 3 else item
        if path.startswith(b"docs/remediation/m7_pytest_current_r1/"):
            continue
        entries.append(item)
    return {"head": head.decode().strip(), "status_sha256": digest(b"\0".join(entries))}

def run(args: list[str], env: dict[str, str]) -> dict[str, object]:
    command = [sys.executable, "-B", "-m", "pytest", *args]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=900)
    summary_line = next((
        line.strip() for line in reversed(completed.stdout.splitlines())
        if re.search(r"\bin [0-9.]+s(?:\s|$)", line)
        and re.search(r"\b(?:passed|failed|error|errors|skipped|xfailed|xpassed|deselected|warnings|warning|no tests ran)\b", line)
    ), None)
    counts = {}
    duration = None
    if summary_line:
        for match in re.finditer(
            r"(\d+) (subtests passed|passed|failed|skipped|xfailed|xpassed|errors|error|deselected|warnings|warning)\b",
            summary_line,
        ):
            counts[match.group(2).replace(" ", "_")] = int(match.group(1))
        time_match = re.search(r"\bin ([0-9.]+)s", summary_line)
        duration = float(time_match.group(1)) if time_match else None
    collected = re.search(r"(\d+) tests collected in ([0-9.]+)s", completed.stdout)
    return {
        "command": command,
        "exit_code": completed.returncode,
        "collected": int(collected.group(1)) if collected else None,
        "summary": {"counts": counts, "duration_seconds": duration, "line": summary_line}
            if summary_line else None,
        "stdout_sha256": digest(completed.stdout.encode()),
        "stderr_sha256": digest(completed.stderr.encode()),
        "raw_output_retained": False,
    }

def exclusive_json(path: Path, value: dict[str, object]) -> str:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(payload)
    return digest(payload)

def main() -> int:
    if EVIDENCE.is_symlink() or not EVIDENCE.is_dir():
        raise SystemExit("evidence directory unavailable")
    if {p.name for p in EVIDENCE.iterdir()} != {"run_pytest_snapshot.py"}:
        raise SystemExit("evidence directory not pristine; refusing to overwrite")
    if RESULT.exists() or RUN.exists():
        raise SystemExit("evidence output already exists; refusing to overwrite")
    env = {
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "PATH": "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "VAMS_ENV": "test",
        "VAMS_ENVOY_BIN": str(ENVOY),
    }
    if sys.version_info[:3] != (3, 12, 14):
        raise SystemExit("pinned Python version mismatch")
    pytest_version = subprocess.run([sys.executable, "-B", "-m", "pytest", "--version"],
                                    cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    if pytest_version.stdout.strip() != "pytest 9.1.1":
        raise SystemExit("pinned pytest version mismatch")
    if ENVOY.is_symlink() or not ENVOY.is_file() or digest(ENVOY.read_bytes()) != ENVOY_SHA256:
        raise SystemExit("pinned Envoy binary identity mismatch")
    envoy_version = subprocess.run([str(ENVOY), "--version"], cwd=ROOT, env=env,
                                    capture_output=True, text=True, check=True)
    if "/1.39.1/Clean/RELEASE/BoringSSL" not in envoy_version.stdout:
        raise SystemExit("pinned Envoy version mismatch")
    git_before = git_snapshot()
    workflow_path = ROOT / ".github/workflows/security-gates.yml"
    workflow_before = digest(workflow_path.read_bytes())
    files_before, inventory_before = source_inventory()
    collection = run(["--collect-only", "-q", "-p", "no:cacheprovider",
                     "--ignore=" + DESIGN_TEST], env)
    main_suite = run(["-v", "--tb=short", "-p", "no:cacheprovider",
                      "--ignore=" + DESIGN_TEST], env)
    design_suite = run(["-v", "--tb=short", "-p", "no:cacheprovider", DESIGN_TEST], env)
    files_after, inventory_after = source_inventory()
    workflow_after = digest(workflow_path.read_bytes())
    git_after = git_snapshot()
    before_map = {row["path"]: row["sha256"] for row in files_before}
    after_map = {row["path"]: row["sha256"] for row in files_after}
    changed = [{"path": p, "before": before_map.get(p), "after": after_map.get(p)}
               for p in sorted(set(before_map) | set(after_map)) if before_map.get(p) != after_map.get(p)]
    result = {
        "schema": "m7-root-pytest-source-bound-r3",
        "python": sys.version.split()[0],
        "python_path": sys.executable,
        "pytest_version": pytest_version.stdout.strip(),
        "envoy": {"path": str(ENVOY), "sha256": digest(ENVOY.read_bytes()),
                  "version_sha256": digest(envoy_version.stdout.encode()),
                  "version": envoy_version.stdout.strip()},
        "git_before": git_before,
        "git_after": git_after,
        "git_unchanged": git_before == git_after,
        "workflow": {"path": ".github/workflows/security-gates.yml",
                     "sha256_before": workflow_before, "sha256_after": workflow_after,
                     "unchanged_during_run": workflow_before == workflow_after},
        "source_inventory": {
            "file_count_before": len(files_before), "sha256_before": inventory_before,
            "file_count_after": len(files_after), "sha256_after": inventory_after,
            "unchanged_during_run": inventory_before == inventory_after,
            "changed_paths": changed,
        },
        "collection": collection,
        "main_suite": main_suite,
        "separate_design_suite": design_suite,
        "raw_test_output_retained": False,
        "network": "disabled by outer bwrap",
        "scope_limit": "Local execution of the current workflow pytest split only; no hosted CI, ledger, testnet, or deployment credit. The pytest cache provider is disabled to respect the read-only checkout.",
    }
    result_hash = exclusive_json(RESULT, result)
    run_record = {
        "schema": "m7-root-pytest-run-r3",
        "outer_command": [
            "bwrap", "--unshare-net", "--ro-bind", "/", "/", "--tmpfs", "/tmp",
            "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--bind",
            str(EVIDENCE), str(EVIDENCE), "--chdir", str(ROOT), sys.executable, "-B",
            "docs/remediation/m7_pytest_current_r1/run_pytest_snapshot.py",
        ],
        "capture_script_sha256": digest(Path(__file__).read_bytes()),
        "result_sha256": result_hash,
        "python": sys.version.split()[0],
        "pytest": pytest_version.stdout.strip(),
        "envoy": result["envoy"],
        "git_before": git_before, "git_after": git_after,
        "workflow_sha256_before": workflow_before, "workflow_sha256_after": workflow_after,
        "inventory_before": inventory_before, "inventory_after": inventory_after,
        "collection": collection, "main_suite": main_suite, "separate_design_suite": design_suite,
        "evidence_credit": "No deployment, ledger, or live-network credit.",
    }
    exclusive_json(RUN, run_record)
    print(json.dumps({
        "collection_exit": collection["exit_code"], "collected": collection["collected"],
        "main_exit": main_suite["exit_code"], "main_summary": main_suite["summary"],
        "design_exit": design_suite["exit_code"], "design_summary": design_suite["summary"],
        "source_unchanged": inventory_before == inventory_after,
        "git_unchanged": git_before == git_after, "changed_paths": changed,
    }, sort_keys=True))
    return int(collection["exit_code"] != 0 or main_suite["exit_code"] != 0 or
               design_suite["exit_code"] != 0 or inventory_before != inventory_after or
               git_before != git_after or main_suite["summary"] is None or
               design_suite["summary"] is None or collection["collected"] is None or
               workflow_before != workflow_after)

if __name__ == "__main__":
    raise SystemExit(main())
