"""Canonical unsigned data codec for the VAMS heartbeat payload v2.

The types in this module validate and encode data only. They do not verify a
signature, resolve authority, choose a schema cutover, consume replay state, or
authorize or mutate a heartbeat.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct

from gateway.heartbeat_principal_v1 import (
    HeartbeatPrincipalDataError,
    HeartbeatPrincipalV1,
    node_id_commitment,
    principal_id_commitment,
)


PAYLOAD_DOMAIN = b"VAMS:GATEWAY:HEARTBEAT-PAYLOAD:v2\x00"
PAYLOAD_TEXT_PREFIX = "VAMS-HB2:"
OBSERVATIONS_DOMAIN = b"VAMS:GATEWAY:HEARTBEAT-OBSERVATION:v1\x00"
PAYLOAD_FIELD_COUNT = 13
MAX_PAYLOAD_BYTES = 8192
MAX_PAYLOAD_TEXT_CHARS = len(PAYLOAD_TEXT_PREFIX) + 2 * MAX_PAYLOAD_BYTES
MAX_OBSERVATIONS_BYTES = 4096
MAX_NODE_ID_BYTES = 256
MAX_TEXT_BYTES = 256
MAX_SKILLS = 32
MAX_SKILL_BYTES = 64
MAX_PROFILE_ENTRIES = 64
MAX_PROFILE_KEY_BYTES = 64
MAX_M2_TIMESTAMP = (1 << 63) - 1
MAX_M2_LIFETIME_SECONDS = 300
UINT64_MAX = (1 << 64) - 1
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1

_VALUE_INT = 0x01
_VALUE_FLOAT = 0x02
class HeartbeatPayloadDataError(ValueError):
    """Malformed, out-of-range, or noncanonical unsigned payload data."""


def _uint(value: object, maximum: int, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or not (0 <= value <= maximum):
        raise HeartbeatPayloadDataError("invalid unsigned integer")
    if positive and value == 0:
        raise HeartbeatPayloadDataError("invalid unsigned integer")
    return value


def _int64(value: object) -> int:
    if type(value) is not int or not (INT64_MIN <= value <= INT64_MAX):
        raise HeartbeatPayloadDataError("invalid signed integer observation")
    return value


def _float64(value: object) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise HeartbeatPayloadDataError("invalid floating-point observation")
    return value


def _text_bytes(value: object, maximum: int, label: str) -> bytes:
    if type(value) is not str or len(value) > maximum:
        raise HeartbeatPayloadDataError("invalid text observation")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeEncodeError:
        raise HeartbeatPayloadDataError("invalid text observation") from None
    if len(encoded) > maximum:
        raise HeartbeatPayloadDataError("invalid text observation")
    return encoded


def _node_id_bytes(value: object) -> bytes:
    if type(value) is not str or not value or len(value) > MAX_NODE_ID_BYTES:
        raise HeartbeatPayloadDataError("invalid node ID")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeEncodeError:
        raise HeartbeatPayloadDataError("invalid node ID") from None
    if not encoded or len(encoded) > MAX_NODE_ID_BYTES:
        raise HeartbeatPayloadDataError("invalid node ID")
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise HeartbeatPayloadDataError("invalid node ID")
    return encoded


def _fixed_bytes(value: object, length: int, *, nonzero: bool = False) -> bytes:
    if type(value) is not bytes or len(value) != length:
        raise HeartbeatPayloadDataError("invalid fixed-width byte field")
    if nonzero and not any(value):
        raise HeartbeatPayloadDataError("missing identity bytes")
    return value


def _tlv(field_id: int, value: bytes) -> bytes:
    if not (1 <= field_id <= 255) or len(value) > 0xFFFF:
        raise HeartbeatPayloadDataError("field exceeds encoding bound")
    return bytes((field_id,)) + len(value).to_bytes(2, "big") + value


def _read_tlvs(
    raw: bytes,
    *,
    domain: bytes,
    maximum: int,
    min_fields: int,
    max_fields: int,
    exact_fields: int | None = None,
) -> list[tuple[int, bytes]]:
    if type(raw) is not bytes or len(raw) > maximum:
        raise HeartbeatPayloadDataError("invalid payload encoding")
    prefix_len = len(domain) + 2
    if len(raw) < prefix_len or not raw.startswith(domain):
        raise HeartbeatPayloadDataError("invalid payload encoding")
    count = int.from_bytes(raw[len(domain):prefix_len], "big")
    if not (min_fields <= count <= max_fields):
        raise HeartbeatPayloadDataError("invalid field count")
    if exact_fields is not None and count != exact_fields:
        raise HeartbeatPayloadDataError("invalid field count")

    result: list[tuple[int, bytes]] = []
    offset = prefix_len
    previous_id = 0
    for index in range(count):
        if len(raw) - offset < 3:
            raise HeartbeatPayloadDataError("truncated field")
        field_id = raw[offset]
        value_len = int.from_bytes(raw[offset + 1:offset + 3], "big")
        offset += 3
        if field_id <= previous_id:
            raise HeartbeatPayloadDataError("noncanonical field order")
        if exact_fields is None and field_id > max_fields:
            raise HeartbeatPayloadDataError("unknown field identifier")
        if exact_fields is not None and field_id != index + 1:
            raise HeartbeatPayloadDataError("noncanonical field order")
        if len(raw) - offset < value_len:
            raise HeartbeatPayloadDataError("truncated field")
        result.append((field_id, raw[offset:offset + value_len]))
        offset += value_len
        previous_id = field_id
    if offset != len(raw):
        raise HeartbeatPayloadDataError("trailing payload bytes")
    return result


def _decode_text(value: bytes, maximum: int) -> str:
    if len(value) > maximum:
        raise HeartbeatPayloadDataError("text field exceeds bound")
    try:
        return value.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise HeartbeatPayloadDataError("invalid UTF-8 field") from None


def _encode_tagged_number(value: object) -> bytes:
    if type(value) is int:
        return bytes((_VALUE_INT,)) + _int64(value).to_bytes(8, "big", signed=True)
    if type(value) is float:
        return bytes((_VALUE_FLOAT,)) + struct.pack(">d", _float64(value))
    raise HeartbeatPayloadDataError("invalid numeric observation")


def _decode_tagged_number(raw: bytes) -> int | float:
    if len(raw) != 9:
        raise HeartbeatPayloadDataError("invalid numeric field width")
    tag = raw[0]
    if tag == _VALUE_INT:
        return _int64(int.from_bytes(raw[1:], "big", signed=True))
    if tag == _VALUE_FLOAT:
        value = struct.unpack(">d", raw[1:])[0]
        return _float64(value)
    raise HeartbeatPayloadDataError("invalid numeric field tag")


@dataclass(frozen=True)
class HeartbeatObservationsV1:
    """Bounded observational values; omitted optional fields remain omitted."""

    block_height: int
    region: str | None = None
    cost_per_hour: int | float | None = None
    credit_score: int | None = None
    passports: str | None = None
    skills: tuple[str, ...] | None = None
    cognitive_profile: tuple[tuple[str, int | float], ...] | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _uint(self.block_height, UINT64_MAX, "block height")
        if self.region is not None:
            _text_bytes(self.region, MAX_TEXT_BYTES, "region")
        if self.cost_per_hour is not None:
            _encode_tagged_number(self.cost_per_hour)
        if self.credit_score is not None:
            _int64(self.credit_score)
        if self.passports is not None:
            _text_bytes(self.passports, MAX_TEXT_BYTES, "passports")

        if self.skills is not None:
            if type(self.skills) is not tuple or len(self.skills) > MAX_SKILLS:
                raise HeartbeatPayloadDataError("invalid skills observation")
            for skill in self.skills:
                _text_bytes(skill, MAX_SKILL_BYTES, "skill")

        if self.cognitive_profile is not None:
            if (
                type(self.cognitive_profile) is not tuple
                or len(self.cognitive_profile) > MAX_PROFILE_ENTRIES
            ):
                raise HeartbeatPayloadDataError("invalid cognitive profile")
            previous_key: bytes | None = None
            for pair in self.cognitive_profile:
                if type(pair) is not tuple or len(pair) != 2:
                    raise HeartbeatPayloadDataError("invalid cognitive profile")
                key, value = pair
                key_bytes = _text_bytes(key, MAX_PROFILE_KEY_BYTES, "profile key")
                if previous_key is not None and key_bytes <= previous_key:
                    raise HeartbeatPayloadDataError("noncanonical cognitive profile")
                _encode_tagged_number(value)
                previous_key = key_bytes

    def _field_values(self) -> list[tuple[int, bytes]]:
        self.validate()
        values: list[tuple[int, bytes]] = [
            (1, self.block_height.to_bytes(8, "big")),
        ]
        if self.region is not None:
            values.append((2, _text_bytes(self.region, MAX_TEXT_BYTES, "region")))
        if self.cost_per_hour is not None:
            values.append((3, _encode_tagged_number(self.cost_per_hour)))
        if self.credit_score is not None:
            values.append((4, bytes((_VALUE_INT,)) + self.credit_score.to_bytes(8, "big", signed=True)))
        if self.passports is not None:
            values.append((5, _text_bytes(self.passports, MAX_TEXT_BYTES, "passports")))
        if self.skills is not None:
            encoded_skills = bytearray((len(self.skills),))
            for skill in self.skills:
                encoded = _text_bytes(skill, MAX_SKILL_BYTES, "skill")
                encoded_skills.extend(len(encoded).to_bytes(2, "big"))
                encoded_skills.extend(encoded)
            values.append((6, bytes(encoded_skills)))
        if self.cognitive_profile is not None:
            encoded_profile = bytearray((len(self.cognitive_profile),))
            for key, value in self.cognitive_profile:
                key_bytes = _text_bytes(key, MAX_PROFILE_KEY_BYTES, "profile key")
                encoded_profile.extend(len(key_bytes).to_bytes(2, "big"))
                encoded_profile.extend(key_bytes)
                encoded_profile.extend(_encode_tagged_number(value))
            values.append((7, bytes(encoded_profile)))
        return values

    def canonical_bytes(self) -> bytes:
        fields = self._field_values()
        encoded = bytearray(OBSERVATIONS_DOMAIN)
        encoded.extend(len(fields).to_bytes(2, "big"))
        for field_id, value in fields:
            encoded.extend(_tlv(field_id, value))
        if len(encoded) > MAX_OBSERVATIONS_BYTES:
            raise HeartbeatPayloadDataError("observations exceed encoding bound")
        return bytes(encoded)

    def to_updates(self) -> dict[str, object]:
        """Return a fresh legacy-field projection without applying defaults."""
        self.validate()
        updates: dict[str, object] = {"block_height": self.block_height}
        if self.region is not None:
            updates["region"] = self.region
        if self.cost_per_hour is not None:
            updates["cost_per_hour"] = self.cost_per_hour
        if self.credit_score is not None:
            updates["credit_score"] = self.credit_score
        if self.passports is not None:
            updates["passports"] = self.passports
        if self.skills is not None:
            updates["skills"] = list(self.skills)
        if self.cognitive_profile is not None:
            updates["cognitive_profile"] = dict(self.cognitive_profile)
        return updates

    @classmethod
    def from_bytes(cls, raw: bytes) -> "HeartbeatObservationsV1":
        fields = _read_tlvs(
            raw,
            domain=OBSERVATIONS_DOMAIN,
            maximum=MAX_OBSERVATIONS_BYTES,
            min_fields=1,
            max_fields=7,
        )
        if fields[0][0] != 1 or len(fields[0][1]) != 8:
            raise HeartbeatPayloadDataError("missing or malformed block height")
        values: dict[int, bytes] = dict(fields)
        block_height = int.from_bytes(values[1], "big")

        region = _decode_text(values[2], MAX_TEXT_BYTES) if 2 in values else None
        cost_per_hour = _decode_tagged_number(values[3]) if 3 in values else None
        credit_score: int | None = None
        if 4 in values:
            raw_credit = values[4]
            if len(raw_credit) != 9 or raw_credit[0] != _VALUE_INT:
                raise HeartbeatPayloadDataError("invalid credit score encoding")
            credit_score = _int64(int.from_bytes(raw_credit[1:], "big", signed=True))
        passports = _decode_text(values[5], MAX_TEXT_BYTES) if 5 in values else None

        skills: tuple[str, ...] | None = None
        if 6 in values:
            raw_skills = values[6]
            if not raw_skills or raw_skills[0] > MAX_SKILLS:
                raise HeartbeatPayloadDataError("invalid skills encoding")
            skill_count = raw_skills[0]
            offset = 1
            parsed_skills: list[str] = []
            for _ in range(skill_count):
                if len(raw_skills) - offset < 2:
                    raise HeartbeatPayloadDataError("truncated skills encoding")
                length = int.from_bytes(raw_skills[offset:offset + 2], "big")
                offset += 2
                if length > MAX_SKILL_BYTES or len(raw_skills) - offset < length:
                    raise HeartbeatPayloadDataError("invalid skill length")
                parsed_skills.append(_decode_text(raw_skills[offset:offset + length], MAX_SKILL_BYTES))
                offset += length
            if offset != len(raw_skills):
                raise HeartbeatPayloadDataError("trailing skills bytes")
            skills = tuple(parsed_skills)

        cognitive_profile: tuple[tuple[str, int | float], ...] | None = None
        if 7 in values:
            raw_profile = values[7]
            if not raw_profile or raw_profile[0] > MAX_PROFILE_ENTRIES:
                raise HeartbeatPayloadDataError("invalid cognitive profile encoding")
            entry_count = raw_profile[0]
            offset = 1
            parsed_profile: list[tuple[str, int | float]] = []
            previous_key: bytes | None = None
            for _ in range(entry_count):
                if len(raw_profile) - offset < 2:
                    raise HeartbeatPayloadDataError("truncated cognitive profile")
                key_len = int.from_bytes(raw_profile[offset:offset + 2], "big")
                offset += 2
                if key_len > MAX_PROFILE_KEY_BYTES or len(raw_profile) - offset < key_len + 9:
                    raise HeartbeatPayloadDataError("invalid cognitive profile key")
                key_raw = raw_profile[offset:offset + key_len]
                key = _decode_text(key_raw, MAX_PROFILE_KEY_BYTES)
                offset += key_len
                if previous_key is not None and key_raw <= previous_key:
                    raise HeartbeatPayloadDataError("noncanonical cognitive profile")
                number = _decode_tagged_number(raw_profile[offset:offset + 9])
                offset += 9
                parsed_profile.append((key, number))
                previous_key = key_raw
            if offset != len(raw_profile):
                raise HeartbeatPayloadDataError("trailing cognitive profile bytes")
            cognitive_profile = tuple(parsed_profile)

        parsed = cls(
            block_height=block_height,
            region=region,
            cost_per_hour=cost_per_hour,
            credit_score=credit_score,
            passports=passports,
            skills=skills,
            cognitive_profile=cognitive_profile,
        )
        if parsed.canonical_bytes() != raw:
            raise HeartbeatPayloadDataError("noncanonical observations")
        return parsed


@dataclass(frozen=True)
class HeartbeatPayloadV2:
    """Canonical V2 data; matching a record is structural, never authorization."""

    authority_source_digest: bytes
    principal_digest: bytes
    principal_id: bytes
    principal_generation: int
    policy_root: bytes
    policy_version: int
    authority_epoch: int
    node_id: str
    body_public_key: bytes
    m2_nonce: bytes
    m2_issued_at: int
    m2_expires_at: int
    observations_v1: HeartbeatObservationsV1

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _fixed_bytes(self.authority_source_digest, 32)
        _fixed_bytes(self.principal_digest, 32)
        _fixed_bytes(self.principal_id, 32, nonzero=True)
        _uint(self.principal_generation, UINT64_MAX, "principal generation", positive=True)
        _fixed_bytes(self.policy_root, 32, nonzero=True)
        _uint(self.policy_version, UINT64_MAX, "policy version", positive=True)
        _uint(self.authority_epoch, UINT64_MAX, "authority epoch", positive=True)
        _node_id_bytes(self.node_id)
        _fixed_bytes(self.body_public_key, 64)
        _fixed_bytes(self.m2_nonce, 16, nonzero=True)
        _uint(self.m2_issued_at, MAX_M2_TIMESTAMP, "M2 issued at")
        _uint(self.m2_expires_at, MAX_M2_TIMESTAMP, "M2 expires at")
        if self.m2_expires_at <= self.m2_issued_at:
            raise HeartbeatPayloadDataError("invalid M2 time window")
        if self.m2_expires_at - self.m2_issued_at > MAX_M2_LIFETIME_SECONDS:
            raise HeartbeatPayloadDataError("M2 lifetime exceeds bound")
        if type(self.observations_v1) is not HeartbeatObservationsV1:
            raise HeartbeatPayloadDataError("invalid observations record")
        self.observations_v1.canonical_bytes()

    def _field_values(self) -> tuple[bytes, ...]:
        self.validate()
        return (
            self.authority_source_digest,
            self.principal_digest,
            self.principal_id,
            self.principal_generation.to_bytes(8, "big"),
            self.policy_root,
            self.policy_version.to_bytes(8, "big"),
            self.authority_epoch.to_bytes(8, "big"),
            _node_id_bytes(self.node_id),
            self.body_public_key,
            self.m2_nonce,
            self.m2_issued_at.to_bytes(8, "big"),
            self.m2_expires_at.to_bytes(8, "big"),
            self.observations_v1.canonical_bytes(),
        )

    def canonical_bytes(self) -> bytes:
        encoded = bytearray(PAYLOAD_DOMAIN)
        encoded.extend(PAYLOAD_FIELD_COUNT.to_bytes(2, "big"))
        for field_id, value in enumerate(self._field_values(), start=1):
            encoded.extend(_tlv(field_id, value))
        if len(encoded) > MAX_PAYLOAD_BYTES:
            raise HeartbeatPayloadDataError("payload exceeds encoding bound")
        return bytes(encoded)

    @property
    def payload_text(self) -> str:
        return PAYLOAD_TEXT_PREFIX + self.canonical_bytes().hex()

    @property
    def digest(self) -> bytes:
        """SHA-256 of the exact canonical ASCII payload text."""
        return hashlib.sha256(self.payload_text.encode("ascii")).digest()

    @property
    def canonical_binary_digest(self) -> bytes:
        """SHA-256 of the canonical binary frame; distinct from ``digest``."""
        return hashlib.sha256(self.canonical_bytes()).digest()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "HeartbeatPayloadV2":
        fields = _read_tlvs(
            raw,
            domain=PAYLOAD_DOMAIN,
            maximum=MAX_PAYLOAD_BYTES,
            min_fields=PAYLOAD_FIELD_COUNT,
            max_fields=PAYLOAD_FIELD_COUNT,
            exact_fields=PAYLOAD_FIELD_COUNT,
        )
        values = tuple(value for _, value in fields)
        expected_lengths = (32, 32, 32, 8, 32, 8, 8, None, 64, 16, 8, 8, None)
        for value, expected in zip(values, expected_lengths, strict=True):
            if expected is not None and len(value) != expected:
                raise HeartbeatPayloadDataError("invalid field width")
        node_id = _decode_text(values[7], MAX_NODE_ID_BYTES)
        observations = HeartbeatObservationsV1.from_bytes(values[12])
        parsed = cls(
            authority_source_digest=values[0],
            principal_digest=values[1],
            principal_id=values[2],
            principal_generation=int.from_bytes(values[3], "big"),
            policy_root=values[4],
            policy_version=int.from_bytes(values[5], "big"),
            authority_epoch=int.from_bytes(values[6], "big"),
            node_id=node_id,
            body_public_key=values[8],
            m2_nonce=values[9],
            m2_issued_at=int.from_bytes(values[10], "big"),
            m2_expires_at=int.from_bytes(values[11], "big"),
            observations_v1=observations,
        )
        if parsed.canonical_bytes() != raw:
            raise HeartbeatPayloadDataError("noncanonical payload encoding")
        return parsed

    @classmethod
    def from_payload_text(cls, text: str) -> "HeartbeatPayloadV2":
        if (
            type(text) is not str
            or len(text) > MAX_PAYLOAD_TEXT_CHARS
            or len(text) < len(PAYLOAD_TEXT_PREFIX)
            or not text.startswith(PAYLOAD_TEXT_PREFIX)
        ):
            raise HeartbeatPayloadDataError("invalid payload text")
        hex_text = text[len(PAYLOAD_TEXT_PREFIX):]
        if len(hex_text) % 2 or any(ch not in "0123456789abcdef" for ch in hex_text):
            raise HeartbeatPayloadDataError("invalid payload text")
        if len(hex_text) // 2 > MAX_PAYLOAD_BYTES:
            raise HeartbeatPayloadDataError("payload text exceeds bound")
        try:
            raw = bytes.fromhex(hex_text)
        except ValueError:
            raise HeartbeatPayloadDataError("invalid payload text") from None
        return cls.from_bytes(raw)

    def matches_record_data(
        self,
        record: HeartbeatPrincipalV1,
        authority_source_digest: bytes,
        m2_nonce: bytes,
        m2_issued_at: int,
        m2_expires_at: int,
    ) -> bool:
        """Compare data values only; this does not authenticate or authorize."""
        if type(record) is not HeartbeatPrincipalV1:
            return False
        try:
            self.validate()
            authority_source_digest = _fixed_bytes(authority_source_digest, 32)
            m2_nonce = _fixed_bytes(m2_nonce, 16, nonzero=True)
            m2_issued_at = _uint(m2_issued_at, MAX_M2_TIMESTAMP, "M2 issued at")
            m2_expires_at = _uint(m2_expires_at, MAX_M2_TIMESTAMP, "M2 expires at")
            if (
                m2_expires_at <= m2_issued_at
                or m2_expires_at - m2_issued_at > MAX_M2_LIFETIME_SECONDS
            ):
                return False
            record_bytes = record.canonical_bytes()
            canonical_record = HeartbeatPrincipalV1.from_bytes(record_bytes)
            if canonical_record != record:
                return False
            derived_node_commitment = node_id_commitment(
                self.node_id,
                host_domain=record.host_domain,
                service_domain=record.service_domain,
            )
            derived_principal_id = principal_id_commitment(
                host_domain=record.host_domain,
                service_domain=record.service_domain,
                node_id_commitment=derived_node_commitment,
            )
        except (
            AttributeError,
            HeartbeatPayloadDataError,
            HeartbeatPrincipalDataError,
            TypeError,
            ValueError,
        ):
            return False
        return (
            self.authority_source_digest == authority_source_digest
            and self.principal_digest == hashlib.sha256(record_bytes).digest()
            and self.principal_id == record.principal_id == derived_principal_id
            and self.principal_generation == record.principal_generation
            and self.policy_root == record.policy_root
            and self.policy_version == record.policy_version
            and self.authority_epoch == record.authority_epoch
            and self.node_id != ""
            and record.node_id_commitment == derived_node_commitment
            and self.body_public_key == record.body_public_key
            and self.m2_nonce == m2_nonce
            and self.m2_issued_at == m2_issued_at
            and self.m2_expires_at == m2_expires_at
        )
