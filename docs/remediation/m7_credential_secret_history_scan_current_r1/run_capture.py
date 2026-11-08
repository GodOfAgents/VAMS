import hashlib
import json
import subprocess
from pathlib import Path

root = Path("/home/GodOfAgents/code/VAMS-testnet")
base = root / "docs/remediation/m7_credential_secret_history_scan_current_r1"
python = "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
commands = [
    ("default_credential_scan", [python, "-B", "scripts/security/default_credential_scan.py"]),
    ("secret_history_prevention_scan", [python, "-B", "scripts/security/secret_history_prevention_scan.py"]),
]
results = []
for name, command in commands:
    argv = ["bwrap", "--unshare-net", "--ro-bind", "/", "/", "--tmpfs", "/tmp", "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--bind", str(base), str(base), "--chdir", str(root), "--clearenv", "--setenv", "PATH", "/usr/bin:/bin"] + command
    result = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (base / (name + ".stdout")).write_bytes(result.stdout)
    (base / (name + ".stderr")).write_bytes(result.stderr)
    (base / (name + ".exit")).write_text(str(result.returncode) + chr(10))
    results.append({"name": name, "bwrap_argv": argv, "exit_code": result.returncode})
paths = ["scripts/security/default_credential_scan.py", "scripts/security/secret_history_prevention_scan.py", ".github/workflows/security-gates.yml"]
hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}
metadata = {"schema_version": "m7-credential-and-secret-history-current-r1", "date": "2026-10-03", "status": "awaiting_independent_review", "repository": {"head": "829ab544571f12efe50ecb5740f129c8acb3e16f", "branch": "testnet/remediation-20260907"}, "toolchain": {"python": "Python 3.12.14", "python_path": python, "network": "bwrap --unshare-net", "checkout": "read-only; evidence directory writable", "environment": "cleared; PATH=/usr/bin:/bin"}, "source_sha256": hashes, "workflow_commands": ["python scripts/security/default_credential_scan.py", "python scripts/security/secret_history_prevention_scan.py"], "results": results, "classification": "Current VAMS-owned tracked and non-ignored untracked filesystem scan; scanner output contains path/line/type only, not matching credential literal values. No full Git-history scan or external secret-service validation.", "independent_review": {"status": "PENDING"}}
(base / "RUN.json").write_text(json.dumps(metadata, indent=2) + chr(10))
raise SystemExit(0 if all(item["exit_code"] == 0 for item in results) else 1)
