#!/usr/bin/env python3
"""Run all-category TruffleHog without exposing candidate values to logs/artifacts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SAFE_GIT_FIELDS = ("commit", "file", "line", "repository")


def _trufflehog_binary() -> str | None:
    configured = os.environ.get("TRUFFLEHOG_BIN")
    if configured:
        binary = Path(configured)
        return str(binary) if binary.is_file() else None
    return shutil.which("trufflehog")


def _is_bare_repository() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-bare-repository"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


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


def _is_safe_local_repository_uri(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "file"
        and parsed.hostname in {None, "", "localhost"}
        and parsed.username is None
        and parsed.password is None
        and bool(parsed.path)
        and not parsed.query
        and not parsed.fragment
    )


def run(output: Path, repository_uri: str | None = None) -> int:
    binary = _trufflehog_binary()
    if binary is None:
        print("TruffleHog gate requires the pinned trufflehog binary.")
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    if repository_uri is None:
        repository_uri = Path.cwd().resolve().as_uri()
        bare_repository = _is_bare_repository()
    elif not _is_safe_local_repository_uri(repository_uri):
        print("Explicit TruffleHog repository URI must be a credential-free local file URI.")
        return 2
    else:
        bare_repository = False
    command = [
        binary,
        "git",
        repository_uri,
        "--json",
        "--fail",
        "--no-update",
        "--no-verification",
        "--results=verified,unknown,unverified",
    ]
    if bare_repository:
        command.append("--bare")
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
        "command_profile": "git-all-results-no-verification",
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
    parser.add_argument("--repository-uri")
    args = parser.parse_args()
    return run(args.output, args.repository_uri)


if __name__ == "__main__":
    sys.exit(main())
