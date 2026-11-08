# F05.2a evidence-classification amendment R3

This successor classification changes only the disposition of the original negative case ID applied_genesis_parameter, preserving its registry ID and security assertion. It is based on the exact-R5 synthetic paired evidence and independent paired review.

Evidence: R6 positive RUN 457cb0ec423477df1d232501506e713f3ce7800210635b35535abff0b2417c8e; R7 normal-policy negative RUN 651fc64426b0968828a597564b48ae4a6dbba68b0f5d516d37f28b8bc5924d7e; R9 exact-R5 remove_seed_guard mutant RUN 4ce6eebe967ac9cf44e57a30c3dac5242071c9d0b1ad944d65064f6b890f7b3b. Independent paired review: docs/remediation/m3_f05_2a_applied_genesis_paired_review_r2_20261005/INDEPENDENT-REVIEW.md with SHA-256 c65b3f61f55276c84f940becfe54ebe59f9d96f29ade8a06153c4374ed5b8731.

The normal policy byte hash and ID match R5 across R6/R7; the same applied seed, key vector, PoP signatures, and negative seed-omission semantics are retained in the mutant package. The one-guard mutant accepts at the compiled Mint[0] entrypoint. Independent review supports the single negative row as transaction-simulator evidence under a synthetic alternate applied policy.

Negative totals become 47/55 PASS and 8 PENDING. Transaction-simulator totals become 43/51 PASS and 8 PENDING. Mutation totals remain 18/21 PASS and 3 PENDING; this control does not add mutation-suite credit. No original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit is inferred. F05/M3 remains open; readiness NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
