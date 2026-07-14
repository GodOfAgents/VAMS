"""Validated encrypted witness-sidecar handling for the VDSO canary.

Only ciphertext and commitments cross storage boundaries.  The sidecar content
hash is a non-consensus, length-delimited commitment over all encrypted
metadata, including the nonce and recipient key envelopes.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Tuple

from .keccak import domain_hash


SIDECAR_SCHEMA_VERSION = 1
MAX_CIPHERTEXT_BYTES = 786_432
MAX_RECIPIENTS = 64
MAX_ENCAPSULATED_KEY_BYTES = 4_096
MAX_WRAPPED_KEY_BYTES = 8_192
SIDECAR_CONTENT_DOMAIN = b"VAMS:SIDECAR-CONTENT:v1"


class SidecarCryptoUnavailable(RuntimeError):
    """Raised when the required sidecar crypto backend is unavailable."""


def _require_bytes(name: str, value: bytes, *, exact: int | None = None, maximum: int) -> None:
    if not isinstance(value, bytes) or not value:
        raise ValueError(f"{name} must be non-empty bytes")
    if exact is not None and len(value) != exact:
        raise ValueError(f"{name} must contain exactly {exact} bytes")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds the {maximum}-byte limit")


@dataclass(frozen=True)
class RecipientEnvelope:
    recipient_id: bytes
    encapsulated_key: bytes
    wrapped_key: bytes

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_bytes("recipient_id", self.recipient_id, exact=32, maximum=32)
        _require_bytes(
            "encapsulated_key",
            self.encapsulated_key,
            maximum=MAX_ENCAPSULATED_KEY_BYTES,
        )
        _require_bytes("wrapped_key", self.wrapped_key, maximum=MAX_WRAPPED_KEY_BYTES)


def sidecar_content_hash(
    *,
    schema_version: int,
    nonce: bytes,
    ciphertext: bytes,
    plaintext_root: bytes,
    policy_hash: bytes,
    recipient_envelopes: Tuple[RecipientEnvelope, ...],
) -> bytes:
    """Commit to every encrypted sidecar field using length-delimited framing."""

    parts = [
        schema_version.to_bytes(2, "big"),
        nonce,
        ciphertext,
        plaintext_root,
        policy_hash,
        len(recipient_envelopes).to_bytes(2, "big"),
    ]
    for envelope in recipient_envelopes:
        parts.extend(
            (
                envelope.recipient_id,
                envelope.encapsulated_key,
                envelope.wrapped_key,
            )
        )
    return domain_hash(SIDECAR_CONTENT_DOMAIN, tuple(parts))


@dataclass(frozen=True)
class EncryptedWitnessSidecar:
    schema_version: int
    nonce: bytes
    ciphertext: bytes
    plaintext_root: bytes
    content_hash: bytes
    policy_hash: bytes
    recipient_envelopes: Tuple[RecipientEnvelope, ...]

    def __post_init__(self) -> None:
        self.validate_integrity()

    def validate_integrity(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != SIDECAR_SCHEMA_VERSION
        ):
            raise ValueError(f"sidecar schema_version must equal {SIDECAR_SCHEMA_VERSION}")
        _require_bytes("nonce", self.nonce, exact=24, maximum=24)
        _require_bytes("ciphertext", self.ciphertext, maximum=MAX_CIPHERTEXT_BYTES)
        _require_bytes("plaintext_root", self.plaintext_root, exact=32, maximum=32)
        _require_bytes("content_hash", self.content_hash, exact=32, maximum=32)
        _require_bytes("policy_hash", self.policy_hash, exact=32, maximum=32)
        if not isinstance(self.recipient_envelopes, tuple):
            raise ValueError("recipient_envelopes must be an immutable tuple")
        if not 1 <= len(self.recipient_envelopes) <= MAX_RECIPIENTS:
            raise ValueError(f"sidecar requires between 1 and {MAX_RECIPIENTS} recipients")
        if any(
            not isinstance(envelope, RecipientEnvelope)
            for envelope in self.recipient_envelopes
        ):
            raise ValueError("recipient_envelopes contains an invalid envelope")
        for envelope in self.recipient_envelopes:
            envelope.validate()
        recipient_ids = tuple(
            envelope.recipient_id for envelope in self.recipient_envelopes
        )
        if recipient_ids != tuple(sorted(recipient_ids)):
            raise ValueError("recipient envelopes must be sorted by recipient_id")
        if len(set(recipient_ids)) != len(recipient_ids):
            raise ValueError("recipient envelopes must contain unique recipient IDs")
        expected = sidecar_content_hash(
            schema_version=self.schema_version,
            nonce=self.nonce,
            ciphertext=self.ciphertext,
            plaintext_root=self.plaintext_root,
            policy_hash=self.policy_hash,
            recipient_envelopes=self.recipient_envelopes,
        )
        if not hmac.compare_digest(expected, self.content_hash):
            raise ValueError("sidecar content_hash does not match encrypted metadata")


HPKESeal = Callable[[bytes, bytes, bytes], Tuple[bytes, bytes]]


def encrypt_sidecar(
    plaintext: bytes,
    *,
    plaintext_root: bytes,
    policy_hash: bytes,
    recipients: Iterable[Tuple[bytes, bytes]],
    hpke_seal: Optional[HPKESeal],
    associated_data: bytes,
) -> EncryptedWitnessSidecar:
    """Encrypt a sidecar and wrap its data key for each unique recipient.

    ``hpke_seal`` must implement RFC 9180 base mode with
    X25519/HKDF-SHA256/ChaCha20Poly1305 and returns ``(enc, ciphertext)``.
    """

    _require_bytes("plaintext", plaintext, maximum=MAX_CIPHERTEXT_BYTES - 16)
    _require_bytes("plaintext_root", plaintext_root, exact=32, maximum=32)
    _require_bytes("policy_hash", policy_hash, exact=32, maximum=32)
    _require_bytes("associated_data", associated_data, maximum=4_096)
    if hpke_seal is None:
        raise SidecarCryptoUnavailable("an audited RFC 9180 HPKE backend is required")
    try:
        from nacl.bindings import crypto_aead_xchacha20poly1305_ietf_encrypt
    except ImportError as exc:
        raise SidecarCryptoUnavailable(
            "PyNaCl XChaCha20-Poly1305 backend is required"
        ) from exc

    recipient_values = tuple(recipients)
    if not 1 <= len(recipient_values) <= MAX_RECIPIENTS:
        raise ValueError(f"sidecar requires between 1 and {MAX_RECIPIENTS} recipients")
    for recipient_id, recipient_public_key in recipient_values:
        _require_bytes("recipient_id", recipient_id, exact=32, maximum=32)
        _require_bytes("recipient_public_key", recipient_public_key, maximum=4_096)
    recipient_ids = tuple(recipient_id for recipient_id, _key in recipient_values)
    if len(set(recipient_ids)) != len(recipient_ids):
        raise ValueError("recipients must contain unique recipient IDs")

    data_key = os.urandom(32)
    nonce = os.urandom(24)
    ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(
        plaintext, associated_data, nonce, data_key
    )

    envelopes = []
    for recipient_id, recipient_public_key in recipient_values:
        enc, wrapped = hpke_seal(recipient_public_key, data_key, associated_data)
        envelopes.append(RecipientEnvelope(recipient_id, enc, wrapped))
    ordered_envelopes = tuple(sorted(envelopes, key=lambda item: item.recipient_id))
    content_hash = sidecar_content_hash(
        schema_version=SIDECAR_SCHEMA_VERSION,
        nonce=nonce,
        ciphertext=ciphertext,
        plaintext_root=plaintext_root,
        policy_hash=policy_hash,
        recipient_envelopes=ordered_envelopes,
    )
    return EncryptedWitnessSidecar(
        schema_version=SIDECAR_SCHEMA_VERSION,
        nonce=nonce,
        ciphertext=ciphertext,
        plaintext_root=plaintext_root,
        content_hash=content_hash,
        policy_hash=policy_hash,
        recipient_envelopes=ordered_envelopes,
    )
