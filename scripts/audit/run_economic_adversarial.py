#!/usr/bin/env python3
"""Run deterministic adversarial concentration campaigns for testnet evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

from economic_concentration import PROFILE_PATH, evaluate


ATTACK_EXPECTATIONS = {
    "linked_reward_capture": "reward linked-operator share",
    "linked_capacity_capture": "capacity linked-operator share",
    "regional_reward_capture": "reward share exceeds",
    "thin_liquidity": "thin liquidity without a hardware-cost floor",
    "wash_return": "operator-linked reward return detected",
}


def _baseline(rng: random.Random) -> dict:
    providers = []
    for region_index in range(4):
        for owner_index in range(6):
            jitter = rng.randint(0, 20) / 100
            providers.append(
                {
                    "beneficial_owner": f"owner-{region_index}-{owner_index}",
                    "region": f"region-{region_index}",
                    "reward": 100 + jitter,
                    "capacity": 100 + (0.2 - jitter),
                }
            )
    return {"providers": providers, "region_controls": {}}


def _inject(snapshot: dict, attack: str) -> None:
    providers = snapshot["providers"]
    if attack == "linked_reward_capture":
        for provider in providers[:6]:
            provider["beneficial_owner"] = "linked-cartel"
            provider["reward"] = 500
    elif attack == "linked_capacity_capture":
        for provider in providers[:6]:
            provider["beneficial_owner"] = "linked-cartel"
            provider["capacity"] = 500
    elif attack == "regional_reward_capture":
        for provider in providers[:6]:
            provider["reward"] = 300
    elif attack == "thin_liquidity":
        snapshot["providers"] = [
            provider
            for provider in providers
            if provider["region"] != "region-0"
            or provider["beneficial_owner"].endswith(("-0", "-1", "-2", "-3"))
        ]
    elif attack == "wash_return":
        snapshot["reward_flows"] = [
            {
                "operator_owner": "operator-a",
                "reward_recipient_owner": "human-a",
                "return_recipient_owner": "operator-a",
                "reward_timestamp": 1_000_000,
                "return_timestamp": 1_086_400,
                "reward_amount": 100,
                "returned_amount": 80,
            }
        ]
    else:
        raise ValueError(f"unknown attack: {attack}")


def run_campaign(epochs: int, seed: int, profile: dict) -> dict:
    if epochs < 1:
        raise ValueError("epochs must be positive")
    rng = random.Random(seed)
    canonical_profile = json.dumps(
        profile, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    attacks = tuple(ATTACK_EXPECTATIONS)
    detections: Counter[str] = Counter()
    undetected: Counter[str] = Counter()
    baseline_failures = 0

    for epoch in range(epochs):
        snapshot = _baseline(rng)
        if not evaluate(snapshot, profile)["passed"]:
            baseline_failures += 1

        attack = attacks[epoch % len(attacks)]
        _inject(snapshot, attack)
        result = evaluate(snapshot, profile)
        expected = ATTACK_EXPECTATIONS[attack]
        if any(expected in violation for violation in result["violations"]):
            detections[attack] += 1
        else:
            undetected[attack] += 1

    return {
        "schema_version": "1.0.0",
        "profile_sha256": hashlib.sha256(canonical_profile).hexdigest(),
        "stop_conditions": profile["concentration_stop_conditions"],
        "thin_liquidity": profile["thin_liquidity"],
        "seed": seed,
        "epochs": epochs,
        "attack_classes": list(attacks),
        "detections": dict(sorted(detections.items())),
        "undetected": dict(sorted(undetected.items())),
        "baseline_false_positives": baseline_failures,
        "passed": baseline_failures == 0 and not undetected,
        "limitations": [
            "Synthetic campaign; live beneficial-owner attestations remain required.",
            "Does not replace governance-capture or chain-level settlement simulation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    report = run_campaign(args.epochs, args.seed, profile)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
