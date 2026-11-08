"""Exact typed contract for the selected testnet profile 1.0.0.

This validates configuration identity, not deployed controls or live evidence.
Alternative stricter values may satisfy general policy bounds but require a
reviewed profile version; they are not the selected v1 configuration.
"""
from __future__ import annotations

from types import MappingProxyType


_PROFILE = MappingProxyType({
    "profile_version": "1.0.0",
    "asset_policy": "faucet-only",
    "staking_rewards_enabled": False,
    "real_fiat_enabled": False,
    "real_yield_capital_enabled": False,
    "vdso": MappingProxyType({
        "mode": "off", "authoritative_enabled": False, "value_bearing_domains_enabled": False,
    }),
    "exposure_limits": MappingProxyType({
        "single_operation_insurance_reserve_bps": 100,
        "daily_aggregate_insurance_reserve_bps": 1000,
    }),
    "concentration_stop_conditions": MappingProxyType({
        "linked_operator_share_bps": 2000, "top_four_provider_share_bps": 5000,
        "hhi": 0.25, "regional_reward_share_bps": 3000,
    }),
    "thin_liquidity": MappingProxyType({
        "minimum_independent_providers": 5,
        "require_hardware_cost_weighted_floor_below_minimum": True,
    }),
    "governance": MappingProxyType({
        "safe_threshold": 3, "safe_owners": 5, "timelock_seconds": 172800,
        "emergency_threshold": 2, "emergency_owners": 3, "emergency_scope": "pause-only",
    }),
    "soak_periods": MappingProxyType({"closed_canary_days": 7, "public_testnet_days": 14}),
})


def validate_testnet_profile(profile: object) -> list[str]:
    """Return deterministic profile errors without coercing or mutating input."""
    errors: list[str] = []

    def check(actual: object, expected: object, path: str) -> None:
        if isinstance(expected, MappingProxyType):
            if type(actual) is not dict:
                errors.append(f"{path} must be an object")
                return
            if set(actual) - set(expected):
                errors.append(f"{path} has unexpected fields for profile 1.0.0")
            for key, value in expected.items():
                field = f"{path}.{key}"
                if key not in actual:
                    errors.append(f"{field} is required")
                else:
                    check(actual[key], value, field)
        elif type(actual) is not type(expected) or actual != expected:
            errors.append(f"{path} must match the selected profile 1.0.0 value and JSON type")

    check(profile, _PROFILE, "testnet-profile")
    return errors
