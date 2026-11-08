# F05.2a evidence-classification amendment R5

**Disposition: awaiting independent review.** This successor changes only the original negative case applied_keys_unsorted from pending to transaction-simulator pass. The original case ID and security assertion compile_with_unsorted_keys_and_matching_datum are preserved, as are the frozen registry ID/hash, every other negative-case row and all mutation entries.

## Exact evidence

- R14 positive-control RUN: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r14_20261005/RUN.json, SHA-256 9d40df445cca42f37aab07bb221cc54535b95d70d79e6c64a236def6c2ea6aa1.
- R14 independent positive review: docs/remediation/m3_f05_2a_applied_keys_unsorted_r14_review_r1_20261005/INDEPENDENT-REVIEW.md, SHA-256 f08ac5add7f4096054d994ed3a1977663cf4c88096b8a5fdd295e086e09c450e.
- R15 normal-policy negative RUN: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r15_20261005/RUN.json, SHA-256 2943e4d762012bb8e617255d7c54102596456fa6da3b25b841896a05554790c3.
- R15 independent one-guard mutant-byte review: docs/remediation/m3_f05_2a_applied_keys_unsorted_r15_mutant_byte_review_r1_20261005/INDEPENDENT-REVIEW.md, SHA-256 c17eecfb046a1f744b9193e2305fc9383a6fd8f077720eeb4e629509fd965aa1.
- R16 one-guard mutant RUN: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r16_20261005/RUN.json, SHA-256 11ff6ab03cac0dc488af7cc486bb994bf79fd1d0fb49ee4dff8ae619ff37fd24.
- R16 independent paired triad review: docs/remediation/m3_f05_2a_applied_keys_unsorted_r16_review_r1_20261005/INDEPENDENT-REVIEW.md, SHA-256 9f3b58dc98ee5144705db7f4101181904a93166d7d6b3e5730688e922216e54b.

The independent triad review pairs the accepted R14 positive control, R15 production-policy compiled Mint[0] rejection, and R16 acceptance under the exact reviewed one-guard ordering mutant. It supports attribution to the named unsorted-key order condition within local transaction-simulator evidence scope.

## Scope and limits

This evidence is limited to a synthetic alternate applied policy. It grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. The R16 mutant is an attribution control and adds no mutation-suite credit. Captures are local structured runner records; raw simulator stdout/stderr and external attestation are unavailable. This overlay itself has not received independent review and remains proposed until that review passes.

Proposed counts: negative cases 49/55 pass, 6 pending, 0 failed; transaction-simulator 45/51 pass, 6 pending, 0 failed. Context-only and routing-only totals are unchanged. Mutation-suite results remain 18/21 pass, 3 pending, 0 failed.

F05/M3 remains open; readiness is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
