"""
VAMS Regional Economics — Unit Tests
=======================================
Tests multiplier decay curves, capacity tracking,
and CandidateScorer integration.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from neuron.economics.regional import RegionalEconomics, RegionConfig


# ═══════════════════════════════════════════════════════════════
# Tests: Multiplier Calculations
# ═══════════════════════════════════════════════════════════════

class TestMultiplierCalculations:

    def _make_econ(self):
        regions = {
            "us-east-1": RegionConfig("us-east-1", "US East", target_capacity=500, bootstrap_multiplier=1.0),
            "af-south-1": RegionConfig("af-south-1", "Africa", target_capacity=50, bootstrap_multiplier=3.0),
            "eu-west-1": RegionConfig("eu-west-1", "EU West", target_capacity=400, bootstrap_multiplier=1.5),
        }
        return RegionalEconomics(regions=regions)

    def test_empty_region_full_multiplier(self):
        econ = self._make_econ()
        # 0% capacity → full bootstrap
        assert econ.get_reward_multiplier("af-south-1") == 3.0

    def test_below_50pct_full_multiplier(self):
        econ = self._make_econ()
        econ.update_capacity("af-south-1", 20)  # 40% of 50
        assert econ.get_reward_multiplier("af-south-1") == 3.0

    def test_at_50pct_full_multiplier(self):
        econ = self._make_econ()
        econ.update_capacity("af-south-1", 25)  # Exactly 50%
        assert econ.get_reward_multiplier("af-south-1") == 3.0

    def test_at_75pct_midpoint_decay(self):
        econ = self._make_econ()
        econ.update_capacity("af-south-1", 37)  # ~74% — halfway through decay
        # Expected: 3.0 - (2.0 * ~0.48) ≈ 2.04
        mult = econ.get_reward_multiplier("af-south-1")
        assert 1.8 < mult < 2.2  # Allow margin for integer division

    def test_at_100pct_standard_rate(self):
        econ = self._make_econ()
        econ.update_capacity("af-south-1", 50)  # 100%
        assert econ.get_reward_multiplier("af-south-1") == 1.0

    def test_over_capacity_standard_rate(self):
        econ = self._make_econ()
        econ.update_capacity("af-south-1", 200)  # 400% over
        assert econ.get_reward_multiplier("af-south-1") == 1.0

    def test_saturated_region_no_boost(self):
        econ = self._make_econ()
        # us-east-1 has multiplier=1.0 (already saturated)
        assert econ.get_reward_multiplier("us-east-1") == 1.0

    def test_unknown_region_standard_rate(self):
        econ = self._make_econ()
        assert econ.get_reward_multiplier("mars-1") == 1.0


# ═══════════════════════════════════════════════════════════════
# Tests: Capacity Management
# ═══════════════════════════════════════════════════════════════

class TestCapacityManagement:

    def test_update_capacity(self):
        econ = RegionalEconomics(regions={
            "test": RegionConfig("test", "Test", target_capacity=100, bootstrap_multiplier=2.0),
        })
        econ.update_capacity("test", 42)
        stats = econ.get_region_stats("test")
        assert stats["current_capacity"] == 42
        assert stats["fill_ratio"] == 0.42

    def test_bulk_update(self):
        econ = RegionalEconomics(regions={
            "r1": RegionConfig("r1", "R1", target_capacity=100, bootstrap_multiplier=2.0),
            "r2": RegionConfig("r2", "R2", target_capacity=200, bootstrap_multiplier=1.5),
        })
        econ.bulk_update_capacity({"r1": 50, "r2": 150})
        assert econ.get_region_stats("r1")["current_capacity"] == 50
        assert econ.get_region_stats("r2")["current_capacity"] == 150

    def test_unknown_region_update_ignored(self):
        econ = RegionalEconomics(regions={
            "test": RegionConfig("test", "Test", target_capacity=100, bootstrap_multiplier=2.0),
        })
        econ.update_capacity("unknown", 999)  # Should not raise


# ═══════════════════════════════════════════════════════════════
# Tests: Queries
# ═══════════════════════════════════════════════════════════════

class TestQueries:

    def test_get_region_stats(self):
        econ = RegionalEconomics(regions={
            "test": RegionConfig("test", "Test Region", target_capacity=100, bootstrap_multiplier=2.0),
        })
        econ.update_capacity("test", 30)
        stats = econ.get_region_stats("test")

        assert stats["region_id"] == "test"
        assert stats["display_name"] == "Test Region"
        assert stats["target_capacity"] == 100
        assert stats["current_capacity"] == 30
        assert stats["fill_ratio"] == 0.3
        assert stats["current_multiplier"] == 2.0  # Below 50% → full

    def test_get_all_multipliers(self):
        econ = RegionalEconomics(regions={
            "r1": RegionConfig("r1", "R1", target_capacity=100, bootstrap_multiplier=2.0),
            "r2": RegionConfig("r2", "R2", target_capacity=100, bootstrap_multiplier=3.0),
        })
        mults = econ.get_all_multipliers()
        assert "r1" in mults
        assert "r2" in mults
        assert mults["r1"] == 2.0
        assert mults["r2"] == 3.0

    def test_get_underserved_regions(self):
        econ = RegionalEconomics(regions={
            "full": RegionConfig("full", "Full", target_capacity=100, bootstrap_multiplier=1.5),
            "empty": RegionConfig("empty", "Empty", target_capacity=100, bootstrap_multiplier=3.0),
        })
        econ.update_capacity("full", 80)
        econ.update_capacity("empty", 10)

        underserved = econ.get_underserved_regions(threshold=0.5)
        assert len(underserved) == 1
        assert underserved[0]["region_id"] == "empty"

    def test_unknown_region_returns_none(self):
        econ = RegionalEconomics(regions={})
        assert econ.get_region_stats("unknown") is None


# ═══════════════════════════════════════════════════════════════
# Tests: Scorer Integration
# ═══════════════════════════════════════════════════════════════

class TestScorerIntegration:

    def test_multiplier_map_usable_by_scorer(self):
        """Ensures get_all_multipliers() output is compatible with CandidateScorer."""
        from neuron.composer.scorer import CandidateScorer

        econ = RegionalEconomics(regions={
            "us-east-1": RegionConfig("us-east-1", "US East", target_capacity=500, bootstrap_multiplier=1.0),
            "af-south-1": RegionConfig("af-south-1", "Africa", target_capacity=50, bootstrap_multiplier=3.0),
        })

        multipliers = econ.get_all_multipliers()
        scorer = CandidateScorer(regional_multipliers=multipliers)

        # Verify the scorer can use the multiplier map
        assert scorer._regional_multipliers == multipliers


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
