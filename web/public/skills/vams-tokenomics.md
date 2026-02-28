---
name: vams-tokenomics
description: Comprehensive guide to the $VAMS token economy — utility, supply dynamics, vesting schedules, fee distribution, and burn mechanics that power the Agentic Economy.
metadata:
  permissions:
    - token_read
  version: 1.0.0
  author: VAMS Core Team
  license: MIT
  tags:
    - tokenomics
    - economics
    - VAMS-token
    - supply
    - vesting
---

# VAMS Tokenomics Skill

> **"$VAMS is not a meme coin. It's the unit of trust in the Agentic Economy."**

The $VAMS token is the native currency of the VAMS network. It provides utility across all five layers of the stack — from gas fees and staking to governance voting and agent payments. This skill documents the full economic design.

---

## Token Utility

$VAMS serves **five distinct functions** within the protocol:

| Function | Description | Layer |
|---|---|---|
| ⛽ **Gas** | Pay L3 transaction fees | Foundational |
| 🔒 **Staking** | Collateral for agent operators | Economic |
| 🗳️ **Governance** | Vote on protocol upgrades | Trust |
| 💰 **Payments** | Agent-to-agent & agent-to-human payments | Network |
| 🔥 **Fee Burns** | Deflationary pressure via partial fee burning | Economic |

---

## Supply Schedule

| Parameter | Value |
|---|---|
| **Total Supply** | 1,000,000,000 $VAMS |
| **Initial Circulating** | ~15% at TGE |
| **Inflation** | 0% fixed supply — no minting after genesis |
| **Burn Mechanism** | 2% of all protocol fees burned quarterly |

### Allocation

```
┌──────────────────────────────────────────────────┐
│  Community & Ecosystem    40%  ████████████████   │
│  Team & Advisors          15%  ██████             │
│  Foundation Reserve       15%  ██████             │
│  Staking Rewards Pool     15%  ██████             │
│  Liquidity & Partnerships 10%  ████               │
│  Initial Sale              5%  ██                 │
└──────────────────────────────────────────────────┘
```

---

## Vesting Schedules

### Team & Advisors (15%)
- **Cliff**: 12 months
- **Linear Vest**: 36 months after cliff
- **GMV Gate**: Unlocks gated by Gross Marketplace Value milestones
- **Contract**: `VAMSVesting.sol`

### Foundation Reserve (15%)
- **Cliff**: 6 months
- **Linear Vest**: 48 months
- **GMV Gate**: Yes — prevents dumping before product-market fit

### Community (40%)
- **No Cliff**: Distributed via staking rewards, grants, and ecosystem incentives
- **Schedule**: Linear release over 60 months

---

## Fee Distribution Model

Every transaction on the VAMS L3 generates fees that are distributed:

```
Transaction Fees
    ├── 40% → Stakers & Delegators
    ├── 20% → Active Agent Operators
    ├── 15% → DAO Treasury
    ├── 10% → Insurance Fund
    ├── 10% → Sequencer Operators
    └──  5% → Burn 🔥
```

---

## Deflationary Mechanics

1. **Fee Burns**: 5% of every transaction fee is permanently burned
2. **Quarterly Burns**: 2% of accumulated protocol fees burned
3. **Slashing Burns**: 50% of slashed tokens are burned (50% → Insurance Fund)

### Projected Supply Reduction
At target network utilization, estimated **1.5–3% annual deflation** after full supply release.

---

## Economic Security

| Risk | Mitigation |
|---|---|
| Team dump at unlock | GMV-gated vesting — must hit revenue milestones |
| Whale governance capture | Quadratic voting + delegation caps |
| Death spiral (price crash) | Insurance Fund covers slashing gaps |
| Insufficient validator rewards | Dynamic fee adjustment via governance |

---

## Smart Contracts

| Contract | Purpose |
|---|---|
| `VAMSToken.sol` | ERC-20 token with burn capability |
| `VAMSVesting.sol` | GMV-gated vesting for team/foundation |
| `VAMSStaking.sol` | Staking rewards distribution |
| `InsuranceFundProxy.sol` | Insurance fund management |

---

## References

| Resource | Link |
|---|---|
| Tokenomics Doc | [TOKENOMICS.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/TOKENOMICS.md) |
| Vesting Contract | [VAMSVesting.sol](https://github.com/GodOfAgents/VAMS/blob/main/contracts/src/vesting/VAMSVesting.sol) |
| Whitepaper §5 — Economics | [WHITEPAPER.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/WHITEPAPER.md) |

---

*VAMS Economic Layer v0.3.0 · Fixed Supply, Growing Utility*
