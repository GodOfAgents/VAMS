# VAMS Current Architecture

**Architecture version:** v0.8.0  
**Lifecycle:** Hardened pre-testnet candidate  
**Last verified:** 2026-07-13

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

Celestia and Near remain candidate DA integrations, but neither current adapter
qualifies as VDSO live evidence: Near does not submit/retrieve the blob, and
Celestia can silently return a mock receipt. VDSO blocks both until a reviewed
signed-submission and exact-retrieval proof path exists. Avail, EigenDA, OMS
identity, Trails, Coinme, TEE, bridge, interrupt, and storage integrations must
also fail closed when configured as mocks in testnet or production environments.
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

## VDSO Canary Foundation

`ADR-VDSO-001` remains `Proposed`, and no VDSO component is deployed. The
repository now contains an additive, fail-closed canary foundation:

| Boundary | Implemented source | Current limit |
| --- | --- | --- |
| VIR-Core reference | `vams-vm/` | Restricted positional CBOR, bounded integer interpreter, host/epoch binding, and Rust/Python/Aiken intent vectors exist. Settlement vectors independently bind proof and payload. SP1 and RISC Zero integrations remain disabled placeholders. |
| Polygon contracts | `contracts/src/vdso/` | Object/version CAS, authority epochs, fencing, proof and capability routing, quarantine, VIR-v1 policy admission, Cardano-write rejection, and settlement separation exist. No adapter, verifier, program, or domain is activated by deployment rehearsal; upgradeable proxy adapters/verifiers are not eligible until implementation identity can be pinned. |
| Neuron and Gateway | `neuron/vdso/`, `gateway/vdso.py` | Shadow/canary intent validation, exact VIR encoding, signed capability derivation, Tier-2 hybrid authorization for every nonzero settlement-cost budget, nonce/replay controls, sidecar-root binding, ciphertext-only sidecars, and fail-closed DA routing exist. Live evidence requires separately injected receipt-verifier and blob-retriever observers that are not bound to the submitting adapter; the runtime identity guard alone does not prove operational independence, so deployment provenance remains a canary-admission review requirement. Current Near/Celestia adapters remain explicitly ineligible. Live stores, audited HPKE/ML-DSA backends, and deployment verification are still required. |
| Cardano conformance | `cardano/lib/vams/vdso.ak` | Shared intent-vector, host-wire, and proof/payload checks exist. Native Aiken conformance permits only non-economic `READ` and `ACCUMULATE`; `CONSUME` and `RESERVE` fail closed, while the Polygon kernel rejects every Cardano-authoritative write. |

These source artifacts are implementation evidence only. They are not
deployment, independent-audit, live-DA, privacy-assurance, or public-testnet
evidence.

VDSO preserves rather than replaces the dual-host architecture:

| Host | Proposed VDSO authority |
| --- | --- |
| Polygon Amoy | EVM execution, high-frequency settlement, routing, and explicitly allowlisted canary state domains. |
| Cardano Pre-Prod | Governance, identity, insurance, and native-validator state domains. |

Each state domain has exactly one authoritative writer at a time. Cross-host
proofs synchronize commitments without creating a second valid history. A
Cardano read/conformance-first rollout is staging order only; it does not demote
Cardano or transfer its assigned domains to Polygon.

The canary is designed to run beside the current Phase 6 path. Legacy routes remain
authoritative until a separately approved, independently reproduced,
domain-specific migration. Classical HPKE protects proposed witness sidecars;
it is not post-quantum confidentiality. The current code requires an injected,
reviewed RFC 9180 implementation and otherwise fails closed. Tier 2 binds the
hybrid secp256k1 plus ML-DSA-65 suite, but the Gateway deliberately blocks it
until a reviewed ML-DSA verifier is configured. Proof and settlement security
remain separate claims.
