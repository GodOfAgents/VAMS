import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sentinel.world_state_fidelity import WorldStateFidelitySentinel


def _build_trace(
    *,
    state_cardinality: int,
    dependency_density: int,
    horizon_length: int,
    branching_factor: int,
    observation_noise: int,
    mutation_rate: int,
):
    trace = []
    collapse_step = min(
        horizon_length,
        max(
            1,
            state_cardinality
            + dependency_density
            + branching_factor
            - observation_noise
            - mutation_rate,
        ),
    )

    for step in range(1, horizon_length + 1):
        verified_state = {
            "slot": step,
            "dependencies": list(range(dependency_density)),
            "branch": step % max(1, branching_factor),
        }
        agent_state = dict(verified_state)
        if step >= collapse_step:
            agent_state["slot"] = max(0, step - mutation_rate)

        trace.append(
            {
                "step": step,
                "agent_state": agent_state,
                "verified_external_state": verified_state,
                "action_valid": step < collapse_step + 2,
            }
        )
    return trace


def test_phase_boundary_harness_detects_state_load_collapse():
    sentinel = WorldStateFidelitySentinel()

    solved_trace = _build_trace(
        state_cardinality=8,
        dependency_density=2,
        horizon_length=6,
        branching_factor=1,
        observation_noise=0,
        mutation_rate=0,
    )
    collapse_trace = _build_trace(
        state_cardinality=2,
        dependency_density=2,
        horizon_length=6,
        branching_factor=2,
        observation_noise=2,
        mutation_rate=2,
    )

    solved = sentinel.evaluate_trace(solved_trace)
    collapsed = sentinel.evaluate_trace(collapse_trace)

    assert solved.state_fidelity_score == 1.0
    assert collapsed.state_fidelity_score < solved.state_fidelity_score
    assert collapsed.first_state_divergence_step is not None
    assert collapsed.first_invalid_action_step is not None
    assert (
        collapsed.first_state_divergence_step
        < collapsed.first_invalid_action_step
    )
