# F05.2a seed-hash mutation accepted — 2026-10-02

Registered `remove_seed_hash_guard`, paired only with `seed_datum_hash`, is
accepted after independent PASS. Negative counts remain 42/55 PASS, 13 pending;
mutation counts are now 7/21 PASS, 14 pending. Slice ledger:
`docs/remediation/m3_f05_2a_seed_hash_r1/CASE-STATUS.json`.

Exact command: `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-seed-hash-mutation-20261002-r3/run_seed_hash_mutation.py` — exit 0. Both pinned Aiken runtimes accepted original/mutant positives, rejected the seed-hash mutation under the original applied policy at compiled evaluation, and accepted it under the independently compiled mutant with Mint[0] invoked. Stale-script/wrong-policy controls failed closed. Candidate manifest SHA-256: `2fa2c783ce594e30055c491d33bd6126ce1f6446365ff4f954bd876c63f9040d`.

Independent review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-seed-hash-independent-review-20261002-r1/REVIEW.json`, SHA-256 `db5ee21b7485c257c0ed851fca3bf30e7b142d9ae381f884a93d29d7fc3454cc`. The reviewer confirmed one exact predicate replacement, original policy ID `9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731`, derived mutant ID, inline datum hash change to `ab` repeated 32 bytes, unchanged PoP datum fields, synthetic funding signatures, both runtimes, routing controls and cleanup.

Synthetic transaction-simulator evidence only; no ledger admission, live-network evidence, or full F05.2a acceptance. No production validator, blueprint, lock, frozen fixture, credential, vendor, or Git history changed. `git diff --check` passed. INV-1–INV-10 and mock behavior were not touched. F05/M3 and all later mandatory gates remain open; Pre-Prod admission is INCONCLUSIVE and promotion is NOT READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.

Next single slice: `remove_seed_index_guard` paired with `seed_datum_index`, preserving original applied-policy identity for the baseline.
