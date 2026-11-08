"""Pure synthetic source data; no node, chain, proxy or issuer authentication."""
from dataclasses import replace
import hashlib
import unittest

from gateway.heartbeat_authority_source_v1 import (
    DOMAIN, EVM_NETWORK_DOMAIN, HeartbeatAuthoritySourceDataError as Error,
    HeartbeatAuthoritySourceV1 as Source, evm_network_context_digest,
)


def sample():
    return Source(1, evm_network_context_digest(80002, b"\x09" * 32),
                  b"\x11" * 20, b"\x22" * 32, b"\x33" * 20, b"\x44" * 32, 1)


class HeartbeatAuthoritySourceV1Tests(unittest.TestCase):
    def test_network_preimage_is_tagged_uint256_and_exact_genesis(self):
        expected = hashlib.sha256(b"VAMS:GATEWAY:EVM-NETWORK:v1\0" + (80002).to_bytes(32, "big") + b"\x09" * 32).digest()
        self.assertEqual(evm_network_context_digest(80002, b"\x09" * 32), expected)
        self.assertEqual(evm_network_context_digest((1 << 256) - 1, b"\x01" * 32),
                         hashlib.sha256(EVM_NETWORK_DOMAIN + b"\xff" * 32 + b"\x01" * 32).digest())
        self.assertNotEqual(expected, evm_network_context_digest(80001, b"\x09" * 32))
        self.assertNotEqual(expected, evm_network_context_digest(80002, b"\x08" * 32))

    def test_network_type_range_and_genesis_guards(self):
        for value in (False, True, 0, -1, 1 << 256, "80002", 80002.0, None):
            with self.subTest(value=type(value).__name__), self.assertRaises(Error):
                evm_network_context_digest(value, b"\x09" * 32)
        for value in (bytes(32), b"1" * 31, b"1" * 33, bytearray(b"1" * 32), "a" * 32):
            with self.assertRaises(Error):
                evm_network_context_digest(80002, value)

    def test_literal_field_order_and_roundtrip(self):
        s = sample()
        values = [b"\x01", s.network_context_digest, b"\x11" * 20, b"\x22" * 32,
                  b"\x33" * 20, b"\x44" * 32, b"\0\x01"]
        raw = b"VAMS:GATEWAY:AUTHORITY-SOURCE:v1\0\0\x07"
        for field_id, value in enumerate(values, 1):
            raw += bytes((field_id,)) + len(value).to_bytes(2, "big") + value
        self.assertEqual(s.canonical_bytes(), raw)
        self.assertEqual(s.digest, hashlib.sha256(raw).digest())
        self.assertEqual(Source.from_bytes(raw), s)

    def test_every_truncation_and_alternate_framing_rejects(self):
        raw = sample().canonical_bytes()
        for end in range(len(raw)):
            with self.subTest(end=end), self.assertRaises(Error):
                Source.from_bytes(raw[:end])
        start = len(DOMAIN) + 2
        for position, value in ((0, 0), (len(DOMAIN), 1), (len(DOMAIN) + 1, 6),
                                (start, 2), (start + 1, 1), (start + 2, 2)):
            mutated = bytearray(raw);mutated[position] = value
            with self.assertRaises(Error):
                Source.from_bytes(bytes(mutated))
        for extra in (b"\0", b"\x08\0\x01\x01"):
            with self.assertRaises(Error):
                Source.from_bytes(raw + extra)

    def test_exact_widths_nonzero_and_no_mutable_identity_values(self):
        names = {"network_context_digest": 32, "registry_address": 20,
                 "registry_code_hash": 32, "policy_address": 20, "policy_code_hash": 32}
        for name, size in names.items():
            for value in (bytes(size), b"1" * (size - 1), b"1" * (size + 1), bytearray(b"1" * size), None):
                with self.subTest(field=name), self.assertRaises(Error):
                    replace(sample(), **{name: value})

    def test_scheme_schema_bool_and_reserved_cardano_reject(self):
        for value in (0, 2, 255, True, "1", 1.0, None):
            with self.assertRaises(Error):
                replace(sample(), scheme=value)
        for value in (0, 2, 65535, True, "1", 1.0, None):
            with self.assertRaises(Error):
                replace(sample(), registry_schema_version=value)

    def test_total_guard_and_strict_bytes_input(self):
        raw = sample().canonical_bytes()
        for value in (raw + bytes(512 - len(raw)), bytes(513), bytearray(raw), raw.hex(), None):
            with self.assertRaises(Error):
                Source.from_bytes(value)

    def test_deployment_changes_digest_without_conferring_qualification(self):
        s = sample()
        for change in (dict(registry_address=b"\x12" * 20), dict(registry_code_hash=b"\x23" * 32),
                       dict(policy_address=b"\x34" * 20), dict(policy_code_hash=b"\x45" * 32)):
            self.assertNotEqual(s.digest, replace(s, **change).digest)
        # Opaque bytes can name an unapproved/proxy address. Data validation
        # cannot establish its code or profile: the authenticated reader must.
        self.assertEqual(Source.from_bytes(s.canonical_bytes()), s)
        self.assertFalse(hasattr(s, "is_authorized"))

    def test_frozen_values_are_rechecked_after_illicit_object_mutation(self):
        s = sample();object.__setattr__(s, "scheme", 2)
        with self.assertRaises(Error):
            s.canonical_bytes()


if __name__ == "__main__":
    unittest.main()
