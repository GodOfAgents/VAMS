"""
World-state fidelity telemetry for long-horizon agent audits.

This module compares an agent's represented state against verified external
state per step. It is telemetry-only: scores are reported to Sentinel audit
records and must not drive rewards, slashing, or routing until calibrated.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional


def stable_state_hash(state: Any) -> str:
    """Return a deterministic SHA-256 hash for JSON-like state."""
    payload = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorldStateStep:
    step_index: int
    agent_state: Any
    verified_external_state: Any
    action_valid: bool = True
    observed_at: Optional[float] = None
    verified_at: Optional[float] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WorldStateStep":
        return cls(
            step_index=int(payload.get("step_index", payload.get("step", 0))),
            agent_state=payload.get("agent_state", {}),
            verified_external_state=payload.get("verified_external_state", {}),
            action_valid=bool(payload.get("action_valid", True)),
            observed_at=payload.get("observed_at"),
            verified_at=payload.get("verified_at"),
        )


@dataclass(frozen=True)
class WorldStateFidelityReport:
    agent_state_hash: str
    verified_external_state_hash: str
    state_fidelity_score: float
    first_state_divergence_step: Optional[int]
    first_invalid_action_step: Optional[int]
    staleness_score: float
    false_progress_score: float
    status: str = "telemetry_only"
    rewardImpact: str = "none"
    regionalBonusImpact: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WorldStateFidelitySentinel:
    """Computes world-state fidelity diagnostics from per-step traces."""

    def __init__(self, staleness_limit_seconds: float = 300.0):
        if staleness_limit_seconds <= 0:
            raise ValueError("staleness_limit_seconds must be positive")
        self.staleness_limit_seconds = float(staleness_limit_seconds)

    def evaluate_trace(
        self,
        steps: Iterable[Dict[str, Any] | WorldStateStep],
        now: Optional[float] = None,
    ) -> WorldStateFidelityReport:
        parsed_steps: List[WorldStateStep] = [
            step if isinstance(step, WorldStateStep) else WorldStateStep.from_dict(step)
            for step in steps
        ]
        if not parsed_steps:
            return WorldStateFidelityReport(
                agent_state_hash="",
                verified_external_state_hash="",
                state_fidelity_score=1.0,
                first_state_divergence_step=None,
                first_invalid_action_step=None,
                staleness_score=0.0,
                false_progress_score=0.0,
            )

        current_time = time.time() if now is None else float(now)
        latest = parsed_steps[-1]
        divergence_steps: List[int] = []
        invalid_steps: List[int] = []
        stale_scores: List[float] = []

        for step in parsed_steps:
            agent_hash = stable_state_hash(step.agent_state)
            external_hash = stable_state_hash(step.verified_external_state)
            if agent_hash != external_hash:
                divergence_steps.append(step.step_index)
            if not step.action_valid:
                invalid_steps.append(step.step_index)
            if step.verified_at is not None:
                age = max(0.0, current_time - float(step.verified_at))
                stale_scores.append(min(1.0, age / self.staleness_limit_seconds))

        first_divergence = divergence_steps[0] if divergence_steps else None
        first_invalid = invalid_steps[0] if invalid_steps else None
        matching_steps = len(parsed_steps) - len(divergence_steps)
        fidelity_score = matching_steps / len(parsed_steps)

        false_progress_score = 0.0
        if first_divergence is not None:
            post_divergence = [
                step for step in parsed_steps if step.step_index >= first_divergence
            ]
            valid_after_divergence = [
                step for step in post_divergence if step.action_valid
            ]
            false_progress_score = (
                len(valid_after_divergence) / len(post_divergence)
                if post_divergence
                else 0.0
            )

        return WorldStateFidelityReport(
            agent_state_hash=stable_state_hash(latest.agent_state),
            verified_external_state_hash=stable_state_hash(latest.verified_external_state),
            state_fidelity_score=round(fidelity_score, 6),
            first_state_divergence_step=first_divergence,
            first_invalid_action_step=first_invalid,
            staleness_score=round(max(stale_scores) if stale_scores else 0.0, 6),
            false_progress_score=round(false_progress_score, 6),
        )
