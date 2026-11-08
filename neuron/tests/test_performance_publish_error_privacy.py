"""Actual publisher error boundary with synthetic inputs and no adapter execution."""
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from neuron.da import performance_audit as publisher
from neuron.da.models import AuditReport, DAProtocol, DAReceipt
from neuron.runtime_safety import load_runtime_policy


MARKER = "SYNTHETIC_ONLY_PRIVATE_MARKER"
FIXED_ERROR = "Invalid Sentinel report or DA target"
FIXED_LOG = "Sentinel report rejected before DA submission"


class NeverStringifyTarget:
    def __init__(self):
        self.calls = 0

    def __str__(self):
        self.calls += 1
        raise AssertionError("Error reporting must not stringify arbitrary targets")


class NeverStringifyError(ValueError):
    def __str__(self):
        raise AssertionError("Error reporting must not stringify exceptions")


class PerformancePublishErrorPrivacyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.audit_log = publisher.PerformanceAuditLog(
            mock_mode=True,
            config={"enabled_protocols": ["celestia"]},
            runtime_policy=load_runtime_policy({"VAMS_ENV": "test"}),
            environ={"VAMS_ENV": "test"},
        )
        self.adapter = self.audit_log.adapters[DAProtocol.CELESTIA]
        self.adapter.submit_blob = AsyncMock(side_effect=AssertionError("No real DA submission permitted"))
        self.adapter.verify_blob = AsyncMock(side_effect=AssertionError("No real DA verification permitted"))
        self.history = [{"id": "existing-synthetic-history"}]
        self.audit_log.audit_history = self.history

    @staticmethod
    def valid_report():
        return {"nodeId": "synthetic-node", "sentinelId": "synthetic-sentinel",
                "challengeType": "gpu", "metricsScore": 5000, "passed": True,
                "kpis": {}, "timestamp": 1700000200, "duration": 1.0}

    async def assert_private_rejection(self, report, target, protocol="unknown"):
        self.adapter.submit_blob.reset_mock()
        self.adapter.verify_blob.reset_mock()
        with self.assertLogs(publisher.logger, level="ERROR") as logged:
            result = await self.audit_log.publish_sentinel_report(report, da_target=target)
        self.adapter.submit_blob.assert_not_awaited()
        self.adapter.verify_blob.assert_not_awaited()
        self.assertIs(self.audit_log.audit_history, self.history)
        self.assertEqual(self.history, [{"id": "existing-synthetic-history"}])
        self.assertEqual(result, {"success": False, "protocol": protocol, "error": FIXED_ERROR})
        self.assertEqual(len(logged.records), 1)
        self.assertEqual(logged.records[0].msg, FIXED_LOG)
        self.assertEqual(logged.records[0].args, ())
        self.assertIsNone(logged.records[0].exc_info)
        self.assertNotIn(MARKER, json.dumps(result))
        self.assertNotIn(MARKER, "\n".join(logged.output))
        self.assertLess(len(json.dumps(result)), 150)
        return result

    def test_actual_lane_source_is_loaded(self):
        self.assertEqual(Path(publisher.__file__).resolve(),
                         Path(__file__).resolve().parents[1] / "da" / "performance_audit.py")

    async def test_unknown_target_does_not_reflect_synthetic_private_marker(self):
        await self.assert_private_rejection(self.valid_report(), MARKER)

    async def test_very_long_unknown_target_has_fixed_bounded_outputs(self):
        await self.assert_private_rejection(self.valid_report(), MARKER + "x" * 16384)

    async def test_actual_malformed_reports_are_rejected_without_disclosure(self):
        malformed = ({}, None, [], {"nodeId": MARKER},
                     {**self.valid_report(), "challengeType": MARKER})
        for index, report in enumerate(malformed):
            with self.subTest(case=index):
                await self.assert_private_rejection(report, DAProtocol.CELESTIA, "celestia")

    async def test_known_enum_labels_are_canonical_on_rejection(self):
        for target in DAProtocol:
            with self.subTest(protocol=target.value):
                await self.assert_private_rejection({}, target, target.value)

    async def test_known_normalized_string_labels_are_canonical_on_rejection(self):
        for target in DAProtocol:
            with self.subTest(protocol=target.value):
                await self.assert_private_rejection({}, " \t" + target.value.upper() + "\n ", target.value)

    async def test_unknown_empty_none_and_nonstring_targets_use_unknown_label(self):
        never_stringify = NeverStringifyTarget()
        targets = ("", " ", None, MARKER, 0, 1, True, False, [], {}, never_stringify)
        for index, target in enumerate(targets):
            with self.subTest(case=index):
                # Missing report fields reject before the target parser; output
                # generation must not invoke an arbitrary target's __str__.
                await self.assert_private_rejection({}, target)
        self.assertEqual(never_stringify.calls, 0)

    async def test_each_caught_parser_fault_is_sanitized(self):
        # Synthetic parser fault injection; the publisher boundary remains real.
        for error in (publisher.DAConfigurationError, KeyError, TypeError, ValueError):
            with self.subTest(error=error.__name__):
                with patch.object(AuditReport, "from_sentinel_report", side_effect=error(MARKER)):
                    await self.assert_private_rejection(self.valid_report(), DAProtocol.CELESTIA, "celestia")

    async def test_exception_is_not_stringified_for_output(self):
        with patch.object(AuditReport, "from_sentinel_report", side_effect=NeverStringifyError()):
            await self.assert_private_rejection(self.valid_report(), DAProtocol.CELESTIA, "celestia")

    async def test_disabled_known_target_preserves_canonical_label(self):
        await self.assert_private_rejection(self.valid_report(), DAProtocol.EIGEN_DA, "eigenda")

    async def test_synthetic_success_result_and_history_remain_compatible(self):
        # Explicit synthetic receipt: never provider-native or release evidence.
        receipt = DAReceipt(protocol=DAProtocol.CELESTIA, blob_id="synthetic-only",
                            height=42, commitment="synthetic-commitment", simulated=True)
        self.adapter.submit_blob = AsyncMock(return_value=receipt)
        report = self.valid_report()
        result = await self.audit_log.publish_sentinel_report(report)
        expected_hash = AuditReport.from_sentinel_report(report).compute_hash()
        self.assertEqual(result, {
            "success": True, "protocol": "celestia", "blob_id": "synthetic-only",
            "daHeight": 42, "daCommitment": "synthetic-commitment",
            "reportHash": expected_hash, "merkleRoot": expected_hash, "merkleProof": [expected_hash],
            "verified": False, "mock_mode": True, "release_evidence_eligible": False,
            "simulated": True, "runtime_classification": self.audit_log.runtime_policy.runtime_classification,
            "evidence_classification": "non-authoritative",
        })
        self.adapter.submit_blob.assert_awaited_once_with(AuditReport.from_sentinel_report(report).serialize())
        self.adapter.verify_blob.assert_not_awaited()
        self.assertIs(self.audit_log.audit_history, self.history)
        self.assertEqual(len(self.history), 2)
        self.assertEqual(self.history[0], {"id": "existing-synthetic-history"})
        self.assertEqual(self.history[1]["report_hash"], expected_hash)
        self.assertEqual(self.history[1]["protocol"], "celestia")

    async def test_existing_submission_failure_output_and_no_history_remain_compatible(self):
        self.adapter.submit_blob = AsyncMock(side_effect=RuntimeError(MARKER))
        with self.assertLogs(publisher.logger, level="ERROR") as logged:
            result = await self.audit_log.publish_sentinel_report(self.valid_report())
        self.assertEqual(result, {"success": False, "protocol": "celestia",
                                  "error": "DA submission failed on celestia"})
        self.assertEqual(logged.records[0].getMessage(), "DA submission failed on celestia")
        self.assertNotIn(MARKER, json.dumps(result) + "\n".join(logged.output))
        self.adapter.submit_blob.assert_awaited_once()
        self.adapter.verify_blob.assert_not_awaited()
        self.assertIs(self.audit_log.audit_history, self.history)
        self.assertEqual(self.history, [{"id": "existing-synthetic-history"}])


if __name__ == "__main__":
    unittest.main()
