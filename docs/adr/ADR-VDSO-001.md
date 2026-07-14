# ADR-VDSO-001: Canonical State Objects and Dual-Host Settlement

**Status:** Proposed  
**Decision owners:** VAMS governance  
**Decision date:** Not approved  
**Review baseline:** `fa5165ca82e7304e87397beac35053a9699017c7`  
**Last verified:** 2026-07-13

## Context

The VDSO discussion proposes protocol-owned state objects, deterministic
intents, explicit access modes, capability-based adapters, asynchronous
reservations, a canonical Transition VM, and cross-language conformance. These
mechanisms do not exist as a complete protocol at the review baseline. The
discussion is preserved as provenance in
[`VAMS-Discussions_001.txt`](../team/VAMS-Discussions_001.txt); it is not a
normative specification or deployment record.

VAMS already uses a dual-host architecture. Polygon Amoy is the intended EVM
execution environment. Cardano Pre-Prod is the intended governance, identity,
insurance, and native-validator environment. VDSO must harden that allocation,
not remove Cardano or make Polygon a universal constitutional host.

## Decision

VAMS will develop VDSO as a side-by-side, fail-closed canary governed by the
requirements below. This ADR authorizes specification and canary implementation
work only. It does not authorize deployment, economic migration, or a claim of
testnet readiness.

### VDSO-AUTH-001: One authoritative writer per state domain

Each state domain has exactly one authoritative writer at any instant. A host
handoff requires a governance-approved migration manifest, finalized source
checkpoint, destination reconstruction, matching state root from two
independent implementations, and an atomic authority epoch change. A receipt
from a prior authority epoch is stale. No fallback may make two hosts writable.

### VDSO-AUTH-002: Preserve Polygon–Cardano dual-host roles

| Host | Authoritative domains during the canary |
| --- | --- |
| Polygon Amoy | EVM execution, high-frequency settlement, routing, and explicitly allowlisted VDSO canary objects. |
| Cardano Pre-Prod | Governance, identity, insurance, and native-validator domains. |

Cross-host proofs synchronize commitments and settlement outcomes. They do not
transfer domain authority implicitly. Cardano's initial read/conformance phase
is a rollout order, not a reduction of its architectural role.

### VDSO-CANON-001: Canonical protocol artifacts

The canonical wire form will be deterministic CBOR restricted to schema-defined
positional arrays. Maps, floats, tags, indefinite lengths, duplicate fields,
unknown versions, and unordered object references are rejected. Consensus
identifiers use domain-separated Keccak-256:

$$
intentId = Keccak256(\text{"VAMS:INTENT:v1"} \parallel CanonicalUnsignedIntent)
$$

$$
programId = Keccak256(\text{"VAMS:PROGRAM:v1"} \parallel virVersion \parallel
bytecodeHash \parallel hostSetHash \parallel gasScheduleHash \parallel
arithmeticPolicyHash)
$$

$$
workflowId = Keccak256(\text{"VAMS:WORKFLOW:v1"} \parallel intentId \parallel
workflowDefinitionHash \parallel runtimeVersion)
$$

The consensus result cannot depend on chain ID, wall-clock time, compiler path,
debug metadata, prover version, transaction hash, or settlement block. Those
values belong in non-semantic settlement metadata.

The initial public types are `StateObjectHeader`, `ObjectRef`, `ObjectAccess`,
`UnsignedIntent`, `AuthEnvelope`, `ExecutionQuote`, `CapabilityRequirements`,
`EvidenceRef`, `EncryptedWitnessSidecar`, `Reservation`, `TransitionReceipt`,
`SettlementMetadata`, and `AdapterConfig`.

### VDSO-ACCESS-001: Explicit access and arithmetic semantics

V1 supports `READ`, `CONSUME`, `RESERVE`, and `ACCUMULATE`. Oracle objects use
`READ`; mutable pools use `CONSUME` or a separately specified batch transition;
they are never treated as non-consuming oracle references.

Consensus arithmetic uses bounded integers, schema-fixed scales, checked
overflow, and operation-declared rounding. Floats, recursion, threads, network
calls, wall-clock reads, implicit randomness, dynamic linking, and unbounded
loops are prohibited.

### VDSO-RES-001: Reservation and recovery safety

The lifecycle is:

```text
AVAILABLE -> RESERVED -> COMMITTED
                     \-> RECOVERY_PENDING -> ABORTED
```

Every reservation receives a monotonically increasing fencing token and
authority epoch. Destination execution must reject an older token, stale epoch,
wrong program, wrong object version, or mismatched output commitment. Expiry
only enters `RECOVERY_PENDING`; it never unlocks value. Abort requires an
authenticated destination abort, verified proof of non-execution, or a defined
challenge-and-compensation result. Ambiguous finality freezes the object.

Emergency pause blocks new reservations but must preserve valid commit and
recovery paths for existing reservations.

### VDSO-PRIV-001: Minimized headers and encrypted sidecars

Public headers contain commitments and pseudonymous identifiers only. Prompts,
reasoning traces, credentials, raw TEE reports, full signatures, direct
identifiers, and private object contents are forbidden.

Each sidecar uses a random data-encryption key and authenticated payload
encryption. Recipient key envelopes use an RFC 9180 X25519/HKDF-SHA256/
ChaCha20Poly1305 HPKE suite, with the header hash, schema, policy, and recipient
bound as authenticated context. This v1 confidentiality profile is classical;
it is **not** post-quantum confidentiality.

Selective disclosure uses salted, domain-separated Merkle leaves. Both the
plaintext witness root and ciphertext hash are committed. Deletion means
retention enforcement and cryptographic key erasure; immutable DA ciphertext is
not described as erased. Plaintext sensitive data is prohibited from logs,
telemetry, and public evidence.

### VDSO-PQ-001: Hybrid Tier 2 authorization without blanket claims

Tier 2 value, governance, reservation, insurance, and treasury intents require
both secp256k1 and ML-DSA-65 authorization. The signature-suite identifier is
inside the signed intent. Missing, invalid, or downgraded signatures fail
closed. Tier 0 and Tier 1 may use classical authorization under versioned
policy while remaining crypto-agile.

Every route reports three independent classifications:

- `authorizationSecurity`;
- `proofSecurity`;
- `settlementSecurity`.

A route is never called post-quantum secure unless all three are post-quantum
under the selected modes. SP1 or RISC Zero use alone does not satisfy this
condition; any elliptic-curve compression/wrapper is labeled non-PQ.

### VDSO-ADAPTER-001: Capability and conformance gating

Adapter activation requires supported protocol versions, code hash, verifier
identity, capability profile, conformance-corpus root, expiry, and governance
approval through the existing Safe/timelock controls. Emergency governance may
quarantine an adapter immediately but cannot silently reactivate it.

Routing filters mandatory security, privacy, finality, and fencing
capabilities before deterministic cost/latency selection. It fails closed when
no adapter qualifies and never downgrades a requirement. An adapter without
destination fencing and verified non-execution cannot advertise value-bearing
`RESERVE`.

Avail, EigenDA, mock OMS, mock Trails, mock TEE, mock encrypted ordering, and
other stub/mock paths are ineligible for live VDSO evidence. Only independently
verified Celestia or Near routes may become live-capable during the canary.

### VDSO-EVID-001: Typed evidence and proof separation

Evidence acquisition occurs outside deterministic execution. The kernel accepts
only typed, fresh, subject-bound, revocation-aware evidence receipts whose
verifier and policy are explicit. Boolean OMS responses and structurally valid
mock TEE quotes are not evidence receipts.

Semantic transition commitments remain structurally separate from bridge proof,
payload hash, chain transaction data, and settlement metadata, preserving
INV-10.

The pre-deployment settlement envelope is versioned independently as
`vdso-settlement-v2`. It binds explicit `sourceHost` and `destinationHost`
fields; `destinationHost` must match the domain authority binding. Cross-host
settlement requires unequal non-null hosts, a nonzero source-chain reference,
source transaction, finalized height, bridge-proof hash, and payload hash, with
`bridgeProofHash != payloadHash`. Same-host metadata requires equal hosts and an
all-zero settlement tuple. Version 1 settlement envelopes fail closed.

### VDSO-ROLL-001: Parallel canary and promotion

Rollout order is `off -> shadow -> canary -> authoritative`, independently per
state domain. Shadow mode performs no canonical write or capital movement.
Legacy Phase 6 routes remain authoritative until a separately approved domain
cutover.

Value cannot enter the canary until at least $1 \times 10^5$ shadow transitions
run over seven continuous days with zero semantic divergence. Authoritative
promotion requires a further 30-day closed economic canary, two independent
execution backends, privacy and cryptography review, exact-commit invariant and
conformance evidence, governance approval, and a rehearsed rollback.

Rollback pauses new VDSO reservations and returns new writes to the last
reconciled authority checkpoint. Existing reservations must commit or use the
authenticated recovery path; rollback never abandons or automatically unlocks
them.

## Invariant Impact

| Invariant | ADR requirement |
| --- | --- |
| INV-1, INV-2, INV-8, INV-9 | VDSO delegates emissions, insurance, supply, and solvency enforcement to existing authoritative controls; it does not duplicate or weaken them. |
| INV-3, INV-4 | Intent authorization cannot extend session expiry or bypass the core-contract whitelist. |
| INV-5 | Institutional routes require typed, fail-closed OMS evidence; Boolean/mock evidence is rejected. |
| INV-6 | TEE evidence binds the root EOA and cannot substitute a session key. |
| INV-7 | Oracle `READ` objects include freshness policy and reject stale evidence. |
| INV-10 | Transition semantics, bridge proof, payload hash, and settlement metadata remain distinct typed fields. |

## Rejected Alternatives

- A universal Polygon authority: rejects the established dual-host allocation.
- Multiple simultaneous writers for one domain: creates conflicting canonical
  histories and cross-host double-spend risk.
- Automatic timeout unlock: unsafe under delayed destination finality.
- A Boolean privacy capability: cannot express actual confidentiality or
  disclosure guarantees.
- Blanket “post-quantum VDSO” wording: conflates authorization, proof, and
  settlement assumptions.
- Replacing current routes in place: creates an unrecoverable Phase 6 migration
  boundary before the protocol is verified.

## Acceptance Consequences

This ADR remains `Proposed` until its evidence manifest and documentation gate
pass. It may become `Accepted for Canary` only after the runtime, contracts,
Cardano adapter, conformance vectors, independent reviews, and rollout controls
exist and pass exact-commit gates. A later governance ADR is required for any
authoritative state-domain migration.
