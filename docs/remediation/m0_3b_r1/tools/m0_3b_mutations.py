#!/usr/bin/env python3
"""Executable fail-closed mutation matrix for M0.3b-R1."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m0_3b_adjudicator as m


def load_decisions(path):
    document = m.base.read_json(path)
    records = document.get("records") if isinstance(document, dict) else document
    if not isinstance(records, list):
        raise m.AdjudicationError("invalid decisions")
    return records


def run(repo, decisions_path):
    repo = Path(repo).resolve()
    decisions = load_decisions(decisions_path)
    state = m.provenance(repo)
    blobs, _ = m.direct_tree(repo, state["submodule_commit"])
    manifest_sha = m.base.digest(m.base.encoded(m.base.source_manifest(repo)))
    report = [
        {
            "File": decision["relative_path"],
            "RuleID": decision["rule_id"],
            "StartLine": decision["line_start"],
            "EndLine": decision["line_end"],
        }
        for decision in decisions
    ]
    kwargs = {
        "head": state["head"],
        "commit": state["submodule_commit"],
        "repo": repo,
        "state": state,
        "manifest_sha256": manifest_sha,
        "owned_blobs": blobs,
    }
    baseline = m.build_records(report, decisions=decisions, **kwargs)
    if not m.approved_gate(baseline, decisions):
        raise m.AdjudicationError("baseline gate does not pass")
    results = {}

    mutations = {
        "stale_head": ("head", "d" * 40),
        "stale_commit": ("submodule_commit", "d" * 40),
        "stale_submodule_head": ("submodule_head", "d" * 40),
        "dirty_submodule": ("submodule_clean", False),
        "stale_file_hash": ("file_sha256", "d" * 64),
        "stale_manifest": ("source_manifest_sha256", "d" * 64),
        "rebound_path": (
            "relative_path",
            m.PREFIX + "/contracts/utils/NoncesKeyedUpgradeable.sol",
        ),
        "rebound_rule": ("rule_id", "another-rule"),
        "rebound_line_start": ("line_start", 1),
        "rebound_line_end": ("line_end", 1),
    }
    for name, (field, value) in mutations.items():
        changed = copy.deepcopy(decisions)
        changed[0][field] = value
        try:
            records = m.build_records(report, decisions=changed, **kwargs)
            results[name] = (
                not m.approved_gate(records, changed)
                and any(record["disposition"] == "unresolved" for record in records)
            )
        except m.base.AdjudicationError:
            results[name] = True

    added_report = report + [
        {
            **report[0],
            "RuleID": "another-rule",
        }
    ]
    added = m.build_records(added_report, decisions=decisions, **kwargs)
    results["finding_added"] = (
        len(added) == len(decisions) + 1
        and not m.approved_gate(added, decisions)
        and sum(record["disposition"] == "unresolved" for record in added) == 1
    )

    omitted_report = report[:-1]
    omitted_ids = {
        m.base.stable_id(
            state["head"],
            state["submodule_commit"],
            item["File"],
            item["RuleID"],
            item["StartLine"],
            item["EndLine"],
        )
        for item in omitted_report
    }
    omitted_decisions = [
        decision for decision in decisions
        if decision["finding_id"] in omitted_ids
    ]
    omitted = m.build_records(
        omitted_report,
        decisions=omitted_decisions,
        **kwargs,
    )
    results["finding_omitted"] = (
        len(omitted) == len(decisions) - 1
        and not m.approved_gate(omitted, decisions)
    )

    try:
        m.build_records(report + [report[0]], decisions=decisions, **kwargs)
        results["finding_duplicated"] = False
    except m.base.AdjudicationError:
        results["finding_duplicated"] = True

    pending = copy.deepcopy(decisions)
    pending[0]["reviewer_status"] = "pending_review"
    pending_records = m.build_records(report, decisions=pending, **kwargs)
    results["pending_review"] = (
        pending_records[0]["disposition"] == "unresolved"
        or any(record["disposition"] == "unresolved" for record in pending_records)
    ) and not m.approved_gate(pending_records, pending)

    unresolved = copy.deepcopy(decisions)
    unresolved[0].update(
        disposition="unresolved",
        rationale="review_incomplete",
        source_review="not_proven",
        file_role="unreviewed",
        reviewer_status="pending_review",
        reviewer="pending",
        reachability={domain: "not_assessed" for domain in m.DOMAINS},
    )
    unresolved_records = m.build_records(report, decisions=unresolved, **kwargs)
    results["unresolved_disposition"] = (
        any(record["disposition"] == "unresolved" for record in unresolved_records)
        and not m.approved_gate(unresolved_records, unresolved)
    )

    potential = copy.deepcopy(decisions)
    potential[0].update(
        disposition="potential_credential",
        rationale="credential_or_ambiguous_datum",
        source_review="credential_or_ambiguous_datum",
    )
    potential_records = m.build_records(report, decisions=potential, **kwargs)
    results["potential_disposition"] = (
        any(
            record["disposition"] == "potential_credential"
            for record in potential_records
        )
        and not m.approved_gate(potential_records, potential)
    )

    sensitive = copy.deepcopy(decisions)
    sensitive[0]["evidence_refs"].append(
        {"path": "docs/remediation/m0_3b_r1/REVIEW.md", "sha256": "e" * 64, "nested": [{"raw_match": "removed"}]}
    )
    try:
        m.build_records(report, decisions=sensitive, **kwargs)
        results["nested_sensitive_field"] = False
    except m.base.AdjudicationError:
        results["nested_sensitive_field"] = True

    nested_report = [
        {
            "File": m.PREFIX
            + "/lib/openzeppelin-contracts/test/token/ERC20/ERC20.test.js",
            "RuleID": "generic-api-key",
            "StartLine": 1,
            "EndLine": 1,
        }
    ]
    try:
        m.build_records(nested_report, decisions=[], **kwargs)
        results["nested_gitlink_excluded"] = False
    except m.base.AdjudicationError:
        results["nested_gitlink_excluded"] = True

    dirty_state = dict(state, submodule_clean=False)
    dirty_records = m.build_records(
        report,
        decisions=decisions,
        **(kwargs | {"state": dirty_state}),
    )
    results["clean_pin_enforced"] = (
        all(record["disposition"] == "unresolved" for record in dirty_records)
        and not m.approved_gate(dirty_records, decisions)
    )

    with tempfile.TemporaryDirectory(prefix="m03b-arbitrary-") as temporary:
        root = Path(temporary)
        path = m.PREFIX + "/test/token/Arbitrary.test.js"
        target = root / path
        target.parent.mkdir(parents=True)
        target.write_text("const arbitrary = 'test';\n", encoding="utf-8")
        results["vendor_test_path_not_sufficient"] = (
            m.source_proof(root, path, 1, 1) == ("not_proven", "unreviewed")
        )

    if not all(results.values()):
        raise m.AdjudicationError("one or more mutations did not fail closed")
    return {
        "schema": "m0_3b_r1_mutation_matrix",
        "baseline_count": len(baseline),
        "checks": dict(sorted(results.items())),
        "passed": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--decisions", required=True)
    args = parser.parse_args()
    try:
        result = run(args.repo, args.decisions)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "m0_3b_r1_mutation_matrix",
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
