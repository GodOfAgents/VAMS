from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit.credential_incident_evidence import (
    REQUIRED_NETWORKS,
    REQUIRED_ROLE_CHECKS,
    validate_credential_incident_report,
)


COMMIT = "a" * 40
NOW = "2026-07-15T00:00:00+00:00"


def _artifact(root: Path, name: str) -> dict[str, str]:
    path = root / "docs" / "audit" / "evidence" / "credential-incident" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(name.encode())
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _report(root: Path) -> dict:
    identities = []
    for index in range(3):
        roles = {
            role: {"clear": True, "evidence": _artifact(root, f"identity-{index}-{role}.json")}
            for role in sorted(REQUIRED_ROLE_CHECKS)
        }
        funding = [
            {
                "network": network,
                "public_identifier": f"public-{index}-{network}",
                "observed_at": NOW,
                "zero_balance": True,
                "evidence": _artifact(root, f"identity-{index}-{network}.json"),
            }
            for network in sorted(REQUIRED_NETWORKS)
        ]
        identities.append(
            {
                "fingerprint_sha256": f"{index + 1:064x}",
                "key_type": "public-test-fixture",
                "revoked_at": NOW,
                "replacement_fingerprint_sha256": f"{index + 10:064x}",
                "public_identifiers": [f"public-{index}"],
                "role_impact_checks": roles,
                "funding_checks": funding,
                "revocation_evidence": _artifact(root, f"identity-{index}-revocation.json"),
            }
        )
    return {
        "schema_version": "1.0.0",
        "commit_sha": COMMIT,
        "incident_id": "VAMS-PEM-2026-001",
        "affected_identities": identities,
        "history_rewrite": {
            "completed": True,
            "completed_at": NOW,
            "all_refs_rewritten": True,
            "collaborators_recloned": True,
            "forks_coordinated": True,
            "github_cached_refs_purged": True,
            "changed_refs_evidence": _artifact(root, "changed-refs.txt"),
            "github_support_evidence": _artifact(root, "github-support.json"),
        },
        "full_history_scans": {
            "gitleaks": {
                "full_history": True,
                "findings_count": 0,
                "command": "gitleaks git . --log-opts=--all",
                "evidence": _artifact(root, "gitleaks.json"),
            },
            "trufflehog": {
                "full_history": True,
                "findings_count": 0,
                "command": "trufflehog git . --results=verified,unknown,unverified",
                "evidence": _artifact(root, "trufflehog.json"),
            },
        },
        "reviewer": "Ada Reviewer",
        "reviewer_organization": "Independent Security Lab",
        "reviewed_at": NOW,
        "blocking_findings_open": 0,
    }


class CredentialIncidentEvidenceTests(unittest.TestCase):
    def test_valid_public_closure_evidence_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "report.json"
            path.write_text(json.dumps(_report(root)), encoding="utf-8")
            self.assertEqual(validate_credential_incident_report(path, COMMIT, root), [])

    def test_missing_rotation_or_full_history_result_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = _report(root)
            report["affected_identities"][0]["revocation_evidence"] = {
                "path": "docs/audit/evidence/missing.json",
                "sha256": "0" * 64,
            }
            report["full_history_scans"]["trufflehog"]["command"] = "trufflehog git ."
            path = root / "report.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            errors = validate_credential_incident_report(path, COMMIT, root)
            self.assertTrue(any("missing" in error for error in errors))
            self.assertTrue(any("every result class" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
