#!/usr/bin/env python3
"""Fail CI when default credentials are introduced into VAMS-owned files."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath


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

# Exact existing negative controls and detector/documentation bytes. These are
# security-test evidence, never accepted runtime credentials. A changed, missing,
# moved or linked file fails closed; no directory or pattern is exempted.
REGRESSION_EVIDENCE = {
    ".semgrep/tests/vams-security.js": (
        "af3ef6d8804e8b1ebba7f7dd66a7551adb91221712b86ae47022dcab16bbb032",
        (2, 4),
    ),
    ".semgrep/tests/vams-security.py": (
        "13863c7137c1375b2886052a9b20f027936b451959754ede2e4dbcf051004703",
        (36, 38, 40),
    ),
    ".semgrep/vams-security.yml": (
        "57755ad0d0dbada28a1db429ed78cd8e33c7e10ac0a9ea98b91b5cbc9230361d",
        (63, 70, 71, 75, 82, 83, 84),
    ),
    "docs/remediation/repair_20261110/SEMGREP-VAMS-RULES.md": (
        "61985429e23973115f225b7d5e674202e233af38174f53c48e8f4142a7856201",
        (22,),
    ),
}


def _git_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        os.fsdecode(item)
        for item in result.stdout.split(b"\0")
        if item
    ]


def _is_excluded(path: str) -> bool:
    if path.startswith(EXCLUDED_PREFIXES):
        return True
    return bool(set(PurePosixPath(path).parts) & EXCLUDED_PARTS)


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


def _regression_evidence(root: Path, paths: set[str]) -> tuple[dict[str, str], list[str]]:
    valid: dict[str, str] = {}
    errors: list[str] = []
    for relative, (digest, expected_lines) in REGRESSION_EVIDENCE.items():
        path = root / relative
        try:
            parts = Path(relative).parts
            linked = any(root.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts) + 1))
            if relative not in paths or linked or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("missing or linked evidence")
            info = path.stat()
            # All four frozen files are small. Bound the read even if a checked
            # out file is concurrently replaced or grown.
            if not stat.S_ISREG(info.st_mode) or info.st_size > 32_768:
                raise ValueError("invalid evidence file")
            with path.open("rb") as stream:
                data = stream.read(32_769)
            if len(data) > 32_768 or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("evidence changed")
            text = data.decode("utf-8")
            lines = tuple(i for i, line in enumerate(text.splitlines(), 1)
                          if TOKENS["default gateway password"] in line)
            if lines != expected_lines:
                raise ValueError("evidence occurrence set changed")
        except (OSError, UnicodeError, ValueError):
            errors.append(f"{relative}: security regression evidence changed or unavailable")
        else:
            valid[relative] = text
    return valid, errors


def scan(root: Path, paths: list[str]) -> list[str]:
    # Git emits slash-separated paths, including on Windows. Backslashes in
    # POSIX filenames and undecodable bytes are distinct inventory identities.
    inventory = set(paths)
    valid_evidence, findings = _regression_evidence(root, inventory)

    for relative in sorted(inventory):
        if _is_excluded(relative):
            continue
        if relative in REGRESSION_EVIDENCE and relative not in valid_evidence:
            # Already a blocking finding. Do not follow or read invalid evidence.
            continue

        # The exemption applies only to the buffer actually hashed above.
        # Never reopen frozen evidence after validating it.
        text = valid_evidence[relative] if relative in valid_evidence else _read_text(root / relative)
        if text is None:
            continue

        for label, token in TOKENS.items():
            if token not in text:
                continue
            if (label, relative) in ALLOWLIST:
                continue
            if label == "default gateway password" and relative in valid_evidence:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                if token in line:
                    findings.append(f"{relative}:{line_no}: {label} token is not allowed")

    return findings


def main() -> int:
    findings = scan(ROOT, _git_files())
    if findings:
        print("Default credential scan failed:")
        for finding in findings:
            print(f"  - {finding}")
        return 1

    print("Default credential scan passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
