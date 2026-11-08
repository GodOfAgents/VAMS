from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

root = Path("/home/GodOfAgents/code/VAMS-testnet")
out = root / "docs/remediation/m7_f05_address_option_r1"
aiken = "/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken"
python = "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
source = root / "scripts/remediation/test_f05_2a_authority_bootstrap_public.py"
cardano = sorted(path for path in (root / "cardano").rglob("*") if path.is_file() and "build" not in path.relative_to(root / "cardano").parts)
protected = [source, root / "scripts/remediation/test_f05_2a_address_encoding.py", *cardano]
def inventory():
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
before = inventory()
command = ["bwrap", "--unshare-net", "--ro-bind", "/", "/", "--tmpfs", "/tmp", "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--bind", str(out), str(out), "--chdir", str(root), python, "-B", str(source), "--aiken", aiken, "--output", str(out / "HARNESS_RESULT.json")]
completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=900)
(out / "HARNESS.stdout").write_text(completed.stdout)
(out / "HARNESS.stderr").write_text(completed.stderr)
(out / "HARNESS.exit").write_text(str(completed.returncode) + "\n")
after = inventory()
summary = {"schema": "f05-address-harness-capture-v1", "command": command, "exit_code": completed.returncode, "protected_file_count": len(before), "protected_unchanged": before == after, "protected_before": before, "protected_after": after, "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(), "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(), "result_created": (out / "HARNESS_RESULT.json").exists(), "stderr_tail": completed.stderr.splitlines()[-8:]}
(out / "HARNESS_CAPTURE.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("exit_code", "protected_file_count", "protected_unchanged", "result_created", "stderr_tail")}, indent=2))
raise SystemExit(0 if before == after else 3)
