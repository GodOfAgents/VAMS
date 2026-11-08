# F05.2a wrong authority-NFT output credential — 2026-10-02

Independent review accepts the registered r2_wrong_state_address candidate and
maps the same transaction/run set to output_wrong_payment_credential because
the two source branches construct the same predicate scenario: the authority
NFT output uses payment credential 65… and one empty no-datum output remains at
the expected state credential. The 2M ADA move from sponsor change preserves
transaction validity/value conservation; it is not a distinct contract
predicate. One shared behavior is represented by two frozen IDs; no separate
mutation diversity is claimed.

Counts: **40/55 registered negatives PASS, 15 pending; 4/21 mutations PASS,
17 pending**. Reviewer verified original target Mint/script/policy, two
body-bound funding signatures, output credential/cardinality, sponsor rebalance
and 17,000,000 = 16,000,000 + 1,000,000. Exact commands:

PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-r2-wrong-state-address-negative-20261002-r1/build_case.py

PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-r2-wrong-state-address-negative-20261002-r1/execute_case.py

Valid positive accepted and this candidate rejected at compiled evaluation with
target invoked on pinned Aiken 1.1.21 and 1.1.23; wrappers exited 0 and cleanup
was clean. Independent review:
 /home/GodOfAgents/vams-evidence/m3-f05-2a-r2-wrong-state-address-independent-review-20261002-r1/REVIEW.json
SHA256 54504d0fcebe322924d0ef0811f97d3bda26df17e2439ef9f1fe77a26d62887d.

Synthetic transaction-simulator evidence only, not ledger admission or live
behavior. Test funding key bytes were not persisted. No production source or
invariants changed. F05/M3 remain open, Pre-Prod INCONCLUSIVE, promotion NOT
READY; deployment, Deposit, Slash activation and ExecuteIntent remain disabled.

Next slice is selected after reconciling the frozen queue and independent
blockers; parameter-variant classification and original committee signer
availability remain unresolved.
