---
name: vams-security-hardening
description: Comprehensive security framework for VAMS agents and smart contracts — covering reentrancy guards, access control, prompt injection defense, oracle security, and pre-audit hardening.
metadata:
  permissions:
    - security_scan
    - contract_read
  version: 1.0.0
  author: VAMS Core Team
  license: MIT
  tags:
    - security
    - audit
    - smart-contracts
    - agent-security
    - defense
---

# VAMS Security Hardening Skill

> **"Security is not a feature. It's a constraint that shapes every line of code."**

The VAMS security model covers both **smart contract safety** and **agent manipulation resistance**. This skill documents the defense-in-depth strategy used across the protocol, from Solidity patterns to prompt injection defenses.

---

## Overview

VAMS operates in a **maximally adversarial environment** — public blockchains where anyone can interact with contracts and attempt to manipulate agents. Security is enforced at every layer:

| Layer | Threat Surface | Defense |
|---|---|---|
| **Foundational** | Key compromise | HSM/TEE key storage, rotation |
| **Network** | P2P message forgery | Signed + encrypted channels |
| **Logic** | Agent manipulation | Prompt injection defense, sandboxing |
| **Trust** | Proof forgery | ZK verification, multi-party attestation |
| **Economic** | Token theft, MEV | Reentrancy guards, slippage limits |

---

## Smart Contract Security

### Mandatory Patterns

Every VAMS contract follows these non-negotiable patterns:

#### 1. Checks-Effects-Interactions (CEI)
```solidity
function withdraw(uint256 amount) external {
    // CHECKS
    if (balances[msg.sender] < amount) revert InsufficientBalance();
    
    // EFFECTS
    balances[msg.sender] -= amount;
    
    // INTERACTIONS
    (bool success,) = msg.sender.call{value: amount}("");
    if (!success) revert TransferFailed();
}
```

#### 2. ReentrancyGuard
All state-modifying external functions use OpenZeppelin's `ReentrancyGuard`:
```solidity
function stake(uint256 amount) external nonReentrant { ... }
```

#### 3. Access Control
Role-based access via OpenZeppelin `AccessControl`:
```solidity
bytes32 public constant SLASHER_ROLE = keccak256("SLASHER_ROLE");
bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");
```

#### 4. Pausable
All critical contracts can be paused by the Guardian multisig:
```solidity
function emergencyPause() external onlyRole(GUARDIAN_ROLE) {
    _pause();
}
```

#### 5. UUPS Upgradability
Deterministic upgrades with authorization checks:
```solidity
function _authorizeUpgrade(address newImplementation)
    internal
    override
    onlyRole(UPGRADER_ROLE)
{}
```

---

## Agent Security

### Prompt Injection Defense
VAMS agents implement layered defenses against prompt injection:

| Defense | Description |
|---|---|
| **Input Sanitization** | Strip control characters, limit length |
| **System Prompt Anchoring** | Immutable system prompt hash verified per request |
| **Output Validation** | Agent outputs checked against allowlist of actions |
| **Sandboxed Execution** | Agents run in isolated environments with limited capabilities |
| **Transaction Limits** | Max single-transaction value enforced on-chain |

### Key Management
- **Generation**: ECDSA secp256k1 via secure random
- **Storage**: Encrypted at rest, never in plaintext on disk
- **Rotation**: Automatic key rotation every 90 days
- **Recovery**: Shamir's Secret Sharing for key backup

### Malicious Transaction Prevention
Agents cannot sign arbitrary transactions. The VAMS Neuron SDK enforces:
1. **Allowlisted contract addresses** — only interact with verified VAMS contracts
2. **Value caps** — per-transaction and daily spending limits
3. **Signature review** — human-in-the-loop for high-value operations

---

## Attack Scenarios & Mitigations

| Attack | Category | Mitigation |
|---|---|---|
| **Reentrancy** | Contract | CEI pattern + ReentrancyGuard |
| **Flash Loan Governance** | Economic | Snapshot voting (block N-1) |
| **MEV Sandwich** | Economic | Private mempool + slippage limits |
| **Sybil (Fake Agents)** | Network | Minimum stake requirement |
| **Replay** | Network | Nonce tracking + chain ID |
| **Oracle Manipulation** | Trust | Multi-source aggregation + TWAP |
| **Double Signing** | Consensus | Slashing + equivocation proofs |
| **Prompt Injection** | Agent | Sandboxing + output validation |
| **Griefing** | Economic | Gas-efficient operations + insurance fund |

---

## Security Tooling

| Tool | Purpose | Integration |
|---|---|---|
| **Slither** | Static analysis for Solidity | CI/CD pipeline |
| **Aderyn** | Smart contract vulnerability detection | Pre-commit hooks |
| **Foundry Fuzzing** | Property-based testing | Test suite |
| **Echidna** | Invariant testing | Nightly CI runs |
| **Manual Audit** | External security review | Pre-mainnet |

---

## Pre-Audit Checklist

- [ ] All contracts compile without warnings
- [ ] 100% branch coverage in test suite
- [ ] Slither reports reviewed and triaged
- [ ] Access control matrix documented
- [ ] Upgrade paths tested on fork
- [ ] Emergency pause tested on fork
- [ ] Key rotation procedures documented
- [ ] Incident response playbook created

---

## References

| Resource | Link |
|---|---|
| Smart Contracts | [contracts/](https://github.com/GodOfAgents/VAMS/tree/main/contracts) |
| Architecture §Security | [ARCHITECTURE_v0-3-0.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/ARCHITECTURE_v0-3-0.md) |
| Staking (Slashing) | [VAMSStaking.sol](https://github.com/GodOfAgents/VAMS/blob/main/contracts/src/staking/VAMSStaking.sol) |

---

*VAMS Trust Layer v0.3.0 · Defense in Depth, Verified by Design*
