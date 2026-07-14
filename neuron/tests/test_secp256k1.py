import hashlib

import pytest

from neuron.secp256k1 import (
    SECP256K1_ORDER,
    generate_private_key,
    load_private_key_pem,
    private_key_pem,
    public_key_bytes,
    sign_digest,
    sign_message,
    verify_digest,
    verify_message,
)


def test_message_signature_round_trip_and_tamper_rejection():
    key = generate_private_key()
    public_key = public_key_bytes(key)
    signature = sign_message(key, b"VAMS-auth-message")

    assert len(public_key) == 64
    assert len(signature) == 64
    assert verify_message(public_key, b"VAMS-auth-message", signature)
    assert not verify_message(public_key, b"tampered", signature)


def test_digest_signature_round_trip_and_wrong_digest_rejection():
    key = generate_private_key()
    digest = hashlib.sha256(b"intent").digest()
    signature = sign_digest(key, digest)

    assert verify_digest(public_key_bytes(key), digest, signature)
    assert not verify_digest(
        public_key_bytes(key), hashlib.sha256(b"other").digest(), signature
    )


def test_verifier_rejects_noncanonical_high_s_signature():
    key = generate_private_key()
    message = b"canonical-signature"
    signature = sign_message(key, message)
    r = int.from_bytes(signature[:32], "big")
    low_s = int.from_bytes(signature[32:], "big")
    high_s = SECP256K1_ORDER - low_s
    malleated = r.to_bytes(32, "big") + high_s.to_bytes(32, "big")

    assert high_s > SECP256K1_ORDER // 2
    assert not verify_message(public_key_bytes(key), message, malleated)


@pytest.mark.parametrize(
    ("public_key", "signature"),
    [(b"", b""), (b"\x00" * 63, b"\x00" * 64), (b"\x00" * 64, b"\x00" * 63)],
)
def test_verifier_rejects_malformed_wire_values(public_key, signature):
    assert not verify_message(public_key, b"message", signature)


def test_private_key_pem_round_trip_preserves_public_identity():
    key = generate_private_key()
    loaded = load_private_key_pem(private_key_pem(key))

    assert public_key_bytes(loaded) == public_key_bytes(key)


def test_digest_signing_rejects_non_sha256_length():
    with pytest.raises(ValueError, match="32 bytes"):
        sign_digest(generate_private_key(), b"short")
