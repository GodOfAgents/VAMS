#!/usr/bin/env python3
"""Run all-category TruffleHog without exposing candidate values to logs/artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SAFE_GIT_FIELDS = ("commit", "file", "line", "repository")


def sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    source_metadata = event.get("SourceMetadata")
    data = source_metadata.get("Data", {}) if isinstance(source_metadata, dict) else {}
    git_data = data.get("Git", {}) if isinstance(data, dict) else {}
    if not isinstance(git_data, dict):
        git_data = {}
    sanitized: dict[str, Any] = {
        "detector": str(event.get("DetectorName", "unknown")),
        "verified": event.get("Verified") is True,
    }
    for field in SAFE_GIT_FIELDS:
        value = git_data.get(field)
        if isinstance(value, (str, int)) and str(value):
            sanitized[field] = value
    return sanitized


def run(output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "trufflehog",
        "git",
        f"file://{Path.cwd().as_posix()}",
        "--json",
        "--fail",
        "--no-update",
        "--results=verified,unknown,unverified",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    findings: list[dict[str, Any]] = []
    malformed = 0
    assert process.stdout is not None
    for line in process.stdout:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(event, dict):
            findings.append(sanitize_event(event))
        else:
            malformed += 1
    return_code = process.wait()
    report = {
        "command_profile": "git-all-results-no-update",
        "findings_count": len(findings),
        "verified_count": sum(1 for item in findings if item["verified"]),
        "unverified_or_unknown_count": sum(
            1 for item in findings if not item["verified"]
        ),
        "malformed_event_count": malformed,
        "scanner_exit_code": return_code,
        "findings": findings,
    }
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if malformed or findings or return_code != 0:
        print(
            "TruffleHog gate failed: "
            f"{len(findings)} sanitized findings, {malformed} malformed events."
        )
        return 1
    print("TruffleHog gate passed with zero findings across all result classes.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    sys.exit(main())
