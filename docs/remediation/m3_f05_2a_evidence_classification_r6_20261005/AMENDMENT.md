# F05.2a evidence-classification amendment R6

**Disposition: awaiting independent review.** This successor to R5 changes only the negative case r2_signature_for_other_seed from pending to synthetic transaction-simulator pass. It preserves the original case ID and assertion sign_same_tuple_with_alternate_seed, the frozen source registry, every other negative row, and every mutation row.

## Exact evidence

- R17 accepted positive control: docs/remediation/m3_f05_2a_proof_other_seed_positive_attempt_r1_20261005/RUN.json (SHA-256 f9a86dca6d7fed12a92fb2afb59ac77836c6b963b178403f0ef77b8c9494992f).
- R18 wrong-seed negative under the unmodified applied policy: docs/remediation/m3_f05_2a_proof_other_seed_negative_attempt_r1_20261005/RUN.json (SHA-256 2f3d042cd4350d821b0ce91dafa4cddfdb36dc23258eefb6115b947fd764b0be).
- R19 one-guard seed-domain mutant control: docs/remediation/m3_f05_2a_proof_other_seed_mutant_attempt_r1_20261005/RUN.json (SHA-256 ecd352f4acfb379b36a05ab623f8a25a6d5e6a8be4f9181de92cba37f3c973ba).
- Independent integrated triad review: docs/remediation/m3_f05_2a_proof_other_seed_triad_review_r1_20261005/INDEPENDENT-REVIEW.md (SHA-256 997d6658265add2675332e2759a578b59eee0b0dbdfa96f6233ea510217566ee).

The review verified exact applied/mint/V3 binding, 5/5 valid PoPs, 2/2 final-body-bound ephemeral funding witnesses, identical negative proof bytes across R18/R19, value conservation, compiled Mint[0] behavior, and clean cleanup. R17 accepts the correct applied-seed proof. R18 rejects the alternate-seed proof at compiled Mint[0] under the unmodified test policy. R19 accepts the same negative proof bytes after a single seed-domain argument mutation, with the mutant policy, mint, and V3 witness rebound. This supports only the preserved negative-case row at synthetic local transaction-simulator scope. R19 is attribution evidence only and adds no mutation-suite credit.

## Scope and limits

Synthetic test-only alternate applied policy; ephemeral keys only. No original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. Local structured simulator records are retained; raw simulator stdout/stderr and external attestation are unavailable. No broader evidence is inferred.

Proposed counts: negative cases 50/55 pass, 5 pending, 0 failed; transaction-simulator 46/51 pass, 5 pending, 0 failed. Context-only and routing-only counts are unchanged. Mutation suite remains 18/21 pass, 3 pending, 0 failed.

F05/M3 remains open; readiness is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
