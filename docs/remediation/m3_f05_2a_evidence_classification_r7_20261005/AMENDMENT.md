# F05.2a evidence-classification amendment R7

Disposition: awaiting independent review. This successor to R6 changes only r2_signature_for_other_network from pending to synthetic transaction-simulator pass. It preserves the original case ID and assertion sign_tuple_with_another_network_magic, the frozen source registry, every other negative row and every mutation row.

## Exact evidence

R20 accepted positive RUN: docs/remediation/m3_f05_2a_proof_other_network_positive_attempt_r1_20261005/RUN.json (SHA-256 f83f9efb074e5b7396d395a61154adc8d716b57a3a4193119b46e03d3e531e8a). R20 independent review: docs/remediation/m3_f05_2a_proof_other_network_positive_review_r1_20261005/INDEPENDENT-REVIEW.md (SHA-256 a86e5fe5594048f9bff65f92a4dcf6f124dfe25063578d1aeeaf21a933f6c6ff).

R21 unmodified-policy negative RUN: docs/remediation/m3_f05_2a_proof_other_network_negative_attempt_r1_20261005/RUN.json (SHA-256 e31385db7d8c0e0b7ebc4610298813ed66373a59a736109d354db4addc9ec179). It rejected at compiled Mint[0] with generic compiled_evaluation only; the R21 review correctly withheld named-condition credit.

R22 same-negative one-guard mutant RUN: docs/remediation/m3_f05_2a_proof_other_network_mutant_attempt_r1_20261005/RUN.json (SHA-256 364d859090a4d80549a63bb57b04b0f36d1d89b967cc5707e3dc784c79315eaa). Independent pre-execution mutant review: docs/remediation/m3_f05_2a_proof_other_network_mutant_preexecution_review_r1_20261005/INDEPENDENT-REVIEW.md (SHA-256 1d92f77fcd16b90c19ebb1330f46aa7175eea84b74e635f89120b7a0cf07b6f7). Integrated triad review PASS: docs/remediation/m3_f05_2a_proof_other_network_triad_review_r1_20261005/INDEPENDENT-REVIEW.md (SHA-256 df63119b2896ee637d2c7bfff8fe99c0204763643f4170bbf0e7f8ef4b478895).

The reviewed R20/R21/R22 evidence supports exactly the preserved negative row at synthetic local transaction-simulator scope. The mutant changes only the expected network-magic constant in a test copy, reuses R21 proof bytes, and rebinds its own policy, mint and V3 witness. R22 is attribution evidence only and adds no mutation-suite credit.

## Scope and limits

Synthetic test-only alternate applied policy; ephemeral keys only. No original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. Structured local runner records are retained; raw simulator stdout/stderr and external attestation are unavailable.

Proposed counts: negative cases 51/55 pass, 4 pending, 0 failed; transaction-simulator 47/51 pass, 4 pending, 0 failed. Context-only and routing-only counts are unchanged. Mutation suite remains 18/21 pass, 3 pending, 0 failed.

F05/M3 remains open; readiness is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
