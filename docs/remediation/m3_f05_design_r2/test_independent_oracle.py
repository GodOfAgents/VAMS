"""Independent byte-oracle checks, deliberately without validator imports."""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from independent_oracle import (
    ack_bytes,
    action_id,
    authority_state_bytes,
    certificate_bytes,
    effect_commitment,
    payload_bytes,
    sha,
    sync_bytes,
    executor_call_hash,
    _uint,
)


ROOT = Path(os.environ.get("F05_R4_FIXTURE_DIR", Path(__file__).resolve().parent))
CONTRACT = json.loads((ROOT / "CONTRACT.json").read_text(encoding="utf-8"))
_vectors_path = ROOT / "VECTORS.json"
if _vectors_path.exists():
    ACTION_VECTORS = json.loads(_vectors_path.read_text(encoding="utf-8"))["action_vectors"]
else:
    ACTION_VECTORS = json.loads((ROOT / "action-vectors.json").read_text(encoding="utf-8"))

KNOWN_ANSWERS = [
    {"payload":"9e4f62ee97c0866c7031e93516bc13ca731bec5d9cb50cd07cb6381451dab3e7","action":"71c076ea617e58830d8c1ff6ba6e70354bc9340d918d8bf200699549896a0edb","certificate":"f39b4fff6736172e3acc4cbf011e01a8ee45a4d328920d8d8328a034139ecbbe","effect":"3c3d7ec68b584e1340b3e91c55bdec4549b7aebf09dfcddc3163e800d40dfb5c","ack":"4bb451a509e1ce85a63f9bb48efcafa7cbb05caa02d4e95360481900f8789d03"},
    {"payload":"f17e289483e8c5e0e21dbb4aa931727ddbc8e67de013dd96794dd3d44be60f7c","action":"10b6c643fba10cbb0e5c447cd296209a4ad35dd79c98dcff63fa8ecdb9964774","certificate":"87da51ab115b9db280669a09edbf0f001d9f79d3bdefd36316c718f7586146f6","effect":"93399017f2a9debf836eec1c42988c056203d57dd62797628e2ce1f28417bd0d","ack":"ee59d27690b5f252cd6c01abd70b04da977d931dddaaa892c27278b071a5ed10"},
    {"payload":"4b875e62aa9f8b098103b416122d3a0aec70c5c91b1542fcaec7ce7a687281da","action":"f94f4843d2a3b98664a8e453d3166a174f65be8b6709f57a3db3771d8e2b40da","certificate":"4d9b6909a92f4618e65be84a3f7489ab392c8df5d166704f7f7155a3422a1a05","effect":"978e25ca66650ad322450719aea42cda178365a1c64db9a5532ab7daf1879139","ack":"ac0801314cd0bbc3c10250077f59d068af86effa55748c47aed6d36d9dc9cecb"},
    {"payload":"fe69cb885cc2cb4d7fe4143bf589e3a0f004845ae5e8b23b0e37c54b770f1702","action":"1d4db5d2732e240cf01da26237b0bf09a2a8098b7f726bd85915da791086147e","certificate":"9a051e52fd453d040bf69f932f5481a9ded11cea0a7d0ecb92c48449ee282ae7","effect":"7c048a76a704594fc87f51fff8a8c89b233cb4439a89e1a788a89c9bec0ba1ca","ack":"a3b8d671285fa189127d90b104b34a678371c9704bd5d387509c7e30c1c44a4a"},
]


class IndependentOracleTests(unittest.TestCase):
    def test_all_four_action_oracles_match_literal_known_answers(self) -> None:
        self.assertEqual(len(ACTION_VECTORS), 4)
        self.assertEqual([x["action_name"] for x in ACTION_VECTORS],
                         ["WRAPPED_CREDIT", "WRAPPED_RELEASE", "SLASH_AGENT", "EXECUTE_INTENT"])
        for index, record in enumerate(ACTION_VECTORS):
            expected = KNOWN_ANSWERS[index]
            action = CONTRACT["actions"][index]
            payload = payload_bytes(action, record["payload"], action["payload_domain_hex"])
            self.assertEqual(payload.hex(), record["payload_bytes_hex"])
            self.assertEqual(sha(payload).hex(), expected["payload"])
            self.assertEqual(action_id(record["identity_fields"], record["payload_sha256"], CONTRACT["action_id_serialization"]["domain_hex"]).hex(), expected["action"])
            cert = certificate_bytes(record["certificate"]["message_fields"], CONTRACT["certificate"]["message_fields"], CONTRACT["certificate"]["message_domain_hex"])
            self.assertEqual(len(cert), 321)
            self.assertEqual(cert.hex(), record["certificate"]["message_bytes_hex"])
            self.assertEqual(sha(cert).hex(), expected["certificate"])
            self.assertEqual(sha(authority_state_bytes(record["authority"]["canonical_state"], CONTRACT)).hex(),
                             "8cf803bd4b23ca557300e549790eb94214c2fbd3c8df377532128595b2646806")
            sync = record["authority"]["polygon_mirror"]["sync_certificate"]
            sync_message = sync_bytes(sync["message_fields"], CONTRACT)
            self.assertEqual(len(sync_message), 389)
            self.assertEqual(sha(sync_message).hex(), "d37233a4a46f9d37332a9b64b1e4e6257fc58b9628d5dd48ed86219179c7e8ea")
            self.assertEqual(effect_commitment(record, action, CONTRACT).hex(), expected["effect"])
            if record["action_name"] == "EXECUTE_INTENT":
                executor_hash = executor_call_hash(
                    record["payload"], CONTRACT["executor_registry"]["test_only_mapping"],
                    action["code"], CONTRACT["domain_bytes"]["executor_call"]["domain_hex"],
                )
                self.assertEqual(executor_hash.hex(), "1567d76c9d892a30b2951d9b23fcdf9865308a364811925cd0803cacdb5486e2")
                self.assertEqual(record["action_effects"]["after"]["executor_effect_hash_hex"], executor_hash.hex())
            receipt = record["transaction"]["ack"]["receipt"]
            ack = ack_bytes(receipt["message_fields"], CONTRACT)
            self.assertEqual(len(ack), 351)
            self.assertEqual(ack.hex(), receipt["message_bytes_hex"])
            self.assertEqual(sha(ack).hex(), expected["ack"])

    def test_positive_action_state_transitions_have_explicit_accounting(self) -> None:
        scale = CONTRACT["asset"]["source_units_per_wrapped_unit"]
        for record in ACTION_VECTORS:
            self.assertEqual(record["expected"], {"accepted": True, "result_code": "ACCEPT"})
            before = record["state_before"]["global"]
            source = record["state_after_source"]["global"]
            dest = record["state_after_destination"]["global"]
            final = record["state_after"]["global"]
            self.assertEqual(final, dest)
            self.assertEqual(record["state_before"]["source_stream"]["nonce"], 0)
            self.assertEqual(record["state_after_source"]["source_stream"]["nonce"], 1)
            self.assertEqual(record["state_after_destination"]["source_stream"], record["state_after_source"]["source_stream"])
            self.assertEqual(record["state_after"]["source_stream"], record["state_after_source"]["source_stream"])
            amount = record["payload"].get("source_amount_base", 0)
            wrapped = record["payload"].get("wrapped_amount", 0)
            name = record["action_name"]
            if name == "WRAPPED_CREDIT":
                self.assertEqual((source["current_locked_source_balance_base"], source["actual_escrow_token_balance_base"], source["pending_credit_base"]), (amount, amount, amount))
                self.assertEqual((dest["minted"], dest["outstanding"], dest["pending_credit_base"]), (amount // scale, amount // scale, 0))
            elif name == "WRAPPED_RELEASE":
                release_base = wrapped * scale
                self.assertEqual((before["minted"], before["outstanding"], before["current_locked_source_balance_base"]), (10, 10, 10 * scale))
                self.assertEqual((source["burned"], source["outstanding"], source["pending_release_base"]), (1, 9, release_base))
                self.assertEqual((dest["current_locked_source_balance_base"], dest["actual_escrow_token_balance_base"], dest["pending_release_base"]), (9 * scale, 9 * scale, 0))
            elif name == "SLASH_AGENT":
                self.assertEqual(source, before)
                self.assertEqual(dest["slash_reserve_lovelace"], record["payload"]["slash_amount_lovelace"])
            else:
                self.assertEqual(source, before)
                self.assertEqual(dest, before)
            self.assertEqual(record["counter_changes"], {k: dest[k] - before[k] for k in ("minted", "burned", "outstanding")})
            for snap in (record["state_before"], record["state_after_source"], record["state_after_destination"], record["state_after"]):
                g = snap["global"]
                self.assertEqual(g["outstanding"], g["minted"] - g["burned"])
                self.assertEqual(g["current_locked_source_balance_base"],
                                 (g["minted"] - g["burned"]) * scale + g["pending_credit_base"] + g["pending_release_base"])

    def test_all_action_and_attestation_signatures_are_real_ed25519(self) -> None:
        signature_checks = []
        for index, record in enumerate(ACTION_VECTORS):
            action = CONTRACT["actions"][index]
            cert = certificate_bytes(record["certificate"]["message_fields"], CONTRACT["certificate"]["message_fields"], CONTRACT["certificate"]["message_domain_hex"])
            sync = record["authority"]["polygon_mirror"]["sync_certificate"]
            sync_message = sync_bytes(sync["message_fields"], CONTRACT)
            receipt = record["transaction"]["ack"]["receipt"]
            ack = ack_bytes(receipt["message_fields"], CONTRACT)
            for item, msg in ((record["certificate"], cert), (sync, sync_message), (receipt, ack)):
                self.assertEqual(item["message_bytes_hex"], msg.hex())
                self.assertEqual(len(item["signatures_hex"]), 3)
                self.assertEqual(item["signer_ids"], [0, 1, 2])
                for signer, signature in zip(item["signer_ids"], item["signatures_hex"], strict=True):
                    public_key = Ed25519PublicKey.from_public_bytes(
                        bytes.fromhex(item["committee_public_keys_hex"][signer])
                    )
                    try:
                        public_key.verify(bytes.fromhex(signature), msg)
                    except InvalidSignature:
                        signature_checks.append(False)
                    else:
                        signature_checks.append(True)
        self.assertTrue(signature_checks)
        self.assertEqual(signature_checks, [True] * len(signature_checks))

    def test_uint64_and_uint128_boundaries_are_literal(self) -> None:
        for width, maximum, encoded in (
            (8, 18446744073709551615, "ffffffffffffffff"),
            (16, 340282366920938463463374607431768211455, "ffffffffffffffffffffffffffffffff"),
        ):
            self.assertEqual((0).to_bytes(width, "big").hex(), "00" * width)
            self.assertEqual(maximum.to_bytes(width, "big").hex(), encoded)
            self.assertEqual(_uint(0, width), bytes(width))
            self.assertEqual(_uint(maximum, width).hex(), encoded)
            with self.assertRaises(OverflowError):
                (maximum + 1).to_bytes(width, "big")
            with self.assertRaises(ValueError):
                _uint(maximum + 1, width)
            with self.assertRaises(ValueError):
                _uint(-1, width)
        for bad in (True, False):
            with self.assertRaises(ValueError):
                # bool is deliberately excluded despite Python's bool-is-int relation.
                _uint(bad, 8)

    def test_oracle_module_has_no_validator_dependency(self) -> None:
        source = (Path(__file__).with_name("independent_oracle.py")).read_text(encoding="utf-8")
        self.assertNotIn("validate_design", source)
        self.assertNotIn("importlib", source)


if __name__ == "__main__":
    unittest.main()
