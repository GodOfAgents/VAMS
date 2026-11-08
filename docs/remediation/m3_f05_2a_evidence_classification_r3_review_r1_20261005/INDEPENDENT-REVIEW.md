# Independent review: F05.2a evidence classification R3

Date: 2026-10-05

## Verdict

**PASS for the R2-to-R3 classification amendment.** The successor preserves the original case ID and source assertion, changes only the disposition of `applied_genesis_parameter` and the corresponding totals, cites the exact paired independent review, and keeps the credit boundary synthetic and local.

## Exact identities

- R2 `CASE-STATUS.json`: SHA-256 `74ab40cdf9e4463ae3eaadd876f5df379460e1ffa6292081203006e047b4aa28`.
- R3 `CASE-STATUS.json`: SHA-256 `3369c2e2ee6ef7afbf840e1aa1ca32aae39418ccba45b13c09914083f015c54e`.
- R3 `AMENDMENT.md`: SHA-256 `9885fa3b918f4a5e88d554be48df15fcbd7a87b43454ab7833bc23d22775075c`.
- R3 `SHA256SUMS`: SHA-256 `fc749e98c54fc2dd5f900928b6b71bc71277c0391633f20cd817bb6a97f4add1`.
- Source registry `docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json`: SHA-256 `98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d`, unchanged from R2.
- Paired execution review `docs/remediation/m3_f05_2a_applied_genesis_paired_review_r2_20261005/INDEPENDENT-REVIEW.md`: SHA-256 `c65b3f61f55276c84f940becfe54ebe59f9d96f29ade8a06153c4374ed5b8731`.

## Findings

The R3 JSON is strict JSON with no duplicate keys. After restoring the target row to pending and reverting only its related counters, normalized R3 equals R2. No other case ID, assertion, classification, observation, mutation entry, or source-registry identity changes.

The original registry case remains `applied_genesis_parameter` with assertion `compile_with_different_genesis_ref_keep_transaction`. R3 classifies that row as `transaction_simulator` and cites the paired-review file above. The paired review ties the R6 accepted positive, R7 compiled rejection at Mint[0], and R9 accepted `remove_seed_guard` mutant to the same retained R5 synthetic alternate-policy family.

The three referenced run records match their cited SHA-256 values:

- R6 positive: `457cb0ec423477df1d232501506e713f3ce7800210635b35535abff0b2417c8e`.
- R7 negative: `651fc64426b0968828a597564b48ae4a6dbba68b0f5d516d37f28b8bc5924d7e`.
- R9 one-guard mutant: `4ce6eebe967ac9cf44e57a30c3dac5242071c9d0b1ad944d65064f6b890f7b3b`.

The structured records agree on intended Mint[0] invocation and report valid body-bound ephemeral funding signatures, ADA and native-asset conservation, and no persisted private-key material. Their recorded stages are respectively `script_accepted`, `compiled_evaluation`, and `script_accepted`.

R3 totals are internally consistent: **47/55 negative cases PASS, 8 pending; 43/51 transaction-simulator cases PASS, 8 pending; context-only 3/3 and routing-only 1/1 unchanged.** Mutation evidence stays **18/21 PASS**, with the same three pending IDs. The mutant is not counted as new mutation-suite credit.

The amendment explicitly limits the new case credit to a synthetic alternate applied policy. It grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit; F05/M3 stays open, readiness remains NOT READY, and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Verification performed

Read-only review only. No tests, compiler, simulator, network, installation, or fixture mutation was performed.

- Duplicate-key-aware JSON parsing and normalized R2/R3 comparison"È›y¯ßy‘ **PASS**.
- R3 normalization check+ßuÁ‚ùÁT **PASS**; only the target disposition and associated counts differ.
- `cd docs/remediation/m3_f05_2a_evidence_classification_r3_20261005 && sha256sum -c SHA256SUMS`"È›y¯ßy‘ **PASS** (`AMENDMENT.md` and `CASE-STATUS.json` both OK).
- SHA-256 checks of the cited R6/R7/R9 records, paired review, source registry, and R3 files"È›y¯ßy‘ **PASS**, identities listed above.

## Limitations

The underlying run captures are local structured records; the paired review reports that raw simulator stdout/stderr and external attestation were not retained. That review also did not independently rebuild the compiled mutant. This classification supports only the stated synthetic simulator credit and does not establish ledger or live-network behavior.
