"""Stdlib boundary tests for the unsigned heartbeat payload v2 codec."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import struct
import unittest

from gateway.heartbeat_payload_v2 import (
    HeartbeatPayloadDataError,
    MAX_M2_TIMESTAMP,
    MAX_NODE_ID_BYTES,
    MAX_OBSERVATIONS_BYTES,
    MAX_PAYLOAD_BYTES,
    MAX_PAYLOAD_TEXT_CHARS,
    OBSERVATIONS_DOMAIN,
    PAYLOAD_DOMAIN,
    PAYLOAD_TEXT_PREFIX,
    HeartbeatObservationsV1,
    HeartbeatPayloadV2,
)
from gateway.heartbeat_principal_v1 import (
    HeartbeatPrincipalV1,
    node_id_commitment,
    principal_id_commitment,
)


HOST_DOMAIN = b"\x05" * 32
SERVICE_DOMAIN = b"\x06" * 32
AUTHORITY_DIGEST = b"\x0a" * 32
OUTER_NONCE = b"\x0b" * 16
ISSUED_AT = 1_800_000_000
EXPIRES_AT = ISSUED_AT + 300
NODE_ID = "fixture-node-A"


def _principal(
    *,
    node_id: str = NODE_ID,
    host_domain: bytes = HOST_DOMAIN,
    service_domain: bytes = SERVICE_DOMAIN,
    body_public_key: bytes = bytes(range(64)),
    policy_root: bytes = b"\x07" * 32,
    policy_version: int = 3,
    authority_epoch: int = 4,
    principal_generation: int = 5,
) -> HeartbeatPrincipalV1:
    signer_key = bytes(range(1, 65))
    node_commitment = node_id_commitment(
        node_id, host_domain=host_domain, service_domain=service_domain
    )
    return HeartbeatPrincipalV1(
        principal_id=principal_id_commitment(
            host_domain=host_domain,
            service_domain=service_domain,
            node_id_commitment=node_commitment,
        ),
        node_id_commitment=node_commitment,
        m2_signer_did="did:key:" + signer_key.hex(),
        m2_signer_public_key=signer_key,
        certificate_fingerprint=b"\x08" * 32,
        body_public_key=body_public_key,
        host_domain=host_domain,
        service_domain=service_domain,
        audience="gateway-test",
        method="POST",
        path="/heartbeat",
        query=b"",
        policy_root=policy_root,
        policy_version=policy_version,
        authority_epoch=authority_epoch,
        principal_generation=principal_generation,
        not_before=0,
        expires_at=MAX_M2_TIMESTAMP,
    )


def _observations(**changes: object) -> HeartbeatObservationsV1:
    values: dict[str, object] = {"block_height": 42}
    values.update(changes)
    return HeartbeatObservationsV1(**values)


def _payload(
    *,
    node_id: str = NODE_ID,
    observations: HeartbeatObservationsV1 | None = None,
    body_public_key: bytes = bytes(range(64)),
    authority_source_digest: bytes = AUTHORITY_DIGEST,
    principal_digest: bytes | None = None,
    principal_id: bytes | None = None,
    principal_generation: int = 5,
    policy_root: bytes = b"\x07" * 32,
    policy_version: int = 3,
    authority_epoch: int = 4,
    m2_nonce: bytes = OUTER_NONCE,
    m2_issued_at: int = ISSUED_AT,
    m2_expires_at: int = EXPIRES_AT,
) -> HeartbeatPayloadV2:
    record = _principal(
        node_id=node_id,
        body_public_key=body_public_key,
        principal_generation=principal_generation,
        policy_root=policy_root,
        policy_version=policy_version,
        authority_epoch=authority_epoch,
    )
    return HeartbeatPayloadV2(
        authority_source_digest=authority_source_digest,
        principal_digest=record.digest if principal_digest is None else principal_digest,
        principal_id=record.principal_id if principal_id is None else principal_id,
        principal_generation=principal_generation,
        policy_root=policy_root,
        policy_version=policy_version,
        authority_epoch=authority_epoch,
        node_id=node_id,
        body_public_key=body_public_key,
        m2_nonce=m2_nonce,
        m2_issued_at=m2_issued_at,
        m2_expires_at=m2_expires_at,
        observations_v1=observations or _observations(),
    )


def _frame(domain: bytes, fields: list[tuple[int, bytes]]) -> bytes:
    result = bytearray(domain)
    result.extend(len(fields).to_bytes(2, "big"))
    for field_id, value in fields:
        result.append(field_id)
        result.extend(len(value).to_bytes(2, "big"))
        result.extend(value)
    return bytes(result)


def _fields(raw: bytes, domain: bytes) -> list[tuple[int, bytes]]:
    offset = len(domain) + 2
    count = int.from_bytes(raw[len(domain):offset], "big")
    result = []
    for _ in range(count):
        field_id = raw[offset]
        length = int.from_bytes(raw[offset + 1:offset + 3], "big")
        offset += 3
        result.append((field_id, raw[offset:offset + length]))
        offset += length
    return result


class HeartbeatPayloadV2Tests(unittest.TestCase):
    def test_payload_round_trip_text_digest_and_structural_record_match(self) -> None:
        record = _principal()
        payload = _payload(observations=_observations(region="west", skills=("swap",)))
        raw = payload.canonical_bytes()
        text = payload.payload_text

        self.assertEqual(HeartbeatPayloadV2.from_bytes(raw), payload)
        self.assertEqual(HeartbeatPayloadV2.from_payload_text(text), payload)
        self.assertTrue(text.startswith(PAYLOAD_TEXT_PREFIX))
        self.assertEqual(payload.digest, hashlib.sha256(text.encode("ascii")).digest())
        self.assertEqual(payload.canonical_binary_digest, hashlib.sha256(raw).digest())
        self.assertNotEqual(payload.digest, payload.canonical_binary_digest)
        self.assertTrue(payload.matches_record_data(
            record, AUTHORITY_DIGEST, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))

    def test_record_data_match_rejects_each_snapshot_or_envelope_mismatch(self) -> None:
        payload = _payload()
        record = _principal()
        self.assertFalse(payload.matches_record_data(
            record, b"\x09" * 32, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))
        self.assertFalse(payload.matches_record_data(
            record, AUTHORITY_DIGEST, b"\x0c" * 16, ISSUED_AT, EXPIRES_AT
        ))
        self.assertFalse(payload.matches_record_data(
            record, AUTHORITY_DIGEST, OUTER_NONCE, ISSUED_AT + 1, EXPIRES_AT + 1
        ))
        changed_record = _principal(policy_root=b"\x0d" * 32)
        self.assertFalse(payload.matches_record_data(
            changed_record, AUTHORITY_DIGEST, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))
        self.assertFalse(payload.matches_record_data(
            object(), AUTHORITY_DIGEST, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))

    def test_record_match_recomputes_exact_raw_node_commitment_and_scoped_id(self) -> None:
        payload = _payload()
        other_node_record = _principal(node_id="fixture-node-B")
        self.assertFalse(payload.matches_record_data(
            other_node_record, AUTHORITY_DIGEST, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))
        other_node_payload = _payload(node_id="fixture-node-B")
        self.assertFalse(other_node_payload.matches_record_data(
            _principal(), AUTHORITY_DIGEST, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))

    def test_updates_omit_none_and_preserve_present_empty_values(self) -> None:
        omitted = _observations()
        self.assertEqual(omitted.to_updates(), {"block_height": 42})

        present = _observations(
            region="",
            passports="",
            skills=(),
            cognitive_profile=(),
        )
        updates = present.to_updates()
        self.assertEqual(updates, {
            "block_height": 42,
            "region": "",
            "passports": "",
            "skills": [],
            "cognitive_profile": {},
        })
        updates["skills"].append("local mutation")
        updates["cognitive_profile"]["x"] = 1.0
        self.assertEqual(present.to_updates()["skills"], [])
        self.assertEqual(present.to_updates()["cognitive_profile"], {})

    def test_node_id_validation_is_exact_and_bounded(self) -> None:
        for node_id in ("", "a" * (MAX_NODE_ID_BYTES + 1), "a\x00b", "a\x7fb", "\ud800"):
            with self.subTest(node_id=repr(node_id)):
                with self.assertRaises(HeartbeatPayloadDataError):
                    replace(_payload(), node_id=node_id)
        accepted = _payload(node_id="é" * 128)
        self.assertEqual(len(accepted.node_id.encode("utf-8")), MAX_NODE_ID_BYTES)
        self.assertEqual(
            HeartbeatPayloadV2.from_bytes(accepted.canonical_bytes()).node_id,
            accepted.node_id,
        )
        composed = _payload(node_id="é")
        decomposed = _payload(node_id="e\u0301")
        self.assertNotEqual(composed.canonical_bytes(), decomposed.canonical_bytes())

    def test_fixed_identity_types_and_key_shape_only(self) -> None:
        base = _payload()
        for name, value in (
            ("authority_source_digest", bytearray(AUTHORITY_DIGEST)),
            ("authority_source_digest", b"\x01" * 31),
            ("principal_digest", bytearray(b"\x01" * 32)),
            ("principal_digest", b"\x01" * 31),
            ("principal_id", b"\x00" * 32),
            ("policy_root", b"\x00" * 32),
            ("m2_nonce", b"\x00" * 16),
            ("body_public_key", b"\x01" * 63),
        ):
            with self.subTest(field=name, value=repr(value)[:20]):
                with self.assertRaises(HeartbeatPayloadDataError):
                    replace(base, **{name: value})
        # The pure codec checks the public key's wire shape, not its curve point.
        structural_only_key = replace(base, body_public_key=b"\x00" * 64)
        self.assertEqual(structural_only_key.body_public_key, b"\x00" * 64)

    def test_zero_opaque_digests_are_valid_data_not_authority_sentinels(self) -> None:
        record = _principal()
        zero_fields = _payload(
            authority_source_digest=b"\x00" * 32,
            principal_digest=b"\x00" * 32,
        )
        self.assertEqual(
            HeartbeatPayloadV2.from_bytes(zero_fields.canonical_bytes()),
            zero_fields,
        )
        self.assertFalse(zero_fields.matches_record_data(
            record, b"\x00" * 32, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))

        zero_source = _payload(authority_source_digest=b"\x00" * 32)
        self.assertTrue(zero_source.matches_record_data(
            record, b"\x00" * 32, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))
        # This method only reports equality of supplied data; neither the
        # record nor the payload exposes an authority/approval result.
        self.assertFalse(hasattr(zero_source, "is_authorized"))

    def test_integer_ranges_and_outer_m2_timestamp_limits(self) -> None:
        for name, value in (
            ("principal_generation", 0),
            ("principal_generation", True),
            ("policy_version", 1 << 64),
            ("authority_epoch", -1),
            ("m2_issued_at", True),
            ("m2_issued_at", MAX_M2_TIMESTAMP + 1),
            ("m2_expires_at", MAX_M2_TIMESTAMP + 1),
            ("m2_expires_at", ISSUED_AT),
            ("m2_expires_at", ISSUED_AT + 301),
        ):
            with self.subTest(field=name, value=value):
                with self.assertRaises(HeartbeatPayloadDataError):
                    replace(_payload(), **{name: value})
        self.assertEqual(_payload(m2_issued_at=0, m2_expires_at=300).m2_expires_at, 300)

    def test_observation_numeric_types_and_finite_float_canonicality(self) -> None:
        valid = _observations(
            cost_per_hour=12,
            credit_score=750,
            cognitive_profile=(("M", 0.5),),
        )
        self.assertEqual(HeartbeatObservationsV1.from_bytes(valid.canonical_bytes()), valid)
        for kwargs in (
            {"block_height": True},
            {"cost_per_hour": True},
            {"cost_per_hour": float("nan")},
            {"cost_per_hour": float("inf")},
            {"credit_score": 750.0},
            {"credit_score": 1 << 63},
            {"cognitive_profile": (("M", False),)},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(HeartbeatPayloadDataError):
                    _observations(**kwargs)

        for negative_zero_observations in (
            _observations(cost_per_hour=-0.0),
            _observations(cognitive_profile=(("M", -0.0),)),
        ):
            round_trip = HeartbeatObservationsV1.from_bytes(
                negative_zero_observations.canonical_bytes()
            )
            self.assertEqual(round_trip, negative_zero_observations)
            if round_trip.cost_per_hour is not None:
                self.assertEqual(
                    struct.pack(">d", round_trip.cost_per_hour),
                    bytes.fromhex("8000000000000000"),
                )
            if round_trip.cognitive_profile is not None:
                self.assertEqual(
                    struct.pack(">d", round_trip.cognitive_profile[0][1]),
                    bytes.fromhex("8000000000000000"),
                )

    def test_zero_numeric_representations_have_distinct_wire_digests(self) -> None:
        integer_zero = _payload(observations=_observations(cost_per_hour=0))
        positive_zero = _payload(observations=_observations(cost_per_hour=0.0))
        negative_zero = _payload(observations=_observations(cost_per_hour=-0.0))

        self.assertEqual(integer_zero.observations_v1.cost_per_hour, 0)
        self.assertEqual(positive_zero.observations_v1.cost_per_hour, 0.0)
        self.assertEqual(negative_zero.observations_v1.cost_per_hour, 0.0)
        self.assertNotEqual(integer_zero.canonical_bytes(), positive_zero.canonical_bytes())
        self.assertNotEqual(positive_zero.canonical_bytes(), negative_zero.canonical_bytes())
        self.assertNotEqual(integer_zero.digest, positive_zero.digest)
        self.assertNotEqual(positive_zero.digest, negative_zero.digest)
        self.assertNotEqual(integer_zero.digest, negative_zero.digest)
        self.assertNotEqual(
            positive_zero.canonical_binary_digest,
            negative_zero.canonical_binary_digest,
        )

        decoded = HeartbeatPayloadV2.from_bytes(negative_zero.canonical_bytes())
        self.assertEqual(
            struct.pack(">d", decoded.observations_v1.cost_per_hour),
            bytes.fromhex("8000000000000000"),
        )

    def test_observation_text_and_tuple_bounds(self) -> None:
        accepted = _observations(
            region="r" * 256,
            passports="p" * 256,
            skills=tuple("s" * 64 for _ in range(32)),
            cognitive_profile=tuple((f"{i:02}", i) for i in range(64)),
        )
        self.assertLessEqual(len(accepted.canonical_bytes()), MAX_OBSERVATIONS_BYTES)
        self.assertEqual(HeartbeatObservationsV1.from_bytes(accepted.canonical_bytes()), accepted)

        for kwargs in (
            {"region": "r" * 257},
            {"passports": "p" * 257},
            {"skills": ["not", "a", "tuple"]},
            {"skills": tuple("s" * 65 for _ in range(1))},
            {"skills": tuple("s" for _ in range(33))},
            {"cognitive_profile": (("b", 1), ("a", 2))},
            {"cognitive_profile": (("a", 1), ("a", 2))},
            {"cognitive_profile": (("k" * 65, 1),)},
        ):
            with self.subTest(kwargs=repr(kwargs)[:70]):
                with self.assertRaises(HeartbeatPayloadDataError):
                    _observations(**kwargs)

    def test_maximum_valid_aggregate_records_fit_below_guards(self) -> None:
        profile = tuple((f"{i:02}" + "a" * 62, i) for i in range(53))
        observations = _observations(
            block_height=(1 << 64) - 1,
            cognitive_profile=profile,
        )
        observation_bytes = observations.canonical_bytes()
        self.assertLessEqual(len(observation_bytes), MAX_OBSERVATIONS_BYTES)
        self.assertGreater(len(observation_bytes), MAX_OBSERVATIONS_BYTES - 128)

        payload = _payload(
            node_id="n" * MAX_NODE_ID_BYTES,
            observations=observations,
        )
        payload_bytes = payload.canonical_bytes()
        self.assertLessEqual(len(payload_bytes), MAX_PAYLOAD_BYTES)
        self.assertEqual(HeartbeatPayloadV2.from_bytes(payload_bytes), payload)
        with self.assertRaises(HeartbeatPayloadDataError):
            _observations(cognitive_profile=tuple(
                (f"{i:02}" + "a" * 62, i) for i in range(54)
            )).canonical_bytes()

    def test_observation_decoder_preserves_negative_zero_and_rejects_wrong_tags_and_trailing_data(self) -> None:
        observation = _observations(cost_per_hour=1.0, credit_score=2)
        fields = _fields(observation.canonical_bytes(), OBSERVATIONS_DOMAIN)
        cost = next(value for field_id, value in fields if field_id == 3)
        bad_negative_zero = bytes((2,)) + struct.pack(">d", -0.0)
        negative_zero_fields = [(field_id, bad_negative_zero if field_id == 3 else value)
                                for field_id, value in fields]
        decoded_negative_zero = HeartbeatObservationsV1.from_bytes(
            _frame(OBSERVATIONS_DOMAIN, negative_zero_fields)
        )
        self.assertEqual(
            struct.pack(">d", decoded_negative_zero.cost_per_hour),
            bytes.fromhex("8000000000000000"),
        )
        for bad in (
            observation.canonical_bytes() + b"\x00",
            _frame(OBSERVATIONS_DOMAIN, [(1, b"\x00" * 7), *fields[1:]]),
            _frame(OBSERVATIONS_DOMAIN, [(1, fields[0][1]), (9, cost)]),
        ):
            with self.subTest(size=len(bad)):
                with self.assertRaises(HeartbeatPayloadDataError):
                    HeartbeatObservationsV1.from_bytes(bad)

        bad_credit = [(field_id, b"\x02" + b"\x00" * 8 if field_id == 4 else value)
                      for field_id, value in fields]
        with self.assertRaises(HeartbeatPayloadDataError):
            HeartbeatObservationsV1.from_bytes(_frame(OBSERVATIONS_DOMAIN, bad_credit))

        ordered_fields = _fields(
            _observations(region="x", passports="y").canonical_bytes(),
            OBSERVATIONS_DOMAIN,
        )
        nested_bad = (
            _frame(OBSERVATIONS_DOMAIN, [ordered_fields[0], ordered_fields[2], ordered_fields[1]]),
            _frame(OBSERVATIONS_DOMAIN, [ordered_fields[0], (2, b"\xff")]),
        )
        for bad in nested_bad:
            with self.subTest(nested_size=len(bad)):
                with self.assertRaises(HeartbeatPayloadDataError):
                    HeartbeatObservationsV1.from_bytes(bad)

        profile = _observations(cognitive_profile=(("a", 1), ("b", 2)))
        profile_fields = _fields(profile.canonical_bytes(), OBSERVATIONS_DOMAIN)
        duplicate_key = (
            b"\x02"
            + b"\x00\x01a\x01" + (1).to_bytes(8, "big", signed=True)
            + b"\x00\x01a\x01" + (2).to_bytes(8, "big", signed=True)
        )
        malformed_profile = [(field_id, duplicate_key if field_id == 7 else value)
                             for field_id, value in profile_fields]
        with self.assertRaises(HeartbeatPayloadDataError):
            HeartbeatObservationsV1.from_bytes(_frame(OBSERVATIONS_DOMAIN, malformed_profile))

    def test_payload_decoder_rejects_noncanonical_frame_and_text(self) -> None:
        payload = _payload()
        raw = payload.canonical_bytes()
        fields = _fields(raw, PAYLOAD_DOMAIN)
        malformed = (
            _frame(PAYLOAD_DOMAIN, [(fields[0][0], fields[0][1]), (fields[0][0], fields[1][1]), *fields[2:]]),
            _frame(PAYLOAD_DOMAIN, [fields[1], fields[0], *fields[2:]]),
            _frame(PAYLOAD_DOMAIN, [*fields[:-1], (14, fields[-1][1])]),
            raw + b"\x00",
            raw[:-1],
            _frame(PAYLOAD_DOMAIN, [*fields[:7], (8, b"\xff"), *fields[8:]]),
            _frame(PAYLOAD_DOMAIN, [*fields[:1], (2, b"\x00" * 31), *fields[2:]]),
        )
        for bad in malformed:
            with self.subTest(size=len(bad)):
                with self.assertRaises(HeartbeatPayloadDataError):
                    HeartbeatPayloadV2.from_bytes(bad)

        text = payload.payload_text
        hex_part = text[len(PAYLOAD_TEXT_PREFIX):]
        with self.assertRaises(HeartbeatPayloadDataError):
            HeartbeatPayloadV2.from_payload_text(PAYLOAD_TEXT_PREFIX + hex_part.upper())
        with self.assertRaises(HeartbeatPayloadDataError):
            HeartbeatPayloadV2.from_payload_text("VAMS-HB3:" + hex_part)
        with self.assertRaises(HeartbeatPayloadDataError):
            HeartbeatPayloadV2.from_payload_text(text + "0")
        with self.assertRaises(HeartbeatPayloadDataError):
            HeartbeatPayloadV2.from_payload_text(
                PAYLOAD_TEXT_PREFIX + "00" * (MAX_PAYLOAD_BYTES + 1)
            )
        with self.assertRaises(HeartbeatPayloadDataError):
            HeartbeatPayloadV2.from_bytes(b"\x00" * (MAX_PAYLOAD_BYTES + 1))
        self.assertLessEqual(len(text), MAX_PAYLOAD_TEXT_CHARS)

    def test_principal_digest_uses_exact_canonical_record(self) -> None:
        record = _principal()
        payload = _payload()
        self.assertEqual(payload.principal_digest, hashlib.sha256(record.canonical_bytes()).digest())
        changed = replace(payload, principal_digest=b"\x0f" * 32)
        self.assertFalse(changed.matches_record_data(
            record, AUTHORITY_DIGEST, OUTER_NONCE, ISSUED_AT, EXPIRES_AT
        ))


if __name__ == "__main__":
    unittest.main()
