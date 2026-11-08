# M3.2a-R13 oracle-defect remediation

Date: 2026-09-27
Scope: remediation of R12 independent-oracle defects only. No M3.2b implementation and no frozen R7 artifact, Cardano source, lockfile, dependency, credential, deployment, vendor or Git-history change.

## R12 baseline

The R12 package at /home/GodOfAgents/vams-evidence/m3-2a-r12-review-20260926-829ab544571f was verified before editing. Its SHA256SUMS digest is d62015e901856555ded633320dd60dc333eb5ed0dbe336b1308bff008528f7be. R12 reported malformed snapshot acceptance, unbounded arithmetic, authority-reference drift, raw TypeError leakage, noncanonical target whitespace, unmodelled reserve destinations and datum-structure coverage gaps.

## Remediation

address_value_oracle.py now:
- requires an exact versioned snapshot schema, closed keys, strict network/freshness arguments, duplicate-key rejection, bounded numeric fields and sanitized nonzero CLI failures;
- exposes strict_u8/strict_u32/strict_u64 plus checked add, subtract and multiply helpers; validates all value, reserve, quorum, weight, lifecycle, snapshot and topology inputs before arithmetic;
- rejects authority-reference count drift and validates both flattened and frozen nested topology records with closed field equality;
- validates canonical lower-case target encodings against the frozen allowlist and rejects whitespace/control/length/prefix mutations;
- adds closed OutputRecord and reserve-destination validation for voter, proposer and authority continuation outputs;
- adds InlineDatum schema, ordered fields, strict widths/types, constructor and exact frozen-vector byte/size checks for AuthorityDatumV1, ProposalDatumV1, VoteLockRecordV1 and IntentDatumV1;
- keeps the public CLI bounded and traceback-free.

The independent test module now covers every R12 finding, exact numeric boundaries, all frozen topology rows and field mutations, concrete destination mutations, canonical datum mutations, malformed public entry points and sanitized snapshot CLI behavior. Tests use literal schema expectations and frozen JSON fixtures; they do not import production generators or calculate expected results from the implementation.

## Fresh verification

- focused oracle suite: 9/9 passed;
- Python compilation: passed;
- snapshot matrix: malformed, stale, wrong-network, unknown-key, duplicate-key and overflow inputs returned sanitized JSON with exit 1; valid canonical snapshot returned exit 0;
- R12 overflow, authority-reference, whitespace and malformed-container probes now raise OracleError;
- frozen R7 JSON parsing: passed;
- R12 evidence package verification: passed;
- Cardano/provenance continuity checks remain required after integration.

F01-F05 remain open, Deposit remains disabled, M3 remains OPEN, Pre-Prod admission is INCONCLUSIVE, promotion is NOT READY, and M3.2b is not authorized. This is local remediation only; the next slice is independent M3.2a-R14 oracle delta review.

## Invariant and mock impact

INV-1 through INV-10 are unchanged and preserved. The change is design-only oracle evidence and does not alter production validators, economic contracts, Gateway/M1/M2 behavior, mock-mode policy, deployment state or credentials.

