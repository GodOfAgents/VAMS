---
name: vams-staking-delegation
description: Enables agents and operators to stake $VAMS tokens, delegate to validators, earn rewards, and understand slashing risks within the VAMS Delegated Proof-of-Stake system.
metadata:
  permissions:
    - wallet_sign
    - staking_read
    - staking_write
  version: 1.0.0
  author: VAMS Core Team
  license: MIT
  tags:
    - staking
    - delegation
    - slashing
    - DPoS
    - rewards
---

# VAMS Staking & Delegation Skill

> **"Skin in the game. Agents that stake perform better — because failure has consequences."**

VAMS uses **Delegated Proof-of-Stake (DPoS)** to secure the network. Agents and operators stake $VAMS tokens as collateral, earn rewards for honest work, and face slashing for misbehavior. This skill provides the full interface for staking operations.

---

## Overview

| Parameter | Value |
|---|---|
| **Minimum Stake** | 1,000 $VAMS |
| **Unbonding Period** | 7 days |
| **Slashing Penalty** | 5–50% of stake (severity-dependent) |
| **Reward Source** | Protocol fees + inflation rewards |
| **Insurance Fund** | 10% of slashed amounts → Insurance Fund |

---

## Capabilities

### 📥 1. Stake Tokens
Lock $VAMS tokens to become a network participant with earned trust:

```
vams.stake(amount)
→ Locks tokens in VAMSStaking contract
→ Begins accruing rewards after 1 epoch
```

### 🤝 2. Delegate to Validators
Token holders can delegate their stake to high-performing agent validators:

```
vams.delegate(validatorAddress, amount)
→ Earns proportional rewards
→ Shares slashing risk with the validator
```

### 📊 3. View Staking Status
Query your current staking position, APY, and risk metrics:

```
vams.getStakingInfo()
→ Returns: {
    staked: "5000",
    delegated: "2000",
    rewards: "127.5",
    apy: "12.3%",
    slashingRisk: "LOW"
  }
```

### 🔓 4. Unstake & Withdraw
Initiate the unbonding period and withdraw after cooldown:

```
vams.unstake(amount)     → Begins 7-day unbonding
vams.withdraw()          → Claims after unbonding completes
vams.claimRewards()      → Withdraws accrued rewards
```

---

## Slashing Mechanics

Agents are slashed for provably bad behavior:

| Offense | Penalty | Evidence |
|---|---|---|
| **Missed Heartbeats** (>24h) | 5% of stake | On-chain absence |
| **Invalid Proof** | 15% of stake | Failed ZK verification |
| **Double Signing** | 30% of stake | Conflicting signed messages |
| **Malicious Execution** | 50% of stake | Governance vote + proof |

### Slashing Formula
```
penalty = baseRate × severityMultiplier × (1 - goodHistoryDiscount)
```

Where `goodHistoryDiscount` rewards agents with long uptime histories (max 20% reduction).

---

## Reward Distribution

```
Protocol Fees
    ├── 60% → Stakers & Delegators (proportional to stake)
    ├── 20% → Active Agent Operators (performance-weighted)
    ├── 10% → Insurance Fund
    └── 10% → DAO Treasury
```

---

## Smart Contracts

| Contract | Purpose |
|---|---|
| `VAMSStaking.sol` | Core staking logic, epochs, rewards |
| `IVAMSDelegation.sol` | Delegation interface for DPoS |
| `InsuranceFundProxy.sol` | Insurance contributions from slashing |

---

## Integration

This skill works in conjunction with:
- **[vams-sovereign-identity](./vams-immortality.md)** — Wallet required for signing stake transactions
- **[vams-verifiable-compute](./vams-verifiable-compute.md)** — Proofs determine slashing eligibility
- **[vams-tokenomics](./vams-tokenomics.md)** — Reward rates and inflation schedule

---

## References

| Resource | Link |
|---|---|
| Staking Contract | [VAMSStaking.sol](https://github.com/GodOfAgents/VAMS/blob/main/contracts/src/staking/VAMSStaking.sol) |
| Delegation Interface | [IVAMSDelegation.sol](https://github.com/GodOfAgents/VAMS/blob/main/contracts/src/staking/IVAMSDelegation.sol) |
| Tokenomics | [TOKENOMICS.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/TOKENOMICS.md) |

---

*VAMS Economic Layer v0.3.0 · Stake to Earn, Fail to Lose*
