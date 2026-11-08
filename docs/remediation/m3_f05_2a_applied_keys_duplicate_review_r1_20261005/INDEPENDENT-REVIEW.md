# Independent paired-control review: applied_keys_duplicate

**Review result: PASS for duplicate-key negative-case attribution only.** This is an independent review of the immutable R5 package and three paired execution records. No fixture was rerun, and this review does not write or promote any case ledger, status, or handoff entry.

## Bound evidence

R5 applied-parameter family:

- Family manifest SHA-256: `3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e`
- Root `SHA256SUMS` SHA-256: `ad27af4dd49aac3e8d0ba570468adf5c4fc32e02b5acc3303b2f40b67e5c71f0`
- `applied_keys_duplicate/FIXTURE-MANIFEST.json` SHA-256: `7c7d3c779ef452df3fd808d1e0465c9eeef855058dfa5c3f5ce961b4b4536caa`

Attempt captures:

| Attempt | RUN.json SHA-256 | SHA256SUMS SHA-256 |
| --- | --- | --- |
| Accepted positive control, R3 | `2207fae0ad8c50de5de7869753eb0e2f58b17580faa32898193e44e7b199362b` | `236a5f6b2a242d1592c5c18e04004d935642bd929d7f06108be20c227699d598` |
| Duplicate-key negative, R4 | `c9f8291509a2bbf24ac4ca18dfb241203c5f8aa1c276fd7eed1bdfb637ca2799` | `c0b9f6b751a22d91288f2c41d276d7dddc49a1c025d8428528a2c9a45deb582a` |
| One-guard mutant control, R5 | `bb27d89cbdc38f11ff6b116393602f3613ba1306486ee307f3c028ce15f976dd` | `552a9f5944ad119d46218743ddb3487cf7c80ed97d27c9125e0aea3b0aff59df` |

The negative transaction/input/output hashes are respectively `4e538bf83ddef70b48c7d3536a8f3ea1daac7151f2f8534667ff541c9f8a52ac`, `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe`, and `b46446ed205485e9831b6cf6111350620368f5e8dd3b1b6d03cec2ae02fbd0e4`. The mutant-control hashes are `dc7e2ed5088a7d7d10e03c116f408ca99f0324de2f412c40414ba4fe00d257b9`, the same raw-input hash `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe`, and raw-output hash `ff6527fab75c8c2e175dbc2a4391de063b841a3f2d52d2773d06359467cecbf7`. All recorded sizes match the package files. The two attempt records cross-reference one another's hash and the same R5 family/case manifests.

The attempt records identify Aiken `v1.1.21+42babe5`, binary SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`, and immutable runner SHA-256 `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c`. The mutant record's applied policy ID is `1b8e1c1bbc466063dc2602bf2696ec4a4e6cd2f2e6048c2376e5afd5`; the negative's is `d1f886d981117ada5f4e92370e1921c1c3616ce37b558b3fc42b65b9`. Each attempt records that its minted policy ID and compiled V3 witness hash equal the supplied policy ID.

## Attribution finding

The R5 case manifest preserves the original `applied_keys_duplicate` assertion: compile with duplicate keys and a matching datum. Its negative fixture uses duplicated first and second keys, with matching datum state and proofs recorded as valid for the applied parameter. The immutable source predicate `valid_ordered_keys` requires strict increase at each adjacent pair.

The disposable mutant changes only the first comparison, `bytearray.to_int_big_endian(first) < bytearray.to_int_big_endian(second)`, to `True`. The source mutation routine uses a single exact-once replacement for that predicate. The negative record reports compiled evaluation at Mint[0] with child exit 1 and wrapper exit 0. The mutant record reports `script_accepted` at Mint[0] with child and wrapper exit 0. Both report clean child/process-group/snapshot cleanup. This differential supports attribution of the negative rejection to the duplicate first pair's strict-order guard. The separately captured R5 positive control was also accepted at Mint[0].

Accordingly, this paired evidence supports the **one `applied_keys_duplicate` negative-case row** under R4.1. It does **not** support an increment to the 21-case mutation total: the one-guard mutant is an attribution control, not a mutation-suite case. The captures leave case status unchanged and report 45/55 negative PASS and 18/21 mutation PASS. This review does not change those counts or any ledger.

## Scope and limitations

This is synthetic local evidence for an alternate applied policy. It grants no original-policy, full-ledger-admission, or live-network credit. The attempt captures are local self-records: they preserve the runner's classification summary but not raw simulator stdout/stderr or an external attestation. The R5 case manifest remains the immutable pre-execution snapshot with negative status PENDING and mutant status not executed. The runner dynamically imports `f05_2a_tx_sim_registry.py`; that helper's current hash was observed as `c03230249c7e73f6929cc944b7af3e30d98b8168f8abd184fa39332a601a394e`, but the attempt captures do not pin its execution-time hash. These limitations are retained in this review and do not change the reported evidence scope.
