"""Unsigned, canonical data for a future scoped heartbeat principal.

This module validates record shape and compares request identity fields only.
It does not authenticate an issuer, consult current host policy, establish
enrollment, check revocation, or authorize a request.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


DOMAIN = b"VAMS:GATEWAY:HEARTBEAT-PRINCIPAL:v1\x00"
NODE_ID_DOMAIN = b"VAMS:GATEWAY:NODE-ID:v1\x00"
PRINCIPAL_ID_DOMAIN = b"VAMS:GATEWAY:HEARTBEAT-PRINCIPAL-ID:v1\x00"
PRINCIPAL_FIELD_ORDER = (
    "principal_id",
    "node_id_commitment",
    "m2_signer_did",
    "m2_signer_public_key",
    "certificate_fingerprint",
    "body_public_key",
    "host_domain",
    "service_domain",
    "audience",
    "method",
    "path",
    "query",
    "policy_root",
    "policy_version",
    "authority_epoch",
    "principal_generation",
    "not_before",
    "expires_at",
)
PRINCIPAL_FIELD_IDS = {name: index for index, name in enumerate(PRINCIPAL_FIELD_ORDER, 1)}
FIELD_COUNT = len(PRINCIPAL_FIELD_ORDER)
MAX_NODE_ID_BYTES = 256
MAX_AUDIENCE_BYTES = 128
MAX_FIELD_BYTES = 256
MAX_ENCODING_BYTES = 1024
UINT64_MAX = (1 << 64) - 1

_DID_KEY_PREFIX = "did:key:"
_LOWER_HEX_128_RE = re.compile(r"[0-9a-f]{128}", re.ASCII)
_AUDIENCE_RE = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,126}[a-z0-9])?", re.ASCII)
_BYTE_FIELDS = {
    "principal_id": (32, True),
    "node_id_commitment": (32, True),
    "m2_signer_public_key": (64, False),
    "certificate_fingerprint": (32, True),
    "body_public_key": (64, False),
    "host_domain": (32, True),
    "service_domain": (32, True),
    "query": (0, False),
    "policy_root": (32, True),
}
_INTEGER_FIELDS = (
    "policy_version",
    "authority_epoch",
    "principal_generation",
    "not_before",
    "expires_at",
)


class HeartbeatPrincipalDataError(ValueError):
    """Malformed or noncanonical unsigned principal data."""


def _did_public_key(signer_did: str) -> bytes:
    if (
        type(signer_did) is not str
        or len(signer_did) != len(_DID_KEY_PREFIX) + 128
        or not signer_did.startswith(_DID_KEY_PREFIX)
    ):
        raise HeartbeatPrincipalDataError("invalid M2 signer DID")
    key_hex = signer_did[len(_DID_KEY_PREFIX):]
    if _LOWER_HEX_128_RE.fullmatch(key_hex) is None:
        raise HeartbeatPrincipalDataError("invalid M2 signer DID")
    return bytes.fromhex(key_hex)


def _audience_bytes(audience: str) -> bytes:
    if type(audience) is not str or _AUDIENCE_RE.fullmatch(audience) is None:
        raise HeartbeatPrincipalDataError("invalid M2 audience")
    encoded = audience.encode("ascii")
    if len(encoded) > MAX_AUDIENCE_BYTES:
        raise HeartbeatPrincipalDataError("invalid M2 audience")
    return encoded


def _nonzero_bytes32(value: object, label: str) -> bytes:
    if type(value) is not bytes or len(value) != 32 or not any(value):
        raise HeartbeatPrincipalDataError("invalid " + label)
    return value


def node_id_commitment(
    node_id: str,
    *,
    host_domain: bytes,
    service_domain: bytes,
) -> bytes:
    """Commit to host, service, and exact UTF-8 node ID without normalization."""
    host_domain = _nonzero_bytes32(host_domain, "host domain")
    service_domain = _nonzero_bytes32(service_domain, "service domain")
    if type(node_id) is not str or not node_id or len(node_id) > MAX_NODE_ID_BYTES:
        raise HeartbeatPrincipalDataError("invalid node ID")
    try:
        encoded = node_id.encode("utf-8", "strict")
    except UnicodeEncodeError:
        raise HeartbeatPrincipalDataError("invalid node ID") from None
    if not encoded or len(encoded) > MAX_NODE_ID_BYTES:
        raise HeartbeatPrincipalDataError("invalid node ID")
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise HeartbeatPrincipalDataError("invalid node ID")
    return hashlib.sha256(
        NODE_ID_DOMAIN
        + host_domain
        + service_domain
        + len(encoded).to_bytes(2, "big")
        + encoded
    ).digest()


def principal_id_commitment(
    *,
    host_domain: bytes,
    service_domain: bytes,
    node_id_commitment: bytes,
) -> bytes:
    """Derive issuer-free identity from the scoped host/service/node tuple."""
    host_domain = _nonzero_bytes32(host_domain, "host domain")
    service_domain = _nonzero_bytes32(service_domain, "service domain")
    node_id_commitment = _nonzero_bytes32(node_id_commitment, "node ID commitment")
    return hashlib.sha256(
        PRINCIPAL_ID_DOMAIN + host_domain + service_domain + node_id_commitment
    ).digest()


def _uint64(value: object, name: str, *, positive: bool = False) -> int:
    if type(value) is not int or not (0 <= value <= UINT64_MAX):
        raise HeartbeatPrincipalDataError("invalid unsigned integer field")
    if positive and value == 0:
        raise HeartbeatPrincipalDataError("invalid unsigned integer field")
    return value


def _string_bytes(value: object, name: str, expected: str) -> bytes:
    if type(value) is not str or value != expected:
        raise HeartbeatPrincipalDataError("invalid heartbeat route scope")
    return value.encode("ascii")


@dataclass(frozen=True)
class HeartbeatPrincipalV1:
    """Canonical unsigned principal data; not proof of enrollment or authority."""

    principal_id: bytes
    node_id_commitment: bytes
    m2_signer_did: str
    m2_signer_public_key: bytes
    certificate_fingerprint: bytes
    body_public_key: bytes
    host_domain: bytes
    service_domain: bytes
    audience: str
    method: str
    path: str
    query: bytes
    policy_root: bytes
    policy_version: int
    authority_epoch: int
    principal_generation: int
    not_before: int
    expires_at: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for name, (expected_length, must_be_nonzero) in _BYTE_FIELDS.items():
            value = getattr(self, name)
            if type(value) is not bytes or len(value) != expected_length:
                raise HeartbeatPrincipalDataError("invalid principal byte field")
            if must_be_nonzero and not any(value):
                raise HeartbeatPrincipalDataError("missing principal identity field")

        if _did_public_key(self.m2_signer_did) != self.m2_signer_public_key:
            raise HeartbeatPrincipalDataError("M2 DID/key mismatch")
        if self.principal_id != principal_id_commitment(
            host_domain=self.host_domain,
            service_domain=self.service_domain,
            node_id_commitment=self.node_id_commitment,
        ):
            raise HeartbeatPrincipalDataError("principal ID does not match scoped identity")
        _audience_bytes(self.audience)
        _string_bytes(self.method, "method", "POST")
        _string_bytes(self.path, "path", "/heartbeat")
        for name in ("policy_version", "authority_epoch", "principal_generation"):
            _uint64(getattr(self, name), name, positive=True)
        not_before = _uint64(self.not_before, "not_before")
        expires_at = _uint64(self.expires_at, "expires_at")
        if expires_at <= not_before:
            raise HeartbeatPrincipalDataError("invalid validity interval")

    def _field_values(self) -> tuple[bytes, ...]:
        self.validate()
        return (
            self.principal_id,
            self.node_id_commitment,
            self.m2_signer_did.encode("ascii"),
            self.m2_signer_public_key,
            self.certificate_fingerprint,
            self.body_public_key,
            self.host_domain,
            self.service_domain,
            _audience_bytes(self.audience),
            self.method.encode("ascii"),
            self.path.encode("ascii"),
            self.query,
            self.policy_root,
            self.policy_version.to_bytes(8, "big"),
            self.authority_epoch.to_bytes(8, "big"),
            self.principal_generation.to_bytes(8, "big"),
            self.not_before.to_bytes(8, "big"),
            self.expires_at.to_bytes(8, "big"),
        )

    def canonical_bytes(self) -> bytes:
        """Return domain-separated, ordered ID/u16-length/value records."""
        encoded = bytearray(DOMAIN)
        encoded.extend(FIELD_COUNT.to_bytes(2, "big"))
        for field_id, value in enumerate(self._field_values(), start=1):
            if len(value) > MAX_FIELD_BYTES:
                raise HeartbeatPrincipalDataError("principal field exceeds bound")
            encoded.append(field_id)
            encoded.extend(len(value).to_bytes(2, "big"))
            encoded.extend(value)
        if len(encoded) > MAX_ENCODING_BYTES:
            raise HeartbeatPrincipalDataError("principal encoding exceeds bound")
        return bytes(encoded)

    @property
    def digest(self) -> bytes:
        return hashlib.sha256(self.canonical_bytes()).digest()

    def interval_contains(self, now: int) -> bool:
        """Check only encoded time bounds; this is not an active-authority check."""
        now = _uint64(now, "now")
        return self.not_before <= now < self.expires_at

    def matches_request_binding(
        self,
        *,
        node_id: str,
        m2_signer_did: str,
        m2_signer_public_key: bytes,
        certificate_fingerprint: bytes,
        body_public_key: bytes,
        host_domain: bytes,
        service_domain: bytes,
        audience: str,
        method: bytes,
        raw_path: bytes,
        raw_query: bytes,
    ) -> bool:
        """Compare tuple fields only; does not authenticate or authorize them."""
        try:
            supplied_node_commitment = node_id_commitment(
                node_id,
                host_domain=self.host_domain,
                service_domain=self.service_domain,
            )
            supplied_did_key = _did_public_key(m2_signer_did)
            supplied_audience = _audience_bytes(audience)
        except HeartbeatPrincipalDataError:
            return False
        exact_bytes = (
            (m2_signer_public_key, 64),
            (certificate_fingerprint, 32),
            (body_public_key, 64),
            (host_domain, 32),
            (service_domain, 32),
            (method, None),
            (raw_path, None),
            (raw_query, 0),
        )
        if any(type(value) is not bytes or (length is not None and len(value) != length)
               for value, length in exact_bytes):
            return False
        return (
            self.node_id_commitment == supplied_node_commitment
            and self.m2_signer_did == m2_signer_did
            and self.m2_signer_public_key == supplied_did_key == m2_signer_public_key
            and self.certificate_fingerprint == certificate_fingerprint
            and self.body_public_key == body_public_key
            and self.host_domain == host_domain
            and self.service_domain == service_domain
            and self.audience.encode("ascii") == supplied_audience
            and method == b"POST"
            and raw_path == b"/heartbeat"
            and raw_query == b""
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "HeartbeatPrincipalV1":
        if type(raw) is not bytes or len(raw) > MAX_ENCODING_BYTES:
            raise HeartbeatPrincipalDataError("invalid principal encoding")
        prefix_length = len(DOMAIN) + 2
        if len(raw) < prefix_length or not raw.startswith(DOMAIN):
            raise HeartbeatPrincipalDataError("invalid principal encoding")
        count = int.from_bytes(raw[len(DOMAIN):prefix_length], "big")
        if count != FIELD_COUNT:
            raise HeartbeatPrincipalDataError("invalid principal field count")

        values: list[bytes] = []
        offset = prefix_length
        for expected_id in range(1, FIELD_COUNT + 1):
            if len(raw) - offset < 3:
                raise HeartbeatPrincipalDataError("truncated principal field")
            field_id = raw[offset]
            length = int.from_bytes(raw[offset + 1:offset + 3], "big")
            offset += 3
            if field_id != expected_id or length > MAX_FIELD_BYTES:
                raise HeartbeatPrincipalDataError("noncanonical principal field")
            if len(raw) - offset < length:
                raise HeartbeatPrincipalDataError("truncated principal field")
            values.append(raw[offset:offset + length])
            offset += length
        if offset != len(raw):
            raise HeartbeatPrincipalDataError("trailing principal bytes")

        try:
            parsed = cls(
                principal_id=values[0],
                node_id_commitment=values[1],
                m2_signer_did=values[2].decode("ascii", "strict"),
                m2_signer_public_key=values[3],
                certificate_fingerprint=values[4],
                body_public_key=values[5],
                host_domain=values[6],
                service_domain=values[7],
                audience=values[8].decode("ascii", "strict"),
                method=values[9].decode("ascii", "strict"),
                path=values[10].decode("ascii", "strict"),
                query=values[11],
                policy_root=values[12],
                policy_version=int.from_bytes(values[13], "big") if len(values[13]) == 8 else _invalid_integer(),
                authority_epoch=int.from_bytes(values[14], "big") if len(values[14]) == 8 else _invalid_integer(),
                principal_generation=int.from_bytes(values[15], "big") if len(values[15]) == 8 else _invalid_integer(),
                not_before=int.from_bytes(values[16], "big") if len(values[16]) == 8 else _invalid_integer(),
                expires_at=int.from_bytes(values[17], "big") if len(values[17]) == 8 else _invalid_integer(),
            )
        except (UnicodeDecodeError, HeartbeatPrincipalDataError):
            raise HeartbeatPrincipalDataError("invalid principal field value") from None
        if parsed.canonical_bytes() != raw:
            raise HeartbeatPrincipalDataError("noncanonical principal encoding")
        return parsed


def _invalid_integer() -> int:
    raise HeartbeatPrincipalDataError("invalid integer field width")
