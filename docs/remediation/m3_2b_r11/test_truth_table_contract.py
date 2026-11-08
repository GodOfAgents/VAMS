"""M3.2b-R11 closed truth-table contract regressions."""
from __future__ import annotations

import unittest

from docs.remediation.m3_2b_r10 import test_candidate_truth_table as r10


class TruthTableContractTests(unittest.TestCase):
    def test_exact_closed_set_is_one_positive_and_twelve_negative_rows(self) -> None:
        r10.validate_truth_table_rows()
        self.assertEqual(len(r10.ROWS), 13)
        self.assertEqual(sum(row[2] == "detected" for row in r10.ROWS), 1)
        self.assertEqual(sum(row[2] != "detected" for row in r10.ROWS), 12)

    def test_row_deletion_is_rejected(self) -> None:
        rows = list(r10.ROWS[:-1])
        with self.assertRaises(AssertionError):
            r10.validate_truth_table_rows(rows)

    def test_duplicate_row_is_rejected(self) -> None:
        rows = list(r10.ROWS)
        rows[-1] = rows[-2]
        with self.assertRaises(AssertionError):
            r10.validate_truth_table_rows(rows)

    def test_extra_row_is_rejected(self) -> None:
        rows = list(r10.ROWS)
        rows.append(("unexpected", dict(r10.ROWS[0][1]), "detected"))
        with self.assertRaises(AssertionError):
            r10.validate_truth_table_rows(rows)

    def test_schema_mutation_is_rejected(self) -> None:
        rows = list(r10.ROWS)
        row_id, record, expected = rows[0]
        malformed = dict(record)
        malformed.pop("hashes_differ")
        rows[0] = (row_id, malformed, expected)
        with self.assertRaises(AssertionError):
            r10.validate_truth_table_rows(rows)

    def test_unknown_and_boolean_integer_rows_are_present(self) -> None:
        ids = {row[0] for row in r10.ROWS}
        self.assertIn("malformed_unknown", ids)
        self.assertIn("malformed_bool_integer", ids)
        expected = {row[0]: row[2] for row in r10.ROWS}
        self.assertEqual(expected["malformed_unknown"], "invalid_harness")
        self.assertEqual(expected["malformed_bool_integer"], "invalid_harness")


if __name__ == "__main__":
    unittest.main()
