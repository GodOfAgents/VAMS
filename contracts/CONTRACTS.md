# VAMS Protocol - Deployed Contracts

## 🚀 V2 Release (Ready for Deployment)

These contracts have been updated for **VAMS v2.0.0** Tokenomics and Governance.
*Status: Ready for Testnet Deployment.*

### Core Infrastructure
| Contract | Description |
| :--- | :--- |
| **`VAMSToken`** | ERC-20 with Votes, Permit, and Burnable extensions. |
| **`VAMSVesting`** | Handles vesting for Community, Treasury, Team, and Investors. |
| **`VAMSStaking`** | Global staking logic with 2.5% initial inflation. |

### Governance Layer (On-Chain)
| Contract | Description |
| :--- | :--- |
| **`VAMSGovernor`** | OpenZeppelin Governor (Voting, Proposals). |
| **`VAMSTimelockController`** | Final executor of governance proposals; holds Treasury funds. |

### Economic Layer (The Brain)
| Contract | Description |
| :--- | :--- |
| **`VAMSFeeCollector`** | Collects protocol fees and routes to Treasury/Insurance/Burn. |
| **`VAMSInsuranceFund`** | Slash protection and insolvency coverage. |
| **`VAMSPaymentHandler`** | Abstraction layer for x402 micropayments. |

### Security & Routing
| Contract | Description |
| :--- | :--- |
| **`VAMSSlasher`** | Handles operator penalties and slashing logic. |
| **`VAMSRouter`** | Conditional L1 Router for cross-chain execution. |
| **`VAMSAgentRegistry`** | On-chain registry for verified agents and medals. |

---

## ⚠️ Archived V1 Contracts (Deprecated)

> **History:** V1 deployer was compromised (2026-02-11). The addresses below are abandoned.

| Contract | Address | Status |
| :--- | :--- | :--- |
| **$VAMS Token (V1)** | `0x62a705eD1cAbBBafFCd99e9b2497024031329fd4` | 🔴 **DEAD** |
| **Timelock (V1)** | `0xabCC69eff15753B547E02AB56FC0aa62765fb768` | 🔴 **DEAD** |

