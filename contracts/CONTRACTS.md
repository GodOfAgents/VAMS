# VAMS Protocol - Deployed Contracts

## 🚀 V2 Release (Ready for Deployment)

These contracts have been updated for **VAMS v2.0.0** Tokenomics and Governance.
*Status: Ready for Testnet Deployment.*

### Core Infrastructure
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSToken`** | ERC-20 with Votes, Permit, Burnable, and Anti-Whale extensions. | 52 |
| **`VAMSVesting`** | Handles vesting for Community, Treasury, Team, and Investors. GMV-gated unlocks. | 41 |
| **`VAMSStaking`** | Global staking logic with 2.5% initial inflation, tiered APY, dynamic unbonding. | 67 |

### Governance Layer (On-Chain)
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSGovernor`** | OpenZeppelin Governor (Voting, Proposals, Quadratic logic). | 38 |
| **`VAMSTimelockController`** | Final executor of governance proposals; holds Treasury funds. | 29 |
| **`GovernorExecutor`** | Bridge governance — executes Cardano Brain intents on Polygon. | 12 |

### Economic Layer
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSFeeCollector`** | Collects protocol fees and routes to Treasury/Insurance/Burn. | 34 |
| **`VAMSInsuranceFund`** | Slash protection, bridge failure coverage, insolvency fund. | 19 |
| **`VAMSPaymentHandler`** | Abstraction layer for x402 micropayments. | 16 |
| **`VAMSCompensation`** | User compensation for bridge/execution failures. | 11 |

### Security & Routing
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSSentinel`** | Autonomous on-chain anomaly detection (L1/L2/L3 layers). | 48 |
| **`VAMSSlasher`** | Handles operator penalties and slashing logic. | 28 |
| **`SlashingParameters`** | Configurable slashing rates per violation type. | 16 |
| **`VAMSRouter`** | Conditional L1 Router for cross-chain execution. | 22 |
| **`VAMSAgentRegistry`** | On-chain registry for verified agents, challenge system, and medals. | 55 |

### Base Infrastructure
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSUpgradeableBase`** | UUPS proxy base with storage gaps. | 8 |
| **`VAMSEmergencyPausable`** | Emergency pause with 48h auto-expiry. | 12 |
| **`VAMSCombinedBase`** | Combined base (upgradeable + pausable). | 6 |
| **`InsuranceFundProxy`** | Bridge-compatible insurance fund proxy for cross-chain claims. | 5 |

**Total: 469 tests across 19 suites**

---

## ⚠️ Archived V1 Contracts (Deprecated)

> **History:** V1 deployer was compromised (2026-02-11). The addresses below are abandoned.

| Contract | Address | Status |
| :--- | :--- | :--- |
| **$VAMS Token (V1)** | `0x62a705eD1cAbBBafFCd99e9b2497024031329fd4` | 🔴 **DEAD** |
| **Timelock (V1)** | `0xabCC69eff15753B547E02AB56FC0aa62765fb768` | 🔴 **DEAD** |
