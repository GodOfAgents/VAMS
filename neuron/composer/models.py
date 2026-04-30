"""
VAMS Resource Composition Engine — Data Models
================================================
Defines the core specification types and resource blueprints that
agents use to declare infrastructure requirements.

Inspired by ICN Instance Blueprints (Section 3 of ICN Whitepaper).

Architecture Reference:
    - ICN Gap #3: Resource Composition Engine
    - VAMS Phase 3, Sprint 5
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════

class GPUType(str, Enum):
    """Supported GPU types (mirrors HardwareClasses.sol)."""
    H100 = "GPU_H100"
    A100 = "GPU_A100"
    L40S = "GPU_L40S"
    RTX_4090 = "GPU_RTX_4090"
    ANY = "GPU_ANY"


class StorageType(str, Enum):
    """Storage media types."""
    NVME = "STORAGE_NVME"
    HDD = "STORAGE_HDD"
    ANY = "STORAGE_ANY"


class TEEType(str, Enum):
    """TEE enclave types."""
    SGX = "TEE_SGX"
    NITRO = "TEE_NITRO"
    NONE = "TEE_NONE"


class AllocationStatus(str, Enum):
    """Status of a provisioned instance."""
    PENDING = "pending"
    ACTIVE = "active"
    SCALING = "scaling"
    DEPROVISIONING = "deprovisioning"
    TERMINATED = "terminated"
    FAILED = "failed"


# ═══════════════════════════════════════════════════════════════
# Resource Specification Building Blocks
# ═══════════════════════════════════════════════════════════════

@dataclass
class ComputeSpec:
    """
    Compute resource requirements.
    
    Examples:
        ComputeSpec(gpu_type=GPUType.A100, gpu_count=4, vcpu=32)
        ComputeSpec(gpu_type=GPUType.ANY, gpu_count=1, vcpu=8)
    """
    gpu_type: GPUType = GPUType.ANY
    gpu_count: int = 0
    vcpu: int = 4
    tflops_min: float = 0.0  # Minimum TFLOPS requirement (0 = don't care)

    def matches_hw_class(self, hw_class_name: str) -> bool:
        """Check if a hardware class name satisfies this spec."""
        if self.gpu_type == GPUType.ANY:
            return hw_class_name.startswith("GPU_") or hw_class_name.startswith("CPU_")
        return hw_class_name == self.gpu_type.value


@dataclass
class MemorySpec:
    """Memory resource requirements."""
    ram_gb: int = 16
    bandwidth_gbps: float = 0.0  # Minimum bandwidth (0 = don't care)


@dataclass
class StorageSpec:
    """Storage resource requirements."""
    type: StorageType = StorageType.ANY
    capacity_gb: int = 100
    iops_min: int = 0          # Minimum 4K random IOPS (0 = don't care)
    persistent: bool = True    # Require persistent (survives restart)


@dataclass
class NetworkSpec:
    """Network resource requirements."""
    bandwidth_mbps: int = 100
    region: str = ""           # Preferred region (empty = any)
    max_latency_ms: int = 0    # Max latency to target region (0 = don't care)


@dataclass
class TEESpec:
    """Trusted Execution Environment requirements."""
    tee_type: TEEType = TEEType.NONE
    attestation_required: bool = False


# ═══════════════════════════════════════════════════════════════
# Instance Blueprint — The Core Request Object
# ═══════════════════════════════════════════════════════════════

@dataclass
class InstanceBlueprint:
    """
    A complete resource configuration request.
    
    Agents submit blueprints to the ResourceComposer, which
    resolves them into hardware allocations across VAMS providers.

    Inspired by ICN's Instance Blueprints for standardized
    resource packaging.
    
    Examples:
        # Standard inference setup
        InstanceBlueprint(
            name="my-inference-job",
            compute=ComputeSpec(gpu_type=GPUType.A100, gpu_count=4, vcpu=32),
            memory=MemorySpec(ram_gb=128),
            storage=StorageSpec(type=StorageType.NVME, capacity_gb=500),
            networking=NetworkSpec(region="us-east-1"),
            max_cost_per_hour=50.0,
        )
    """
    name: str
    compute: ComputeSpec = field(default_factory=ComputeSpec)
    memory: MemorySpec = field(default_factory=MemorySpec)
    storage: StorageSpec = field(default_factory=StorageSpec)
    networking: NetworkSpec = field(default_factory=NetworkSpec)
    tee: TEESpec = field(default_factory=TEESpec)

    # Economic constraints
    max_cost_per_hour: float = 0.0       # Budget cap in $VAMS (0 = uncapped)
    min_duration_seconds: int = 3600      # Minimum booking (default 1h)
    max_duration_seconds: int = 86400     # Maximum booking (default 24h)

    # Scaling behavior
    elastic: bool = False                 # Allow auto-scaling
    min_replicas: int = 1                 # Minimum nodes when elastic
    max_replicas: int = 1                 # Maximum nodes when elastic

    # Trust requirements
    min_sla_score_bps: int = 7500         # Minimum Sentinel SLA score (75%)
    min_trust_tier: str = "bronze"        # "bronze", "silver", "gold", "platinum"

    # AUTOSKILL Phase 3b: Skill alignment requirements
    skill_vector: Optional[List[float]] = None  # Desired skill profile coordinates

    def blueprint_hash(self) -> str:
        """Deterministic hash for deduplication and caching."""
        payload = (
            f"{self.name}:{self.compute.gpu_type}:{self.compute.gpu_count}:"
            f"{self.compute.vcpu}:{self.memory.ram_gb}:"
            f"{self.storage.type}:{self.storage.capacity_gb}:"
            f"{self.networking.region}:{self.max_cost_per_hour}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses."""
        return {
            "name": self.name,
            "blueprint_hash": self.blueprint_hash(),
            "compute": {
                "gpu_type": self.compute.gpu_type.value,
                "gpu_count": self.compute.gpu_count,
                "vcpu": self.compute.vcpu,
                "tflops_min": self.compute.tflops_min,
            },
            "memory": {
                "ram_gb": self.memory.ram_gb,
                "bandwidth_gbps": self.memory.bandwidth_gbps,
            },
            "storage": {
                "type": self.storage.type.value,
                "capacity_gb": self.storage.capacity_gb,
                "iops_min": self.storage.iops_min,
                "persistent": self.storage.persistent,
            },
            "networking": {
                "bandwidth_mbps": self.networking.bandwidth_mbps,
                "region": self.networking.region,
                "max_latency_ms": self.networking.max_latency_ms,
            },
            "tee": {
                "tee_type": self.tee.tee_type.value,
                "attestation_required": self.tee.attestation_required,
            },
            "max_cost_per_hour": self.max_cost_per_hour,
            "elastic": self.elastic,
            "min_sla_score_bps": self.min_sla_score_bps,
            "skill_vector": self.skill_vector,
        }


# ═══════════════════════════════════════════════════════════════
# Scoring & Allocation Result Types
# ═══════════════════════════════════════════════════════════════

@dataclass
class ScoredCandidate:
    """
    A hardware node scored against a blueprint.
    Produced by CandidateScorer, consumed by ResourceAllocator.
    """
    node_id: str
    provider: str
    hw_class: str
    region: str
    capacity_units: int
    reservation_price: float       # $VAMS per hour (from on-chain registry)
    collateral_staked: float       # $VAMS bonded

    # Scoring dimensions (0.0 to 1.0, higher is better)
    price_score: float = 0.0
    sla_score: float = 0.0
    latency_score: float = 0.0
    regional_score: float = 0.0
    skill_alignment_score: float = 0.0  # AUTOSKILL Phase 3b

    # Composite
    total_score: float = 0.0

    # Raw metrics used for scoring
    benchmark_score_bps: int = 0   # Latest Sentinel benchmark (0-10000)
    latency_ms: float = 0.0       # Latest latency probe result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "provider": self.provider,
            "hw_class": self.hw_class,
            "region": self.region,
            "reservation_price": self.reservation_price,
            "total_score": round(self.total_score, 4),
            "price_score": round(self.price_score, 4),
            "sla_score": round(self.sla_score, 4),
            "latency_score": round(self.latency_score, 4),
            "regional_score": round(self.regional_score, 4),
            "skill_alignment_score": round(self.skill_alignment_score, 4),
            "benchmark_score_bps": self.benchmark_score_bps,
        }


@dataclass
class ResourceAssignment:
    """One provider's contribution to an allocation plan."""
    node_id: str
    provider: str
    hw_class: str
    region: str
    allocated_units: int
    hourly_cost: float             # $VAMS per hour for this assignment
    score: float                   # Score of the assigned node


@dataclass
class AllocationPlan:
    """
    The result of the ResourceAllocator — describes how a blueprint
    is fulfilled across one or more providers.
    """
    blueprint_hash: str
    assignments: List[ResourceAssignment] = field(default_factory=list)
    total_hourly_cost: float = 0.0
    total_nodes: int = 0
    is_multi_provider: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blueprint_hash": self.blueprint_hash,
            "total_hourly_cost": round(self.total_hourly_cost, 4),
            "total_nodes": self.total_nodes,
            "is_multi_provider": self.is_multi_provider,
            "assignments": [
                {
                    "node_id": a.node_id,
                    "provider": a.provider,
                    "hw_class": a.hw_class,
                    "region": a.region,
                    "allocated_units": a.allocated_units,
                    "hourly_cost": round(a.hourly_cost, 4),
                }
                for a in self.assignments
            ],
        }


@dataclass
class ProvisionedInstance:
    """
    A successfully provisioned resource allocation.
    Returned to the agent after a blueprint is composed and locked.
    """
    instance_id: str
    blueprint: InstanceBlueprint
    allocation: AllocationPlan
    status: AllocationStatus = AllocationStatus.PENDING
    provisioned_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    escrow_tx_hash: Optional[str] = None  # x402 escrow transaction

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "blueprint_name": self.blueprint.name,
            "status": self.status.value,
            "allocation": self.allocation.to_dict(),
            "provisioned_at": self.provisioned_at,
            "expires_at": self.expires_at,
            "escrow_tx_hash": self.escrow_tx_hash,
        }
