"""Canonical VAMS gateway request-authentication envelope (M2.1).

M2.3 applies this contract through the root gateway's closed route policy. The
existing gateway administrator trust anchor remains the configured
``GATEWAY_ADMIN_DID`` and its embedded secp256k1 public key.

In live modes the authenticated HTTP semantics begin at the output of the
pinned Envoy ingress, after its reviewed RFC 9112 framing and normalization
boundary. The envelope still binds the forwarded method, canonical target and
query, exact decoded body bytes, audience, signer/key, nonce, time bounds,
algorithm, and version. Ingress normalization never permits duplicate M2
headers or conflicting authenticated values.
"""

from __future__ import annotations

import hashlib
import os
import re
import struct
import threading
import time
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Protocol
from urllib.parse import unquote_to_bytes

from fastapi import HTTPException, Request

from neuron.runtime_safety import (
    LiveModeSafetyError,
    RuntimeConfigurationError,
    RuntimePolicy,
    load_runtime_policy,
)
from neuron.secp256k1 import PUBLIC_KEY_BYTES, SIGNATURE_BYTES, verify_message


AUTH_VERSION = "1"
AUTH_ALGORITHM = "secp256k1-ecdsa-sha256"
AUTH_AUDIENCE_VARIABLE = "GATEWAY_AUTH_AUDIENCE"
AUTH_MAX_LIFETIME_SECONDS = 300
AUTH_MAX_FUTURE_SKEW_SECONDS = 300
AUTH_MAX_PATH_BYTES = 2_048
AUTH_MAX_QUERY_BYTES = 8_192
AUTH_MAX_BODY_BYTES = 1_048_576
AUTH_MAX_HEADER_BYTES = 4_096
AUTH_MAX_REPLAY_ENTRIES = 10_000
AUTH_DOMAIN = b"VAMS:GATEWAY:REQUEST-AUTH:v1\x00"

AUTH_HEADERS = {
    "version": b"x-vams-auth-version",
    "algorithm": b"x-vams-auth-algorithm",
    "audience": b"x-vams-auth-audience",
    "signer": b"x-vams-auth-signer",
    "nonce": b"x-vams-auth-nonce",
    "issued_at": b"x-vams-auth-issued-at",
    "expires_at": b"x-vams-auth-expires-at",
    "signature": b"x-vams-auth-signature",
}
LEGACY_AUTH_HEADERS = frozenset(
    {b"x-vams-did", b"x-vams-signature", b"x-vams-timestamp"}
)

_TOKEN_RE = re.compile(rb"[A-Z]+")
_AUDIENCE_RE = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,126}[a-z0-9])?")
_LOWER_HEX_32_RE = re.compile(r"[0-9a-f]{32}")
_LOWER_HEX_128_RE = re.compile(r"[0-9a-f]{128}")
_DECIMAL_RE = re.compile(r"0|[1-9][0-9]{0,18}")
_HEX = b"0123456789ABCDEF"
_UNRESERVED = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


class GatewayAuthenticationError(ValueError):
    """Sanitized authentication failure safe for an HTTP response or log."""

    def __init__(self, code: str, component: str = "request envelope") -> None:
        self.code = code
        self.component = component
        super().__init__(
            f"gateway request authentication failed: {component} ({code})"
        )


class Clock(Protocol):
    def now(self) -> int: ...


class SystemClock:
    def now(self) -> int:
        return int(time.time())


class KeyStatus(str, Enum):
    AVAILABLE = "available"
    UNKNOWN = "unknown"
    REVOKED = "revoked"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class KeyResolution:
    status: KeyStatus
    public_key: bytes | None = None

    def __post_init__(self) -> None:
        if self.status is KeyStatus.AVAILABLE:
            if not isinstance(self.public_key, bytes) or len(self.public_key) != PUBLIC_KEY_BYTES:
                raise ValueError("available key resolution requires a 64-byte key")
        elif self.public_key is not None:
            raise ValueError("non-available key resolution cannot contain key material")


class KeyResolver(Protocol):
    def resolve(self, signer: str) -> KeyResolution: ...


class ConfiguredAdminDIDResolver:
    """Resolve only the existing configured administrator DID trust anchor."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        source = os.environ if environ is None else environ
        configured = source.get("GATEWAY_ADMIN_DID")
        try:
            if configured is not None:
                _public_key_from_did(configured)
        except GatewayAuthenticationError:
            configured = None
        self._configured_did = configured

    def resolve(self, signer: str) -> KeyResolution:
        if self._configured_did is None:
            return KeyResolution(KeyStatus.UNAVAILABLE)
        if signer != self._configured_did:
            return KeyResolution(KeyStatus.UNKNOWN)
        try:
            return KeyResolution(KeyStatus.AVAILABLE, _public_key_from_did(signer))
        except GatewayAuthenticationError:
            return KeyResolution(KeyStatus.UNAVAILABLE)


class ReplayOutcome(str, Enum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REVOKED = "revoked"
    UNAVAILABLE = "unavailable"
    STORAGE_FAILURE = "storage_failure"


@dataclass(frozen=True)
class ReplayNamespace:
    auth_version: str
    audience: str
    signer_digest: bytes
    nonce: bytes

    def __post_init__(self) -> None:
        if self.auth_version != AUTH_VERSION:
            raise ValueError("replay authentication version is unsupported")
        if not isinstance(self.audience, str) or not self.audience:
            raise ValueError("replay audience is required")
        if not isinstance(self.signer_digest, bytes) or len(self.signer_digest) != 32:
            raise ValueError("replay signer digest must be 32 bytes")
        if not isinstance(self.nonce, bytes) or len(self.nonce) != 16:
            raise ValueError("replay nonce must be 16 bytes")


class ReplayStore(Protocol):
    def reserve_and_consume(
        self, namespace: ReplayNamespace, *, expires_at: int, now: int
    ) -> ReplayOutcome: ...


class ProcessLocalReplayStore:
    """Bounded deterministic test double; forbidden in every live mode."""

    def __init__(
        self,
        policy: RuntimePolicy,
        *,
        max_entries: int = AUTH_MAX_REPLAY_ENTRIES,
    ) -> None:
        observed = load_runtime_policy()
        if policy != observed:
            raise RuntimeConfigurationError(
                "process-local gateway replay policy does not match the effective "
                "runtime environment"
            )
        if observed.is_live:
            raise LiveModeSafetyError(
                "process-local gateway replay storage is forbidden when "
                f"VAMS_ENV={observed.mode.value}"
            )
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("replay max_entries must be a positive integer")
        self._max_entries = max_entries
        self._entries: dict[ReplayNamespace, int] = {}
        self._lock = threading.Lock()

    def reserve_and_consume(
        self, namespace: ReplayNamespace, *, expires_at: int, now: int
    ) -> ReplayOutcome:
        if type(expires_at) is not int or type(now) is not int:
            return ReplayOutcome.STORAGE_FAILURE
        with self._lock:
            expired = [key for key, expiry in self._entries.items() if expiry <= now]
            for key in expired:
                del self._entries[key]
            if namespace in self._entries:
                return ReplayOutcome.DUPLICATE
            if len(self._entries) >= self._max_entries:
                return ReplayOutcome.STORAGE_FAILURE
            self._entries[namespace] = expires_at
            return ReplayOutcome.ACCEPTED


@dataclass(frozen=True)
class GatewayAuthEnvelope:
    version: str
    algorithm: str
    method: bytes
    raw_path: bytes
    raw_query: bytes
    body_sha256: bytes
    audience: str
    signer: str
    nonce: bytes
    issued_at: int
    expires_at: int

    def __post_init__(self) -> None:
        if self.version != AUTH_VERSION:
            raise GatewayAuthenticationError("unsupported_version")
        if self.algorithm != AUTH_ALGORITHM:
            raise GatewayAuthenticationError("unsupported_algorithm")
        _validate_method(self.method)
        _validate_raw_path(self.raw_path)
        _validate_raw_query(self.raw_query)
        if not isinstance(self.body_sha256, bytes) or len(self.body_sha256) != 32:
            raise GatewayAuthenticationError("malformed_body_digest")
        _validate_audience(self.audience)
        _public_key_from_did(self.signer)
        if not isinstance(self.nonce, bytes) or len(self.nonce) != 16 or not any(self.nonce):
            raise GatewayAuthenticationError("malformed_nonce")
        _validate_timestamp_type(self.issued_at)
        _validate_timestamp_type(self.expires_at)

    def canonical_bytes(self) -> bytes:
        """Return a closed, tagged, length-prefixed canonical wire message."""

        fields = (
            self.version.encode("ascii"),
            self.algorithm.encode("ascii"),
            self.method,
            self.raw_path,
            self.raw_query,
            self.body_sha256,
            self.audience.encode("ascii"),
            self.signer.encode("ascii"),
            self.nonce,
            self.issued_at.to_bytes(8, "big"),
            self.expires_at.to_bytes(8, "big"),
        )
        encoded = bytearray(AUTH_DOMAIN)
        encoded.extend(struct.pack(">H", len(fields)))
        for field_id, value in enumerate(fields, start=1):
            encoded.extend(struct.pack(">BI", field_id, len(value)))
            encoded.extend(value)
        return bytes(encoded)


@dataclass(frozen=True)
class AuthenticatedGatewayRequest:
    envelope: GatewayAuthEnvelope
    raw_body: bytes


class GatewayRequestAuthenticator:
    """Authenticate a real ASGI request without changing its body bytes."""

    def __init__(
        self,
        *,
        expected_audience: str,
        clock: Clock,
        key_resolver: KeyResolver,
        replay_store: ReplayStore,
    ) -> None:
        _validate_audience(expected_audience)
        self._expected_audience = expected_audience
        self._clock = clock
        self._key_resolver = key_resolver
        self._replay_store = replay_store

    async def authenticate(self, request: Request) -> AuthenticatedGatewayRequest:
        headers = _read_auth_headers(request.scope)
        raw_body = await request.body()
        if len(raw_body) > AUTH_MAX_BODY_BYTES:
            raise GatewayAuthenticationError("body_too_large")
        envelope = _build_envelope(request.scope, headers, raw_body)
        now = self._clock.now()
        _validate_time_window(envelope, now)
        if envelope.audience != self._expected_audience:
            raise GatewayAuthenticationError("audience_mismatch")

        try:
            resolution = self._key_resolver.resolve(envelope.signer)
        except Exception as exc:
            raise GatewayAuthenticationError(
                "key_unavailable", "key resolver"
            ) from exc
        if resolution.status is KeyStatus.UNKNOWN:
            raise GatewayAuthenticationError("unknown_signer", "key resolver")
        if resolution.status is KeyStatus.REVOKED:
            raise GatewayAuthenticationError("revoked_signer", "key resolver")
        if resolution.status is KeyStatus.UNAVAILABLE:
            raise GatewayAuthenticationError("key_unavailable", "key resolver")
        if resolution.status is not KeyStatus.AVAILABLE or resolution.public_key is None:
            raise GatewayAuthenticationError("invalid_key_outcome", "key resolver")

        signature = _parse_signature(headers["signature"])
        if not verify_message(
            resolution.public_key, envelope.canonical_bytes(), signature
        ):
            raise GatewayAuthenticationError("invalid_signature", "signature verifier")

        namespace = ReplayNamespace(
            auth_version=envelope.version,
            audience=envelope.audience,
            signer_digest=hashlib.sha256(envelope.signer.encode("ascii")).digest(),
            nonce=envelope.nonce,
        )
        try:
            outcome = self._replay_store.reserve_and_consume(
                namespace, expires_at=envelope.expires_at, now=now
            )
        except Exception as exc:
            raise GatewayAuthenticationError(
                "storage_failure", "replay store"
            ) from exc
        if outcome is not ReplayOutcome.ACCEPTED:
            code = {
                ReplayOutcome.DUPLICATE: "duplicate_nonce",
                ReplayOutcome.REVOKED: "revoked_nonce",
                ReplayOutcome.UNAVAILABLE: "replay_unavailable",
                ReplayOutcome.STORAGE_FAILURE: "storage_failure",
            }.get(outcome, "invalid_replay_outcome")
            raise GatewayAuthenticationError(code, "replay store")
        return AuthenticatedGatewayRequest(envelope=envelope, raw_body=raw_body)


def gateway_auth_dependency(
    authenticator: GatewayRequestAuthenticator,
) -> Callable[[Request], object]:
    """Create a stable FastAPI dependency for M2.3 route integration."""

    async def dependency(request: Request) -> AuthenticatedGatewayRequest:
        try:
            return await authenticator.authenticate(request)
        except GatewayAuthenticationError as exc:
            status = 503 if exc.code in {
                "key_unavailable",
                "replay_unavailable",
                "storage_failure",
            } else 401
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    return dependency


def configured_gateway_audience(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    audience = source.get(AUTH_AUDIENCE_VARIABLE)
    if audience is None:
        raise GatewayAuthenticationError("missing_audience_configuration")
    _validate_audience(audience)
    return audience


def _build_envelope(
    scope: Mapping[str, object], headers: Mapping[str, bytes], raw_body: bytes
) -> GatewayAuthEnvelope:
    method = scope.get("method")
    raw_path = scope.get("raw_path")
    raw_query = scope.get("query_string", b"")
    if not isinstance(method, str):
        raise GatewayAuthenticationError("malformed_method")
    try:
        method_bytes = method.encode("ascii")
    except UnicodeEncodeError as exc:
        raise GatewayAuthenticationError("malformed_method") from exc
    if not isinstance(raw_path, bytes) or not isinstance(raw_query, bytes):
        raise GatewayAuthenticationError("malformed_request_target")
    return GatewayAuthEnvelope(
        version=_decode_ascii(headers["version"], "version"),
        algorithm=_decode_ascii(headers["algorithm"], "algorithm"),
        method=method_bytes,
        raw_path=raw_path,
        raw_query=raw_query,
        body_sha256=hashlib.sha256(raw_body).digest(),
        audience=_decode_ascii(headers["audience"], "audience"),
        signer=_decode_ascii(headers["signer"], "signer"),
        nonce=_parse_nonce(headers["nonce"]),
        issued_at=_parse_timestamp(headers["issued_at"], "issued_at"),
        expires_at=_parse_timestamp(headers["expires_at"], "expires_at"),
    )


def _read_auth_headers(scope: Mapping[str, object]) -> dict[str, bytes]:
    raw_headers = scope.get("headers")
    if not isinstance(raw_headers, list):
        raise GatewayAuthenticationError("malformed_headers")
    found: dict[str, list[bytes]] = {name: [] for name in AUTH_HEADERS}
    total = 0
    for pair in raw_headers:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise GatewayAuthenticationError("malformed_headers")
        name, value = pair
        if not isinstance(name, bytes) or not isinstance(value, bytes):
            raise GatewayAuthenticationError("malformed_headers")
        lowered = name.lower()
        matched = False
        for logical, wire_name in AUTH_HEADERS.items():
            if lowered == wire_name:
                found[logical].append(value)
                total += len(name) + len(value)
                matched = True
        if lowered in LEGACY_AUTH_HEADERS:
            raise GatewayAuthenticationError("conflicting_legacy_auth_header")
        if lowered.startswith(b"x-vams-auth-") and not matched:
            raise GatewayAuthenticationError("unknown_auth_header")
    if total > AUTH_MAX_HEADER_BYTES:
        raise GatewayAuthenticationError("auth_headers_too_large")
    result: dict[str, bytes] = {}
    for logical, values in found.items():
        if not values:
            raise GatewayAuthenticationError(f"missing_{logical}")
        if len(values) != 1:
            raise GatewayAuthenticationError(f"duplicate_{logical}")
        result[logical] = values[0]
    return result


def _validate_method(method: bytes) -> None:
    if not isinstance(method, bytes) or not _TOKEN_RE.fullmatch(method):
        raise GatewayAuthenticationError("malformed_method")
    if method not in {b"GET", b"POST", b"PUT", b"PATCH", b"DELETE"}:
        raise GatewayAuthenticationError("unsupported_method")


def _validate_raw_path(raw_path: bytes) -> None:
    if not isinstance(raw_path, bytes) or not (1 <= len(raw_path) <= AUTH_MAX_PATH_BYTES):
        raise GatewayAuthenticationError("malformed_path")
    if not raw_path.startswith(b"/") or raw_path.startswith(b"//"):
        raise GatewayAuthenticationError("malformed_path")
    if b"?" in raw_path or b"#" in raw_path or b"\\" in raw_path or b"://" in raw_path:
        raise GatewayAuthenticationError("malformed_path")
    _validate_percent_encoding(raw_path, component="path", reject_escaped_unreserved=True)
    try:
        decoded = unquote_to_bytes(raw_path).decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise GatewayAuthenticationError("malformed_path") from exc
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in decoded):
        raise GatewayAuthenticationError("malformed_path")
    if unicodedata.normalize("NFC", decoded) != decoded:
        raise GatewayAuthenticationError("noncanonical_path")
    if any(segment in {".", ".."} for segment in decoded.split("/")):
        raise GatewayAuthenticationError("path_traversal")
    if b"//" in raw_path:
        raise GatewayAuthenticationError("malformed_path")


def _validate_raw_query(raw_query: bytes) -> None:
    if not isinstance(raw_query, bytes) or len(raw_query) > AUTH_MAX_QUERY_BYTES:
        raise GatewayAuthenticationError("malformed_query")
    if not raw_query:
        return
    if b"#" in raw_query or b";" in raw_query:
        raise GatewayAuthenticationError("malformed_query")
    _validate_percent_encoding(raw_query, component="query", reject_escaped_unreserved=True)
    for part in raw_query.split(b"&"):
        if not part:
            raise GatewayAuthenticationError("malformed_query")
        name, separator, value = part.partition(b"=")
        if not name:
            raise GatewayAuthenticationError("malformed_query")
        for item in (name, value if separator else b""):
            try:
                decoded = unquote_to_bytes(item).decode("utf-8", "strict")
            except UnicodeDecodeError as exc:
                raise GatewayAuthenticationError("malformed_query") from exc
            if unicodedata.normalize("NFC", decoded) != decoded:
                raise GatewayAuthenticationError("noncanonical_query")


def _validate_percent_encoding(
    value: bytes, *, component: str, reject_escaped_unreserved: bool
) -> None:
    index = 0
    while index < len(value):
        byte = value[index]
        if byte >= 0x80 or byte < 0x20 or byte == 0x7F:
            raise GatewayAuthenticationError(f"malformed_{component}")
        if byte != 0x25:
            index += 1
            continue
        if index + 2 >= len(value):
            raise GatewayAuthenticationError(f"malformed_{component}")
        pair = value[index + 1 : index + 3]
        if pair[0] not in _HEX or pair[1] not in _HEX:
            raise GatewayAuthenticationError(f"malformed_{component}")
        decoded = int(pair, 16)
        if decoded in {0x2F, 0x5C} or (
            reject_escaped_unreserved and decoded in _UNRESERVED
        ):
            raise GatewayAuthenticationError(f"noncanonical_{component}")
        index += 3


def _validate_audience(audience: str) -> None:
    if not isinstance(audience, str) or not _AUDIENCE_RE.fullmatch(audience):
        raise GatewayAuthenticationError("malformed_audience")


def _public_key_from_did(signer: str) -> bytes:
    if not isinstance(signer, str) or not signer.startswith("did:key:"):
        raise GatewayAuthenticationError("malformed_signer")
    key_hex = signer[8:]
    if not _LOWER_HEX_128_RE.fullmatch(key_hex):
        raise GatewayAuthenticationError("malformed_signer")
    return bytes.fromhex(key_hex)


def _parse_nonce(value: bytes) -> bytes:
    rendered = _decode_ascii(value, "nonce")
    if not _LOWER_HEX_32_RE.fullmatch(rendered):
        raise GatewayAuthenticationError("malformed_nonce")
    nonce = bytes.fromhex(rendered)
    if not any(nonce):
        raise GatewayAuthenticationError("malformed_nonce")
    return nonce


def _parse_timestamp(value: bytes, name: str) -> int:
    rendered = _decode_ascii(value, name)
    if not _DECIMAL_RE.fullmatch(rendered):
        raise GatewayAuthenticationError(f"malformed_{name}")
    parsed = int(rendered)
    _validate_timestamp_type(parsed)
    return parsed


def _validate_timestamp_type(value: int) -> None:
    if type(value) is not int or not (0 <= value <= (1 << 63) - 1):
        raise GatewayAuthenticationError("malformed_timestamp")


def _validate_time_window(envelope: GatewayAuthEnvelope, now: int) -> None:
    _validate_timestamp_type(now)
    if envelope.expires_at <= envelope.issued_at:
        raise GatewayAuthenticationError("invalid_time_window")
    if envelope.expires_at - envelope.issued_at > AUTH_MAX_LIFETIME_SECONDS:
        raise GatewayAuthenticationError("lifetime_too_long")
    if envelope.issued_at > now + AUTH_MAX_FUTURE_SKEW_SECONDS:
        raise GatewayAuthenticationError("issued_in_future")
    if envelope.expires_at <= now:
        raise GatewayAuthenticationError("expired")


def _parse_signature(value: bytes) -> bytes:
    rendered = _decode_ascii(value, "signature")
    if not _LOWER_HEX_128_RE.fullmatch(rendered):
        raise GatewayAuthenticationError("malformed_signature")
    signature = bytes.fromhex(rendered)
    if len(signature) != SIGNATURE_BYTES:
        raise GatewayAuthenticationError("malformed_signature")
    return signature


def _decode_ascii(value: bytes, name: str) -> str:
    try:
        return value.decode("ascii", "strict")
    except UnicodeDecodeError as exc:
        raise GatewayAuthenticationError(f"malformed_{name}") from exc
