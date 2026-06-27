"""
VAMS CHC Cognitive Scorer — Unit Tests
========================================
Tests the CHC cognitive shortfall scoring formula, blueprint serialization,
and multi-axis ranking behavior in CandidateScorer.
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
)
from neuron.composer.scorer import (
    CandidateScorer,
    RawNodeData,
    ScorerWeights,
)


def test_blueprint_hashing_with_cognitive_requirements():
    """Verify cognitive requirements are hashed and serialized correctly."""
    bp1 = InstanceBlueprint(
        name="test-bp",
        cognitive_requirements={"K": 0.8, "R": 0.9}
    )
    bp2 = InstanceBlueprint(
        name="test-bp",
        cognitive_requirements={"K": 0.8, "R": 0.5}
    )
    bp3 = InstanceBlueprint(
        name="test-bp",
        cognitive_requirements={"R": 0.9, "K": 0.8} # different order, same content
    )

    # Different cognitive profiles must produce different hashes
    assert bp1.blueprint_hash() != bp2.blueprint_hash()
    
    # Deterministic order hashing (sorting keys)
    assert bp1.blueprint_hash() == bp3.blueprint_hash()

    # to_dict serialization check
    d = bp1.to_dict()
    assert "cognitive_requirements" in d
    assert d["cognitive_requirements"] == {"K": 0.8, "R": 0.9}


def test_cognitive_shortfall_calculation_exact_match():
    """Verify node meeting all cognitive requirements gets 1.0."""
    bp = InstanceBlueprint(
        name="exact-match-bp",
        cognitive_requirements={"WM": 0.8, "MS": 0.7},
        min_sla_score_bps=0
    )
    
    node = RawNodeData(
        node_id="node-1",
        provider="0x1",
        hw_class="GPU_ANY",
        region="us-east-1",
        capacity_units=4,
        reservation_price=10.0,
        collateral_staked=1000.0,
        cognitive_profile={"WM": 0.8, "MS": 0.7}
    )

    scorer = CandidateScorer(weights=ScorerWeights(
        price=0.20, sla=0.20, latency=0.20, regional=0.20, skill_alignment=0.10, cognitive_alignment=0.10
    ))
    
    candidates = scorer.score(bp, [node])
    assert len(candidates) == 1
    assert candidates[0].cognitive_alignment_score == 1.0


def test_cognitive_shortfall_calculation_with_penalties():
    """Verify node below cognitive requirements gets penalized proportionally."""
    bp = InstanceBlueprint(
        name="shortfall-bp",
        cognitive_requirements={"WM": 0.8, "MS": 0.8},
        min_sla_score_bps=0
    )
    
    # Node shortfall:
    # WM: Req 0.8, Prof 0.6 -> shortfall = 0.2
    # MS: Req 0.8, Prof 0.4 -> shortfall = 0.4
    # Mean shortfall = (0.2 + 0.4) / 2 = 0.3
    # Alignment score = 1.0 - 0.3 = 0.7
    node = RawNodeData(
        node_id="node-1",
        provider="0x1",
        hw_class="GPU_ANY",
        region="us-east-1",
        capacity_units=4,
        reservation_price=10.0,
        collateral_staked=1000.0,
        cognitive_profile={"WM": 0.6, "MS": 0.4}
    )

    scorer = CandidateScorer(weights=ScorerWeights(
        price=0.20, sla=0.20, latency=0.20, regional=0.20, skill_alignment=0.10, cognitive_alignment=0.10
    ))
    
    candidates = scorer.score(bp, [node])
    assert len(candidates) == 1
    assert abs(candidates[0].cognitive_alignment_score - 0.7) < 0.001


def test_cognitive_shortfall_exceeding_requirements():
    """Verify exceeding requirements does not penalize and is clamped to 1.0."""
    bp = InstanceBlueprint(
        name="exceeds-bp",
        cognitive_requirements={"WM": 0.5, "MS": 0.5},
        min_sla_score_bps=0
    )
    
    # Node:
    # WM: Req 0.5, Prof 0.9 -> shortfall = 0.0 (clamped)
    # MS: Req 0.5, Prof 0.8 -> shortfall = 0.0 (clamped)
    # Mean shortfall = 0.0
    # Alignment score = 1.0
    node = RawNodeData(
        node_id="node-1",
        provider="0x1",
        hw_class="GPU_ANY",
        region="us-east-1",
        capacity_units=4,
        reservation_price=10.0,
        collateral_staked=1000.0,
        cognitive_profile={"WM": 0.9, "MS": 0.8}
    )

    scorer = CandidateScorer(weights=ScorerWeights(
        price=0.20, sla=0.20, latency=0.20, regional=0.20, skill_alignment=0.10, cognitive_alignment=0.10
    ))
    
    candidates = scorer.score(bp, [node])
    assert len(candidates) == 1
    assert candidates[0].cognitive_alignment_score == 1.0


def test_candidate_ranking_based_on_chc_profile():
    """Verify ranking favors nodes with better cognitive alignment."""
    bp = InstanceBlueprint(
        name="ranking-bp",
        cognitive_requirements={"K": 0.8, "R": 0.8},
        min_sla_score_bps=0
    )
    
    # Perfect match: S_cog = 1.0
    node_best = RawNodeData(
        node_id="best-node",
        provider="0x1",
        hw_class="GPU_ANY",
        region="us-east-1",
        capacity_units=4,
        reservation_price=10.0,
        collateral_staked=1000.0,
        cognitive_profile={"K": 0.8, "R": 0.8}
    )

    # Moderate match: S_cog = 0.85
    node_mid = RawNodeData(
        node_id="mid-node",
        provider="0x2",
        hw_class="GPU_ANY",
        region="us-east-1",
        capacity_units=4,
        reservation_price=10.0,
        collateral_staked=1000.0,
        cognitive_profile={"K": 0.7, "R": 0.6}  # shortfalls: 0.1, 0.2 -> mean 0.15
    )

    # Poor match: S_cog = 0.4
    node_poor = RawNodeData(
        node_id="poor-node",
        provider="0x3",
        hw_class="GPU_ANY",
        region="us-east-1",
        capacity_units=4,
        reservation_price=10.0,
        collateral_staked=1000.0,
        cognitive_profile={"K": 0.2, "R": 0.2}  # shortfalls: 0.6, 0.6 -> mean 0.6
    )

    scorer = CandidateScorer(weights=ScorerWeights(
        price=0.10, sla=0.10, latency=0.10, regional=0.10, skill_alignment=0.10, cognitive_alignment=0.50
    ))
    
    candidates = scorer.score(bp, [node_mid, node_poor, node_best])
    assert len(candidates) == 3
    assert candidates[0].node_id == "best-node"
    assert candidates[1].node_id == "mid-node"
    assert candidates[2].node_id == "poor-node"
    assert candidates[0].total_score > candidates[1].total_score > candidates[2].total_score


def test_both_skill_and_cognitive_alignment():
    """Verify both PCA skill alignment and CHC cognitive alignment work together."""
    bp = InstanceBlueprint(
        name="dual-alignment-bp",
        skill_vector=[1.0, 0.0],
        cognitive_requirements={"M": 0.8},
        min_sla_score_bps=0
    )
    
    # Perfectly aligned in skills (cosine sim = 1.0) and cognitive (S_cog = 1.0)
    node_good = RawNodeData(
        node_id="good-node",
        provider="0x1",
        hw_class="GPU_ANY",
        region="us-east-1",
        capacity_units=4,
        reservation_price=10.0,
        collateral_staked=1000.0,
        skill_profile=[1.0, 0.0],
        cognitive_profile={"M": 0.8}
    )

    # Poor skills (cosine sim = 0.5 normalized) but good cognitive
    node_bad_skills = RawNodeData(
        node_id="bad-skills-node",
        provider="0x2",
        hw_class="GPU_ANY",
        region="us-east-1",
        capacity_units=4,
        reservation_price=10.0,
        collateral_staked=1000.0,
        skill_profile=[0.0, 1.0],  # orthogonal -> cos_sim = 0.0 -> normalized is 0.5
        cognitive_profile={"M": 0.8}
    )

    scorer = CandidateScorer(weights=ScorerWeights(
        price=0.20, sla=0.20, latency=0.20, regional=0.20, skill_alignment=0.10, cognitive_alignment=0.10
    ))

    candidates = scorer.score(bp, [node_bad_skills, node_good])
    assert len(candidates) == 2
    assert candidates[0].node_id == "good-node"
    assert candidates[0].skill_alignment_score == 1.0
    assert candidates[0].cognitive_alignment_score == 1.0

    assert candidates[1].node_id == "bad-skills-node"
    assert abs(candidates[1].skill_alignment_score - 0.5) < 0.001
    assert candidates[1].cognitive_alignment_score == 1.0

    # good-node total score should be higher because of skill alignment score
    assert candidates[0].total_score > candidates[1].total_score
