#!/usr/bin/env python3
"""Executable fail-closed mutation matrix for M0.3c-R1."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m0_3c_adjudicator as m


def load_decisions(path):
    document = m.base.read_json(path)
    records = document.get("records") if isinstance(document, dict) else document
    if not isinstance(records, list):
        raise m.AdjudicationError("invalid decisions")
    return records


def run(repo, decisions_path, semantic_attestation_path, semantic_attestation_sha256):
    repo = Path(repo).resolve()
    decisions = load_decisions(decisions_path)
    state = m.provenance(repo)
    blobs, _ = m.direct_tree(repo, state["submodule_commit"])
    manifest_sha = m.base.digest(m.base.encoded(m.base.source_manifest(repo)))
    decision_sha = m.base.digest(Path(decisions_path).read_bytes())
    semantic_records = m.validate_semantic_attestation(
        repo,
        Path("/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks"),
        decisions_path,
        decision_sha,
        manifest_sha,
        state,
        blobs,
        semantic_attestation_path,
        semantic_attestation_sha256,
    )
    declared_errors = m.production_declarations(repo, state["submodule_commit"])
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
        "semantic_records": semantic_records,
        "declared_errors": declared_errors,
    }
    gate = lambda records, approved: m.approved_gate(
        records, approved, semantic_records
    )
    baseline = m.build_records(report, decisions=decisions, **kwargs)
    if not gate(baseline, decisions):
        raise m.AdjudicationError("baseline gate does not pass")
    results = {}

    mutations = {
        "stale_head": ("head", "d" * 40),
        "stale_parent_commit": ("parent_submodule_commit", "d" * 40),
        "stale_parent_head": ("parent_submodule_head", "d" * 40),
        "dirty_parent": ("parent_submodule_clean", False),
        "stale_target_commit": ("submodule_commit", "d" * 40),
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
                not gate(records, changed)
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
        and not gate(added, decisions)
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
        and not gate(omitted, decisions)
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
    ) and not gate(pending_records, pending)

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
        and not gate(unresolved_records, unresolved)
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
        and not gate(potential_records, potential)
    )

    sensitive = copy.deepcopy(decisions)
    sensitive[0]["evidence_refs"].append(
        {"path": "docs/remediation/m0_3c_r1/REVIEW.md", "sha256": "e" * 64, "nested": [{"raw_match": "removed"}]}
    )
    try:
        m.build_records(report, decisions=sensitive, **kwargs)
        results["nested_sensitive_field"] = False
    except m.base.AdjudicationError:
        results["nested_sensitive_field"] = True

    child_report = [
        {
            "File": next(iter(m.CHILD_GITLINKS))
            + "/test/OwnedByChild.test.js",
            "RuleID": "generic-api-key",
            "StartLine": 1,
            "EndLine": 1,
        }
    ]
    try:
        m.build_records(child_report, decisions=[], **kwargs)
        results["child_gitlink_excluded"] = False
    except m.base.AdjudicationError:
        results["child_gitlink_excluded"] = True

    for name, field in (
        ("parent_clean_pin_enforced", "parent_submodule_clean"),
        ("target_clean_pin_enforced", "submodule_clean"),
    ):
        dirty_state = dict(state, **{field: False})
        dirty_kwargs = kwargs | {"state": dirty_state}
        dirty_records = m.build_records(
            report,
            decisions=decisions,
            **dirty_kwargs,
        )
        results[name] = (
            all(record["disposition"] == "unresolved" for record in dirty_records)
            and not gate(dirty_records, decisions)
        )

    unknown = copy.deepcopy(decisions)
    unknown[0]["finding_id"] = "e" * 64
    try:
        m.build_records(report, decisions=unknown, **kwargs)
        results["unknown_decision"] = False
    except m.base.AdjudicationError:
        results["unknown_decision"] = True

    prior = m.base.read_json(repo / "docs/remediation/m0_3b_r1/decisions.json")["records"][0]
    try:
        m.build_records(report, decisions=[prior], **kwargs)
        results["cross_tranche_decision"] = False
    except m.base.AdjudicationError:
        results["cross_tranche_decision"] = True

    with tempfile.TemporaryDirectory(prefix="m03c-arbitrary-") as temporary:
        root = Path(temporary)
        path = m.PREFIX + "/test/token/Arbitrary.test.js"
        target = root / path
        target.parent.mkdir(parents=True)
        target.write_text("const arbitrary = 'test';\n", encoding="utf-8")
        results["vendor_test_path_not_sufficient"] = (
            m.source_proof(root, path, 1, 1) == ("not_proven", "unreviewed")
        )

    assertion_id = next(
        identifier for identifier, semantic in semantic_records.items()
        if semantic["classification"] == "expected_custom_error_assertion"
    )
    context_mutations = {
        "context_missing": lambda row: row.pop("context"),
        "context_target_rebound": lambda row: row["context"].__setitem__("call_target", "this.other"),
        "context_signature_rebound": lambda row: row["context"].__setitem__("error_signature", "ERC20InvalidReceiver(uint256)"),
        "context_selector_rebound": lambda row: row["context"].__setitem__("error_selector", "00000000"),
        "context_owner_rebound": lambda row: row["context"]["declaration_owner"].__setitem__("path", "contracts/Other.sol"),
        "context_owner_blob_rebound": lambda row: row["context"]["declaration_owner"].__setitem__("source_object_id", "0" * 40),
        "context_chain_rebound": lambda row: row["context"]["reachability_chains"][0]["containers"].pop(),
        "context_caller_blob_rebound": lambda row: row["context"]["execution_targets"][0].__setitem__("caller_object_id", "0" * 40),
    }
    for name, mutate in context_mutations.items():
        changed_semantics = copy.deepcopy(semantic_records)
        mutate(changed_semantics[assertion_id])
        changed_kwargs = kwargs | {"semantic_records": changed_semantics}
        try:
            changed_records = m.build_records(report, decisions=decisions, **changed_kwargs)
            results[name] = (
                any(record["disposition"] == "unresolved" for record in changed_records)
                and not m.approved_gate(changed_records, decisions, changed_semantics)
            )
        except (m.AdjudicationError, m.base.AdjudicationError, KeyError, TypeError):
            results[name] = True

    if not all(results.values()):
        raise m.AdjudicationError("one or more mutations did not fail closed")
    return {
        "schema": "m0_3c_r7_mutation_matrix",
        "baseline_count": len(baseline),
        "checks": dict(sorted(results.items())),
        "passed": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--semantic-attestation", required=True)
    parser.add_argument("--semantic-attestation-sha256", required=True)
    args = parser.parse_args()
    try:
        result = run(
            args.repo,
            args.decisions,
            args.semantic_attestation,
            args.semantic_attestation_sha256,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "m0_3c_r7_mutation_matrix",
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
