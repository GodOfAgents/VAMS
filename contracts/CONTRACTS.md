# VAMS Smart Contracts

> Comprehensive documentation of the VAMS protocol smart contract architecture.

## Overview

The VAMS (Verifiable Agentic Model Systems) protocol implements a 5-layer architecture for decentralized AI agent infrastructure. All contracts follow the UUPS upgradeable pattern with proper storage gaps for safe future upgrades.

## Contract Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     VAMS Contract Stack                         │
├─────────────────────────────────────────────────────────────────┤
│  Layer 5: Economic Layer                                        │
│  ├── VAMSFeeCollector.sol     - Fee distribution               │
│  ├── VAMSInsuranceFund.sol    - Slashing protection            │
│  ├── VAMSPaymentHandler.sol   - x402 payment channels          │
│  ├── BatchSettlement.sol      - Merkle batch settlements       │
│  ├── X402EscrowManager.sol    - HTLC escrows                   │
│  ├── X402NonceRegistry.sol    - Double-spend prevention        │
│  ├── ProviderBondRegistry.sol - Provider bonding               │
│  ├── TwoPhaseCommitManager.sol- Atomic transactions            │
│  ├── OutageRecoveryManager.sol- Disaster recovery              │
│  └── TransactionCompensation.sol- Failed tx compensation       │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: Trust Layer                                           │
│  ├── SlashingOracle.sol       - Commit-reveal voting           │
│  └── VAMSSlasher.sol          - Slashing execution             │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Logic Layer                                           │
│  └── VAMSRouter.sol           - Agent-to-provider routing      │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Network Layer                                         │
│  └── VAMSAgentRegistry.sol    - Agent registration             │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Foundational Layer                                    │
│  ├── VAMSUpgradeableBase.sol  - Upgrade + governance base      │
│  └── VAMSEmergencyPausable.sol- Emergency pause system         │
└─────────────────────────────────────────────────────────────────┘
```

## Core Contracts

### Base Layer (`/src/base/`)

#### VAMSUpgradeableBase.sol
- **Purpose**: Base contract for all upgradeable VAMS contracts
- **Features**: UUPS upgrade pattern, 4-phase governance migration
- **Inheritance**: Initializable, UUPSUpgradeable, OwnableUpgradeable
- **Storage Gap**: ✅ 50 slots reserved

#### VAMSEmergencyPausable.sol
- **Purpose**: Emergency pause functionality with time-bounded controls
- **Features**: 72-hour emergency pause, multi-guardian activation
- **Inheritance**: VAMSUpgradeableBase, PausableUpgradeable
- **Storage Gap**: ✅ 50 slots reserved

### Registry Layer (`/src/registry/`)

#### VAMSAgentRegistry.sol
- **Purpose**: Agent registration with challenge windows
- **Features**: 7-day challenge period, slashing integration
- **Inheritance**: VAMSUpgradeableBase, VAMSEmergencyPausable
- **Storage Gap**: ✅ 50 slots reserved

### Routing Layer (`/src/routing/`)

#### VAMSRouter.sol
- **Purpose**: Intelligent routing between agents and providers
- **Features**: Staked routing, reputation scoring, phase-based modes
- **Inheritance**: VAMSUpgradeableBase, VAMSEmergencyPausable
- **Storage Gap**: ✅ 50 slots reserved

### Slashing Layer (`/src/slashing/`)

#### SlashingOracle.sol
- **Purpose**: Decentralized dispute resolution via commit-reveal voting
- **Features**: 24-hour commit, 48-hour reveal, stake-weighted voting
- **Inheritance**: VAMSUpgradeableBase
- **Storage Gap**: ✅ 50 slots reserved

#### VAMSSlasher.sol
- **Purpose**: Executes slashing penalties on misbehaving operators
- **Features**: Tiered penalties, jailing mechanism
- **Inheritance**: VAMSUpgradeableBase
- **Storage Gap**: ✅ 50 slots reserved

### Economic Layer (`/src/economic/`)

#### VAMSFeeCollector.sol
- **Purpose**: Collects and distributes protocol fees
- **Features**: Phase-based distribution (burn/stake/treasury/insurance)
- **Roles**: FEE_COLLECTOR_ROLE, FEE_DISTRIBUTOR_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### VAMSInsuranceFund.sol
- **Purpose**: Insurance against slashing events
- **Features**: Guardian-approved claims, coverage tiers
- **Roles**: GUARDIAN_ROLE, SLASHER_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### VAMSPaymentHandler.sol
- **Purpose**: x402 payment channel management
- **Features**: 24-hour dispute window, 0.05% settlement fee
- **Roles**: OPERATOR_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### BatchSettlement.sol
- **Purpose**: Gas-efficient Merkle batch settlements
- **Features**: 90% gas savings, lazy claiming
- **Roles**: GATEWAY_ROLE, RESOLVER_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### X402EscrowManager.sol
- **Purpose**: HTLC-based escrows for x402 settlements
- **Features**: Hash-lock claims, dispute resolution
- **Roles**: SETTLER_ROLE, REFUNDER_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### X402NonceRegistry.sol
- **Purpose**: Prevents double-spending in x402 micropayments
- **Features**: Receipt verification, batch operations
- **Roles**: SETTLER_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### ProviderBondRegistry.sol
- **Purpose**: Provider bonding for settlement accountability
- **Features**: 7-day withdrawal delay, slashing integration
- **Roles**: SLASHER_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### TwoPhaseCommitManager.sol
- **Purpose**: Two-phase commit for cross-contract atomicity
- **Features**: Prepare/commit/rollback phases
- **Roles**: COORDINATOR_ROLE, ADMIN_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### OutageRecoveryManager.sol
- **Purpose**: Emergency fund release during chain outages
- **Features**: 24-hour grace, 7-day emergency mode
- **Roles**: GUARDIAN_ROLE, OPERATOR_ROLE
- **Storage Gap**: ✅ 50 slots reserved

#### TransactionCompensation.sol
- **Purpose**: Compensation for failed transactions during outages
- **Features**: Multi-guardian approval, tiered limits
- **Roles**: GUARDIAN_ROLE, PROCESSOR_ROLE
- **Storage Gap**: ✅ 50 slots reserved

## Governance Phases

| Phase | Access Control | Upgrade Mechanism | Features |
|-------|---------------|-------------------|----------|
| 1 | Admin multi-sig | Direct upgrade | Training wheels |
| 2 | Guardian committee | 24h timelock | Community validation |
| 3 | DAO governance | 7d timelock | Full decentralization |
| 4 | Immutable | Disabled | Ossification |

## Security Features

### Storage Gaps
All upgradeable contracts include `uint256[50] private __gap;` to reserve storage slots for future state variables. This prevents storage collisions during upgrades.

### Access Control
- Role-based via OpenZeppelin's `AccessControlUpgradeable`
- Timelock for sensitive operations in Phase 2+
- Multi-sig requirements for critical roles

### Reentrancy Protection
- All state-changing functions use `ReentrancyGuardUpgradeable`
- Checks-Effects-Interactions pattern followed

### SafeERC20
- All token transfers use OpenZeppelin SafeERC20
- Protects against non-standard ERC20 implementations

### Flash Loan Protection
- SlashingOracle requires 7-day minimum stake age for voting
- Prevents flash loan manipulation of slashing votes

### Pause Mechanism
- Emergency pause with automatic expiry
- Guardian quorum required for activation
- Grace periods before state changes

## Deployment

```bash
# Build contracts
forge build

# Run tests
forge test

# Deploy to local network
forge script script/Deploy.s.sol --broadcast

# Deploy to testnet
forge script script/Deploy.s.sol --rpc-url $RPC_URL --broadcast --verify
```

## Testing

```bash
# Run all tests
forge test

# Run with verbosity
forge test -vvv

# Run specific test file
forge test --match-path test/economic/VAMSFeeCollector.t.sol

# Gas report
forge test --gas-report
```

## Audit Status

- [x] Internal review complete
- [x] Copilot security review addressed
- [x] Slither static analysis (280 findings, no critical/high)
- [x] P0 SafeERC20 fix in VAMSAgentRegistry
- [x] P1 Stake age validation in SlashingOracle
- [x] Governance phase transition tests (32 tests)
- [ ] External audit (ready to schedule)

---

*For security issues, see [SECURITY.md](../.github/SECURITY.md)*
