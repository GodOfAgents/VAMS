# VAMS Protocol - Deployed Contracts

## 🚀 V2 Release (Ready for Testnet)

These contracts have been updated for **VAMS v0.6.0** Tokenomics, Governance, and Open Money Stack (OMS) integrations.
*Status: Ready for Testnet Deployment (Polygon Amoy + Cardano Pre-Prod).*

### Core Infrastructure
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSToken`** | ERC-20 with Votes, Permit, Burnable, and Anti-Whale extensions. | 45 |
| **`VAMSVesting`** | Handles vesting for Community, Team, and Investors across 7 vesting types. | 3 |
| **`VAMSStaking`** | Global staking logic with APY locks and dynamic unbonding unbonding rules. | 42 |

### Governance Layer
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSGovernor`** | OpenZeppelin Governor (Voting, Proposals, Quadratic logic). | 1 |
| **`VAMSTimelockController`** | Final executor of governance proposals; holds Treasury funds. | 32 |
| **`GovernorExecutor`** | Bridge governance — executes Cardano Brain intents on Polygon. | 31 |

### Economic Layer (ICN Modular Stack + OMS Extensions)
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`ComposedSettlement`** | Asynchronous escrow settlements for orchestrated multi-provider blueprints. | 14 |
| **`RegionAwareDEC`** | Dynamic geospatial token emissions, capping regional datacenter shares at 30%. | 16 |
| **`RegionalIncentives`** | Evaluates geospatial network utilization to distribute regional bonuses. | 17 |
| **`RewardDistributor`** | Distributes incentives with stablecoin and hybrid opt-in split payouts. | 15 |
| **`VAMSInsuranceFund`** | Slash protection, including yield management capabilities (YIELD_MANAGER_ROLE). | 5 |
| **`VAMSFeeCollector`** | Collects protocol fees (capped mathematically at 5 bps) and routes to yield/burn. | 39 |
| **`TransactionCompensation`** | Manages insurance payout payouts for failed bridges or compute dropouts. | 35 |
| **`BatchSettlement`** | Aggregates micro-transactions with verified signatures to mitigate MEV. | 28 |

### Security & Routing
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSSentinel`** | Autonomous on-chain anomaly detection watchdog (L1/L2/L3 layers). | 28 |
| **`SLAEnforcer`** | Executes oracle-mediated SLA compliance checks and slashes operators. | 8 |
| **`SlashingParameters`** | Configurable slashing parameters per node violation type. | 31 |
| **`VAMSRouter`** | Conditional routing coordinator executing CLR prioritizations. | 3 |
| **`VAMSAgentRegistry`** | On-chain registry for verified agents, supporting Sequence wallet authorized keys. | 26 |
| **`VAMSHardwareRegistry`** | Hardware registry verifying node capabilities and collateral bonds. | 22 |
| **`VAMSTrustAggregator`** | Aggregates consensus scores for nodes from 10 distinct security inputs. | 19 |

### Base Infrastructure
| Contract | Description | Tests |
| :--- | :--- | :--- |
| **`VAMSUpgradeableBase`** | UUPS proxy base with storage gap safeguards. | 11 |
| **`VAMSEmergencyPausable`** | Pauses selected targets in emergency with 48h auto-expiry. | 12 |
| **`InsuranceFundProxy`** | Bridge-compatible proxy managing cross-chain claims. | 8 |

**Total: 619 tests across 30 suites**

---

## ⚠️ Archived V1 Contracts (Deprecated)

> **History:** V1 deployer was compromised (2026-02-11). The addresses below are abandoned and fully deprecated.

| Contract | Address | Status |
| :--- | :--- | :--- |
| **$VAMS Token (V1)** | `0x62a705eD1cAbBBafFCd99e9b2497024031329fd4` | 🔴 **DEAD** |
| **Timelock (V1)** | `0xabCC69eff15753B547E02AB56FC0aa62765fb768` | 🔴 **DEAD** |
