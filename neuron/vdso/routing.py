"""Deterministic fail-closed VDSO capability routing."""

from __future__ import annotations

from typing import Iterable, Tuple

from .models import (
    AccessMode,
    AdapterProfile,
    CapabilityRequirements,
    ExecutionTier,
    HostAuthority,
    UnsignedIntent,
)


class NoEligibleAdapterError(LookupError):
    """Raised when no adapter satisfies every signed requirement."""


def _eligible(
    profile: AdapterProfile, requirements: CapabilityRequirements, now: int
) -> bool:
    if not profile.active or profile.quarantined or profile.expires_at <= now:
        return False
    if profile.mock_mode or profile.stub:
        return False
    if profile.host_authority != requirements.host_authority:
        return False
    if requirements.access_mode not in profile.access_modes:
        return False
    if (
        requirements.access_mode != AccessMode.READ
        and requirements.execution_tier != ExecutionTier.IMMEDIATE_DUAL_VALIDITY
    ):
        return False
    if int(profile.maximum_tier) < int(requirements.execution_tier):
        return False
    if profile.privacy_class < requirements.minimum_privacy_class:
        return False
    if profile.estimated_cost > requirements.maximum_cost:
        return False
    if not set(requirements.required_da).issubset(profile.da_protocols):
        return False
    if requirements.host_authority == HostAuthority.CARDANO and requirements.access_mode in {
        AccessMode.CONSUME,
        AccessMode.RESERVE,
    }:
        return False
    return True


def select_adapter(
    profiles: Iterable[AdapterProfile],
    requirements: CapabilityRequirements,
    *,
    now: int,
) -> AdapterProfile:
    """Select the cheapest compatible adapter with stable tie-breaking."""

    candidates = [
        profile for profile in profiles if _eligible(profile, requirements, now)
    ]
    if not candidates:
        raise NoEligibleAdapterError("no adapter satisfies all signed capabilities")
    return min(
        candidates,
        key=lambda profile: (
            profile.estimated_cost,
            profile.estimated_latency_ms,
            profile.adapter_id,
        ),
    )


def derive_capability_requirements(
    intent: UnsignedIntent,
) -> Tuple[CapabilityRequirements, ...]:
    """Derive routing policy only from fields committed by the signed intent."""

    intent.validate_execution_policy()
    required_da = {
        ExecutionTier.NATIVE_NON_ECONOMIC: (),
        ExecutionTier.BATCHED_VALIDITY: ("celestia",),
        ExecutionTier.IMMEDIATE_DUAL_VALIDITY: ("celestia", "near"),
    }[ExecutionTier(intent.execution_tier)]
    access_modes = tuple(access.mode for access in intent.accesses) or (
        AccessMode.READ,
    )
    return tuple(
        CapabilityRequirements(
            host_authority=intent.binding.host_authority,
            access_mode=AccessMode(access_mode),
            execution_tier=intent.execution_tier,
            minimum_privacy_class=int(intent.execution_tier),
            maximum_cost=intent.max_settlement_cost,
            required_da=required_da,
        )
        for access_mode in access_modes
    )


def select_intent_adapters(
    profiles: Iterable[AdapterProfile],
    intent: UnsignedIntent,
    *,
    now: int,
) -> Tuple[AdapterProfile, ...]:
    """Resolve every derived capability requirement without caller overrides."""

    if isinstance(now, bool) or not isinstance(now, int) or now < 0:
        raise ValueError("adapter routing time must be a nonnegative integer")
    available = tuple(profiles)
    return tuple(
        select_adapter(available, requirement, now=now)
        for requirement in derive_capability_requirements(intent)
    )
