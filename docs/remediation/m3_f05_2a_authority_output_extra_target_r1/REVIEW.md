# F05.2a extra expected-credential output — 2026-10-02

Independent review accepts authority_output_extra_target only. Candidate keeps
the original authority NFT output and adds one no-datum, no-asset output at the
expected state script credential, so the target credential appears twice and
the policy cardinality guard rejects. This is distinct from the wrong-state-
address candidate, which moves the NFT to a different payment credential.

Counts: **41/55 registered negatives PASS, 14 pending; 4/21 mutations PASS,
17 pending**. The reviewer verified original policy/script identity, two
body-bound funding signatures, 17,000,000 input lovelace =
16,000,000 outputs + 1,000,000 fee, and pinned-runtime outcomes.

Exact commands:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-authority-output-extra-target-negative-20261002-r1/build_case.py
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-authority-output-extra-target-negative-20261002-r1/execute_case.py
Valid positive accepted; candidate rejected at compiled evaluation with target
invoked under pinned Aiken 1.1.21 and 1.1.23. Wrappers exited 0 and cleanup
was clean. Independent review:
 /home/GodOfAgents/vams-evidence/m3-f05-2a-authority-output-extra-target-independent-review-20261002-r1/REVIEW.json
SHA256 76f347329c3a947302966bf376e5033ea0bb7cb194121f62bb8fa0921b4592b2.

This is synthetic transaction-simulator evidence only. No ledger admission or
live-network evidence is claimed. No production source/invariants changed.
F05/M3 remain open; Pre-Prod INCONCLUSIVE, promotion NOT READY; deployment,
Deposit, Slash activation and ExecuteIntent remain disabled.

Next single slice: assess authority_output_missing's phase-1 ledger validity and
whether it can receive only synthetic script-evaluation classification.
