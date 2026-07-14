"""Unit tests for artifact-bound runtime and privacy evidence validation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("runtime_privacy_evidence.py")
SPEC = importlib.util.spec_from_file_location("runtime_privacy_evidence", MODULE_PATH)
evidence = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(evidence)


COMMIT = "a" * 40
SUBMITTED_AT = "2026-07-13T10:00:00+00:00"
RETRIEVED_AT = "2026-07-13T10:01:00+00:00"
GENERATED_AT = "2026-07-13T10:02:00+00:00"


def _write(root: Path, relative: str, content: bytes) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": relative, "sha256": hashlib.sha256(content).hexdigest()}


def _valid_runtime(root: Path) -> dict:
    gateway_artifact = _write(
        root,
        "docs/audit/evidence/runtime/gateway-report.json",
        b'{"external_gateway_checks":"passed"}',
    )
    gateway_checks = {
        name: {"passed": True, "artifact": gateway_artifact}
        for name in sorted(evidence.REQUIRED_GATEWAY_CHECKS)
    }
    receipts = []
    for provider, network in evidence.PROVIDER_NETWORK.items():
        payload = f"{provider}-retrieved-public-payload".encode()
        payload_hash = hashlib.sha256(payload).hexdigest()
        submission = _write(
            root,
            f"docs/audit/evidence/runtime/{provider}-submission.json",
            f'{{"provider":"{provider}","accepted":true}}'.encode(),
        )
        retrieval = _write(
            root,
            f"docs/audit/evidence/runtime/{provider}-retrieved.bin",
            payload,
        )
        receipts.append(
            {
                "provider": provider,
                "network": network,
                "submission_id": f"{provider}-submission-1",
                "inclusion_reference": f"{provider}-inclusion-1",
                "commitment": "0x" + "b" * 64,
                "payload_sha256": payload_hash,
                "retrieved_payload_sha256": payload_hash,
                "submitted_at": SUBMITTED_AT,
                "retrieved_at": RETRIEVED_AT,
                "retrieval_verified": True,
                "mock_mode": False,
                "submitter_identity": f"{provider}-submitter",
                "retrieval_observer_identity": f"{provider}-independent-observer",
                "submission_artifact": submission,
                "retrieval_artifact": retrieval,
            }
        )
    return {
        "schema_version": "2.0.0",
        "commit_sha": COMMIT,
        "environment": "testnet",
        "generated_at": GENERATED_AT,
        "gateway_checks": gateway_checks,
        "da_receipts": receipts,
        "excluded_live_routes": sorted(evidence.REQUIRED_EXCLUDED_ROUTES),
    }


def _minimal_inventory(root: Path) -> dict:
    source = root / "neuron/da/adapters/celestia_adapter.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "class CelestiaDAAdapter:\n"
        "    async def submit_blob(self, data):\n"
        "        return data\n"
        "    async def verify_blob(self, receipt):\n"
        "        return False\n",
        encoding="utf-8",
    )
    (root / "neuron/sentinel").mkdir(parents=True, exist_ok=True)
    (root / "neuron/vdso").mkdir(parents=True, exist_ok=True)
    test_path = root / "neuron/tests/test_da_live_boundaries.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_boundary():\n    pass\n", encoding="utf-8")
    return {
        "schema_version": "1.0.0",
        "scope": list(evidence.PUBLISHER_SCOPE),
        "publishers": [
            {
                "id": "celestia-blob-submission",
                "path": "neuron/da/adapters/celestia_adapter.py",
                "symbol": "CelestiaDAAdapter.submit_blob",
                "channel": "public-da",
                "payload_policy": "transport-only",
                "operational_live_capable": True,
                "release_evidence_eligible": False,
                "block_reason": "Independent release observer is required.",
                "control_refs": [
                    "neuron/da/adapters/celestia_adapter.py::CelestiaDAAdapter.verify_blob"
                ],
                "tests": ["neuron/tests/test_da_live_boundaries.py"],
            }
        ],
    }


def _valid_privacy(root: Path) -> dict:
    inventory_path = root / "docs/audit/privacy-publisher-inventory.json"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(
        json.dumps(_minimal_inventory(root), sort_keys=True), encoding="utf-8"
    )
    artifacts = {
        "data_inventory": _write(
            root, "docs/audit/evidence/privacy/data-inventory.json", b"data inventory"
        ),
        "retention_policy": _write(
            root, "docs/audit/evidence/privacy/retention-policy.md", b"retention policy"
        ),
        "redaction_tests": _write(
            root, "docs/audit/evidence/privacy/redaction-tests.txt", b"redaction tests passed"
        ),
        "public_content_review": _write(
            root, "docs/audit/evidence/privacy/public-review.md", b"public review approved"
        ),
        "publisher_inventory": {
            "path": "docs/audit/privacy-publisher-inventory.json",
            "sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        },
    }
    return {
        "schema_version": "2.0.0",
        "commit_sha": COMMIT,
        "reviewer": "Ada Reviewer",
        "reviewer_organization": "Independent Privacy Lab",
        "reviewed_at": GENERATED_AT,
        "data_inventory_approved": True,
        "retention_policy_approved": True,
        "redaction_tests_passed": True,
        "public_content_reviewed": True,
        "publisher_inventory_complete": True,
        "blocking_findings_open": 0,
        "evidence_artifacts": artifacts,
    }


class RuntimeEvidenceTests(unittest.TestCase):
    def test_valid_report_binds_gateway_and_independent_da_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "runtime.json"
            path.write_text(json.dumps(_valid_runtime(root)), encoding="utf-8")

            self.assertEqual(evidence.validate_runtime_report(path, COMMIT, root), [])

    def test_runtime_artifacts_may_reside_in_downloaded_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            bundle = Path(temp_dir) / "bundle"
            report = _valid_runtime(bundle)
            path = bundle / "docs/audit/evidence/runtime-integration.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report), encoding="utf-8")

            self.assertEqual(
                evidence.validate_runtime_report(path, COMMIT, root, bundle), []
            )

    def test_legacy_boolean_only_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = _valid_runtime(root)
            report["schema_version"] = "1.0.0"
            report["gateway_checks"] = {
                name: True for name in evidence.REQUIRED_GATEWAY_CHECKS
            }
            path = root / "runtime.json"
            path.write_text(json.dumps(report), encoding="utf-8")

            errors = evidence.validate_runtime_report(path, COMMIT, root)
            self.assertTrue(any("schema_version" in error for error in errors))
            self.assertTrue(any("must be an object" in error for error in errors))

    def test_failed_gateway_check_cannot_be_hidden_by_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = _valid_runtime(root)
            report["gateway_checks"]["mtls"]["passed"] = False
            path = root / "runtime.json"
            path.write_text(json.dumps(report), encoding="utf-8")

            errors = evidence.validate_runtime_report(path, COMMIT, root)
            self.assertTrue(any("gateway_checks.mtls did not pass" in error for error in errors))

    def test_duplicate_provider_mock_and_self_observer_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = _valid_runtime(root)
            report["da_receipts"][1]["provider"] = "celestia"
            report["da_receipts"][1]["network"] = "celestia-mocha"
            report["da_receipts"][0]["mock_mode"] = True
            report["da_receipts"][0]["retrieval_observer_identity"] = report[
                "da_receipts"
            ][0]["submitter_identity"]
            path = root / "runtime.json"
            path.write_text(json.dumps(report), encoding="utf-8")

            errors = evidence.validate_runtime_report(path, COMMIT, root)
            self.assertTrue(any("duplicate celestia" in error for error in errors))
            self.assertTrue(any("mock evidence" in error for error in errors))
            self.assertTrue(any("independent" in error for error in errors))
            self.assertTrue(any("missing providers: near" in error for error in errors))

    def test_retrieval_artifact_must_be_exact_payload_without_simulation_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = _valid_runtime(root)
            receipt = report["da_receipts"][0]
            replacement = _write(
                root,
                "docs/audit/evidence/runtime/celestia-retrieved-mock.bin",
                b"[MOCK] payload",
            )
            receipt["retrieval_artifact"] = replacement
            path = root / "runtime.json"
            path.write_text(json.dumps(report), encoding="utf-8")

            errors = evidence.validate_runtime_report(path, COMMIT, root)
            self.assertTrue(any("non-live marker" in error for error in errors))
            self.assertTrue(any("not the retrieved payload" in error for error in errors))

    def test_malformed_provider_type_is_rejected_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = _valid_runtime(root)
            report["da_receipts"][0]["provider"] = ["celestia"]
            path = root / "runtime.json"
            path.write_text(json.dumps(report), encoding="utf-8")

            errors = evidence.validate_runtime_report(path, COMMIT, root)
            self.assertTrue(any("provider is unsupported" in error for error in errors))


class PrivacyEvidenceTests(unittest.TestCase):
    def test_valid_review_binds_inventory_and_each_approval_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "privacy.json"
            path.write_text(json.dumps(_valid_privacy(root)), encoding="utf-8")

            self.assertEqual(evidence.validate_privacy_review(path, COMMIT, root), [])

    def test_privacy_artifacts_may_reside_in_downloaded_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            bundle = Path(temp_dir) / "bundle"
            review = _valid_privacy(root)
            for name, reference in review["evidence_artifacts"].items():
                if name == "publisher_inventory":
                    continue
                source = root / reference["path"]
                destination = bundle / reference["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
                source.unlink()
            path = bundle / "docs/audit/evidence/privacy-review.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(review), encoding="utf-8")

            self.assertEqual(
                evidence.validate_privacy_review(path, COMMIT, root, bundle), []
            )

    def test_generic_reviewer_and_unbound_approvals_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review = _valid_privacy(root)
            review["reviewer"] = "github-actions"
            review["reviewer_organization"] = "automated"
            review.pop("evidence_artifacts")
            path = root / "privacy.json"
            path.write_text(json.dumps(review), encoding="utf-8")

            errors = evidence.validate_privacy_review(path, COMMIT, root)
            self.assertTrue(any("named human" in error for error in errors))
            self.assertTrue(any("reviewer organization" in error for error in errors))
            self.assertTrue(any("evidence_artifacts" in error for error in errors))

    def test_boolean_blocking_finding_count_is_not_accepted_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review = _valid_privacy(root)
            review["blocking_findings_open"] = False
            path = root / "privacy.json"
            path.write_text(json.dumps(review), encoding="utf-8")

            errors = evidence.validate_privacy_review(path, COMMIT, root)
            self.assertTrue(any("open blocking findings" in error for error in errors))

    def test_inventory_detects_unclassified_publisher(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory = _minimal_inventory(root)
            new_path = root / "neuron/vdso/new_sink.py"
            new_path.write_text(
                "class NewSink:\n"
                "    async def publish(self, payload):\n"
                "        return payload\n",
                encoding="utf-8",
            )
            path = root / "inventory.json"
            path.write_text(json.dumps(inventory), encoding="utf-8")

            errors = evidence.validate_publisher_inventory(path, root)
            self.assertTrue(any("NewSink.publish" in error for error in errors))

    def test_inventory_cannot_promote_current_publisher_by_status_flip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory = _minimal_inventory(root)
            inventory["publishers"][0]["release_evidence_eligible"] = True
            inventory["publishers"][0]["block_reason"] = None
            path = root / "inventory.json"
            path.write_text(json.dumps(inventory), encoding="utf-8")

            errors = evidence.validate_publisher_inventory(path, root)
            self.assertTrue(any("cannot qualify" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
