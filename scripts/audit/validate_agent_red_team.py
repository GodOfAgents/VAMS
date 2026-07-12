#!/usr/bin/env python3
"""Validate minimum adversarial coverage for the VAMS agent test corpus."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "docs" / "audit" / "agent-red-team-corpus.json"
REQUIRED_CATEGORIES = {
    "prompt-injection",
    "wallet-capability",
    "session-expiry",
    "contract-scope",
    "identity-outage",
    "tee-binding",
    "memory-poisoning",
    "manifest-escalation",
    "reward-hacking",
    "bridge-confusion",
    "chc-spoofing",
    "duplicate-side-effect",
}


def main() -> int:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    ids = [case.get("id") for case in cases]
    categories = {case.get("category") for case in cases}
    errors: list[str] = []
    if len(ids) != len(set(ids)):
        errors.append("case IDs must be unique")
    missing = REQUIRED_CATEGORIES - categories
    if missing:
        errors.append(f"missing categories: {sorted(missing)}")
    for case in cases:
        if case.get("expected") != "deny":
            errors.append(f"{case.get('id')}: pre-testnet adversarial cases must deny")
        if not case.get("attack"):
            errors.append(f"{case.get('id')}: attack description is required")

    if errors:
        print("Agent red-team corpus validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Agent red-team corpus validation passed: {len(cases)} attack classes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
