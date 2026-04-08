"""
VAMS Service Block SDK Client
================================
Python client for interacting with the ServiceBlockRegistry
smart contract and resolving service blocks into blueprints.

Architecture Reference:
    - ICN Gap #6: Service Blocks
    - VAMS Phase 3, Sprint 8
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from neuron.composer.models import (
    ComputeSpec,
    GPUType,
    InstanceBlueprint,
    MemorySpec,
    NetworkSpec,
    StorageSpec,
    StorageType,
    TEESpec,
    TEEType,
)

logger = logging.getLogger("VAMS-ServiceBlocks")


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

@dataclass
class ServiceBlockInfo:
    """Mirror of the on-chain ServiceBlock struct."""
    block_id: str
    builder: str
    name: str
    category: str
    description: str
    resource_requirements_hash: str
    deployment_cid: str
    revenue_share_bps: int
    min_trust_tier: int
    staked_amount: float
    is_verified: bool
    is_active: bool
    registered_at: float
    total_provisions: int

    # Off-chain blueprint spec (resolved from deployment_cid)
    blueprint: Optional[InstanceBlueprint] = None


# ═══════════════════════════════════════════════════════════════
# Pre-registered Service Block Definitions
# ═══════════════════════════════════════════════════════════════
# These are in-memory definitions that map service block names
# to their resource requirements. In production, these would be
# fetched from the DA layer (Celestia, Arweave, etc.)

_SERVICE_BLOCK_BLUEPRINTS: Dict[str, InstanceBlueprint] = {
    "llama_inference": InstanceBlueprint(
        name="llama_inference",
        compute=ComputeSpec(gpu_type=GPUType.A100, gpu_count=2, vcpu=16, tflops_min=200.0),
        memory=MemorySpec(ram_gb=64),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=200),
        networking=NetworkSpec(bandwidth_mbps=1000),
        max_cost_per_hour=30.0,
        min_sla_score_bps=8000,
    ),
    "vector_db": InstanceBlueprint(
        name="vector_db",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=8),
        memory=MemorySpec(ram_gb=32),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=500, iops_min=80000),
        networking=NetworkSpec(bandwidth_mbps=500),
        max_cost_per_hour=10.0,
        min_sla_score_bps=8500,
    ),
    "tee_wrapper": InstanceBlueprint(
        name="tee_wrapper",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=16),
        memory=MemorySpec(ram_gb=64),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=100),
        tee=TEESpec(tee_type=TEEType.SGX, attestation_required=True),
        max_cost_per_hour=20.0,
        min_sla_score_bps=9000,
        min_trust_tier="gold",
    ),
    "celestia_audit": InstanceBlueprint(
        name="celestia_audit",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=4),
        memory=MemorySpec(ram_gb=8),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=50),
        networking=NetworkSpec(bandwidth_mbps=100),
        max_cost_per_hour=3.0,
        min_sla_score_bps=7500,
    ),
    "x402_payments": InstanceBlueprint(
        name="x402_payments",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=4),
        memory=MemorySpec(ram_gb=8),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=20),
        networking=NetworkSpec(bandwidth_mbps=200, max_latency_ms=50),
        max_cost_per_hour=2.0,
        min_sla_score_bps=9000,
    ),
    "mev_protection": InstanceBlueprint(
        name="mev_protection",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=8),
        memory=MemorySpec(ram_gb=16),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=50),
        networking=NetworkSpec(bandwidth_mbps=1000, max_latency_ms=10),
        max_cost_per_hour=15.0,
        min_sla_score_bps=9500,
    ),
    "high_speed_compute": InstanceBlueprint(
        name="high_speed_compute",
        compute=ComputeSpec(gpu_type=GPUType.H100, gpu_count=4, vcpu=32),
        memory=MemorySpec(ram_gb=256),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=1000, iops_min=100000),
        networking=NetworkSpec(bandwidth_mbps=10000, max_latency_ms=5),
        max_cost_per_hour=100.0,
        min_sla_score_bps=9500,
    ),
    "multi_chain_bridge": InstanceBlueprint(
        name="multi_chain_bridge",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=8),
        memory=MemorySpec(ram_gb=16),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=100),
        networking=NetworkSpec(bandwidth_mbps=500),
        max_cost_per_hour=8.0,
        min_sla_score_bps=9000,
    ),
    "storage_cluster_block": InstanceBlueprint(
        name="storage_cluster_block",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=8),
        memory=MemorySpec(ram_gb=32),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=5000, iops_min=50000),
        networking=NetworkSpec(bandwidth_mbps=5000),
        max_cost_per_hour=20.0,
        min_sla_score_bps=8500,
    ),
    "cpu_compute_block": InstanceBlueprint(
        name="cpu_compute_block",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=32),
        memory=MemorySpec(ram_gb=128),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=200),
        networking=NetworkSpec(bandwidth_mbps=1000),
        max_cost_per_hour=15.0,
        min_sla_score_bps=8000,
    ),
}


# ═══════════════════════════════════════════════════════════════
# Service Block Client
# ═══════════════════════════════════════════════════════════════

class ServiceBlockClient:
    """
    Python SDK client for the ServiceBlockRegistry.

    Provides methods to query, resolve, and compose service blocks.

    Usage:
        client = ServiceBlockClient()
        blocks = client.list_blocks(category="AI")
        blueprint = client.resolve_blueprint("llama_inference")
    """

    def __init__(self, contract_client=None):
        """
        Args:
            contract_client: Optional Web3 contract instance.
                             If None, uses in-memory block definitions.
        """
        self._contract = contract_client

    # ──────────────────────────────────────────────────
    # Query API
    # ──────────────────────────────────────────────────

    def list_blocks(
        self,
        category: Optional[str] = None,
        verified_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """List available service blocks."""
        result = []
        for name, bp in _SERVICE_BLOCK_BLUEPRINTS.items():
            block_info = {
                "name": name,
                "category": self._infer_category(name),
                "gpu_type": bp.compute.gpu_type.value,
                "gpu_count": bp.compute.gpu_count,
                "ram_gb": bp.memory.ram_gb,
                "storage_gb": bp.storage.capacity_gb,
                "max_cost_per_hour": bp.max_cost_per_hour,
                "tee_required": bp.tee.tee_type != TEEType.NONE,
            }

            if category and block_info["category"] != category:
                continue

            result.append(block_info)
        return result

    def get_block(self, block_name: str) -> Optional[Dict[str, Any]]:
        """Get full metadata for a service block."""
        bp = _SERVICE_BLOCK_BLUEPRINTS.get(block_name)
        if not bp:
            return None
        return {
            "name": block_name,
            "category": self._infer_category(block_name),
            "blueprint": bp.to_dict(),
        }

    # ──────────────────────────────────────────────────
    # Resolution API
    # ──────────────────────────────────────────────────

    def resolve_blueprint(self, block_name: str) -> InstanceBlueprint:
        """
        Convert a service block's resource requirements into
        an InstanceBlueprint for the ResourceComposer.

        Args:
            block_name: Name of the service block

        Returns:
            InstanceBlueprint ready for provisioning

        Raises:
            KeyError: If block not found
        """
        bp = _SERVICE_BLOCK_BLUEPRINTS.get(block_name)
        if not bp:
            raise KeyError(
                f"Unknown service block '{block_name}'. "
                f"Available: {list(_SERVICE_BLOCK_BLUEPRINTS.keys())}"
            )
        return bp

    def resolve_macro(self, macro_name: str) -> List[InstanceBlueprint]:
        """
        Resolve a macro service block into its constituent blueprints.

        Args:
            macro_name: Name of the macro block

        Returns:
            List of InstanceBlueprints for all constituent blocks
        """
        from neuron.services.macro_blocks import get_macro

        macro = get_macro(macro_name)
        blueprints = []
        for block_name in macro["blocks"]:
            bp = self.resolve_blueprint(block_name)
            blueprints.append(bp)
        return blueprints

    # ──────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────

    @staticmethod
    def _infer_category(name: str) -> str:
        """Infer category from block name."""
        ai_hints = ("llama", "inference", "vector", "compute")
        storage_hints = ("storage", "archive")
        security_hints = ("tee", "mev", "audit")
        network_hints = ("bridge", "payments", "x402")

        name_lower = name.lower()
        if any(h in name_lower for h in ai_hints):
            return "AI"
        if any(h in name_lower for h in storage_hints):
            return "STORAGE"
        if any(h in name_lower for h in security_hints):
            return "SECURITY"
        if any(h in name_lower for h in network_hints):
            return "NETWORK"
        return "OTHER"
