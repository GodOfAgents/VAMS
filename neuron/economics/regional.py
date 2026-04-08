"""
VAMS Regional Economics Model
===============================
Incentivizes providers to fill underserved geographic regions
via bootstrap multipliers that decay as capacity targets are met.

Multiplier Mechanics:
    - Region below 50% target capacity → full bootstrap multiplier
    - Region 50-100% capacity → linear decay from multiplier to 1.0×
    - Region at or above target → 1.0× (standard market rate)

This module provides the Python-side calculations. On-chain enforcement
is handled by RegionalIncentives.sol.

Architecture Reference:
    - ICN Gap #4: Regional Economics
    - VAMS Phase 3, Sprint 7
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("VAMS-RegionalEcon")


# ═══════════════════════════════════════════════════════════════
# Region Configuration
# ═══════════════════════════════════════════════════════════════

@dataclass
class RegionConfig:
    """Configuration for a geographic region."""
    region_id: str            # ISO 3166 or cloud region code
    display_name: str
    target_capacity: int      # Target number of capacity units
    bootstrap_multiplier: float  # Max reward multiplier (1.0 — 3.0)
    current_capacity: int = 0    # Live count from HardwareRegistry
    is_active: bool = True


# Default region configurations — bootstrap incentives for underserved areas
DEFAULT_REGIONS: Dict[str, RegionConfig] = {
    # Americas
    "us-east-1": RegionConfig("us-east-1", "US East (Virginia)", target_capacity=500, bootstrap_multiplier=1.0),
    "us-west-2": RegionConfig("us-west-2", "US West (Oregon)", target_capacity=400, bootstrap_multiplier=1.2),
    "sa-east-1": RegionConfig("sa-east-1", "South America (São Paulo)", target_capacity=100, bootstrap_multiplier=2.5),
    "ca-central-1": RegionConfig("ca-central-1", "Canada (Montreal)", target_capacity=150, bootstrap_multiplier=1.5),
    # Europe
    "eu-west-1": RegionConfig("eu-west-1", "EU West (Ireland)", target_capacity=400, bootstrap_multiplier=1.0),
    "eu-central-1": RegionConfig("eu-central-1", "EU Central (Frankfurt)", target_capacity=350, bootstrap_multiplier=1.1),
    "eu-north-1": RegionConfig("eu-north-1", "EU North (Stockholm)", target_capacity=100, bootstrap_multiplier=1.8),
    # Asia-Pacific
    "ap-southeast-1": RegionConfig("ap-southeast-1", "Asia Pacific (Singapore)", target_capacity=200, bootstrap_multiplier=2.0),
    "ap-northeast-1": RegionConfig("ap-northeast-1", "Asia Pacific (Tokyo)", target_capacity=250, bootstrap_multiplier=1.3),
    "ap-south-1": RegionConfig("ap-south-1", "Asia Pacific (Mumbai)", target_capacity=150, bootstrap_multiplier=2.5),
    # Middle East & Africa
    "me-south-1": RegionConfig("me-south-1", "Middle East (Bahrain)", target_capacity=50, bootstrap_multiplier=3.0),
    "af-south-1": RegionConfig("af-south-1", "Africa (Cape Town)", target_capacity=50, bootstrap_multiplier=3.0),
}


# ═══════════════════════════════════════════════════════════════
# Regional Economics Engine
# ═══════════════════════════════════════════════════════════════

class RegionalEconomics:
    """
    Calculates regional reward multipliers and capacity statistics.

    The multiplier incentivizes providers to deploy in underserved
    regions. As a region fills, the multiplier decays linearly
    from the bootstrap value to 1.0×.

    Usage:
        econ = RegionalEconomics()
        econ.update_capacity("af-south-1", 10)
        multiplier = econ.get_reward_multiplier("af-south-1")
        # Returns 3.0 (region far below 50% target)
    """

    def __init__(
        self,
        regions: Optional[Dict[str, RegionConfig]] = None,
    ):
        self._regions = {}
        source = regions or DEFAULT_REGIONS
        for k, v in source.items():
            self._regions[k] = RegionConfig(
                region_id=v.region_id,
                display_name=v.display_name,
                target_capacity=v.target_capacity,
                bootstrap_multiplier=v.bootstrap_multiplier,
                current_capacity=v.current_capacity,
                is_active=v.is_active,
            )

    # ──────────────────────────────────────────────────
    # Core Multiplier Calculation
    # ──────────────────────────────────────────────────

    def get_reward_multiplier(self, region_id: str) -> float:
        """
        Calculate the current reward multiplier for a region.

        Decay curve:
            - 0 — 50% of target:    full bootstrap_multiplier
            - 50% — 100% of target: linear decay → 1.0×
            - ≥ 100% of target:     1.0× (standard rate)

        Returns:
            float: Multiplier (1.0 — bootstrap_multiplier)
        """
        region = self._regions.get(region_id)
        if region is None or not region.is_active:
            return 1.0  # Unknown or inactive region = no boost

        if region.target_capacity <= 0:
            return 1.0

        fill_ratio = region.current_capacity / region.target_capacity

        if fill_ratio >= 1.0:
            # At or above target — standard market rate
            return 1.0
        elif fill_ratio <= 0.5:
            # Below 50% — full bootstrap incentive
            return region.bootstrap_multiplier
        else:
            # 50% — 100%: linear decay
            # At 50%: multiplier = bootstrap_multiplier
            # At 100%: multiplier = 1.0
            decay_progress = (fill_ratio - 0.5) / 0.5  # 0.0 → 1.0
            return region.bootstrap_multiplier - (
                (region.bootstrap_multiplier - 1.0) * decay_progress
            )

    # ──────────────────────────────────────────────────
    # Capacity Management
    # ──────────────────────────────────────────────────

    def update_capacity(self, region_id: str, capacity: int) -> None:
        """Update the current capacity for a region."""
        region = self._regions.get(region_id)
        if region:
            region.current_capacity = capacity
        else:
            logger.warning(f"Unknown region '{region_id}' — ignoring capacity update")

    def bulk_update_capacity(self, capacities: Dict[str, int]) -> None:
        """Batch update from HardwareRegistry node counts."""
        for region_id, capacity in capacities.items():
            self.update_capacity(region_id, capacity)

    # ──────────────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────────────

    def get_region_stats(self, region_id: str) -> Optional[Dict]:
        """Get stats for a specific region."""
        region = self._regions.get(region_id)
        if not region:
            return None

        return {
            "region_id": region.region_id,
            "display_name": region.display_name,
            "target_capacity": region.target_capacity,
            "current_capacity": region.current_capacity,
            "fill_ratio": round(region.current_capacity / max(1, region.target_capacity), 4),
            "bootstrap_multiplier": region.bootstrap_multiplier,
            "current_multiplier": round(self.get_reward_multiplier(region_id), 4),
            "is_active": region.is_active,
        }

    def get_all_region_stats(self) -> List[Dict]:
        """Get capacity heatmap data for all regions."""
        return [
            self.get_region_stats(rid)
            for rid in sorted(self._regions.keys())
        ]

    def get_all_multipliers(self) -> Dict[str, float]:
        """
        Get multiplier map for integration with CandidateScorer.

        Returns:
            Dict mapping region_id → current_multiplier
        """
        return {
            rid: self.get_reward_multiplier(rid)
            for rid in self._regions
        }

    def get_underserved_regions(self, threshold: float = 0.5) -> List[Dict]:
        """Get regions below the fill threshold."""
        result = []
        for rid, region in self._regions.items():
            if not region.is_active:
                continue
            fill = region.current_capacity / max(1, region.target_capacity)
            if fill < threshold:
                result.append(self.get_region_stats(rid))
        return sorted(result, key=lambda x: x["fill_ratio"])
