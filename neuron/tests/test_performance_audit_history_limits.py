"""Focused public-method regressions for audit-history limits."""

from __future__ import annotations

import unittest

from neuron.da.performance_audit import PerformanceAuditLog
from neuron.runtime_safety import load_runtime_policy


class TestPerformanceAuditHistoryLimits(unittest.TestCase):
    def setUp(self) -> None:
        policy = load_runtime_policy({"VAMS_ENV": "test"})
        self.audit_log = PerformanceAuditLog(
            mock_mode=True,
            config={"enabled_protocols": ["celestia"]},
            runtime_policy=policy,
            environ={"VAMS_ENV": "test"},
        )

    @staticmethod
    def records(count: int) -> list[dict[str, str]]:
        return [{"id": f"record-{index}"} for index in range(count)]

    def test_zero_and_negative_limits_are_rejected(self) -> None:
        self.audit_log.audit_history = self.records(4)

        for limit in (0, -1, -50):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.audit_log.get_audit_history(limit=limit)

    def test_bool_float_and_string_limits_are_rejected(self) -> None:
        self.audit_log.audit_history = self.records(4)

        for limit in (True, False, 1.0, 1.5, "3"):
            with self.subTest(limit=limit), self.assertRaises(TypeError):
                self.audit_log.get_audit_history(limit=limit)

    def test_default_limit_returns_the_most_recent_50_in_order(self) -> None:
        self.audit_log.audit_history = self.records(63)

        result = self.audit_log.get_audit_history()

        self.assertEqual(
            [record["id"] for record in result],
            [f"record-{index}" for index in range(13, 63)],
        )

    def test_positive_limits_preserve_recent_record_order(self) -> None:
        self.audit_log.audit_history = self.records(5)

        for limit, expected_ids in (
            (1, ["record-4"]),
            (3, ["record-2", "record-3", "record-4"]),
            (8, ["record-0", "record-1", "record-2", "record-3", "record-4"]),
        ):
            with self.subTest(limit=limit):
                result = self.audit_log.get_audit_history(limit=limit)
                self.assertEqual([record["id"] for record in result], expected_ids)

    def test_empty_history_returns_empty_for_default_and_positive_limits(self) -> None:
        self.assertEqual(self.audit_log.get_audit_history(), [])
        self.assertEqual(self.audit_log.get_audit_history(limit=1), [])

    def test_read_does_not_mutate_or_replace_underlying_history(self) -> None:
        original_history = self.records(5)
        original_contents = list(original_history)
        self.audit_log.audit_history = original_history

        self.audit_log.get_audit_history(limit=3)

        self.assertIs(self.audit_log.audit_history, original_history)
        self.assertEqual(self.audit_log.audit_history, original_contents)


if __name__ == "__main__":
    unittest.main()
