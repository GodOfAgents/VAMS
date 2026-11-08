# Independent R7 to R8 evidence classification overlay review

Review id: m3_f05_2a_evidence_classification_r8_independent_review_r1_20261005
Outcome: PASS
Target: r2_signature_for_other_validator_hash

## Checks performed

Verified every file in docs/remediation/m3_f05_2a_evidence_classification_r8_20261005/SHA256SUMS. All five package entries passed. Independently ran:

    python3 docs/remediation/m3_f05_2a_evidence_classification_r8_20261005/compare_r7_to_r8.py

The comparator returned PASS and independently reported the sole target delta PENDING -> PASS, negative case counts 52 PASS / 3 PENDING / 0 FAILED, transaction_simulator counts 48 PASS / 3 PENDING / 0 FAILED out of 51, unchanged mutation rows, and 74 verified evidence hashes. The R8 row preserves case id r2_signature_for_other_validator_hash and assertion sign_tuple_with_another_state_validator_hash. Its classification is transaction_simulator.

The comparator normalizes only the target status row and corresponding negative aggregate and transaction_simulator counts, then requires exact equality with R7. It separately asserts exact mutation-row equality, target original assertion preservation, all 74 evidence file hashes, and the positive, normal-negative, mutant, and pre-execution review hash links and result bindings.

The R8 target row links the integrated independent triad review at docs/remediation/m3_f05_2a_proof_other_validator_hash_triad_review_r1_20261005/INDEPENDENT-REVIEW.md with SHA-256 0d0ab5989ee71555dc207424990136b403116aed556fc65eba12e55f38b86698. The row and amendment specify R4.1 proof-domain choice B and synthetic_parameter_bound_tx_sim evidence. Its scope explicitly sets mutation_suite, original_policy, ledger_admission, pre_prod, live_network, and deployment_readiness to false. The synthetic alternate-policy mutant supports named-condition attribution only.

## Limits

This review validates the evidence-classification overlay and its hash links; it does not execute transactions or independently repeat the underlying simulator runs. The accepted status is one synthetic transaction_simulator negative row only. It grants no mutation-suite, original-policy negative, full-ledger admission, Cardano Pre-Prod, live-network, or deployment-readiness credit. STATUS and HANDOFF are outside this overlay and were not edited.
