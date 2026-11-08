# F05.2a R2 swapped datum keys — 2026-10-02

Independent review accepts r2_swapped_datum_keys only. Counts return to
36/55 negative PASS, 19 pending; 4/21 mutations PASS, 17 pending. The reviewer
verified this candidate swaps ordered-key indices 0↔1, which matches the R2
registered case and not datum_key_order (indices 1↔2). The original applied
script, policy ID, seed inputs, Mint map and R2 proofs are bound; two synthetic
funding signatures verify; input/output value balance is 17,000,000 =
16,000,000 + 1,000,000.

Exact existing execution command:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/execute_datum_family.py
That grouped command executed the preserved candidate under pinned Aiken
1.1.21 and 1.1.23; valid positive accepted and the candidate rejected at
compiled evaluation with target invoked, wrapper exit 0, child exit 1, clean
cleanup on both. The existing datum_key_order label was erroneous and has been
reopened; this evidence is not credited to it. Independent review:
 /home/GodOfAgents/vams-evidence/m3-f05-2a-r2-swapped-datum-keys-independent-review-20261002-r1/REVIEW.json
SHA256 4edb7f73bdaee819e44a8474f888b1aeed318e977296042ebad98776a75eaf05.

This is synthetic transaction-simulator evidence only, not ledger admission or
live-network behavior. Test funding keys were generated only for synthetic
fixtures; no private material was persisted. No production source or invariant
changed. F05/M3 remain open, Pre-Prod INCONCLUSIVE, promotion NOT READY;
deployment, Deposit, Slash activation and ExecuteIntent remain disabled.

Next single slice: correct datum_key_order with its distinct indices 1↔2
permutation and independent review. The applied-parameter family and R2
other-message cases remain pending/blockers; no activation gate is relaxed.
