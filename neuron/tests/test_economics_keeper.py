"""
Tests for the Economics Keeper Bot.
Validates epoch timing, finalization execution, callbacks,
and observability status reporting.
"""

import time
import pytest
from unittest.mock import MagicMock

from neuron.economics.reward_engine import RewardEngine, EpochRewardSummary
from neuron.economics.keeper import EconomicsKeeper


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

def _mock_epoch_calc(*args, **kwargs):
    return EpochRewardSummary(
        epoch_id=0,
        total_distributed=10_000.0,
        provider_count=2,
        provider_rewards=[],
        merkle_root="0xabc123"
    )

@pytest.fixture
def mock_engine():
    engine = MagicMock(spec=RewardEngine)
    engine.calculate_epoch_rewards.side_effect = _mock_epoch_calc
    return engine


@pytest.fixture
def sample_providers():
    return [
        {"address": "0xP1", "region_id": "us-east-1", "capacity_contribution": 100},
        {"address": "0xP2", "region_id": "af-south-1", "capacity_contribution": 50},
    ]


@pytest.fixture
def keeper(mock_engine, sample_providers):
    # Short duration for testing logic
    k = EconomicsKeeper(
        reward_engine=mock_engine,
        epoch_duration_seconds=3600,
        provider_fetcher=lambda: sample_providers,
        builder_rev_fetcher=lambda: {"0xP1": 500.0},
        emission_budget_fetcher=lambda: 383_000.0
    )
    return k


# ═══════════════════════════════════════════════════════════════
# Timing & State Tests
# ═══════════════════════════════════════════════════════════════

class TestKeeperTiming:
    def test_should_finalize_initial(self, keeper):
        """Should not finalize immediately after init."""
        assert not keeper.should_finalize_epoch()

    def test_should_finalize_after_duration(self, keeper):
        """Should finalize if time elapsed exceeds duration."""
        # Manually backdate the last epoch
        keeper.last_epoch_time = time.time() - 4000
        assert keeper.should_finalize_epoch()

    def test_status_reporting(self, keeper):
        """Status should report correct epoch state."""
        status = keeper.get_status()
        assert status["current_epoch_id"] == 1
        assert status["epoch_duration_seconds"] == 3600
        assert status["is_running"] is False
        assert status["completed_epochs"] == 0
        assert 0 <= status["seconds_until_next_epoch"] <= 3600


# ═══════════════════════════════════════════════════════════════
# Finalization Tests
# ═══════════════════════════════════════════════════════════════

class TestKeeperFinalization:
    def test_manual_finalization(self, keeper, sample_providers):
        """Manual finalization advances epoch state and records history."""
        summary = keeper.finalize_epoch_manual(
            providers=sample_providers,
            emission_budget=10_000.0
        )

        assert summary.epoch_id == 1
        assert summary.merkle_root == "0xabc123"
        
        # State advanced
        assert keeper.current_epoch_id == 2
        assert len(keeper.epoch_history) == 1
        assert keeper.epoch_history[1] == summary

    def test_auto_finalization(self, keeper):
        """Auto finalization uses fetchers and processes correctly."""
        keeper._finalize_epoch_auto()

        # Engine should have been called with fetcher returns
        keeper.engine.calculate_epoch_rewards.assert_called_once()
        args, kwargs = keeper.engine.calculate_epoch_rewards.call_args
        
        assert kwargs["epoch_emission_budget"] == 383_000.0
        assert kwargs["builder_revenues"] == {"0xP1": 500.0}
        assert len(kwargs["providers"]) == 2

        # State advanced
        assert keeper.current_epoch_id == 2

    def test_auto_finalization_missing_fetchers(self, mock_engine):
        """Should not crash if fetchers are missing."""
        k = EconomicsKeeper(reward_engine=mock_engine)
        k._finalize_epoch_auto()
        
        mock_engine.calculate_epoch_rewards.assert_not_called()
        assert k.current_epoch_id == 1  # Did not advance


# ═══════════════════════════════════════════════════════════════
# Observability Tests
# ═══════════════════════════════════════════════════════════════

class TestKeeperObservability:
    def test_get_summaries(self, keeper):
        """Can retrieve individual and all summaries."""
        keeper._finalize_epoch_auto()
        keeper._finalize_epoch_auto()

        summary1 = keeper.get_epoch_summary(1)
        summary2 = keeper.get_epoch_summary(2)

        assert summary1 is not None and summary1.epoch_id == 1
        assert summary2 is not None and summary2.epoch_id == 2
        
        all_summaries = keeper.get_all_summaries()
        assert len(all_summaries) == 2


# ═══════════════════════════════════════════════════════════════
# Thread Daemon Tests
# ═══════════════════════════════════════════════════════════════

class TestKeeperDaemon:
    def test_lifecycle(self, keeper):
        """Keeper thread starts and stops gracefully."""
        assert not keeper._running
        
        keeper.start()
        assert keeper._running
        assert keeper._thread is not None
        assert keeper._thread.is_alive()
        
        keeper.stop()
        assert not keeper._running
        assert not keeper._thread.is_alive()
