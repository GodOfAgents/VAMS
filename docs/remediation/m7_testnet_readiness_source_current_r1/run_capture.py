import hashlib
import json
import subprocess
from pathlib import Path

root = Path("/home/GodOfAgents/code/VAMS-testnet")
base = root / "docs/remediation/m7_testnet_readiness_source_current_r1"
python = "/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
commands = [
    ("ceremony_source_scan", [python, "-B", "scripts/audit/deployment_readiness.py"], False),
    ("ceremony_source_tests", [python, "-B", "scripts/audit/test_deployment_readiness.py"], False),
    ("testnet_live_mode_preflight", [python, "-B", "scripts/security/runtime_mode_preflight.py", "--require-live", "--expected-mode", "testnet"], True),
    ("runtime_preflight_tests", [python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "scripts/security/test_runtime_mode_preflight.py"], False),
]
results = []
for name, command, testnet_env in commands:
    argv = ["bwrap", "--unshare-net", "--ro-bind", "/", "/", "--tmpfs", "/tmp", "--dev-bind", "/dev", "/dev", "--proc", "/proc", "--bind", str(base), str(base), "--chdir", str(root), "--clearenv", "--setenv", "PATH", "/usr/bin:/bin"]
    if testnet_env:
        argv.extend(["--setenv", "VAMS_ENV", "testnet"])
    argv.extend(command)
    result = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (base / (name + ".stdout")).write_bytes(result.stdout)
    (base / (name + ".stderr")).write_bytes(result.stderr)
    (base / (name + ".exit")).write_text(str(result.returncode) + chr(10))
    results.append({"name": name, "bwrap_argv": argv, "exit_code": result.returncode})
source_paths = [".github/workflows/security-gates.yml", "scripts/audit/deployment_readiness.py", "scripts/audit/test_deployment_readiness.py", "scripts/security/runtime_mode_preflight.py", "scripts/security/test_runtime_mode_preflight.py", "neuron/runtime_safety.py", "contracts/script/DeployTestnet.s.sol", "contracts/src/governance/VAMSTimelockController.sol", "contracts/src/governance/GovernorExecutor.sol", "contracts/src/token/VAMSToken.sol", "contracts/script/DeployV2.s.sol", "contracts/script/DeployVAMS.s.sol", "cdk-deployment/deploy.sh"]
source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in source_paths}
metadata = {"schema_version": "m7-deployment-source-and-mode-preflight-current-r1", "date": "2026-10-03", "status": "awaiting_independent_review", "repository": {"head": "829ab544571f12efe50ecb5740f129c8acb3e16f", "branch": "testnet/remediation-20260907"}, "toolchain": {"python": "Python 3.12.14", "python_path": python, "pytest": "pytest 9.1.1", "network": "bwrap --unshare-net", "checkout": "read-only; evidence directory writable", "environment": "cleared; testnet mode set only for preflight command"}, "source_sha256": source_hashes, "workflow_commands": ["python scripts/audit/deployment_readiness.py", "python scripts/audit/test_deployment_readiness.py", "VAMS_ENV=testnet python scripts/security/runtime_mode_preflight.py --require-live --expected-mode testnet", "python -m pytest -q scripts/security/test_runtime_mode_preflight.py"], "results": results, "limits": "Static source assertions and local runtime-mode policy only. No on-chain Safe role ownership, addresses, explorer verification, wallet credentials, live chain interaction, full release gates, or deployment readiness is established.", "independent_review": {"status": "PENDING"}}
(base / "RUN.json").write_text(json.dumps(metadata, indent=2) + chr(10))
raise SystemExit(0 if all(item["exit_code"] == 0 for item in results) else 1)
