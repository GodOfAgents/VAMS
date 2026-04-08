"""
VAMS Resource Composition Engine
=================================
Transforms VAMS from a provider marketplace into an
intelligent infrastructure orchestrator.

Phase 3, Sprint 5-6 of ICN-Inspired Architecture Improvements.
"""

from neuron.composer.models import (
    ComputeSpec,
    MemorySpec,
    StorageSpec,
    NetworkSpec,
    InstanceBlueprint,
    ProvisionedInstance,
    ScoredCandidate,
    AllocationPlan,
)
from neuron.composer.scorer import CandidateScorer

__all__ = [
    "ComputeSpec",
    "MemorySpec",
    "StorageSpec",
    "NetworkSpec",
    "InstanceBlueprint",
    "ProvisionedInstance",
    "ScoredCandidate",
    "AllocationPlan",
    "CandidateScorer",
]
