# F05.2a corrected datum key ordering — 2026-10-02

Independent review accepts the registered datum_key_order case only. The
candidate swaps authority datum ordered_keys indices 1↔2 (zero-based) and
changes only the datum's ordered-key field. This corrects the prior evidence
label erratum: the earlier 0↔1 candidate is credited solely to
r2_swapped_datum_keys.

Counts: **37/55 negatives PASS, 18 pending; 4/21 mutations PASS, 17 pending**.
The exact candidate preserves policy ID 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731 and script hash
fc8726cff89172d4944e257a2eb2659d35363c8e5a4d423ed8a2112eb5af7e59. Two
synthetic funding signatures verify and balance is 17,000,000 =
16,000,000 + 1,000,000.

Exact build command:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-datum-key-order-corrected-negative-20261002-r1/build_case.py

Exact execution command:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-datum-key-order-corrected-negative-20261002-r1/execute_case.py
Result: valid positive accepted and candidate rejected at compiled evaluation with
target invoked on Aiken 1.1.21 (SHA256
07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79) and
Aiken 1.1.23 (SHA256
748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3). Wrapper
exit 0, child exits 0/1, cleanup clean for each. Independent review PASS for
datum_key_order only:
 /home/GodOfAgents/vams-evidence/m3-f05-2a-datum-key-order-corrected-independent-review-20261002-r1/REVIEW.json
SHA256 b9022aee974c33b8bd058229000e892cf9423ce55c13ea9bc7e92ad6766111f2.

This is synthetic transaction-simulator evidence, not ledger admission or live
behavior. Test-only funding keys were transient and no private material was
persisted. No production source or invariants changed. F05/M3 remain open,
Pre-Prod INCONCLUSIVE, promotion NOT READY; deployment, Deposit, Slash
activation and ExecuteIntent remain disabled.

Next feasible single case: r2_duplicate_datum_key. Signature-for-other-message
cases await availability or authorized disposition for the original applied
committee signers. Parameter-variant cases await the separate evidence-contract
classification decision.
