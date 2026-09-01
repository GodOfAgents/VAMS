from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.audit.test_history_rewrite_script import (
    _maintenance_approval,
    _rotation_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "audit" / "history_rewrite_input_validator.py"
MAIN_SHA = "d" * 40


def _run(rotation: object, approval: object) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        rotation_path = root / "rotation.json"
        approval_path = root / "approval.json"
        rotation_path.write_text(json.dumps(rotation), encoding="utf-8")
        approval_path.write_text(json.dumps(approval), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--rotation-evidence",
                str(rotation_path),
                "--maintenance-approval",
                str(approval_path),
                "--expected-main-sha",
                MAIN_SHA,
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


class HistoryRewriteInputValidatorTests(unittest.TestCase):
    def test_accepts_complete_incident_bound_local_approval(self) -> None:
        result = _run(_rotation_evidence(), _maintenance_approval(MAIN_SHA))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("approve only the local rewrite", result.stdout)

    def test_rejects_placeholder_records(self) -> None:
        result = _run({"status": "decommissioned"}, {"approved": True})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rotation evidence missing fields", result.stdout)
        self.assertIn("maintenance approval missing fields", result.stdout)

    def test_rejects_remote_force_push_preapproval(self) -> None:
        rotation = _rotation_evidence()
        approval = _maintenance_approval(MAIN_SHA)
        rotation["remote_force_push_approved"] = True
        approval["remote_force_push_approved"] = True

        result = _run(rotation, approval)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not pre-approve a remote force push", result.stdout)

    def test_rejects_uncleared_identity_role(self) -> None:
        rotation = copy.deepcopy(_rotation_evidence())
        identities = rotation["affected_identities"]
        assert isinstance(identities, list)
        identities[0]["role_impact_checks"]["safe"]["clear"] = False

        result = _run(rotation, _maintenance_approval(MAIN_SHA))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("role_impact_checks.safe is not clear", result.stdout)

    def test_rejects_unbound_or_incomplete_freeze(self) -> None:
        approval = _maintenance_approval("e" * 40)
        approval["actions_enabled"] = True
        approval["branch_ruleset"]["bypass_actor_count"] = 1
        approval["inventory_counts"]["tags"] = 1

        result = _run(_rotation_evidence(), approval)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not bind the mirrored main SHA", result.stdout)
        self.assertIn("GitHub Actions must be disabled", result.stdout)
        self.assertIn("must have zero bypass actors", result.stdout)
        self.assertIn("inventory_counts.tags must be zero", result.stdout)


if __name__ == "__main__":
    unittest.main()
