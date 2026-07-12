from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("run_economic_adversarial.py")
SPEC = importlib.util.spec_from_file_location("run_economic_adversarial", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
PROFILE = json.loads(module.PROFILE_PATH.read_text(encoding="utf-8"))


class EconomicAdversarialTests(unittest.TestCase):
    def test_all_attack_classes_are_detected_without_false_positives(self) -> None:
        report = module.run_campaign(100, 20260711, PROFILE)

        self.assertTrue(report["passed"])
        self.assertEqual(report["baseline_false_positives"], 0)
        self.assertEqual(report["undetected"], {})
        self.assertEqual(set(report["detections"]), set(module.ATTACK_EXPECTATIONS))
        self.assertEqual(len(report["profile_sha256"]), 64)

    def test_campaign_requires_positive_epoch_count(self) -> None:
        with self.assertRaises(ValueError):
            module.run_campaign(0, 20260711, PROFILE)


if __name__ == "__main__":
    unittest.main()
