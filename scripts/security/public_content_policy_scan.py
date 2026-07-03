#!/usr/bin/env python3
"""Block non-public proposal and funding draft paths from the public repo."""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BLOCKED_PATTERNS = (
    "docs/funding/**",
    "docs/team/idex-*.md",
)


def _git_files() -> list[str]:
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


def main() -> int:
    blocked: list[str] = []
    for rel_path in _git_files():
        for pattern in BLOCKED_PATTERNS:
            if fnmatch.fnmatch(rel_path, pattern):
                blocked.append(rel_path)
                break

    if blocked:
        print("Public content policy failed. Move these files out of the public repo:")
        for path in blocked:
            print(f"  - {path}")
        return 1

    print("Public content policy scan passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
