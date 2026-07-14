"""Ciphertext-only DA publication for VDSO witness sidecars."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from functools import partial
from typing import Awaitable, Callable, Optional

from neuron.da.adapters.base import DAAdapter
from neuron.da.adapters.celestia_adapter import CelestiaDAAdapter
from neuron.da.adapters.near_adapter import NearDAAdapter
from neuron.da.models import DAProtocol
from neuron.runtime_safety import require_not_live_mock

from .codec import encode_array
from .sidecar import EncryptedWitnessSidecar


class VDSODAError(RuntimeError):
    """Raised when encrypted sidecar publication cannot be verified."""


@dataclass(frozen=True)
class VDSODAReceipt:
    protocol: str
    blob_id: str
    height: int
    commitment: str
    content_hash: bytes


@dataclass(frozen=True)
class RetrievalBoundLiveEvidence:
    """Operational evidence capability independent of adapter self-assertions.

    Availability is accepted only when separately injected observers verify the
    receipt and retrieve the exact submitted bytes. ``mock_mode``, adapter
    self-verification, and ``receipt.verified`` are never evidence. The runtime
    identity guard rejects direct or partially applied methods bound to the
    selected adapter; independent operational and deployment provenance remains
    a separate canary-admission requirement.
    """

    receipt_verifier: Callable[[object, bytes], Awaitable[bool]]
    blob_retriever: Callable[[object], Awaitable[Optional[bytes]]]

    def __post_init__(self) -> None:
        if not callable(self.receipt_verifier) or not callable(self.blob_retriever):
            raise ValueError("independent DA verifier and retriever callbacks are required")

    async def verify(self, adapter: DAAdapter, receipt, payload: bytes) -> bool:
        if (
            _is_bound_to_adapter(self.receipt_verifier, adapter)
            or _is_bound_to_adapter(self.blob_retriever, adapter)
        ):
            raise VDSODAError(
                "live-evidence callbacks must be independent of the submission adapter"
            )
        if receipt.protocol != adapter.protocol:
            return False
        if not isinstance(receipt.blob_id, str) or not receipt.blob_id:
            return False
        if (
            isinstance(receipt.height, bool)
            or not isinstance(receipt.height, int)
            or receipt.height < 0
        ):
            return False
        expected_commitment = "0x" + hashlib.sha256(payload).hexdigest()
        if not isinstance(receipt.commitment, str) or not hmac.compare_digest(
            receipt.commitment.lower(), expected_commitment
        ):
            return False
        if await self.receipt_verifier(receipt, payload) is not True:
            return False
        retrieved = await self.blob_retriever(receipt)
        return isinstance(retrieved, bytes) and hmac.compare_digest(retrieved, payload)


def _is_bound_to_adapter(callback: Callable, adapter: DAAdapter) -> bool:
    """Detect direct and partially applied adapter-bound methods."""

    target = callback
    while isinstance(target, partial):
        target = target.func
    return getattr(target, "__self__", None) is adapter


def serialize_encrypted_sidecar(sidecar: EncryptedWitnessSidecar) -> bytes:
    """Serialize ciphertext and key envelopes; plaintext is not accepted."""

    try:
        sidecar.validate_integrity()
    except ValueError as exc:
        raise VDSODAError("encrypted sidecar integrity validation failed") from exc
    return encode_array(
        (
            sidecar.schema_version,
            sidecar.nonce,
            sidecar.ciphertext,
            sidecar.plaintext_root,
            sidecar.content_hash,
            sidecar.policy_hash,
            tuple(
                (
                    envelope.recipient_id,
                    envelope.encapsulated_key,
                    envelope.wrapped_key,
                )
                for envelope in sidecar.recipient_envelopes
            ),
        )
    )


class EncryptedSidecarPublisher:
    """Publish to one explicitly selected live-capable adapter and verify it."""

    def __init__(
        self,
        adapter: DAAdapter,
        *,
        live_evidence: RetrievalBoundLiveEvidence,
    ) -> None:
        require_not_live_mock(
            "VDSO encrypted sidecar publisher", getattr(adapter, "mock_mode", True)
        )
        if adapter.protocol not in {DAProtocol.CELESTIA, DAProtocol.NEAR_DA}:
            raise VDSODAError("VDSO live sidecars support only Celestia or Near")
        if getattr(adapter, "mock_mode", True):
            raise VDSODAError("mock DA adapters cannot publish VDSO evidence")
        if isinstance(adapter, (NearDAAdapter, CelestiaDAAdapter)):
            raise VDSODAError(
                "current Near/Celestia adapters are not VDSO live-evidence capable; "
                "signed submission and exact retrieval proof are required"
            )
        if type(live_evidence) is not RetrievalBoundLiveEvidence:
            raise VDSODAError(
                "a retrieval-bound live-evidence capability is required"
            )
        self.adapter = adapter
        self.live_evidence = live_evidence

    async def publish(
        self,
        sidecar: EncryptedWitnessSidecar,
        *,
        expected_sidecar_root: bytes,
    ) -> VDSODAReceipt:
        try:
            sidecar.validate_integrity()
        except ValueError as exc:
            raise VDSODAError("encrypted sidecar integrity validation failed") from exc
        if (
            not isinstance(expected_sidecar_root, bytes)
            or len(expected_sidecar_root) != 32
            or not hmac.compare_digest(expected_sidecar_root, sidecar.content_hash)
        ):
            raise VDSODAError(
                "encrypted sidecar is detached from the signed intent sidecar_root"
            )
        payload = serialize_encrypted_sidecar(sidecar)
        try:
            receipt = await self.adapter.submit_blob(
                payload, namespace=b"vams-vdso-sidecar-v1"
            )
        except Exception as exc:
            raise VDSODAError("DA sidecar submission failed") from exc
        if receipt.protocol != self.adapter.protocol:
            raise VDSODAError("DA receipt protocol does not match the selected adapter")
        try:
            live = await self.live_evidence.verify(self.adapter, receipt, payload)
        except VDSODAError:
            raise
        except Exception as exc:
            raise VDSODAError("DA live-evidence verification failed") from exc
        if live is not True:
            raise VDSODAError(
                "DA receipt lacks retrieval-bound live submission evidence"
            )
        return VDSODAReceipt(
            protocol=receipt.protocol.value,
            blob_id=receipt.blob_id,
            height=receipt.height,
            commitment=receipt.commitment,
            content_hash=sidecar.content_hash,
        )
