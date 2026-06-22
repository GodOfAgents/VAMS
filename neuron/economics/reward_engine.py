"""
VAMS Provider Reward Distribution Engine
==========================================
Off-chain reward calculation combining regional bonuses,
staking tier boosts, and builder revenue shares.

Used by the keeper bot to prepare on-chain reward distributions
and by the Gateway API for APR/reward estimation endpoints.

Architecture Reference:
    - VAMS Phase 4, Sprint 11
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from neuron.economics.regional import RegionalEconomics
from neuron.economics.gas_premium import GasAbstractionPremiumCalculator

logger = logging.getLogger("VAMS-RewardEngine")


# ═══════════════════════════════════════════════════════════════
# Staking Tier Definitions
# ═══════════════════════════════════════════════════════════════

class StakingTier(Enum):
    IRON = "IRON"
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    DIAMOND = "DIAMOND"


# Tier thresholds (in VAMS tokens) and boost BPS
TIER_CONFIG = {
    StakingTier.IRON:    {"min_stake": 0,          "boost_bps": 0},
    StakingTier.BRONZE:  {"min_stake": 10_000,     "boost_bps": 200},    # +2%
    StakingTier.SILVER:  {"min_stake": 50_000,     "boost_bps": 500},    # +5%
    StakingTier.GOLD:    {"min_stake": 200_000,    "boost_bps": 1_000},  # +10%
    StakingTier.DIAMOND: {"min_stake": 1_000_000,  "boost_bps": 2_000},  # +20%
}


def get_staking_tier(staked_amount: float) -> StakingTier:
    """Determine staking tier from staked token amount."""
    for tier in reversed(list(StakingTier)):
        if staked_amount >= TIER_CONFIG[tier]["min_stake"]:
            return tier
    return StakingTier.IRON


def get_boost_bps(tier: StakingTier) -> int:
    """Get the boost BPS for a staking tier."""
    return TIER_CONFIG[tier]["boost_bps"]


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

@dataclass
class ProviderReward:
    """Reward breakdown for a single provider."""
    provider: str
    region_id: str
    base_reward: float
    regional_bonus: float
    staking_boost: float
    builder_revenue: float = 0.0
    gas_premium_burn: float = 0.0
    symbiosis_decay_factor: float = 1.0
    total_reward: float = 0.0
    staking_tier: StakingTier = StakingTier.IRON

    def __post_init__(self):
        self.total_reward = max(0.0, (
            self.base_reward
            + self.regional_bonus
            + self.staking_boost
            + self.builder_revenue
            - self.gas_premium_burn
        ) * self.symbiosis_decay_factor)


@dataclass
class EpochRewardSummary:
    """Summary of an epoch's reward distribution."""
    epoch_id: int
    total_distributed: float
    provider_count: int
    provider_rewards: List[ProviderReward]
    merkle_root: str = ""


# ═══════════════════════════════════════════════════════════════
# Reward Engine
# ═══════════════════════════════════════════════════════════════

class RewardEngine:
    """
    Off-chain provider reward calculation engine.

    Computes rewards for all active providers in an epoch by combining:
    1. Base reward — proportional to escrow completions
    2. Regional bonus — from RegionalIncentives multipliers
    3. Staking boost — tier-based percentage addition
    4. Builder revenue — accumulated marketplace revenue shares

    Usage:
        engine = RewardEngine(regional_economics=econ)
        rewards = engine.calculate_epoch_rewards(
            providers=provider_list,
            epoch_emission_budget=383_000.0,
        )
    """

    def __init__(
        self,
        regional_economics: Optional[RegionalEconomics] = None,
    ):
        self._economics = regional_economics or RegionalEconomics()

    # ──────────────────────────────────────────────────
    # Core Calculation
    # ──────────────────────────────────────────────────

    def calculate_epoch_rewards(
        self,
        providers: List[Dict],
        epoch_emission_budget: float,
        builder_revenues: Optional[Dict[str, float]] = None,
    ) -> EpochRewardSummary:
        """
        Calculate rewards for all providers in an epoch.

        Args:
            providers: List of dicts with keys:
                - address: str — provider wallet
                - region_id: str — operating region
                - capacity_contribution: int — capacity units contributed
                - escrow_completions: float — total settlement value completed
                - staked_amount: float — VAMS staked by this provider
            epoch_emission_budget: Total tokens available for emission this epoch.
            builder_revenues: Optional dict of builder_address → accumulated revenue.

        Returns:
            EpochRewardSummary with per-provider breakdown.
        """
        if not providers:
            return EpochRewardSummary(
                epoch_id=0, 
                total_distributed=0.0, 
                provider_count=0, 
                provider_rewards=[],
                merkle_root="0x" + "0" * 64
            )

        # Step 1: Calculate base rewards proportional to escrow completions
        total_completions = sum(p.get("escrow_completions", 0.0) for p in providers)
        rewards: List[ProviderReward] = []
        calculator = GasAbstractionPremiumCalculator()

        for prov in providers:
            address = prov["address"]
            region_id = prov.get("region_id", "")
            staked = prov.get("staked_amount", 0.0)
            completions = prov.get("escrow_completions", 0.0)

            # Base: proportional to completions share of epoch budget
            if total_completions > 0:
                base_share = completions / total_completions
            else:
                base_share = 1.0 / len(providers)

            base_reward = epoch_emission_budget * base_share

            # Regional bonus
            regional_bonus = 0.0
            if region_id:
                try:
                    stats = self._economics.get_region_stats(region_id)
                    multiplier = stats.get("current_multiplier", 1.0)
                    if multiplier > 1.0:
                        regional_bonus = base_reward * (multiplier - 1.0)
                except (KeyError, Exception):
                    pass

            # Staking boost
            tier = get_staking_tier(staked)
            boost_bps = get_boost_bps(tier)
            staking_boost = (base_reward * boost_bps) / 10_000

            # Builder revenue
            builder_rev = 0.0
            if builder_revenues and address in builder_revenues:
                builder_rev = builder_revenues[address]

            # Gas premium burn portion
            required_blocks = prov.get("required_service_blocks", [])
            premium_rate = calculator.calculate_premium_rate(required_blocks)
            gas_premium_burn = base_reward * premium_rate

            # Calculate loopback/wash-trading decay factor: F = prod(1 - e^(-lambda * dt))
            decay_factor = 1.0
            decay_rate = 0.5 / 86400  # lambda = 0.5 per day
            deltas = prov.get("loopback_deltas", [])
            for dt in deltas:
                # dt is time delta in seconds
                event_decay = 1.0 - math.exp(-decay_rate * float(dt))
                decay_factor *= event_decay

            reward = ProviderReward(
                provider=address,
                region_id=region_id,
                base_reward=round(base_reward, 6),
                regional_bonus=round(regional_bonus, 6),
                staking_boost=round(staking_boost, 6),
                builder_revenue=round(builder_rev, 6),
                gas_premium_burn=round(gas_premium_burn, 6),
                symbiosis_decay_factor=round(decay_factor, 6),
                staking_tier=tier,
            )
            rewards.append(reward)

        total_distributed = sum(r.total_reward for r in rewards)

        summary = EpochRewardSummary(
            epoch_id=0,
            total_distributed=round(total_distributed, 6),
            provider_count=len(rewards),
            provider_rewards=rewards,
        )

        # Generate merkle root
        summary.merkle_root = self.generate_merkle_root(rewards)

        return summary

    # ──────────────────────────────────────────────────
    # APR Estimation
    # ──────────────────────────────────────────────────

    def estimate_provider_apr(
        self,
        region_id: str,
        capacity_contribution: int,
        staked_amount: float,
        epoch_emission_budget: float,
        total_region_capacity: int = 100,
        epochs_per_year: float = 52.18,
    ) -> Dict:
        """
        Estimate annualized APR for a provider.

        Returns:
            Dict with apr, weekly_reward, annual_reward, tier details.
        """
        if total_region_capacity <= 0:
            total_region_capacity = 1

        # Provider's capacity share
        capacity_share = capacity_contribution / total_region_capacity

        # Base weekly reward
        base_reward = epoch_emission_budget * capacity_share

        # Regional bonus
        regional_bonus = 0.0
        try:
            stats = self._economics.get_region_stats(region_id)
            multiplier = stats.get("current_multiplier", 1.0)
            if multiplier > 1.0:
                regional_bonus = base_reward * (multiplier - 1.0)
        except Exception:
            pass

        # Staking boost
        tier = get_staking_tier(staked_amount)
        boost_bps = get_boost_bps(tier)
        staking_boost = (base_reward * boost_bps) / 10_000

        weekly_total = base_reward + regional_bonus + staking_boost
        annual_total = weekly_total * epochs_per_year

        apr = annual_total / staked_amount if staked_amount > 0 else 0.0

        return {
            "apr": round(apr, 6),
            "apr_pct": round(apr * 100, 2),
            "weekly_reward": round(weekly_total, 4),
            "annual_reward": round(annual_total, 4),
            "base_reward": round(base_reward, 4),
            "regional_bonus": round(regional_bonus, 4),
            "staking_boost": round(staking_boost, 4),
            "staking_tier": tier.value,
            "boost_pct": round(boost_bps / 100, 1),
        }

    # ──────────────────────────────────────────────────
    # Merkle Root
    # ──────────────────────────────────────────────────

    def generate_merkle_root(self, rewards: List[ProviderReward]) -> str:
        """
        Generate a Merkle root from reward entries for on-chain submission.

        Uses simple binary tree with keccak-like hashing (SHA-256 for off-chain).
        """
        if not rewards:
            return "0x" + "0" * 64

        # Create leaf hashes
        leaves = []
        for r in rewards:
            leaf_data = f"{r.provider}:{r.total_reward}:{r.region_id}:{r.symbiosis_decay_factor}"
            leaf_hash = hashlib.sha256(leaf_data.encode()).hexdigest()
            leaves.append(leaf_hash)

        # Build tree bottom-up
        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])  # Duplicate last for odd count

            next_level = []
            for i in range(0, len(leaves), 2):
                combined = leaves[i] + leaves[i + 1]
                parent = hashlib.sha256(combined.encode()).hexdigest()
                next_level.append(parent)
            leaves = next_level

        return f"0x{leaves[0]}"
