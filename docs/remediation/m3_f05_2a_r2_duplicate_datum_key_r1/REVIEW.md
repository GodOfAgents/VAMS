# F05.2a R2 duplicate datum key — 2026-10-02

Independent mapping review accepts r2_duplicate_datum_key using the already
executed datum_duplicate_key candidate. The frozen registry/source operations
are identical: assign ordered_keys[1] = ordered_keys[0]. This is one unique
negative mutation mapped to two registered IDs; no separate run or additional
mutation diversity is claimed.

Counts: **38/55 registered negatives PASS, 17 pending; 4/21 mutations PASS,
17 pending**. The candidate and prior integrated review bind the original
policy/script, verify the two synthetic funding signatures and value balance,
and show positive acceptance plus compiled rejection on both pinned Aiken
runtimes. The case-specific mapping review is:
 /home/GodOfAgents/vams-evidence/m3-f05-2a-r2-duplicate-datum-key-independent-review-20261002-r1/REVIEW.json
SHA256 d18853d3347e9d9b0f021b54e25f990fc8eef5c3f742ba45a4fa85f17877b581.

Exact original build/execution commands:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/build_datum_semantics_family.py
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/execute_datum_family.py
The existing run set includes this exact duplicate-key candidate and both Aiken
1.1.21/1.1.23 outcomes. It is synthetic transaction-simulator evidence only,
not ledger admission or live-network evidence.

The unique negative behavior count does not increase from mapping this alias.
No production source or invariant changed. F05/M3 remain open, Pre-Prod
INCONCLUSIVE, promotion NOT READY; deployment, Deposit, Slash activation and
ExecuteIntent remain disabled.

Next feasible single slice: r2_wrong_state_address, subject to preserving
canonical policy/script and separately reviewed value topology. The
parameter-variant evidence-contract decision and signatures for the original
applied committee remain unresolved.
