# F05.2a epoch mutation accepted — 2026-10-02

Registered `remove_epoch_guard`, paired only with `datum_epoch`, is accepted
after independent dual-runtime replay. Negative counts remain 42/55 PASS, 13
pending; mutation counts are now 9/21 PASS, 12 pending. Ledger:
`docs/remediation/m3_f05_2a_epoch_r1/CASE-STATUS.json`.

Exact command: `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-epoch-mutation-20261002-r2/run_epoch_mutation.py` — exit 0. Both pinned Aiken runtimes accepted original/mutant valid controls, rejected datum epoch 1 under the original applied policy at compiled evaluation, and accepted it under the mutant with Mint[0] invoked. Stale-script and wrong-policy controls failed closed. Candidate manifest SHA-256: `d5c745a45b340f6acc2e65bfd4f9d24c7a0c64d5dfcc84d7ee32d10327943f05`.

Independent review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-epoch-independent-review-20261002-r1/REVIEW.json`, SHA-256 `b3a931fe0f4826f4f50de919a107cac9232355839dc903cd458621b842d80a97`. Reviewer confirmed exact one-expression mutation, original and mutant IDs, epoch 0→1, unchanged PoP fields and transaction vectors, valid synthetic funding signatures, all eight independent replays with target invocation and clean cleanup, and routing controls.

Evidence is bounded synthetic transaction simulation only; no ledger admission, live-network evidence, or full F05.2a acceptance. No production source, fixture, blueprint, lock, credentials, vendor or Git history changed. `git diff --check` passed. INV-1–INV-10 and mock behavior were not touched. F05/M3 and later mandatory gates remain open; Pre-Prod is INCONCLUSIVE and promotion is NOT READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.

Next: reassess the complete authoritative roadmap and current blockers before selecting the next single slice.
