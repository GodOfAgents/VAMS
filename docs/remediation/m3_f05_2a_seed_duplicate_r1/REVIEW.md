# F05.2a duplicate seed input — 2026-10-02

Independent review accepts exactly the seed_duplicate negative simulator case.
Counts: **36/55 negatives PASS, 19 pending; 4/21 mutations PASS, 17 pending**.
Mutation counts are unchanged. The duplicate input is invalid at the ledger
layer; evidence establishes script evaluation only.

The reviewer verified the evidence manifest, repeated seed references and
resolved UTxO rows, body-bound funding signatures, value conservation, unchanged
target policy/script and successful positive plus negative evaluation on both
pinned Aiken runtimes. Independent review:
 /home/GodOfAgents/vams-evidence/m3-f05-2a-seed-duplicate-independent-review-20261002-r1/REVIEW.json
SHA256 c3ecf7d951a3717971aead25715fce83053a943f6c2398f0647685486770afbe.

Exact candidate command:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/build_seed_duplicate.py
Result: exit 0; valid accepted and duplicate-input candidate rejected at compiled
Mint[0] on pinned Aiken 1.1.21. Pinned Aiken 1.1.23 replay: same outcomes,
wrapper exit 0, cleanup clean. git diff --check: PASS.

This remains synthetic simulator evidence only: the duplicate transaction
input is ledger-invalid, with no ledger admission or live-network evidence.
INV-1–INV-10 and mock behavior are unchanged. F05/M3 remain open; Pre-Prod is
INCONCLUSIVE and promotion is NOT READY. Deployment, Deposit, Slash activation,
and ExecuteIntent remain disabled. T06/history and all other mandatory roadmap
gates remain outstanding.

Next single slice: registered applied_genesis_parameter negative only, subject
to preserving the original applied policy identity and explicit review of its
parameter-derived policy semantics.
