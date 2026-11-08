from pathlib import Path
import subprocess

root = Path("/home/GodOfAgents/code/VAMS-testnet")
base = root / "docs/remediation/m3_f05_2a_r3_harness_current_r3"
command = [
    "bwrap", "--unshare-net", "--ro-bind", "/", "/", "--tmpfs", "/tmp",
    "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--bind", str(base), str(base),
    "--chdir", str(root),
    "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python", "-B",
    "scripts/remediation/test_f05_2a_authority_bootstrap_public.py",
    "--aiken", "/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken",
    "--tx-sim-r3-canaries", "--output", str(base / "RESULT.json"),
]
result = subprocess.run(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
(base / "RUN.stdout").write_bytes(result.stdout)
(base / "RUN.stderr").write_bytes(result.stderr)
(base / "RUN.exit").write_text(str(result.returncode) + chr(10))
raise SystemExit(result.returncode)
