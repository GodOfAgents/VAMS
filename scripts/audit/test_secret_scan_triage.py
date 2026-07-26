from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
GITLEAKS_DOC = ROOT / "docs" / "audit" / "GITLEAKS_ADJUDICATION.md"
TRUFFLEHOG_DOC = ROOT / "docs" / "audit" / "TRUFFLEHOG_TRIAGE.md"
INCIDENT_RUNBOOK = ROOT / "docs" / "audit" / "CREDENTIAL_INCIDENT_RUNBOOK.md"
CLOSURE_REPORT = (
    ROOT / "docs" / "audit" / "evidence" / "credential-incident-report.json"
)


class SecretScanTriageTests(unittest.TestCase):
    def test_gitleaks_ci_classification_sums_to_report_total(self) -> None:
        text = GITLEAKS_DOC.read_text(encoding="utf-8")
        section = text.split("## Exact Protected-CI Path Classification", 1)[1]
        section = section.split("## TruffleHog Correlation", 1)[0]
        counts = [
            int(match.group(1))
            for match in re.finditer(r"^\|[^\n]+\|\s*(\d+)\s*\|[^\n]+$", section, re.MULTILINE)
        ]
        self.assertEqual(counts, [802, 46, 6, 9, 3, 1, 2])
        self.assertEqual(sum(counts), 869)

    def test_trufflehog_triage_is_exact_and_contains_no_fill_rows(self) -> None:
        text = TRUFFLEHOG_DOC.read_text(encoding="utf-8")
        row_numbers = [
            int(match.group(1))
            for match in re.finditer(r"^\|\s*(\d+)\s*\|", text, re.MULTILINE)
        ]
        self.assertEqual(row_numbers, list(range(1, 21)))
        self.assertNotIn("_TBD_", text)
        self.assertNotIn("**DONE", text)
        self.assertRegex(text, r"zero\s+verified and 20 unverified")

    def test_no_repository_closure_report_exists_without_real_evidence(self) -> None:
        self.assertFalse(
            CLOSURE_REPORT.exists(),
            "credential closure reports belong in protected operational evidence",
        )

    def test_runbook_rejects_failed_endpoint_probe_as_revocation_proof(self) -> None:
        text = INCIDENT_RUNBOOK.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        self.assertIn("invalid project id", normalized)
        self.assertIn("cannot prove", normalized)
        self.assertIn("cannot establish the exact revocation time", normalized)
        self.assertIn("exact_revocation_time_unavailable=true", normalized)


if __name__ == "__main__":
    unittest.main()
