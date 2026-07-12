#!/usr/bin/env python3
"""Validate architecture-version and core-invariant source traceability."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = ROOT / "docs" / "audit"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    matrix = _load(AUDIT_DIR / "control-matrix.json")
    architecture = _load(AUDIT_DIR / "architecture-traceability.json")
    controls = _load(AUDIT_DIR / "invariant-controls.json")
    current = architecture.get("current_architecture_version")
    if current != matrix.get("architecture_version"):
        errors.append("architecture traceability version does not match control matrix")
    if controls.get("architecture_version") != current:
        errors.append("invariant control version does not match current architecture")

    versions = architecture.get("versions", [])
    if [item.get("version") for item in versions] != [
        "0.3.0", "0.4.0", "0.5.0", "0.6.0", "0.7.0", "0.8.0"
    ]:
        errors.append("architecture versions must trace 0.3.0 through 0.8.0")
    for item in versions:
        if item.get("lifecycle") not in {"historical", "current"}:
            errors.append(f"architecture version {item.get('version')} has invalid lifecycle")
        if not isinstance(item.get("maturity"), str) or not item["maturity"].strip():
            errors.append(f"architecture version {item.get('version')} lacks maturity")
        path = ROOT / item.get("document", "")
        if not path.is_file():
            errors.append(f"architecture document is missing: {path.relative_to(ROOT)}")
    for component in architecture.get("current_components", []):
        if not (ROOT / component).is_file():
            errors.append(f"current architecture component is missing: {component}")

    control_items = controls.get("controls", [])
    ids = [item.get("id") for item in control_items]
    expected_ids = [f"INV-{index}" for index in range(1, 11)]
    if ids != expected_ids:
        errors.append("invariant controls must be exactly INV-1 through INV-10")
    for control in control_items:
        for group in ("enforcement", "tests"):
            anchors = control.get(group)
            if not isinstance(anchors, list) or not anchors:
                errors.append(f"{control.get('id')} has no {group} anchors")
                continue
            for anchor in anchors:
                relative_path = anchor.get("path", "")
                path = ROOT / relative_path
                if not path.is_file():
                    errors.append(f"{control.get('id')} missing anchor: {relative_path}")
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                for expected in anchor.get("must_contain", []):
                    if expected not in text:
                        errors.append(
                            f"{control.get('id')} anchor {relative_path} lacks {expected!r}"
                        )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Architecture and invariant traceability failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Architecture 0.8.0 and INV-1..INV-10 traceability passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
