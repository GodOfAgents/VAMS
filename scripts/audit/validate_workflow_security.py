#!/usr/bin/env python3
"""Fail CI when workflow actions or security tools use mutable versions."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "security-gates.yml"


def validate() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    errors: list[str] = []
    action_refs = re.findall(r"^\s*uses:\s*[^@\s]+@([^\s#]+)", text, re.MULTILINE)
    if not action_refs:
        errors.append("security workflow contains no action references")
    for ref in action_refs:
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            errors.append(f"GitHub Action is not commit-pinned: {ref}")
    forbidden = (
        "txpipe/setup-aiken",
        "trufflesecurity/trufflehog@main",
        "version: stable",
        "pip install --upgrade pip",
        "pip install slither-analyzer\n",
        "pip install semgrep\n",
    )
    for value in forbidden:
        if value in text:
            errors.append(f"security workflow contains mutable tool reference: {value}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Workflow supply-chain validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Workflow supply-chain validation passed: all {len(re.findall(r'uses:', WORKFLOW.read_text(encoding='utf-8')))} actions are commit-pinned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
