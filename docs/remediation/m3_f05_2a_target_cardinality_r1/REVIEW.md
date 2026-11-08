# F05.2a target-output cardinality mutation acceptance

remove_target_output_cardinality_guard / authority_output_extra_target is accepted at synthetic transaction-simulator scope after independent review of corrected candidate r2.

Candidate: /home/GodOfAgents/vams-evidence/m3-f05-2a-target-cardinality-mutation-20261002-r2/
Candidate manifest SHA-256: 4f0fb7a5b1ef0c939ef5bad7e088de303d742af8bba9a5e5748e37c0a068b5f9
Independent review: /home/GodOfAgents/vams-evidence/m3-f05-2a-target-cardinality-independent-review-20261002-r2/REVIEW.json
Review SHA-256: 13f1b24632d1486a692e193f209ea0e4055b168cfdaa515472385e62c525286b
Metadata addendum: /home/GodOfAgents/vams-evidence/m3-f05-2a-target-cardinality-independent-review-20261002-r2/ADDENDUM.json
Addendum SHA-256: ef4f9c7cdf7b55ce2bccf528921d5486b38af859d6ff77b3db23b26550578c1c

Exact command:

PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-target-cardinality-mutation-20261002-r2/run_target_cardinality_mutation.py

Result: exit 0. All eight original-valid, original-extra-target-negative, mutant-valid, and mutant-extra-target-negative cases pass across pinned Aiken 1.1.21 and 1.1.23 with target invocation and clean teardown. Stale-script and wrong-policy routing controls fail before target invocation. The disposable policy mutation removes only count_state_credential_outputs(...) == 1. The paired three-output transaction preserves the authentic NFT output and adds a second no-datum/no-asset output at the expected state credential; outputs are 10M, 4M, and 2M lovelace, balancing 17M input = 16M outputs + 1M fee. Funding witnesses verify and match persisted resolved-input payment-key hashes.

Candidate r1 is preserved but rejected: independent review found the witness public-key hashes did not match payment credentials in the persisted resolved inputs. It receives no mutation credit. Candidate r2 fixes that binding and passes independent review.

Counts: 42/55 negative cases PASS (13 pending, 0 failed); 14/21 mutations PASS (7 pending, 0 failed). Evidence is synthetic transaction-simulator evidence only. It establishes neither ledger admission nor live-network behavior. No canonical production source, applied policy identity, blueprint, or lock was changed. F05/M3 remain open and testnet readiness is not established; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
