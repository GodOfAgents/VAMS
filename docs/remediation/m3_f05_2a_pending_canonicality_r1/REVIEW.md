# F05.2a pending-canonicality mutation acceptance

remove_pending_canonicality_guard / datum_pending_noncanonical is accepted at synthetic transaction-simulator scope after independent review.

Candidate: /home/GodOfAgents/vams-evidence/m3-f05-2a-pending-canonicality-mutation-20261002-r1/
Candidate manifest SHA-256: D965899EDBE6EFB4030E7A7FE4DB62DE97334B80AE42FC3EF167D02C81247365
Independent review: /home/GodOfAgents/vams-evidence/m3-f05-2a-pending-canonicality-independent-review-20261002-r1/REVIEW.json
Review SHA-256: 168b8d4eb0145a876439c480d7d75b6f65ad0135fe9a4451fae96a26ee1f3dd6

Exact command:

PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-pending-canonicality-mutation-20261002-r1/run_pending_canonicality_mutation.py

Result: exit 0. All eight original-positive, original-pending-negative, mutant-positive, and mutant-pending-negative rows pass across pinned Aiken 1.1.21 and 1.1.23, with target invocation and clean teardown. Both stale-script and wrong-policy routing controls fail before target invocation. The mutation removes only canonical_none(state.pending); the negative changes only pending.ordered_next_keys from 160 zero bytes to 01 followed by 159 zero bytes. Independent review: PASS.

Counts: 42/55 negative cases PASS (13 pending, 0 failed); 13/21 mutations PASS (8 pending, 0 failed). Evidence is synthetic transaction-simulator evidence only. It establishes neither ledger admission nor live-network behavior. No canonical production source, applied policy identity, blueprint, or lock was changed. F05/M3 remain open and testnet readiness is not established; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
