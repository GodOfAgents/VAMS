"""
VAMS Resource Composition Engine — Pre-defined Blueprints
==========================================================
ICN-inspired Instance Blueprints for common infrastructure patterns.

These blueprints serve as starting templates — agents can use them
directly or customize before submission.

Architecture Reference:
    - ICN Gap #3: Resource Composition Engine
    - VAMS Phase 3, Sprint 6
"""

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


# ═══════════════════════════════════════════════════════════════
# AI / ML Blueprints
# ═══════════════════════════════════════════════════════════════

AI_INFERENCE_STANDARD = InstanceBlueprint(
    name="AI_INFERENCE_STANDARD",
    compute=ComputeSpec(gpu_type=GPUType.A100, gpu_count=4, vcpu=32, tflops_min=250.0),
    memory=MemorySpec(ram_gb=128, bandwidth_gbps=100.0),
    storage=StorageSpec(type=StorageType.NVME, capacity_gb=500, iops_min=50000),
    networking=NetworkSpec(bandwidth_mbps=1000),
    max_cost_per_hour=50.0,
    min_sla_score_bps=8000,
)

AI_TRAINING_LARGE = InstanceBlueprint(
    name="AI_TRAINING_LARGE",
    compute=ComputeSpec(gpu_type=GPUType.H100, gpu_count=8, vcpu=64, tflops_min=800.0),
    memory=MemorySpec(ram_gb=512, bandwidth_gbps=200.0),
    storage=StorageSpec(type=StorageType.NVME, capacity_gb=2000, iops_min=100000),
    networking=NetworkSpec(bandwidth_mbps=10000),
    max_cost_per_hour=200.0,
    min_duration_seconds=3600 * 4,    # 4h minimum
    max_duration_seconds=3600 * 72,   # 72h maximum
    min_sla_score_bps=9000,
)

AI_FINETUNING_BUDGET = InstanceBlueprint(
    name="AI_FINETUNING_BUDGET",
    compute=ComputeSpec(gpu_type=GPUType.RTX_4090, gpu_count=2, vcpu=16),
    memory=MemorySpec(ram_gb=64),
    storage=StorageSpec(type=StorageType.NVME, capacity_gb=200, iops_min=20000),
    networking=NetworkSpec(bandwidth_mbps=500),
    max_cost_per_hour=15.0,
    min_sla_score_bps=7000,
)

# ═══════════════════════════════════════════════════════════════
# Storage Blueprints
# ═══════════════════════════════════════════════════════════════

STORAGE_CLUSTER = InstanceBlueprint(
    name="STORAGE_CLUSTER",
    compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=16),
    memory=MemorySpec(ram_gb=64),
    storage=StorageSpec(type=StorageType.NVME, capacity_gb=10000, iops_min=100000),
    networking=NetworkSpec(bandwidth_mbps=10000),
    max_cost_per_hour=30.0,
    min_sla_score_bps=9000,
)

ARCHIVE_STORAGE = InstanceBlueprint(
    name="ARCHIVE_STORAGE",
    compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=4),
    memory=MemorySpec(ram_gb=16),
    storage=StorageSpec(type=StorageType.HDD, capacity_gb=50000, persistent=True),
    networking=NetworkSpec(bandwidth_mbps=100),
    max_cost_per_hour=5.0,
    min_sla_score_bps=7500,
)

# ═══════════════════════════════════════════════════════════════
# Edge / Low-Latency Blueprints
# ═══════════════════════════════════════════════════════════════

EDGE_INFERENCE = InstanceBlueprint(
    name="EDGE_INFERENCE",
    compute=ComputeSpec(gpu_type=GPUType.RTX_4090, gpu_count=1, vcpu=16),
    memory=MemorySpec(ram_gb=64),
    storage=StorageSpec(type=StorageType.NVME, capacity_gb=100),
    networking=NetworkSpec(bandwidth_mbps=1000, max_latency_ms=20),
    max_cost_per_hour=10.0,
    min_sla_score_bps=8500,
)

# ═══════════════════════════════════════════════════════════════
# Confidential Compute Blueprints
# ═══════════════════════════════════════════════════════════════

CONFIDENTIAL_COMPUTE = InstanceBlueprint(
    name="CONFIDENTIAL_COMPUTE",
    compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=32),
    memory=MemorySpec(ram_gb=128),
    storage=StorageSpec(type=StorageType.NVME, capacity_gb=500),
    networking=NetworkSpec(bandwidth_mbps=1000),
    tee=TEESpec(tee_type=TEEType.SGX, attestation_required=True),
    max_cost_per_hour=40.0,
    min_sla_score_bps=9000,
    min_trust_tier="gold",
)

CONFIDENTIAL_AI = InstanceBlueprint(
    name="CONFIDENTIAL_AI",
    compute=ComputeSpec(gpu_type=GPUType.A100, gpu_count=2, vcpu=32),
    memory=MemorySpec(ram_gb=128),
    storage=StorageSpec(type=StorageType.NVME, capacity_gb=500),
    networking=NetworkSpec(bandwidth_mbps=1000),
    tee=TEESpec(tee_type=TEEType.NITRO, attestation_required=True),
    max_cost_per_hour=80.0,
    min_sla_score_bps=9000,
    min_trust_tier="gold",
)

# ═══════════════════════════════════════════════════════════════
# Elastic / Auto-Scaling Blueprints
# ═══════════════════════════════════════════════════════════════

ELASTIC_API_GATEWAY = InstanceBlueprint(
    name="ELASTIC_API_GATEWAY",
    compute=ComputeSpec(gpu_type=GPUType.ANY, gpu_count=0, vcpu=8),
    memory=MemorySpec(ram_gb=32),
    storage=StorageSpec(type=StorageType.NVME, capacity_gb=100),
    networking=NetworkSpec(bandwidth_mbps=5000, max_latency_ms=10),
    elastic=True,
    min_replicas=2,
    max_replicas=8,
    max_cost_per_hour=50.0,
    min_sla_score_bps=9000,
)


# ═══════════════════════════════════════════════════════════════
# Blueprint Registry (Lookup by name)
# ═══════════════════════════════════════════════════════════════

BLUEPRINT_REGISTRY = {
    "AI_INFERENCE_STANDARD": AI_INFERENCE_STANDARD,
    "AI_TRAINING_LARGE": AI_TRAINING_LARGE,
    "AI_FINETUNING_BUDGET": AI_FINETUNING_BUDGET,
    "STORAGE_CLUSTER": STORAGE_CLUSTER,
    "ARCHIVE_STORAGE": ARCHIVE_STORAGE,
    "EDGE_INFERENCE": EDGE_INFERENCE,
    "CONFIDENTIAL_COMPUTE": CONFIDENTIAL_COMPUTE,
    "CONFIDENTIAL_AI": CONFIDENTIAL_AI,
    "ELASTIC_API_GATEWAY": ELASTIC_API_GATEWAY,
}


def get_blueprint(name: str) -> InstanceBlueprint:
    """Look up a pre-defined blueprint by name."""
    bp = BLUEPRINT_REGISTRY.get(name)
    if bp is None:
        raise KeyError(
            f"Unknown blueprint '{name}'. "
            f"Available: {list(BLUEPRINT_REGISTRY.keys())}"
        )
    return bp


def list_blueprints() -> list:
    """List all available blueprint names and summaries."""
    result = []
    for name, bp in BLUEPRINT_REGISTRY.items():
        result.append({
            "name": name,
            "blueprint_hash": bp.blueprint_hash(),
            "gpu_type": bp.compute.gpu_type.value,
            "gpu_count": bp.compute.gpu_count,
            "ram_gb": bp.memory.ram_gb,
            "storage_gb": bp.storage.capacity_gb,
            "max_cost_per_hour": bp.max_cost_per_hour,
            "elastic": bp.elastic,
        })
    return result
