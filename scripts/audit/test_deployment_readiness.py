from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("deployment_readiness.py")
SPEC = importlib.util.spec_from_file_location("deployment_readiness", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class DeploymentReadinessTests(unittest.TestCase):
    def test_testnet_ceremony_source_is_fail_closed(self) -> None:
        self.assertEqual(module.validate_source(), [])

    def test_scanner_covers_reward_and_minter_disablement(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("staking.rewardPerSecond() == 0", source)
        self.assertIn("token.hasRole(token.MINTER_ROLE(), address(staking))", source)


if __name__ == "__main__":
    unittest.main()
