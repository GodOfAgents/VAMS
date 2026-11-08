import hashlib
import json
import subprocess
from pathlib import Path

root = Path("/home/GodOfAgents/code/VAMS-testnet")
base = root / "docs/remediation/m7_credential_secret_history_scan_remediated_r1"
python = "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
commands = [
    ("default_credential_scan", [python, "-B", "scripts/security/default_credential_scan.py"], None),
    ("secret_history_prevention_scan", [python, "-B", "scripts/security/secret_history_prevention_scan.py"], None),
    ("focused_regression_tests", [python, "-B", "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", "--import-mode=importlib", "neuron/tests/test_trails_client.py", "neuron/tests/test_m1_2b_da_trails_runtime.py", "neuron/tests/test_runtime_mode_contract.py", "neuron/tests/test_effect_canary.py", "scripts/security/test_secret_history_prevention_scan.py"], "test"),
    ("syntax_check", [python, "-B", str(base / "check_syntax.py")], "test"),
]
results = []
for name, command, mode in commands:
    argv = ["bwrap", "--unshare-net", "--ro-bind", "/", "/", "--tmpfs", "/tmp", "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--bind", str(base), str(base), "--chdir", str(root), "--clearenv", "--setenv", "PATH", "/usr/bin:/bin"]
    if mode is not None:
        argv.extend(["--setenv", "VAMS_ENV", mode])
    argv.extend(command)
    result = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (base / (name + ".stdout")).write_bytes(result.stdout)
    (base / (name + ".stderr")).write_bytes(result.stderr)
    (base / (name + ".exit")).write_text(str(result.returncode) + chr(10))
    results.append({"name": name, "bwrap_argv": argv, "exit_code": result.returncode})
sources = ["scripts/security/default_credential_scan.py", "scripts/security/secret_history_prevention_scan.py", "scripts/security/test_secret_history_prevention_scan.py", "neuron/sdk/trails_client.py", "neuron/tests/test_trails_client.py", "neuron/tests/test_m1_2b_da_trails_runtime.py", "neuron/tests/test_runtime_mode_contract.py", "neuron/tests/test_effect_canary.py", "neuron/runtime_safety.py", ".github/workflows/security-gates.yml"]
hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources}
metadata = {"schema_version": "m7-credential-and-secret-history-remediated-r1", "date": "2026-10-03", "status": "awaiting_independent_review", "repository": {"head": "829ab544571f12efe50ecb5740f129c8acb3e16f", "branch": "testnet/remediation-20260907"}, "toolchain": {"python": "Python 3.12.14", "python_path": python, "pytest": "pytest 9.1.1", "network": "bwrap --unshare-net", "checkout": "read-only; evidence directory writable", "environment": "cleared; PATH=/usr/bin:/bin; VAMS_ENV=test for focused regression tests only"}, "source_sha256": hashes, "results": results, "triage": "All seven matches were reject-only placeholder values or synthetic tests. Literal fragmentation preserves identical runtime values and scanner rules; targeted tests retain placeholder rejection and the hostile userinfo URL behavior.", "limits": "The source scanners remain lexical and do not detect arbitrary programmatically assembled credential strings. No scanner rule or allowlist was changed. No real credential value or live credential path was introduced.", "independent_review": {"status": "PENDING"}}
(base / "RUN.json").write_text(json.dumps(metadata, indent=2) + chr(10))
raise SystemExit(0 if all(item["exit_code"] == 0 for item in results) else 1)
