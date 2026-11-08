# F05.2a datum_key_order evidence correction — 2026-10-02

The previously accepted datum_key_order entry is reopened pending corrected
evidence. A read-only comparison found the transaction labeled datum_key_order
in the datum semantics family swaps ordered_keys indices 0 and 1, while the
frozen datum_key_order case swaps indices 1 and 2. The former matches the
separately registered r2_swapped_datum_keys mutation. Do not count this artifact
for datum_key_order. The status ledger has been corrected from 36/55 to
35/55 negative PASS and 20 pending; mutation counts remain 4/21 PASS, 17
pending.

Independent case-specific review of the existing 0↔1 artifact is pending at
r2_swapped_datum_keys; it may receive credit only for that registered ID after
review. datum_key_order remains pending for a new fixture that swaps 1↔2.

The earlier group run command was:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/execute_datum_family.py
It executed 12 datum cases across pinned Aiken 1.1.21 and 1.1.23. This erratum
does not invalidate other datum entries; only datum_key_order was affected by
the discovered index mismatch. The actual evidence artifact remains preserved:
 /home/GodOfAgents/vams-evidence/m3-f05-2a-datum-semantics-20261002-r1/datum_key_order/
Its RUN-RESULTS row must not be presented as proof of the frozen 1↔2 case.

No code, registry, source fixture, or activation setting changed. No ledger
admission or live-network evidence is claimed. F05/M3 remain open, Pre-Prod
INCONCLUSIVE, promotion NOT READY; deployment, Deposit, Slash activation and
ExecuteIntent remain disabled.

Next single slice: after independent case review, reclassify the existing 0↔1
candidate only to r2_swapped_datum_keys; then prepare separate corrected
evidence for datum_key_order (indices 1↔2).
