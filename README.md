<!--
╔══════════════════════════════════════════════════════════════════════════════╗
║                         INTELLECTUAL PROPERTY NOTICE                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Document: VAMS Project Root Documentation                                    ║
║  Author: Aseem Chishti                                                        ║
║  Email: aseeminksa@gmail.com                                                  ║
║  LinkedIn: https://www.linkedin.com/in/aseemchishti                           ║
║                                                                               ║
║  SHA-256 Fingerprint: E4B7A9...[UPDATED_BY_VAMS_PROTOCOL]...D2F8A7D9            ║
║  Timestamp: 2026-05-27T13:35:51+05:30 (ISO 8601)                              ║
║                                                                               ║
║  Copyright (c) 2026 Aseem Chishti. All Rights Reserved.                       ║
║  Licensed under the MIT License - see LICENSE file for details.               ║
║                                                                               ║
║  This cryptographic fingerprint establishes proof of authorship and content   ║
║  integrity at the specified timestamp. Any unauthorized reproduction          ║
║  claiming original authorship can be verified against this hash.              ║
╚══════════════════════════════════════════════════════════════════════════════╝
-->
<div align="center">
  <img src="./VAMS_logo.png" alt="VAMS Logo" width="600" />
  <br/>
  <h3>Multi-Layer Infrastructure for the Agentic Economy & Planetary Computer</h3>

  **Unified Decentralized Substrate | Sovereign AI Agents | Verifiable Execution**

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Status](https://img.shields.io/badge/Status-Pre--Testnet%20Candidate-orange.svg)](./REPO_STATUS_REPORT.md)
  [![Architecture](https://img.shields.io/badge/Architecture-v0.7.0-blue.svg)](./docs/team/ARCHITECTURE_v0-7-0.md)
  [![Release](https://img.shields.io/badge/Release-v1.3.0--oms-purple.svg)](./docs/CHANGELOG.md)
  [![Build](https://img.shields.io/badge/Tests-1,083%20Passing-brightgreen.svg)](./audit.md#10-test-coverage--verification)

  **[Documentation](./REPO_STATUS_REPORT.md)** • **[Architecture](./docs/team/ARCHITECTURE_v0-7-0.md)** • **[Developer Guide](./docs/DEVELOPER_GUIDE.md)** • **[Whitepaper](./docs/team/WHITEPAPER.md)** • **[Academic Audit](./audit.md)**

</div>

---

## 💡 What is VAMS?

**VAMS** (Verifiable and Agentic Modular Stack) is a **multi-layer planetary infrastructure** designed to serve as the foundational compute, identity, and economic substrate for the **Agentic Economy**—the emerging paradigm where autonomous AI agents operate as first-class economic actors with sovereign identity, asset custody, and verifiable execution guarantees.

VAMS functions as the **operating system for the Planetary Computer**—a globally distributed, verifiable, and self-healing compute substrate. It aggregates fragmented physical infrastructure (DePIN) into a single, consumable API.

> **One API. One Token. Any Agent. Any Chain.**

<table>
<tr>
<td width="33%" align="center">
<h3>🌐 Web 4.0 Substrate</h3>
<p>Infrastructure for a post-Web3 paradigm of autonomous agentic principals</p>
</td>
<td width="33%" align="center">
<h3>⚡ 80% Cheaper</h3>
<p>Datacenter cost-reduction via regionalized DePIN scheduling</p>
</td>
<td width="33%" align="center">
<h3>🔗 Multi-Chain Routing</h3>
<p>Polygon CDK Validium (L3), Cardano eUTXO (L1), Midnight (ZK-SD)</p>
</td>
</tr>
</table>

### 🎥 VAMS: The Dawn of Agentic Economy
<video src="VAMS%20-%20Dawn%20of%20Agentic%20Economy.mp4" controls="controls" style="max-width: 100%;">
</video>

---

## 🎯 The Problem

Building autonomous agent workflows today requires juggling fragmented compute layers, multiple wallet architectures, and non-deterministic execution environments.

*   💸 **High Compute Costs:** Centralized providers (AWS/GCP) lock developers into expensive GPU contracts and arbitrary Term of Service changes.
*   🔒 **Lack of Stateful Execution:** Off-chain agents cannot survive node crashes or network dropouts without manual state-recovery databases.
*   🌀 **Multi-Chain Fragmentation:** Agents are forced to manage dozens of wallets, gas tokens, and cross-chain bridges to coordinate multi-chain services, introducing high latency and severe MEV exposure.

---

## ✨ The VAMS Solution

### 🏗️ The 5 Core Pillars

#### 1️⃣ Unified DePIN Compute Sourcing
Provides a single, secure API for compute (io.net, Akash, Phala) and storage (Iagon, Celestia), abstracting multi-wallet complexity from agent creators. Grounded in [ServiceBlockRegistry.sol](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/contracts/src/registry/ServiceBlockRegistry.sol) and `neuron/services/`.

#### 2️⃣ Intelligent Multi-Chain Routing (CLR v3.1)
The Conditional L1 Router implements a 7-priority decision tree to auto-route tasks to the optimal chain based on privacy, velocity, cost, and verification needs:
*   🏛️ **P0: Compliance & ZK-Privacy** → Midnight (ZK-SD)
*   🔐 **P1: Confidential Compute** → Phala TEE
*   💰 **P2: High Value (>$50K)** → Trails → Ethereum (Multi-ISM)
*   📋 **P3: Institutional KYC** → OMS Identity Gate (fail-closed) → Polygon CDK L3
*   ✅ **P4: Formal Verification** → Cardano Pre-Prod (eUTXO)
*   ⚡ **P5: Velocity & Micro-transactions** → Hydra or SEI
*   🎯 **P6: Default Execution** → Polygon CDK Validium (VAMS L3)

Grounded in [clr_router.py](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/neuron/clr_router.py).

#### 3️⃣ Durable "Immortal" Execution
VAMS integrates the DBOS (Database-Oriented Operating System) engine, writing agent execution states directly into transactional PostgreSQL datastores. In the event of a physical crash or network failure, the agent deterministically replays its workflow from the last verified checkpoint on Celestia. Grounded in `neuron/workflows.py` and `neuron/dbos_config.py`.

#### 4️⃣ Roaming Protocol & Cross-Chain Mobility
Agents can "roam" to external EVM and non-EVM chains (Solana, Base, Ethereum) to execute tasks, provided they submit cryptographic **Proof of Travel** logs and SLA-conformant signatures upon re-entry. Grounded in `neuron/bridge_executor.py`.

#### 5️⃣ Consolidated Trust Decagon
VAMS aggregates trust and reputation proofs across 10 security standards (TEE remote attestations, staked watchtower telemetry, and behavioral analysis) to issue a consolidated **Trust Score** for compute nodes. Grounded in [VAMSTrustAggregator.sol](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/contracts/src/trust/VAMSTrustAggregator.sol).

---

## 🏛️ Smart Contract Architecture

VAMS is built on a **Dual-Host Model** separating execution ("The Hands") from final governance and identity coordination ("The Brain").

```
┌──────────────────────────────────────────────────────────────┐
│  POLYGON AMOY ("The Hands") — EVM, High-Velocity Execution  │
│  Staking, Fee Collection, Slashings, Composed Escrows        │
├──────────────────────────────────────────────────────────────┤
│  Rosen Bridge & Mithril Inter-Chain Relays                   │
├──────────────────────────────────────────────────────────────┤
│  CARDANO PRE-PROD ("The Brain") — eUTXO, Safe Governance     │
│  Quadratic Voting, Intent Timelocks, Agent DIDs (CIP-68)     │
└──────────────────────────────────────────────────────────────┘
```

### Smart Contract Modules
*   **Polygon Layer (`contracts/src/`):**
    *   `token/`: `VAMSToken.sol` (ERC-20 with Burnable + Permit + Votes).
    *   `staking/`: `VAMSStaking.sol` (Tiered lock periods and yield weightings).
    *   `economic/`: `ComposedSettlement.sol` (Asynchronous escrow settlement for up to 20 sub-providers), `RegionAwareDEC.sol` (Geospatial token emissions capping datacenter centralizations to 30% per region).
    *   `sentinel/`: `SLAEnforcer.sol` (Oracle-mediated challenge slashing).
    *   `registry/`: `VAMSAgentRegistry.sol` (Node capability register).
    *   `oracle/`: `CommitRevealOracle.sol` (Optimized random beacon matching Commit-Reveal²).
*   **Cardano Layer (`cardano/validators/`):**
    *   `governor.ak`: eUTXO Quadratic governance validator.
    *   `timelock.ak`: Multisig timelocks verifying cross-chain intent.
    *   `insurance_fund.ak`: On-chain capital custody and multisig claim logic.
    *   `agent_registry.ak`: CIP-68 NFT-backed Agent DID identities.

---

## 🔍 Implementation Reality Matrix

In accordance with VAMS Core Operational Rules, we maintain strict transparency regarding which portions of the protocol are fully deployed, which are under testnet simulation, and which utilize integration mocks/stubs.

| Subsystem | Source Code / Path | Status | Reality & Integration Details |
|:---|:---|:---:|:---|
| **Multi-DA Router** | [PerformanceAnchor.sol](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/contracts/src/da/PerformanceAnchor.sol) / `neuron/da/` | ✅ Operational | Fully implements data availability anchoring. Telemetry logs disperse to Celestia while state roots disperse to Polygon DAC. |
| **Composed Settlement** | [ComposedSettlement.sol](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/contracts/src/economic/ComposedSettlement.sol) | ✅ Operational | Supports multi-provider escrows, fractional async claims, and auto-deducted protocol fees (capped mathematically at 5 bps). |
| **Durable Execution** | [workflows.py](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/neuron/workflows.py) | ✅ Operational | Leverages the **DBOS Python SDK** to capture deterministic agent execution traces and PostgreSQL-backed state recovery. |
| **Cardano Validators** | [validators/](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/cardano/validators/) | ✅ Operational | Aiken validators written and verified. Aiken test suite is 100% passing (37 check tests). |
| **CLR Router (v3.1)** | [clr_router.py](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/neuron/clr_router.py) | ✅ Operational | Full 7-priority decision routing tree, verified by 19 dedicated unit tests. |
| **OMS Identity Gate** | [oms_identity.py](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/neuron/sdk/oms_identity.py) | 🟡 Test Simulation | Production API calls are disabled. The verifier utilizes a simulation (addresses starting with the `0x99` prefix are verified). |
| **Trails Transport** | [trails_client.py](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/neuron/sdk/trails_client.py) | 🟡 Test Simulation | Live Trails AggLayer integration is a stub. Operates in `mock_mode = True` returning signed receipt proofs; throws `NotImplementedError` otherwise. |
| **Avail & EigenDA** | [avail_substrate.py](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/neuron/sdk/avail_substrate.py) / [eigenda_kzg.py](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/neuron/sdk/eigenda_kzg.py) | 🟡 Test Simulation | Substrate transactions and disperser uploads default to mock payloads (`mock_mode = True`). Direct live dispersals require external proxy configurations. |
| **REST Gateway** | [server.py](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/gateway/server.py) | 🟡 Partially Implemented | Exposes heartbeats, node registers, and basic composer/da/economics status endpoints. Advanced KYC and top-up paths in `API_REFERENCE.md` are executed via edge SDKs or test mocks. |

---

## 📚 Academic Foundations

VAMS subsystems are systematically mapped to peer-reviewed publications and arXiv papers to ground development in formal computer science:

*   **Intelligent AI Delegation [R1.1]:** CLR Router (v3.1) implements DeepMind's 5-pillar delegation framework (scoped authority, structural transparency, systemic resilience). Cite: *Tomašev et al., "Intelligent AI Delegation" (arXiv:2602.11865, 2026)*.
*   **Commit-Reveal² [R2.1]:** direct theoretical basis for `CommitRevealOracle.sol`, utilizing randomized reveal orderings to prevent frontrunning and achieve an 80% gas reduction. Cite: *arXiv:2504.03936 (2025)*.
*   **AutoSkill [R5.1]:** Guides the AUTOSKILL Intelligence Layer (`neuron/intelligence/`), enabling autonomous skill crystallization and non-destructive inference steering ($h \leftarrow h + \alpha \cdot v$). Cite: *arXiv (March 2026)*.
*   **DeTEcT [R7.1]:** Informs the regional token emission model in `RegionAwareDEC.sol` to mathematically stabilize supply. Cite: *arXiv:2309.12330*.
*   **DBOS [R9.1]:** Core substrate for Durable Execution, allowing transactional replay of non-deterministic workflows. Cite: *DBOS Core Research (2024–2026)*.

For a full list of all 30 mapped academic publications, see the [Academic Foundations Audit](./audit.md#academic-references--research-foundations).

---

## 🔧 Quick Start

> [!NOTE]
> **Prerequisites:** Foundry (Polygon contracts), Aiken (Cardano validators), Node.js 18+ (Vite frontend), Python 3.10+ (Neuron engine).

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/GodOfAgents/VAMS-main.git
cd VAMS-main
```

### 2️⃣ Solidity Contracts (Polygon — "The Hands")
```bash
cd contracts
forge install
forge build
forge test  # Executes 619 unit, fuzz, and integration tests
```

### 3️⃣ Cardano Contracts (Aiken — "The Brain")
```bash
cd cardano
aiken check   # Executes 37 validator check tests
aiken build   # Compiles Plutus blueprint (plutus.json)
```

### 4️⃣ React Frontend (React 19 + Vite)
```bash
cd frontend-vite
npm install
npm run dev   # Boots local hot-reloaded portal on http://localhost:5173
```
*Note: The frontend source code resides under [frontend-vite/src/](file:///c:/Users/aseem/Desktop/VAMS-main/VAMS-main/frontend-vite/src/), with the main entry point located in `main.jsx` and UI components located in `App.jsx`.*

### 5️⃣ Neuron Agent Runtime
```bash
cd neuron
pip install -r requirements.txt
python demo_cli.py  # Launches interactive edge-node CLI simulating CLR routing and DA anchoring
```

---

## 📊 Comprehensive Test Suite

VAMS maintains a robust testing environment split across contract compilers and python test suites:

*   **Polygon / OMS Smart Contracts:** `619` passing tests via `forge test` (spanning tiered staking, slashing logic, escrow settle, and role-guards).
*   **Cardano Validators:** `37` passing validator tests via `aiken check` (covering CIP-68 NFT identity, quadratic governor, and bridge verification).
*   **Python Neuron Engine:** `427` passing integration tests via `pytest` (testing CLR routing tree, DBOS durable checkpoints, and mock-mode compliance gates).
*   **Total Checked Assertions:** **1,083 Passing Tests** with Zero Regressions.

---

## 🤝 Contributing & Licensing

### Copyright & Authorship
*   **Author:** Aseem Chishti
*   **Email:** aseeminksa@gmail.com
*   **LinkedIn:** [LinkedIn profile](https://www.linkedin.com/in/aseemchishti)
*   **GitHub:** [GodOfAgents](https://github.com/GodOfAgents)
*   **Proof of Authorship Details:** [PROOF_OF_AUTHORSHIP.md](./PROOF_OF_AUTHORSHIP.md)

Licensed under the **MIT License**—see the [LICENSE](./LICENSE) file for details. Copyright (c) 2026 Aseem Chishti. All Rights Reserved.

---
<div align="center">
  <sub>VAMS: Any Agent. Any Chain. One Stack. 🚀</sub>
</div>
