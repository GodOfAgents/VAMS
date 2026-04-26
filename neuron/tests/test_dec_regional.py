"""
Tests for the Region-Aware DEC Simulator.
Validates emission allocation math, cap enforcement, and provider reward estimation.
"""

import pytest
from neuron.economics.regional import RegionalEconomics, RegionConfig
from neuron.economics.dec_regional import (
    RegionAwareDECSimulator,
    RegionEmissionAlloc,
    EpochSimulation,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def basic_economics():
    """Economics engine with 4 regions at varying fill levels."""
    regions = {
        "us-east-1": RegionConfig("us-east-1", "US East", target_capacity=500, bootstrap_multiplier=1.0, current_capacity=500),
        "eu-west-1": RegionConfig("eu-west-1", "EU West", target_capacity=400, bootstrap_multiplier=1.0, current_capacity=300),
        "af-south-1": RegionConfig("af-south-1", "Africa South", target_capacity=50, bootstrap_multiplier=3.0, current_capacity=10),
        "ap-south-1": RegionConfig("ap-south-1", "AP South", target_capacity=150, bootstrap_multiplier=2.5, current_capacity=60),
    }
    return RegionalEconomics(regions=regions)


@pytest.fixture
def simulator(basic_economics):
    """DEC simulator with default settings."""
    return RegionAwareDECSimulator(
        regional_economics=basic_economics,
        total_supply=1_000_000_000.0,
        global_emission_rate_bps=200,  # 2%
        epoch_duration_days=7.0,
        region_cap_bps=3_000,  # 30%
    )


# ═══════════════════════════════════════════════════════════════
# Epoch Budget Tests
# ═══════════════════════════════════════════════════════════════

class TestEpochBudget:
    def test_budget_calculation(self, simulator):
        """Verify epoch budget = totalSupply × rate × (days / 365.25)."""
        budget = simulator.get_epoch_emission_budget()

        # 1B × 2% / 365.25 × 7 = ~383,299 tokens
        expected = 1_000_000_000.0 * 0.02 * (7 / 365.25)
        assert abs(budget - expected) < 1.0, f"Budget {budget} != expected {expected}"

    def test_budget_scales_with_rate(self):
        """Doubling the emission rate should double the budget."""
        sim_low = RegionAwareDECSimulator(global_emission_rate_bps=100)
        sim_high = RegionAwareDECSimulator(global_emission_rate_bps=200)

        assert abs(sim_high.get_epoch_emission_budget() / sim_low.get_epoch_emission_budget() - 2.0) < 0.01

    def test_budget_scales_with_epoch_duration(self):
        """Doubling epoch duration should double the budget."""
        sim_short = RegionAwareDECSimulator(epoch_duration_days=7.0)
        sim_long = RegionAwareDECSimulator(epoch_duration_days=14.0)

        assert abs(sim_long.get_epoch_emission_budget() / sim_short.get_epoch_emission_budget() - 2.0) < 0.01


# ═══════════════════════════════════════════════════════════════
# Allocation Tests
# ═══════════════════════════════════════════════════════════════

class TestRegionAllocations:
    def test_allocations_sum_close_to_10000(self, simulator):
        """Total allocation BPS should sum close to 10000."""
        epoch = simulator.simulate_epoch()
        total_bps = sum(a.allocation_bps for a in epoch.region_allocations)

        assert total_bps <= 10_000, f"Total BPS {total_bps} exceeds 10000"
        assert total_bps >= 9_500, f"Total BPS {total_bps} too low (rounding)"

    def test_higher_multiplier_gets_more(self, simulator):
        """Regions with higher multipliers should get proportionally more."""
        epoch = simulator.simulate_epoch()
        allocs = {a.region_id: a for a in epoch.region_allocations}

        # af-south-1 has 3.0x multiplier, us-east-1 has 1.0x
        # Per-unit weighted capacity: AF = 3.0, US = 1.0
        # So per-unit, AF should be weighted 3x higher
        af_per_unit = allocs["af-south-1"].weighted_capacity / 10  # 10 capacity
        us_per_unit = allocs["us-east-1"].weighted_capacity / 500  # 500 capacity
        assert af_per_unit > us_per_unit * 2.5, "Africa per-unit weight should be ~3x US"

    def test_cap_enforcement(self, simulator):
        """No region should exceed the cap."""
        epoch = simulator.simulate_epoch()

        for alloc in epoch.region_allocations:
            assert alloc.allocation_bps <= simulator.region_cap_bps, \
                f"Region {alloc.region_id} exceeds cap: {alloc.allocation_bps}"

    def test_strict_cap_redistributes(self):
        """When a region is capped, surplus is redistributed."""
        # Create scenario where one region dominates
        regions = {
            "dominant": RegionConfig("dominant", "Dominant", target_capacity=1000, bootstrap_multiplier=1.0, current_capacity=10000),
            "small": RegionConfig("small", "Small", target_capacity=100, bootstrap_multiplier=3.0, current_capacity=10),
        }
        econ = RegionalEconomics(regions=regions)
        sim = RegionAwareDECSimulator(
            regional_economics=econ,
            region_cap_bps=3_000,  # 30% cap
        )

        epoch = sim.simulate_epoch()
        allocs = {a.region_id: a for a in epoch.region_allocations}

        # Dominant region should be capped at 30%
        assert allocs["dominant"].allocation_bps == 3_000
        # Small region gets the rest
        assert allocs["small"].allocation_bps > 0

    def test_total_emitted_matches_budget(self, simulator):
        """Total emitted across regions should closely match epoch budget."""
        epoch = simulator.simulate_epoch()

        assert epoch.total_emitted > 0
        # Due to BPS rounding, total_emitted may be slightly less than budget
        assert epoch.total_emitted <= epoch.total_emission_budget * 1.01
        assert epoch.total_emitted >= epoch.total_emission_budget * 0.90


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_no_regions(self):
        """Simulator handles no regions gracefully."""
        econ = RegionalEconomics(regions={})
        sim = RegionAwareDECSimulator(regional_economics=econ)
        epoch = sim.simulate_epoch()

        assert len(epoch.region_allocations) == 0
        assert epoch.total_emitted == 0.0

    def test_all_regions_at_target(self):
        """When all regions are at 100%+, allocation is proportional to raw capacity."""
        regions = {
            "r1": RegionConfig("r1", "R1", target_capacity=100, bootstrap_multiplier=3.0, current_capacity=200),
            "r2": RegionConfig("r2", "R2", target_capacity=100, bootstrap_multiplier=3.0, current_capacity=200),
        }
        econ = RegionalEconomics(regions=regions)
        sim = RegionAwareDECSimulator(regional_economics=econ, region_cap_bps=10_000)

        epoch = sim.simulate_epoch()
        allocs = {a.region_id: a for a in epoch.region_allocations}

        # Both at target → multiplier = 1.0x, same capacity → equal allocation
        assert abs(allocs["r1"].allocation_bps - allocs["r2"].allocation_bps) < 100

    def test_zero_capacity_region_gets_minimum(self):
        """Region with 0 capacity still gets a minimum weight (bootstrapping)."""
        regions = {
            "empty": RegionConfig("empty", "Empty", target_capacity=100, bootstrap_multiplier=3.0, current_capacity=0),
            "full": RegionConfig("full", "Full", target_capacity=100, bootstrap_multiplier=1.0, current_capacity=100),
        }
        econ = RegionalEconomics(regions=regions)
        sim = RegionAwareDECSimulator(regional_economics=econ, region_cap_bps=10_000)

        epoch = sim.simulate_epoch()
        allocs = {a.region_id: a for a in epoch.region_allocations}

        assert allocs["empty"].allocation_bps > 0, "Empty region should still get an allocation"
        assert allocs["empty"].emitted_this_epoch > 0, "Empty region should still receive tokens"

    def test_inactive_region_excluded(self):
        """Inactive regions are excluded from allocation."""
        regions = {
            "active": RegionConfig("active", "Active", target_capacity=100, bootstrap_multiplier=2.0, current_capacity=50),
            "inactive": RegionConfig("inactive", "Inactive", target_capacity=100, bootstrap_multiplier=2.0, current_capacity=50, is_active=False),
        }
        econ = RegionalEconomics(regions=regions)
        sim = RegionAwareDECSimulator(regional_economics=econ)

        epoch = sim.simulate_epoch()
        region_ids = {a.region_id for a in epoch.region_allocations}

        assert "active" in region_ids
        assert "inactive" not in region_ids


# ═══════════════════════════════════════════════════════════════
# Provider Reward Estimation Tests
# ═══════════════════════════════════════════════════════════════

class TestProviderEstimation:
    def test_estimate_provider_reward(self, simulator):
        """Provider contributing capacity should get proportional reward."""
        result = simulator.estimate_provider_reward("af-south-1", capacity_contribution=5)

        assert result["weekly_reward"] > 0
        assert result["annual_reward"] > result["weekly_reward"]
        assert 0 < result["share_of_region"] <= 1.0
        assert result["region_multiplier"] == 3.0  # Full bootstrap

    def test_estimate_unknown_region(self, simulator):
        """Unknown region returns zero reward with error."""
        result = simulator.estimate_provider_reward("nonexistent-region", capacity_contribution=10)

        assert result["weekly_reward"] == 0.0
        assert "error" in result

    def test_estimate_apr(self, simulator):
        """APR estimation should be reasonable."""
        apr = simulator.estimate_provider_apr(
            region_id="af-south-1",
            capacity_contribution=5,
            staked_amount=10_000.0,
        )

        assert apr >= 0, "APR should be non-negative"
        # Should be a reasonable number (not infinity or ridiculous)
        assert apr <= 100.0, "APR should be less than or equal to 10000%"

    def test_estimate_apr_zero_stake(self, simulator):
        """Zero staked amount should return 0 APR."""
        apr = simulator.estimate_provider_apr(
            region_id="af-south-1",
            capacity_contribution=5,
            staked_amount=0.0,
        )
        assert apr == 0.0

    def test_get_all_region_emissions(self, simulator):
        """Dashboard endpoint should return data for all active regions."""
        emissions = simulator.get_all_region_emissions()

        assert len(emissions) == 4
        for e in emissions:
            assert "region_id" in e
            assert "allocation_pct" in e
            assert "emission_tokens" in e
            assert e["emission_tokens"] >= 0
