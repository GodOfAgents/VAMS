"""Fail-closed VDSO shadow/canary service used by the gateway boundary."""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Iterable, Optional, Protocol, Tuple

from neuron.runtime_safety import current_environment, is_live_environment

from .models import AdapterProfile, DomainAuthorityBinding, StateObjectHeader, UnsignedIntent
from .sidecar import EncryptedWitnessSidecar


class VDSOMode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    CANARY = "canary"
    AUTHORITATIVE = "authoritative"


class VDSOServiceError(RuntimeError):
    """Raised when VDSO canary policy rejects an operation."""


NonceKey = Tuple[bytes, bytes, int, int]


class NonceStore(Protocol):
    """Atomic intent-nonce claim store supplied by durable deployments."""

    durable: bool

    def check_and_record(self, key: NonceKey, intent_id: bytes) -> bool:
        """Atomically return true for a new claim or the same intent retry."""


class InMemoryNonceStore:
    """Bounded process-local nonce store for local/shadow development only."""

    durable = False

    def __init__(self, *, max_entries: int = 16_384) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._claims: OrderedDict[NonceKey, bytes] = OrderedDict()
        self._lock = threading.Lock()

    def check_and_record(self, key: NonceKey, intent_id: bytes) -> bool:
        with self._lock:
            existing = self._claims.get(key)
            if existing is not None:
                self._claims.move_to_end(key)
                return existing == intent_id
            if len(self._claims) >= self._max_entries:
                raise VDSOServiceError("local nonce store is full; refusing an unsafe eviction")
            self._claims[key] = intent_id
            return True


@dataclass(frozen=True)
class CanaryDeploymentConfig:
    environment: str
    object_store_address: str
    execution_kernel_address: str
    adapter_registry_address: str


CanaryDeploymentVerifier = Callable[
    [CanaryDeploymentConfig, DomainAuthorityBinding], bool
]


@dataclass(frozen=True)
class IntentRecord:
    intent: UnsignedIntent
    status: str
    selected_adapter_id: Optional[bytes]
    external_writes: int = 0


@dataclass(frozen=True)
class SidecarCommitmentRecord:
    content_hash: bytes
    plaintext_root: bytes
    policy_hash: bytes


class VDSOCanaryService:
    """Thread-safe control surface with no hidden authoritative fallback.

    A live canary must inject a durable nonce store and a deployment verifier.
    The verifier is responsible for externally checking chain identity, bytecode,
    role ownership, state-domain authority, and authority epoch for each binding.
    """

    def __init__(
        self,
        *,
        mode: Optional[VDSOMode] = None,
        adapters: Iterable[AdapterProfile] = (),
        height_provider: Optional[Callable[[DomainAuthorityBinding], int]] = None,
        nonce_store: Optional[NonceStore] = None,
        deployment_verifier: Optional[CanaryDeploymentVerifier] = None,
    ) -> None:
        raw_mode = (
            mode.value
            if isinstance(mode, VDSOMode)
            else (mode or os.getenv("VDSO_MODE", "off"))
        )
        self.mode = VDSOMode(str(raw_mode).strip().lower())
        self._live_environment = is_live_environment()
        if self.mode == VDSOMode.AUTHORITATIVE:
            raise VDSOServiceError(
                "authoritative VDSO mode is blocked until audited registries, "
                "proof backends, and migration evidence exist"
            )

        self._deployment_config: Optional[CanaryDeploymentConfig] = None
        if self._live_environment and self.mode == VDSOMode.CANARY:
            required = {
                "VDSO_OBJECT_STORE_ADDRESS": os.getenv("VDSO_OBJECT_STORE_ADDRESS", ""),
                "VDSO_EXECUTION_KERNEL_ADDRESS": os.getenv(
                    "VDSO_EXECUTION_KERNEL_ADDRESS", ""
                ),
                "VDSO_ADAPTER_REGISTRY_ADDRESS": os.getenv(
                    "VDSO_ADAPTER_REGISTRY_ADDRESS", ""
                ),
            }
            invalid = [
                name for name, value in required.items() if not _is_nonzero_address(value)
            ]
            if invalid:
                raise VDSOServiceError(
                    "VDSO canary requires nonzero 20-byte on-chain registry addresses "
                    f"in {current_environment()}: {', '.join(invalid)}"
                )
            if height_provider is None:
                raise VDSOServiceError(
                    "live VDSO canary requires an injected trusted host-height provider"
                )
            if nonce_store is None or not getattr(nonce_store, "durable", False):
                raise VDSOServiceError(
                    "live VDSO canary requires an injected durable atomic nonce store"
                )
            if deployment_verifier is None:
                raise VDSOServiceError(
                    "live VDSO canary requires an injected deployment verifier"
                )
            self._deployment_config = CanaryDeploymentConfig(
                environment=current_environment(),
                object_store_address=required["VDSO_OBJECT_STORE_ADDRESS"],
                execution_kernel_address=required["VDSO_EXECUTION_KERNEL_ADDRESS"],
                adapter_registry_address=required["VDSO_ADAPTER_REGISTRY_ADDRESS"],
            )

        self._adapters: Dict[bytes, AdapterProfile] = {
            profile.adapter_id: profile for profile in adapters
        }
        self._objects: Dict[bytes, StateObjectHeader] = {}
        self._intents: Dict[bytes, IntentRecord] = {}
        self._ciphertext_sidecars: Dict[bytes, EncryptedWitnessSidecar] = {}
        self._height_provider = height_provider
        self._nonce_store = (
            nonce_store if nonce_store is not None else InMemoryNonceStore()
        )
        self._deployment_verifier = deployment_verifier
        self._lock = threading.RLock()

    def _trusted_current_height(self, binding: DomainAuthorityBinding) -> int:
        if self._height_provider is None:
            raise VDSOServiceError(
                "trusted host height provider is not configured; "
                "valid_until_height cannot be evaluated"
            )
        try:
            current_height = self._height_provider(binding)
        except Exception as exc:
            raise VDSOServiceError("trusted host height provider failed") from exc
        if (
            isinstance(current_height, bool)
            or not isinstance(current_height, int)
            or not 0 <= current_height <= (1 << 64) - 1
        ):
            raise VDSOServiceError(
                "trusted host height provider returned an invalid uint64 height"
            )
        return current_height

    def _verify_live_deployment(self, binding: DomainAuthorityBinding) -> None:
        if not (self._live_environment and self.mode == VDSOMode.CANARY):
            return
        if self._deployment_config is None or self._deployment_verifier is None:
            raise VDSOServiceError("live canary deployment verification is unavailable")
        try:
            verified = self._deployment_verifier(self._deployment_config, binding)
        except Exception as exc:
            raise VDSOServiceError("live canary deployment verification failed") from exc
        if verified is not True:
            raise VDSOServiceError("live canary deployment verification rejected binding")

    def simulate(
        self,
        intent: UnsignedIntent,
        *,
        current_height: Optional[int] = None,
    ) -> IntentRecord:
        if self.mode == VDSOMode.OFF:
            raise VDSOServiceError("VDSO is disabled")
        intent.validate_execution_policy()
        trusted_height = self._trusted_current_height(intent.binding)
        if current_height is not None:
            if (
                isinstance(current_height, bool)
                or not isinstance(current_height, int)
                or not 0 <= current_height <= (1 << 64) - 1
            ):
                raise VDSOServiceError("requested current_height is not a uint64")
            if current_height != trusted_height:
                raise VDSOServiceError(
                    "requested current_height does not match the trusted host height"
                )
        self._verify_live_deployment(intent.binding)
        if trusted_height > intent.valid_until_height:
            raise VDSOServiceError("intent is expired")
        return IntentRecord(intent=intent, status="simulated", selected_adapter_id=None)

    def submit_shadow(self, intent: UnsignedIntent) -> IntentRecord:
        """Record an intent without performing any external write."""

        self.simulate(intent)
        nonce_key = (
            intent.actor_root,
            intent.binding.state_domain,
            intent.binding.authority_epoch,
            intent.nonce,
        )
        try:
            accepted = self._nonce_store.check_and_record(nonce_key, intent.intent_id)
        except Exception as exc:
            if isinstance(exc, VDSOServiceError):
                raise
            raise VDSOServiceError("atomic nonce store operation failed") from exc
        if accepted is not True:
            raise VDSOServiceError(
                "nonce reuse across distinct intents is rejected for this authority binding"
            )
        with self._lock:
            if intent.intent_id in self._intents:
                return self._intents[intent.intent_id]
            record = IntentRecord(
                intent=intent,
                status=(
                    "shadow_accepted"
                    if self.mode == VDSOMode.SHADOW
                    else "canary_queued"
                ),
                selected_adapter_id=None,
                external_writes=0,
            )
            self._intents[intent.intent_id] = record
            return record

    def get_intent(self, intent_id: bytes) -> IntentRecord:
        with self._lock:
            try:
                return self._intents[intent_id]
            except KeyError as exc:
                raise KeyError("unknown intent") from exc

    def get_object(self, object_id: bytes) -> StateObjectHeader:
        with self._lock:
            try:
                return self._objects[object_id]
            except KeyError as exc:
                raise KeyError("unknown object") from exc

    def list_adapters(self) -> Tuple[AdapterProfile, ...]:
        with self._lock:
            return tuple(sorted(self._adapters.values(), key=lambda item: item.adapter_id))

    def store_encrypted_sidecar(self, sidecar: EncryptedWitnessSidecar) -> None:
        try:
            sidecar.validate_integrity()
        except ValueError as exc:
            raise VDSOServiceError("encrypted sidecar integrity validation failed") from exc
        with self._lock:
            existing = self._ciphertext_sidecars.get(sidecar.content_hash)
            if existing is not None and existing != sidecar:
                raise VDSOServiceError("sidecar content-hash collision or mismatched replay")
            self._ciphertext_sidecars[sidecar.content_hash] = sidecar

    def get_sidecar_commitment(self, content_hash: bytes) -> SidecarCommitmentRecord:
        with self._lock:
            try:
                sidecar = self._ciphertext_sidecars[content_hash]
            except KeyError as exc:
                raise KeyError("unknown sidecar") from exc
        return SidecarCommitmentRecord(
            content_hash=sidecar.content_hash,
            plaintext_root=sidecar.plaintext_root,
            policy_hash=sidecar.policy_hash,
        )

    def require_bound_sidecar(self, intent: UnsignedIntent) -> None:
        """Join the signed v1 sidecar root to an uploaded encrypted sidecar."""

        if intent.sidecar_root == b"\x00" * 32:
            return
        with self._lock:
            sidecar = self._ciphertext_sidecars.get(intent.sidecar_root)
        if sidecar is None:
            raise VDSOServiceError(
                "signed intent sidecar_root has no matching encrypted sidecar"
            )
        try:
            sidecar.validate_integrity()
        except ValueError as exc:
            raise VDSOServiceError("bound encrypted sidecar failed integrity checks") from exc
        if sidecar.content_hash != intent.sidecar_root:
            raise VDSOServiceError("encrypted sidecar is detached from signed sidecar_root")


def _is_nonzero_address(value: str) -> bool:
    return (
        len(value) == 42
        and value.startswith("0x")
        and all(character in "0123456789abcdefABCDEF" for character in value[2:])
        and int(value[2:], 16) != 0
    )
