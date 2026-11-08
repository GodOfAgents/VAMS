# F05.2a status mutation acceptance

remove_status_guard / datum_status is accepted at synthetic transaction-simulator scope after independent review.

Candidate: /home/GodOfAgents/vams-evidence/m3-f05-2a-status-mutation-20261002-r1/
Candidate manifest SHA-256: 6eec0b3e52ea08b91f56fe7059ca216e6edabf5c61b28002ac2243f0582fa7c4
Independent review: /home/GodOfAgents/vams-evidence/m3-f05-2a-status-independent-review-20261002-r1/REVIEW.json
Review SHA-256: 50d56cb8382fab8d35a2cd1c3aa0af9c8160e16e46c72b7ef9ec4193b55b35b2

Exact command:

PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-status-mutation-20261002-r1/run_status_mutation.py

Result: exit 0. All eight original-positive, original-status-negative, mutant-positive, and mutant-status-negative cases pass across pinned Aiken 1.1.21 and 1.1.23; target invocation is true. Both routing controls fail closed before target invocation. The mutation changes only state.status == AuthorityActive; the datum case changes Active to Paused. Independent review: PASS.

Counts: 42/55 negative cases PASS (13 pending, 0 failed); 12/21 mutations PASS (9 pending, 0 failed). Evidence is synthetic transaction-simulator evidence only. It does not establish ledger admission or live-network behavior. No canonical production source, applied policy identity, blueprint, or lock was changed. F05/M3 remain open and testnet readiness is not established; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
