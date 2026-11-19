"""Focused local checks for the frozen F05.1-R4 design contract."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from validate_design import (
    DesignError,
    action_id,
    action_quantity_allowed,
    certificate_message,
    convert_source_amount,
    counter_transition,
    cursor_accepts,
    load_json,
    payload_hash,
    validate_contract,
    verify_signatures,
)

HERE = Path(__file__).resolve().parent
CONTRACT = load_json(HERE / "CONTRACT.json")
VECTORS = load_json(HERE / "VECTORS.json")


class F05DesignTests(unittest.TestCase):
    def test_closed_contract_and_frozen_action_vector_set(self):
        self.assertEqual(validate_contract(CONTRACT, VECTORS), {"actions": 4, "certificate_fields": 22})
        self.assertEqual(
            [item["action_name"] for item in VECTORS["action_vectors"]],
            ["WRAPPED_CREDIT", "WRAPPED_RELEASE", "SLASH_AGENT", "EXECUTE_INTENT"],
        )

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory(prefix="vams-duplicate-key-") as temp:
            path = Path(temp) / "duplicate.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaises(DesignError):
                load_json(path)

    def test_unknown_contract_key_rejected(self):
        changed = copy.deepcopy(CONTRACT)
        changed["unreviewed"] = True
        with self.assertRaises(DesignError):
            validate_contract(changed, VECTORS)

    def test_source_supply_and_per_action_mint_boundaries(self):
        scale = CONTRACT["asset"]["source_units_per_wrapped_unit"]
        source_max = CONTRACT["asset"]["source_max_supply_base"]
        mint_max = CONTRACT["asset"]["cardano_mint_burn_max_abs_quantity"]
        self.assertEqual(convert_source_amount(0, CONTRACT), 0)
        for amount in (1, scale - 1, scale + 1):
            with self.assertRaisesRegex(DesignError, "NOT_EXACTLY_DIVISIBLE"):
                convert_source_amount(amount, CONTRACT)
        self.assertEqual(convert_source_amount(scale, CONTRACT), 1)
        action_source_max = mint_max * scale
        self.assertEqual(convert_source_amount(action_source_max, CONTRACT), mint_max)
        self.assertTrue(action_quantity_allowed(mint_max, CONTRACT))
        self.assertFalse(action_quantity_allowed(0, CONTRACT))
        with self.assertRaisesRegex(DesignError, "MINT_BURN_INT64_CAP"):
            convert_source_amount(action_source_max + scale, CONTRACT)
        with self.assertRaisesRegex(DesignError, "SOURCE_CAP_EXCEEDED"):
            convert_source_amount(source_max + 1, CONTRACT)

    def test_cumulative_counter_maximum_and_overflow(self):
        maximum = CONTRACT["asset"]["counter_max"]
        self.assertEqual(counter_transition(maximum - 1, 0, 1, "mint", CONTRACT), (maximum, 0, maximum))
        with self.assertRaisesRegex(DesignError, "overflow"):
            counter_transition(maximum, 0, 1, "mint", CONTRACT)
        with self.assertRaisesRegex(DesignError, "overflow or underflow"):
            counter_transition(0, 0, 1, "burn", CONTRACT)

    def test_cardano_asset_output_uint64_boundary(self):
        limit = CONTRACT["asset"]["cardano_multiasset_max_quantity"]
        self.assertLess(CONTRACT["asset"]["max_wrapped_supply"], limit)
        self.assertLessEqual(CONTRACT["asset"]["max_wrapped_supply"], 2**64 - 1)
        self.assertLessEqual(CONTRACT["asset"]["cardano_mint_burn_max_abs_quantity"], 2**63 - 1)

    def test_canonical_certificate_layout_and_hashes(self):
        sample = VECTORS["action_vectors"][0]
        payload = bytes.fromhex(sample["payload_bytes_hex"])
        payload_digest = payload_hash(payload)
        action_digest = action_id(
            sample["identity_fields"], payload_digest, CONTRACT["action_id_serialization"]["domain_hex"]
        )
        message = certificate_message(
            sample["certificate"]["message_fields"], CONTRACT["certificate"]["message_domain_hex"]
        )
        self.assertEqual(payload_digest.hex(), sample["payload_sha256"])
        self.assertEqual(action_digest.hex(), sample["action_id_hex"])
        self.assertEqual(message.hex(), sample["certificate"]["message_bytes_hex"])
        self.assertEqual(len(message), 321)
        self.assertEqual(hashlib.sha256(message).hexdigest(), sample["certificate"]["message_sha256"])

    def test_ed25519_exact_three_sorted_distinct_members(self):
        private = [Ed25519PrivateKey.from_private_bytes(bytes([i]) * 32) for i in range(1, 6)]
        public = [key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw) for key in private]
        members = sorted(public)
        by_public = {key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw): key for key in private}
        message = b"VAMS-F05-SYNTHETIC-CERTIFICATE-V1"
        signers = members[:3]
        signatures = [{"public_key_hex": key.hex(), "signature_hex": by_public[key].sign(message).hex()} for key in signers]
        self.assertTrue(verify_signatures([key.hex() for key in members], message, signatures))
        self.assertFalse(verify_signatures([key.hex() for key in members], message, signatures[:2]))
        self.assertFalse(verify_signatures([key.hex() for key in members], message, [signatures[0], signatures[0], signatures[2]]))
        bad_signature = copy.deepcopy(signatures)
        bad_signature[0]["signature_hex"] = "00" * 64
        self.assertFalse(verify_signatures([key.hex() for key in members], message, bad_signature))
        self.assertFalse(verify_signatures([key.hex() for key in members[::-1]], message, signatures))

    def test_checkpoint_conflict_staleness_future_and_nonce_replay(self):
        cursor = {"checkpoint_number": 10, "checkpoint_hash_hex": "aa" * 32, "previous_checkpoint_hash_hex": "99" * 32, "source_action_nonce": 4}
        base = {"source_event_block_number": 11, "finalized_checkpoint_number": 11, "finalized_checkpoint_hash_hex": "bb" * 32, "previous_certified_checkpoint_hash_hex": "aa" * 32, "source_action_nonce": 5}
        self.assertTrue(cursor_accepts(cursor, base))
        self.assertFalse(cursor_accepts(cursor, {**base, "source_event_block_number": 12}))
        self.assertFalse(cursor_accepts(cursor, {**base, "finalized_checkpoint_number": 9}))
        self.assertFalse(cursor_accepts(cursor, {**base, "finalized_checkpoint_number": 10, "finalized_checkpoint_hash_hex": "cc" * 32}))
        self.assertFalse(cursor_accepts(cursor, {**base, "previous_certified_checkpoint_hash_hex": "dd" * 32}))
        self.assertFalse(cursor_accepts(cursor, {**base, "source_action_nonce": 4}))
        self.assertFalse(cursor_accepts(cursor, {**base, "source_action_nonce": 6}))

    def test_action_identity_binds_domain_and_payload(self):
        sample = VECTORS["action_vectors"][0]
        payload_digest = payload_hash(bytes.fromhex(sample["payload_bytes_hex"]))
        domain = CONTRACT["action_id_serialization"]["domain_hex"]
        original = action_id(sample["identity_fields"], payload_digest, domain)
        changed = copy.deepcopy(sample["identity_fields"])
        changed["destination_network_magic"] = 2
        self.assertNotEqual(original, action_id(changed, payload_digest, domain))
        changed = copy.deepcopy(sample["identity_fields"])
        changed["action_code"] = 3
        self.assertNotEqual(original, action_id(changed, payload_digest, domain))
        self.assertNotEqual(payload_digest, payload_hash(bytes.fromhex(sample["payload_bytes_hex"]) + b"x"))


if __name__ == "__main__":
    unittest.main()
