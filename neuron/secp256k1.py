"""Strict secp256k1 signing primitives for VAMS wire protocols.

The public-key wire format is the 64-byte ``x || y`` encoding used by the
existing DID and heartbeat protocols. Signatures are the 64-byte ``r || s``
encoding, use SHA-256, and are normalized to low-S form. Verification rejects
non-canonical signatures so a valid signature has a single wire encoding.
"""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


SECP256K1_ORDER = int(
    "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",
    16,
)
SCALAR_BYTES = 32
PUBLIC_KEY_BYTES = 64
SIGNATURE_BYTES = 64

PrivateKey = ec.EllipticCurvePrivateKey
PublicKey = ec.EllipticCurvePublicKey


def generate_private_key() -> PrivateKey:
    """Generate a secp256k1 private key using the operating-system RNG."""

    return ec.generate_private_key(ec.SECP256K1())


def load_private_key_pem(data: bytes, password: bytes | None = None) -> PrivateKey:
    """Load a PEM key and reject non-secp256k1 key material."""

    key = serialization.load_pem_private_key(data, password=password)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
        key.curve, ec.SECP256K1
    ):
        raise ValueError("identity key must use secp256k1")
    return key


def private_key_pem(key: PrivateKey) -> bytes:
    """Serialize a private key as an unencrypted SEC1 PEM document."""

    _require_private_key(key)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_key_bytes(key: PrivateKey | PublicKey) -> bytes:
    """Return the canonical 64-byte ``x || y`` public-key encoding."""

    public_key = key.public_key() if isinstance(key, ec.EllipticCurvePrivateKey) else key
    _require_public_key(public_key)
    numbers = public_key.public_numbers()
    return numbers.x.to_bytes(SCALAR_BYTES, "big") + numbers.y.to_bytes(
        SCALAR_BYTES, "big"
    )


def sign_message(key: PrivateKey, message: bytes) -> bytes:
    """Sign a message with ECDSA/SHA-256 and return canonical raw ``r || s``."""

    _require_private_key(key)
    der = key.sign(message, ec.ECDSA(hashes.SHA256()))
    return _canonical_raw_signature(der)


def verify_message(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify a canonical raw ECDSA/SHA-256 signature without raising."""

    return _verify(public_key, message, signature, prehashed=False)


def sign_digest(key: PrivateKey, digest: bytes) -> bytes:
    """Sign an existing 32-byte SHA-256 digest and return raw ``r || s``."""

    _require_private_key(key)
    _require_digest(digest)
    der = key.sign(digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    return _canonical_raw_signature(der)


def verify_digest(public_key: bytes, digest: bytes, signature: bytes) -> bool:
    """Verify a canonical raw signature over an existing SHA-256 digest."""

    if len(digest) != hashes.SHA256().digest_size:
        return False
    return _verify(public_key, digest, signature, prehashed=True)


def _verify(
    public_key: bytes,
    data: bytes,
    signature: bytes,
    *,
    prehashed: bool,
) -> bool:
    try:
        key = _public_key_from_bytes(public_key)
        der = _raw_signature_to_der(signature)
        algorithm = (
            ec.ECDSA(utils.Prehashed(hashes.SHA256()))
            if prehashed
            else ec.ECDSA(hashes.SHA256())
        )
        key.verify(der, data, algorithm)
        return True
    except (InvalidSignature, TypeError, ValueError):
        return False


def _public_key_from_bytes(encoded: bytes) -> PublicKey:
    if not isinstance(encoded, bytes) or len(encoded) != PUBLIC_KEY_BYTES:
        raise ValueError("public key must be 64 bytes")
    x = int.from_bytes(encoded[:SCALAR_BYTES], "big")
    y = int.from_bytes(encoded[SCALAR_BYTES:], "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1()).public_key()


def _canonical_raw_signature(der: bytes) -> bytes:
    r, s = utils.decode_dss_signature(der)
    if s > SECP256K1_ORDER // 2:
        s = SECP256K1_ORDER - s
    return r.to_bytes(SCALAR_BYTES, "big") + s.to_bytes(SCALAR_BYTES, "big")


def _raw_signature_to_der(signature: bytes) -> bytes:
    if not isinstance(signature, bytes) or len(signature) != SIGNATURE_BYTES:
        raise ValueError("signature must be 64 bytes")
    r = int.from_bytes(signature[:SCALAR_BYTES], "big")
    s = int.from_bytes(signature[SCALAR_BYTES:], "big")
    if not (1 <= r < SECP256K1_ORDER):
        raise ValueError("signature r is out of range")
    if not (1 <= s <= SECP256K1_ORDER // 2):
        raise ValueError("signature s is non-canonical")
    return utils.encode_dss_signature(r, s)


def _require_private_key(key: PrivateKey) -> None:
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
        key.curve, ec.SECP256K1
    ):
        raise ValueError("private key must use secp256k1")


def _require_public_key(key: PublicKey) -> None:
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(
        key.curve, ec.SECP256K1
    ):
        raise ValueError("public key must use secp256k1")


def _require_digest(digest: bytes) -> None:
    if len(digest) != hashes.SHA256().digest_size:
        raise ValueError("SHA-256 digest must be 32 bytes")
