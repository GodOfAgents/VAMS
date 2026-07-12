from __future__ import annotations

import importlib.util
import json
import math
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("economic_concentration.py")
SPEC = importlib.util.spec_from_file_location("economic_concentration", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
PROFILE = json.loads(module.PROFILE_PATH.read_text(encoding="utf-8"))


def balanced_snapshot() -> dict:
    providers = []
    for region_index in range(4):
        region = f"region-{region_index}"
        for owner_index in range(5):
            providers.append(
                {
                    "beneficial_owner": f"owner-{region_index}-{owner_index}",
                    "region": region,
                    "reward": 1,
                    "capacity": 1,
                }
            )
    return {"providers": providers, "region_controls": {}}


class EconomicConcentrationTests(unittest.TestCase):
    def test_balanced_market_passes(self) -> None:
        result = module.evaluate(balanced_snapshot(), PROFILE)
        self.assertTrue(result["passed"])

    def test_linked_operator_and_regional_capture_fail(self) -> None:
        snapshot = balanced_snapshot()
        for provider in snapshot["providers"][:6]:
            provider["beneficial_owner"] = "linked-cartel"
            provider["reward"] = 20

        result = module.evaluate(snapshot, PROFILE)

        self.assertFalse(result["passed"])
        self.assertTrue(any("linked-operator" in item for item in result["violations"]))
        self.assertTrue(any("region region-0" in item for item in result["violations"]))

    def test_thin_region_requires_hardware_floor(self) -> None:
        snapshot = balanced_snapshot()
        snapshot["providers"] = snapshot["providers"][:4]

        failed = module.evaluate(snapshot, PROFILE)
        self.assertTrue(any("hardware-cost floor" in item for item in failed["violations"]))

        snapshot["region_controls"] = {
            "region-0": {"hardware_floor_enforced": True}
        }
        controlled = module.evaluate(snapshot, PROFILE)
        self.assertFalse(
            any("hardware-cost floor" in item for item in controlled["violations"])
        )

    def test_seven_day_reward_return_is_flagged(self) -> None:
        snapshot = balanced_snapshot()
        snapshot["reward_flows"] = [
            {
                "operator_owner": "operator",
                "reward_recipient_owner": "human",
                "return_recipient_owner": "operator",
                "reward_timestamp": 1_000,
                "return_timestamp": 1_000 + 86_400,
                "reward_amount": 100,
                "returned_amount": 80,
            }
        ]

        result = module.evaluate(snapshot, PROFILE)

        self.assertFalse(result["passed"])
        self.assertTrue(any("seven days" in item for item in result["violations"]))

    def test_direct_operator_reward_return_is_flagged(self) -> None:
        snapshot = balanced_snapshot()
        snapshot["reward_flows"] = [
            {
                "operator_owner": "operator",
                "reward_recipient_owner": "operator",
                "return_recipient_owner": "operator",
                "reward_timestamp": 1_000,
                "return_timestamp": 2_000,
                "reward_amount": 100,
                "returned_amount": 100,
            }
        ]

        result = module.evaluate(snapshot, PROFILE)

        self.assertFalse(result["passed"])
        self.assertTrue(any("seven days" in item for item in result["violations"]))

    def test_unrelated_fast_transfer_is_not_operator_return(self) -> None:
        snapshot = balanced_snapshot()
        snapshot["reward_flows"] = [
            {
                "operator_owner": "operator",
                "reward_recipient_owner": "human",
                "return_recipient_owner": "unrelated-merchant",
                "reward_timestamp": 1_000,
                "return_timestamp": 2_000,
                "reward_amount": 100,
                "returned_amount": 100,
            }
        ]

        result = module.evaluate(snapshot, PROFILE)

        self.assertTrue(result["passed"])

    def test_reward_flow_requires_beneficial_owner_attribution(self) -> None:
        snapshot = balanced_snapshot()
        snapshot["reward_flows"] = [
            {
                "operator_owner": "operator",
                "reward_recipient_owner": "human",
                "reward_timestamp": 1_000,
                "return_timestamp": 2_000,
                "reward_amount": 100,
                "returned_amount": 100,
            }
        ]

        with self.assertRaises(ValueError):
            module.evaluate(snapshot, PROFILE)

    def test_non_finite_provider_values_are_rejected(self) -> None:
        snapshot = balanced_snapshot()
        snapshot["providers"][0]["reward"] = math.nan

        with self.assertRaises(ValueError):
            module.evaluate(snapshot, PROFILE)


if __name__ == "__main__":
    unittest.main()
