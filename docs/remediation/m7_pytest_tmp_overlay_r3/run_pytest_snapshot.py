from __future__ import annotations
import hashlib, json, os, re, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/home/GodOfAgents/code/VAMS-testnet")
EVIDENCE = Path("/tmp/vams-evidence")
RESULT = EVIDENCE / "RESULT.json"
RUN = EVIDENCE / "RUN.json"
ENVOY = Path("/home/GodOfAgents/vams-evidence/toolchains/envoy-1.39.1/envoy")
ENVOY_SHA256 = "002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8"
EXCLUDED = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv"}
DESIGN_TEST = "docs/remediation/m3_f05_design_r2/test_design.py"
WORKFLOW = ".github/workflows/security-gates.yml"
EVIDENCE_REL = "docs/remediation/m7_pytest_tmp_overlay_r3/"
SAFE_QUALIFIED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
SAFE_TEST = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,200}$")

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def source_inventory() -> tuple[int, str]:
    paths = {ROOT / "pytest.ini", ROOT / "conftest.py"}
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED for part in path.relative_to(ROOT).parts):
            continue
        if path.is_symlink():
            raise RuntimeError("Python source symlink in test inventory")
        if path.is_file():
            paths.add(path)
    state = hashlib.sha256()
    count = 0
    for path in sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix()):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("non-regular pytest input")
        rel = path.relative_to(ROOT).as_posix()
        state.update(rel.encode() + b"\0" + digest(path.read_bytes()).encode("ascii") + b"\n")
        count += 1
    return count, state.hexdigest()

def git_snapshot() -> dict[str, str]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
    raw = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                         cwd=ROOT, capture_output=True, check=True).stdout
    entries = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        path = item[3:] if len(item) >= 3 else item
        if path.startswith(EVIDENCE_REL.encode()):
            continue
        entries.append(item)
    return {"head": head.decode().strip(), "status_sha256": digest(b"\0".join(entries))}

def safe_case(case: ET.Element) -> dict[str, object]:
    raw_class = case.attrib.get("classname", "")
    raw_name = case.attrib.get("name", "")
    raw_base, sep, raw_params = raw_name.partition("[")
    classname = raw_class.replace(str(ROOT) + "/", "")
    if not SAFE_QUALIFIED.fullmatch(classname):
        classname = "sha256:" + digest(raw_class.encode())
    test_name = raw_base if SAFE_TEST.fullmatch(raw_base) else "sha256:" + digest(raw_name.encode())
    outcome = "passed"
    exception_type = None
    failure = case.find("failure")
    error = case.find("error")
    if failure is not None:
        outcome, exception_type = "failure", failure.attrib.get("type")
    elif error is not None:
        outcome, exception_type = "error", error.attrib.get("type")
    elif case.find("skipped") is not None:
        outcome = "skipped"
    return {
        "classname": classname,
        "test_name": test_name,
        "parameterized": bool(sep),
        "parameter_fragment_sha256": digest(raw_params.encode()) if sep else None,
        "outcome": outcome,
        "exception_type": exception_type if exception_type and SAFE_QUALIFIED.fullmatch(exception_type) else
            ("sha256:" + digest(exception_type.encode()) if exception_type else None),
    }

def execute(args: list[str], env: dict[str, str], label: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="vams-pytest-junit-") as temp:
        junit_path = Path(temp) / "report.xml"
        command = ["/usr/bin/bwrap", "--bind", "/", "/",
                   "--bind", "/tmp", "/tmp", "--dev-bind", "/dev", "/dev",
                   "--proc", "/proc", "--bind", str(ROOT), str(ROOT),
                   "--ro-bind", str(EVIDENCE), str(EVIDENCE),
                   "--chdir", str(ROOT), "--", sys.executable, "-B", "-m", "pytest",
                   "-q", "--tb=no", "-p", "no:cacheprovider", *args,
                   "--junitxml=" + str(junit_path)]
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                   text=True, timeout=900)
        if not junit_path.is_file():
            raise RuntimeError(label + " did not produce JUnit XML")
        raw_xml = junit_path.read_bytes()
        report = ET.fromstring(raw_xml)
        cases = [safe_case(case) for case in report.findall(".//testcase")]
        failures = [case for case in cases if case["outcome"] in ("failure", "error")]
        outcome_counts = {}
        for case in cases:
            outcome_counts[str(case["outcome"])] = outcome_counts.get(str(case["outcome"]), 0) + 1
        declared_failures = 0
        declared_errors = 0
        for suite in report.findall(".//testsuite"):
            declared_failures += int(suite.attrib.get("failures", "0"))
            declared_errors += int(suite.attrib.get("errors", "0"))
        if declared_failures + declared_errors != len(failures):
            raise RuntimeError(label + " JUnit failure rows do not match suite counters")
        return {
            "label": label,
            "command": command,
            "exit_code": completed.returncode,
            "junit_sha256": digest(raw_xml),
            "junit_raw_retained": False,
            "testcase_count": len(cases),
            "outcome_counts": outcome_counts,
            "declared_failure_count": declared_failures,
            "declared_error_count": declared_errors,
            "failing_tests": failures,
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
        raise SystemExit("evidence bind unavailable")
    if {p.name for p in EVIDENCE.iterdir()} != {"run_pytest_snapshot.py"}:
        raise SystemExit("evidence directory not pristine")
    if RESULT.exists() or RUN.exists():
        raise SystemExit("evidence output already exists")
    env = {
        "HOME": "/tmp", "TMPDIR": "/tmp",
        "PATH": "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "VAMS_ENV": "test", "VAMS_ENVOY_BIN": str(ENVOY),
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
    workflow_path = ROOT / WORKFLOW
    workflow_before = digest(workflow_path.read_bytes())
    count_before, inventory_before = source_inventory()
    main_suite = execute(["--ignore=" + DESIGN_TEST], env, "main")
    design_suite = execute([DESIGN_TEST], env, "design")
    count_after, inventory_after = source_inventory()
    workflow_after = digest(workflow_path.read_bytes())
    git_after = git_snapshot()
    stable = (count_before == count_after and inventory_before == inventory_after and
              workflow_before == workflow_after and git_before == git_after)
    results = {"main": main_suite, "design": design_suite}
    exit_semantics = {
        name: suite["exit_code"] == (1 if suite["failing_tests"] else 0)
        for name, suite in results.items()
    }
    gate_pass = (all(suite["exit_code"] == 0 and not suite["failing_tests"]
                     for suite in results.values()))
    result = {
        "schema": "m7-pytest-tmp-overlay-r3",
        "python": sys.version.split()[0], "python_path": sys.executable,
        "pytest_version": pytest_version.stdout.strip(),
        "envoy": {"path": str(ENVOY), "sha256": digest(ENVOY.read_bytes()),
                  "version": envoy_version.stdout.strip()},
        "environment": {"VAMS_ENV": "test", "VAMS_ENVOY_BIN": str(ENVOY),
                        "ambient_environment_inherited": False},
        "git_before": git_before, "git_after": git_after, "git_unchanged": git_before == git_after,
        "workflow": {"path": WORKFLOW, "sha256_before": workflow_before,
                     "sha256_after": workflow_after, "unchanged": workflow_before == workflow_after},
        "python_inventory": {"count_before": count_before, "sha256_before": inventory_before,
                             "count_after": count_after, "sha256_after": inventory_after,
                             "unchanged": count_before == count_after and inventory_before == inventory_after},
        "main_suite": main_suite, "design_suite": design_suite,
        "exit_semantics_match": exit_semantics,
        "gate_pass": gate_pass,
        "network": "disabled by outer bwrap",
        "writable_checkout": "bwrap tmp-overlay over the canonical checkout; all test writes discarded at teardown",
        "redaction": "JUnit XML and raw pytest output were temporary; only normalized module/function IDs, parameter-fragment hashes, outcomes, safe exception types, and output hashes are retained.",
        "scope_limit": "Local current-workflow pytest execution only; no hosted CI, ledger, testnet, or deployment credit.",
    }
    result_hash = exclusive_json(RESULT, result)
    run_record = {
        "schema": "m7-pytest-tmp-overlay-run-r3",
        "expected_outer_command": [
            "bwrap", "--unshare-net", "--ro-bind", "/", "/", "--tmpfs", "/tmp",
            "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--dir", "/tmp/vams-evidence",
            "--bind", str(ROOT / EVIDENCE_REL.rstrip("/")), "/tmp/vams-evidence",
            "--overlay-src", str(ROOT), "--tmp-overlay", str(ROOT), "--chdir", str(ROOT),
            sys.executable, "-B", "/tmp/vams-evidence/run_pytest_snapshot.py",
        ],
        "invocation_attestation": "Expected bwrap command is wrapper-written metadata, not independent process telemetry.",
        "capture_script_sha256": digest(Path(__file__).read_bytes()),
        "result_sha256": result_hash,
        "python": sys.version.split()[0], "pytest": pytest_version.stdout.strip(),
        "envoy": result["envoy"],
        "git_before": git_before, "git_after": git_after,
        "workflow_sha256_before": workflow_before, "workflow_sha256_after": workflow_after,
        "python_inventory_before": inventory_before, "python_inventory_after": inventory_after,
        "main_suite": main_suite, "design_suite": design_suite,
        "gate_pass": gate_pass, "exit_semantics_match": exit_semantics,
        "evidence_credit": "No deployment, ledger, or live-network credit.",
    }
    exclusive_json(RUN, run_record)
    print(json.dumps({
        "gate_pass": gate_pass, "stable_source_workflow_git": stable,
        "main_testcase_count": main_suite["testcase_count"],
        "main_outcomes": main_suite["outcome_counts"],
        "design_testcase_count": design_suite["testcase_count"],
        "design_outcomes": design_suite["outcome_counts"],
        "main_failures": main_suite["failing_tests"],
        "design_failures": design_suite["failing_tests"],
    }, sort_keys=True))
    return int(not stable or not all(exit_semantics.values()))

if __name__ == "__main__":
    raise SystemExit(main())
