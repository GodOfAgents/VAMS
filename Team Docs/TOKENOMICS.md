<!--
╔══════════════════════════════════════════════════════════════════════════════╗
║                         INTELLECTUAL PROPERTY NOTICE                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Document: VAMS Tokenomics v1.0.0                                            ║
║  Author: Aseem Chishti                                                       ║
║  Email: aseeminksa@gmail.com                                                 ║
║  LinkedIn: https://www.linkedin.com/in/aseemchishti                          ║
║                                                                              ║
║  Copyright (c) 2026 Aseem Chishti. All Rights Reserved.                      ║
║  Licensed under the MIT License - see LICENSE file for details.              ║
╚══════════════════════════════════════════════════════════════════════════════╝
-->

# $VAMS Tokenomics

## The Economic Engine of the Verifiable and Agentic Modular Stack

**Version:** 1.0.0  
**Date:** January 2026  
**Status:** Pre-Launch Specification

---

## Table of Contents

1.  [Executive Summary](#1-executive-summary)
2.  [Token Overview](#2-token-overview)
3.  [Allocation Breakdown](#3-allocation-breakdown)
4.  [Vesting Schedules](#4-vesting-schedules)
5.  [Revenue Model](#5-revenue-model)
6.  [Value Accrual Mechanisms](#6-value-accrual-mechanisms)
7.  [Emission Schedule](#7-emission-schedule)
8.  [Staking & Governance](#8-staking--governance)
9.  [Economic Security](#9-economic-security)
10. [Founder & Team Compensation](#10-founder--team-compensation)

---

## 1. Executive Summary

The $VAMS token is the native utility token powering the VAMS ecosystem—a unified payment and governance layer that abstracts the complexity of multi-protocol DePIN infrastructure. Rather than requiring users to manage AKT (Akash), IO (io.net), TAO (Bittensor), TIA (Celestia), and other protocol tokens, $VAMS provides a single token interface for all infrastructure consumption.

### Key Metrics

| Parameter               | Value                                    |
|-------------------------|------------------------------------------|
| **Token Name**          | VAMS                                     |
| **Token Symbol**        | $VAMS                                    |
| **Total Supply**        | 1,000,000,000 (1 billion, fixed cap)     |
| **Initial Circulating** | 150,000,000 (15%) — see TGE breakdown    |
| **Token Standard**      | ERC-20 (Ethereum) + Wrapped variants     |
| **Governance**          | Progressive decentralization to full DAO |

#### TGE Circulating Supply Breakdown (150M / 15%)

| Source                      | Tokens      | % of Supply | Notes                              |
|-----------------------------|-------------|-------------|------------------------------------|
| **Initial Liquidity**       | 50,000,000  | 5%          | DEX/CEX liquidity pools            |
| **Community Airdrop**       | 50,000,000  | 5%          | Early adopters, testnet participants |
| **Ecosystem Grants**        | 50,000,000  | 5%          | Developer incentives, integrations |
| **Total at TGE**            | 150,000,000 | 15%         |                                    |

---

## 2. Token Overview

### 2.1 Token Utility

$VAMS serves five critical functions within the ecosystem:

| Function       | Description |
|----------------|-------------|
| **Payment**         | Universal payment for compute, storage, DA, and TEE services |
| **Gas Abstraction** | Pay gas in $VAMS; protocol handles multi-chain conversion |
| **Staking** | Secure the network, earn rewards, participate in governance |
| **Governance** | Vote on protocol upgrades, parameter changes, treasury allocation |
| **Collateral** | Required stake for CLR operators, bridge validators, and providers |

### 2.2 Why a Native Token?

1. **Economic Unification**: One token to access 15+ DePIN protocols
2. **Value Capture**: Protocol fees accrue to $VAMS holders, not fragmented across tokens
3. **Aligned Incentives**: Stakers have skin in the game for network security
4. **Governance Rights**: Token holders control protocol evolution
5. **Reduced Friction**: Agents handle one token instead of managing 10+ wallets

### 2.3 Payment Architecture (Universal Top-Up)

VAMS uses a **"Pay with Any Token"** model. Users top-up their account with any supported token, and the protocol handles all conversions to $VAMS automatically.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    UNIVERSAL PAYMENT FLOW                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  USER TOP-UP                  VAMS PROTOCOL                 PROVIDERS    │
│  ──────────                   ─────────────                 ─────────    │
│                                                                          │
│  Credit Card ──┐                                                         │
│  USDC/USDT ────┼──► Auto-Convert ──► $VAMS ──► Swap ──► Provider Token  │
│  ETH/SOL ──────┤    to $VAMS         Balance    to       (AKT, IO, etc.)│
│  Any Token ────┘                                Native                   │
│                                                                          │
│  Dynamic Fee: 0.1% - 1.0% (based on network load)                       │
│  All fees → 100% Buyback & Burn                                         │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Dynamic Protocol Fee

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Floor** | 0.1% | Minimum fee (covers operational costs) |
| **Base** | 0.3% | Default when network is normal |
| **Ceiling** | 1.0% | Maximum fee (prevents gouging) |

| Transaction Type    | Min   | Default | Max  | Notes |
|---------------------|-------|---------|------|-------|
| Standard Compute    | 0.1%  | 0.3%    | 1.0% | — |
| High-Value (>$10K)  | 0.05% | 0.1%    | 0.5% | Volume discount |
| Micropayments (<$1) | $0.005 OR 0.5% | $0.01 OR 0.75% | $0.02 OR 1.0% | Fixed fee floor for competitiveness¹ |
| Bridge Transfers    | 0.1%  | 0.25%   | 0.5% | — |
| Gas Abstraction     | 2%    | 5%      | 7%   | Reduced from 10% for UX retention |

> ¹ **Micropayment Rationale**: Fixed fee floor ($0.005-$0.02) ensures competitiveness with x402/Lightning at scale. Percentage alternative applies when it results in lower fee. Comparable to Stripe's $0.05 minimum.

Fee parameters adjustable by DAO governance within bounds.

> **Dynamic TAO Integration**: Fee parameters may also be adjusted automatically by the Dynamic TAO RL-based controller within these bounds (max ±10% per epoch). The static ranges above serve as hard limits that the RL model cannot exceed. See [ARCHITECTURE_v0-3-0.md §3.5](./ARCHITECTURE_v0-3-0.md) for the complete validation framework.

#### Developer Console (AWS-Style UX)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  VAMS Developer Console                            [wallet] ▼  [Logout] │
├──────────────────────────┬──────────────────────────────────────────────┤
│                          │                                              │
│  💳 BALANCE             │  📊 USAGE THIS MONTH                         │
│  ─────────               │  ────────────────────                        │
│  $1,247.50 USD           │  Compute (Akash):    $423.00    ████████░░   │
│  (12,475 VAMS)           │  GPU (io.net):       $312.00    ██████░░░░   │
│                          │  Storage (Arweave):   $89.00    ██░░░░░░░░   │
│  [+ Top Up]              │  TEE (Phala):         $45.00    █░░░░░░░░░   │
│                          │                                              │
│  TOP-UP OPTIONS          │  Total:              $869.00                 │
│  ───────────────         │                                              │
│  • Credit Card           │  ─────────────────────────────────────────   │
│  • USDC / USDT           │  🔥 Active Services                          │
│  • ETH / SOL             │  • 2x GPU instances (io.net)                 │
│  • Any ERC-20            │  • 1x Akash deployment                       │
│                          │  • 3x Agent workflows                        │
│                          │                                              │
└──────────────────────────┴──────────────────────────────────────────────┘
```

**CLI Alternative:**
```bash
$ vams balance                # View balance in USD
$ vams topup 100 --from usdc  # Top up with USDC
$ vams deploy ./agent.yaml    # Deploy with cost estimate
$ vams usage --month          # View monthly breakdown
```

#### $VAMS Value Capture

| Mechanism | How It Drives $VAMS Value |
|-----------|---------------------------|
| **All Payments → VAMS**  | Every transaction creates buy pressure  |
| **Buyback & Burn**       | 100% of fees used to buy and burn $VAMS |
| **Staking Requirements** | CLR operators must stake 100K+ VAMS     |
| **Governance Rights**    | Only $VAMS stakers vote on protocol     |
| **No Token Giveaways**   | No cashback, no emissions dilution      |

---

## 3. Allocation Breakdown

### 3.1 Token Distribution

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     $VAMS TOKEN ALLOCATION (1B Total)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ██████████████████████████████████████    Community & Ecosystem (34%)  │
│  ██████████████████████████                Protocol Treasury (21%)      │
│  ████████████████                          Founder (16%)                 │
│  ██████████████                            Investors (14%)               │
│  ██████████                                Team & Advisors (10%)         │
│  ██████                                    Initial Liquidity (5%)        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Detailed Allocation Table

| Category | Allocation | Tokens | Purpose |
|----------|-----------|--------|---------|
| **Community & Ecosystem** | 34% | 340,000,000 | Airdrops, staking rewards, grants, liquidity mining |
| **Protocol Treasury** | 21% | 210,000,000 | Development, partnerships, ecosystem growth |
| **Founder** | 16% | 160,000,000 | Founder equity (solo founder) |
| **Investors** | 14% | 140,000,000 | Pre-seed, Seed, Strategic rounds |
| **Team & Advisors** | 10% | 100,000,000 | Future engineering hires, advisors |
| **Initial Liquidity** | 5% | 50,000,000 | DEX/CEX liquidity at TGE |
| **Total** | 100% | 1,000,000,000 | |

### 3.3 Investor Breakdown (14% Total)

| Round | Allocation | Tokens | Status |
|-------|-----------|--------|--------|
| **Strategic Partners** | 7% | 70,000,000 | Active outreach (Grants + Partnerships) |
| **Seed Round** | 4% | 40,000,000 | Future (~$800K-1M) |
| **Ecosystem Partners** | 3% | 30,000,000 | Protocol integrations |

---

## 4. Vesting Schedules

### 4.1 Vesting Overview

All non-circulating tokens follow structured vesting to ensure long-term alignment:

```
Timeline (Months)
│
│  TGE    6m      12m     18m     24m     30m     36m     42m     48m     60m
│   │      │       │       │       │       │       │       │       │       │
│   ▼      ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼
│   
│   ░░░░░░░░░░░░░░████████████████████████████████████████████████  Founder
│   ░░░░░░████████████████████████████████████████████████          Team
│   ░░░░░░░░░░░░████████████████████████████████                    Alliance
│   ░░░░████████████████████████████████                            Seed
│   ████████████████████████████████████████████████████████████    Community
│
│   Legend: ░ = Cliff (locked)  █ = Vesting (linear unlock)
```

### 4.2 Detailed Vesting Terms

| Category                | Cliff     | Vesting Period | Unlock Schedule                         |
|-------------------------|-----------|----------------|-----------------------------------------|
| **Founder**             | 12 months | 48 months      | 25% at cliff, then monthly linear       |
| **Team & Advisors**     | 12 months | 36 months      | 25% at cliff, then monthly linear       |
| **Alliance (Pre-Seed)** | 12 months | 36 months      | 25% at cliff, then monthly linear       |
| **Seed Investors**      | 6 months  | 24 months      | 20% at cliff, then monthly linear       |
| **Strategic**           | 3 months  | 18 months      | 15% at cliff, then monthly linear       |
| **Community**           | None      | 60 months      | Linear unlock with activity multipliers |
| **Treasury**            | 6 months  | 48 months      | 2%/month operational runway, DAO unlocks rest |
| **Liquidity**           | None      | None           | Fully unlocked at TGE                   |


### 4.3 Founder Vesting Example (160M $VAMS)

| Month | Event  | Tokens Unlocked | Cumulative  | % Vested |
|-------|--------|-----------------|-------------|----------|
| 0     | TGE    | 0               | 0           | 0%       |
| 12    | Cliff  | 40,000,000      | 40,000,000  | 25%      |
| 24    | Year 2 | 40,000,000      | 80,000,000  | 50%      |
| 36    | Year 3 | 40,000,000      | 120,000,000 | 75%      |
| 48    | Year 4 | 40,000,000      | 160,000,000 | 100%     |

---

## 5. Revenue Model

### 5.1 Protocol Revenue Streams

VAMS generates revenue through multiple sustainable mechanisms:

| Revenue Stream              | Rate     | Description                                         |
|-----------------------------|----------|-----------------------------------------------------|
| **Protocol Fees**           | 0.1-0.5% | Transaction fees on all protocol activity           |
| **Gas Abstraction Premium** | 2-7%     | Markup on cross-chain gas conversions               |
| **x402 Settlement**         | 0.05%    | Micropayment processing for agent commerce          |
| **Bridge Fees**             | 0.25%    | Cross-chain asset transfers                         |
| **Infrastructure Markup**   | 1-5%     | Commission on managed L1s (Compute + ACP-77 fees)   |
| **Ecosystem Grants**        | Variable | Non-dilutive funding from integrated L1/L2 partners |

> **x402 Settlement Security**: Micropayments are secured by atomic escrow with nonce-based double-spend prevention. Providers must bond 10,000+ $VAMS and are protected by settlement failure recovery mechanisms. See [ARCHITECTURE_v0-3-0.md §20.2](./ARCHITECTURE_v0-3-0.md) for technical specification.

### 5.2 Revenue Projections

| Year   | Monthly Volume | Protocol Revenue | Annual Revenue |
|--------|----------------|------------------|----------------|
| **Y1** | $500K          | $1,500           | $18K           |
| **Y2** | $5M            | $15,000          | $180K          |
| **Y3** | $50M           | $150,000         | $1.8M          |
| **Y4** | $250M          | $750,000         | $9M            |
| **Y5** | $1B            | $3,000,000       | $36M           |

> Assumes 0.3% average protocol fee rate and growth trajectory aligned with crypto infrastructure adoption.

### 5.3 Ecosystem Grant Strategy (Non-Dilutive)

VAMS is uniquely positioned to receive grants from the protocols it aggregates:

| Provider             | Grant Program      | Potential      | Priority |
|----------------------|--------------------|----------------|----------|
| **Polygon/AggLayer** | Village Grants     | $25k - $100k   | High     |
| **Avalanche**        | infraBUIDL         | $50k - $100k   | Medium   |
| **Near Protocol**    | Horizon/Foundation | $10k - $50k    | High     |
| **Filecoin/Arweave** | Open Data/Permaweb | $5k - $50k     | Medium   |
| **Bittensor**        | Subnet Grants      | TAO Allocation | Medium   |

**Strategy**: Apply for "Integration Grants" immediately upon Testnet launch to extend runway without dilution.

---

## 6. Value Accrual Mechanisms

### 6.1 Fee Distribution

Protocol revenue distribution follows a **two-phase model**:

#### Phase 1: Bootstrap Period (Until Token Vesting Complete — ~Month 60)

```
Protocol Revenue (100%)
        │
        └──► Buyback & Burn (100%)     → Maximum deflationary pressure
```

> **Rationale**: During the vesting period, new tokens enter circulation from unlocks. 100% burn maximizes deflationary counterbalance to vesting emissions.

#### Phase 2: Mature Protocol (Post-Vesting)

```
Protocol Revenue (100%)
        │
        ├──► Buyback & Burn (40%)      → Deflationary pressure
        │
        ├──► Staking Rewards (30%)     → Validator/delegator incentives
        │
        ├──► Treasury (20%)            → Development & ecosystem grants
        │
        └──► Insurance Fund (10%)      → Black swan protection
```

> **Transition**: Fee distribution shift from Phase 1 → Phase 2 requires DAO governance approval.

### 6.2 Buyback & Burn Mechanism

- **Trigger**: Automated weekly buybacks from open market
- **Execution**: Smart contract purchases $VAMS using accumulated fees
- **Burn**: Tokens sent to `0x000...dead` address
- **Transparency**: All burns verifiable on-chain

### 6.3 Staking Rewards

| Tier         | Staked Amount             | Base APY | Bonus                    |
|--------------|---------------------------|----------|--------------------------|
| **Bronze**   | 1,000 - 10,000 $VAMS      | 6%       | -                        |
| **Silver**   | 10,001 - 100,000 $VAMS    | 8%       | Priority support         |
| **Gold**     | 100,001 - 1,000,000 $VAMS | 10%      | Governance weight 1.5x   |
| **Platinum** | 1,000,001+ $VAMS          | 12%      | CLR operator eligibility |

> **Note**: APYs shown are *target rates*, subject to participation levels. Higher staking participation reduces individual APY proportionally. Actual rewards = (Your Stake / Total Staked) × Annual Emissions.

---

## 7. Emission Schedule

### 7.1 Annual Emissions

New tokens are minted for staking rewards according to a decreasing schedule:

| Year | New Emissions | % of Supply | Cumulative Inflation |
|------|---------------|-------------|----------------------|
| 1    | 25,000,000    | 2.50%       | 2.50%                |
| 2    | 20,000,000    | 1.95%       | 4.45%                |
| 3    | 15,000,000    | 1.42%       | 5.87%                |
| 4    | 10,000,000    | 0.92%       | 6.79%                |
| 5    | 5,000,000     | 0.46%       | 7.25%                |
| 6-10 | 1,000,000/yr  | ~0.09%/yr   | ~7.70%               |

> **Dynamic TAO Integration**: The schedule above represents the *maximum* annual emissions. The Dynamic TAO controller may reduce effective emission rates within bounds (0.1% - 5% annual) based on network demand signals. This provides flexibility while ensuring the static schedule serves as a hard ceiling. See [ARCHITECTURE_v0-3-0.md §3.5](./ARCHITECTURE_v0-3-0.md) for RL model validation and safety mechanisms.

### 7.3 Terminal Emission Policy (Post-Year 10)

After Year 10, emissions follow a **fixed terminal rate** to ensure perpetual network security:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Terminal Rate** | 500,000 $VAMS/year | 0.05% annual inflation floor |
| **Adjustment** | DAO governance can reduce (never increase) | Prevents inflation creep |
| **Hard Cap Trigger** | If burned > emitted for 4 consecutive quarters, emissions pause | Auto-deflationary mode |
| **Security Floor** | Minimum 10M $VAMS staked to resume emissions | Ensures network security |

> **Design Philosophy**: Terminal emissions guarantee validators always have incentive to secure the network, while burns from protocol usage create net-deflationary pressure at maturity.

### 7.4 Deflationary Potential

The buyback & burn mechanism creates deflationary pressure proportional to protocol usage.

**Formula:**
```
Tokens Burned = Annual Fee Revenue ($) / VAMS Price ($)
Net Inflation = (Tokens Emitted - Tokens Burned) / Total Supply
```

**Break-Even Revenue (to offset emissions):**

| Emission Year | Tokens Emitted | Revenue Needed at $0.10/VAMS | Revenue Needed at $1.00/VAMS |
|---------------|----------------|------------------------------|------------------------------|
| Y1            | 25M            | $2.5M                        | $25M                         |
| Y3            | 15M            | $1.5M                        | $15M                         |
| Y5            | 5M             | $500K                        | $5M                          |

**Scenario Analysis (Year 3):**

| Scenario | Monthly Volume | Annual Revenue | VAMS Price | Tokens Burned | Net Result             |
|----------|----------------|----------------|------------|---------------|------------------------|
| **Bear** | $5M            | $180K          | $0.05      | 3.6M          | +1.1% inflationary     |
| **Base** | $50M           | $1.8M          | $0.20      | 9M            | +0.6% inflationary     |
| **Bull** | $200M          | $7.2M          | $0.50      | 14.4M         | ~0% neutral            |

> **Note**: We do not guarantee a specific deflationary timeline. Burn rate depends on protocol adoption and market conditions. Higher token prices mean fewer tokens burned per dollar of revenue.

---

## 8. Staking & Governance

### 8.1 Governance Power

Staked tokens grant governance rights:

| Action | Requirement |
|--------|-------------|
| **Create Proposal** | 100,000 $VAMS staked + 10,000 $VAMS deposit |
| **Vote on Proposals** | 1 $VAMS = 1 vote (staked only) |
| **Emergency Pause** | 5% of staked supply (multi-sig) |
| **Protocol Upgrade** | 66% approval, **20% quorum** |
| **Treasury Spend** | 51% approval, **20% quorum** |
| **Parameter Change** | 60% approval, **15% quorum** |

### 8.2 Proposal Deposit Mechanism

To prevent governance spam and ensure serious proposals:

| Parameter | Value |
|-----------|-------|
| **Deposit Amount** | 10,000 $VAMS (~$1,000 at $0.10) |
| **Refund Condition** | Proposal reaches quorum (pass or fail) |
| **Burn Condition** | Proposal fails to reach quorum |
| **Cooldown** | 7 days between proposals from same address |

> **Anti-Spam**: Deposits create cost for frivolous proposals while refunding legitimate governance participation.

### 8.3 Staking Mechanics

| Parameter | Value |
|-----------|-------|
| **Minimum Stake** | 1,000 $VAMS |
| **Lock Period** | 7 days (unbonding) |
| **Compounding** | Auto-compound option available |

### 8.4 Slashing Penalties (Detailed)

Validators and operators face proportional penalties for misbehavior:

| Offense | Severity | Slash % | Jail Period | Notes |
|---------|----------|---------|-------------|-------|
| **Downtime** (missed 50+ blocks) | Low | 0.5% | 1 hour | Auto-unjail after period |
| **Downtime** (missed 500+ blocks) | Medium | 2% | 24 hours | Manual unjail required |
| **Double-Signing** | High | 5% | 7 days | Tombstone after 3 offenses |
| **State Manipulation** | Critical | 10% | Permanent | Full stake burned |
| **Bridge Fraud** | Critical | 10% | Permanent | Plus insurance fund claim |
| **TEE Attestation Fraud** | Critical | 10% | Permanent | Cryptographic proof required |

> **Slashed tokens**: 50% burned, 50% to Insurance Fund. Repeat offenders face escalating penalties.

---

## 9. Economic Security

### 9.1 Circuit Breakers

Automatic protections against market manipulation:

| Alert Level | Token Drop (24h) | Action |
|-------------|------------------|--------|
| **Yellow** | 50-74% | Extended unbonding (14 days) |
| **Orange** | 75-89% | Withdrawal limits, reduced emissions |
| **Red** | ≥90% | Emergency pause, DAO governance activation |

### 9.2 Insurance Fund

| Parameter | Value |
|-----------|-------|
| **Target Size** | 5% of TVL (min 1M $VAMS) |
| **Funding Sources** | 10% of fees + 100% of slashed stakes |
| **Coverage** | Bridge exploits, TEE compromise, oracle failures |
| **Claims** | DAO approval required |

### 9.3 Oracle Security & Attack Mitigation

VAMS employs multi-layer oracle protection:

| Layer | Mechanism | Protection |
|-------|-----------|------------|
| **Multi-Oracle** | Aggregate from 3+ sources (Chainlink, Pyth, RedStone) | No single point of failure |
| **TWAP** | 15-minute time-weighted average prices | Flash loan resistance |
| **Deviation Check** | Reject prices deviating >5% from median | Manipulation detection |
| **Heartbeat** | Oracle must update within 1 hour | Stale price protection |
| **Circuit Breaker** | Pause if all oracles deviate >20% | Black swan protection |

**Oracle Attack Response Protocol:**

```
Deviation Detected (>5%)
        │
        ├─► Alert: Log to monitoring, notify operators
        │
        ├─► If >10% deviation: Switch to backup oracle set
        │
        ├─► If >20% deviation: Pause affected price feeds
        │
        └─► If 3+ oracles fail: Emergency protocol pause (requires 5% multi-sig to resume)
```

### 9.4 Anti-Whale Provisions

| Mechanism | Limit |
|-----------|-------|
| **Single Wallet Cap** | 5% of circulating supply |
| **Daily Transfer Limit** | 1% of circulating (first 6 months) |
| **Governance Cap** | Max 10% voting power per entity |

### 9.5 Token Velocity Sinks

Mechanisms to encourage holding and reduce speculative velocity:

| Sink | Mechanism | Effect |
|------|-----------|--------|
| **Staking Tiers** | Higher APY for longer lock-ups (30/90/180 days) | Reduces liquid supply |
| **Governance Multiplier** | 1.5x voting power for 6+ month stakes | Rewards long-term alignment |
| **Fee Discounts** | 10-25% protocol fee reduction for stakers | Utility incentive to hold |
| **CLR Operator Bonds** | 100K+ VAMS locked for 12 months minimum | Infrastructure commitment |
| **Bridge Collateral** | Validators must over-collateralize 150% | Security requirement |
| **Loyalty Rewards** | Monthly bonus for unbroken staking streaks | Gamified retention |

> **Velocity Target**: Aim for <4 annual turns (similar to ETH) vs typical utility token 10-20x velocity.

---

## 10. Founder & Team Compensation

### 10.1 Founder (Solo) Allocation

As a solo founder, the following structure applies:

| Component | Amount | Notes |
|-----------|--------|-------|
| **Token Allocation** | 16% (160M $VAMS) | 4-year vest, 1-year cliff |
| **Year 1 Salary** | $3,000/mo ($36K/yr) | Survival mode (Covered by Grants/Pre-seed) |
| **Year 2 Salary** | $5,000/mo ($60K/yr) | Post-MVP / Series A |
| **Year 3 Salary** | $8,000/mo ($96K/yr) | Post-PMF |
| **Year 4 Salary** | $12,000/mo ($144K/yr) | Scaling |
| **Year 5 Salary** | Market Rate | Mature company |

### 10.2 Engineering Team Reserve

| Reserved Allocation | Purpose |
|---------------------|---------|
| 5-8% from Team Pool | Hire specialized engineers (Blockchain, AI/ML, DePIN) |
| 2-year vest, 1-year cliff | Standard employee terms |

### 10.3 Advisory Pool

| Advisor Type | Allocation | Vesting |
|--------------|-----------|---------|
| Strategic Advisor | 0.5% | 2 years, quarterly |
| Technical Advisor | 0.25% | 2 years, quarterly |
| Industry Mentor | 0.25% | 2 years, quarterly |

---

## Appendix A: Token Unlock Schedule

### Full Supply Reconciliation

The following table provides a complete breakdown of circulating supply by source at each milestone:

| Month | Liquidity | Community¹ | Treasury² | Founder | Investors³ | Team | Emissions⁴ | **Circulating** | **% Total** |
|-------|-----------|------------|-----------|---------|------------|------|------------|-----------------|-------------|
| 0 (TGE) | 50M | 100M | 0 | 0 | 0 | 0 | 0 | **150M** | **15.0%** |
| 3 | 50M | 117M | 0 | 0 | 4.5M | 0 | 6.25M | **177.75M** | **17.8%** |
| 6 | 50M | 134M | 0 | 0 | 16.5M | 0 | 12.5M | **213M** | **21.3%** |
| 12 | 50M | 168M | 0 | 40M | 48.5M | 25M | 25M | **356.5M** | **35.7%** |
| 24 | 50M | 236M | 0 | 80M | 108.5M | 58.3M | 45M | **577.8M** | **57.8%** |
| 36 | 50M | 304M | 52.5M | 120M | 140M | 91.7M | 60M | **818.2M** | **81.8%** |
| 48 | 50M | 340M | 105M | 160M | 140M | 100M | 70M | **965M** | **96.5%** |
| 60 | 50M | 340M | 157.5M | 160M | 140M | 100M | 75M | **1,022.5M** | **102.3%** |

> **Footnotes:**
> 1. **Community (340M)**: 100M at TGE (Airdrop + Grants), remainder linear over 60 months (~4M/month)
> 2. **Treasury (210M)**: 6-month cliff, then 2%/month operational runway (~4.2M/month), DAO unlocks remainder
> 3. **Investors (140M)**: Pre-Seed 70M (12mo cliff, 36mo vest), Seed 40M (6mo cliff, 24mo vest), Strategic 30M (3mo cliff, 18mo vest)
> 4. **Emissions**: Staking rewards per Section 7.1 schedule (25M Y1, 20M Y2, 15M Y3, 10M Y4, 5M Y5)

### Supply Exceeds 1B — Explanation

At Month 60, circulating supply appears to exceed 1B due to **NET emissions**. This is offset by:

| Mechanism | Effect |
|-----------|--------|
| **Buyback & Burn** | Protocol fees used to permanently remove tokens |
| **Slashing** | Misbehaving validators lose staked tokens (burned) |
| **Unclaimed Airdrops** | Unclaimed tokens return to treasury after 12 months |

**Target Equilibrium**: Burns should offset ~50-100% of emissions by Year 3 (see Section 7.4 Deflationary Potential).

> **Note on Rounding**: Circulating supply values are rounded to nearest 0.5M for readability. Actual values may vary slightly based on exact unlock timing and DAO decisions on Treasury releases.

### Simplified Circulating Supply Chart

```
Circulating Supply (Millions)
│
1000 ─────────────────────────────────────────────────── ▲ Full Supply
│                                                   ╱
│                                              ╱
800 ─────────────────────────────────────╱
│                                   ╱
│                              ╱
600 ─────────────────────╱
│                   ╱
│              ╱
400 ─────╱
│   ╱
│╱
200 ─
│ ▆▆▆▆
│ ████
0 ┼────────┬────────┬────────┬────────┬────────┬────────
  TGE     Y1       Y2       Y3       Y4       Y5
  (15%)   (35.7%)  (57.8%)  (81.8%)  (96.5%)  (100%+)
```

---

## Appendix B: Comparative Analysis

### vs. Other Infrastructure Tokens

| Token | Total Supply | Team % | Community % | Vesting |
|-------|-------------|--------|-------------|---------|
| **$VAMS** | 1B | 26% | 34% | 4-year |
| **$AKT (Akash)** | 388M | 20% | 30% | 4-year |
| **$IO (io.net)** | 800M | 25% | 35% | 4-year |
| **$TIA (Celestia)** | 1B | 26.8% | 26.8% | 4-year |
| **$TAO (Bittensor)** | 21M | 0% | 100% | Emission-based |

---

## Appendix C: Smart Contract Addresses

> To be populated post-deployment

| Contract | Network | Address |
|----------|---------|---------|
| $VAMS Token | Ethereum | TBD |
| Vesting Contract | Ethereum | TBD |
| Staking Contract | VAMS L3 | TBD |
| Treasury Multisig | Ethereum | TBD |
| Burn Address | Ethereum | `0x000...dead` |

---

## Disclaimer

This tokenomics document is provided for informational purposes only and does not constitute financial, investment, legal, or tax advice. Token allocations, vesting schedules, and economic parameters are subject to change based on market conditions, regulatory requirements, and community governance decisions. Past performance of similar projects does not guarantee future results. Consult with qualified professionals before making any investment decisions.

---

**Document Version:** 1.0.0  
**Last Updated:** January 2026  
**Maintainer:** Aseem Chishti  
**Contact:** aseeminksa@gmail.com

---

*VAMS – The Sovereign Brain for the Agentic Web*
