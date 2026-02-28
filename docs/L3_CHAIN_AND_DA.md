     # VAMS L3 Chain & Data Availability

## Overview
VAMS (Verifiable Agentic Model Systems) operates its own Layer 3 (L3) chain using **Polygon CDK**. This L3 is configured as a **Validium**, meaning it posts validity proofs to the L2 (Polygon Amoy/Mainnet) but keeps data off-chain for cost efficiency and scalability.

To ensure this off-chain data is safe, we use a **Multi-DA Router** with **Data Availability Sampling (DAS)**.

## Architecture

### The L3 Validium
- **Stack**: Polygon CDK (Zero-Knowledge Rollup technology)
- **Settlement**: Polygon PoS (via AggLayer in future updates)
- **Gas Token**: $VAMS
- **Throughput**: High (dedicated blockspace for agents)

### Data Availability Strategy
We do not rely on a single DA provider. The `DARouter` dynamically routes data payloads.

| Provider | Type | Verification | Use Case |
| :--- | :--- | :--- | :--- |
| **Polygon DA** | Committee (DAC) | **Signatures** (2/N) | **L3 State Roots** (Fast, Cheap) |
| **Celestia** | Decentralized L1 | **DAS** (Sampling) | **Agent Logs**, Public Audit Trail |
| **Near DA** | Sharded L1 | Optimistic/Light | High-Frequency / Ephemeral Data |
| **Avail** | Validity L1 | KZG Commitments | Backup for Validity Proofs |

## Data Availability Sampling (DAS)
VAMS agents run light clients that verify data is available without downloading the full block.

### 1. Celestia (Probabilistic)
We perform 2D Reed-Solomon sampling. By requesting small random chunks of the data root, we can statistically guarantee (99.9%) that the entire data block is available.

### 2. Polygon DA (Deterministic)
We rely on a Data Availability Committee (DAC). Verification involves checking valid signatures from a quorum of committee members.

## Failover Logic
1. **Primary**: Attempt Polygon DA.
2. **Failure**: If DAC is unreachable or signatures are invalid...
3. **Fallback**: Route payload to Celestia.
4. **Final Backup**: Route to Avail/Near.

## Running Node
See `cdk-deployment/README.md` for instructions on spinning up a local CDK node.
