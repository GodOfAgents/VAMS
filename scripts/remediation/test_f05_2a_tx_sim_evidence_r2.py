"""Dependency-free regressions for the F05.2a R2 evidence boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

import f05_2a_tx_sim_evidence_contract as contract
import f05_2a_tx_sim_registry as registry


FIXTURES = contract.ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1"
VALID_TX = (FIXTURES / "valid.tx.cbor").read_bytes()
NEGATIVE_TX = (FIXTURES / "authority_value_minus_one.tx.cbor").read_bytes()
POSITIVE_TX_ID = "695e8caab89a518b36885cb8377a8e8d472acd1090f55389a4a49cd65131f34b"
NEGATIVE_TX_ID = "83d9259683d268005ae4dbf06a600de63712220ceb9a4e4ae6db65600f50988a"


def transcript(tx: bytes, suffix: str = "") -> str:
    body = registry.roundtrip(tx)[0]
    tx_id = hashlib.blake2b(registry.dumps(body), digest_size=32).hexdigest()
    return ("      Parsing script context\n"
            f"   Simulating {tx_id}\n"
            "   Evaluating Mint[0]\n" + suffix)


class R2EvidenceContractTests(unittest.TestCase):
    def test_exact_real_simulator_transcripts(self) -> None:
        positive_stderr = ("      Parsing script context\n"
                           f"   Simulating {POSITIVE_TX_ID}\n"
                           "   Evaluating Mint[0]\n")
        negative_stderr = ("      Parsing script context\n"
                           f"   Simulating {NEGATIVE_TX_ID}\n"
                           "   Evaluating Mint[0]\n"
                           "        Error \x1b[31mfailed script execution\n"
                           "      Mint[0] the validator crashed / exited prematurely\x1b[39m\n")
        for cpu in (431999255, 431990367):
            positive = {"exit": 0, "stdout": json.dumps([{"mem": 424440,
                        "cpu": cpu, "traces": []}]), "stderr": positive_stderr}
            self.assertEqual(registry.classify_tx_sim_result(
                positive, VALID_TX, contract.POLICY_HASH),
                {"stage": "script_accepted", "target_script_invoked": True})
        negative = {"exit": 1, "stdout": "", "stderr": negative_stderr}
        self.assertEqual(registry.classify_tx_sim_result(
            negative, NEGATIVE_TX, contract.POLICY_HASH),
            {"stage": "compiled_evaluation", "target_script_invoked": True})

    def test_ambiguous_or_conflicting_transcripts_fail_closed(self) -> None:
        failure = ("        Error failed script execution\n"
                   "      Mint[0] the validator crashed / exited prematurely\n")
        success = json.dumps([{"mem": 424440, "cpu": 431999255,
                               "traces": []}])
        cases = [
            ({"exit": 1, "stdout": "", "stderr": "Parsing script context Evaluating Mint[0] failed script execution"}, NEGATIVE_TX),
            ({"exit": 0, "stdout": "", "stderr": transcript(NEGATIVE_TX, failure)}, NEGATIVE_TX),
            ({"exit": 1, "stdout": success, "stderr": transcript(VALID_TX)}, VALID_TX),
            ({"exit": 0, "stdout": success, "stderr": transcript(VALID_TX, "   Evaluating Mint[0]\n")}, VALID_TX),
            ({"exit": 1, "stdout": "", "stderr": transcript(NEGATIVE_TX, "Error failed script execution\n")}, NEGATIVE_TX),
            ({"exit": 1, "stdout": "Evaluating Mint[0]", "stderr": transcript(NEGATIVE_TX, failure)}, NEGATIVE_TX),
            ({"exit": 0, "stdout": '[{"mem":1,"mem":2,"cpu":1,"traces":[]}]',
              "stderr": transcript(VALID_TX)}, VALID_TX),
            ({"exit": 1, "stdout": "", "stderr": transcript(VALID_TX, failure)}, NEGATIVE_TX),
            ({"exit": 0, "stdout": success, "stderr": transcript(NEGATIVE_TX)}, VALID_TX),
        ]
        # The final two cases have well-formed text but the wrong body ID.
        for case, tx in cases:
            with self.subTest(case=case):
                self.assertEqual(registry.classify_tx_sim_result(
                    case, tx, contract.POLICY_HASH),
                    {"stage": "indeterminate", "target_script_invoked": False})

    def test_six_applied_hashes_and_historical_33_are_pending(self) -> None:
        generated = contract.generate()
        self.assertEqual(generated["schema_version"],
                         "f05-2a-ledger-negative-evidence-contract-r2")
        rows = generated["negative_cases"]
        self.assertEqual(len(rows), 55)
        self.assertEqual(len(generated["compiled_mutations"]), 21)
        self.assertTrue(all(row["status"] == "PENDING" for row in rows))
        self.assertTrue(all(row["status"] == "PENDING" for row in generated["compiled_mutations"]))
        applied = [row for row in rows if row["id"] in contract.APPLIED_PARAMETER_CASES]
        self.assertEqual({row["id"] for row in applied}, contract.APPLIED_PARAMETER_CASES)
        for row in applied:
            self.assertIsNone(row["target_policy_hash"])
            self.assertIsNone(row["compiled_target_policy_id"])
        for row in generated["compiled_mutations"]:
            if row["category"] in {"alternate_parameter_mutation", "context_only_mutation"}:
                self.assertIsNone(row["target_policy_hash"])
        prior = next(row for row in rows if row["id"] == "authority_value_minus_one")
        self.assertEqual(prior["status"], "PENDING")
        self.assertIn("historical_evidence_ref", prior)
        self.assertIn("sponsor change plus one", prior["preservation_delta"])


if __name__ == "__main__":
    unittest.main()
