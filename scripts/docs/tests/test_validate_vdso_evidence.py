"""Regression tests for the VDSO evidence validator."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = ROOT / "scripts" / "docs" / "validate_vdso_evidence.py"
SPEC = importlib.util.spec_from_file_location("validate_vdso_evidence", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class VDSOEvidenceValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = json.loads(VALIDATOR.DEFAULT_EVIDENCE.read_text(encoding="utf-8"))

    def _validate_modified(self, data: dict) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return VALIDATOR.validate(evidence_path=path)

    def test_canonical_manifest_passes(self) -> None:
        self.assertEqual([], VALIDATOR.validate())

    def test_source_hash_mismatch_fails(self) -> None:
        data = copy.deepcopy(self.canonical)
        data["source_provenance"]["source_sha256"] = "A" * 64
        errors = self._validate_modified(data)
        self.assertTrue(any("SHA-256 mismatch" in error for error in errors), errors)

    def test_duplicate_principle_fails(self) -> None:
        data = copy.deepcopy(self.canonical)
        data["findings"][1]["principle"] = data["findings"][0]["principle"]
        errors = self._validate_modified(data)
        self.assertTrue(any("each principle exactly once" in error for error in errors), errors)

    def test_dual_host_authority_downgrade_fails(self) -> None:
        data = copy.deepcopy(self.canonical)
        data["dual_host_policy"]["authority_rule"] = "polygon_universal_writer"
        errors = self._validate_modified(data)
        self.assertTrue(any("one_authoritative_writer_per_state_domain" in error for error in errors), errors)

    def test_deployment_promotion_without_evidence_fails(self) -> None:
        data = copy.deepcopy(self.canonical)
        data["verdict"]["deployment_readiness"] = "yes"
        errors = self._validate_modified(data)
        self.assertTrue(any("deployment_readiness must remain no" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
