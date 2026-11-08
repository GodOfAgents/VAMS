from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path("/home/GodOfAgents/code/VAMS-testnet")
EVIDENCE = ROOT / "docs/remediation/m3_f05_2a_verify_signature_r3_current_r2"
PYTHON = Path("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python")
AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken")
HARNESS = ROOT / "scripts/remediation/test_f05_2a_authority_bootstrap_public.py"
FILES = [
    HARNESS,
    ROOT / "scripts/remediation/f05_2a_tx_sim_runner_r3.py",
    ROOT / "scripts/remediation/f05_2a_tx_sim_registry.py",
    ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1/CANARY-MANIFEST.json",
    ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1/applied-policy.cbor",
    ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1/valid.tx.cbor",
    ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1/invalid_signature.tx.cbor",
    ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1/raw_inputs.cbor",
    ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1/raw_outputs.cbor",
]
def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
def file_hashes() -> dict[str, str]:
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in FILES}
def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout.decode().strip()
def snapshot() -> dict:
    refs = [line.split(" ", 1) for line in git("for-each-ref", "--format=%(refname) %(objectname)").splitlines()]
    return {"head": git("rev-parse", "HEAD"),
            "branch": git("symbolic-ref", "--quiet", "--short", "HEAD"),
            "refs": [{"name": n, "oid": oid} for n, oid in refs],
            "reachable_commit_count": int(git("rev-list", "--all", "--count")),
            "is_shallow": git("rev-parse", "--is-shallow-repository") == "true"}
def main() -> None:
    result_path, run_path = EVIDENCE / "RESULT.json", EVIDENCE / "RUN.json"
    if EVIDENCE.is_symlink() or not EVIDENCE.is_dir():
        raise SystemExit("evidence directory missing or symlinked")
    if {p.name for p in EVIDENCE.iterdir()} != {"run_capture.py"}:
        raise SystemExit("evidence outputs already exist; refusing overwrite")
    if any(p.is_symlink() for p in FILES + [PYTHON, AIKEN, HARNESS]):
        raise SystemExit("symlinked tool or source path")
    if not all(p.is_file() for p in FILES + [PYTHON, AIKEN]):
        raise SystemExit("required source, fixture, or tool missing")
    if Path(sys.executable).resolve() != PYTHON.resolve() or sys.version_info[:3] != (3, 12, 14):
        raise SystemExit("pinned Python interpreter mismatch")
    python_version = subprocess.run([str(PYTHON), "--version"], cwd=ROOT, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, check=True).stdout.decode().strip()
    if python_version != "Python 3.12.14":
        raise SystemExit("pinned Python version output mismatch")
    source_before = file_hashes()
    git_before = snapshot()
    version = subprocess.run([str(AIKEN), "--version"], cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=True).stdout.decode().strip()
    if version != "aiken v1.1.21+42babe5":
        raise SystemExit("pinned Aiken version mismatch")
    command = [str(PYTHON), "-B", str(HARNESS), "--aiken", str(AIKEN),
               "--tx-sim-r3-canaries", "--output", str(result_path)]
    cp = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if cp.returncode != 0 or not result_path.is_file():
        raise SystemExit("current-source R3 canary mode failed; sanitized capture withheld")
    result_bytes = result_path.read_bytes()
    result = json.loads(result_bytes)
    stdout_result = json.loads(cp.stdout)
    expected = [("valid", "script_accepted", 0), ("invalid_signature", "compiled_evaluation", 1)]
    observed = [(r.get("id"), r.get("result"), r.get("simulator_child_exit")) for r in result.get("canaries", [])]
    if (result != stdout_result or result.get("status") != "pass" or
        result.get("mode") != "snapshot_bound_transaction_canaries_only" or
        result.get("registry") != "not_run" or observed != expected):
        raise SystemExit("unexpected current-source canary classifications")
    if result.get("evidence_class") != "synthetic_local_transaction_simulator":
        raise SystemExit("evidence class mismatch")
    if file_hashes() != source_before or snapshot() != git_before:
        raise SystemExit("source or Git refs changed during canary run")
    run = {
        "schema_version": "m3-f05-verify-signature-r3-current-r2",
        "purpose": "Current-source comparison of fixed synthetic valid and invalid-signature canaries; no registry, F05 case, or mutation run.",
        "command": command,
        "execution_boundary": "bwrap --unshare-net; checkout read-only; evidence directory only writable",
        "toolchain": {"python": python_version, "python_path": str(PYTHON),
                      "python_sha256": sha(PYTHON.read_bytes()), "aiken": version,
                      "aiken_path": str(AIKEN), "aiken_sha256": sha(AIKEN.read_bytes())},
        "git_before": git_before, "git_after": snapshot(),
        "source_input_sha256": source_before,
        "process": {"exit_code": cp.returncode, "stdout_sha256": sha(cp.stdout),
                    "stderr_sha256": sha(cp.stderr), "result_sha256": sha(result_bytes)},
        "capture_script_sha256": sha(Path(__file__).read_bytes()),
        "result_sha256": sha(result_bytes),
        "canary_classifications": observed,
        "ledger_counts": {"negative_cases": "45/55", "mutations": "18/21"},
        "evidence_credit": "No registered F05 case or mutation credit; synthetic simulator only; no ledger admission or live-network evidence."
    }
    if run_path.exists():
        raise SystemExit("RUN.json already exists; refusing overwrite")
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"exit_code": cp.returncode, "canaries": observed,
                      "policy_id": result["canaries"][0]["policy_id"],
                      "source_sha256": source_before[HARNESS.relative_to(ROOT).as_posix()]}, sort_keys=True))
if __name__ == "__main__":
    main()
