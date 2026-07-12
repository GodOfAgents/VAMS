#!/usr/bin/env python3
"""Evaluate VAMS testnet provider and reward concentration stop conditions."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "docs" / "audit" / "testnet-profile.json"


def _shares(values: dict[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        return {}
    return {owner: value / total for owner, value in values.items()}


def _concentration(shares: dict[str, float]) -> dict[str, float]:
    ordered = sorted(shares.values(), reverse=True)
    return {
        "largest_share": ordered[0] if ordered else 0.0,
        "top_four_share": sum(ordered[:4]),
        "hhi": sum(share * share for share in ordered),
    }


def evaluate(snapshot: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    providers = snapshot.get("providers")
    if not isinstance(providers, list) or not providers:
        raise ValueError("snapshot must contain at least one provider")

    owner_rewards: dict[str, float] = defaultdict(float)
    owner_capacity: dict[str, float] = defaultdict(float)
    region_rewards: dict[str, float] = defaultdict(float)
    region_owners: dict[str, set[str]] = defaultdict(set)
    for provider in providers:
        owner = str(provider["beneficial_owner"]).strip()
        region = str(provider["region"]).strip()
        reward = float(provider.get("reward", 0))
        capacity = float(provider.get("capacity", 0))
        if (
            not owner
            or not region
            or not math.isfinite(reward)
            or not math.isfinite(capacity)
            or reward < 0
            or capacity < 0
        ):
            raise ValueError("provider owner/region must be set and values non-negative")
        owner_rewards[owner] += reward
        owner_capacity[owner] += capacity
        region_rewards[region] += reward
        region_owners[region].add(owner)

    reward_metrics = _concentration(_shares(owner_rewards))
    capacity_metrics = _concentration(_shares(owner_capacity))
    regional_shares = _shares(region_rewards)
    limits = profile["concentration_stop_conditions"]
    thin = profile["thin_liquidity"]
    region_controls = snapshot.get("region_controls", {})
    violations: list[str] = []

    linked_limit = limits["linked_operator_share_bps"] / 10_000
    top_four_limit = limits["top_four_provider_share_bps"] / 10_000
    hhi_limit = float(limits["hhi"])
    regional_limit = limits["regional_reward_share_bps"] / 10_000
    for label, metrics in (("reward", reward_metrics), ("capacity", capacity_metrics)):
        if metrics["largest_share"] > linked_limit:
            violations.append(f"{label} linked-operator share exceeds {linked_limit:.0%}")
        if metrics["top_four_share"] > top_four_limit:
            violations.append(f"{label} top-four share exceeds {top_four_limit:.0%}")
        if metrics["hhi"] >= hhi_limit:
            violations.append(f"{label} HHI is at or above {hhi_limit:.2f}")

    for region, share in regional_shares.items():
        if share > regional_limit:
            violations.append(f"region {region} reward share exceeds {regional_limit:.0%}")
    for region, owners in region_owners.items():
        if (
            thin.get("require_hardware_cost_weighted_floor_below_minimum", True)
            and len(owners) < thin["minimum_independent_providers"]
        ):
            control = region_controls.get(region, {})
            if not control.get("hardware_floor_enforced", False):
                violations.append(
                    f"region {region} has thin liquidity without a hardware-cost floor"
                )

    for flow in snapshot.get("reward_flows", []):
        operator_owner = str(flow.get("operator_owner", "")).strip()
        reward_recipient_owner = str(flow.get("reward_recipient_owner", "")).strip()
        return_recipient_owner = str(flow.get("return_recipient_owner", "")).strip()
        if not operator_owner or not reward_recipient_owner or not return_recipient_owner:
            raise ValueError("reward flow beneficial owners must be set")
        reward_amount = float(flow.get("reward_amount", 0))
        returned_amount = float(flow.get("returned_amount", 0))
        reward_timestamp = int(flow.get("reward_timestamp", 0))
        return_timestamp = int(flow.get("return_timestamp", 0))
        if not math.isfinite(reward_amount) or not math.isfinite(returned_amount):
            raise ValueError("reward flow amounts must be finite")
        if reward_amount <= 0 or returned_amount <= 0:
            continue
        if returned_amount > reward_amount:
            raise ValueError("returned reward amount cannot exceed the original reward")
        if reward_timestamp <= 0 or return_timestamp <= 0:
            raise ValueError("reward flow timestamps must be positive")
        if return_timestamp < reward_timestamp:
            raise ValueError("reward return timestamp cannot precede the reward")
        if (
            return_recipient_owner == operator_owner
            and return_timestamp - reward_timestamp < 7 * 24 * 60 * 60
        ):
            returned_share = returned_amount / reward_amount
            violations.append(
                "operator-linked reward return detected inside seven days "
                f"({returned_share:.1%} returned)"
            )

    return {
        "passed": not violations,
        "reward": reward_metrics,
        "capacity": capacity_metrics,
        "regional_reward_shares": regional_shares,
        "independent_owners_by_region": {
            region: len(owners) for region, owners in region_owners.items()
        },
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    result = evaluate(snapshot, profile)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
