#!/usr/bin/env python3
"""Run lockfile-only npm audits and retain sanitized vulnerability metadata."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
BIN = pathlib.Path(
    "/home/GodOfAgents/vams-evidence/toolchains/node-22.23.2/unpacked/"
    "node-v22.23.2-linux-x64/bin"
)
OUTPUT = pathlib.Path(__file__).resolve().parent / "RESULT.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    env = os.environ.copy()
    env["PATH"] = f"{BIN}:{env.get('PATH', '')}"
    env["npm_config_cache"] = "/tmp/vams-npm-audit-cache"
    env["npm_config_userconfig"] = "/dev/null"
    results = []
    for label, extra in (("all", []), ("production", ["--omit=dev"])):
        command = [
            str(BIN / "npm"), "audit", "--package-lock-only", "--json",
            "--audit-level=high", "--ignore-scripts", *extra
        ]
        completed = subprocess.run(
            command, cwd=ROOT / "frontend-vite", env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )
        raw = completed.stdout
        try:
            report = json.loads(raw)
            parsed = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            report = {}
            parsed = False
        vulnerabilities = []
        for name, item in sorted(report.get("vulnerabilities", {}).items()):
            fix = item.get("fixAvailable")
            fix_summary = (
                {key: fix.get(key) for key in ("name", "version", "isSemVerMajor")}
                if isinstance(fix, dict) else fix
            )
            via = []
            for advisory in item.get("via", []):
                if isinstance(advisory, dict):
                    via.append({
                        key: advisory.get(key)
                        for key in ("source", "name", "title", "severity", "range", "url")
                    })
                else:
                    via.append({"name": advisory})
            vulnerabilities.append({
                "name": name,
                "severity": item.get("severity"),
                "is_direct": item.get("isDirect"),
                "range": item.get("range"),
                "nodes": sorted(item.get("nodes", [])),
                "fix_available": fix_summary,
                "via": via,
                "effects": sorted(item.get("effects", [])),
            })
        results.append({
            "scope": label,
            "command": [
                "npm", "audit", "--package-lock-only", "--json",
                "--audit-level=high", "--ignore-scripts", *extra
            ],
            "exit_code": completed.returncode,
            "report_parse_ok": parsed,
            "raw_output_sha256": sha256(raw),
            "raw_output_retained": False,
            "stderr_sha256": sha256(completed.stderr),
            "vulnerability_count": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
            "dependency_counts": report.get("metadata", {}).get("dependencies", {}),
        })
    OUTPUT.write_text(
        json.dumps({"schema": "m7-npm-audit-sanitized-v1", "results": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if all(item["report_parse_ok"] for item in results) else 2


if __name__ == "__main__":
    sys.exit(main())
