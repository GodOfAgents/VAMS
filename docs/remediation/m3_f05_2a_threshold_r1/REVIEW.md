# F05.2a threshold mutation accepted — 2026-10-02

Registered `remove_threshold_guard`, paired only with `datum_threshold`, is
accepted after independent dual-runtime replay. Negative counts remain 42/55
PASS, 13 pending; mutation counts are now 11/21 PASS, 10 pending. Ledger:
`docs/remediation/m3_f05_2a_threshold_r1/CASE-STATUS.json`.

Exact command: `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-threshold-mutation-20261002-r1/run_threshold_mutation.py` — exit 0. Both pinned Aiken runtimes accepted original/mutant positive controls, rejected datum threshold 4 under the original applied policy at compiled evaluation, and accepted it under the mutant with Mint[0] invoked. Stale-script and wrong-policy controls failed closed. Candidate manifest SHA-256: `2de102cf05ed08082ed9690c2e5b0ab83b6df36b7b5334cdfe3e433cd2cd8526`.

Independent review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-threshold-independent-review-20261002-r1/REVIEW.json`, SHA-256 `4ea50cf9921ac82dc23bfcf75c3b9cfaea74542c854c6241ddcdf7a90b7a1120`. The reviewer verified exact one-expression deletion, original/mutant IDs, datum threshold 3→4 only, unchanged PoP fields and transaction vectors, funding signatures, eight independent replays and clean controls.

Evidence is synthetic transaction-simulator behavior only; no ledger admission, live-network evidence, or full F05.2a acceptance. No canonical production source, frozen fixture, blueprint, lock, credentials, vendor or Git history changed. `git diff --check` passed. INV-1–INV-10 and mock behavior were not touched. F05/M3 and all later mandatory gates remain open; Pre-Prod is INCONCLUSIVE, promotion NOT READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.

Next: reassess the complete authoritative roadmap and blockers before selecting the next single slice.
