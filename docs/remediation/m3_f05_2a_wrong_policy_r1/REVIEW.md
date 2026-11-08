# F05.2a wrong-policy routing control acceptance

mint_wrong_policy is accepted only as the frozen routing/non-invocation contract. The independently reviewed runner stopped at target_policy_binding_mismatch; the original applied V3 witness remained present, but the Aiken child was never created. This is not a target-policy rejection or script-evaluation result.

Candidate evidence: /home/GodOfAgents/vams-evidence/m3-f05-2a-wrong-policy-routing-20261002-r1/
Candidate manifest SHA-256: 86991f07a5fce67f0598f3eb5710999fd9208b13db4ef0977ac559c52db3ce75
Frozen R2 contract SHA-256: 3510e127d369e9eab24a7ebe5a5dea10daaf55fd9589a297d78776bda940f6e9
Source fixture registry SHA-256: 98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d
Runner SHA-256: 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c

Exact command:
PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-wrong-policy-routing-20261002-r1/run_wrong_policy_routing.py

Result: exit 0. Observed error_code=target_policy_binding_mismatch, wrapper exit 2, simulator child exit null, target invocation false, clean cleanup. Independent read-only review confirmed fixture hashes, sole mint-policy-key body change (9d669a…8731 to ee×28), byte-identical original witness, and zero Popen calls. Reviewer accepted the routing-only promotion and count reconciliation. Frozen contract and original registry were not modified.

Category reconciliation against frozen R2: transaction-simulator 41 PASS / 10 pending; context-only 1 PASS / 2 pending; routing-only 1 PASS / 0 pending. Registered total is 43 PASS / 12 pending / 0 failed. The prior summary's category subtotal incorrectly placed already-passing seed_duplicate among context-only pending; it is corrected here without changing its case disposition. Mutation counts remain 17/21 PASS, 4 pending.

No executed-script rejection coverage is added by this routing PASS. No ledger admission or live-network result is claimed. Transaction signatures after the body-only policy-key mutation are not asserted valid. No canonical contract source, applied policy, blueprint, lock, or frozen evidence contract changed. Testnet readiness is not established; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
