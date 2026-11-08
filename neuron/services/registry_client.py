"""
VAMS Service Block SDK Client
================================
Local simulated catalogue and declaration-to-blueprint resolution. An
authenticated on-chain registry reader is not implemented by this module.

Architecture Reference:
    - ICN Gap #6: Service Blocks
    - VAMS Phase 3, Sprint 8
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration, LiveModeSafetyError, RuntimeConfigurationError,
    RuntimePolicy, load_runtime_policy,
)

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


class ServiceBlockMemoryPolicy(str, Enum):
    """Off-chain memory policy used to prevent unreviewed prompt-memory loops."""

    STATELESS = "STATELESS"
    SESSION_ICL = "SESSION_ICL"
    EXTERNAL_READONLY = "EXTERNAL_READONLY"
    PERSISTENT_MUTATING_REQUIRES_REVIEW = "PERSISTENT_MUTATING_REQUIRES_REVIEW"


class ServiceBlockPermission(str, Enum):
    """SkillOps permission scopes mirrored by the Solidity bitmap."""

    EXTERNAL_READ = "EXTERNAL_READ"
    SESSION_WRITE = "SESSION_WRITE"
    PERSISTENT_MUTATION = "PERSISTENT_MUTATION"
    WALLET_ACCESS = "WALLET_ACCESS"
    NETWORK_EGRESS = "NETWORK_EGRESS"
    TEE_REQUIRED = "TEE_REQUIRED"


_PERMISSION_BITS: Dict[ServiceBlockPermission, int] = {
    ServiceBlockPermission.EXTERNAL_READ: 1 << 0,
    ServiceBlockPermission.SESSION_WRITE: 1 << 1,
    ServiceBlockPermission.PERSISTENT_MUTATION: 1 << 2,
    ServiceBlockPermission.WALLET_ACCESS: 1 << 3,
    ServiceBlockPermission.NETWORK_EGRESS: 1 << 4,
    ServiceBlockPermission.TEE_REQUIRED: 1 << 5,
}


@dataclass(frozen=True)
class ServiceBlockManifest:
    """Deterministic off-chain SkillOps manifest metadata."""

    block_name: str
    permission_scopes: List[str]
    manifest_version: int = 1
    capability_root: Optional[str] = None
    manifest_hash: Optional[str] = None

    def permissions_bitmap(self) -> int:
        bitmap = 0
        for scope in self.permission_scopes:
            permission = ServiceBlockClient._validate_permission_scope(scope)
            bitmap |= _PERMISSION_BITS[permission]
        return bitmap

    def computed_capability_root(self) -> str:
        if self.capability_root:
            return self.capability_root
        return "0x" + hashlib.sha256(
            f"{self.block_name}:capabilities".encode("utf-8")
        ).hexdigest()

    def computed_manifest_hash(self) -> str:
        if self.manifest_hash:
            return self.manifest_hash
        payload = {
            "block_name": self.block_name,
            "capability_root": self.computed_capability_root(),
            "manifest_version": self.manifest_version,
            "permission_scopes": list(self.permission_scopes),
            "permissions_bitmap": self.permissions_bitmap(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "0x" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_name": self.block_name,
            "manifest_hash": self.computed_manifest_hash(),
            "capability_root": self.computed_capability_root(),
            "manifest_version": self.manifest_version,
            "permission_scopes": list(self.permission_scopes),
            "permissions_bitmap": self.permissions_bitmap(),
        }


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
    "ServiceBlock_OMS_v1": InstanceBlueprint(
        name="ServiceBlock_OMS_v1",
        compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=4),
        memory=MemorySpec(ram_gb=8),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=20),
        networking=NetworkSpec(bandwidth_mbps=200, max_latency_ms=50),
        max_cost_per_hour=3.5,
        min_sla_score_bps=9000,
        min_trust_tier="silver",
    ),
}


_SERVICE_BLOCK_MEMORY_POLICIES: Dict[str, ServiceBlockMemoryPolicy] = {
    "llama_inference": ServiceBlockMemoryPolicy.STATELESS,
    "vector_db": ServiceBlockMemoryPolicy.EXTERNAL_READONLY,
    "tee_wrapper": ServiceBlockMemoryPolicy.STATELESS,
    "celestia_audit": ServiceBlockMemoryPolicy.STATELESS,
    "x402_payments": ServiceBlockMemoryPolicy.STATELESS,
    "mev_protection": ServiceBlockMemoryPolicy.STATELESS,
    "high_speed_compute": ServiceBlockMemoryPolicy.STATELESS,
    "multi_chain_bridge": ServiceBlockMemoryPolicy.STATELESS,
    "storage_cluster_block": ServiceBlockMemoryPolicy.EXTERNAL_READONLY,
    "cpu_compute_block": ServiceBlockMemoryPolicy.STATELESS,
    "ServiceBlock_OMS_v1": ServiceBlockMemoryPolicy.STATELESS,
}


_SERVICE_BLOCK_PERMISSION_SCOPES: Dict[str, List[str]] = {
    "llama_inference": ["EXTERNAL_READ", "NETWORK_EGRESS"],
    "vector_db": ["EXTERNAL_READ"],
    "tee_wrapper": ["EXTERNAL_READ", "TEE_REQUIRED"],
    "celestia_audit": ["EXTERNAL_READ", "NETWORK_EGRESS"],
    "x402_payments": ["EXTERNAL_READ", "WALLET_ACCESS", "NETWORK_EGRESS"],
    "mev_protection": ["EXTERNAL_READ", "NETWORK_EGRESS"],
    "high_speed_compute": ["EXTERNAL_READ", "NETWORK_EGRESS"],
    "multi_chain_bridge": ["EXTERNAL_READ", "WALLET_ACCESS", "NETWORK_EGRESS"],
    "storage_cluster_block": ["EXTERNAL_READ"],
    "cpu_compute_block": ["EXTERNAL_READ", "NETWORK_EGRESS"],
    "ServiceBlock_OMS_v1": ["EXTERNAL_READ", "NETWORK_EGRESS"],
}


# ═══════════════════════════════════════════════════════════════
# Service Block Client
# ═══════════════════════════════════════════════════════════════

class ServiceBlockClient(ImmutableRuntimeConfiguration):
    """
    Explicit non-live simulation of a Service Block catalogue.

    No authenticated on-chain registry read is implemented by this client.

    Usage:
        client = ServiceBlockClient(simulation=True)  # VAMS_ENV=test/local/demo
        blocks = client.list_blocks(category="AI")
        blueprint = client.resolve_blueprint("llama_inference")
    """

    _immutable_runtime_fields = frozenset({"simulation", "runtime_policy", "_runtime_environ"})

    def __init__(self, contract_client=None, *, simulation: bool = False,
                 policy: Optional[RuntimePolicy] = None):
        if type(simulation) is not bool:
            raise RuntimeConfigurationError("ServiceBlockClient simulation must be a boolean")
        if policy is not None and type(policy) is not RuntimePolicy:
            raise RuntimeConfigurationError("ServiceBlockClient requires a RuntimePolicy")
        self._runtime_environ = os.environ
        self.runtime_policy = None
        # Default construction is inert/import-safe. It cannot later be armed.
        if simulation or policy is not None:
            observed = load_runtime_policy(self._runtime_environ)
            if policy is not None and policy != observed:
                raise RuntimeConfigurationError("Conflicting ServiceBlockClient runtime policy")
            observed.authorize_component_mock("ServiceBlockClient simulation", simulation)
            self.runtime_policy = observed
        self.simulation = simulation
        # Retained for API compatibility; its presence never qualifies a read.
        self._contract = contract_client
        self._freeze_runtime_configuration()

    def assert_simulation_available(self) -> None:
        """Reject before static catalogue access unless current non-live opt-in holds."""
        if not self.simulation or self.runtime_policy is None:
            raise LiveModeSafetyError("Authenticated Service Block registry reader unavailable")
        observed = load_runtime_policy(self._runtime_environ)
        if observed != self.runtime_policy:
            raise RuntimeConfigurationError("ServiceBlockClient runtime policy changed")
        observed.authorize_component_mock("ServiceBlockClient simulation", True)

    def list_macros(self) -> List[Dict[str, Any]]:
        self.assert_simulation_available()
        from neuron.services.macro_blocks import list_macros
        return list_macros()

    # ──────────────────────────────────────────────────
    # Query API
    # ──────────────────────────────────────────────────

    def list_blocks(
        self,
        category: Optional[str] = None,
        verified_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """List simulated declarations; verified_only is not an on-chain filter."""
        self.assert_simulation_available()
        result = []
        for name, bp in _SERVICE_BLOCK_BLUEPRINTS.items():
            memory_policy = self.get_memory_policy(name)
            manifest = self.get_skillops_manifest(name)
            block_info = {
                "simulation": True,
                "registry_verified": False,
                "evidence_classification": "non-authoritative",
                "name": name,
                "category": self._infer_category(name),
                "gpu_type": bp.compute.gpu_type.value,
                "gpu_count": bp.compute.gpu_count,
                "ram_gb": bp.memory.ram_gb,
                "storage_gb": bp.storage.capacity_gb,
                "max_cost_per_hour": bp.max_cost_per_hour,
                "tee_required": bp.tee.tee_type != TEEType.NONE,
                "memory_policy": memory_policy.value,
                "memory_policy_requires_review": (
                    memory_policy
                    == ServiceBlockMemoryPolicy.PERSISTENT_MUTATING_REQUIRES_REVIEW
                ),
                "skillops_manifest": manifest.to_dict(),
            }

            if category and block_info["category"] != category:
                continue

            result.append(block_info)
        return result

    def get_block(self, block_name: str) -> Optional[Dict[str, Any]]:
        """Get full metadata for a service block."""
        self.assert_simulation_available()
        bp = _SERVICE_BLOCK_BLUEPRINTS.get(block_name)
        if not bp:
            return None
        memory_policy = self.get_memory_policy(block_name)
        manifest = self.get_skillops_manifest(block_name)
        return {
            "simulation": True,
            "registry_verified": False,
            "evidence_classification": "non-authoritative",
            "name": block_name,
            "category": self._infer_category(block_name),
            "memory_policy": memory_policy.value,
            "memory_policy_requires_review": (
                memory_policy
                == ServiceBlockMemoryPolicy.PERSISTENT_MUTATING_REQUIRES_REVIEW
            ),
            "skillops_manifest": manifest.to_dict(),
            "blueprint": bp.to_dict(),
        }

    def get_memory_policy(self, block_name: str) -> ServiceBlockMemoryPolicy:
        """
        Return the memory policy for a registered service block.

        Missing or unknown policies fail closed so a live Service Block cannot
        silently become a persistent prompt-memory mutation surface.
        """
        self.assert_simulation_available()
        if block_name not in _SERVICE_BLOCK_BLUEPRINTS:
            raise KeyError(f"Unknown service block '{block_name}'")

        if block_name not in _SERVICE_BLOCK_MEMORY_POLICIES:
            raise KeyError(f"Missing memory policy for service block '{block_name}'")

        return self._validate_memory_policy(
            _SERVICE_BLOCK_MEMORY_POLICIES[block_name]
        )

    def get_skillops_manifest(self, block_name: str) -> ServiceBlockManifest:
        """
        Return validated SkillOps manifest metadata for a registered block.

        Missing or unknown permission scopes fail closed so off-chain registry
        mirrors do not silently grant undeclared capabilities.
        """
        self.assert_simulation_available()
        if block_name not in _SERVICE_BLOCK_BLUEPRINTS:
            raise KeyError(f"Unknown service block '{block_name}'")

        if block_name not in _SERVICE_BLOCK_PERMISSION_SCOPES:
            raise KeyError(f"Missing SkillOps manifest for service block '{block_name}'")

        manifest = ServiceBlockManifest(
            block_name=block_name,
            permission_scopes=list(_SERVICE_BLOCK_PERMISSION_SCOPES[block_name]),
        )
        return self.validate_skillops_manifest(manifest)

    def validate_skillops_manifest(
        self,
        manifest: ServiceBlockManifest,
    ) -> ServiceBlockManifest:
        """Validate SkillOps permission scopes and memory-policy coupling."""
        self.assert_simulation_available()
        if (
            isinstance(manifest.manifest_version, bool)
            or not isinstance(manifest.manifest_version, int)
            or manifest.manifest_version <= 0
        ):
            raise ValueError("SkillOps manifest version must be a positive integer")
        if not manifest.permission_scopes:
            raise ValueError("SkillOps manifest must declare at least one permission")

        permissions = {
            self._validate_permission_scope(scope)
            for scope in manifest.permission_scopes
        }
        memory_policy = self.get_memory_policy(manifest.block_name)
        if (
            ServiceBlockPermission.PERSISTENT_MUTATION in permissions
            and memory_policy
            != ServiceBlockMemoryPolicy.PERSISTENT_MUTATING_REQUIRES_REVIEW
        ):
            raise ValueError(
                "Persistent mutation permission requires review-gated memory policy"
            )

        manifest.permissions_bitmap()
        manifest.computed_manifest_hash()
        return manifest

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
            InstanceBlueprint after local declaration checks

        Raises:
            KeyError: If the block or required metadata is missing
            ValueError: If local permission or memory declarations are invalid
        """
        self.assert_simulation_available()
        bp = _SERVICE_BLOCK_BLUEPRINTS.get(block_name)
        if not bp:
            raise KeyError(
                f"Unknown service block '{block_name}'. "
                f"Available: {list(_SERVICE_BLOCK_BLUEPRINTS.keys())}"
            )
        # Resolution callers must pass the same local metadata checks as listings.
        self.get_skillops_manifest(block_name)
        return bp

    def resolve_macro(self, macro_name: str) -> List[InstanceBlueprint]:
        """
        Resolve a macro service block into its constituent blueprints.

        Args:
            macro_name: Name of the macro block

        Returns:
            List of InstanceBlueprints for all constituent blocks
        """
        self.assert_simulation_available()
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
    def _validate_memory_policy(policy: Any) -> ServiceBlockMemoryPolicy:
        """Validate a memory policy and reject unknown values."""
        if isinstance(policy, ServiceBlockMemoryPolicy):
            return policy

        try:
            return ServiceBlockMemoryPolicy(policy)
        except ValueError as exc:
            allowed = [p.value for p in ServiceBlockMemoryPolicy]
            raise ValueError(
                f"Unknown service block memory policy '{policy}'. "
                f"Allowed policies: {allowed}"
            ) from exc

    @staticmethod
    def _validate_permission_scope(scope: Any) -> ServiceBlockPermission:
        """Validate a SkillOps permission scope and reject unknown values."""
        if isinstance(scope, ServiceBlockPermission):
            return scope

        try:
            return ServiceBlockPermission(scope)
        except ValueError as exc:
            allowed = [p.value for p in ServiceBlockPermission]
            raise ValueError(
                f"Unknown service block permission scope '{scope}'. "
                f"Allowed scopes: {allowed}"
            ) from exc

    @staticmethod
    def _infer_category(name: str) -> str:
        """Infer category from block name."""
        ai_hints = ("llama", "inference", "vector", "compute")
        storage_hints = ("storage", "archive")
        security_hints = ("tee", "mev", "audit")
        network_hints = ("bridge", "payments", "x402", "oms")

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
