#!/usr/bin/env python3
"""Re-prove every .gitleaksignore entry against the accepted disposition manifest.

Owner decision 9 (2026-11-08) accepted 638 first-party current-tree Gitleaks
findings as non-credential. Gitleaks honours `.gitleaksignore` automatically,
so this check must run before any secret-scan gate. It fails unless:

* every ignore entry is an exact `path:rule:line` fingerprint that maps to
  exactly one ACCEPTED_NON_CREDENTIAL record in the manifest, and vice versa;
* every referenced file still exists, is a regular file, and has the SHA-256
  recorded when the finding was proven (any edit invalidates its entries);
* paths stay inside the reviewed evidence areas and the rule is unchanged;
* the recorded line still exists in the file.

It never reads or prints token values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

MANIFEST = Path("docs/remediation/repair_20261108/secret-scan-dispositions.json")
IGNORE = Path(".gitleaksignore")
ALLOWED_PREFIXES = ("docs/remediation/", "scripts/remediation/")
ALLOWED_RULES = {"generic-api-key"}
ACCEPTED = "ACCEPTED_NON_CREDENTIAL"


class ReproofError(RuntimeError):
    pass


def _ignore_entries(path: Path) -> list[str]:
    if not path.is_file() or path.is_symlink():
        raise ReproofError("ignore file unavailable")
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    if len(entries) != len(set(entries)):
        raise ReproofError("duplicate ignore entry")
    return entries


def _split_fingerprint(fingerprint: str) -> tuple[str, str, int]:
    try:
        path, rule, line = fingerprint.rsplit(":", 2)
        number = int(line)
    except ValueError as exc:
        raise ReproofError("malformed fingerprint") from exc
    pure = PurePosixPath(path)
    if (number < 1 or pure.is_absolute() or ".." in pure.parts or str(pure) != path
            or not path.startswith(ALLOWED_PREFIXES) or rule not in ALLOWED_RULES):
        raise ReproofError("fingerprint outside the reviewed scope")
    return path, rule, number


def reprove(root: Path) -> int:
    entries = _ignore_entries(root / IGNORE)
    manifest_path = root / MANIFEST
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ReproofError("disposition manifest unavailable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("findings")
    if not isinstance(records, list) or not records:
        raise ReproofError("disposition manifest has no findings")
    by_fingerprint: dict[str, dict] = {}
    for record in records:
        fingerprint = record.get("gitleaks_fingerprint")
        if not isinstance(fingerprint, str) or fingerprint in by_fingerprint:
            raise ReproofError("missing or duplicate manifest fingerprint")
        if record.get("disposition") != ACCEPTED or not record.get("owner_ruling"):
            raise ReproofError("manifest record is not an accepted owner ruling")
        path, rule, line = _split_fingerprint(fingerprint)
        if (record.get("file"), record.get("rule"), record.get("line")) != (path, rule, line):
            raise ReproofError("manifest record does not match its fingerprint")
        by_fingerprint[fingerprint] = record
    if set(entries) != set(by_fingerprint):
        raise ReproofError("ignore entries and accepted manifest records differ")
    hashes: dict[str, str] = {}
    lines: dict[str, int] = {}
    for fingerprint in entries:
        record = by_fingerprint[fingerprint]
        relative = record["file"]
        target = root / Path(*relative.split("/"))
        if relative not in hashes:
            if not target.is_file() or target.is_symlink():
                raise ReproofError("ignored file is missing or not a regular file")
            data = target.read_bytes()
            hashes[relative] = hashlib.sha256(data).hexdigest()
            lines[relative] = len(data.splitlines())
        if hashes[relative] != record.get("file_sha256"):
            raise ReproofError("ignored file changed since its finding was proven")
        if record["line"] > lines[relative]:
            raise ReproofError("ignored line no longer exists")
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        count = reprove(args.repo.resolve())
    except (ReproofError, OSError, UnicodeError, ValueError) as exc:
        print(f"gitleaks_ignore_reproof=fail reason={exc}", file=sys.stderr)
        return 1
    print(f"gitleaks_ignore_reproof=pass entries={count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
