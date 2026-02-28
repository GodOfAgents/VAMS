---
name: vams-governance
description: On-chain DAO governance for the VAMS protocol — proposal creation, voting mechanics, timelock execution, and progressive decentralization from Foundation to community control.
metadata:
  permissions:
    - governance_read
    - governance_vote
    - wallet_sign
  version: 1.0.0
  author: VAMS Core Team
  license: MIT
  tags:
    - governance
    - DAO
    - voting
    - decentralization
    - timelock
---

# VAMS Governance Skill

> **"Protocol changes are not dictated. They are proposed, debated, and executed by the agents and humans who use the system."**

VAMS governance is fully on-chain. Token holders and registered agents can propose protocol changes, vote on upgrades, and execute decisions through a time-locked execution pipeline. This skill provides the interface for all governance operations.

---

## Overview

| Parameter | Value |
|---|---|
| **Governance Model** | Token-weighted + Delegation |
| **Proposal Threshold** | 100,000 $VAMS (0.01% of supply) |
| **Voting Period** | 7 days |
| **Timelock Delay** | 48 hours (standard) / 24 hours (emergency) |
| **Quorum** | 4% of total supply |
| **Execution** | `GovernorExecutor.sol` with cross-chain support |

---

## Capabilities

### 📝 1. Create Proposals
Any agent or token holder meeting the threshold can propose protocol changes:

```
vams.governance.propose({
  title: "Increase staking rewards by 2%",
  description: "Proposal rationale...",
  actions: [{ target, value, calldata }],
  crossChain: false
})
```

### 🗳️ 2. Vote
Cast votes — For, Against, or Abstain — weighted by token holdings + delegations:

```
vams.governance.vote(proposalId, "FOR")
vams.governance.delegateVote(delegateAddress)
```

### ⏰ 3. Timelock & Execution
Approved proposals enter the timelock before execution:

```
vams.governance.queue(proposalId)     → Enters timelock
vams.governance.execute(proposalId)   → After delay expires
```

### 🚨 4. Emergency Powers
The Foundation Guardian can pause the protocol in emergencies (subject to progressive removal):

```
vams.governance.emergencyPause()
→ Requires: Guardian multisig (3/5)
→ Activates: 72-hour auto-unpause timer
→ Governance can override with supermajority (67%)
```

---

## Governance Flow

```
Proposal Created
    │
    ▼
Voting Period (7 days)
    │
    ├── Quorum NOT met → Proposal Defeated
    │
    ├── Majority Against → Proposal Defeated
    │
    └── Majority For + Quorum Met
            │
            ▼
        Timelock (48h)
            │
            ▼
        Execution
            │
            └── Cross-chain relay (if multi-chain)
```

---

## Progressive Decentralization

VAMS follows a staged path from Foundation control to full DAO sovereignty:

| Phase | Timeline | Foundation Power | DAO Power |
|---|---|---|---|
| **Phase 0** — Bootstrap | Months 0–6 | Full admin | Advisory only |
| **Phase 1** — Shared | Months 6–18 | Veto power only | Proposals + voting |
| **Phase 2** — Transfer | Months 18–36 | Emergency pause only | Full control |
| **Phase 3** — Sovereign | 36+ months | None | Complete sovereignty |

### Admin Key Burndown
```
Phase 0: Foundation holds upgradeability keys
Phase 1: Timelock added to all admin operations
Phase 2: Multi-sig expanded to include community members
Phase 3: Admin keys burned — protocol is immutable (non-emergency paths)
```

---

## Anti-Capture Mechanisms

| Risk | Mitigation |
|---|---|
| Whale accumulation | Delegation caps + quadratic voting signals |
| Flash-loan governance | Snapshot-based voting (block N-1) |
| Voter apathy | Delegation incentives — delegates earn 1% of delegator rewards |
| Malicious proposals | Timelock + Guardian veto during Phase 1–2 |

---

## Smart Contracts

| Contract | Purpose |
|---|---|
| `VAMSGovernor.sol` | Core governance logic (OpenZeppelin Governor) |
| `GovernorExecutor.sol` | Cross-chain timelock execution |
| `VAMSToken.sol` | Voting power via ERC20Votes |

---

## References

| Resource | Link |
|---|---|
| Governor Contract | [GovernorExecutor.sol](https://github.com/GodOfAgents/VAMS/blob/main/contracts/src/governance/GovernorExecutor.sol) |
| Architecture §Governance | [ARCHITECTURE_v0-3-0.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/ARCHITECTURE_v0-3-0.md) |
| Whitepaper §6 — Governance | [WHITEPAPER.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/WHITEPAPER.md) |

---

*VAMS Trust Layer v0.3.0 · Governed by Code, Evolved by Community*
