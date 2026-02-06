# VAMS Smart Contracts

> VAMS Protocol on-chain components using UUPS upgradeable pattern.

## Quick Start

```bash
# Install Foundry (if not installed)
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Install dependencies
forge install OpenZeppelin/openzeppelin-contracts
forge install OpenZeppelin/openzeppelin-contracts-upgradeable

# Build
forge build

# Test (375 tests)
forge test

# Static Analysis
pip install slither-analyzer
slither . --config-file slither.config.json
```

## Architecture

```
contracts/
├── src/
│   ├── base/           # UUPS + Emergency Pause (2 contracts)
│   ├── token/          # VAMSToken (ERC-20 + Burnable + Permit + Votes)
│   ├── staking/        # VAMSStaking (Tiered APY, Lock Periods)
│   ├── vesting/        # VAMSVesting (7 schedule types)
│   ├── routing/        # VAMSRouter (CLR implementation)
│   ├── slashing/       # SlashingOracle, VAMSSlasher
│   ├── registry/       # VAMSAgentRegistry
│   ├── economic/       # FeeCollector, Insurance, Payment, 2PC, Compensation
│   └── governance/     # VAMSTimelockController
├── test/               # 375 tests (Unit, Integration, Fuzz, Governance)
├── script/             # Deployment scripts
└── slither.config.json # Static analysis config
```

## Security Status

| Item | Status |
|------|--------|
| Storage Gaps | ✅ All 16 upgradeable contracts |
| SafeERC20 | ✅ VAMSAgentRegistry |
| Flash Loan Protection | ✅ 7-day stake age for voting |
| Slither Analysis | ✅ 280 findings (no critical/high) |
| Governance Tests | ✅ 32 phase transition tests |
| External Audit | 📅 Ready to schedule |

## Upgrade Pattern

### Ownership Phases

1. **Phase 1** (Testnet): Deployer EOA
2. **Phase 2** (Guarded Mainnet): Team Multisig 3/5
3. **Phase 3** (DAO Transition): Timelock Controller
4. **Phase 4** (Optional): Renounce upgradeability

### Timelock

- Standard upgrades: **48 hours**
- Emergency upgrades: **24 hours** (requires pause first)

### Emergency Pause

- **Guardians (2/3)**: Pause immediately, 48h auto-expiry
- **Multisig (3/5)**: Extend pause, execute emergency upgrades
- **DAO**: Ratify emergency actions within 7 days

## Usage

Inherit from `VAMSCombinedBase` for contracts needing both features:

```solidity
import "./VAMSCombinedBase.sol";

contract MyContract is VAMSCombinedBase {
    function initialize(
        address admin, 
        address[] memory guardians
    ) public initializer {
        __VAMSCombinedBase_init(admin, guardians);
    }
    
    function criticalFunction() external whenNotPausedOrExpired {
        // Protected by emergency pause
    }
}
```

## Documentation

- [CONTRACTS.md](./CONTRACTS.md) - Full contract architecture
- [SECURITY.md](../.github/SECURITY.md) - Security policy
- [slither_report.txt](./slither_report.txt) - Static analysis results

## License

MIT
