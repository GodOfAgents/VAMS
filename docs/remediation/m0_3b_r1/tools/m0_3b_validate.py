#!/usr/bin/env python3
"""Validate the sanitized M0.3b evidence package and its exact schemas."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m0_3b_adjudicator as m


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=m.base._pairs,
    )




def reject_sensitive(value, field=""):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z]", "", key.lower()) if isinstance(key, str) else ""
            if not isinstance(key, str) or normalized in m.base.FORBIDDEN:
                raise m.AdjudicationError("forbidden durable field")
            reject_sensitive(child, key)
    elif isinstance(value, list):
        for child in value:
            reject_sensitive(child, field)
    elif isinstance(value, str):
        if len(value) > 4096:
            raise m.AdjudicationError("unsafe durable string")
        if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\\s+[A-Za-z0-9._-]+|AKIA[0-9A-Z]{16}", value):
            raise m.AdjudicationError("suspicious durable string")
    elif value is not None and type(value) not in {bool, int, float}:
        raise m.AdjudicationError("unsafe durable type")

def validate(repo, evidence):
    repo = Path(repo).resolve()
    evidence = Path(evidence).resolve()
    manifest = evidence / "SHA256SUMS"
    entries = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not re.fullmatch(r"[0-9a-f]{64}  [A-Za-z0-9_./-]+", line):
            raise m.AdjudicationError("invalid checksum line")
        expected, name = line.split("  ")
        if name in entries or name == "SHA256SUMS":
            raise m.AdjudicationError("duplicate or recursive checksum")
        target = (evidence / name).resolve()
        if evidence not in target.parents or not target.is_file():
            raise m.AdjudicationError("unsafe checksum target")
        if digest(target) != expected:
            raise m.AdjudicationError("checksum mismatch")
        entries[name] = expected
    required = {
        "findings.json",
        "decisions.json",
        "ledger.json",
        "summary.json",
        "record.json",
        "reachability.json",
        "commands.json",
        "environment.json",
        "reviewed-hashes.json",
        "source-manifest.json",
        "excluded-gitlinks.json",
        "verification/m0_3b_reconcile.py",
        "verification/m0_3b_mutations.py",
    }
    if not required.issubset(entries):
        raise m.AdjudicationError("missing evidence artifact")
    findings = load(evidence / "findings.json")
    decisions = load(evidence / "decisions.json")
    ledger = load(evidence / "ledger.json")
    summary = load(evidence / "summary.json")
    record = load(evidence / "record.json")
    reachability = load(evidence / "reachability.json")
    commands = load(evidence / "commands.json")
    environment = load(evidence / "environment.json")
    reviewed = load(evidence / "reviewed-hashes.json")
    for value in (
        findings,
        decisions,
        ledger,
        summary,
        record,
        reachability,
        commands,
        environment,
        reviewed,
    ):
        reject_sensitive(value)
    finding_records = findings.get("records")
    decision_records = decisions.get("records")
    ledger_records = ledger.get("records")
    if not all(isinstance(value, list) for value in (finding_records, decision_records, ledger_records)):
        raise m.AdjudicationError("invalid record containers")
    if not (len(finding_records) == len(decision_records) == len(ledger_records) == 160):
        raise m.AdjudicationError("record count mismatch")
    for record_item in finding_records + decision_records + ledger_records:
        m.validate_record(record_item)
    ids = [
        {record_item["finding_id"] for record_item in records}
        for records in (finding_records, decision_records, ledger_records)
    ]
    if any(len(value) != 160 for value in ids) or not (ids[0] == ids[1] == ids[2]):
        raise m.AdjudicationError("identity reconciliation failure")
    if m.base.encoded(decision_records) != m.base.encoded(ledger_records):
        raise m.AdjudicationError("approved ledger differs from decisions")
    if summary.get("disposition_totals") != {
        "confirmed_noncredential_fixture": 160,
        "potential_credential": 0,
        "unresolved": 0,
    }:
        raise m.AdjudicationError("unexpected dispositions")
    if record.get("scanner_exit") != 1 or record.get("adjudication_exit") != 0 or record.get("raw_removed") is not True:
        raise m.AdjudicationError("unexpected run result")
    if set(reachability.get("domains", {}).values()) != {"absent"}:
        raise m.AdjudicationError("reachability is not absent")
    for item in commands:
        command = item.get("command")
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(argument, str) or "<" in argument or ">" in argument for argument in command)
        ):
            raise m.AdjudicationError("placeholder or invalid command")
    if any("raw" in path.name.lower() and path.name != "reviewed-hashes.json" for path in evidence.rglob("*") if path.is_file()):
        raise m.AdjudicationError("raw artifact persisted")
    docs = load(repo / "docs/remediation/m0_3b_r1/decisions.json")
    if m.base.encoded(docs) != m.base.encoded(decisions):
        raise m.AdjudicationError("repository and evidence decisions differ")
    return {
        "schema": "m0_3b_r1_validation",
        "checksums": len(entries),
        "finding_count": 160,
        "decision_count": 160,
        "ledger_count": 160,
        "status": "pass",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    try:
        result = validate(args.repo, args.evidence)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "m0_3b_r1_validation",
                    "status": "failure",
                    "type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
