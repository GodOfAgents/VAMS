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

# Test (469 tests across 19 suites)
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
│   ├── vesting/        # VAMSVesting (7 schedule types, GMV-gated unlocks)
│   ├── routing/        # VAMSRouter (CLR implementation)
│   ├── slashing/       # SlashingOracle, VAMSSlasher
│   ├── registry/       # VAMSAgentRegistry
│   ├── economic/       # FeeCollector, Insurance, Payment, Compensation
│   ├── infrastructure/ # VAMSSentinel (autonomous on-chain guardian)
│   └── governance/     # VAMSTimelockController, GovernorExecutor
├── test/               # 469 tests (Unit, Integration, Fuzz, Governance)
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

- **VAMSSentinel (Autonomous)**: On-chain anomaly detection with 3 layers:
  - L1: Invariant checks (sub-second pause)
  - L2: Keeper consensus (staked keepers, 2-of-3 agreement)
  - L3: Price circuit breaker (Chainlink-verified)
- **DAO**: Ratifies emergency actions and resumes operations
- Auto-expiry: 48h max pause duration

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

## Integration with Neuron (v0.6.0)

These contracts are designed to be consumed by the **VAMS Neuron** client (`neuron/`).
- **Registration**: Agents use `VAMSAgentRegistry.register()`
- **Routing**: `neuron/clr_router.py` (CLR v3.1) mirrors `VAMSRouter.sol` logic off-chain with a 7-priority decision tree.
- **MEV Protection**: `neuron/mev_protection.py` implements encrypted mempool + batch auctions (Architecture §20.4.3).
- **Bridge Execution**: `neuron/bridge_executor.py` provides Python SDK for ICB bridge verification (mirrors `cardano/lib/vams/icb.ak`).
- **Payments**: `neuron/payments/x402.py` interacts with `VAMSPaymentHandler`.

## Documentation
- [CONTRACTS.md](./CONTRACTS.md) - Full contract architecture
- [SECURITY.md](../.github/SECURITY.md) - Security policy
- [slither_report.txt](./slither_report.txt) - Static analysis results

## License

MIT
