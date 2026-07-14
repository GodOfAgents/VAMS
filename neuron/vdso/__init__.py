"""VDSO canary primitives.

This package is intentionally isolated from the legacy VAMS execution path.
It implements deterministic shadow/canary coordination only; authoritative
execution remains disabled until the on-chain registries and proof backends are
configured and independently reviewed.
"""

from .models import (
    AccessMode,
    AdapterProfile,
    CapabilityRequirements,
    DomainAuthorityBinding,
    DomainMode,
    ExecutionTier,
    FailureCode,
    HostAuthority,
    ObjectAccess,
    SettlementMetadata,
    SignatureSuite,
    StateObjectHeader,
    TransitionReceipt,
    UnsignedIntent,
)
from .service import VDSOCanaryService, VDSOMode

__all__ = [
    "AccessMode",
    "AdapterProfile",
    "CapabilityRequirements",
    "DomainAuthorityBinding",
    "DomainMode",
    "ExecutionTier",
    "FailureCode",
    "HostAuthority",
    "ObjectAccess",
    "SettlementMetadata",
    "SignatureSuite",
    "StateObjectHeader",
    "TransitionReceipt",
    "UnsignedIntent",
    "VDSOCanaryService",
    "VDSOMode",
]
