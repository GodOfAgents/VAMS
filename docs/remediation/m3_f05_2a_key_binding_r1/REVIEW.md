# F05.2a key-binding mutation accepted — 2026-10-02

Registered `remove_key_binding_guard`, paired only with `datum_key_binding`,
is accepted after independent dual-runtime replay. Negative counts remain
42/55 PASS, 13 pending; mutation counts are now 10/21 PASS, 11 pending.
Ledger: `docs/remediation/m3_f05_2a_key_binding_r1/CASE-STATUS.json`.

Exact command: `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-key-binding-mutation-20261002-r1/run_key_binding_mutation.py` — exit 0. Both pinned Aiken runtimes accepted original/mutant valid controls, rejected the first datum key changed to 32 zero bytes under the original applied policy at compiled evaluation, and accepted it under the mutant with Mint[0] invoked. Stale-script and wrong-policy controls failed closed. Candidate manifest SHA-256: `6e08de35aea9de65aaa689c9b033ab2f0ae6fb135d1dd0a3ac84da90b5d9e70c`.

Independent review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-key-binding-independent-review-20261002-r1/REVIEW.json`, SHA-256 `10449367f226414bf6ce3a7c50bae6cf238deab87525c270f15093f6c8202838`. Reviewer independently confirmed the exact one-line guard removal, original/mutant IDs, datum delta, preserved PoP fields and raw vectors, all synthetic funding signatures, eight core replays with expected invocation/results and clean cleanup, plus routing controls.

Evidence is synthetic transaction-simulator behavior only; no ledger admission, live-network evidence, or full F05.2a acceptance. No canonical production source, frozen fixture, blueprint, lock, credentials, vendor, or Git history changed. `git diff --check` passed. INV-1–INV-10 and mock behavior were not touched. F05/M3 and all later mandatory gates remain open; Pre-Prod is INCONCLUSIVE and promotion is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next: reassess the complete authoritative roadmap and current blockers before selecting the next single slice.
