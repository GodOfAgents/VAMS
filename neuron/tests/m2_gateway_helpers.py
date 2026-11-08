"""Synthetic M2 gateway signing helpers used only by local tests."""

from __future__ import annotations

import hashlib
import json
import time

from cryptography.hazmat.primitives.asymmetric import ec

from gateway.request_auth import AUTH_ALGORITHM, AUTH_VERSION, GatewayAuthEnvelope
from neuron.secp256k1 import public_key_bytes, sign_message


AUDIENCE = "vams.gateway.test"
PRIVATE_KEY = ec.derive_private_key(1, ec.SECP256K1())
PUBLIC_KEY = public_key_bytes(PRIVATE_KEY)
SIGNER = "did:key:" + PUBLIC_KEY.hex()


def compact_json(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()


def signed_headers(
    method: str,
    raw_path: str,
    *,
    body: bytes = b"",
    raw_query: str = "",
    nonce: int = 1,
    now: int | None = None,
    issued_at: int | None = None,
    expires_at: int | None = None,
    audience: str = AUDIENCE,
    version: str = AUTH_VERSION,
    algorithm: str = AUTH_ALGORITHM,
) -> dict[str, str]:
    effective_now = int(time.time()) if now is None else now
    effective_issued_at = effective_now if issued_at is None else issued_at
    effective_expires_at = (
        effective_issued_at + 120 if expires_at is None else expires_at
    )
    envelope = GatewayAuthEnvelope(
        version,
        algorithm,
        method.encode("ascii"),
        raw_path.encode("ascii"),
        raw_query.encode("ascii"),
        hashlib.sha256(body).digest(),
        audience,
        SIGNER,
        nonce.to_bytes(16, "big"),
        effective_issued_at,
        effective_expires_at,
    )
    headers = {
        "X-VAMS-Auth-Version": version,
        "X-VAMS-Auth-Algorithm": algorithm,
        "X-VAMS-Auth-Audience": audience,
        "X-VAMS-Auth-Signer": SIGNER,
        "X-VAMS-Auth-Nonce": envelope.nonce.hex(),
        "X-VAMS-Auth-Issued-At": str(envelope.issued_at),
        "X-VAMS-Auth-Expires-At": str(envelope.expires_at),
        "X-VAMS-Auth-Signature": sign_message(
            PRIVATE_KEY, envelope.canonical_bytes()
        ).hex(),
    }
    if method in {"POST", "PUT", "PATCH"}:
        headers["Content-Type"] = "application/json"
    return headers
