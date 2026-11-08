# Regional Economics & Rewards (`neuron/economics/`)

This package implements Phase 4 (Economics) of the ICN-inspired roadmap.

## Overview
Implements dynamic DePIN incentives, regional bootstrap multipliers, and the composed settlement abstractions to shift VAMS from a flat global market to a geo-economically optimized infrastructure layer.

## Components
- `regional.py`: The `RegionalEconomics` engine. Calculates active multiplier limits and decay curves based on node density in regions like `eu-central-1` or `ap-southeast-1`.
- `reward_engine.py`: Computes the final daily provider reward considering SLA tier, regional multipliers, and staking boosts.
- `dec_regional.py`: Simulates continuous off-chain emission of Dynamic Emission Credits (DEC) based on a network-wide soft cap logic.
- `composed_settlement.py`: Python SDK over the `ComposedSettlement` escrow contract. Handles multi-provider payment splits for composed instances.
- `keeper.py`: A background loop for local epoch calculation/history; it does not submit or synchronize on-chain DEC state.
- `yield_manager.py`: Read-only contract-query wrapper. Both incomplete yield write methods reject in every runtime before accessing a fund or signer. The selected restricted profile keeps real yield disabled; this SDK implements no authentic deployment, withdrawal or recovery transaction.

Reward calculations, APR estimates and locally generated candidate roots are not
proof of payouts or applied chain state. Restricted-profile rewards remain zero;
local economic simulations do not enable them. A pass-through balance query is
not authenticated custody evidence. Any future yield/recovery route needs its
own chain-bound design, actual custody authorization and qualification; the former
fabricated transaction hashes are no longer returned.

## Relevant Contracts
- `RewardDistributor.sol`
- `RegionAwareDEC.sol`
- `ComposedSettlement.sol`
