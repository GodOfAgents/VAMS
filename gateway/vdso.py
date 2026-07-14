"""Strict FastAPI boundary for the isolated VDSO shadow/canary service."""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections import OrderedDict
from base64 import b64decode
from typing import Annotated, List, Literal, Optional, Protocol

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from neuron.secp256k1 import verify_digest, verify_message
from neuron.vdso.auth import (
    AuthorizationEnvelope,
    AuthorizationError,
    AuthorizationVerifier,
)
from neuron.vdso.keccak import domain_hash
from neuron.vdso.models import (
    AccessMode,
    DomainAuthorityBinding,
    ExecutionTier,
    HostAuthority,
    MAX_OBJECT_ACCESSES,
    ObjectAccess,
    SignatureSuite,
    UnsignedIntent,
)
from neuron.vdso.service import VDSOCanaryService, VDSOServiceError
from neuron.vdso.sidecar import (
    MAX_CIPHERTEXT_BYTES,
    MAX_ENCAPSULATED_KEY_BYTES,
    MAX_RECIPIENTS,
    MAX_WRAPPED_KEY_BYTES,
    EncryptedWitnessSidecar,
    RecipientEnvelope,
)
from neuron.runtime_safety import is_live_environment


HEX32_PATTERN = r"^0x[0-9a-fA-F]{64}$"
HEX_PATTERN = r"^0x(?:[0-9a-fA-F]{2})+$"
AUTH_REPLAY_WINDOW_SECONDS = 300


class ReplayStore(Protocol):
    """Atomic replay claim store; live implementations must be shared."""

    shared: bool

    def check_and_record(self, key: str, now: int, expires_at: int) -> bool:
        """Atomically record a fresh key, returning false for a replay."""


class InMemoryReplayStore:
    """Bounded process-local replay store for local development only."""

    shared = False

    def __init__(self, *, max_entries: int = 8_192) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, int] = OrderedDict()
        self._lock = threading.Lock()

    def check_and_record(self, key: str, now: int, expires_at: int) -> bool:
        with self._lock:
            expired = [item for item, expiry in self._entries.items() if expiry <= now]
            for item in expired:
                del self._entries[item]
            if key in self._entries:
                return False
            if len(self._entries) >= self._max_entries:
                raise RuntimeError("local replay store is full; refusing an unsafe eviction")
            self._entries[key] = expires_at
            return True

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

router = APIRouter(prefix="/v1/vdso", tags=["vdso-canary"])
service = VDSOCanaryService()
replay_store: Optional[ReplayStore] = None
_local_replay_store = InMemoryReplayStore()


def _hex_bytes(value: str, *, length: Optional[int] = None) -> bytes:
    try:
        raw = bytes.fromhex(value[2:] if value.startswith("0x") else value)
    except ValueError as exc:
        raise ValueError("invalid hexadecimal value") from exc
    if length is not None and len(raw) != length:
        raise ValueError(f"hex value must contain exactly {length} bytes")
    return raw


def _hex32(value: str) -> bytes:
    return _hex_bytes(value, length=32)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ObjectAccessRequest(StrictModel):
    object_id: str = Field(pattern=HEX32_PATTERN)
    mode: Literal["read", "consume", "reserve", "accumulate"]
    expected_version: int = Field(ge=0, le=(1 << 64) - 1)
    fencing_token: Optional[int] = Field(default=None, ge=1, le=(1 << 64) - 1)

    def to_domain(self) -> ObjectAccess:
        return ObjectAccess(
            object_id=_hex32(self.object_id),
            mode={
                "read": AccessMode.READ,
                "consume": AccessMode.CONSUME,
                "reserve": AccessMode.RESERVE,
                "accumulate": AccessMode.ACCUMULATE,
            }[self.mode],
            expected_version=self.expected_version,
            fencing_token=self.fencing_token,
        )


class DomainAuthorityBindingRequest(StrictModel):
    state_domain: str = Field(pattern=HEX32_PATTERN)
    host_authority: Literal["polygon-amoy", "cardano-pre-prod"]
    authority_epoch: int = Field(ge=0, le=(1 << 64) - 1)

    def to_domain(self) -> DomainAuthorityBinding:
        return DomainAuthorityBinding(
            state_domain=_hex32(self.state_domain),
            host_authority={
                "polygon-amoy": HostAuthority.POLYGON,
                "cardano-pre-prod": HostAuthority.CARDANO,
            }[self.host_authority],
            authority_epoch=self.authority_epoch,
        )


class UnsignedIntentRequest(StrictModel):
    schema_version: Literal[1]
    actor_root: str = Field(pattern=HEX32_PATTERN)
    binding: DomainAuthorityBindingRequest
    nonce: int = Field(ge=0, le=(1 << 64) - 1)
    valid_until_height: int = Field(ge=0, le=(1 << 64) - 1)
    program_id: str = Field(pattern=HEX32_PATTERN)
    workflow_definition_hash: str = Field(pattern=HEX32_PATTERN)
    accesses: List[ObjectAccessRequest] = Field(
        default_factory=list, max_length=MAX_OBJECT_ACCESSES
    )
    input_commitment: str = Field(pattern=HEX32_PATTERN)
    expected_output_commitment: str = Field(pattern=HEX32_PATTERN)
    evidence_root: str = Field(pattern=HEX32_PATTERN)
    sidecar_root: str = Field(pattern=HEX32_PATTERN)
    signature_suite: Literal["secp256k1", "secp256k1+ml-dsa-65"]
    execution_tier: Literal[0, 1, 2]
    max_execution_units: int = Field(ge=1, le=(1 << 64) - 1)
    max_settlement_cost: int = Field(ge=0, le=(1 << 64) - 1)

    def to_domain(self) -> UnsignedIntent:
        accesses = tuple(access.to_domain() for access in self.accesses)
        return UnsignedIntent(
            schema_version=self.schema_version,
            actor_root=_hex32(self.actor_root),
            binding=self.binding.to_domain(),
            nonce=self.nonce,
            valid_until_height=self.valid_until_height,
            program_id=_hex32(self.program_id),
            workflow_definition_hash=_hex32(self.workflow_definition_hash),
            accesses=accesses,
            input_commitment=_hex32(self.input_commitment),
            expected_output_commitment=_hex32(self.expected_output_commitment),
            evidence_root=_hex32(self.evidence_root),
            sidecar_root=_hex32(self.sidecar_root),
            signature_suite={
                "secp256k1": SignatureSuite.SECP256K1,
                "secp256k1+ml-dsa-65": SignatureSuite.SECP256K1_AND_ML_DSA_65,
            }[self.signature_suite],
            execution_tier=ExecutionTier(self.execution_tier),
            max_execution_units=self.max_execution_units,
            max_settlement_cost=self.max_settlement_cost,
        )


class AuthorizationEnvelopeRequest(StrictModel):
    suite: Literal["secp256k1", "secp256k1+ml-dsa-65"]
    secp256k1_public_key: str = Field(pattern=HEX_PATTERN, max_length=132)
    secp256k1_signature: str = Field(pattern=HEX_PATTERN, max_length=256)
    ml_dsa_65_public_key_b64: Optional[str] = Field(default=None, max_length=4_000)
    ml_dsa_65_signature_b64: Optional[str] = Field(default=None, max_length=8_000)

    def to_domain(self) -> AuthorizationEnvelope:
        try:
            pq_public_key = (
                b64decode(self.ml_dsa_65_public_key_b64, validate=True)
                if self.ml_dsa_65_public_key_b64
                else b""
            )
            pq_signature = (
                b64decode(self.ml_dsa_65_signature_b64, validate=True)
                if self.ml_dsa_65_signature_b64
                else b""
            )
        except ValueError as exc:
            raise ValueError("invalid base64 ML-DSA authorization field") from exc
        return AuthorizationEnvelope(
            suite={
                "secp256k1": SignatureSuite.SECP256K1,
                "secp256k1+ml-dsa-65": SignatureSuite.SECP256K1_AND_ML_DSA_65,
            }[self.suite],
            secp256k1_public_key=_hex_bytes(self.secp256k1_public_key),
            secp256k1_signature=_hex_bytes(self.secp256k1_signature),
            ml_dsa_65_public_key=pq_public_key,
            ml_dsa_65_signature=pq_signature,
        )


class SignedIntentRequest(StrictModel):
    intent: UnsignedIntentRequest
    authorization: AuthorizationEnvelopeRequest


class IntentSimulationRequest(StrictModel):
    intent: UnsignedIntentRequest
    current_height: int = Field(ge=0, le=(1 << 64) - 1)


class RecipientEnvelopeRequest(StrictModel):
    recipient_id: str = Field(pattern=HEX32_PATTERN)
    encapsulated_key_b64: str = Field(min_length=4, max_length=5_500)
    wrapped_key_b64: str = Field(min_length=4, max_length=11_000)

    def to_domain(self) -> RecipientEnvelope:
        try:
            encapsulated_key = b64decode(self.encapsulated_key_b64, validate=True)
            wrapped_key = b64decode(self.wrapped_key_b64, validate=True)
        except ValueError as exc:
            raise ValueError("recipient envelope fields must be canonical base64") from exc
        if not encapsulated_key or len(encapsulated_key) > MAX_ENCAPSULATED_KEY_BYTES:
            raise ValueError("encapsulated key is empty or exceeds its limit")
        if not wrapped_key or len(wrapped_key) > MAX_WRAPPED_KEY_BYTES:
            raise ValueError("wrapped key is empty or exceeds its limit")
        return RecipientEnvelope(
            recipient_id=_hex32(self.recipient_id),
            encapsulated_key=encapsulated_key,
            wrapped_key=wrapped_key,
        )


class CiphertextSidecarRequest(StrictModel):
    schema_version: Literal[1]
    nonce_b64: str = Field(min_length=32, max_length=64)
    ciphertext_b64: str = Field(min_length=4, max_length=1_100_000)
    plaintext_root: str = Field(pattern=HEX32_PATTERN)
    content_hash: str = Field(pattern=HEX32_PATTERN)
    policy_hash: str = Field(pattern=HEX32_PATTERN)
    recipient_envelopes: List[RecipientEnvelopeRequest] = Field(
        min_length=1, max_length=MAX_RECIPIENTS
    )

    @field_validator("nonce_b64")
    @classmethod
    def validate_nonce(cls, value: str) -> str:
        try:
            raw = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("nonce_b64 must be canonical base64") from exc
        if len(raw) != 24:
            raise ValueError("sidecar nonce must contain exactly 24 bytes")
        return value

    @field_validator("ciphertext_b64")
    @classmethod
    def validate_ciphertext(cls, value: str) -> str:
        try:
            raw = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("ciphertext_b64 must be canonical base64") from exc
        if not raw or len(raw) > MAX_CIPHERTEXT_BYTES:
            raise ValueError("ciphertext is empty or exceeds the VDSO sidecar limit")
        return value

    def to_domain(self) -> EncryptedWitnessSidecar:
        return EncryptedWitnessSidecar(
            schema_version=self.schema_version,
            nonce=b64decode(self.nonce_b64, validate=True),
            ciphertext=b64decode(self.ciphertext_b64, validate=True),
            plaintext_root=_hex32(self.plaintext_root),
            content_hash=_hex32(self.content_hash),
            policy_hash=_hex32(self.policy_hash),
            recipient_envelopes=tuple(
                envelope.to_domain() for envelope in self.recipient_envelopes
            ),
        )


class DisclosureRequest(StrictModel):
    claim_key_hash: str = Field(pattern=HEX32_PATTERN)
    disclosed_value_hash: str = Field(pattern=HEX32_PATTERN)
    salt: str = Field(pattern=HEX32_PATTERN)
    siblings: List[str] = Field(max_length=256)
    path_bits: List[Literal[0, 1]] = Field(max_length=256)
    expected_root: str = Field(pattern=HEX32_PATTERN)

    @field_validator("siblings")
    @classmethod
    def validate_siblings(cls, value: List[str]) -> List[str]:
        if any(not sibling.startswith("0x") or len(sibling) != 66 for sibling in value):
            raise ValueError("every sibling must be a bytes32 hexadecimal value")
        return value


def _active_replay_store() -> ReplayStore:
    candidate = replay_store
    if is_live_environment():
        if candidate is None or getattr(candidate, "shared", False) is not True:
            raise HTTPException(
                status_code=503,
                detail="live VDSO authentication requires a shared atomic replay store",
            )
        return candidate
    return candidate if candidate is not None else _local_replay_store


async def require_vdso_request_auth(
    request: Request,
    x_vams_did: Annotated[Optional[str], Header()] = None,
    x_vams_signature: Annotated[Optional[str], Header()] = None,
    x_vams_timestamp: Annotated[Optional[str], Header()] = None,
    x_vams_content_sha256: Annotated[Optional[str], Header()] = None,
) -> bytes:
    """Authenticate and body-bind every non-public VDSO request."""

    if not all((x_vams_did, x_vams_signature, x_vams_timestamp, x_vams_content_sha256)):
        raise HTTPException(
            status_code=401,
            detail="body-bound VDSO DID authentication is required",
        )
    if not x_vams_did.startswith("did:key:"):
        raise HTTPException(status_code=401, detail="unsupported DID method")
    if (
        not x_vams_timestamp.isascii()
        or not x_vams_timestamp.isdecimal()
        or len(x_vams_timestamp) > 20
        or (len(x_vams_timestamp) > 1 and x_vams_timestamp.startswith("0"))
    ):
        raise HTTPException(
            status_code=401,
            detail="authentication timestamp must be canonical integer epoch seconds",
        )
    timestamp = int(x_vams_timestamp)
    if timestamp > (1 << 64) - 1:
        raise HTTPException(
            status_code=401,
            detail="authentication timestamp must be canonical integer epoch seconds",
        )
    now = int(time.time())
    if abs(now - timestamp) > AUTH_REPLAY_WINDOW_SECONDS:
        raise HTTPException(status_code=401, detail="authentication timestamp expired")

    body = await request.body()
    actual_digest = hashlib.sha256(body).hexdigest()
    if not hmac.compare_digest(actual_digest, x_vams_content_sha256.lower()):
        raise HTTPException(status_code=401, detail="request body digest mismatch")

    replay_key = hashlib.sha256(
        (
            f"{x_vams_did}:{x_vams_timestamp}:"
            f"{request.method}:{request.url.path}:{actual_digest}"
        ).encode()
    ).hexdigest()

    try:
        public_key = bytes.fromhex(x_vams_did[len("did:key:") :])
        signature = bytes.fromhex(x_vams_signature)
        message = (
            f"VAMS_VDSO_AUTH:{request.method}:{request.url.path}:{x_vams_timestamp}:{actual_digest}"
        ).encode()
        if not verify_message(public_key, message, signature):
            raise ValueError("signature verification failed")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid VDSO DID signature") from exc
    store = _active_replay_store()
    try:
        fresh = store.check_and_record(
            replay_key,
            now,
            timestamp + AUTH_REPLAY_WINDOW_SECONDS + 1,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="VDSO replay protection is unavailable",
        ) from exc
    if not fresh:
        raise HTTPException(status_code=401, detail="replayed VDSO request")
    return public_key


def _secp256k1_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    return verify_digest(public_key, message, signature)


authorization_verifier = AuthorizationVerifier(
    secp256k1_verify=_secp256k1_verify,
    # No shape-only fallback: Tier 2 remains blocked until an audited ML-DSA
    # verifier is configured and covered by NIST known-answer tests.
    ml_dsa_65_verify=None,
)


def _intent_response(record) -> dict:
    return {
        "intent_id": "0x" + record.intent.intent_id.hex(),
        "workflow_id": "0x" + record.intent.workflow_id.hex(),
        "status": record.status,
        "selected_adapter_id": (
            "0x" + record.selected_adapter_id.hex() if record.selected_adapter_id else None
        ),
        "external_writes": record.external_writes,
        "mode": service.mode.value,
    }


def _validate_actor_binding(intent: UnsignedIntent, did_public_key: bytes) -> None:
    expected = domain_hash(b"VAMS:ACTOR:v1", (did_public_key,))
    if not hmac.compare_digest(intent.actor_root, expected):
        raise HTTPException(status_code=403, detail="DID key is not bound to intent actor_root")


@router.post("/intents/simulate")
async def simulate_intent(
    request: IntentSimulationRequest,
    did_public_key: bytes = Depends(require_vdso_request_auth),
):
    try:
        intent = request.intent.to_domain()
        _validate_actor_binding(intent, did_public_key)
        return _intent_response(
            service.simulate(intent, current_height=request.current_height)
        )
    except (ValueError, VDSOServiceError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/intents")
async def submit_intent(
    request: SignedIntentRequest,
    did_public_key: bytes = Depends(require_vdso_request_auth),
):
    try:
        intent = request.intent.to_domain()
        envelope = request.authorization.to_domain()
        _validate_actor_binding(intent, did_public_key)
        if envelope.secp256k1_public_key != did_public_key:
            raise AuthorizationError("request DID and intent authorization key differ")
        authorization_verifier.verify(intent, envelope)
        return _intent_response(service.submit_shadow(intent))
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, VDSOServiceError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/intents/{intent_id}")
async def get_intent(intent_id: str):
    try:
        return _intent_response(service.get_intent(_hex32(intent_id)))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="unknown intent") from exc


@router.get("/objects/{object_id}")
async def get_object(object_id: str):
    try:
        header = service.get_object(_hex32(object_id))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="unknown object") from exc
    return {
        "schema_version": header.schema_version,
        "object_id": "0x" + header.object_id.hex(),
        "binding": {
            "state_domain": "0x" + header.binding.state_domain.hex(),
            "host_authority": (
                "polygon-amoy"
                if header.binding.host_authority == HostAuthority.POLYGON
                else "cardano-pre-prod"
            ),
            "authority_epoch": header.binding.authority_epoch,
        },
        "version": header.version,
        "state_commitment": "0x" + header.state_commitment.hex(),
    }


@router.get("/adapters")
async def list_adapters():
    return {
        "mode": service.mode.value,
        "adapters": [
            {
                "adapter_id": "0x" + profile.adapter_id.hex(),
                "host_authority": (
                    "polygon-amoy"
                    if profile.host_authority == HostAuthority.POLYGON
                    else "cardano-pre-prod"
                ),
                "access_modes": [mode.name.lower() for mode in profile.access_modes],
                "maximum_tier": int(profile.maximum_tier),
                "privacy_class": profile.privacy_class,
                "active": profile.active,
                "quarantined": profile.quarantined,
                "expires_at": profile.expires_at,
                "conformance_root": "0x" + profile.conformance_root.hex(),
            }
            for profile in service.list_adapters()
            if not profile.mock_mode and not profile.stub
        ],
    }


@router.post("/sidecars")
async def upload_ciphertext_sidecar(
    request: CiphertextSidecarRequest,
    _did_public_key: bytes = Depends(require_vdso_request_auth),
):
    try:
        sidecar = request.to_domain()
        service.store_encrypted_sidecar(sidecar)
    except (ValueError, VDSOServiceError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"content_hash": request.content_hash.lower(), "stored": True}


@router.get("/sidecars/{content_hash}")
async def get_sidecar_commitment(content_hash: str):
    try:
        record = service.get_sidecar_commitment(_hex32(content_hash))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="unknown sidecar") from exc
    return {
        "content_hash": "0x" + record.content_hash.hex(),
        "plaintext_root": "0x" + record.plaintext_root.hex(),
        "policy_hash": "0x" + record.policy_hash.hex(),
    }


@router.post("/disclosures/verify")
async def verify_disclosure(request: DisclosureRequest):
    if len(request.siblings) != len(request.path_bits):
        raise HTTPException(status_code=422, detail="siblings and path_bits lengths differ")
    node = domain_hash(
        b"VAMS:CLAIM:v1",
        (
            _hex32(request.claim_key_hash),
            _hex32(request.disclosed_value_hash),
            _hex32(request.salt),
        ),
    )
    for sibling_hex, path_bit in zip(request.siblings, request.path_bits):
        sibling = _hex32(sibling_hex)
        left, right = (node, sibling) if path_bit == 0 else (sibling, node)
        node = domain_hash(b"VAMS:CLAIM-NODE:v1", (left, right))
    return {"valid": hmac.compare_digest(node, _hex32(request.expected_root))}
