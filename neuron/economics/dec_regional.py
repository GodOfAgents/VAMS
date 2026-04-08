"""
VAMS Region-Aware Dynamic Emission Controller (DEC) Simulator
===============================================================
Off-chain simulation of region-weighted emission allocation.
Used by the Gateway API for reward estimation and by the Keeper
bot for pre-flight epoch calculations.

Architecture Reference:
    - ICN Gap #4: Regional Economics
    - VAMS Phase 4, Sprint 9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from neuron.economics.regional import RegionalEconomics, RegionConfig

logger = logging.getLogger("VAMS-DEC-Regional")


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

@dataclass
class RegionEmissionAlloc:
    """Per-region emission allocation for an epoch."""
    region_id: str
    weighted_capacity: float
    allocation_bps: int       # Share of epoch budget (BPS)
    emitted_this_epoch: float = 0.0


@dataclass
class EpochSimulation:
    """Result of simulating an epoch's emission distribution."""
    epoch_id: int
    total_emission_budget: float
    global_emission_rate_bps: int
    total_supply: float
    epoch_duration_days: float
    region_allocations: List[RegionEmissionAlloc]
    total_emitted: float
    region_cap_bps: int


# ═══════════════════════════════════════════════════════════════
# Region-Aware DEC Simulator
# ═══════════════════════════════════════════════════════════════

class RegionAwareDECSimulator:
    """
    Simulates region-weighted emission allocation off-chain.

    This mirrors the on-chain RegionAwareDEC.sol logic for:
      - Pre-flight checks before keeper transactions
      - Gateway API reward estimation endpoints
      - Dashboard emission forecasting

    Usage:
        econ = RegionalEconomics()
        econ.update_capacity("af-south-1", 10)
        sim = RegionAwareDECSimulator(regional_economics=econ)
        result = sim.simulate_epoch(epoch_id=1)
    """

    def __init__(
        self,
        regional_economics: Optional[RegionalEconomics] = None,
        total_supply: float = 1_000_000_000.0,
        global_emission_rate_bps: int = 200,  # 2% annual
        epoch_duration_days: float = 7.0,
        region_cap_bps: int = 3_000,  # 30%
    ):
        self._economics = regional_economics or RegionalEconomics()
        self.total_supply = total_supply
        self.global_emission_rate_bps = global_emission_rate_bps
        self.epoch_duration_days = epoch_duration_days
        self.region_cap_bps = region_cap_bps

    # ──────────────────────────────────────────────────
    # Core Simulation
    # ──────────────────────────────────────────────────

    def get_epoch_emission_budget(self) -> float:
        """
        Calculate the total emission budget for one epoch.

        Formula: totalSupply × annualRate / 10000 × (epochDays / 365.25)
        """
        annual_emission = (self.total_supply * self.global_emission_rate_bps) / 10_000
        epoch_budget = annual_emission * (self.epoch_duration_days / 365.25)
        return epoch_budget

    def simulate_epoch(self, epoch_id: int = 0) -> EpochSimulation:
        """
        Simulate a full epoch's emission distribution across regions.

        Returns:
            EpochSimulation with per-region allocations and totals.
        """
        epoch_budget = self.get_epoch_emission_budget()

        # Phase 1: calculate weighted capacities
        all_stats = self._economics.get_all_region_stats()
        raw_allocations: List[RegionEmissionAlloc] = []
        total_weighted_cap = 0.0

        for stat in all_stats:
            if not stat["is_active"]:
                continue

            multiplier = stat["current_multiplier"]
            capacity = max(stat["current_capacity"], 1)  # min 1 for bootstrapping
            weighted_cap = capacity * multiplier

            raw_allocations.append(RegionEmissionAlloc(
                region_id=stat["region_id"],
                weighted_capacity=weighted_cap,
                allocation_bps=0,
            ))
            total_weighted_cap += weighted_cap

        if total_weighted_cap == 0 or len(raw_allocations) == 0:
            return EpochSimulation(
                epoch_id=epoch_id,
                total_emission_budget=epoch_budget,
                global_emission_rate_bps=self.global_emission_rate_bps,
                total_supply=self.total_supply,
                epoch_duration_days=self.epoch_duration_days,
                region_allocations=[],
                total_emitted=0.0,
                region_cap_bps=self.region_cap_bps,
            )

        # Phase 2: proportional BPS allocation with cap enforcement
        capped_total_bps = 0
        uncapped_indices = []

        for i, alloc in enumerate(raw_allocations):
            raw_bps = int((alloc.weighted_capacity * 10_000) / total_weighted_cap)

            if raw_bps > self.region_cap_bps:
                alloc.allocation_bps = self.region_cap_bps
                capped_total_bps += self.region_cap_bps
            else:
                alloc.allocation_bps = raw_bps  # preliminary
                uncapped_indices.append(i)

        # Redistribute capped surplus
        if capped_total_bps > 0 and len(uncapped_indices) > 0:
            remaining_bps = 10_000 - capped_total_bps
            uncapped_weighted_total = sum(
                raw_allocations[i].weighted_capacity for i in uncapped_indices
            )

            if uncapped_weighted_total > 0:
                for i in uncapped_indices:
                    raw_allocations[i].allocation_bps = int(
                        (raw_allocations[i].weighted_capacity * remaining_bps)
                        / uncapped_weighted_total
                    )

        # Phase 3: calculate token amounts
        total_emitted = 0.0
        for alloc in raw_allocations:
            alloc.emitted_this_epoch = (epoch_budget * alloc.allocation_bps) / 10_000
            total_emitted += alloc.emitted_this_epoch

        return EpochSimulation(
            epoch_id=epoch_id,
            total_emission_budget=epoch_budget,
            global_emission_rate_bps=self.global_emission_rate_bps,
            total_supply=self.total_supply,
            epoch_duration_days=self.epoch_duration_days,
            region_allocations=raw_allocations,
            total_emitted=total_emitted,
            region_cap_bps=self.region_cap_bps,
        )

    # ──────────────────────────────────────────────────
    # Provider Reward Estimation
    # ──────────────────────────────────────────────────

    def estimate_provider_reward(
        self,
        region_id: str,
        capacity_contribution: int,
    ) -> Dict:
        """
        Estimate a single provider's reward for contributing capacity.

        Args:
            region_id: The region the provider operates in.
            capacity_contribution: How many capacity units the provider contributes.

        Returns:
            Dict with estimated weekly and annualized reward.
        """
        epoch = self.simulate_epoch()

        # Find this region's allocation
        region_alloc = None
        for alloc in epoch.region_allocations:
            if alloc.region_id == region_id:
                region_alloc = alloc
                break

        if region_alloc is None:
            return {
                "region_id": region_id,
                "weekly_reward": 0.0,
                "annual_reward": 0.0,
                "share_of_region": 0.0,
                "region_total_emission": 0.0,
                "error": "Region not found or inactive",
            }

        # Provider's share of the region = contribution / total region capacity
        region_stats = self._economics.get_region_stats(region_id)
        total_region_capacity = max(region_stats["current_capacity"], 1)
        provider_share = capacity_contribution / total_region_capacity

        weekly_reward = region_alloc.emitted_this_epoch * provider_share
        annual_reward = weekly_reward * (365.25 / self.epoch_duration_days)

        return {
            "region_id": region_id,
            "weekly_reward": round(weekly_reward, 4),
            "annual_reward": round(annual_reward, 4),
            "share_of_region": round(provider_share, 6),
            "region_total_emission": round(region_alloc.emitted_this_epoch, 4),
            "region_multiplier": round(region_stats["current_multiplier"], 4),
            "region_fill_ratio": round(region_stats["fill_ratio"], 4),
        }

    def estimate_provider_apr(
        self,
        region_id: str,
        capacity_contribution: int,
        staked_amount: float,
    ) -> float:
        """
        Estimate annualized APR for a provider.

        Args:
            region_id: Provider's region.
            capacity_contribution: Units of capacity.
            staked_amount: Amount of $VAMS staked by this provider.

        Returns:
            APR as a decimal (e.g. 0.15 = 15%)
        """
        if staked_amount <= 0:
            return 0.0

        estimate = self.estimate_provider_reward(region_id, capacity_contribution)
        annual_reward = estimate.get("annual_reward", 0.0)

        return annual_reward / staked_amount if staked_amount > 0 else 0.0

    # ──────────────────────────────────────────────────
    # Batch Helpers
    # ──────────────────────────────────────────────────

    def get_all_region_emissions(self) -> List[Dict]:
        """
        Get emission breakdown for all regions (for dashboard heatmap).

        Returns:
            List of dicts with region emission details.
        """
        epoch = self.simulate_epoch()
        return [
            {
                "region_id": alloc.region_id,
                "weighted_capacity": round(alloc.weighted_capacity, 2),
                "allocation_pct": round(alloc.allocation_bps / 100, 2),
                "emission_tokens": round(alloc.emitted_this_epoch, 4),
            }
            for alloc in epoch.region_allocations
        ]
