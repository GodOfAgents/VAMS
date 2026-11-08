# F05.2a evidence-classification amendment R2

This successor classification changes only the evidence disposition for the original negative case ID applied_keys_duplicate. The original registry and security assertion are unchanged.

The accepted evidence is a paired local synthetic transaction-simulator triad under R5: a positive control accepted at Mint[0], the duplicate-key negative rejected during compiled evaluation at Mint[0], and the one-guard mutant (removing only the strict-order comparison) accepted at Mint[0]. Independent review in docs/remediation/m3_f05_2a_applied_keys_duplicate_review_r1_20261005/INDEPENDENT-REVIEW.md concludes this supports the applied_keys_duplicate negative row.

Evidence identities: R5 family manifest 3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e; positive attempt RUN 2207fae0ad8c50de5de7869753eb0e2f58b17580faa32898193e44e7b199362b; negative attempt RUN c9f8291509a2bbf24ac4ca18dfb241203c5f8aa1c276fd7eed1bdfb637ca2799; mutant attempt RUN bb27d89cbdc38f11ff6b116393602f3613ba1306486ee307f3c028ce15f976dd; paired review SHA-256 1ee2dc4e2d5cb2bcbf5005068e5ccf96a60f9b70a115b8edafab65ab9630ce86.

The case is classified as transaction_simulator evidence for a synthetic alternate-applied-policy entrypoint only. This classification does not establish the original applied policy, full ledger admission, Cardano Pre-Prod behavior, or live-network behavior. No mutation-suite credit is added. Negative ledger totals move from 45/55 to 46/55 PASS; 9 remain pending. Mutation totals remain 18/21 PASS and 3 pending.

Review captures are local self-records without retained raw simulator stdout/stderr or external attestation. This amendment does not alter any registry ID, assertion, frozen contract, source, or deployment gate.
