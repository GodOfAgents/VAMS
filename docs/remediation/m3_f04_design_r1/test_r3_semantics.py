#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class R3SemanticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topology = json.loads((ROOT / "TRANSITION_TOPOLOGY.json").read_text())["transitions"]
        cls.rules = json.loads((ROOT / "VALUE_RULES.json").read_text())
        cls.matrix = json.loads((ROOT / "ACCEPTANCE_MATRIX.json").read_text())["rows"]

    def row(self, name):
        return next(x for x in self.topology if x["id"] == name)

    def test_deregister_has_single_owner_payout_and_no_state(self):
        row = self.row("deregister")
        self.assertEqual(row["outputs"]["agent_state"], 0)
        self.assertEqual(row["outputs"]["owner_release"], 1)
        self.assertEqual(row["owner_release"], "exactly one owner key-credential payout containing stake and every non-identity state asset")
        self.assertEqual(row["identity_burn"], -1)

    def test_every_mutating_transition_has_one_authority_reference(self):
        for row in self.topology:
            self.assertEqual(row["inputs"]["authority_reference"], 1)
            self.assertIn("reference", row["authority_reference"].lower())

    def test_update_continuation_and_non_ada_rules_are_exact(self):
        row = self.row("update")
        self.assertEqual(row["outputs"]["agent_state"], 1)
        self.assertIn("exactly one same registry script", row["continuation"])
        self.assertIn("all non-identity assets_out == assets_in", self.rules["rules"]["update"])

    def test_operator_roles_and_slash_interface_are_closed(self):
        self.assertEqual(self.rules["operator_rules"]["owner"], ["register", "change_operator", "change_metadata", "deregister"])
        self.assertEqual(self.rules["operator_rules"]["operator"], ["change_metadata"])
        self.assertTrue(self.rules["post_f05_slash_interface"]["authority"].startswith("RegistryAuthorityV1.slash_enabled == true"))
        slash = self.row("slash")
        self.assertEqual(slash["pre_f05"], "reject_unconditionally")
        self.assertIn("EvidenceAttestationV1", slash["evidence_reference"])

    def test_mutation_matrix_contains_r3_controls(self):
        ids = {x["id"] for x in self.matrix}
        for required in ("deregister_wrong_payout", "deregister_duplicate_payout", "deregister_non_ada_loss", "update_wrong_authority_reference", "update_non_ada_loss", "register_symbolic_policy_rebind", "slash_expired_evidence"):
            self.assertIn(required, ids)

if __name__ == "__main__":
    unittest.main(verbosity=2)
