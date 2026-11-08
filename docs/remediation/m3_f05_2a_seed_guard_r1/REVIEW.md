# F05.2a seed-guard mutation accepted — 2026-10-02

Registered mutation `remove_seed_guard`, paired only with `seed_missing`, is
accepted after independent review PASS_WITH_SCOPED_CAVEAT. Counts are unchanged
for negatives (42/55 PASS, 13 pending) and now 5/21 mutations PASS, 16 pending.
Current slice ledger: `docs/remediation/m3_f05_2a_seed_guard_r1/CASE-STATUS.json`.

Exact candidate command: `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-seed-guard-mutation-20261002-r6/run_seed_guard_mutation.py` — exit 0. Both pinned Aiken 1.1.21 and 1.1.23 accepted original and mutant positive controls, rejected the original seed-missing transaction at compiled evaluation, and accepted the mutant transaction with Mint[0] invoked. Stale-script and wrong-expected-policy controls failed closed with clean cleanup. Exact candidate manifest SHA-256: `77200345078ca055d9c083bfc2a3c494ef35d465e250251eeceebd481b5f93a1`.

Independent review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-seed-guard-independent-review-20261002-r1/REVIEW.json`, SHA-256 `006780cd2539f94dc3bbf03a88ecea1353b421d2282ccae9b9153ab007ff7b63`. The reviewer verified the single registered source replacement, fixed original applied policy ID, mutant ID and output-asset rebind, 15,000,000 lovelace input = 14,000,000 outputs + 1,000,000 fee, test funding signatures and input-key linkage, dual-runtime invocation, controls, and all 331 candidate checksums.

The separate schema-version context control returned a UPLC parser error and is excluded from all credit. Its UPLC context result is not transaction-simulator or ledger evidence. This slice establishes synthetic transaction-simulator behavior only, not ledger admission, live-network evidence, or full F05.2a acceptance. No production validator, blueprint, lock, frozen registry, credentials, vendors, or Git history changed. `git diff --check` passed. INV-1–INV-10 and mock behavior were not touched. F05/M3 and all later mandatory gates remain open; Pre-Prod admission is INCONCLUSIVE and promotion is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice: `remove_schema_version_guard` paired with `datum_schema_version`, preserving the accepted original applied-policy identity for the baseline and keeping mutant evidence separate.
