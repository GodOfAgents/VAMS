"""Stdlib tests for the unsigned heartbeat consent v2 data codec."""
from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import unittest

from gateway.heartbeat_consent_v2 import (
    BASE_DOMAIN,
    MAX_ENCODING_BYTES,
    MODE_ENROLL,
    MODE_RECOVER_LOST_KEY,
    MODE_ROTATE_NORMAL,
    ROLE_MASK_ENROLL,
    ROLE_MASK_RECOVER_LOST_KEY,
    ROLE_MASK_ROTATE_NORMAL,
    WITNESS_DOMAIN,
    HeartbeatConsentBaseIntentV2,
    HeartbeatConsentDataError,
    HeartbeatConsentWitnessV2,
)


ZERO32 = bytes(32)


def _base(mode: int = MODE_ENROLL, **changes: object) -> HeartbeatConsentBaseIntentV2:
    if mode == MODE_ENROLL:
        expected_digest, expected_generation, proposed_generation = ZERO32, 0, 1
    else:
        expected_digest, expected_generation, proposed_generation = b"\x09" * 32, 7, 8
    values: dict[str, object] = {
        "mode": mode,
        "source_scheme": 1,
        "authority_source_digest": b"\x01" * 32,
        "timelock_address": b"\x02" * 20,
        "timelock_code_hash": b"\x03" * 32,
        "authority_config_digest": b"\x04" * 32,
        "authority_change_sequence": 11,
        "policy_root": b"\x05" * 32,
        "policy_version": 12,
        "authority_epoch": 13,
        "principal_id": b"\x06" * 32,
        "proposed_record_digest": b"\x07" * 32,
        "expected_record_digest": expected_digest,
        "expected_generation": expected_generation,
        "proposed_generation": proposed_generation,
        "consent_nonce": 14,
        "timelock_predecessor": ZERO32,
        "timelock_salt": b"\x08" * 32,
    }
    values.update(changes)
    return HeartbeatConsentBaseIntentV2(**values)


def _role_mask(mode: int) -> int:
    if mode == MODE_ENROLL:
        return ROLE_MASK_ENROLL
    if mode == MODE_ROTATE_NORMAL:
        return ROLE_MASK_ROTATE_NORMAL
    return ROLE_MASK_RECOVER_LOST_KEY


def _witness(base: HeartbeatConsentBaseIntentV2, **changes: object) -> HeartbeatConsentWitnessV2:
    values: dict[str, object] = {
        "base_intent_digest": base.digest,
        "operation_id": b"\x0a" * 32,
        "queued_eta": 1_900,
        "post_eta_challenge_commitment": b"\x0b" * 32,
        "issued_at": 2_000,
        "expires_at": 2_001,
        "mode": base.mode,
        "required_role_mask": _role_mask(base.mode),
    }
    values.update(changes)
    return HeartbeatConsentWitnessV2(**values)


def _first_field_offset(domain: bytes) -> int:
    return len(domain) + 2


class HeartbeatConsentV2CodecTests(unittest.TestCase):
    def test_all_modes_round_trip_and_derive_deterministic_role_masks(self) -> None:
        cases = (
            (MODE_ENROLL, ROLE_MASK_ENROLL),
            (MODE_ROTATE_NORMAL, ROLE_MASK_ROTATE_NORMAL),
            (MODE_RECOVER_LOST_KEY, ROLE_MASK_RECOVER_LOST_KEY),
        )
        for mode, role_mask in cases:
            with self.subTest(mode=mode):
                base = _base(mode)
                base_raw = base.canonical_bytes()
                parsed_base = HeartbeatConsentBaseIntentV2.from_bytes(base_raw)
                self.assertEqual(parsed_base, base)
                self.assertEqual(parsed_base.canonical_bytes(), base_raw)
                self.assertEqual(base.digest, hashlib.sha256(base_raw).digest())

                witness = _witness(base)
                witness_raw = witness.canonical_bytes()
                parsed_witness = HeartbeatConsentWitnessV2.from_bytes(witness_raw)
                self.assertEqual(parsed_witness, witness)
                self.assertEqual(parsed_witness.canonical_bytes(), witness_raw)
                self.assertEqual(witness.digest, hashlib.sha256(witness_raw).digest())
                self.assertEqual(witness.required_role_mask, role_mask)
                self.assertTrue(witness.matches_base_data(base))
                self.assertFalse(witness.matches_base_data(_base(mode, consent_nonce=15)))

    def test_enrollment_and_replacement_compare_and_set_shapes(self) -> None:
        with self.assertRaises(HeartbeatConsentDataError):
            _base(MODE_ENROLL, expected_generation=1)
        with self.assertRaises(HeartbeatConsentDataError):
            _base(MODE_ENROLL, proposed_generation=2)
        with self.assertRaises(HeartbeatConsentDataError):
            _base(MODE_ENROLL, expected_record_digest=b"\x01" * 32)
        with self.assertRaises(HeartbeatConsentDataError):
            _base(MODE_RECOVER_LOST_KEY, proposed_generation=9)
        with self.assertRaises(HeartbeatConsentDataError):
            _base(MODE_ROTATE_NORMAL, expected_generation=(1 << 64) - 1, proposed_generation=0)

        for mode in (MODE_ROTATE_NORMAL, MODE_RECOVER_LOST_KEY):
            with self.subTest(zero_expected_digest_mode=mode):
                replacement = _base(mode, expected_record_digest=ZERO32)
                self.assertGreater(replacement.expected_generation, 0)
                self.assertEqual(replacement.proposed_generation, replacement.expected_generation + 1)
                self.assertEqual(
                    HeartbeatConsentBaseIntentV2.from_bytes(replacement.canonical_bytes()),
                    replacement,
                )

    def test_zero_opaque_digests_and_challenge_round_trip_without_authority(self) -> None:
        base = _base(
            MODE_ENROLL,
            authority_source_digest=ZERO32,
            authority_config_digest=ZERO32,
            proposed_record_digest=ZERO32,
        )
        base_raw = base.canonical_bytes()
        parsed_base = HeartbeatConsentBaseIntentV2.from_bytes(base_raw)
        self.assertEqual(parsed_base, base)
        self.assertEqual(parsed_base.digest, hashlib.sha256(base_raw).digest())
        self.assertEqual(parsed_base.authority_source_digest, ZERO32)
        self.assertEqual(parsed_base.authority_config_digest, ZERO32)
        self.assertEqual(parsed_base.proposed_record_digest, ZERO32)

        witness = _witness(base, post_eta_challenge_commitment=ZERO32)
        witness_raw = witness.canonical_bytes()
        parsed_witness = HeartbeatConsentWitnessV2.from_bytes(witness_raw)
        self.assertEqual(parsed_witness, witness)
        self.assertEqual(parsed_witness.digest, hashlib.sha256(witness_raw).digest())
        self.assertEqual(parsed_witness.post_eta_challenge_commitment, ZERO32)
        self.assertTrue(parsed_witness.matches_base_data(parsed_base))

        for mode in (MODE_ROTATE_NORMAL, MODE_RECOVER_LOST_KEY):
            with self.subTest(all_zero_opaque_replacement=mode):
                replacement = _base(
                    mode,
                    authority_source_digest=ZERO32,
                    authority_config_digest=ZERO32,
                    proposed_record_digest=ZERO32,
                    expected_record_digest=ZERO32,
                )
                encoded = replacement.canonical_bytes()
                self.assertEqual(HeartbeatConsentBaseIntentV2.from_bytes(encoded), replacement)
                self.assertEqual(replacement.digest, hashlib.sha256(encoded).digest())

    def test_rejects_unsupported_modes_schemes_booleans_and_integer_subclasses(self) -> None:
        class IntSubclass(int):
            pass

        invalid_bases = (
            {"mode": True},
            {"mode": 4},
            {"source_scheme": True},
            {"source_scheme": 2},
            {"authority_change_sequence": True},
            {"authority_change_sequence": IntSubclass(11)},
            {"policy_version": False},
            {"authority_epoch": -1},
            {"principal_id": bytearray(b"\x06" * 32)},
            {"timelock_address": b"\x00" * 20},
            {"timelock_code_hash": ZERO32},
            {"principal_id": ZERO32},
            {"policy_root": ZERO32},
            {"authority_source_digest": bytearray(32)},
            {"authority_config_digest": bytearray(32)},
            {"authority_config_digest": b"\x01" * 31},
            {"proposed_record_digest": b"\x01" * 33},
        )
        for changes in invalid_bases:
            with self.subTest(changes=changes), self.assertRaises(HeartbeatConsentDataError):
                _base(**changes)

    def test_base_frame_rejects_bad_domain_count_order_duplicate_width_truncation_and_trailing(self) -> None:
        raw = _base().canonical_bytes()
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(b"X" + raw[1:])
        v1_domain = raw.replace(b"CONSENT-BASE:v2", b"CONSENT-BASE:v1", 1)
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(v1_domain)
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(raw[:-1])
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(raw + b"\x00")
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(raw + bytes(MAX_ENCODING_BYTES + 1))

        offset = _first_field_offset(BASE_DOMAIN)
        duplicate = bytearray(raw)
        duplicate[offset + 4] = 1
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(bytes(duplicate))

        unknown = bytearray(raw)
        unknown[offset] = 0xFF
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(bytes(unknown))

        reordered = bytearray(raw)
        reordered[offset] = 2
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(bytes(reordered))

        bad_width = bytearray(raw)
        bad_width[offset + 1:offset + 3] = b"\x00\x00"
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(bytes(bad_width))

        bad_count = bytearray(raw)
        bad_count[len(BASE_DOMAIN) + 1] -= 1
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentBaseIntentV2.from_bytes(bytes(bad_count))

    def test_witness_rejects_wrong_mode_role_mask_and_inconsistent_times(self) -> None:
        base = _base(MODE_ROTATE_NORMAL)
        exact_eta = _witness(base, queued_eta=2_000, issued_at=2_000, expires_at=2_001)
        self.assertEqual(HeartbeatConsentWitnessV2.from_bytes(exact_eta.canonical_bytes()), exact_eta)
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, mode=MODE_ENROLL)
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, required_role_mask=ROLE_MASK_ENROLL)
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, required_role_mask=True)
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, queued_eta=True)
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, issued_at=1_899)
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, expires_at=2_000)
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, required_role_mask=0x07)
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, post_eta_challenge_commitment=bytearray(32))
        with self.assertRaises(HeartbeatConsentDataError):
            _witness(base, post_eta_challenge_commitment=b"\x0b" * 31)

    def test_witness_frame_rejects_bad_domain_field_order_truncation_and_trailing(self) -> None:
        raw = _witness(_base()).canonical_bytes()
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentWitnessV2.from_bytes(b"X" + raw[1:])
        v1_domain = raw.replace(b"CONSENT-WITNESS:v2", b"CONSENT-WITNESS:v1", 1)
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentWitnessV2.from_bytes(v1_domain)
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentWitnessV2.from_bytes(raw[:-1])
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentWitnessV2.from_bytes(raw + b"\x00")

        offset = _first_field_offset(WITNESS_DOMAIN)
        reordered = bytearray(raw)
        reordered[offset] = 2
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentWitnessV2.from_bytes(bytes(reordered))

        unknown = bytearray(raw)
        unknown[offset] = 0xFF
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentWitnessV2.from_bytes(bytes(unknown))

        bad_width = bytearray(raw)
        bad_width[offset + 1:offset + 3] = b"\x00\x1f"
        with self.assertRaises(HeartbeatConsentDataError):
            HeartbeatConsentWitnessV2.from_bytes(bytes(bad_width))

    def test_witness_digests_are_domain_and_field_sensitive_and_not_signatures(self) -> None:
        base = _base()
        witness = _witness(base)
        self.assertNotEqual(base.digest, witness.digest)
        self.assertNotEqual(witness.digest, replace(witness, operation_id=b"\x0c" * 32).digest)
        witness_fields = {item.name for item in fields(witness)}
        self.assertNotIn("signature", witness_fields)
        self.assertNotIn("old_signature", witness_fields)

    def test_total_encoding_cap_at_1024_and_1025_bytes(self) -> None:
        base_raw = _base().canonical_bytes()
        witness_raw = _witness(_base()).canonical_bytes()
        self.assertEqual(MAX_ENCODING_BYTES, 1024)
        self.assertLess(len(base_raw), MAX_ENCODING_BYTES)
        self.assertLess(len(witness_raw), MAX_ENCODING_BYTES)

        for raw, decoder, label in (
            (base_raw, HeartbeatConsentBaseIntentV2.from_bytes, "base"),
            (witness_raw, HeartbeatConsentWitnessV2.from_bytes, "witness"),
        ):
            for target in (1024, 1025):
                with self.subTest(kind=label, total_length=target):
                    malformed = raw + bytes(target - len(raw))
                    self.assertEqual(len(malformed), target)
                    with self.assertRaises(HeartbeatConsentDataError):
                        decoder(malformed)


if __name__ == "__main__":
    unittest.main()
