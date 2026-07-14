"""Deterministic VDSO canary orchestration with explicit external steps.

The module is DBOS-compatible: every non-deterministic callback is an isolated
step with an intent-derived idempotency key.  The caller supplies DBOS-decorated
callbacks in deployed environments; pure intent construction and identifiers
remain outside those callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Tuple

from .codec import encode_array
from .keccak import domain_hash
from .models import AccessMode, UnsignedIntent
from .routing import NoEligibleAdapterError, select_intent_adapters
from .service import VDSOCanaryService, VDSOMode, VDSOServiceError


ExternalStep = Callable[[str, bytes], Awaitable[bytes]]


class VDSOWorkflowError(RuntimeError):
    """Raised when a durable canary step fails or is not configured."""


@dataclass(frozen=True)
class VDSOWorkflowDependencies:
    acquire_evidence: ExternalStep
    submit_execution: ExternalStep
    await_finality: ExternalStep
    verify_receipt: ExternalStep
    recover_reservation: Optional[ExternalStep] = None


@dataclass(frozen=True)
class VDSOWorkflowResult:
    intent_id: bytes
    workflow_id: bytes
    status: str
    completed_steps: Tuple[str, ...]
    external_writes: int
    recovery_started: bool
    selected_adapter_ids: Tuple[bytes, ...] = ()


def idempotency_key(intent_id: bytes, step_name: str) -> str:
    if len(intent_id) != 32 or not step_name or len(step_name) > 64:
        raise ValueError("invalid VDSO idempotency-key input")
    digest = domain_hash(b"VAMS:STEP:v1", (intent_id, step_name.encode("ascii")))
    return f"vdso:{intent_id.hex()}:{step_name}:{digest.hex()}"


class VDSOOrchestrator:
    def __init__(
        self,
        service: VDSOCanaryService,
        dependencies: Optional[VDSOWorkflowDependencies] = None,
        routing_time_provider: Optional[Callable[[], int]] = None,
    ) -> None:
        self.service = service
        self.dependencies = dependencies
        self.routing_time_provider = routing_time_provider

    async def run(self, intent: UnsignedIntent) -> VDSOWorkflowResult:
        try:
            intent.validate_execution_policy()
        except ValueError as exc:
            raise VDSOWorkflowError("signed intent violates host/access policy") from exc
        record = self.service.submit_shadow(intent)
        if self.service.mode == VDSOMode.SHADOW:
            return VDSOWorkflowResult(
                intent_id=intent.intent_id,
                workflow_id=intent.workflow_id,
                status=record.status,
                completed_steps=("canonical_simulation",),
                external_writes=0,
                recovery_started=False,
            )
        if self.service.mode != VDSOMode.CANARY or self.dependencies is None:
            raise VDSOWorkflowError("canary external steps are not configured")

        try:
            self.service.require_bound_sidecar(intent)
            if self.routing_time_provider is None:
                raise VDSOWorkflowError(
                    "canary capability routing time source is not configured"
                )
            routing_time = self.routing_time_provider()
            selected_adapters = select_intent_adapters(
                self.service.list_adapters(),
                intent,
                now=routing_time,
            )
        except (NoEligibleAdapterError, ValueError, VDSOServiceError) as exc:
            raise VDSOWorkflowError(
                "signed capability routing failed closed before external execution"
            ) from exc

        selected_adapter_ids = tuple(
            adapter.adapter_id for adapter in selected_adapters
        )
        completed = ["capability_routing"]
        writes = 0
        reserved = any(access.mode == AccessMode.RESERVE for access in intent.accesses)
        try:
            evidence = await self.dependencies.acquire_evidence(
                idempotency_key(intent.intent_id, "acquire_evidence"), intent.canonical_bytes()
            )
            completed.append("acquire_evidence")
            object_ids = tuple(access.object_id for access in intent.accesses) or (
                b"\x00" * 32,
            )
            routed_submission = encode_array(
                (
                    intent.intent_id,
                    tuple(zip(object_ids, selected_adapter_ids)),
                    evidence,
                )
            )
            submission = await self.dependencies.submit_execution(
                idempotency_key(intent.intent_id, "submit_execution"),
                routed_submission,
            )
            writes += 1
            completed.append("submit_execution")
            finality = await self.dependencies.await_finality(
                idempotency_key(intent.intent_id, "await_finality"), submission
            )
            completed.append("await_finality")
            verification = await self.dependencies.verify_receipt(
                idempotency_key(intent.intent_id, "verify_receipt"), finality
            )
            if verification != b"verified":
                raise VDSOWorkflowError("receipt verification failed closed")
            completed.append("verify_receipt")
            return VDSOWorkflowResult(
                intent_id=intent.intent_id,
                workflow_id=intent.workflow_id,
                status="canary_verified",
                completed_steps=tuple(completed),
                external_writes=writes,
                recovery_started=False,
                selected_adapter_ids=selected_adapter_ids,
            )
        except Exception as exc:
            if reserved:
                if self.dependencies.recover_reservation is None:
                    raise VDSOWorkflowError(
                        "reservation entered recovery-pending but no authenticated "
                        "recovery step is configured"
                    ) from exc
                await self.dependencies.recover_reservation(
                    idempotency_key(intent.intent_id, "recover_reservation"), intent.intent_id
                )
                completed.append("recover_reservation")
                return VDSOWorkflowResult(
                    intent_id=intent.intent_id,
                    workflow_id=intent.workflow_id,
                    status="recovery_pending",
                    completed_steps=tuple(completed),
                    external_writes=writes,
                    recovery_started=True,
                    selected_adapter_ids=selected_adapter_ids,
                )
            raise VDSOWorkflowError("VDSO canary workflow failed") from exc
