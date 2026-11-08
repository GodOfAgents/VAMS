"""M3.2b-R8 closed mutation-classification regressions."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "scripts/remediation/test_m3_2b_compiled_mutations.py"
sys.path.insert(0, str(ROOT / "scripts/remediation"))
import test_m3_2b_compiled_mutations as harness


BASE_FACTS = {
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


def facts(**changes: object) -> dict[str, object]:
    record = dict(BASE_FACTS)
    record.update(changes)
    return record


def load_candidate(candidate_path: Path, canonical_path: Path = HARNESS, require_mutation: bool = False):
    """Load exactly one candidate under a fresh module name, never by import name."""
    candidate = candidate_path.resolve(strict=True)
    canonical = canonical_path.resolve(strict=True)
    candidate_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
    canonical_hash = hashlib.sha256(canonical.read_bytes()).hexdigest()
    if require_mutation and candidate_hash == canonical_hash:
        raise AssertionError("mutation candidate is byte-identical to canonical harness")
    module_name = f"_m3_2b_candidate_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if spec is None or spec.loader is None:
        raise AssertionError("candidate module spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        loaded = Path(module.__file__).resolve(strict=True)
        if loaded != candidate:
            raise AssertionError("candidate module loaded from an unexpected path")
        if hashlib.sha256(loaded.read_bytes()).hexdigest() != candidate_hash:
            raise AssertionError("candidate source hash changed while loading")
        if candidate.read_text().count("def classify_mutation(") != 1:
            raise AssertionError("candidate classifier function is not unique")
        if not callable(getattr(module, "classify_mutation", None)):
            raise AssertionError("candidate classifier is not callable")
        module._candidate_metadata = {
            "requested_path": str(candidate),
            "loaded_path": str(loaded),
            "candidate_sha256": candidate_hash,
            "canonical_sha256": canonical_hash,
            "module_name": module_name,
        }
        return module
    except BaseException:
        sys.modules.pop(module_name, None)
        raise


TRUTH_TABLE = (
    ("all_valid", facts(), "detected"),
    ("mutant_not_executed", facts(mutant_executed=False), "invalid_harness"),
    ("original_in_mutant_slot", facts(original_in_mutant_slot=True), "invalid_harness"),
    ("hashes_equal", facts(hashes_differ=False), "invalid_harness"),
    ("stale_credential_accepted", facts(stale_credential_rejected=False), "invalid_harness"),
    ("valid_original_rejects", facts(valid_original="reject"), "fixture_invalid"),
    ("targeted_original_accepts", facts(targeted_invalid_original="accept"), "control_not_enforced"),
    ("rebound_mutant_rejects", facts(rebound_mutant="reject"), "mutation_not_detected"),
    ("evaluator_error", facts(evaluator_error=True), "evaluator_error"),
    ("repetition_disagrees", facts(repetitions_agree=False), "nondeterministic"),
    ("missing_field", {k: v for k, v in facts().items() if k != "hashes_differ"}, "invalid_harness"),
    ("unknown_field", facts(unknown=True), "invalid_harness"),
    ("bool_integer", facts(repetition_count=True), "invalid_harness"),
)


class ClassificationTests(unittest.TestCase):
    def _cli(self, record: object, harness_path: Path = HARNESS) -> tuple[int, dict[str, object], str]:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as raw:
            json.dump(record, raw)
            raw.flush()
            run = subprocess.run(
                ["python3", str(harness_path), "--classify-facts", raw.name],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PYTHONPATH": str(ROOT / "scripts/remediation"),
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                timeout=15,
            )
        payload = json.loads(run.stdout)
        return run.returncode, payload, run.stderr

    def test_closed_truth_table_direct(self) -> None:
        for name, record, expected in TRUTH_TABLE:
            with self.subTest(name=name):
                self.assertEqual(harness.classify_mutation(record).value, expected)

    def test_closed_truth_table_cli_matches_direct(self) -> None:
        for name, record, expected in TRUTH_TABLE:
            with self.subTest(name=name):
                exit_code, payload, stderr = self._cli(record)
                self.assertEqual(payload, {"classification": expected, "status": expected}, stderr)
                self.assertEqual(exit_code, 0 if expected == "detected" else 1)

    def test_source_mutations_fail_the_same_public_table(self) -> None:
        mutations = (
            (
                "always_detected",
                "    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
                "    return MutationClassification.DETECTED\n    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
                "mutant_not_executed",
            ),
            (
                "always_not_detected",
                "    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
                "    return MutationClassification.MUTATION_NOT_DETECTED\n    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)",
                "all_valid",
            ),
            (
                "ignore_mutant_executed",
                "or not facts.mutant_executed",
                "or False",
                "mutant_not_executed",
            ),
            (
                "ignore_hash_changed",
                "or not facts.hashes_differ",
                "or False",
                "hashes_equal",
            ),
            (
                "ignore_stale_binding",
                "or not facts.stale_credential_rejected",
                "or False",
                "stale_credential_accepted",
            ),
            ("ignore_evaluator_error", "if facts.evaluator_error:", "if False:", "evaluator_error"),
            ("ignore_repetition_disagreement", "if not facts.repetitions_agree:", "if False:", "repetition_disagrees"),
        )
        source = HARNESS.read_text()
        for mutation_id, old, new, expected_case in mutations:
            with self.subTest(mutation_id=mutation_id):
                self.assertEqual(source.count(old), 1)
                with tempfile.TemporaryDirectory(prefix=f"m3-2b-r8-{mutation_id}-") as td:
                    mutated = Path(td) / "test_m3_2b_compiled_mutations.py"
                    mutated.write_text(source.replace(old, new, 1))
                    compile_run = subprocess.run(
                        ["python3", "-m", "py_compile", str(mutated)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(compile_run.returncode, 0, compile_run.stderr)
                    candidate_module = load_candidate(mutated, require_mutation=True)
                    try:
                        direct_mismatches = []
                        for name, record, expected in TRUTH_TABLE:
                            actual = candidate_module.classify_mutation(record).value
                            if actual != expected:
                                direct_mismatches.append(name)
                        self.assertIn(expected_case, direct_mismatches)
                    finally:
                        sys.modules.pop(candidate_module._candidate_metadata["module_name"], None)
                    mismatches = []
                    for name, record, expected in TRUTH_TABLE:
                        exit_code, payload, stderr = self._cli(record, mutated)
                        self.assertIn(exit_code, (0, 1), stderr)
                        actual = payload.get("classification")
                        if actual != expected:
                            mismatches.append(name)
                    self.assertIn(expected_case, mismatches)
                    self.assertTrue(mismatches)

    def test_required_fields_are_not_computed_from_production_helpers(self) -> None:
        record = facts()
        record["rebound_mutant"] = "reject"
        self.assertEqual(harness.classify_mutation(record).value, "mutation_not_detected")


if __name__ == "__main__":
    unittest.main()
