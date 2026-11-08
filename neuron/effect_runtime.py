"""Runtime containment for local effect fixtures, separate from action policy.

These helpers use local receipts and must never become live adapters merely by
constructing them directly or changing the environment after construction.
"""
from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimeConfigurationError,
    load_runtime_policy,
)


def local_effect_policy():
    policy = load_runtime_policy()
    if policy.is_live:
        raise LiveModeSafetyError("local effect helpers are unavailable in live modes")
    return policy


class LocalEffectRuntimeBoundary(ImmutableRuntimeConfiguration):
    _immutable_runtime_fields = frozenset({"runtime_policy"})

    def _bind_local_effect_runtime(self):
        self.runtime_policy = local_effect_policy()
        self._freeze_runtime_configuration()

    def _require_local_effect_runtime(self):
        current = local_effect_policy()
        if current != self.runtime_policy:
            raise RuntimeConfigurationError("local effect runtime configuration changed")
