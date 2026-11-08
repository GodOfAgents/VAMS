"""Pure data-contract regressions; never tests production authority."""

from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path
import unittest

from gateway.heartbeat_principal_v1 import (
    DOMAIN,
    FIELD_COUNT,
    MAX_ENCODING_BYTES,
    PRINCIPAL_FIELD_ORDER,
    HeartbeatPrincipalDataError,
    HeartbeatPrincipalV1,
    node_id_commitment,
    principal_id_commitment,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "heartbeat-principal-v1.json"
BYTE_FIELDS = {
    "principal_id",
    "node_id_commitment",
    "m2_signer_public_key",
    "certificate_fingerprint",
    "body_public_key",
    "host_domain",
    "service_domain",
    "query",
    "policy_root",
}
TEXT_FIELDS = {"m2_signer_did", "audience", "method", "path"}
INTEGER_FIELDS = {
    "policy_version",
    "authority_epoch",
    "principal_generation",
    "not_before",
    "expires_at",
}


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _value(spec):
    encoding = spec["encoding"]
    if encoding == "repeat_byte":
        return bytes.fromhex(spec["byte"]) * spec["length"]
    if encoding == "hex":
        return bytes.fromhex(spec["value"])
    if encoding == "ascii":
        return spec["value"]
    if encoding == "did_key":
        return "did:key:" + spec["byte"] * spec["public_key_bytes"]
    if encoding == "uint64":
        return spec["value"]
    raise AssertionError("unknown frozen fixture encoding")


def _principal_from_fixture(fixture=None):
    fixture = fixture or _fixture()
    kwargs = {spec["name"]: _value(spec) for spec in fixture["fields"]}
    for name in BYTE_FIELDS:
        kwargs[name] = bytes(kwargs[name])
    return HeartbeatPrincipalV1(**kwargs)


def _frozen_encoding(fixture):
    result = bytearray(fixture["domain_ascii"].encode("ascii") + b"\x00")
    result.extend(fixture["field_count"].to_bytes(2, "big"))
    for spec in fixture["fields"]:
        value = _value(spec)
        if spec["name"] in BYTE_FIELDS:
            value = bytes(value)
        elif spec["name"] in {"m2_signer_did", "audience", "method", "path"}:
            value = value.encode("ascii")
        elif spec["name"] in INTEGER_FIELDS:
            value = value.to_bytes(8, "big")
        else:
            raise AssertionError("fixture field lacks an explicit encoding")
        result.append(spec["id"])
        result.extend(len(value).to_bytes(2, "big"))
        result.extend(value)
    return bytes(result)


class HeartbeatPrincipalV1DataTests(unittest.TestCase):
    def test_frozen_versioned_serialization_vector_and_digest(self):
        fixture = _fixture()
        principal = _principal_from_fixture(fixture)
        expected = _frozen_encoding(fixture)
        self.assertEqual(DOMAIN, fixture["domain_ascii"].encode("ascii") + b"\x00")
        self.assertEqual(FIELD_COUNT, fixture["field_count"])
        self.assertEqual(
            tuple(spec["name"] for spec in fixture["fields"]),
            PRINCIPAL_FIELD_ORDER,
        )
        self.assertEqual(principal.canonical_bytes(), expected)
        self.assertLessEqual(len(expected), MAX_ENCODING_BYTES)
        self.assertEqual(principal.digest, hashlib.sha256(expected).digest())
        self.assertEqual(HeartbeatPrincipalV1.from_bytes(expected), principal)

    def test_strict_decoder_rejects_truncation_trailing_alternative_order_and_count(self):
        fixture = _fixture()
        raw = _frozen_encoding(fixture)
        self.assertGreater(len(raw), 0)
        prefix = len(DOMAIN) + 2
        records = []
        offset = prefix
        for _ in range(FIELD_COUNT):
            length = int.from_bytes(raw[offset + 1:offset + 3], "big")
            end = offset + 3 + length
            records.append(raw[offset:end])
            offset = end
        self.assertEqual(offset, len(raw))
        malformed = (
            raw[:-1],
            raw + b"\x00",
            b"\x00" * (MAX_ENCODING_BYTES + 1),
            raw[:len(DOMAIN)] + (FIELD_COUNT - 1).to_bytes(2, "big") + raw[prefix:],
            raw[:prefix] + records[1] + records[0] + b"".join(records[2:]),
            bytes([raw[0] ^ 1]) + raw[1:],
        )
        for candidate in malformed:
            with self.subTest(length=len(candidate)):
                with self.assertRaises(HeartbeatPrincipalDataError):
                    HeartbeatPrincipalV1.from_bytes(candidate)

    def test_strict_field_types_and_route_scope(self):
        principal = _principal_from_fixture()
        invalid = (
            {"policy_version": True},
            {"authority_epoch": False},
            {"expires_at": principal.not_before},
            {"expires_at": 1 << 64},
            {"body_public_key": "04" * 64},
            {"m2_signer_did": "did:key:" + "A1" * 64},
            {"m2_signer_did": "did:web:example.invalid"},
            {"audience": "Gateway.testnet"},
            {"method": "GET"},
            {"path": "/heartbeat/"},
            {"query": b"?x=1"},
            {"policy_root": b"\x00" * 32},
            {"certificate_fingerprint": b"\x00" * 32},
        )
        for changes in invalid:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaises(HeartbeatPrincipalDataError):
                    replace(principal, **changes)

    def test_m2_did_and_audience_match_existing_lexical_constraints(self):
        fixture = _fixture()
        principal = _principal_from_fixture(fixture)
        accepted = replace(
            principal,
            audience="a" + "b" * 126 + "c",
        )
        self.assertEqual(len(accepted.audience), 128)
        for audience in ("", "-edge", "edge-", "edge_​", "a" + "b" * 127 + "c"):
            with self.subTest(audience=audience[:20]):
                with self.assertRaises(HeartbeatPrincipalDataError):
                    replace(principal, audience=audience)
        for signer in (
            "did:key:" + "1" * 127,
            "did:key:" + "1" * 129,
            "did:key:" + "1" * 126 + "gg",
        ):
            with self.subTest(signer_length=len(signer)):
                with self.assertRaises(HeartbeatPrincipalDataError):
                    replace(principal, m2_signer_did=signer)

    def test_exact_node_id_commitment_and_no_implicit_normalization(self):
        host = bytes.fromhex("05" * 32)
        service = bytes.fromhex("06" * 32)
        self.assertEqual(
            node_id_commitment("node-α", host_domain=host, service_domain=service),
            node_id_commitment("node-α", host_domain=host, service_domain=service),
        )
        self.assertNotEqual(
            node_id_commitment("node", host_domain=host, service_domain=service),
            node_id_commitment(" node", host_domain=host, service_domain=service),
        )
        self.assertNotEqual(
            node_id_commitment("é", host_domain=host, service_domain=service),
            node_id_commitment("e\u0301", host_domain=host, service_domain=service),
        )
        with self.assertRaises(HeartbeatPrincipalDataError):
            node_id_commitment("node\nline", host_domain=host, service_domain=service)
        with self.assertRaises(HeartbeatPrincipalDataError):
            node_id_commitment("x" * 257, host_domain=host, service_domain=service)
        self.assertEqual(len(node_id_commitment("x" * 256, host_domain=host, service_domain=service)), 32)
        private_invalid_text = "id\ud800marker"
        try:
            node_id_commitment(private_invalid_text, host_domain=host, service_domain=service)
        except HeartbeatPrincipalDataError as exc:
            self.assertEqual(str(exc), "invalid node ID")
            self.assertIsNone(exc.__cause__)
            self.assertNotIn("marker", str(exc))
        else:
            self.fail("invalid Unicode node ID was accepted")

    def test_request_binding_matches_only_exact_identity_and_route_tuple(self):
        principal = _principal_from_fixture()
        node_id = _fixture()["node_id"]
        args = dict(
            node_id=node_id,
            m2_signer_did=principal.m2_signer_did,
            m2_signer_public_key=principal.m2_signer_public_key,
            certificate_fingerprint=principal.certificate_fingerprint,
            body_public_key=principal.body_public_key,
            host_domain=principal.host_domain,
            service_domain=principal.service_domain,
            audience=principal.audience,
            method=b"POST",
            raw_path=b"/heartbeat",
            raw_query=b"",
        )
        self.assertTrue(principal.matches_request_binding(**args))
        for name, value in (
            ("node_id", "another-node"),
            ("m2_signer_did", "did:key:" + "2" * 128),
            ("m2_signer_public_key", b"\x22" * 64),
            ("certificate_fingerprint", b"\x23" * 32),
            ("body_public_key", b"\x24" * 64),
            ("host_domain", b"\x25" * 32),
            ("service_domain", b"\x26" * 32),
            ("audience", "other.testnet"),
            ("method", b"GET"),
            ("raw_path", b"/nodes"),
            ("raw_query", b"?x=1"),
        ):
            changed = dict(args)
            changed[name] = value
            with self.subTest(field=name):
                self.assertFalse(principal.matches_request_binding(**changed))

    def test_request_binding_rejects_non_bytes_and_hostile_equality_objects(self):
        principal = _principal_from_fixture()
        node_id = _fixture()["node_id"]
        good = dict(
            node_id=node_id,
            m2_signer_did=principal.m2_signer_did,
            m2_signer_public_key=principal.m2_signer_public_key,
            certificate_fingerprint=principal.certificate_fingerprint,
            body_public_key=principal.body_public_key,
            host_domain=principal.host_domain,
            service_domain=principal.service_domain,
            audience=principal.audience,
            method=b"POST",
            raw_path=b"/heartbeat",
            raw_query=b"",
        )

        class EqualsEverything:
            def __eq__(self, _other):
                return True

        malformed = (
            {"certificate_fingerprint": bytearray(good["certificate_fingerprint"])},
            {"body_public_key": memoryview(good["body_public_key"])},
            {"host_domain": bytearray(good["host_domain"])},
            {"service_domain": memoryview(good["service_domain"])},
            {"m2_signer_public_key": bytearray(good["m2_signer_public_key"])},
            {"method": bytearray(b"POST")},
            {"raw_path": memoryview(b"/heartbeat")},
            {"raw_query": bytearray()},
            {"certificate_fingerprint": EqualsEverything()},
            {"body_public_key": EqualsEverything()},
            {"method": EqualsEverything()},
            {"raw_path": EqualsEverything()},
            {"raw_query": EqualsEverything()},
        )
        for change in malformed:
            candidate = dict(good)
            candidate.update(change)
            with self.subTest(field=next(iter(change))):
                self.assertFalse(principal.matches_request_binding(**candidate))

    def test_scoped_principal_id_stays_stable_across_key_rotation_only(self):
        fixture = _fixture()
        principal = _principal_from_fixture(fixture)
        host = principal.host_domain
        service = principal.service_domain
        node = fixture["node_id"]
        expected_node = bytes.fromhex(
            "79121d7d912632aaf935e2b08d31942fa6c2242e3d17dd751612188321f6d26d"
        )
        expected_principal = bytes.fromhex(
            "5d3ece6d8181af33a7e09b213d73e8fce828f1fc2ea2a4291b89a1699a02e918"
        )
        self.assertEqual(
            node_id_commitment(node, host_domain=host, service_domain=service),
            expected_node,
        )
        self.assertEqual(principal.node_id_commitment, expected_node)
        self.assertEqual(
            principal_id_commitment(
                host_domain=host,
                service_domain=service,
                node_id_commitment=expected_node,
            ),
            expected_principal,
        )
        self.assertEqual(principal.principal_id, expected_principal)

        rotated = replace(
            principal,
            m2_signer_did="did:key:" + "22" * 64,
            m2_signer_public_key=b"\x22" * 64,
            certificate_fingerprint=b"\x33" * 32,
            body_public_key=b"\x44" * 64,
            policy_root=b"\x08" * 32,
            policy_version=4,
            authority_epoch=12,
            principal_generation=3,
            not_before=1700000400,
            expires_at=1700000700,
        )
        self.assertEqual(rotated.principal_id, principal.principal_id)
        self.assertNotEqual(
            node_id_commitment("fixture-node-B", host_domain=host, service_domain=service),
            principal.node_id_commitment,
        )
        other_host = b"\x0a" * 32
        other_host_node = node_id_commitment(
            node, host_domain=other_host, service_domain=service
        )
        other_host_principal = principal_id_commitment(
            host_domain=other_host,
            service_domain=service,
            node_id_commitment=other_host_node,
        )
        self.assertNotEqual(other_host_node, principal.node_id_commitment)
        self.assertNotEqual(other_host_principal, principal.principal_id)
        other_service = b"\x09" * 32
        other_node_commitment = node_id_commitment(
            node, host_domain=host, service_domain=other_service
        )
        other_principal_id = principal_id_commitment(
            host_domain=host,
            service_domain=other_service,
            node_id_commitment=other_node_commitment,
        )
        self.assertNotEqual(other_node_commitment, principal.node_id_commitment)
        self.assertNotEqual(other_principal_id, principal.principal_id)
        with self.assertRaises(HeartbeatPrincipalDataError):
            replace(principal, service_domain=other_service)
        with self.assertRaises(HeartbeatPrincipalDataError):
            replace(principal, principal_id=b"\x01" * 32)

    def test_record_interval_is_half_open_and_not_an_authority_status(self):
        principal = _principal_from_fixture()
        self.assertFalse(principal.interval_contains(principal.not_before - 1))
        self.assertTrue(principal.interval_contains(principal.not_before))
        self.assertTrue(principal.interval_contains(principal.expires_at - 1))
        self.assertFalse(principal.interval_contains(principal.expires_at))
        with self.assertRaises(HeartbeatPrincipalDataError):
            principal.interval_contains(True)
        self.assertEqual(
            replace(principal, policy_version=(1 << 64) - 1).policy_version,
            (1 << 64) - 1,
        )
        self.assertFalse(hasattr(principal, "is_active"))
        self.assertFalse(hasattr(principal, "is_qualified"))
        self.assertFalse(hasattr(principal, "approved"))
        self.assertNotIn("revoked", {item.name for item in fields(principal)})


if __name__ == "__main__":
    unittest.main()
