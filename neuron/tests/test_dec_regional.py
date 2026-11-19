"""
Tests for the Region-Aware DEC Simulator.
Validates emission allocation math, cap enforcement, and provider reward estimation.
"""

from itertools import permutations

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


def _simulate_weight_vector(weights):
    """Return allocations for positive integer weights with equal multipliers."""
    regions = {
        f"r{i}": RegionConfig(
            f"r{i}", f"Region {i}", target_capacity=weight,
            bootstrap_multiplier=1.0, current_capacity=weight,
        )
        for i, weight in enumerate(weights)
    }
    simulator = RegionAwareDECSimulator(
        regional_economics=RegionalEconomics(regions=regions),
        region_cap_bps=3_000,
    )
    epoch = simulator.simulate_epoch()
    return {alloc.region_id: alloc.allocation_bps for alloc in epoch.region_allocations}


# ═══════════════════════════════════════════════════════════════
# Epoch Budget Tests
# ═══════════════════════════════════════════════════════════════

class TestEpochBudget:
    @pytest.mark.parametrize("region_cap_bps", [500, 3_000])
    def test_region_cap_accepts_onchain_boundaries(self, region_cap_bps):
        sim = RegionAwareDECSimulator(region_cap_bps=region_cap_bps)
        assert sim.region_cap_bps == region_cap_bps

    @pytest.mark.parametrize("region_cap_bps", [0, 499, 3_001, 10_000])
    def test_region_cap_rejects_out_of_range_values(self, region_cap_bps):
        with pytest.raises(ValueError, match="integer from 500 through 3000"):
            RegionAwareDECSimulator(region_cap_bps=region_cap_bps)

    @pytest.mark.parametrize("region_cap_bps", [True, False, 3_000.0, "3000", None])
    def test_region_cap_rejects_non_integers(self, region_cap_bps):
        with pytest.raises(ValueError, match="integer from 500 through 3000"):
            RegionAwareDECSimulator(region_cap_bps=region_cap_bps)

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

    def test_exact_cap_share_does_not_receive_redistributed_budget(self):
        # Raw shares are exactly 4000, 3000, 2000 and 1000 BPS. The second
        # region is saturated at exactly 3000 and must leave the redistribution
        # denominator and budget together with the first region.
        allocations = _simulate_weight_vector((4, 3, 2, 1))

        assert allocations == {"r0": 3_000, "r1": 3_000, "r2": 2_666, "r3": 1_334}
        assert sum(allocations.values()) == 10_000
        assert all(value <= 3_000 for value in allocations.values())

    def test_iterative_caps_conserve_budget_with_rounding(self):
        allocations = _simulate_weight_vector((6, 3, 1, 1))

        assert allocations == {"r0": 3_000, "r1": 3_000, "r2": 2_000, "r3": 2_000}
        assert sum(allocations.values()) == 10_000

    def test_cap_boundary_permutations_never_exceed_budget(self):
        # Dust follows the simulator's stable sorted region order, but totals
        # and each regional ceiling must hold for every input permutation.
        for weights in permutations((4, 3, 2, 1)):
            allocations = _simulate_weight_vector(weights)
            assert sum(allocations.values()) == 10_000
            assert all(value <= 3_000 for value in allocations.values())

    @pytest.mark.parametrize(
        ("region_count", "expected_bps"),
        [(1, 3_000), (2, 6_000), (3, 9_000), (4, 10_000)],
    )
    def test_region_cap_retains_only_unallocatable_budget(self, region_count, expected_bps):
        allocations = _simulate_weight_vector((1,) * region_count)

        assert sum(allocations.values()) == expected_bps
        assert all(value <= 3_000 for value in allocations.values())

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
        # Both regions are capped; the remaining 40% stays unallocated.
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
        """Four equally weighted saturated regions fit below the 30% cap."""
        regions = {
            f"r{i}": RegionConfig(
                f"r{i}", f"R{i}", target_capacity=100,
                bootstrap_multiplier=3.0, current_capacity=100,
            )
            for i in range(4)
        }
        econ = RegionalEconomics(regions=regions)
        sim = RegionAwareDECSimulator(regional_economics=econ)

        epoch = sim.simulate_epoch()
        allocs = {a.region_id: a for a in epoch.region_allocations}

        # All are at target → multiplier = 1.0x and equal 25% shares.
        assert len(allocs) == 4
        assert {alloc.allocation_bps for alloc in allocs.values()} == {2_500}
        assert sum(alloc.allocation_bps for alloc in allocs.values()) == 10_000

    def test_zero_capacity_region_gets_minimum(self):
        """A bootstrap region gets positive weight without relaxing the cap."""
        regions = {
            "empty": RegionConfig("empty", "Empty", target_capacity=100, bootstrap_multiplier=3.0, current_capacity=0),
            **{
                f"full-{i}": RegionConfig(
                    f"full-{i}", f"Full {i}", target_capacity=100,
                    bootstrap_multiplier=1.0, current_capacity=100,
                )
                for i in range(4)
            },
        }
        econ = RegionalEconomics(regions=regions)
        sim = RegionAwareDECSimulator(regional_economics=econ)

        epoch = sim.simulate_epoch()
        allocs = {a.region_id: a for a in epoch.region_allocations}

        assert allocs["empty"].allocation_bps > 0, "Empty region should still get an allocation"
        assert allocs["empty"].emitted_this_epoch > 0, "Empty region should still receive tokens"
        assert all(a.allocation_bps <= 3_000 for a in allocs.values())
        assert sum(a.allocation_bps for a in allocs.values()) == 10_000

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
