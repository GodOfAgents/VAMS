#!/usr/bin/env python3
"""Fail CI when workflow actions or security tools use mutable versions."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "security-gates.yml"
TRUFFLEHOG_GATE = ROOT / "scripts" / "security" / "trufflehog_gate.py"

REQUIRED_ACTION_PINS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-node": "820762786026740c76f36085b0efc47a31fe5020",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
}


def validate() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    errors: list[str] = []
    action_refs = re.findall(r"^\s*uses:\s*[^@\s]+@([^\s#]+)", text, re.MULTILINE)
    if not action_refs:
        errors.append("security workflow contains no action references")
    for ref in action_refs:
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            errors.append(f"GitHub Action is not commit-pinned: {ref}")
    for action, ref in REQUIRED_ACTION_PINS.items():
        if f"uses: {action}@{ref}" not in text:
            errors.append(f"security workflow does not use reviewed Node 24 pin: {action}")
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
    required_controls = (
        "submodules: recursive",
        "version: v1.7.1",
        "--fail-high --json slither-report.json",
        "contracts/slither-adjudications.yml",
        "git-filter-repo==2.47.0",
        "cargo +1.92.0 install cargo-audit --version 0.22.2 --locked",
        "cargo +1.92.0 audit --deny warnings",
        'python -m unittest discover -s scripts/audit -p "test_*.py"',
        "semgrep scan --metrics off --config .semgrep/vams-security.yml --error",
        "--json --output semgrep-reviewed.json",
        ".semgrep/discovery-adjudications.yml",
        "caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648",
        "npm audit --omit=dev --audit-level=high",
        "npm run lint",
    )
    for value in required_controls:
        if value not in text:
            errors.append(f"security workflow is missing required control: {value}")
    if text.count("submodules: recursive") < 2:
        errors.append("Forge and Slither checkouts must both initialize recursive submodules")
    trufflehog_text = TRUFFLEHOG_GATE.read_text(encoding="utf-8")
    if '"--no-verification"' not in trufflehog_text:
        errors.append("TruffleHog gate must not transmit candidate credentials for verification")
    manifest_index = text.find("- name: Generate Commit-Bound Evidence Manifest")
    enforcement_index = text.find("- name: Enforce Required Job Results")
    if manifest_index < 0 or enforcement_index < 0 or manifest_index > enforcement_index:
        errors.append("failure evidence must be generated before aggregate enforcement")
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
