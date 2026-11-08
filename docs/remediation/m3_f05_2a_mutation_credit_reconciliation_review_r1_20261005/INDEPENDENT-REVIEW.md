# Independent review: mutation-credit reconciliation R1

Date: 2026-10-05
Scope: isolated bundle review only; no simulator, build, test, network, or
production/source/status-file access

## Result

**PASS.** The assessment decision is correct: the two remaining mutation rows,
`remove_key_uniqueness_order_guard` (`applied_keys_duplicate`) and
`remove_key_order_guard` (`applied_keys_unsorted`), remain PENDING. Existing R5
triads and the R10 direct-UPLC context evidence cannot promote either mutation
row. A separate mutation capture is required.

## Checksum verification

Both manifests were independently recomputed against the bytes in this bundle:

- `ASSESSMENT.SHA256SUMS`: PASS; `ASSESSMENT.md` matches
  `b138f4f73768f8724f2c574d6f8074446a5f2046c85a5ec9ca51c34840615bd2`.
- `BUNDLE.SHA256SUMS`: PASS; all seven listed bundle files match their recorded
  SHA-256 values, including the assessment manifest and all cited evidence.

## Independent comparison

R4.1 defines the applied-parameter duplicate and unsorted cases as pending
synthetic parameter-bound transaction-simulator evidence. Their contract
requires an independently rebound, condition-isolated one-guard mutant (or
equivalent reviewer-verifiable attribution) that accepts the same negative;
the contract grants no original-policy, ledger-admission, or live-network
credit. The exact two rows in `r4/tx_sim_evidence_contract_r4_1.json` retain
`status: PENDING`, `negative_case: null`, and all credit flags false.

The R5 duplicate review passes only one synthetic negative-case attribution and
states that its one-guard mutant is an attribution control with
`mutation_suite: false`. The R5 unsorted review makes the same distinction:
its positive/negative/mutant triad supports one transaction-simulator negative
case, while the reviewed mutant remains `mutation_suite: false` and the
mutation-suite count remains 18/21. These artifacts therefore do not satisfy
the distinct mutation-ledger executor/classification surface.

The R10 review independently records the only later mutation promotion as
`unconditional_success` with `direct_uplc_context_only`. It preserves the
negative cases, leaves the two named key-order mutations pending, and records
19/21 mutation PASS, 2 PENDING, 0 FAILED. Its credit scope excludes
transaction-simulator, ledger-admission, original-policy, pre-prod, and live
network evidence. That classification cannot promote either remaining row.

The assessment's resulting counts (19/21 mutations PASS, 2 PENDING; 53/55
negative PASS, 49/51 transaction-simulator negatives PASS) and its required
next evidence agree with R4.1, both R5 reviews, and R10. The stated readiness
and deployment boundaries also remain consistent with the cited evidence.

## Required evidence boundary

For each remaining guard, capture a separate mutation-suite record identifying
the exact baseline and independently rebound mutant policy/script bytes and
preserving the R4.1 synthetic-only boundary, followed by independent review.
Do not infer mutation credit from the R5 triads or R10 direct-UPLC context.

No production source, fixture registry, credentials, deployment state, or
status file was inspected or changed by this review.
