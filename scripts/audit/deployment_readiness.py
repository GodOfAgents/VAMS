#!/usr/bin/env python3
"""Static fail-closed checks for the approved VAMS testnet ceremony."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def validate_source() -> list[str]:
    required_snippets = {
        "contracts/script/DeployTestnet.s.sol": (
            "POLYGON_AMOY_CHAIN_ID = 80_002",
            "GOVERNANCE_DELAY = 48 hours",
            'vm.envAddress("VAMS_GOVERNANCE_SAFE")',
            'vm.envAddress("VAMS_TREASURY_SAFE")',
            'vm.envAddress("VAMS_EMERGENCY_COUNCIL")',
            "_requireSafe(governanceSafe, 5, 3)",
            "_requireSafe(emergencyCouncil, 3, 2)",
            "_requireDistinctAuthorities(governanceSafe, treasurySafe, emergencyCouncil)",
            "token.hasRole(token.MINTER_ROLE(), address(staking))",
            "staking.rewardPerSecond() == 0",
            "token.renounceRole(token.DEFAULT_ADMIN_ROLE(), deployer)",
            "timelock.renounceRole(timelock.DEFAULT_ADMIN_ROLE(), deployer)",
            "token.totalSupply() == token.MAX_SUPPLY()",
        ),
        "contracts/src/governance/VAMSTimelockController.sol": (
            "ABSOLUTE_MIN_DELAY = 48 hours",
        ),
        "contracts/src/governance/GovernorExecutor.sol": (
            "MIN_DELAY = 48 hours",
        ),
        "contracts/src/token/VAMSToken.sol": (
            "MAX_SUPPLY = INITIAL_SUPPLY",
            "totalSupply() + amount > MAX_SUPPLY",
        ),
        "contracts/script/DeployV2.s.sol": (
            "VAMS_ALLOW_UNSAFE_LEGACY_DEPLOYMENT",
        ),
        "contracts/script/DeployVAMS.s.sol": (
            "VAMS_ALLOW_UNSAFE_LEGACY_DEPLOYMENT",
        ),
    }

    errors: list[str] = []
    for rel_path, snippets in required_snippets.items():
        path = ROOT / rel_path
        if not path.exists():
            errors.append(f"{rel_path}: missing")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{rel_path}: missing `{snippet}`")

    return errors


def main() -> int:
    errors = validate_source()
    if errors:
        print("Deployment readiness source scan failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Deployment readiness source scan passed.")
    print("On-chain Safe ownership, role transfer, and explorer evidence remain runtime gates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
