"""
VAMS Resource Allocator — Unit Tests
=======================================
Tests single-provider, multi-provider, and elastic
allocation strategies.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from neuron.composer.allocator import AllocationError, ResourceAllocator
from neuron.composer.models import (
    ComputeSpec,
    GPUType,
    InstanceBlueprint,
    MemorySpec,
    ScoredCandidate,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

def _scored(node_id, capacity, price, score=0.9, provider="0xP", hw="GPU_A100", region="us-east-1"):
    return ScoredCandidate(
        node_id=node_id, provider=provider, hw_class=hw, region=region,
        capacity_units=capacity, reservation_price=price, collateral_staked=2000.0,
        total_score=score, price_score=score, sla_score=score,
        latency_score=score, regional_score=0.5,
    )


def _blueprint(name="test", gpu_count=4, max_cost=0.0, elastic=False, min_rep=1, max_rep=1):
    return InstanceBlueprint(
        name=name,
        compute=ComputeSpec(gpu_type=GPUType.A100, gpu_count=gpu_count, vcpu=32),
        memory=MemorySpec(ram_gb=128),
        max_cost_per_hour=max_cost,
        elastic=elastic,
        min_replicas=min_rep,
        max_replicas=max_rep,
        min_sla_score_bps=0,
    )


# ═══════════════════════════════════════════════════════════════
# Tests: Single-Provider Allocation
# ═══════════════════════════════════════════════════════════════

class TestSingleProvider:

    def test_single_node_satisfies_blueprint(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=4)
        candidates = [_scored("node-big", capacity=8, price=25.0)]
        plan = allocator.allocate(bp, candidates)
        assert plan.total_nodes == 1
        assert plan.is_multi_provider is False
        assert plan.assignments[0].allocated_units == 4
        assert plan.total_hourly_cost == 100.0  # 25 * 4

    def test_prefers_single_provider_over_multi(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=4)
        candidates = [
            _scored("big", capacity=8, price=30.0, score=0.8),
            _scored("small1", capacity=2, price=20.0, score=0.9),
            _scored("small2", capacity=2, price=20.0, score=0.85),
        ]
        plan = allocator.allocate(bp, candidates)
        assert plan.total_nodes == 1
        assert plan.assignments[0].node_id == "big"


# ═══════════════════════════════════════════════════════════════
# Tests: Multi-Provider Bin-Packing
# ═══════════════════════════════════════════════════════════════

class TestMultiProvider:

    def test_bin_packing_across_multiple_nodes(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=6)
        candidates = [
            _scored("n1", capacity=3, price=20.0, score=0.9, provider="0xP1"),
            _scored("n2", capacity=3, price=22.0, score=0.85, provider="0xP2"),
            _scored("n3", capacity=3, price=25.0, score=0.8, provider="0xP3"),
        ]
        plan = allocator.allocate(bp, candidates)
        assert plan.total_nodes == 2
        assert plan.is_multi_provider is True
        total_allocated = sum(a.allocated_units for a in plan.assignments)
        assert total_allocated == 6

    def test_insufficient_capacity_raises(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=10)
        candidates = [
            _scored("n1", capacity=3, price=20.0),
            _scored("n2", capacity=3, price=22.0),
        ]
        with pytest.raises(AllocationError, match="Insufficient capacity"):
            allocator.allocate(bp, candidates)

    def test_no_candidates_raises(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=4)
        with pytest.raises(AllocationError, match="No candidates"):
            allocator.allocate(bp, [])

    def test_multi_provider_diverse_providers(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=4)
        candidates = [
            _scored("n1", capacity=2, price=20.0, score=0.9, provider="0xA"),
            _scored("n2", capacity=2, price=22.0, score=0.85, provider="0xB"),
        ]
        plan = allocator.allocate(bp, candidates)
        assert plan.is_multi_provider is True


# ═══════════════════════════════════════════════════════════════
# Tests: Budget Enforcement
# ═══════════════════════════════════════════════════════════════

class TestBudgetEnforcement:

    def test_budget_cap_single_provider(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=4, max_cost=50.0)
        candidates = [
            _scored("expensive", capacity=8, price=20.0, score=0.9),  # 20*4=80 > 50
            _scored("cheap", capacity=8, price=10.0, score=0.8),       # 10*4=40 < 50
        ]
        plan = allocator.allocate(bp, candidates)
        assert plan.assignments[0].node_id == "cheap"
        assert plan.total_hourly_cost <= 50.0

    def test_budget_cap_multi_provider(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=4, max_cost=100.0)
        candidates = [
            _scored("n1", capacity=2, price=20.0, score=0.9),  # 40
            _scored("n2", capacity=2, price=25.0, score=0.85), # 50
        ]
        plan = allocator.allocate(bp, candidates)
        assert plan.total_hourly_cost <= 100.0


# ═══════════════════════════════════════════════════════════════
# Tests: Elastic Allocation
# ═══════════════════════════════════════════════════════════════

class TestElasticAllocation:

    def test_elastic_provisions_min_replicas(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=4, elastic=True, min_rep=2, max_rep=8)
        candidates = [
            _scored("n1", capacity=4, price=20.0, score=0.9),
            _scored("n2", capacity=4, price=22.0, score=0.85),
            _scored("n3", capacity=4, price=25.0, score=0.8),
        ]
        plan = allocator.allocate(bp, candidates)
        assert plan.total_nodes == 2  # min_replicas

    def test_elastic_single_replica(self):
        allocator = ResourceAllocator()
        bp = _blueprint(gpu_count=2, elastic=True, min_rep=1, max_rep=4)
        candidates = [_scored("n1", capacity=4, price=20.0)]
        plan = allocator.allocate(bp, candidates)
        assert plan.total_nodes == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
