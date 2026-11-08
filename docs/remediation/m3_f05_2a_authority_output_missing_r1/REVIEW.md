# F05.2a missing authority state output — 2026-10-02

Independent review accepts authority_output_missing only as synthetic
transaction-simulator script evidence. The candidate removes the authority
state output and sends the single minted NFT to a sponsor key output. It has
zero outputs at the expected state credential, preserves Mint quantity 1 =
output quantity 1 and conserves 17,000,000 input lovelace =
16,000,000 outputs + 1,000,000 fee. Two body-bound funding signatures and
original policy/script binding were verified.

Counts: **42/55 registered negatives PASS, 13 pending; 4/21 mutations PASS,
17 pending**.

Exact commands:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-authority-output-missing-negative-20261002-r1/build_case.py
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-authority-output-missing-negative-20261002-r1/execute_case.py
Valid positive accepted and candidate rejected at compiled evaluation with
target invoked under pinned Aiken 1.1.21/1.1.23; wrappers exited 0, child exits
0/1 and cleanup was clean. Independent review:
 /home/GodOfAgents/vams-evidence/m3-f05-2a-authority-output-missing-independent-review-20261002-r1/REVIEW.json
SHA256 25e08ea1386d8788796a97551fa723a36f4b628828f9f6b5f8fc69deb1686800.

This simulator rejection does not establish ledger admission, and the case
does not claim a phase-1 structural defect. No live-network evidence, source
change, invariant change or activation occurred. F05/M3 remain open, Pre-Prod
INCONCLUSIVE, promotion NOT READY; deployment, Deposit, Slash activation and
ExecuteIntent remain disabled.

Next slice: reassess the pending F05 cases; defer context-only output quantities,
wrong-policy routing and cases requiring unavailable original committee
signatures or parameter-family disposition.
