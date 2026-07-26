#!/usr/bin/env python3
"""Exercise the narrow Gitleaks allowlists against generated decoy fixtures."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".gitleaks.toml"


def _run(source: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "gitleaks",
            "dir",
            str(source),
            "--config",
            str(CONFIG),
            "--redact=100",
            "--report-format",
            "json",
            "--report-path",
            str(report),
            "--exit-code",
            "1",
            "--no-banner",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main() -> int:
    if shutil.which("gitleaks") is None:
        print("Gitleaks allowlist regression requires the pinned gitleaks binary.")
        return 2

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        allowed = root / "allowed"
        blocked = root / "blocked"
        (allowed / "neuron").mkdir(parents=True)
        (allowed / "contracts" / "script").mkdir(parents=True)
        (allowed / "neuron" / "secp256k1.py").write_text(
            "key.curve, ec.SECP256K1\n", encoding="utf-8"
        )
        (allowed / "neuron" / "config.py").write_text(
            'ADDRESS = "0x' + ("1" * 40) + '"\n', encoding="utf-8"
        )
        (allowed / "contracts" / "script" / "DeployX402.s.sol").write_text(
            'address constant TARGET = 0x' + ("2" * 40) + ";\n",
            encoding="utf-8",
        )

        blocked.mkdir()
        private_key = hashlib.sha256(b"vams-private-key-negative-fixture").hexdigest()
        adjacent_key = hashlib.sha256(b"vams-adjacent-negative-fixture").hexdigest()
        generic_token = base64.urlsafe_b64encode(
            hashlib.sha256(b"vams-generic-token-negative-fixture").digest()
        ).decode("ascii").rstrip("=")
        aws_suffix = base64.b32encode(
            hashlib.sha256(b"vams-aws-negative-fixture").digest()
        ).decode("ascii")[:16]
        fixtures = {
            "private-key.txt": 'private_key = "' + private_key + '"\n',
            "aws-token.txt": "aws_access_key_id = "
            + ("AKIA" + aws_suffix)
            + "\n",
            "generic-token.txt": 'api_key = "' + generic_token + '"\n',
            "adjacent-secret.txt": 'address = "0x'
            + ("3" * 40)
            + '"\nprivate_key = "'
            + adjacent_key
            + '"\n',
        }
        for name, content in fixtures.items():
            (blocked / name).write_text(content, encoding="utf-8")

        allowed_report = root / "allowed.json"
        blocked_report = root / "blocked.json"
        allowed_result = _run(allowed, allowed_report)
        blocked_result = _run(blocked, blocked_report)
        if allowed_result.returncode != 0:
            print("Gitleaks narrow allowlist rejected approved public expressions.")
            return 1
        if blocked_result.returncode != 1 or not blocked_report.is_file():
            print("Gitleaks negative fixtures did not fail closed.")
            return 1
        try:
            findings = json.loads(blocked_report.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            print("Gitleaks negative fixture report is missing or invalid.")
            return 1
        finding_paths = {
            Path(str(item.get("File", "")).replace("\\", "/")).name
            for item in findings
            if isinstance(item, dict)
        }
        missing = set(fixtures) - finding_paths
        if missing:
            print(
                "Gitleaks allowlist regression missed negative fixture categories: "
                + ", ".join(sorted(missing))
            )
            return 1
        print(
            "Gitleaks allowlist regression passed: public expressions allowed; "
            "four secret categories rejected."
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
