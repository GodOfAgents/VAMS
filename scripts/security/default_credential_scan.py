#!/usr/bin/env python3
"""Fail CI when default credentials are introduced into VAMS-owned files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".data/",
    "contracts/lib/",
    "contracts/out/",
    "node_modules/",
    "frontend-vite/node_modules/",
)
EXCLUDED_PARTS = {".pytest_cache", "__pycache__"}
TOKENS = {
    "default gateway password": "vams" + "2026",
    "demo API key": "demo" + "-key",
    "placeholder secret": "change" + "me",
}
ALLOWLIST = {
    ("default gateway password", "gateway/server.py"),
    ("default gateway password", "AGENTS.md"),
    ("default gateway password", "REPO_STATUS_REPORT.md"),
    ("default gateway password", "docs/CHANGELOG.md"),
}


def _git_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8", errors="ignore")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _is_excluded(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith(EXCLUDED_PREFIXES):
        return True
    return bool(set(Path(normalized).parts) & EXCLUDED_PARTS)


def _read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="ignore")


def main() -> int:
    findings: list[str] = []

    for rel_path in _git_files():
        normalized = rel_path.replace("\\", "/")
        if _is_excluded(normalized):
            continue

        text = _read_text(ROOT / normalized)
        if text is None:
            continue

        for label, token in TOKENS.items():
            if token not in text:
                continue
            if (label, normalized) in ALLOWLIST:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                if token in line:
                    findings.append(f"{normalized}:{line_no}: {label} token is not allowed")

    if findings:
        print("Default credential scan failed:")
        for finding in findings:
            print(f"  - {finding}")
        return 1

    print("Default credential scan passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
