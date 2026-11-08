# F05.2a evidence-contract amendment R4.1 - 2026-10-05

Status: corrected successor to R4 after independent review found positive-control and attribution gaps. Independent review is required before fixture generation or execution.

Owner choices remain C for all six applied-parameter cases and B for all four proof-domain cases. R4.1 embeds and preserves the original R2 rows and supersedes the unaccepted R4 draft without changing any case ID, security assertion, expected rejection, or target.

Every accepted positive control, negative transaction, and mutant-control transaction must independently bind its own mint policy ID to its own compiled applied Plutus V3 policy ID and witness script hash. Review the exact params, compiled bytes, transaction and raw vectors, funding signatures bound to the final body, and conservation before running the simulator.

For applied-parameter cases, positive controls correct only the named invalid condition and use a newly compiled and rebound policy/transaction. They validate the parameterized compile and transaction path; they do not themselves prove the malformed-parameter negative. Duplicate and unsorted cases require a same-negative one-guard mutant, separately compiled and rebound, to accept. For bad-count and bad-length, do not rely on an impossible one-guard-mutant acceptance: the remaining count predicate and Ed25519 verification can independently reject. Require a reviewer-verifiable first-failure trace/source map or equivalent evidence tied to the exact unmodified compiled bytes and Mint[0] input. If this attribution is unavailable or ambiguous, keep the row PENDING. Other cases require equivalent first-failure attribution or a correctly rebound accepting one-guard mutant.

Proof-domain controls use ephemeral test keys and sign the exact parameter-bound message. No original committee or wallet credentials may be accessed, exported, derived, or persisted. No fixture receives credit without execution and independent review.

The ten cases remain PENDING. Synthetic parameter-bound transaction-simulator evidence grants no exact original-policy, full ledger-admission, or live-network credit. Accepted totals stay 45/55 negative cases and 18/21 mutations. F05/M3 remain open, readiness NOT READY, and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Contract: docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json.
