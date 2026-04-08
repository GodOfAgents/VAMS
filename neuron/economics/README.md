# Regional Economics & Rewards (`neuron/economics/`)

This package implements Phase 4 (Economics) of the ICN-inspired roadmap.

## Overview
Implements dynamic DePIN incentives, regional bootstrap multipliers, and the composed settlement abstractions to shift VAMS from a flat global market to a geo-economically optimized infrastructure layer.

## Components
- `regional.py`: The `RegionalEconomics` engine. Calculates active multiplier limits and decay curves based on node density in regions like `eu-central-1` or `ap-southeast-1`.
- `reward_engine.py`: Computes the final daily provider reward considering SLA tier, regional multipliers, and staking boosts.
- `dec_regional.py`: Simulates continuous off-chain emission of Dynamic Emission Credits (DEC) based on a network-wide soft cap logic.
- `composed_settlement.py`: Python SDK over the `ComposedSettlement` escrow contract. Handles multi-provider payment splits for composed instances.
- `keeper.py`: An automated chron-job bot that synchronizes DEC limits to the blockchain at regular intervals.

## Relevant Contracts
- `RewardDistributor.sol`
- `RegionAwareDEC.sol`
- `ComposedSettlement.sol`
