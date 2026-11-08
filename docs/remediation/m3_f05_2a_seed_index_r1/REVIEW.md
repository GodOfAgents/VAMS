# F05.2a seed-index mutation accepted — 2026-10-02

Registered `remove_seed_index_guard`, paired only with `seed_datum_index`, is
accepted after independent review and replay. Negative counts remain 42/55
PASS, 13 pending; mutation counts are now 8/21 PASS, 13 pending. Ledger:
`docs/remediation/m3_f05_2a_seed_index_r1/CASE-STATUS.json`.

Exact command: `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-seed-index-mutation-20261002-r2/run_seed_index_mutation.py` — exit 0. Both pinned Aiken runtimes accepted original/mutant positive fixtures, rejected the datum-index-8 candidate under the original policy at compiled evaluation, and accepted it under the mutant with Mint[0] invoked. Stale-script and wrong-policy controls failed closed. Candidate manifest SHA-256: `77c2c38425882a390f0ac7a62122373732441b4de53eba0a5477552d190697e9`.

Independent review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-seed-index-independent-review-20261002-r1/REVIEW.json`, SHA-256 `18be5480a33dda01a1e7ebf2bcbed2a622b36e3339ae3bfc8cae33a0eb80ec8a`. The original review inspected structure/checksums; independent replay addendum `/home/GodOfAgents/vams-evidence/m3-f05-2a-seed-index-independent-review-20261002-r1/ADDENDUM-r2.json`, SHA-256 `4779fad81818668543db5e6cff4bcbb33c92a6d5789f625af28323c8c63751dd`, independently reran all eight core transaction-simulator rows across Aiken 1.1.21 and 1.1.23. Original/mutant positives and mutant negative accepted; original negative rejected; every target invoked with matching policy ID, wrapper exit 0 and cleanup clean. The addendum supersedes the initial review's no-replay limitation.

Evidence is bounded synthetic transaction simulation only; it does not establish ledger admission, live-network behavior, or complete F05.2a acceptance. No production source, frozen fixture, blueprint, lock, credentials, vendor, or Git history changed. `git diff --check` passed. INV-1–INV-10 and mock behavior were not touched. F05/M3 and all later mandatory gates remain open; Pre-Prod admission is INCONCLUSIVE and promotion is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next: reassess the complete authoritative roadmap and blockers before selecting the next single slice.
