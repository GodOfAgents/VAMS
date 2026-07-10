import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sentinel.world_state_fidelity import (
    WorldStateFidelitySentinel,
    stable_state_hash,
)


def test_matching_states_have_full_fidelity():
    sentinel = WorldStateFidelitySentinel()

    report = sentinel.evaluate_trace(
        [
            {
                "step": 1,
                "agent_state": {"escrow": "locked", "nonce": 1},
                "verified_external_state": {"escrow": "locked", "nonce": 1},
                "action_valid": True,
            }
        ]
    )

    assert report.state_fidelity_score == 1.0
    assert report.agent_state_hash == report.verified_external_state_hash
    assert report.first_state_divergence_step is None
    assert report.false_progress_score == 0.0
    assert report.status == "telemetry_only"
    assert report.rewardImpact == "none"


def test_divergence_before_invalid_action_is_reported():
    sentinel = WorldStateFidelitySentinel()

    report = sentinel.evaluate_trace(
        [
            {
                "step": 1,
                "agent_state": {"balance": 100, "escrow": "locked"},
                "verified_external_state": {"balance": 100, "escrow": "locked"},
                "action_valid": True,
            },
            {
                "step": 2,
                "agent_state": {"balance": 100, "escrow": "locked"},
                "verified_external_state": {"balance": 80, "escrow": "claimed"},
                "action_valid": True,
            },
            {
                "step": 3,
                "agent_state": {"balance": 100, "escrow": "locked"},
                "verified_external_state": {"balance": 80, "escrow": "claimed"},
                "action_valid": False,
            },
        ]
    )

    assert report.state_fidelity_score == pytest.approx(1 / 3)
    assert report.first_state_divergence_step == 2
    assert report.first_invalid_action_step == 3
    assert report.false_progress_score == 0.5
    assert report.agent_state_hash == stable_state_hash(
        {"balance": 100, "escrow": "locked"}
    )


def test_staleness_score_is_capped():
    sentinel = WorldStateFidelitySentinel(staleness_limit_seconds=10)

    report = sentinel.evaluate_trace(
        [
            {
                "step": 1,
                "agent_state": {"epoch": 1},
                "verified_external_state": {"epoch": 1},
                "action_valid": True,
                "verified_at": 80.0,
            }
        ],
        now=100.0,
    )

    assert report.staleness_score == 1.0
