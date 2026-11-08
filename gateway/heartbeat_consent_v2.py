"""Canonical unsigned heartbeat consent data v2.

This module validates and encodes data only. It does not establish authority,
verify signatures, authenticate a challenge, inspect a Timelock, or authorize
principal mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

BASE_DOMAIN = b"VAMS:GATEWAY:HEARTBEAT-CONSENT-BASE:v2\x00"
WITNESS_DOMAIN = b"VAMS:GATEWAY:HEARTBEAT-CONSENT-WITNESS:v2\x00"
BASE_FIELD_COUNT = 18
WITNESS_FIELD_COUNT = 8
MAX_ENCODING_BYTES = 1024
UINT64_MAX = (1 << 64) - 1

MODE_ENROLL = 1
MODE_ROTATE_NORMAL = 2
MODE_RECOVER_LOST_KEY = 3
VALID_MODES = frozenset((MODE_ENROLL, MODE_ROTATE_NORMAL, MODE_RECOVER_LOST_KEY))

ROLE_OLD_KEY = 0x01
ROLE_NEW_KEY = 0x02
ROLE_MASK_ENROLL = ROLE_NEW_KEY
ROLE_MASK_ROTATE_NORMAL = ROLE_OLD_KEY | ROLE_NEW_KEY
ROLE_MASK_RECOVER_LOST_KEY = ROLE_NEW_KEY


class HeartbeatConsentDataError(ValueError):
    """Malformed, out-of-range, or noncanonical consent data."""


def _uint64(value: object, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or not 0 <= value <= UINT64_MAX:
        raise HeartbeatConsentDataError(f"invalid {label}")
    if positive and value == 0:
        raise HeartbeatConsentDataError(f"invalid {label}")
    return value


def _bytes(value: object, width: int, label: str, *, nonzero: bool = False) -> bytes:
    if type(value) is not bytes or len(value) != width:
        raise HeartbeatConsentDataError(f"invalid {label}")
    if nonzero and not any(value):
        raise HeartbeatConsentDataError(f"missing {label}")
    return value


def _mode(value: object) -> int:
    if type(value) is not int or value not in VALID_MODES:
        raise HeartbeatConsentDataError("unsupported consent mode")
    return value


def _tlv(field_id: int, value: bytes) -> bytes:
    if not 1 <= field_id <= 255 or len(value) > 0xFFFF:
        raise HeartbeatConsentDataError("invalid consent field")
    return bytes((field_id,)) + len(value).to_bytes(2, "big") + value


def _parse_frame(raw: object, domain: bytes, field_count: int) -> tuple[bytes, ...]:
    if type(raw) is not bytes or len(raw) > MAX_ENCODING_BYTES:
        raise HeartbeatConsentDataError("invalid consent frame")
    header_end = len(domain) + 2
    if len(raw) < header_end or not raw.startswith(domain):
        raise HeartbeatConsentDataError("invalid consent frame")
    if int.from_bytes(raw[len(domain):header_end], "big") != field_count:
        raise HeartbeatConsentDataError("invalid consent field count")
    offset = header_end
    values: list[bytes] = []
    for expected_id in range(1, field_count + 1):
        if len(raw) - offset < 3:
            raise HeartbeatConsentDataError("truncated consent field")
        field_id = raw[offset]
        length = int.from_bytes(raw[offset + 1:offset + 3], "big")
        if field_id != expected_id:
            raise HeartbeatConsentDataError("noncanonical consent field order")
        offset += 3
        if len(raw) - offset < length:
            raise HeartbeatConsentDataError("truncated consent value")
        values.append(raw[offset:offset + length])
        offset += length
    if offset != len(raw):
        raise HeartbeatConsentDataError("trailing consent bytes")
    return tuple(values)


@dataclass(frozen=True)
class HeartbeatConsentBaseIntentV2:
    """Immutable unsigned intent data, computable before Timelock scheduling."""

    mode: int
    source_scheme: int
    authority_source_digest: bytes
    timelock_address: bytes
    timelock_code_hash: bytes
    authority_config_digest: bytes
    authority_change_sequence: int
    policy_root: bytes
    policy_version: int
    authority_epoch: int
    principal_id: bytes
    proposed_record_digest: bytes
    expected_record_digest: bytes
    expected_generation: int
    proposed_generation: int
    consent_nonce: int
    timelock_predecessor: bytes
    timelock_salt: bytes

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _mode(self.mode)
        if type(self.source_scheme) is not int or self.source_scheme != 1:
            raise HeartbeatConsentDataError("unsupported authority-source scheme")
        _bytes(self.authority_source_digest, 32, "authority-source digest")
        _bytes(self.timelock_address, 20, "Timelock address", nonzero=True)
        _bytes(self.timelock_code_hash, 32, "Timelock code hash", nonzero=True)
        _bytes(self.authority_config_digest, 32, "authority configuration digest")
        _uint64(self.authority_change_sequence, "authority change sequence")
        _bytes(self.policy_root, 32, "policy root", nonzero=True)
        _uint64(self.policy_version, "policy version", positive=True)
        _uint64(self.authority_epoch, "authority epoch", positive=True)
        _bytes(self.principal_id, 32, "principal ID", nonzero=True)
        _bytes(self.proposed_record_digest, 32, "proposed principal record digest")
        _bytes(self.expected_record_digest, 32, "expected principal record digest")
        expected_generation = _uint64(self.expected_generation, "expected generation")
        proposed_generation = _uint64(self.proposed_generation, "proposed generation", positive=True)
        _uint64(self.consent_nonce, "consent nonce")
        _bytes(self.timelock_predecessor, 32, "Timelock predecessor")
        _bytes(self.timelock_salt, 32, "Timelock salt")

        if self.mode == MODE_ENROLL:
            if self.expected_record_digest != bytes(32) or expected_generation != 0 or proposed_generation != 1:
                raise HeartbeatConsentDataError("invalid enrollment compare-and-set")
        else:
            if (
                expected_generation == 0
                or expected_generation == UINT64_MAX
                or proposed_generation != expected_generation + 1
            ):
                raise HeartbeatConsentDataError("invalid replacement compare-and-set")

    def _field_values(self) -> tuple[bytes, ...]:
        self.validate()
        return (
            bytes((self.mode,)),
            bytes((self.source_scheme,)),
            self.authority_source_digest,
            self.timelock_address,
            self.timelock_code_hash,
            self.authority_config_digest,
            self.authority_change_sequence.to_bytes(8, "big"),
            self.policy_root,
            self.policy_version.to_bytes(8, "big"),
            self.authority_epoch.to_bytes(8, "big"),
            self.principal_id,
            self.proposed_record_digest,
            self.expected_record_digest,
            self.expected_generation.to_bytes(8, "big"),
            self.proposed_generation.to_bytes(8, "big"),
            self.consent_nonce.to_bytes(8, "big"),
            self.timelock_predecessor,
            self.timelock_salt,
        )

    def canonical_bytes(self) -> bytes:
        encoded = bytearray(BASE_DOMAIN)
        encoded.extend(BASE_FIELD_COUNT.to_bytes(2, "big"))
        for field_id, value in enumerate(self._field_values(), 1):
            encoded.extend(_tlv(field_id, value))
        if len(encoded) > MAX_ENCODING_BYTES:
            raise HeartbeatConsentDataError("base intent exceeds encoding bound")
        return bytes(encoded)

    @property
    def digest(self) -> bytes:
        """SHA-256 of the complete exact base-intent frame, once."""
        return hashlib.sha256(self.canonical_bytes()).digest()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "HeartbeatConsentBaseIntentV2":
        values = _parse_frame(raw, BASE_DOMAIN, BASE_FIELD_COUNT)
        widths = (1, 1, 32, 20, 32, 32, 8, 32, 8, 8, 32, 32, 32, 8, 8, 8, 32, 32)
        if tuple(map(len, values)) != widths:
            raise HeartbeatConsentDataError("invalid base intent field width")
        parsed = cls(
            mode=values[0][0],
            source_scheme=values[1][0],
            authority_source_digest=values[2],
            timelock_address=values[3],
            timelock_code_hash=values[4],
            authority_config_digest=values[5],
            authority_change_sequence=int.from_bytes(values[6], "big"),
            policy_root=values[7],
            policy_version=int.from_bytes(values[8], "big"),
            authority_epoch=int.from_bytes(values[9], "big"),
            principal_id=values[10],
            proposed_record_digest=values[11],
            expected_record_digest=values[12],
            expected_generation=int.from_bytes(values[13], "big"),
            proposed_generation=int.from_bytes(values[14], "big"),
            consent_nonce=int.from_bytes(values[15], "big"),
            timelock_predecessor=values[16],
            timelock_salt=values[17],
        )
        if parsed.canonical_bytes() != raw:
            raise HeartbeatConsentDataError("noncanonical base intent")
        return parsed


@dataclass(frozen=True)
class HeartbeatConsentWitnessV2:
    """Unsigned witness preimage; no signature, freshness proof, or authority."""

    base_intent_digest: bytes
    operation_id: bytes
    queued_eta: int
    post_eta_challenge_commitment: bytes
    issued_at: int
    expires_at: int
    mode: int
    required_role_mask: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _bytes(self.base_intent_digest, 32, "base intent digest")
        _bytes(self.operation_id, 32, "operation ID")
        queued_eta = _uint64(self.queued_eta, "queued ETA")
        _bytes(self.post_eta_challenge_commitment, 32, "post-ETA challenge commitment")
        issued_at = _uint64(self.issued_at, "witness issue time")
        expires_at = _uint64(self.expires_at, "witness expiry")
        if issued_at < queued_eta or expires_at <= issued_at:
            raise HeartbeatConsentDataError("invalid witness time ordering")
        mode = _mode(self.mode)
        expected_mask = _required_mask(mode)
        if type(self.required_role_mask) is not int or self.required_role_mask != expected_mask:
            raise HeartbeatConsentDataError("invalid witness role mask")

    def _field_values(self) -> tuple[bytes, ...]:
        self.validate()
        return (
            self.base_intent_digest,
            self.operation_id,
            self.queued_eta.to_bytes(8, "big"),
            self.post_eta_challenge_commitment,
            self.issued_at.to_bytes(8, "big"),
            self.expires_at.to_bytes(8, "big"),
            bytes((self.mode,)),
            bytes((self.required_role_mask,)),
        )

    def canonical_bytes(self) -> bytes:
        encoded = bytearray(WITNESS_DOMAIN)
        encoded.extend(WITNESS_FIELD_COUNT.to_bytes(2, "big"))
        for field_id, value in enumerate(self._field_values(), 1):
            encoded.extend(_tlv(field_id, value))
        if len(encoded) > MAX_ENCODING_BYTES:
            raise HeartbeatConsentDataError("witness exceeds encoding bound")
        return bytes(encoded)

    @property
    def digest(self) -> bytes:
        """SHA-256 of the exact signed witness preimage frame, once."""
        return hashlib.sha256(self.canonical_bytes()).digest()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "HeartbeatConsentWitnessV2":
        values = _parse_frame(raw, WITNESS_DOMAIN, WITNESS_FIELD_COUNT)
        widths = (32, 32, 8, 32, 8, 8, 1, 1)
        if tuple(map(len, values)) != widths:
            raise HeartbeatConsentDataError("invalid witness field width")
        parsed = cls(
            base_intent_digest=values[0],
            operation_id=values[1],
            queued_eta=int.from_bytes(values[2], "big"),
            post_eta_challenge_commitment=values[3],
            issued_at=int.from_bytes(values[4], "big"),
            expires_at=int.from_bytes(values[5], "big"),
            mode=values[6][0],
            required_role_mask=values[7][0],
        )
        if parsed.canonical_bytes() != raw:
            raise HeartbeatConsentDataError("noncanonical witness")
        return parsed

    def matches_base_data(self, base: HeartbeatConsentBaseIntentV2) -> bool:
        """Structural matching only; this does not authenticate or authorize."""
        if type(base) is not HeartbeatConsentBaseIntentV2:
            return False
        try:
            self.validate()
            base.validate()
        except HeartbeatConsentDataError:
            return False
        return (
            self.base_intent_digest == base.digest
            and self.mode == base.mode
            and self.required_role_mask == _required_mask(base.mode)
        )


def _required_mask(mode: int) -> int:
    if mode == MODE_ENROLL:
        return ROLE_MASK_ENROLL
    if mode == MODE_ROTATE_NORMAL:
        return ROLE_MASK_ROTATE_NORMAL
    if mode == MODE_RECOVER_LOST_KEY:
        return ROLE_MASK_RECOVER_LOST_KEY
    raise HeartbeatConsentDataError("unsupported consent mode")
