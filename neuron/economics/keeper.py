"""
VAMS Economics Keeper Bot
=========================
Automates epoch finalization and reward distribution for the 
VAMS Economic Layer. Monitors time, triggers the RewardEngine, 
and produces Merkle roots for on-chain submission.

Architecture Reference:
    - VAMS Phase 4, Sprint 12
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Callable

from neuron.economics.reward_engine import RewardEngine, EpochRewardSummary

logger = logging.getLogger("VAMS-EconomicsKeeper")


class EconomicsKeeper:
    """
    Automates the economic lifecycle of the protocol.
    
    Responsibilities:
    1. Monitor time passed since last epoch.
    2. Fetch provider stats when epochs end.
    3. Generate the EpochRewardSummary and Merkle root.
    4. Provide observability data to the Gateway.
    """

    def __init__(
        self, 
        reward_engine: Optional[RewardEngine] = None,
        epoch_duration_seconds: int = 604800,  # 1 week default
        provider_fetcher: Optional[Callable[[], List[Dict]]] = None,
        builder_rev_fetcher: Optional[Callable[[], Dict[str, float]]] = None,
        emission_budget_fetcher: Optional[Callable[[], float]] = None,
    ):
        self.engine = reward_engine or RewardEngine()
        self.epoch_duration = epoch_duration_seconds
        
        # Callbacks to fetch live network state
        self.provider_fetcher = provider_fetcher
        self.builder_rev_fetcher = builder_rev_fetcher
        self.emission_budget_fetcher = emission_budget_fetcher
        
        # State
        self.current_epoch_id = 1
        self.last_epoch_time = time.time()
        self.epoch_history: Dict[int, EpochRewardSummary] = {}
        
        # Thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ──────────────────────────────────────────────────
    # Epoch Automation
    # ──────────────────────────────────────────────────

    def should_finalize_epoch(self) -> bool:
        """Check if enough time has passed to finalize the epoch."""
        return (time.time() - self.last_epoch_time) >= self.epoch_duration

    def finalize_epoch_manual(
        self,
        providers: List[Dict],
        emission_budget: float,
        builder_revenues: Optional[Dict[str, float]] = None
    ) -> EpochRewardSummary:
        """Manually trigger an epoch finalization with provided data."""
        logger.info(f"Finalizing Epoch {self.current_epoch_id}...")

        summary = self.engine.calculate_epoch_rewards(
            providers=providers,
            epoch_emission_budget=emission_budget,
            builder_revenues=builder_revenues
        )
        
        summary.epoch_id = self.current_epoch_id
        self.epoch_history[self.current_epoch_id] = summary
        
        logger.info(
            f"Epoch {self.current_epoch_id} finalized! "
            f"Providers: {summary.provider_count}, "
            f"Total: {summary.total_distributed:.2f} VAMS. "
            f"Root: {summary.merkle_root}"
        )

        # Advance state
        self.current_epoch_id += 1
        self.last_epoch_time = time.time()

        return summary

    def _finalize_epoch_auto(self):
        """Automatically fetch data and run finalization."""
        if not all([self.provider_fetcher, self.emission_budget_fetcher]):
            logger.warning("Cannot auto-finalize: Missing fetchers")
            return

        try:
            providers = self.provider_fetcher()
            budget = self.emission_budget_fetcher()
            builder_revs = self.builder_rev_fetcher() if self.builder_rev_fetcher else None
            
            self.finalize_epoch_manual(providers, budget, builder_revs)
        except Exception as e:
            logger.error(f"Auto-finalization failed: {e}")

    # ──────────────────────────────────────────────────
    # Daemon Control
    # ──────────────────────────────────────────────────

    def _loop(self):
        """Background loop monitoring time."""
        logger.info(f"Economics Keeper started. Epoch duration: {self.epoch_duration}s")
        while self._running:
            if self.should_finalize_epoch():
                self._finalize_epoch_auto()
                
            # Sleep in short increments to allow quick shutdown
            for _ in range(10):
                if not self._running:
                    break
                time.sleep(1)

    def start(self):
        """Start the background keeper thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background keeper thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    # ──────────────────────────────────────────────────
    # Observability Lookups
    # ──────────────────────────────────────────────────

    def get_epoch_summary(self, epoch_id: int) -> Optional[EpochRewardSummary]:
        """Fetch a completed epoch's summary."""
        return self.epoch_history.get(epoch_id)

    def get_all_summaries(self) -> List[EpochRewardSummary]:
        """Fetch all completed epoch summaries."""
        return list(self.epoch_history.values())

    def get_status(self) -> Dict:
        """Get the current running status of the keeper."""
        time_elapsed = time.time() - self.last_epoch_time
        time_remaining = max(0, self.epoch_duration - time_elapsed)
        
        return {
            "current_epoch_id": self.current_epoch_id,
            "epoch_duration_seconds": self.epoch_duration,
            "seconds_until_next_epoch": int(time_remaining),
            "is_running": self._running,
            "completed_epochs": len(self.epoch_history),
        }
