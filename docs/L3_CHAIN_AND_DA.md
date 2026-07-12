# VAMS L3 Chain & Data Availability

**Lifecycle:** Current design and testnet boundary
**Last verified:** 2026-07-12

## Overview
VAMS (Verifiable and Agentic Modular Stack) contains a Polygon CDK Validium
prototype and an intended dual-host deployment design. It does not currently
operate a deployed L3. The `cdk-deployment/` shell script is a local scaffold
with mock checks, not a production deployment procedure.

To ensure this off-chain data is safe, we use a **Multi-DA Router** with **Data Availability Sampling (DAS)**.

## Architecture

### The L3 Validium
- **Stack**: Polygon CDK (Zero-Knowledge Rollup technology)
- **Settlement**: Polygon PoS (via AggLayer in future updates)
- **Gas Token**: $VAMS
- **Throughput**: High (dedicated blockspace for agents)

### Workflow Execution

- **Engine**: DBOS SDK (PostgreSQL-backed)
- **State Storage**: Workflow execution state is stored in PostgreSQL (Celestia/Arweave are used exclusively for state root anchoring, not active workflow state).
- **Execution**: See [WORKFLOW_ENGINE.md](../neuron/docs/WORKFLOW_ENGINE.md) for details on crash-proof, exactly-once step execution.

### Data Availability Strategy
We do not rely on a single DA provider. The `DARouter` dynamically routes data payloads.

| Provider | Type | Verification | Use Case |
| :--- | :--- | :--- | :--- |
| **Polygon DA** | Committee (DAC) | **Signatures** (2/N) | **L3 State Roots** (Fast, Cheap) |
| **Celestia** | Decentralized L1 | **DAS** (Sampling) | **Agent Logs**, Public Audit Trail |
| **Near DA** | Sharded L1 | Optimistic/Light | High-Frequency / Ephemeral Data |
| **Avail** | Validity L1 | KZG Commitments | Structured stub; blocked from live use |

## Data Availability Sampling (DAS)
VAMS agents run light clients that verify data is available without downloading the full block.

### 1. Celestia (Probabilistic)
We perform 2D Reed-Solomon sampling. By requesting small random chunks of the data root, we can statistically guarantee (99.9%) that the entire data block is available.

### 2. Polygon DA (Deterministic)
We rely on a Data Availability Committee (DAC). Verification involves checking valid signatures from a quorum of committee members.

## Failover Logic
1. Live audit paths use Celestia and Near only after receipt verification.
2. Explicitly disabled targets fail instead of silently rerouting.
3. Avail and EigenDA remain unavailable for live evidence until their adapters are implemented and independently verified.

## Running Node
See `cdk-deployment/README.md` for instructions on spinning up a local CDK node.
