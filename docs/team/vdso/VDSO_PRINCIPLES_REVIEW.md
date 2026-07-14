# VDSO Principles Review

**Status:** Evidence-hardened design review; not deployment approval  
**Baseline commit:** `fa5165ca82e7304e87397beac35053a9699017c7`  
**Source:** [`VAMS-Discussions_001.txt`](../VAMS-Discussions_001.txt)  
**Source SHA-256:**
`EEF1973EA47F5E5D58F2A8EDB45A851E0CF684C2F6FB2F7D7D27BB8643165635`  
**Source size:** 66,551 bytes; 1,992 lines; untracked at review time  
**Structured evidence:**
[`vdso-review-evidence.json`](../../audit/evidence/vdso-review-evidence.json)  
**Last verified:** 2026-07-13

## Verdict

| Question | Answer | Reason |
| --- | --- | --- |
| Is VDSO materially better than current HEAD? | **Conditional Yes** | Protocol-owned objects, explicit access modes, deterministic receipts, conformance vectors, and fenced reservations are meaningful improvements if implemented. |
| Is the discussion safe to adopt unchanged? | **No** | It demotes Cardano, mixes target design with repository fact, leaves privacy and recovery underspecified, and overstates prover post-quantum properties. |
| Is VDSO deployed or testnet-ready? | **No** | The discussion itself states that VDSO, reservations, capability-root adapters, and the Transition VM do not exist (lines 1427–1429). |

The original review's “strongly positive on 6, adequate on 1, gap on 1” claim did
not match its own scorecard. It also treated a proposed repository layout as
present code, described governance-gated adapters as universally eligible,
claimed there was no threat model, and applied a blanket post-quantum label to
STARK-based products without distinguishing their compressed proof modes.

## Dual-Host Correction

The discussion proposes one universal Polygon canonical host at lines 508–539
and removes Cardano's governance, identity, and canonical-state role at lines
651–657. That proposal is rejected.

VDSO must preserve the existing dual-host allocation documented in
[`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md): Polygon Amoy remains the EVM
execution, high-frequency settlement, routing, and canary host; Cardano
Pre-Prod remains the governance, identity, insurance, and native-validator
host. Exactly one host may be the authoritative writer for a particular state
domain at a time. Cross-host proofs synchronize commitments; they never create
two valid histories for one domain.

## Principle Findings

### 1. Sovereignty — target adequate; current weak

The statement “VAMS defines the state machine” at discussion lines 798–804 is a
sound direction, and a compiler/prover-independent `programId` at lines
1933–1961 reduces backend lock-in. The universal-Polygon passages at lines
508–539 and 651–657 would instead replace one constitutional dependency with
another.

Current routing remains a fixed `ChainId` enum and rule tree in
[`VAMSRouter.sol`](../../../contracts/src/routing/VAMSRouter.sol), lines 30–38
and 266–303. The target is therefore `design_only`, not implemented.

**High gap:** define state-domain ownership, migration proofs, exit procedures,
and a governance-controlled handoff that can never authorize two writers.

### 2. Privacy — target partial; current mock-dependent

The compact header and witness sidecar proposal at discussion lines 1126–1176
reduces replication, and compact evidence receipts at lines 1781–1818 can
support disclosure minimization. It does not specify encryption envelopes,
recipient binding, retention, revocation, metadata leakage, or log policy.

Current encrypted ordering is explicitly guarded as mock encryption in
[`mev_protection.py`](../../../neuron/mev_protection.py), lines 145–158. OMS
defaults to mock mode and returns a Boolean in
[`oms_identity.py`](../../../neuron/sdk/oms_identity.py), lines 29–68. The TEE
plugin constructs a placeholder quote and performs structural verification in
[`tee_plugin.py`](../../../neuron/trust_plugins/tee_plugin.py), lines 101–158.

**High gap:** encrypt sidecars with per-object data keys and recipient-bound
classical HPKE envelopes; commit selective-disclosure roots; prohibit plaintext
prompts, credentials, reasoning traces, and quotes from public headers and
telemetry. Classical HPKE is not a post-quantum confidentiality claim.

### 3. Security — target adequate; current partial

Fencing tokens and the rule that expiry never unlocks value, at discussion
lines 1725–1777, are the correct basis for asynchronous safety. They remain an
unimplemented design and do not yet define proof-of-non-execution, challenge,
or compensation verification.

The existing [`RoutingProofVerifier.sol`](../../../contracts/src/routing/RoutingProofVerifier.sol),
lines 48–76, recovers an authorized ECDSA signer and explicitly calls the
signature a v1 mock for ZK. VAMS does have a repository threat model at
[`docs/audit/THREAT_MODEL.md`](../../audit/THREAT_MODEL.md); the missing artifact
was a VDSO-specific extension, not a threat model for the whole project.

**Critical gap:** no value-bearing reservation may enter canary operation until
destination fencing, proof/program binding, authenticated abort, replay
protection, and ambiguous-finality freeze are executable and adversarially
tested.

### 4. Modularity — target strong; current contradicted

The native/proof-verifying adapter split and mandatory conformance corpus at
discussion lines 1180–1253, plus the MLIR → VIR-Core → backend separation at
lines 1465–1496, form a coherent modular target. The directory tree at lines
661–698 is a recommendation, not an inventory of existing code.

Current `VAMSRouter` chooses named chains through a compiled rule tree. No
VDSO adapter interface, canonical VIR-Core interpreter, or cross-language
corpus existed at the review baseline.

**High gap:** adapters require versioned capabilities, code/verifier hashes,
conformance roots, expiry, governance activation, and fail-closed rejection of
unsupported or downgraded semantics.

### 5. Post-quantum readiness — target adequate; current gap

Explicit cryptographic opcodes at discussion lines 1584–1600 make algorithm
migration possible, but `secp256k1` is not post-quantum. “STARK-based” also does
not prove every user-facing proof mode post-quantum: SP1 and RISC Zero both
document modes that rely on elliptic-curve SNARK assumptions. See the
[SP1 security model](https://docs.succinct.xyz/docs/sp1/security/security-model)
and [RISC Zero security model](https://dev.risczero.com/api/security-model).

Tier 2 authorization must require both secp256k1 and ML-DSA-65, with the suite
identifier bound into the intent and either failure rejecting execution.
ML-DSA naming and parameters follow
[NIST FIPS 204](https://csrc.nist.gov/pubs/fips/204/final). Authorization,
execution-proof, and settlement security must be reported separately.

**High gap:** the current routing proof is ECDSA-only, and neither hybrid intent
authorization nor downgrade protection exists at the review baseline.

### 6. Equality — target adequate; current weak

Canonical intents and deterministic conflict handling can give participants the
same published rules. The prior review's claim that any conformant adapter is
eligible omitted the governance enablement requirement at discussion lines
1239–1253. Governance approval is a legitimate safety gate, but it creates a
measurable capture surface.

Current routing can use operator-only decisions and global/manual overrides in
`VAMSRouter.sol`, lines 132–173. That is not evidence of permissionless or
privilege-free routing.

**Medium gap:** publish adapter eligibility, deterministic tie-breaking,
quarantine reasons, appeal/exit paths, and governance/operator concentration
metrics. Do not equate equal rules with guaranteed equal outcomes.

### 7. Decentralisation — target partial; current weak

Multiple proof backends and replaceable settlement adapters can reduce vendor
concentration. The source nevertheless selects one Polygon canonical authority
and does not specify operator membership, prover quorum, governance capture
limits, or recovery relayer decentralisation.

The corrected architecture uses one authoritative writer **per state domain**,
not one universal host. Cardano retains its governance, identity, insurance,
and validator authority. This avoids split-brain without collapsing the
dual-host architecture.

**High gap:** require independent execution backends, published concentration
telemetry, tested host migration, and cross-host proof rules before any domain
becomes authoritative under VDSO.

### 8. Safety — target adequate; current partial

Fail-closed transitions, bounded quotes, stale-input rejection, fencing, and
explicit recovery are strong design elements. They do not replace the existing
VAMS safety controls: `VAMSEmergencyPausable`, `VAMSSentinel`, and
`SLAEnforcer` already exist outside VDSO. The actual gap is their VDSO-specific
integration.

**Critical gap:** define whether pause blocks new reservations while preserving
commit/recovery, map every transition to INV-1 through INV-10, and test
split-brain, stale evidence, proof disagreement, DA outage, duplicate effects,
and rollback without automatic unlock.

## Required ADR Corrections

[`ADR-VDSO-001`](../../adr/ADR-VDSO-001.md) is deliberately `Proposed` and
adopts these corrections:

1. preserve the Polygon–Cardano dual-host allocation;
2. enforce one authoritative writer per state domain;
3. treat the discussion as design input, not implementation evidence;
4. use deterministic canonical encoding and domain-separated identifiers;
5. keep headers free of sensitive plaintext and use classical encrypted
   sidecars with selective disclosure;
6. require hybrid authorization only for Tier 2 while reporting proof and
   settlement security separately;
7. prohibit automatic reservation unlock and semantic security downgrade;
8. run VDSO beside the existing Phase 6 path in shadow/canary mode;
9. require exact-commit conformance, invariant, privacy, cryptography, and
   recovery evidence before promotion.

The review therefore supports continued implementation work, but it is not an
approval to deploy, migrate canonical state, enable value-bearing reservations,
or describe VDSO as operational.
