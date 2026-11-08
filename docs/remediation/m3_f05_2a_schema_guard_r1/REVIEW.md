# F05.2a schema-version mutation accepted — 2026-10-02

Registered mutation `remove_schema_version_guard`, paired only with
`datum_schema_version`, is accepted after independent review PASS. Negative
counts are unchanged at 42/55 PASS, 13 pending; mutation counts are now 6/21
PASS, 15 pending. Current ledger: `docs/remediation/m3_f05_2a_schema_guard_r1/CASE-STATUS.json`.

Exact command: `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-schema-guard-mutation-20261002-r3/run_schema_guard_mutation.py` — exit 0. Both pinned Aiken 1.1.21 and 1.1.23 accepted original/mutant positive controls, rejected the schema-version-2 candidate under the original policy at compiled evaluation, and accepted it under the mutant with Mint[0] invoked. Stale-script and wrong-expected-policy controls failed closed. Candidate manifest SHA-256: `10980e28d8d2ef786260fc834f94f7668a0cad9ea352d724aad4f816687dbb8a`.

Independent review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-schema-guard-independent-review-20261002-r1/REVIEW.json`, SHA-256 `707e66912bea03c2ed5336f2ddf4c82b0a1ae4853541b93b9ba63d37751efea1`. Review verified the frozen pairing, exact one-expression mutation in the disposable source, original and mutant policy identity, schema version 3→2, unchanged raw inputs/outputs and PoP redeemers, both synthetic funding signatures for all four transaction variants, dual-runtime invocation and clean cleanup. Reviewer did not independently rederive each PoP signature message; valid controls pass, and that limitation is retained.

This is synthetic transaction-simulator evidence only. It establishes neither ledger admission nor live-network behavior and is not broad validator acceptance. No production source, frozen fixture, blueprint, lock, credentials, vendors, or Git history changed. `git diff --check` passed. INV-1–INV-10 and mock behavior were not touched. F05/M3 and all other mandatory roadmap gates remain open; Pre-Prod admission is INCONCLUSIVE and promotion is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice: `remove_seed_hash_guard` paired with `seed_datum_hash`, keeping baseline execution bound to the accepted original applied-policy identity.
