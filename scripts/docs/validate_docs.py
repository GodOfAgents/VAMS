#!/usr/bin/env python3
"""Fail closed on high-risk VAMS documentation drift."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "docs" / "documentation-manifest.json"
CURRENT_LIFECYCLE = "current"
FORBIDDEN_CURRENT = {
    "local file URI": r"file:///",
    "obsolete clone URL": r"GodOfAgents/VAMS-main\.git",
    "stale current test total": r"1,083\s+(?:Passing|tests? passing)",
    "unsupported production claim": r"\bproduction-ready infrastructure\b",
}


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _current_documents(manifest: dict) -> list[Path]:
    return [
        ROOT / item["path"]
        for item in manifest.get("documents", [])
        if item.get("lifecycle") == CURRENT_LIFECYCLE
    ]


def _validate_relative_links(path: Path, text: str, errors: list[str]) -> None:
    for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        target = match.group(1).strip().strip("<>")
        if not target or re.match(r"^(https?://|mailto:|#|data:)", target):
            continue
        if target.startswith("file:"):
            errors.append(f"{path.relative_to(ROOT)} contains a local file URI")
            continue
        local_target = target.split("#", 1)[0].split("?", 1)[0]
        if not local_target:
            continue
        resolved = (path.parent / local_target).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"{path.relative_to(ROOT)} link escapes repository: {target}")
            continue
        if not resolved.exists():
            errors.append(f"{path.relative_to(ROOT)} missing link target: {target}")


def validate() -> list[str]:
    errors: list[str] = []
    if not MANIFEST_PATH.is_file():
        return ["documentation manifest is missing"]
    manifest = _load_manifest()
    if manifest.get("current_architecture_version") != "0.8.0":
        errors.append("documentation manifest architecture version must be 0.8.0")

    current_documents = _current_documents(manifest)
    if not current_documents:
        errors.append("documentation manifest has no current documents")
    for path in current_documents:
        if not path.is_file():
            errors.append(f"manifest document is missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".md" and "Last verified:" not in text:
            errors.append(f"{path.relative_to(ROOT)} lacks Last verified metadata")
        for label, pattern in FORBIDDEN_CURRENT.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                errors.append(f"{path.relative_to(ROOT)} contains {label}")
        _validate_relative_links(path, text, errors)

    role_doc = ROOT / "docs" / "role-management-keys.md"
    if role_doc.is_file() and re.search(
        r"Maximum Validity\s*\|[^\n]*(?:48h|72h|7 days|30 days)",
        role_doc.read_text(encoding="utf-8", errors="ignore"),
        flags=re.IGNORECASE,
    ):
        errors.append("role-management guide permits session keys beyond INV-3")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    errors = validate()
    if args.json:
        print(json.dumps({"status": "success" if not errors else "failure", "errors": errors}))
    elif errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Documentation validation passed.")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
