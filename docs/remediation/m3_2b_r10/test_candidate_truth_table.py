"""M3.2b-R10 candidate-only truth-table meta-regressions."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docs.remediation.m3_2b_r8 import test_classification as r8


def _facts(**changes: object) -> dict[str, object]:
    record = {
        "bindings_valid": True,
        "hashes_differ": True,
        "valid_original": "accept",
        "targeted_invalid_original": "reject",
        "rebound_mutant": "accept",
        "mutant_executed": True,
        "original_in_mutant_slot": False,
        "stale_credential_rejected": True,
        "evaluator_error": False,
        "repetitions_agree": True,
        "repetition_count": 10,
    }
    record.update(changes)
    return record


# Expected statuses are deliberately owned by this test, not the candidate.
ROWS = (
    ("valid", _facts(), "detected"),
    ("mutant_not_executed", _facts(mutant_executed=False), "invalid_harness"),
    ("original_substituted", _facts(original_in_mutant_slot=True), "invalid_harness"),
    ("program_hash_unchanged", _facts(hashes_differ=False), "invalid_harness"),
    ("stale_binding_accepted", _facts(stale_credential_rejected=False), "invalid_harness"),
    ("valid_original_rejected", _facts(valid_original="reject"), "fixture_invalid"),
    ("invalid_original_accepted", _facts(targeted_invalid_original="accept"), "control_not_enforced"),
    ("rebound_mutant_rejected", _facts(rebound_mutant="reject"), "mutation_not_detected"),
    ("evaluator_error", _facts(evaluator_error=True), "evaluator_error"),
    ("repetition_disagreement", _facts(repetitions_agree=False), "nondeterministic"),
    ("malformed_missing", {k: v for k, v in _facts().items() if k != "hashes_differ"}, "invalid_harness"),
    ("malformed_unknown", {**_facts(), "unknown_field": 1}, "invalid_harness"),
    ("malformed_bool_integer", _facts(repetition_count=True), "invalid_harness"),
)
_EXPECTED_IDS = frozenset(row[0] for row in ROWS)
_EXPECTED_FACT_FIELDS = frozenset(_facts())


def validate_truth_table_rows(rows=ROWS) -> None:
    if len(rows) != 13 or {row[0] for row in rows} != _EXPECTED_IDS:
        raise AssertionError("truth table must contain exactly the closed 13-row set")
    if sum(row[2] == "detected" for row in rows) != 1:
        raise AssertionError("truth table must contain exactly one detected row")
    if sum(row[2] != "detected" for row in rows) != 12:
        raise AssertionError("truth table must contain exactly twelve negative rows")
    for row_id, record, expected in rows:
        if not isinstance(row_id, str) or not isinstance(record, dict) or not isinstance(expected, str):
            raise AssertionError("truth table row schema is invalid")
        if row_id == "malformed_missing":
            if set(record) != (_EXPECTED_FACT_FIELDS - {"hashes_differ"}):
                raise AssertionError("malformed_missing row is not the required missing-field case")
            continue
        if row_id == "malformed_unknown":
            if set(record) != (_EXPECTED_FACT_FIELDS | {"unknown_field"}):
                raise AssertionError("malformed_unknown row is not the required unknown-field case")
            continue
        if set(record) != _EXPECTED_FACT_FIELDS:
            raise AssertionError(f"truth table row {row_id} has an invalid fact schema")


def run_candidate_truth_table(candidate_path: Path) -> dict[str, object]:
    """Run only the supplied candidate and return sanitized row outcomes."""
    validate_truth_table_rows()
    candidate = candidate_path.resolve(strict=True)
    module = r8.load_candidate(candidate, require_mutation=False)
    try:
        metadata = module._candidate_metadata
        rows = []
        for row_id, record, expected in ROWS:
            actual = module.classify_mutation(record).value
            rows.append({"id": row_id, "expected": expected, "actual": actual, "passed": actual == expected})
        return {
            "candidate_sha256": metadata["candidate_sha256"],
            "loaded_path_matches": metadata["loaded_path"] == str(candidate),
            "row_count": len(rows),
            "passed": all(row["passed"] for row in rows),
            "rows": rows,
        }
    finally:
        sys.modules.pop(module._candidate_metadata["module_name"], None)


def _candidate(root: Path, old: str, new: str) -> Path:
    source = r8.HARNESS.read_text()
    if source.count(old) != 1:
        raise AssertionError("candidate mutation anchor is not unique")
    path = root / "isolated" / "candidate_module.py"
    path.parent.mkdir(parents=True)
    path.write_text(source.replace(old, new, 1))
    compile_run = subprocess.run(
        ["python3", "-m", "py_compile", str(path)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if compile_run.returncode != 0:
        raise AssertionError(compile_run.stderr)
    return path


class CandidateOnlyTruthTableTests(unittest.TestCase):
    def test_canonical_candidate_passes(self) -> None:
        result = run_candidate_truth_table(r8.HARNESS)
        self.assertTrue(result["loaded_path_matches"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["row_count"], 13)

    def test_sanitized_json_contains_no_source_or_temp_paths(self) -> None:
        result = run_candidate_truth_table(r8.HARNESS)
        encoded = json.dumps(
            {"passed": result["passed"], "row_count": result["row_count"], "rows": result["rows"]},
            sort_keys=True,
        )
        self.assertNotIn(str(r8.ROOT), encoded)
        self.assertNotIn("/tmp/", encoded)
        self.assertNotIn("compiledCode", encoded)

    def test_constant_and_bypass_candidates_fail_candidate_only_mode(self) -> None:
        mutations = (
            (
                "constant_detected",
                "    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
                "    return MutationClassification.DETECTED\n    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
            ),
            (
                "constant_not_detected",
                "    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
                "    return MutationClassification.MUTATION_NOT_DETECTED\n    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
            ),
            ("ignore_hash", "or not facts.hashes_differ", "or False"),
            ("ignore_mutant_execution", "or not facts.mutant_executed", "or False"),
            ("ignore_evaluator_error", "if facts.evaluator_error:", "if False:"),
        )
        with tempfile.TemporaryDirectory(prefix="m3-2b-r10-candidates-") as td:
            root = Path(td)
            for name, old, new in mutations:
                with self.subTest(name=name):
                    candidate = _candidate(root / name, old, new)
                    result = run_candidate_truth_table(candidate)
                    self.assertFalse(result["passed"])
                    mismatches = sum(not row["passed"] for row in result["rows"])
                    if name.startswith("constant_"):
                        self.assertEqual(mismatches, 12)
                    else:
                        self.assertGreaterEqual(mismatches, 1)

    def test_repository_owned_meta_regression_rejects_ignored_candidate_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="m3-2b-r10-meta-") as td:
            root = Path(td)
            candidate = _candidate(
                root,
                "    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
                "    return MutationClassification.DETECTED\n    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
            )
            candidate_result = run_candidate_truth_table(candidate)
            canonical_result = run_candidate_truth_table(r8.HARNESS)
            self.assertNotEqual(candidate_result["candidate_sha256"], canonical_result["candidate_sha256"])
            self.assertFalse(candidate_result["passed"])
            self.assertTrue(canonical_result["passed"])


if __name__ == "__main__":
    unittest.main()
