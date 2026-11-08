from __future__ import annotations
import hashlib, json, os, subprocess, tempfile
from pathlib import Path

ROOT = Path("/home/GodOfAgents/code/VAMS-testnet")
EVIDENCE = Path("/home/GodOfAgents/vams-evidence/m7-bandit-current-r3-20261004")
BANDIT = Path("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/bandit")
EXPECTED_VERSION = "1.9.4"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
def source_inventory() -> dict:
    files = []
    for base in (ROOT / "neuron", ROOT / "gateway"):
        for path in sorted(base.rglob("*.py")):
            if path.is_symlink() or not path.is_file():
                raise RuntimeError("symlink or non-regular Python source")
            rel = path.relative_to(ROOT).as_posix()
            files.append((rel, sha(path.read_bytes())))
    blob = b"".join(path.encode() + b"\0" + digest.encode() + b"\n" for path, digest in files)
    return {"python_file_count": len(files), "path_sha256_manifest_sha256": sha(blob)}
def main() -> None:
    result_path, run_path = EVIDENCE / "RESULT.json", EVIDENCE / "RUN.json"
    if EVIDENCE.is_symlink() or not EVIDENCE.is_dir():
        raise SystemExit("evidence directory missing or symlinked")
    if {p.name for p in EVIDENCE.iterdir()} != {"run_capture.py"}:
        raise SystemExit("evidence outputs already exist; refusing overwrite")
    if BANDIT.is_symlink() or not BANDIT.is_file():
        raise SystemExit("pinned Bandit executable missing or symlinked")
    version_out = subprocess.run([str(BANDIT), "--version"], cwd=ROOT,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    version = version_out.stdout.decode().strip().splitlines()[0]
    if version != "bandit " + EXPECTED_VERSION:
        raise SystemExit("pinned Bandit version mismatch")
    binary_hash = sha(BANDIT.read_bytes())
    sources_before = source_inventory()
    command = [str(BANDIT), "-r", "neuron/", "gateway/", "-ll", "-ii",
               "-f", "json"]
    with tempfile.TemporaryDirectory(prefix="vams-bandit-") as temp:
        report_path = Path(temp) / "bandit-report.json"
        full_command = command + ["-o", str(report_path)]
        cp = subprocess.run(full_command, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if not report_path.is_file():
            raise SystemExit("Bandit did not produce its JSON report")
        raw = report_path.read_bytes()
        report = json.loads(raw)
        if type(report) is not dict or type(report.get("results")) is not list:
            raise SystemExit("Bandit report schema unexpected")
        sanitized = []
        for item in report["results"]:
            if type(item) is not dict:
                raise SystemExit("Bandit finding schema unexpected")
            sanitized.append({
                "filename": item.get("filename"),
                "line_number": item.get("line_number"),
                "test_id": item.get("test_id"),
                "issue_severity": item.get("issue_severity"),
                "issue_confidence": item.get("issue_confidence"),
                "issue_text": item.get("issue_text"),
            })
        error_count = len(report.get("errors", []))
        report_hash = sha(raw)
        del raw, report
    if cp.returncode not in (0, 1, 2):
        raise SystemExit("unexpected Bandit exit code")
    sources_after = source_inventory()
    if sources_after != sources_before:
        raise SystemExit("Python source inventory changed during scan")
    result = {
        "schema_version": "m7-bandit-current-r1",
        "evidence_class": "local_static_source_scan",
        "scanner": {"version": version, "path": str(BANDIT), "sha256": binary_hash},
        "command": full_command,
        "scanner_exit_code": cp.returncode,
        "report_sha256": report_hash,
        "raw_report_retained": False,
        "stdout_sha256": sha(cp.stdout),
        "stderr_sha256": sha(cp.stderr),
        "source_inventory": sources_before,
        "source_inventory_after": sources_after,
        "finding_count": len(sanitized),
        "error_count": error_count,
        "findings": sanitized,
        "source_code_snippets_retained": False,
        "network": "disabled by outer bwrap",
        "scope": "Bandit 1.9.4, recursive Python source under neuron/ and gateway/, workflow severity/confidence thresholds -ll -ii.",
        "limitations": "This is a local static-analysis result only; it does not establish full CI parity, runtime behavior, other scanners, or deployment readiness."
    }
    if run_path.exists() or result_path.exists():
        raise SystemExit("output appeared during scan; refusing overwrite")
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run = {
        "schema_version": "m7-bandit-capture-r1",
        "outer_command": [
            "bwrap", "--unshare-net", "--ro-bind", "/", "/", "--tmpfs", "/tmp",
            "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--bind",
            str(EVIDENCE), str(EVIDENCE), "--chdir", str(ROOT),
            "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python",
            "-B", "docs/remediation/m7_bandit_current_r1/run_capture.py"
        ],
        "inner_command": full_command,
        "capture_script_sha256": sha(Path(__file__).read_bytes()),
        "result_sha256": sha(result_path.read_bytes()),
        "scanner_exit_code": cp.returncode,
        "finding_count": len(sanitized),
        "error_count": error_count,
        "source_inventory": sources_before,
        "source_inventory_after": sources_after,
        "tool": {"version": version, "sha256": binary_hash},
        "evidence_credit": "No deployment, ledger, or live-network credit."
    }
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"scanner_exit_code": cp.returncode, "finding_count": len(sanitized),
                      "error_count": error_count, "version": version}, sort_keys=True))
if __name__ == "__main__":
    main()
