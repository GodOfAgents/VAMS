#!/usr/bin/env python3
"""Reject files and credential-shaped literals targeted by the incident rewrite."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_PATHS = {
    "node_identity.pem",
    "neuron/node_identity.pem",
    "simulate-request.mjs",
    "simulate-request-v2.mjs",
    "simulate-request-v3.mjs",
    "register-agent.mjs",
    "verify-escrow.mjs",
    "contracts/test_output_cmd.json",
    "contracts/clean_output.json",
    "neuron/eth_client/sequence_wallet.py",
    "telegram-bot/bot.js",
}
FORBIDDEN_PREFIXES = (".foundry/",)
FORBIDDEN_MAP_NAMES = {"replacements.txt", "replacement-map.txt"}
CREDENTIAL_URI = re.compile(
    r"(?i)\b(?:postgres(?:ql)?|https?)://([^\s/:@]+):([^\s/@]+)@"
)
PLACEHOLDER = re.compile(r"\$\{[A-Z][A-Z0-9_]*\}")
REPLACEMENT_DIRECTIVE = re.compile(
    r"(?im)^\s*literal:(?:postgres(?:ql)?|https?)://[^\r\n]+==>"
)


def _repository_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8", errors="ignore").replace("\\", "/")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    return raw.decode("utf-8", errors="ignore")


def _pure_name(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def scan_paths(root: Path, paths: Iterable[str]) -> list[str]:
    findings: list[str] = []
    for value in paths:
        normalized = value.replace("\\", "/")
        if (
            normalized == ".foundry"
            or normalized in FORBIDDEN_PATHS
            or normalized.startswith(FORBIDDEN_PREFIXES)
        ):
            findings.append(f"{normalized}: incident-removal path must not be tracked")
            continue
        if _pure_name(normalized) in FORBIDDEN_MAP_NAMES:
            findings.append(f"{normalized}: replacement maps must remain external")
            continue
        text = _read_text(root / normalized)
        if text is None:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in CREDENTIAL_URI.finditer(line):
                user, password = match.groups()
                if PLACEHOLDER.fullmatch(user) and PLACEHOLDER.fullmatch(password):
                    continue
                findings.append(
                    f"{normalized}:{line_no}: credential-shaped URI literal is forbidden"
                )
        if REPLACEMENT_DIRECTIVE.search(text):
            findings.append(
                f"{normalized}: exact replacement-map directives must remain external"
            )
    return findings


def main() -> int:
    findings = scan_paths(ROOT, _repository_files())
    if findings:
        print("Secret-history prevention scan failed:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("Secret-history prevention scan passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
