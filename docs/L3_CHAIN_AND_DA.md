# VAMS L3 Chain & Data Availability

**Lifecycle:** Current design and testnet boundary
**Last verified:** 2026-10-18

## Overview
VAMS (Verifiable and Agentic Modular Stack) contains a Polygon CDK Validium
prototype and an intended dual-host deployment design. It does not currently
operate a deployed L3. The `cdk-deployment/` shell script is a local scaffold
with mock checks, not a production deployment procedure.

The design includes multiple DA providers, but the current source does not
provide a deployed or release-qualified multi-provider DA service. The
`PerformanceAuditLog` has a Celestia submission/retrieval path that is marked
ineligible for release evidence. The legacy `DARouter` is simulation-only and
rejects live execution.

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

| Provider | Current source reality | Verification and release status |
| :--- | :--- | :--- |
| **Polygon DA** | The legacy `DARouter` rejects live execution. Its `PolygonDACClient` increments the valid-signature count for each supplied signature; cryptographic signature verification is not implemented. | The documented 2-of-N check is not implemented evidence. |
| **Celestia** | `CelestiaDAAdapter` has live Mocha submission and exact-retrieval code paths. | Retrieved bytes are compared with the receipt commitment, but the adapter is not release-evidence eligible and does not establish provider inclusion/finality or independent observation. |
| **Near DA** | Local simulation only; live submission raises, verification returns false, and retrieval returns no bytes. | Not available for live receipt or retrieval evidence. |
| **Avail** | Structured simulated stub; live construction is rejected. | Verification returns false and retrieval is unavailable. |
| **EigenDA** | Structured simulated stub; live construction is rejected. | Verification returns false and retrieval is unavailable. |

## Data Availability Sampling (DAS)

The repository does not currently implement Celestia DAS verification. In a
live runtime, `CelestiaLightClient` raises `LiveModeSafetyError`. Its non-live
network probe checks `header.NetworkHead` and returns false; it does not sample
shares or verify the requested data root. The former 2D-sampling and 99.9%
claims describe an intended protocol design, not current VAMS behavior or
evidence.

## Failover Logic
1. `PerformanceAuditLog` configures Celestia as its only live-capable audit adapter. The adapter has submission/retrieval code paths, but `release_evidence_eligible` is false; no independent observer or inclusion/finality evidence is provided by that code.
2. Near live submission raises an error, verification returns false, and exact retrieval is unimplemented. Avail and EigenDA remain simulated stubs and reject live construction.
3. The legacy `DARouter` rejects live execution. Its simulated routing and placeholder Polygon signature count are not availability or receipt verification.
4. T30 still requires Celestia Mocha and Near Testnet receipts with `mock_mode=false`, provider-native inclusion evidence, distinct submitter and retrieval-observer identities, and an exact retrieved-payload hash match. No current route satisfies that release gate.

## Running Node
See `cdk-deployment/README.md` for instructions on spinning up a local CDK node.
