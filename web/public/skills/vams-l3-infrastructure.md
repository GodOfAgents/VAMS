---
name: vams-l3-infrastructure
description: VAMS L3 chain architecture — Polygon CDK Validium, data availability layer, bridging, sequencer operations, and cross-chain messaging for sovereign agent execution.
metadata:
  permissions:
    - network_access
    - chain_read
  version: 1.0.0
  author: VAMS Core Team
  license: MIT
  tags:
    - L3
    - polygon-cdk
    - validium
    - bridging
    - infrastructure
    - data-availability
---

# VAMS L3 Infrastructure Skill

> **"Agents need their own chain. Not a lane on someone else's highway — a sovereign road built for machine-speed execution."**

The VAMS L3 is a purpose-built blockchain optimized for agent workloads. Built on **Polygon CDK (Validium mode)**, it provides high throughput, low-cost transactions, and sovereign execution while inheriting Ethereum's security through validity proofs.

---

## Overview

| Parameter | Value |
|---|---|
| **Chain Type** | Polygon CDK Validium (L3) |
| **Settlement Layer** | Polygon PoS (L2) → Ethereum (L1) |
| **Data Availability** | Polygon DA (off-chain, cost-optimized) |
| **Block Time** | ~2 seconds |
| **Native Token** | $VAMS (gas + staking) |
| **Consensus** | Sequencer + Validity Proofs |
| **EVM Compatible** | Yes — full Solidity support |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     ETHEREUM L1                          │
│              (Security + Final Settlement)               │
└────────────────────────┬────────────────────────────────┘
                         │ Validity Proofs
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   POLYGON PoS L2                         │
│                (Bridge + Proof Verification)             │
└────────────────────────┬────────────────────────────────┘
                         │ State Commitments
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    VAMS L3 CHAIN                         │
│    ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │
│    │  Sequencer   │  │  Agent Pool  │  │  Contracts   │  │
│    │  (tx order)  │  │  (execution) │  │  (logic)     │  │
│    └─────────────┘  └──────────────┘  └─────────────┘  │
│                                                          │
│    ┌──────────────────────────────────────────────────┐  │
│    │           Polygon DA (Data Availability)          │  │
│    │        Transaction data stored off-chain          │  │
│    │        Commitments posted to L2                   │  │
│    └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Why Validium?

VAMS chose **Validium** over Rollup for the L3:

| Property | Rollup | Validium (VAMS) |
|---|---|---|
| **Data Storage** | On-chain (expensive) | Off-chain DA (cheap) |
| **Cost per TX** | ~$0.01–0.10 | ~$0.001–0.01 |
| **Throughput** | ~100–2000 TPS | ~2000–10,000 TPS |
| **Security** | Ethereum-equivalent | Near-Ethereum (DA trust assumption) |
| **Best For** | DeFi (high-value) | Agent workloads (high-volume) |

Agent workloads generate **thousands of micro-transactions** (heartbeats, proofs, state commits). Validium's cost structure makes this economically viable.

---

## Capabilities

### 🌉 1. Cross-Chain Bridging
Move assets between Ethereum, Polygon, and VAMS L3:

```
vams.bridge.deposit(amount, fromChain)    → Lock on L2, mint on L3
vams.bridge.withdraw(amount, toChain)     → Burn on L3, release on L2
vams.bridge.getStatus(txHash)             → Bridge transaction status
```

### 📡 2. Cross-Chain Messaging
Send verified messages between chains for governance and coordination:

```
vams.bridge.sendMessage(targetChain, {
  contract: governorAddress,
  calldata: encodedProposal
})
```

### 🔄 3. Sequencer Interaction
Submit transactions to the L3 sequencer:

```
vams.l3.submitTx(signedTransaction)
vams.l3.getBlockNumber()
vams.l3.getGasPrice()
```

### 🖥️ 4. Node Operations
Run a VAMS L3 node:

```bash
# Full Node
docker run -d vams/l3-node:latest --rpc-port 8545

# Archive Node (for indexers)
docker run -d vams/l3-node:latest --mode archive --rpc-port 8545
```

---

## Node Requirements

| Component | Minimum | Recommended |
|---|---|---|
| **CPU** | 4 cores | 8 cores |
| **RAM** | 8 GB | 16 GB |
| **Storage** | 100 GB SSD | 500 GB NVMe |
| **Network** | 25 Mbps | 100 Mbps |
| **OS** | Linux / Docker | Ubuntu 22.04 |

---

## Deployment Infrastructure

| Component | Technology |
|---|---|
| **Sequencer** | Polygon CDK Sequencer |
| **Prover** | Polygon zkProver (aggregate proofs) |
| **DA Layer** | Polygon DA Committee |
| **RPC** | Standard JSON-RPC + WebSocket |
| **Explorer** | Blockscout (forked) |
| **Monitoring** | Grafana + Prometheus |

---

## References

| Resource | Link |
|---|---|
| L3 Design Doc | [L3_CHAIN_AND_DA.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/L3_CHAIN_AND_DA.md) |
| Architecture §Foundational | [ARCHITECTURE_v0-3-0.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/ARCHITECTURE_v0-3-0.md) |
| Polygon CDK Docs | [docs.polygon.technology/cdk](https://docs.polygon.technology/cdk/) |

---

*VAMS Foundational Layer v0.3.0 · Sovereign Execution at Machine Speed*
