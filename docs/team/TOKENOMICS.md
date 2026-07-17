
<!--
╔══════════════════════════════════════════════════════════════════════════════╗
║                         INTELLECTUAL PROPERTY NOTICE                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Document: VAMS Tokenomics Specification v2.0.0                               ║
║  Author: Aseem Chishti                                                        ║
║  Email: aseeminksa@gmail.com                                                  ║
║  LinkedIn: https://www.linkedin.com/in/aseemchishti                           ║
║                                                                               ║
║  SHA-256 Fingerprint: E4B7A9...[UPDATED_BY_VAMS_PROTOCOL]...D2F8A7D9            ║
║  Timestamp: 2026-02-17T00:00:26+05:30 (ISO 8601)                              ║
║                                                                               ║
║  Copyright (c) 2026 Aseem Chishti. All Rights Reserved.                       ║
║  Licensed under the MIT License - see LICENSE file for details.               ║
║                                                                               ║
║  This cryptographic fingerprint establishes proof of authorship and content   ║
║  integrity at the specified timestamp. Any unauthorized reproduction          ║
║  claiming original authorship can be verified against this hash.              ║
╚══════════════════════════════════════════════════════════════════════════════╝
-->

# $VAMS Tokenomics (v2.0.0)

## The Sovereign Brain for the Agentic Web

**Version:** 2.0.0  
**Date:** February 2026  
**Status:** Pre-Launch Specification (Decentralized Init)

---

## 1. Executive Summary

The $VAMS token powers the VAMS ecosystem—a unified payment and governance layer for the Agentic Web. It solves the fragmentation of DePIN by aggregating compute (Akash, io.net), storage (Arweave, Filecoin), and intelligence (Bittensor) into a single verifiable stack.

### Key Metrics

| Parameter | Value |
| :--- | :--- |
| **Token Name** | VAMS |
| **Token Symbol** | $VAMS |
| **Initial Supply** | 1,000,000,000 (1 Billion) |
| **Max Inflation** | 2.5% Year 1 (Decaying) |
| **Initial Circulating** | 100,000,000 (10%) |
| **Token Standard** | ERC-20 (Polygon MVP -> Multi-chain) |
| **Governance** | Quadratic Voting + Time-Weighted Power |

---

## 2. Token Utility

1.  **Universal Payment**: Pay for any DePIN resource (GPU, CPU, Storage) with $VAMS.
2.  **Governance**: Direct the protocol's evolution and treasury allocation.
3.  **Bonding**: Required collateral for Service Providers and Agent Nodes.
4.  **Risk Underwriting (Collateralized Probation)**: Lock $VAMS as a 100% collateral bond to temporarily underwrite higher-value workflows while an agent builds on-chain reputation through cryptographic proofs. (Trust Tiers *cannot* be bought).
5.  **Roaming Security**: Agents stake "Good Behavior Bonds" to maintain Verified status while roaming.
6.  **Delegated Agent Staking (DPoS for AI)**: Lock $VAMS to financially back high-performing agents and earn a share of their generated fees.

> **Note on Infrastructure Security (Restaking Pivot)**: Early L3 architectures forced validators to lock millions of dollars in native tokens to secure the network—a vulnerability allowing crypto whales to buy network consensus cheaply. VAMS avoids this via **Inherited Security**. By utilizing **EigenLayer** and **Polygon's native staked assets**, the VAMS sequencer/prover network borrows billions of dollars of existing economic security. Validators run our hardware using their existing liquid staked tokens (LSTs). This makes the VAMS infrastructure instantly whale-proof while focusing the $VAMS token purely on high-velocity application utility and agent curation.

### Delegated Agent Staking (DPoS for AI)
To leverage the wisdom of the crowd, VAMS allows $VAMS holders to act as financial auditors for AI agents. By delegating stake to specific agents, users create a scalable, cryptoeconomic trust layer.

*   **Backing an Agent:** Users vouch for highly reliable agents by locking up $VAMS in the agent's specific staking pool.
*   **Yield Sharing:** Delegators take a proportional percentage cut of the fees the agent earns while executing user tasks or DeFi operations.
*   **Shared Slashing Risk:** If the backed agent misbehaves, produces invalid ZK proofs, or acts maliciously, both the creator's bond and the users' delegated stake are slashed.
*   **Anti-Whale Mechanics:** 
    *   *Yield Saturation Curves:* Each agent's staking pool has a saturation point. Extraneous Total Value Locked (TVL) sharply dilutes the Annual Percentage Yield (APY). This mathematically forces whales to break up their capital and stake across *multiple* high-performing agents to maximize yield, decentralizing the security.
*   **Security (Upgrade Timelocks):** To prevent an agent creator from "rug pulling" delegators by pushing a malicious update after attracting TVL, any agent accepting delegated stake operates under a mandatory **7-day Upgrade Timelock**. Delegators have a 7-day window to withdraw their stake if they distrust the incoming code or model hash update.

---

## 3. Business Model & Revenue Streams

The VAMS network runs a sustainable "cash-flow" model driven by real economic activity, not just token issuance. Revenue is generated through four primary streams:

1.  **Dynamic Protocol Fee**: A 0.1% to 1.0% variable fee is applied to all agent API requests, compute provisioning (GPU/CPU leasing), and DePIN resource usage flowing through the VAMS gateway.
2.  **Gas Abstraction Premium**: To provide a seamless Web2-like experience, users can top up their VAMS accounts using fiat credit cards or non-native tokens (e.g., USDC, ETH, SOL). VAMS charges a markup (2-7%, default 5%) for this auto-swapping convenience.
3.  **x402 Settlement Fees**: A 0.05% fee is charged when closing/settling the continuous cryptoeconomic micropayment channels (x402) used by agents for high-frequency transactions.
4.  **Bridge Liquidity Fees**: A 0.25% fee is applied to cross-chain asset transfers utilizing the VAMS Roaming Protocol.

### 3.1 Sustainability Equilibrium: Phased Fee Distribution
The VAMS network employs a two-phase protocol fee distribution model to bootstrap and then sustain the network.

**PHASE 1 (Bootstrap - Until Month 60): "Burn & Build"**
Currently, **100% of Protocol Fees** are directed to an automated **Buyback & Burn** smart contract. As agent activity and transaction volume scale on the network, this creates immense deflationary pressure on the $VAMS supply. Validator rewards and ecosystem growth during this phase are funded entirely by the 2.5% decaying emissions and the 40% Ecosystem Grants allocation.

**PHASE 2 (Mature - Post Month 60): "Sustainable Yield"**
Once network emissions reach their terminal rate (500K $VAMS/year), the protocol shifts to a diversified revenue-sharing model to sustain validators mathematically without resting on inflation. Protocol Fee Revenue will be split as follows:
- **40% Buyback & Burn**: Continued deflationary pressure.
- **30% Staking Rewards**: Yield directly distributed to L3 Sequencer node operators and CLR validators.
- **20% DAO Treasury**: Ongoing funding for decentralized operations and core development.
- **10% Insurance Fund**: Capitalizes the smart contract covering bridge exploits, execution failures, or provider insolvency.

---

## 4. Allocation Breakdown (Decentralized Model)

We have optimized the distribution for maximum community ownership and decentralization security.

| Category | Percent | Amount | Vesting Schedule |
| :--- | :--- | :--- | :--- |
| **Community & Ecosystem** | **50%** | 500,000,000 | See sub-allocations |
| ↳ *Liquidity & Airdrop* | *(10%)* | *(100,000,000)* | ***100% Unlocked at TGE*** |
| ↳ *Ecosystem Grants & Mining* | *(40%)* | *(400,000,000)* | *0-month cliff, 60-month linear (~6.67M/month)* |
| **Architect** | **12%** | 120,000,000 | 12-month cliff, 48-month linear vesting (~2.50M/month) |
| **Future Team & Advisors** | **13%** | 130,000,000 | 12-month cliff, 36-month linear (50% Time / 50% GMV-Gated) |
| **Investors** | **13%** | 130,000,000 | See sub-allocations |
| ↳ *Early Investors* | *(5%)* | *(50,000,000)* | *6-month cliff, 18-month linear (~2.78M/month)* |
| ↳ *Regular Investors* | *(8%)* | *(80,000,000)* | *12-month cliff, 30-month linear (~2.67M/month)* |
| **DAO Treasury** | **12%** | 120,000,000 | 6-month cliff, 48-month linear (50% Time / 50% GMV-Gated) |

### Breakdown Details
- **Community & Ecosystem (50%)**: Maintains the "50% community-owned" headline. Internally split into two sub-buckets:
  - *Liquidity & Airdrop (10%)*: Fully liquid at TGE. Bootstraps DEX liquidity and seeds the initial user base.
  - *Ecosystem Grants & Mining (40%)*: Developer grants, validator incentives, and mining rewards. Linearly vested over 60 months to ensure sustained network growth.
- **Architect (12%)**: Separate cap-table line. **12-month cliff** enforces long-term alignment before unlocks begin.
- **Future Team & Advisors (13%)**: Covers future hires and strategic advisors. Features **Performance-Gated Unlocks** (50% releases monthly, 50% only releases when GMV milestones are hit).
- **Investors (13%)**: Split into two tranches to reflect different risk/reward profiles:
  - *Early Investors (5%)*: Seed/angel backers who took the most risk. Shorter cliff (6M) and faster vest (18M).
  - *Regular Investors (8%)*: Strategic/Series-A backers. Standard 12M cliff with a 30-month vest.
- **DAO Treasury (12%)**: Protocol runway. Features **Performance-Gated Unlocks** to ensure treasury inflation only occurs when network demand supports it.

---

## 5. Vesting Schedules

### 5.1 Terms
- **Cliff**: Time before any tokens unlock.
- **Vesting**: Linear monthly unlocks after cliff.

| Category | Cliff | Vesting | Monthly Unlock |
| :--- | :--- | :--- | :--- |
| **Airdrop / Liquidity (10%)** | None | TGE | 100M at TGE |
| **Ecosystem Grants & Mining (40%)** | 0 months | 60 months | ~6.67M / month |
| **Architect (12%)** | **12 months** | **48 months** | ~2.50M / month |
| **Future Team & Advisors (13%)** | 12 months | 36 months | ~3.61M / month (50% GMV-Gated) |
| **Early Investors (5%)** | 6 months | 18 months | ~2.78M / month |
| **Regular Investors (8%)** | 12 months | 30 months | ~2.67M / month |
| **DAO Treasury (12%)** | 6 months | 48 months | ~2.50M / month (50% GMV-Gated) |

---

## 6. Dynamic Emission Controller (DEC)

VAMS employs a Reinforcement Learning (RL) bounded control system—conceptually similar to dynamic emission adjustments in DePIN—known as the **Dynamic Emission Controller (DEC)**. 

The DEC mathematically modulates protocol parameters based on real-time network demand and supply pressure to prevent economic collapse.

### 6.1 Bounded Adjustments
- **Inflation Range**: The DEC can autonomously adjust the annual emission rate between a floor of 0.1% and a hard cap of 2.5%.
- **Fee Multiplier**: The DEC regulates the dynamic protocol fee against API demand, constrained to a maximum 10% movement per epoch.
- **Safety Overrides**: Operates on a 3-model ensemble. If RL models diverge or hit mathematically dangerous threshold boundaries, the system overrides to a conservative baseline and alerts DAO governance.

---

## 7. Emission Schedule (Inflationary Security)

To ensure perpetual network security, VAMS uses a **low-inflation model** strictly for staking rewards.

- **Initial Supply**: 1,000,000,000 (1B)
- **Max Annual Inflation**: 2.5% (25M tokens/year initially)
- **Adjustment**: DAO can reduce inflation rate (0% floor), but never increase above 2.5%.

### Net Deflation Target
With **100% of Protocol Fees directed to Buyback & Burn**, the protocol mathematically achieves **Net Deflation** when annual fee revenue exceeds the dollar value of the newly minted supply. 
- *Formula*: `(Annual Tokens Minted × Avg Token Price) = Required Burn Revenue`
- *Example*: At 2.5% inflation (25M tokens/yr) and an average **$0.20 token price**, the network becomes unconditionally deflationary at **$5,000,000 in annual revenue**.

### Path to Deflation: Benchmarking $5M
To achieve the $5M Deflation Target, VAMS needs approximately $1B in annual Gross Merchandise Value (GMV) flowing through the protocol at a blended 0.5% fee rate, or significantly less when utilizing high-margin fiat on-ramps. 

A balanced network achieving Net Deflation looks like the following equilibrium:
1. **10,000 Active AI Agents** generating $50,000/year each in transaction volume ($500M GMV @ 0.5% fee = **$2.5M**)
2. **1,000,000 micro-transactions settled daily** via x402 channels (Settlement fees = **$1.0M**)
3. **$50M in Fiat/USDC compute purchasing** via the VAMS gateway (3% Abstraction markup = **$1.5M**)
- *Alternatively*, this target can be hit entirely by just **1,000 Enterprise clients** spending $100k/year on decentralized compute via fiat on-ramps.

---

## 7. Governance: Quadratic Voting

To prevent whale dominance, VAMS employs **Quadratic Voting (QV)** for crucial governance decisions.

- **Voting Power** = Market Sqrt(Tokens Staked)
- **Example**:
  - Alice stakes 100 VAMS → 10 Votes
  - Bob stakes 10,000 VAMS → 100 Votes
  - Bob has 100x the stake, but only 10x the voting power.

This protects the "Sovereign Brain" from being controlled by a single large entity.

**Dual-Chain Governance (Implemented):** Quadratic voting is implemented on both chains:
- **Polygon (Solidity):** `VAMSGovernor` contract with `VAMSTimelockController`
- **Cardano (Aiken):** `governor.ak` validator with eUTXO-native quadratic voting and per-UTXO proposal state

---

## 8. Staking Mechanics & Validator Tiers

VAMS utilizes an **Inherited Security** restaking model for L3 consensus, but operators must still stake $VAMS tokens as a cryptoeconomic bond for good behavior and governance weight.

### 8.1 L3 Validator Staking Tiers
To ensure robust security and incentivize long-term participation, validating and operating nodes requires meeting specific tiered thresholds:

| Tier | Minimum Stake | Base APY Target | Notes |
| :--- | :--- | :--- | :--- |
| **Silver** | 50,000 $VAMS | 8% | Entry-level L3 validator participation. |
| **Gold** | 100,000 $VAMS | 10% | Standard participation. Enhanced 1.5x governance weight. |
| **Platinum** | 1,000,000+ $VAMS | 12% | High-security tier. Required for CLR operator eligibility. |

### 8.2 Unbonding Period
To prevent flash-collusion attacks and ensure network stability during market volatility, all staked $VAMS (both validator bonds and delegated stakes) are subject to a **14-day unbonding period**. 
- During economic circuit breaker events (e.g., severe price drops >90%), the unbonding period can be dynamically extended by the protocol up to 30 days.

### 8.3 Cognitive Benchmark Premium & Composition Yields

DePIN compute nodes do not receive flat yields. To incentivize the deployment of high-specification hardware that prevents the "agent amnesia" bottleneck, VAMS ties operator composition yields and market pricing power directly to their verified **Cattell-Horn-Carroll (CHC) cognitive benchmarks**:

1. **Composition Premium Multiplier**: Nodes that report high cognitive profile scores (particularly in Memory Storage `MS`, Fluid Reasoning `R`, and Working Memory `WM`, typically supported by secure TEEs with large memory capacities) receive a yield multiplier of up to **\(1.5\text{x}\)** on their base staking emissions.
2. **Pricing Command**: When matching blueprints via the 6-axis scoring engine, nodes satisfying high cognitive thresholds command a pricing premium in the marketplace. High-performance enclaves can claim higher hourly fees (\(cost\_per\_hour\) in $VAMS) since the shortfall scoring algorithm prioritizes nodes that fully satisfy the blueprint's requirements without penalty.
3. **Attestation Auditing**: These cognitive capabilities are verified by Sentinel nodes during periodic challenge cycles, and any discrepancies or failure to meet the reported CHC metrics results in immediate down-grading of the node's profile, dilution of its yield multiplier, and potential slashing of its staked collateral.

---

## Appendix A: Token Unlock Schedule (v2.1 — Restructured)

> **Key:** All figures are cumulative totals at that snapshot. Monthly rates: Eco Grants 6.67M, Architect 2.50M, Team 3.61M, Early Inv (6M cliff) 2.78M, Reg Inv (12M cliff) 2.67M, Treasury (6M cliff) 2.50M.

| Month | Airdrop/Liq | Eco Grants | Treasury | Architect | Team | Early Inv | Reg Inv | **Total Circulating** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TGE** | 100M | 0M | 0M | 0M | 0M | 0M | 0M | **100M (10.0%)** |
| **M6** | 100M | 40M | 0M *(cliff ends)* | 0M | 0M | 0M *(cliff ends)* | 0M | **140M (14.0%)** |
| **M12** | 100M | 80M | 15M* | 0M *(cliff ends)* | 0M *(cliff ends)* | 16.7M | 0M *(cliff ends)* | **211.7M (21.2%)** |
| **M24** | 100M | 160M | 45M* | 30M | 43.3M* | 50M ✅ | 32M | **460.3M (46.0%)** |
| **M36** | 100M | 240M | 75M* | 60M | 86.7M* | 50M | 64M | **675.7M (67.6%)** |
| **M42** | 100M | 280M | 90M* | 75M | 108.3M* | 50M | 80M ✅ | **783.3M (78.3%)** |
| **M48** | 100M | 320M | 105M* | 90M | 130M ✅ | 50M | 80M | **875M (87.5%)** |
| **M54** | 100M | 360M | 120M ✅ | 105M | 130M | 50M | 80M | **945M (94.5%)** |
| **M60** | 100M | 400M ✅ | 120M | 120M ✅ | 130M | 50M | 80M | **1.000B*** |

*> * = Subject to 50% GMV-Gated Performance Milestones. If GMV targets are missed, these unlocks are deferred. ✅ = tranche fully vested. Includes ~50M inflation rewards over 5 years (via Ecosystem Grants pool), bringing fully-diluted supply to ~1.05B by M60.*


---

## Disclaimer

This document is a technical specification for the VAMS Protocol v2.1.0 (Dual-Chain). Token allocations and economic parameters are subject to governance changes. Not financial advice.
