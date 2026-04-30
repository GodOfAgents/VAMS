"""
VAMS Candidate Scorer — Unit Tests
====================================
Tests the multi-objective scoring engine's filtering,
normalization, and ranking behavior.
"""

import sys
import os
import pytest

# Ensure neuron package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from neuron.composer.models import (
    ComputeSpec,
    GPUType,
    InstanceBlueprint,
    MemorySpec,
    NetworkSpec,
    ScoredCandidate,
    StorageSpec,
    StorageType,
)
from neuron.composer.scorer import (
    CandidateScorer,
    RawNodeData,
    ScorerWeights,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

def _make_nodes() -> list:
    """Create a realistic set of candidate nodes."""
    return [
        RawNodeData(
            node_id="node-a100-useast-1",
            provider="0xProvider1",
            hw_class="GPU_A100",
            region="us-east-1",
            capacity_units=8,
            reservation_price=25.0,
            collateral_staked=5000.0,
            benchmark_score_bps=9200,
            latency_ms=12.0,
        ),
        RawNodeData(
            node_id="node-a100-useast-2",
            provider="0xProvider2",
            hw_class="GPU_A100",
            region="us-east-1",
            capacity_units=4,
            reservation_price=30.0,
            collateral_staked=3000.0,
            benchmark_score_bps=8500,
            latency_ms=18.0,
        ),
        RawNodeData(
            node_id="node-h100-euwest-1",
            provider="0xProvider3",
            hw_class="GPU_H100",
            region="eu-west-1",
            capacity_units=8,
            reservation_price=60.0,
            collateral_staked=10000.0,
            benchmark_score_bps=9800,
            latency_ms=45.0,
        ),
        RawNodeData(
            node_id="node-a100-apac-1",
            provider="0xProvider4",
            hw_class="GPU_A100",
            region="ap-southeast-1",
            capacity_units=4,
            reservation_price=20.0,
            collateral_staked=4000.0,
            benchmark_score_bps=7800,
            latency_ms=80.0,
        ),
        RawNodeData(
            node_id="node-rtx4090-uswest-1",
            provider="0xProvider5",
            hw_class="GPU_RTX_4090",
            region="us-west-2",
            capacity_units=2,
            reservation_price=8.0,
            collateral_staked=1000.0,
            benchmark_score_bps=9500,
            latency_ms=15.0,
        ),
        # Inactive node — should always be filtered
        RawNodeData(
            node_id="node-dead",
            provider="0xProviderDead",
            hw_class="GPU_A100",
            region="us-east-1",
            capacity_units=4,
            reservation_price=5.0,
            collateral_staked=1000.0,
            benchmark_score_bps=9900,
            latency_ms=5.0,
            is_active=False,
        ),
        # Low SLA node — should be filtered by most blueprints
        RawNodeData(
            node_id="node-lowsla",
            provider="0xProviderLow",
            hw_class="GPU_A100",
            region="us-east-1",
            capacity_units=4,
            reservation_price=10.0,
            collateral_staked=2000.0,
            benchmark_score_bps=3000,  # 30% SLA, below typical threshold
            latency_ms=10.0,
        ),
    ]


def _standard_blueprint() -> InstanceBlueprint:
    """Standard A100 inference blueprint."""
    return InstanceBlueprint(
        name="test-inference",
        compute=ComputeSpec(gpu_type=GPUType.A100, gpu_count=4, vcpu=32),
        memory=MemorySpec(ram_gb=128),
        storage=StorageSpec(type=StorageType.NVME, capacity_gb=500),
        networking=NetworkSpec(region=""),  # Any region
        max_cost_per_hour=0.0,  # No budget cap
        min_sla_score_bps=7500,  # 75% minimum
    )


# ═══════════════════════════════════════════════════════════════
# Tests: Filtering
# ═══════════════════════════════════════════════════════════════

class TestCandidateFiltering:
    """Test hard constraint filtering."""

    def test_inactive_nodes_filtered(self):
        scorer = CandidateScorer()
        nodes = _make_nodes()
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        node_ids = [c.node_id for c in candidates]
        assert "node-dead" not in node_ids

    def test_low_sla_filtered(self):
        scorer = CandidateScorer()
        nodes = _make_nodes()
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        node_ids = [c.node_id for c in candidates]
        assert "node-lowsla" not in node_ids

    def test_wrong_hw_class_filtered(self):
        scorer = CandidateScorer()
        nodes = _make_nodes()
        bp = _standard_blueprint()  # Requires GPU_A100
        candidates = scorer.score(bp, nodes)
        node_ids = [c.node_id for c in candidates]
        # H100 nodes and RTX 4090 should be filtered
        assert "node-h100-euwest-1" not in node_ids
        assert "node-rtx4090-uswest-1" not in node_ids

    def test_region_filter(self):
        scorer = CandidateScorer()
        nodes = _make_nodes()
        bp = _standard_blueprint()
        bp.networking.region = "us-east-1"
        candidates = scorer.score(bp, nodes)
        for c in candidates:
            assert c.region == "us-east-1"

    def test_budget_filter(self):
        scorer = CandidateScorer()
        nodes = _make_nodes()
        bp = _standard_blueprint()
        bp.max_cost_per_hour = 22.0
        candidates = scorer.score(bp, nodes)
        for c in candidates:
            assert c.reservation_price <= 22.0

    def test_any_gpu_includes_all(self):
        scorer = CandidateScorer()
        nodes = _make_nodes()
        bp = _standard_blueprint()
        bp.compute.gpu_type = GPUType.ANY
        bp.min_sla_score_bps = 0  # No SLA filter
        candidates = scorer.score(bp, nodes)
        # Should include A100, H100, and RTX_4090 (but not inactive)
        hw_classes = {c.hw_class for c in candidates}
        assert "GPU_A100" in hw_classes
        assert "GPU_H100" in hw_classes
        assert "GPU_RTX_4090" in hw_classes


# ═══════════════════════════════════════════════════════════════
# Tests: Scoring & Ranking
# ═══════════════════════════════════════════════════════════════

class TestCandidateScoring:
    """Test scoring normalization and ranking."""

    def test_scores_sorted_descending(self):
        scorer = CandidateScorer()
        nodes = _make_nodes()
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        for i in range(len(candidates) - 1):
            assert candidates[i].total_score >= candidates[i + 1].total_score

    def test_scores_in_valid_range(self):
        scorer = CandidateScorer()
        nodes = _make_nodes()
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        for c in candidates:
            assert 0.0 <= c.total_score <= 1.0
            assert 0.0 <= c.price_score <= 1.0
            assert 0.0 <= c.sla_score <= 1.0
            assert 0.0 <= c.latency_score <= 1.0
            assert 0.0 <= c.regional_score <= 1.0

    def test_cheaper_node_gets_higher_price_score(self):
        scorer = CandidateScorer()
        nodes = [
            RawNodeData(
                node_id="cheap", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=10.0, collateral_staked=2000.0,
                benchmark_score_bps=8000, latency_ms=20.0,
            ),
            RawNodeData(
                node_id="expensive", provider="0x2", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=50.0, collateral_staked=2000.0,
                benchmark_score_bps=8000, latency_ms=20.0,
            ),
        ]
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        cheap = next(c for c in candidates if c.node_id == "cheap")
        expensive = next(c for c in candidates if c.node_id == "expensive")
        assert cheap.price_score > expensive.price_score

    def test_better_sla_gets_higher_sla_score(self):
        scorer = CandidateScorer()
        nodes = [
            RawNodeData(
                node_id="good_sla", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9500, latency_ms=20.0,
            ),
            RawNodeData(
                node_id="bad_sla", provider="0x2", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=7600, latency_ms=20.0,
            ),
        ]
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        good = next(c for c in candidates if c.node_id == "good_sla")
        bad = next(c for c in candidates if c.node_id == "bad_sla")
        assert good.sla_score > bad.sla_score

    def test_lower_latency_gets_higher_latency_score(self):
        scorer = CandidateScorer()
        nodes = [
            RawNodeData(
                node_id="fast", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=8000, latency_ms=5.0,
            ),
            RawNodeData(
                node_id="slow", provider="0x2", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=8000, latency_ms=100.0,
            ),
        ]
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        fast = next(c for c in candidates if c.node_id == "fast")
        slow = next(c for c in candidates if c.node_id == "slow")
        assert fast.latency_score > slow.latency_score


# ═══════════════════════════════════════════════════════════════
# Tests: Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_no_candidates_returns_empty(self):
        scorer = CandidateScorer()
        bp = _standard_blueprint()
        assert scorer.score(bp, []) == []

    def test_all_filtered_returns_empty(self):
        """All nodes fail hard constraints."""
        scorer = CandidateScorer()
        nodes = [
            RawNodeData(
                node_id="bad", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=1000,  # Way below 7500 threshold
                latency_ms=20.0,
            ),
        ]
        bp = _standard_blueprint()
        assert scorer.score(bp, nodes) == []

    def test_single_candidate(self):
        """Single eligible node should score 1.0 across all dimensions."""
        scorer = CandidateScorer()
        nodes = [
            RawNodeData(
                node_id="only", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9000, latency_ms=20.0,
            ),
        ]
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        assert len(candidates) == 1
        # With single candidate, all dimension scores should be 1.0
        c = candidates[0]
        assert c.price_score == 1.0
        assert c.sla_score == 1.0
        assert c.latency_score == 1.0


# ═══════════════════════════════════════════════════════════════
# Tests: Regional Scoring
# ═══════════════════════════════════════════════════════════════

class TestRegionalScoring:
    """Test regional priority scoring."""

    def test_underserved_region_gets_boost(self):
        scorer = CandidateScorer(
            regional_multipliers={
                "us-east-1": 1.0,       # Saturated
                "ap-southeast-1": 3.0,  # Underserved
            }
        )
        nodes = [
            RawNodeData(
                node_id="saturated", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9000, latency_ms=20.0,
            ),
            RawNodeData(
                node_id="underserved", provider="0x2", hw_class="GPU_A100",
                region="ap-southeast-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9000, latency_ms=20.0,
            ),
        ]
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        underserved = next(c for c in candidates if c.node_id == "underserved")
        saturated = next(c for c in candidates if c.node_id == "saturated")
        assert underserved.regional_score > saturated.regional_score

    def test_no_regional_data_gives_neutral_score(self):
        scorer = CandidateScorer()  # No regional multipliers
        nodes = [
            RawNodeData(
                node_id="n1", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9000, latency_ms=20.0,
            ),
        ]
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        assert candidates[0].regional_score == 0.5  # Neutral


# ═══════════════════════════════════════════════════════════════
# Tests: Weight Configuration
# ═══════════════════════════════════════════════════════════════

class TestWeightConfiguration:
    """Test custom weight configurations."""

    def test_invalid_weights_raises(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            CandidateScorer(weights=ScorerWeights(
                price=0.5, sla=0.5, latency=0.5, regional=0.5
            ))

    def test_price_heavy_weights(self):
        """When price weight is dominant, cheapest node should win."""
        scorer = CandidateScorer(weights=ScorerWeights(
            price=0.85, sla=0.05, latency=0.05, regional=0.05
        ))
        nodes = [
            RawNodeData(
                node_id="cheap", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=10.0, collateral_staked=2000.0,
                benchmark_score_bps=7600, latency_ms=80.0,
            ),
            RawNodeData(
                node_id="expensive_great", provider="0x2", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=100.0, collateral_staked=2000.0,
                benchmark_score_bps=9999, latency_ms=1.0,
            ),
        ]
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        assert candidates[0].node_id == "cheap"

    def test_sla_heavy_weights(self):
        """When SLA weight is dominant, best-performing node should win."""
        scorer = CandidateScorer(weights=ScorerWeights(
            price=0.05, sla=0.85, latency=0.05, regional=0.05
        ))
        nodes = [
            RawNodeData(
                node_id="cheap_bad", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=5.0, collateral_staked=2000.0,
                benchmark_score_bps=7600, latency_ms=10.0,
            ),
            RawNodeData(
                node_id="expensive_good", provider="0x2", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=100.0, collateral_staked=2000.0,
                benchmark_score_bps=9999, latency_ms=10.0,
            ),
        ]
        bp = _standard_blueprint()
        candidates = scorer.score(bp, nodes)
        assert candidates[0].node_id == "expensive_good"


# ═══════════════════════════════════════════════════════════════
# Tests: Skill Alignment Scoring
# ═══════════════════════════════════════════════════════════════

class TestSkillAlignmentScoring:
    """Test AUTOSKILL Phase 3b: Cosine similarity-based skill alignment."""

    def test_high_alignment_wins(self):
        scorer = CandidateScorer(weights=ScorerWeights(
            price=0.20, sla=0.20, latency=0.20, regional=0.20, skill_alignment=0.20
        ))
        
        # Two nodes with same metrics but different skill profiles
        nodes = [
            RawNodeData(
                node_id="aligned", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9000, latency_ms=20.0,
                skill_profile=[0.9, 0.1, 0.0]  # Very aligned with blueprint
            ),
            RawNodeData(
                node_id="misaligned", provider="0x2", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9000, latency_ms=20.0,
                skill_profile=[-0.9, 0.1, 0.0]  # Misaligned
            ),
        ]
        
        bp = _standard_blueprint()
        bp.skill_vector = [1.0, 0.0, 0.0]  # Requesting skill dimension 0
        
        candidates = scorer.score(bp, nodes)
        aligned = next(c for c in candidates if c.node_id == "aligned")
        misaligned = next(c for c in candidates if c.node_id == "misaligned")
        
        assert aligned.skill_alignment_score > misaligned.skill_alignment_score
        assert aligned.total_score > misaligned.total_score

    def test_missing_skill_profile_neutral_score(self):
        scorer = CandidateScorer(weights=ScorerWeights(
            price=0.20, sla=0.20, latency=0.20, regional=0.20, skill_alignment=0.20
        ))
        
        nodes = [
            RawNodeData(
                node_id="no_profile", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9000, latency_ms=20.0,
                skill_profile=None
            )
        ]
        
        bp = _standard_blueprint()
        bp.skill_vector = [1.0, 0.0, 0.0]
        
        candidates = scorer.score(bp, nodes)
        assert candidates[0].skill_alignment_score == 0.0
        
    def test_no_blueprint_skill_vector_neutral_score(self):
        scorer = CandidateScorer(weights=ScorerWeights(
            price=0.20, sla=0.20, latency=0.20, regional=0.20, skill_alignment=0.20
        ))
        
        nodes = [
            RawNodeData(
                node_id="has_profile", provider="0x1", hw_class="GPU_A100",
                region="us-east-1", capacity_units=4,
                reservation_price=25.0, collateral_staked=2000.0,
                benchmark_score_bps=9000, latency_ms=20.0,
                skill_profile=[1.0, 0.0, 0.0]
            )
        ]
        
        bp = _standard_blueprint()
        bp.skill_vector = None
        
        candidates = scorer.score(bp, nodes)
        assert candidates[0].skill_alignment_score == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
