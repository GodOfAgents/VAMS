"""
Tests for the Provider Reward Distribution Engine.
Validates base reward calculation, regional bonus stacking,
staking tier boosts, builder revenue, and Merkle root generation.
"""

import pytest
from neuron.economics.regional import RegionalEconomics, RegionConfig
from neuron.economics.reward_engine import (
    RewardEngine,
    ProviderReward,
    StakingTier,
    get_staking_tier,
    get_boost_bps,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def economics():
    regions = {
        "us-east-1": RegionConfig("us-east-1", "US East", target_capacity=500, bootstrap_multiplier=1.0, current_capacity=500),
        "af-south-1": RegionConfig("af-south-1", "Africa South", target_capacity=50, bootstrap_multiplier=3.0, current_capacity=10),
    }
    return RegionalEconomics(regions=regions)


@pytest.fixture
def engine(economics):
    return RewardEngine(regional_economics=economics)


@pytest.fixture
def sample_providers():
    return [
        {
            "address": "0xP1",
            "region_id": "us-east-1",
            "capacity_contribution": 100,
            "escrow_completions": 5000.0,
            "staked_amount": 100_000.0,  # SILVER
        },
        {
            "address": "0xP2",
            "region_id": "af-south-1",
            "capacity_contribution": 20,
            "escrow_completions": 3000.0,
            "staked_amount": 1_500_000.0,  # DIAMOND
        },
        {
            "address": "0xP3",
            "region_id": "us-east-1",
            "capacity_contribution": 50,
            "escrow_completions": 2000.0,
            "staked_amount": 5_000.0,  # IRON
        },
    ]


# ═══════════════════════════════════════════════════════════════
# Tier Tests
# ═══════════════════════════════════════════════════════════════

class TestStakingTiers:
    def test_iron_tier(self):
        assert get_staking_tier(0) == StakingTier.IRON
        assert get_staking_tier(5_000) == StakingTier.IRON
        assert get_boost_bps(StakingTier.IRON) == 0

    def test_bronze_tier(self):
        assert get_staking_tier(10_000) == StakingTier.BRONZE
        assert get_staking_tier(49_999) == StakingTier.BRONZE
        assert get_boost_bps(StakingTier.BRONZE) == 200

    def test_silver_tier(self):
        assert get_staking_tier(50_000) == StakingTier.SILVER
        assert get_staking_tier(199_999) == StakingTier.SILVER
        assert get_boost_bps(StakingTier.SILVER) == 500

    def test_gold_tier(self):
        assert get_staking_tier(200_000) == StakingTier.GOLD
        assert get_staking_tier(999_999) == StakingTier.GOLD
        assert get_boost_bps(StakingTier.GOLD) == 1_000

    def test_diamond_tier(self):
        assert get_staking_tier(1_000_000) == StakingTier.DIAMOND
        assert get_staking_tier(10_000_000) == StakingTier.DIAMOND
        assert get_boost_bps(StakingTier.DIAMOND) == 2_000


# ═══════════════════════════════════════════════════════════════
# Reward Calculation Tests
# ═══════════════════════════════════════════════════════════════

class TestEpochRewards:
    def test_proportional_base_rewards(self, engine, sample_providers):
        """Providers get base rewards proportional to escrow completions."""
        result = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)

        assert result.provider_count == 3
        # P1: 5000/10000 = 50%, P2: 3000/10000 = 30%, P3: 2000/10000 = 20%
        p1 = result.provider_rewards[0]
        p2 = result.provider_rewards[1]
        p3 = result.provider_rewards[2]

        assert abs(p1.base_reward - 5000.0) < 1.0
        assert abs(p2.base_reward - 3000.0) < 1.0
        assert abs(p3.base_reward - 2000.0) < 1.0

    def test_regional_bonus_applied(self, engine, sample_providers):
        """Provider in underserved region gets regional bonus."""
        result = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)

        # P2 is in af-south-1 (3.0x multiplier) → bonus = base × (3.0 - 1.0) = 6000
        p2 = result.provider_rewards[1]
        assert p2.regional_bonus > 0
        expected_bonus = p2.base_reward * 2.0  # (3.0 - 1.0)
        assert abs(p2.regional_bonus - expected_bonus) < 1.0

    def test_no_regional_bonus_at_target(self, engine, sample_providers):
        """Provider in saturated region gets no regional bonus."""
        result = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)

        p1 = result.provider_rewards[0]
        assert p1.regional_bonus == 0.0

    def test_staking_boost_silver(self, engine, sample_providers):
        """SILVER tier provider gets +5% staking boost."""
        result = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)

        p1 = result.provider_rewards[0]
        expected_boost = (p1.base_reward * 500) / 10_000  # +5%
        assert abs(p1.staking_boost - expected_boost) < 1.0
        assert p1.staking_tier == StakingTier.SILVER

    def test_staking_boost_diamond(self, engine, sample_providers):
        """DIAMOND tier gets +20% staking boost."""
        result = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)

        p2 = result.provider_rewards[1]
        expected_boost = (p2.base_reward * 2_000) / 10_000  # +20%
        assert abs(p2.staking_boost - expected_boost) < 1.0
        assert p2.staking_tier == StakingTier.DIAMOND

    def test_no_staking_boost_iron(self, engine, sample_providers):
        """IRON tier gets no staking boost."""
        result = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)

        p3 = result.provider_rewards[2]
        assert p3.staking_boost == 0.0
        assert p3.staking_tier == StakingTier.IRON

    def test_builder_revenue_integration(self, engine, sample_providers):
        """Builder revenue is added to provider rewards."""
        builder_revs = {"0xP1": 500.0, "0xP3": 200.0}
        result = engine.calculate_epoch_rewards(
            sample_providers, epoch_emission_budget=10_000.0, builder_revenues=builder_revs
        )

        p1 = result.provider_rewards[0]
        p3 = result.provider_rewards[2]
        assert p1.builder_revenue == 500.0
        assert p3.builder_revenue == 200.0

        # P2 has no builder revenue
        p2 = result.provider_rewards[1]
        assert p2.builder_revenue == 0.0

    def test_total_reward_sum(self, engine, sample_providers):
        """Total reward should be sum of all components."""
        result = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)

        for r in result.provider_rewards:
            expected = r.base_reward + r.regional_bonus + r.staking_boost + r.builder_revenue
            assert abs(r.total_reward - expected) < 0.01

    def test_empty_providers(self, engine):
        """Empty provider list returns empty summary."""
        result = engine.calculate_epoch_rewards([], epoch_emission_budget=10_000.0)
        assert result.provider_count == 0
        assert result.total_distributed == 0.0


# ═══════════════════════════════════════════════════════════════
# APR Estimation Tests
# ═══════════════════════════════════════════════════════════════

class TestAPREstimation:
    def test_apr_positive(self, engine):
        """APR should be positive for a provider with stake."""
        result = engine.estimate_provider_apr(
            region_id="af-south-1",
            capacity_contribution=10,
            staked_amount=100_000.0,
            epoch_emission_budget=383_000.0,
            total_region_capacity=50,
        )

        assert result["apr"] > 0
        assert result["apr_pct"] > 0
        assert result["staking_tier"] == "SILVER"

    def test_apr_zero_stake(self, engine):
        """Zero stake should return 0 APR."""
        result = engine.estimate_provider_apr(
            region_id="us-east-1",
            capacity_contribution=10,
            staked_amount=0.0,
            epoch_emission_budget=383_000.0,
        )
        assert result["apr"] == 0.0

    def test_apr_includes_regional_bonus(self, engine):
        """APR in underserved region should be higher."""
        apr_us = engine.estimate_provider_apr(
            region_id="us-east-1",
            capacity_contribution=10,
            staked_amount=100_000.0,
            epoch_emission_budget=383_000.0,
            total_region_capacity=500,
        )

        apr_af = engine.estimate_provider_apr(
            region_id="af-south-1",
            capacity_contribution=10,
            staked_amount=100_000.0,
            epoch_emission_budget=383_000.0,
            total_region_capacity=50,
        )

        assert apr_af["apr"] > apr_us["apr"], "Underserved region should have higher APR"


# ═══════════════════════════════════════════════════════════════
# Merkle Root Tests
# ═══════════════════════════════════════════════════════════════

class TestMerkleRoot:
    def test_merkle_root_deterministic(self, engine, sample_providers):
        """Same inputs should produce same Merkle root."""
        result1 = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)
        result2 = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)

        assert result1.merkle_root == result2.merkle_root

    def test_merkle_root_format(self, engine, sample_providers):
        """Merkle root should be a hex string."""
        result = engine.calculate_epoch_rewards(sample_providers, epoch_emission_budget=10_000.0)
        assert result.merkle_root.startswith("0x")
        assert len(result.merkle_root) == 66  # 0x + 64 hex chars

    def test_merkle_root_empty(self, engine):
        """Empty rewards should produce zero root."""
        result = engine.calculate_epoch_rewards([], epoch_emission_budget=10_000.0)
        assert result.merkle_root == "0x" + "0" * 64
