"""
VAMS Resource Composition Engine — Candidate Scorer
=====================================================
Multi-objective scoring engine that ranks hardware nodes
from the VAMSHardwareRegistry against an InstanceBlueprint.

Scoring Dimensions (each normalized to 0.0 — 1.0):
    1. Price       — Lower reservation price = higher score
    2. SLA History — Higher Sentinel benchmark score = higher score
    3. Latency     — Lower probe latency = higher score
    4. Regional    — Nodes in underserved regions get a boost (Sprint 7)

Architecture Reference:
    - ICN Gap #3: Resource Composition Engine
    - VAMS Phase 3, Sprint 5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from neuron.composer.models import (
    AllocationStatus,
    GPUType,
    InstanceBlueprint,
    ScoredCandidate,
    StorageType,
    TEEType,
)

logger = logging.getLogger("VAMS-Scorer")


# ═══════════════════════════════════════════════════════════════
# Scorer Configuration
# ═══════════════════════════════════════════════════════════════

@dataclass
class ScorerWeights:
    """
    Configurable weights for each scoring dimension.
    Must sum to 1.0 for normalized composite scores.
    """
    price: float = 0.35
    sla: float = 0.30
    latency: float = 0.20
    regional: float = 0.15
    skill_alignment: float = 0.0  # AUTOSKILL Phase 3b: Cosine similarity to requested skill vector

    def validate(self) -> None:
        total = self.price + self.sla + self.latency + self.regional + self.skill_alignment
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Scorer weights must sum to 1.0, got {total:.3f}. "
                f"Adjust weights: price={self.price}, sla={self.sla}, "
                f"latency={self.latency}, regional={self.regional}, "
                f"skill_alignment={self.skill_alignment}"
            )


# ═══════════════════════════════════════════════════════════════
# Raw Node Data (from HardwareRegistry / Sentinel)
# ═══════════════════════════════════════════════════════════════

@dataclass
class RawNodeData:
    """
    Unscored node data fetched from the HardwareRegistry and
    enriched with Sentinel telemetry. This is the input to the
    scorer — one per candidate node.
    """
    node_id: str
    provider: str                   # Provider address
    hw_class: str                   # e.g. "GPU_A100"
    region: str                     # e.g. "us-east-1"
    capacity_units: int             # Standardized capacity
    reservation_price: float        # $VAMS per hour
    collateral_staked: float        # $VAMS bonded
    is_active: bool = True
    benchmark_score_bps: int = 0    # 0-10000 from Sentinel
    latency_ms: float = 0.0        # From latency_probe
    last_benchmark_at: float = 0.0  # Unix timestamp
    skill_profile: Optional[List[float]] = None  # AUTOSKILL Phase 3b: extracted skill vector


# ═══════════════════════════════════════════════════════════════
# Candidate Scorer
# ═══════════════════════════════════════════════════════════════

class CandidateScorer:
    """
    Scores and ranks hardware nodes against an InstanceBlueprint.

    Usage:
        scorer = CandidateScorer()
        candidates = scorer.score(blueprint, raw_nodes)
        # candidates is sorted best-first
    """

    def __init__(
        self,
        weights: Optional[ScorerWeights] = None,
        regional_multipliers: Optional[Dict[str, float]] = None,
    ):
        self.weights = weights or ScorerWeights()
        self.weights.validate()

        # Regional boost multipliers (from RegionalEconomics, Sprint 7)
        # Keys are region names, values are bootstrap multipliers (1.0 = no boost)
        self._regional_multipliers = regional_multipliers or {}

    def set_regional_multipliers(self, multipliers: Dict[str, float]) -> None:
        """Update regional multipliers (called by RegionalEconomics)."""
        self._regional_multipliers = multipliers

    # ──────────────────────────────────────────────────
    # Main API
    # ──────────────────────────────────────────────────

    def score(
        self,
        blueprint: InstanceBlueprint,
        nodes: List[RawNodeData],
    ) -> List[ScoredCandidate]:
        """
        Score all candidate nodes against a blueprint.

        Steps:
            1. Filter nodes that don't match hard constraints
            2. Normalize each scoring dimension across remaining candidates
            3. Compute weighted composite score
            4. Sort best-first (highest score)

        Returns:
            List of ScoredCandidate, sorted by total_score descending.
            Empty list if no candidates pass hard filters.
        """
        # Step 1: Hard filter
        eligible = self._filter_eligible(blueprint, nodes)
        if not eligible:
            logger.warning(
                f"No eligible candidates for blueprint '{blueprint.name}' "
                f"(filtered {len(nodes)} nodes)"
            )
            return []

        # Step 2: Compute dimension ranges for normalization
        price_range = self._compute_range([n.reservation_price for n in eligible])
        sla_range = self._compute_range([n.benchmark_score_bps for n in eligible])
        latency_range = self._compute_range([n.latency_ms for n in eligible])

        # Step 3: Score each candidate
        scored: List[ScoredCandidate] = []
        for node in eligible:
            price_score = self._normalize_inverse(node.reservation_price, price_range)
            sla_score = self._normalize(node.benchmark_score_bps, sla_range)
            latency_score = self._normalize_inverse(node.latency_ms, latency_range)
            regional_score = self._compute_regional_score(node.region)
            
            # AUTOSKILL Phase 3b: Compute skill alignment score using Cosine Similarity
            skill_score = 0.0
            if blueprint.skill_vector and node.skill_profile:
                import math
                v1 = blueprint.skill_vector
                v2 = node.skill_profile
                if len(v1) == len(v2):
                    dot_product = sum(a * b for a, b in zip(v1, v2))
                    norm1 = math.sqrt(sum(a * a for a in v1))
                    norm2 = math.sqrt(sum(b * b for b in v2))
                    if norm1 > 0 and norm2 > 0:
                        cos_sim = dot_product / (norm1 * norm2)
                        # Normalize cosine similarity from [-1, 1] to [0, 1]
                        skill_score = (cos_sim + 1.0) / 2.0

            total = (
                self.weights.price * price_score
                + self.weights.sla * sla_score
                + self.weights.latency * latency_score
                + self.weights.regional * regional_score
                + self.weights.skill_alignment * skill_score
            )

            scored.append(ScoredCandidate(
                node_id=node.node_id,
                provider=node.provider,
                hw_class=node.hw_class,
                region=node.region,
                capacity_units=node.capacity_units,
                reservation_price=node.reservation_price,
                collateral_staked=node.collateral_staked,
                price_score=price_score,
                sla_score=sla_score,
                latency_score=latency_score,
                regional_score=regional_score,
                skill_alignment_score=skill_score,
                total_score=total,
                benchmark_score_bps=node.benchmark_score_bps,
                latency_ms=node.latency_ms,
            ))

        # Step 4: Sort best-first
        scored.sort(key=lambda c: c.total_score, reverse=True)

        logger.info(
            f"Scored {len(scored)} candidates for '{blueprint.name}'. "
            f"Best: {scored[0].node_id} (score={scored[0].total_score:.4f})"
        )
        return scored

    # ──────────────────────────────────────────────────
    # Hard Constraint Filtering
    # ──────────────────────────────────────────────────

    def _filter_eligible(
        self,
        blueprint: InstanceBlueprint,
        nodes: List[RawNodeData],
    ) -> List[RawNodeData]:
        """
        Remove nodes that cannot satisfy the blueprint's hard constraints.
        """
        eligible = []
        for node in nodes:
            if not node.is_active:
                continue

            # Hardware class must match compute spec
            if not blueprint.compute.matches_hw_class(node.hw_class):
                continue

            # Minimum SLA score
            if node.benchmark_score_bps < blueprint.min_sla_score_bps:
                continue

            # Region filter (if specified)
            if blueprint.networking.region and node.region != blueprint.networking.region:
                continue

            # Latency constraint
            if blueprint.networking.max_latency_ms > 0:
                if node.latency_ms > blueprint.networking.max_latency_ms:
                    continue

            # Budget constraint (per-node)
            if blueprint.max_cost_per_hour > 0:
                if node.reservation_price > blueprint.max_cost_per_hour:
                    continue

            # TFLOPS minimum
            if blueprint.compute.tflops_min > 0:
                # Approximate TFLOPS from benchmark score
                # Score 10000 = 100% of class baseline TFLOPS
                estimated_tflops = (node.benchmark_score_bps / 10000.0) * self._class_baseline_tflops(node.hw_class)
                if estimated_tflops < blueprint.compute.tflops_min:
                    continue

            eligible.append(node)

        return eligible

    # ──────────────────────────────────────────────────
    # Normalization Helpers
    # ──────────────────────────────────────────────────

    @staticmethod
    def _compute_range(values: List[float]) -> Tuple[float, float]:
        """Compute (min, max) for normalization. Handles edge cases."""
        if not values:
            return (0.0, 1.0)
        return (min(values), max(values))

    @staticmethod
    def _normalize(value: float, value_range: Tuple[float, float]) -> float:
        """Normalize to 0.0 — 1.0 (higher is better)."""
        mn, mx = value_range
        if mx == mn:
            return 1.0
        return max(0.0, min(1.0, (value - mn) / (mx - mn)))

    @staticmethod
    def _normalize_inverse(value: float, value_range: Tuple[float, float]) -> float:
        """Normalize to 0.0 — 1.0 (lower original value = higher score)."""
        mn, mx = value_range
        if mx == mn:
            return 1.0
        return max(0.0, min(1.0, 1.0 - (value - mn) / (mx - mn)))

    def _compute_regional_score(self, region: str) -> float:
        """
        Compute regional priority score.
        
        Regions with higher bootstrap multipliers (underserved) get
        higher scores to incentivize geographically diversified allocation.
        """
        if not self._regional_multipliers:
            return 0.5  # Neutral when no regional data

        multiplier = self._regional_multipliers.get(region, 1.0)

        # Normalize: multiplier range is typically 1.0 — 3.0
        # Map to 0.0 — 1.0 where higher multiplier = higher score
        max_multiplier = max(self._regional_multipliers.values()) if self._regional_multipliers else 3.0
        return min(1.0, (multiplier - 1.0) / max(1.0, max_multiplier - 1.0))

    @staticmethod
    def _class_baseline_tflops(hw_class: str) -> float:
        """Approximate baseline TFLOPS per hardware class."""
        baselines = {
            "GPU_H100": 989.0,   # FP16
            "GPU_A100": 312.0,   # FP16
            "GPU_L40S": 362.0,   # FP16
            "GPU_RTX_4090": 165.0,  # FP16
            "CPU_EPYC": 5.0,     # FP64 approximate
            "CPU_XEON": 4.0,     # FP64 approximate
        }
        return baselines.get(hw_class, 10.0)
