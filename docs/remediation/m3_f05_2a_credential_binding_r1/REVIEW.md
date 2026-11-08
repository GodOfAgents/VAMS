# F05.2a state-validator credential-binding mutation acceptance

remove_state_validator_credential_binding / r2_wrong_state_address is accepted at synthetic transaction-simulator scope after independent review of corrected candidate r2.

Candidate: /home/GodOfAgents/vams-evidence/m3-f05-2a-credential-binding-mutation-20261002-r2/
Candidate manifest SHA-256: 64c77208398adcbafadda4cf7b61db8c7c205f17a49f0b221f188ca6a6fc92fc
Independent review: /home/GodOfAgents/vams-evidence/m3-f05-2a-credential-binding-independent-review-20261002-r2/REVIEW.json
Review SHA-256: 094adaa283086d14480b7d5ab18e79b24961e2488d86dcad9490fd1db2df942b

Exact command:

PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-credential-binding-mutation-20261002-r2/run_credential_binding_mutation.py

Result: exit 0. All eight original-valid, original-wrong-state-address-negative, mutant-valid, and mutant-wrong-state-address-negative cases pass across pinned Aiken 1.1.21 and 1.1.23 with target invocation and clean teardown. Stale-script and wrong-policy routing controls fail before target invocation. The disposable policy mutation removes only authority_output.address.payment_credential == Script(state_validator_script_hash). The paired transaction moves the authentic NFT and datum to a wrong payment credential while retaining exactly one empty no-datum 2M-lovelace output at the expected state credential; it preserves the separate cardinality predicate. Outputs are 10M, 4M, and 2M lovelace, balancing 17M inputs = 16M outputs + 1M fee. Funding witnesses match persisted resolved-input payment-key hashes.

Candidate r1 is preserved but superseded because its row labels still said extra-target although it used the wrong-state-address fixture; it receives no credit. Candidate r2 corrects the case labels and passes independent review. The existing output_wrong_payment_credential negative is a semantic alias of this same behavior and is not counted as a distinct behavior or run set.

Counts: 42/55 negative cases PASS (13 pending, 0 failed); 15/21 mutations PASS (6 pending, 0 failed). Evidence is synthetic transaction-simulator evidence only. It establishes neither ledger admission nor live-network behavior. No canonical production source, applied policy identity, blueprint, or lock was changed. F05/M3 remain open and testnet readiness is not established; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
