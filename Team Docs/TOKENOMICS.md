
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
| **Initial Circulating** | 150,000,000 (15%) |
| **Token Standard** | ERC-20 (Ethereum/Polygon) |
| **Governance** | Quadratic Voting + Time-Weighted Power |

---

## 2. Token Utility

1.  **Universal Payment**: Pay for any DePIN resource (GPU, CPU, Storage) with $VAMS.
2.  **Staking**: Secure the PoS aggregator chain and earn yield.
3.  **Governance**: Direct the protocol's evolution and treasury allocation.
4.  **Bonding**: Required collateral for Service Providers and Agent Nodes.
5.  **Trust Staking**: Lock $VAMS to upgrade Trust Tiers (e.g., Bronze -> Silver) if lacking external proofs.
6.  **Roaming Security**: Agents stake "Good Behavior Bonds" to maintain Verified status while roaming.

### Value Accrual: "Burn & Build"
- **80% of Protocol Fees** → Buyback & Burn (Deflationary Pressure)
- **20% of Protocol Fees** → DAO Treasury (Sustainable Growth)

---

## 3. Allocation Breakdown (Decentralized Model)

We have optimized the distribution for maximum community ownership and decentralization security.

| Category | Percent | Amount | Vesting Schedule |
| :--- | :--- | :--- | :--- |
| **Community & Ecosystem** | **50%** | 500,000,000 | 10% TGE, 60-month linear vesting |
| **Team & Advisors** | **20%** | 200,000,000 | 12-month cliff, 36-month linear vesting |
| **Early Investors** | **10%** | 100,000,000 | 12-month cliff, 24-month linear vesting |
| **DAO Treasury** | **10%** | 100,000,000 | 6-month cliff, 48-month linear vesting |
| **Airdrop / Liquidity** | **10%** | 100,000,000 | **100% Unlocked at TGE** |

### Breakdown Details
- **Community (40%)**: Mining rewards, developer grants, and ecosystem incentives.
- **Airdrop (10%)**: Immediate distribution to early adopters to bootstrap network effects.
- **Team (20%)**: Divided into Founder (10%) and Future Hires (10%).

---

## 4. Vesting Schedules

### 4.1 Terms
- **Cliff**: Time before any tokens unlock.
- **Vesting**: Linear monthly unlocks after cliff.

| Category | Cliff | Vesting | Monthly Unlock |
| :--- | :--- | :--- | :--- |
| **Founder (10%)** | 12 months | 48 months | ~2.08M / month (after cliff) |
| **Future Team (10%)** | 12 months | 36 months | ~2.77M / month (after cliff) |
| **Investors (10%)** | 12 months | 24 months | ~4.16M / month (after cliff) |
| **DAO Treasury (10%)** | 6 months | 48 months | ~2.08M / month (after cliff) |
| **Community (50%)** | 0 months | 60 months | ~8.33M / month |

---

## 5. Emission Schedule (Inflationary Security)

To ensure perpetual network security, VAMS uses a **low-inflation model** strictly for staking rewards.

- **Initial Supply**: 1,000,000,000 (1B)
- **Max Annual Inflation**: 2.5% (25M tokens/year initially)
- **Adjustment**: DAO can reduce inflation rate (0% floor), but never increase above 2%.

### Net Deflation Target
With **Buyback & Burn (80% of fees)**, the protocol aims to be **net deflationary** when annual fee revenue exceeds ~$4M (at $0.20 token price).

---

## 6. Governance: Quadratic Voting

To prevent whale dominance, VAMS employs **Quadratic Voting (QV)** for crucial governance decisions.

- **Voting Power** = Market Sqrt(Tokens Staked)
- **Example**:
  - Alice stakes 100 VAMS → 10 Votes
  - Bob stakes 10,000 VAMS → 100 Votes
  - Bob has 100x the stake, but only 10x the voting power.

This protects the "Sovereign Brain" from being controlled by a single large entity.

---

## Appendix A: Token Unlock Schedule (Corrected)

| Month | Airdrop/Liq | Community | Treasury | Founder | Team | Investors | **Total Circulating** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TGE** | 100M | 0M | 0M | 0M | 0M | 0M | **100M** (10%) |
| **M6** | 100M | 50M | 0M (Cliff Ends) | 0M | 0M | 0M | **150M** (15.0%) |
| **M12** | 100M | 100M | 12.5M | 0M (Cliff Ends) | 0M (Cliff Ends) | 0M (Cliff Ends) | **212.5M** (21.25%) |
| **M24** | 100M | 200M | 37.5M | 25M | 33M | 50M | **445.5M** (44.55%) |
| **M36** | 100M | 300M | 62.5M | 50M | 66M | 100M (Done) | **678.5M** (67.85%) |
| **M48** | 100M | 400M | 87.5M | 75M | 100M (Done) | 100M | **862.5M** (86.25%) |
| **M60** | 100M | 500M (Done) | 100M (Done) | 100M (Done) | 100M | 100M | **1.00B*** |

*> Includes estimated 50M inflation rewards over 5 years distributed via Community pool.*


---

## Disclaimer

This document is a technical specification for the VAMS Protocol v2.0.0. Token allocations and economic parameters are subject to governance changes. Not financial advice.
