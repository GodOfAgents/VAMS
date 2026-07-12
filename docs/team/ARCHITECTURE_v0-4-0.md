> [!WARNING]
> **This document covers v0.4.0 and is superseded for Intelligence Layer details.**
> For the current architecture including the AUTOSKILL Intelligence Layer (v0.5.0),
> see **[ARCHITECTURE_v0-5-0.md](./ARCHITECTURE_v0-5-0.md)**. The v0.4.0 sections
> below remain valid for the Escrow, DEC, Sentinel, Composer, and Timelock subsystems.

# VAMS Architecture Addendum: v0.4.0 (ICN-Inspired Modular Stack)

**Status:** Implemented in source; deployment evidence pending
**Last verified:** 2026-07-12
**Replaces:** Partial sections of `ARCHITECTURE_v0-3-0.md`. This is an addendum.
**Objective:** Evolve the monolithic agentic framework into a fully composable, decentralized infrastructure stack inspired by the Impossible Cloud Network (ICN).

## 1. Architectural Upgrades & Deprecations

This addendum supersedes specific subsystems defined in v0.3.0. Please refer to this document for the new sources of truth on the following components:

- **Escrow & Settlement:** The legacy `VAMS_BountyEscrow` is **deprecated**. Replaced by the **Master Hybrid Escrow Model** (`ComposedSettlement`).
- **Emission & Tokenomics:** The static inflation model is **deprecated**. Replaced by the **Regional DEC System** (`RegionAwareDEC` and `RegionalIncentives`).
- **Slashing & Compliance:** Static slashing parameters are **deprecated**. Replaced by the dynamic **Sentinel Enforcer Loop** (`SLAEnforcer`).
- **Agent Orchestration:** Agent tasks are no longer hardcoded RPCs. Replaced by the **Intelligence Layer Abstractions** (`ResourceComposer` and `ServiceBlockRegistry`).
- **Governance:** Multisig operational roles are mapped directly to the **Security Council Timelocks**.

---

## 2. Master Hybrid Escrow Model

Located in `contracts/src/economic/ComposedSettlement.sol`.

The previous escrow model forced 1:1 relationships between agents and specific hardware nodes. The new hybrid escrow supports *composed blueprints* where a single AI intent can fund a fragmented fleet of micro-service providers.

### Workflow & Invariants:
1.  **Fund Lock:** An agent locks a bulk amount of $VAMS (`totalAmount`) against a specific composed `blueprintHash`.
2.  **Fractional Claiming:** Up to 20 providers can be listed as beneficiaries. Providers claim their share *asynchronously and independently*. A failure/slash on Provider A does not block Provider B from claiming.
3.  **Revenue Split:** Every claim automatically deducts two fee margins:
    -   *Protocol Fee:* Hardcoded 5 bps routed to the protocol treasury.
    -   *Builder Fee:* Up to 50% (configurable via Service Blocks) routed to the original deployment architect.
4.  **Refunds:** Locked capital that remains unclaimed post-expiry (`expiresAt`) returns to the agent. No capital gets stuck.

---

## 3. Regional DEC System (Dynamic Emissions)

Located in `contracts/src/economic/RegionAwareDEC.sol` & `contracts/src/economic/RegionalIncentives.sol`.

The token emission logic now uses geospatial economics. This maps network inflation directly to physical hardware distribution to counter AWS/GCP datacenter centralization.

### Dynamic Allocation Algorithm:
1.  The base `DynamicEmissionController` computes an annual inflation rate based on total network utilization (defaulting to ~2% but fluctuating up to 5%).
2.  The `RegionAwareDEC` converts this into a 7-day Epoch Budget.
3.  The epoch budget is split across geographic zones (e.g., `EU-CENTRAL-1`, `US-WEST-2`, `APAC-SOUTH-1`).
4.  Each region's slice is calculated via `weightedCapacity` (Multiplier × Registered Active Nodes).
5.  A **Cap Mechanism** ensures no single region can claim more than 30% of the epoch rewards, forcing providers to deploy infrastructure in under-served zones to chase higher yields. 

---

## 4. Sentinel Enforcer Loop

Located in `contracts/src/sentinel/SLAEnforcer.sol` & `contracts/src/da/PerformanceAnchor.sol`.

"Trust through mathematics, not reputation." The Sentinel Network acts as the objective observer of the entire VAMS ecosystem.

### Flow:
-   **Execution:** Registered hardware providers execute inference or compute jobs.
-   **Auditing:** Specialized Sentinel Nodes (high-uptime, staked watchtowers) run probabilistic redundancy checks on the output and latency.
-   **Anchoring (Phase 0):** Sentinels post the raw audit logs to decentralized DA layers (Celestia for logs, Polygon DA for state roots) and push the receipt hash to the `PerformanceAnchor` smart contract.
-   **Enforcement:** Evaluates the `reportHash` via `SLAEnforcer`.
    *   If SLAs are met → `RewardDistributor` accumulates Base Reward + Regional Bonus + Staking Boost.
    *   If SLAs are breached → `SlashingManager` confiscates the provider's bonded hardware collateral.

---

## 5. Intelligence Layer Abstractions (Composer & Blocks)

Located in `contracts/src/infrastructure/ServiceBlockRegistry.sol` & `server.py` (`/composer/*`).

We have decoupled the *infrastructure interface* from the *agent intent*.

1.  **Service Block Registry:** Independent DevOps engineers and architects ("Builders") create deployment configurations (e.g., "Llama 3 70B on 4x A100s with ZK-Proof wrappers"). They stake $VAMS to list it on the registry and set a revenue share expectation.
2.  **Resource Composer Engine:** When an agent needs compute, it sends a generic intent. The Python-based Composer Engine parses the available Service Blocks, benchmarks the current hardware supply against Regional DEC incentives, and dynamically packages a *Blueprint*.
3.  This Blueprint is sent to the `ComposedSettlement` contract for funding.

This creates a permissionless app-store for decentralized compute patterns.

---

## 6. Security Council Timelocks

All upgradeability and economic parameter adjustments are governed by standard OpenZeppelin Timelocks. 
For v0.4.0:
-   `RegionCapBps` adjustments (e.g., from 30% to 20%) require a 48-hour timelock.
-   `TierBoost` percentages in the Reward Distributor require a 72-hour timelock.
-   Protocol Fee changes (locked at 5 bps max) are capped mathematically via the Solidity implementation.
