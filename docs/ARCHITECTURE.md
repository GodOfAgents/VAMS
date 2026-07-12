# VAMS Current Architecture

**Architecture version:** v0.8.0  
**Lifecycle:** Hardened pre-testnet candidate  
**Last verified:** 2026-07-12

VAMS is a dual-host, agent-oriented protocol implementation. Polygon Amoy is
the intended EVM testnet execution environment and Cardano Pre-Prod is the
intended governance, identity, and insurance environment. Neither deployment
has been evidenced in the repository; see `contracts/CONTRACTS.md`.

## Current Components

| Boundary | Implemented source | Current maturity | Economic/security role |
| --- | --- | --- | --- |
| EVM protocol | `contracts/src/` | Implemented; deployment pending | Token, staking, settlement, governance, registry, sentinel, and slashing controls. |
| Cardano validators | `cardano/validators/` | Implemented; deployment pending | Governance, timelock, insurance, agent identity, and NFT policy validation. |
| Neuron runtime | `neuron/` | Implemented with restricted live routes | Routing, SDK capabilities, DA reporting, economics, and agent execution. |
| Gateway | `gateway/server.py` | Implemented; live configuration pending | Authenticated telemetry, composition, status, and API control plane. |
| Cognitive/composer | `neuron/composer/`, `neuron/sdk/semantic_mmu.py`, `neuron/intelligence/world_model.py` | Implemented; live telemetry validation pending | CHC capability matching and controlled memory/workflow guidance. |
| Frontend | `frontend-vite/src/` | Read-only testnet profile | Displays registry and telemetry; wallet transactions are disabled. |

## Live-Route Boundary

Celestia and Near are the only default live-capable DA paths. Avail, EigenDA,
OMS identity, Trails, Coinme, TEE, bridge, interrupt, and storage integrations
must fail closed when configured as mocks in testnet or production environments.
Live deployment also requires Caddy TLS, loopback Uvicorn, DID administration,
mTLS client-certificate allowlists, and commit-bound runtime evidence.

## Testnet Profile

The first testnet profile is faucet-only. Staking rewards, real fiat, real
yield capital, and wallet transactions are disabled. Governance requires
separate 3-of-5 governance and treasury Safes, a 2-of-3 pause-only emergency
council, and a minimum 48-hour timelock.

## Invariants

The architecture is constrained by INV-1 through INV-10. Their executable
enforcement and test anchors are maintained in `docs/audit/invariant-controls.json`.
Architecture traceability proves paths exist; it does not prove deployment,
solvency, or independent assurance.
