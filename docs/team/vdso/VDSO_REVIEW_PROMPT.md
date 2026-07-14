# VDSO Principle Review Prompt

**Status:** Approved review specification  
**Review mode:** Read-only evidence collection  
**Comparison baseline:** Repository `main` at
`fa5165ca82e7304e87397beac35053a9699017c7`  
**Source:** `docs/team/VAMS-Discussions_001.txt`  
**Source SHA-256:**
`EEF1973EA47F5E5D58F2A8EDB45A851E0CF684C2F6FB2F7D7D27BB8643165635`  
**Source size:** 66,551 bytes; 1,992 lines  
**Source state at review:** Untracked; preserved byte-for-byte  
**Last verified:** 2026-07-13

## Objective

Audit the proposed VAMS Deterministic State-Object Model (VDSO) against the
current repository and determine two different questions:

1. Does the proposed design materially improve the current implementation?
2. Is the proposal sufficiently specified and evidenced for adoption or
   deployment?

The answers must remain separate. A design can improve the baseline while
still being unsafe to adopt or deploy.

## Non-Negotiable Architecture Boundary

The review must preserve the Polygon–Cardano dual-host architecture:

- Polygon Amoy is the intended EVM execution, high-frequency settlement,
  routing, and VDSO canary host.
- Cardano Pre-Prod is the intended governance, identity, insurance, and
  native-validator host.
- Each state domain has exactly one authoritative writer at any instant.
- Cross-host commitments synchronize state without creating two authoritative
  histories for the same domain.

Any discussion passage that makes Polygon the universal canonical host or
removes Cardano's assigned authority is a proposal to reject, not a repository
fact.

## Operational Definitions

Evaluate each principle using these definitions:

| Principle | Required evidence |
| --- | --- |
| Sovereignty | Protocol-owned semantics, portable state, documented exit and migration, and no permanent chain or vendor lock-in. |
| Privacy | Data minimization, recipient-bound encryption, selective disclosure, retention controls, metadata analysis, and no plaintext sensitive telemetry. |
| Security | Authorization, replay resistance, proof/program binding, deterministic recovery, fail-closed behavior, and explicit trust assumptions. |
| Modularity | Versioned interfaces, replaceable implementations, conformance vectors, capability negotiation, and no silent semantic downgrade. |
| Post-quantum readiness | Separate classifications for authorization, execution proof, and settlement; named standardized algorithms; downgrade protection; no blanket post-quantum claim. |
| Equality | Published eligibility rules and deterministic selection without undocumented privileged fast lanes; equality does not imply identical outcomes. |
| Decentralisation | Measurable governance, operator, prover, and host concentration limits plus credible exit paths. |
| Safety | Bounded deterministic execution, fencing, pause and recovery controls, stale-state rejection, and protection of INV-1 through INV-10. |

## Evidence Rules

1. Treat the discussion as a non-normative design input, not implementation
   evidence.
2. Cite claim-level discussion line ranges and repository file/line ranges.
3. Use `not_found` or `contradicted` when evidence is absent; never manufacture
   a reference quota.
4. Distinguish these maturity values exactly:
   `implemented_verified`, `implemented_unverified`, `partial`, `mock`,
   `stub`, `design_only`, `not_found`, and `contradicted`.
5. Give every gap one severity: `Critical`, `High`, `Medium`, `Low`, or
   `Informational`.
6. Map every finding to the affected VAMS invariants, or use an empty invariant
   list when none applies.
7. Validate cryptographic claims from primary specifications and vendor
   security models. A STARK-based design is not evidence that every compressed
   or on-chain proof mode is post-quantum secure.
8. Record mock/default behavior for DA, OMS, Trails, TEE, encrypted ordering,
   bridge, and storage paths.
9. Do not change source, run deployments, or promote an ADR while performing
   this review.

## Required Output

Produce:

- a provenance block containing commit, dirty state, source path, hash, size,
  and line count;
- one evidence finding for each of the eight principles;
- separate target-design and current-implementation assessments;
- repository and primary external evidence for each material claim;
- gap severity, remediation, affected invariants, ADR requirement IDs, and a
  verification gate;
- explicit trust-boundary and privacy-metadata analysis;
- separate verdicts for baseline improvement, adoption readiness, and
  deployment readiness;
- a machine-readable manifest conforming to
  `docs/audit/schemas/vdso-review-evidence.schema.json`.

## Acceptance Gates

The review passes only when:

- all eight principles occur exactly once in the evidence manifest;
- every repository citation resolves and its line range exists;
- source hash, byte length, and line count reproduce;
- design-only features are not labeled implemented;
- the Polygon–Cardano dual-host authority rule is explicit;
- classical HPKE is not described as post-quantum confidentiality;
- Tier 2 hybrid authorization requires both classical and ML-DSA signatures;
- SP1/RISC Zero proof modes are classified by their actual security model;
- INV-1 through INV-10 are considered without redefining their enforcement;
- the final answer can be `Conditional Yes` for architectural improvement while
  remaining `No` for deployment.

The canonical result of this prompt is
`docs/team/vdso/VDSO_PRINCIPLES_REVIEW.md`; the corresponding structured
evidence is `docs/audit/evidence/vdso-review-evidence.json`.
