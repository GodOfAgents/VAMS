#!/usr/bin/env python3
"""Tests for the team-controlled bootstrap signer checks (owner decision 12).

All addresses, key hashes and digests below are synthetic counters, not real
keys or accounts.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import team_signer_governance as tsg  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "docs/audit/schemas/team-signer-governance.schema.json"


def _evm(n: int) -> str:
    return "0x" + f"{n:040x}"


def _ada(n: int) -> str:
    return f"{n:056x}"


def _sha(n: int) -> str:
    return f"{n:064x}"


def synthetic() -> dict:
    roles = (*tsg.ROUTINE, *tsg.RECOVERY)
    keys = {role: (i + 1) for i, role in enumerate(roles)}
    return {
        "schema_version": "2.0.0",
        "commit_sha": "a" * 40,
        "governance_mode": "team-controlled-bootstrap",
        "decentralized_governance_claimed": False,
        "independent_review_claimed": False,
        "externally_audited_claimed": False,
        "signers": [
            {"role": r, "evm_address": _evm(keys[r]), "cardano_key_hash": _ada(keys[r]),
             "historical_pem_relationship": False, "independent_key_custody": True}
            for r in tsg.ROUTINE
        ],
        "offline_recovery_seats": [
            {"role": r, "evm_address": _evm(keys[r]), "cardano_key_hash": _ada(keys[r]),
             "historical_pem_relationship": False, "custody_mode": "2-of-3-split-custody",
             "custodians": list(tsg.CUSTODIANS), "custody_threshold": 2,
             "routine_use": False, "rotate_after_use": True}
            for r in tsg.RECOVERY
        ],
        "authorities": [
            {"id": name, "threshold": t, "members": sorted(m), "scope": s,
             "identity": _evm(100 + i) if kind == "evm" else _ada(100 + i)}
            for i, (name, (t, m, s, kind)) in enumerate(tsg.AUTHORITIES.items())
        ],
        "consent_records": [
            {"role": r, **{flag: True for flag in tsg.CONSENT_FLAGS},
             "evidence_path": f"consent/{r.lower()}.json", "evidence_sha256": _sha(i + 1)}
            for i, r in enumerate(tsg.ROUTINE)
        ],
        "rehearsals": [
            {"scenario": s, "passed": True, "evidence_path": f"rehearsal/{s}.json",
             "evidence_sha256": _sha(50 + i)}
            for i, s in enumerate(tsg.SCENARIOS)
        ],
        "emergency_response_target_seconds": 3600,
        "limitations": ["Seats overlap: four people hold every routine seat."],
        "blocking_findings_open": 0,
    }


def _authority(doc: dict, name: str) -> dict:
    return next(a for a in doc["authorities"] if a["id"] == name)


class TeamSignerGovernanceTests(unittest.TestCase):
    def assertRejected(self, doc: dict, fragment: str) -> None:
        errors = tsg.validate_document(doc)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_synthetic_layout_passes(self) -> None:
        self.assertEqual(tsg.validate_document(synthetic()), [])

    def test_source_thresholds_match_layout(self) -> None:
        self.assertEqual(tsg.source_errors(), [])

    def test_source_drift_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "contracts/script").mkdir(parents=True)
            (root / "cardano/lib/vams").mkdir(parents=True)
            deploy = (ROOT / "contracts/script/DeployTestnet.s.sol").read_text(encoding="utf-8")
            (root / "contracts/script/DeployTestnet.s.sol").write_text(
                deploy.replace("_requireSafe(emergencyAuthority, 3, 2,", "_requireSafe(emergencyAuthority, 3, 1,"),
                encoding="utf-8")
            gov = (ROOT / "cardano/lib/vams/governance_v2.ak").read_text(encoding="utf-8")
            (root / "cardano/lib/vams/governance_v2.ak").write_text(
                gov.replace("c.threshold == 3", "c.threshold == 2"), encoding="utf-8")
            errors = tsg.source_errors(root)
        self.assertTrue(any("emergencyAuthority" in e for e in errors), errors)
        self.assertTrue(any("governance_v2" in e for e in errors), errors)

    def test_claims_must_stay_false(self) -> None:
        for claim in ("decentralized_governance_claimed", "independent_review_claimed",
                      "externally_audited_claimed"):
            doc = synthetic()
            doc[claim] = True
            self.assertRejected(doc, claim)

    def test_wrong_threshold_rejected(self) -> None:
        doc = synthetic()
        _authority(doc, "amoy-governance")["threshold"] = 2
        self.assertRejected(doc, "amoy-governance threshold")

    def test_emergency_membership_is_exact(self) -> None:
        doc = synthetic()
        _authority(doc, "amoy-emergency")["members"] = ["ARCHITECT", "SIGNER_A", "SIGNER_C"]
        self.assertRejected(doc, "amoy-emergency members")

    def test_treasury_cannot_use_governance_recovery(self) -> None:
        doc = synthetic()
        members = _authority(doc, "amoy-treasury")["members"]
        members[members.index("TREASURY_RECOVERY")] = "GOVERNANCE_RECOVERY"
        self.assertRejected(doc, "amoy-treasury members")

    def test_missing_or_extra_authority_rejected(self) -> None:
        doc = synthetic()
        doc["authorities"] = [a for a in doc["authorities"] if a["id"] != "cardano-governance"]
        self.assertRejected(doc, "authorities must be exactly")

    def test_recovery_seat_rules(self) -> None:
        for field, value, fragment in (("routine_use", True, "routine approvals"),
                                       ("rotate_after_use", False, "rotated"),
                                       ("custody_threshold", 1, "custody_threshold"),
                                       ("custodians", ["ARCHITECT", "SIGNER_A", "SIGNER_B"], "custodians")):
            doc = synthetic()
            doc["offline_recovery_seats"][0][field] = value
            self.assertRejected(doc, fragment)

    def test_seat_keys_must_be_distinct(self) -> None:
        doc = synthetic()
        doc["signers"][1]["evm_address"] = doc["signers"][0]["evm_address"]
        self.assertRejected(doc, "distinct EVM")
        doc = synthetic()
        doc["offline_recovery_seats"][0]["cardano_key_hash"] = doc["signers"][0]["cardano_key_hash"]
        self.assertRejected(doc, "distinct Cardano")

    def test_zero_address_and_bad_identity_rejected(self) -> None:
        doc = synthetic()
        doc["signers"][0]["evm_address"] = tsg.ZERO_EVM
        self.assertRejected(doc, "non-zero")
        doc = synthetic()
        _authority(doc, "cardano-governance")["identity"] = _evm(7)
        self.assertRejected(doc, "script hash")

    def test_historical_pem_relationship_rejected(self) -> None:
        doc = synthetic()
        doc["signers"][2]["historical_pem_relationship"] = True
        self.assertRejected(doc, "historical PEM")

    def test_consent_and_rehearsal_completeness(self) -> None:
        doc = synthetic()
        doc["consent_records"][0]["amoy_rehearsal_completed"] = False
        self.assertRejected(doc, "amoy_rehearsal_completed")
        doc = synthetic()
        doc["rehearsals"].pop()
        self.assertRejected(doc, "rehearsals must cover")
        doc = synthetic()
        doc["rehearsals"][0]["passed"] = False
        self.assertRejected(doc, "must have passed")

    def test_evidence_paths_stay_inside_bundle(self) -> None:
        for path in ("/etc/passwd", "../outside.json", "a/../../b", "C:\\x.json"):
            doc = synthetic()
            doc["rehearsals"][0]["evidence_path"] = path
            self.assertRejected(doc, "evidence_path")

    def test_overlap_must_be_disclosed(self) -> None:
        doc = synthetic()
        doc["limitations"] = ["Faucet-only."]
        self.assertRejected(doc, "overlap")

    def test_unexpected_field_rejected(self) -> None:
        doc = synthetic()
        doc["signers"][0]["private_key"] = "x"
        self.assertRejected(doc, "unexpected")

    def test_schema_matches_checker(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        props = schema["properties"]
        self.assertEqual(props["schema_version"]["const"], tsg.SCHEMA_VERSION)
        self.assertEqual(props["governance_mode"]["const"], tsg.GOVERNANCE_MODE)
        self.assertEqual(set(props["authorities"]["items"]["properties"]["id"]["enum"]), set(tsg.AUTHORITIES))
        self.assertEqual(set(props["rehearsals"]["items"]["properties"]["scenario"]["enum"]), set(tsg.SCENARIOS))
        self.assertEqual(set(schema["required"]), set(synthetic()))


if __name__ == "__main__":
    unittest.main()
