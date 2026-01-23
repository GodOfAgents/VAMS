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

# Test
forge test
```

## Architecture

```
contracts/
├── src/
│   ├── base/
│   │   ├── VAMSUpgradeableBase.sol    # UUPS + ownership transfer
│   │   └── VAMSEmergencyPausable.sol  # 48h pause + guardians
│   ├── governance/
│   │   └── VAMSTimelockController.sol # 48h timelock
│   ├── examples/
│   │   └── VAMSFeeCollector.sol       # Example implementation
│   └── VAMSCombinedBase.sol           # Combined base
├── test/                               # Forge tests
├── script/                             # Deployment scripts
├── foundry.toml                        # Foundry config
└── remappings.txt                      # Import remappings
```

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

## License

MIT
