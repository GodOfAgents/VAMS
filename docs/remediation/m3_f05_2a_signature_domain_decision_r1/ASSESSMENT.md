# F05 proof-domain signature family blocker audit

Date: 2026-10-03
Status: read-only reconciliation complete; owner decision required.

## Current contract

All four rows (r2_signature_for_other_seed, r2_signature_for_other_network, r2_signature_for_other_validator_hash, r2_signature_for_other_epoch) are PENDING in the accepted overlay and frozen R2 contract. Every row requires category ledger_tx_sim, pinned Aiken tx simulate --cbor, rejection at compiled Mint[0], and exact applied policy ID 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731.

The public test helper creates a fresh ephemeral committee for each run and signs the changed message with those fresh keys. The accepted public fixture contains no private-key fixture for the original committee. Such fresh parameters produce a different applied policy and do not satisfy the current exact-policy contract. The prior single-case assessment for other_seed independently established that direct raw UPLC evaluation fails at verifySignature before reaching the negative and is not acceptable ledger_tx_sim evidence.

## Smallest family decision

A. Keep the exact applied-policy ledger_tx_sim contract and authorize a controlled existing-committee signing path that never exports private key material; then construct and independently review exact CBOR transactions for all four domains.

B. Amend the evidence contract and build test-only parameter-bound synthetic CBOR transactions. This is synthetic simulator evidence only and cannot claim the exact applied policy, ledger admission, or live evidence.

C. Keep all four cases pending until separate signing/evidence authorization is available.

No signature was requested or generated. No private key was read, derived, or persisted. No compile or simulator ran. Source hashes and the exact row reconciliation are in RUN.json.

F05 remains 45/55 negatives and 18/21 mutations. Six applied-parameter variants retain their separate A/B/C decision in docs/remediation/m3_f05_2a_applied_genesis_parameter_design_r1/DECISION-REQUIRED.md. F04 also retains its A/B normative identity-path decision in docs/remediation/m7_agent_nft_audit_r1/ASSESSMENT.md. Testnet readiness remains NOT READY; all deployment and activation gates remain disabled.

Independent read-only review by /root/f05_other_seed_blocker_review: PASS for the exact four-row signature-domain family audit. The reviewer matched the R2 contract, fixture registry, accepted overlay, helper, runner, and prior blocker record hashes. All four rows are PENDING, category ledger_tx_sim, use pinned Aiken tx simulate --cbor, expect rejection at compiled Mint[0], and bind the exact applied policy ID. The current helper generates a fresh five-key ephemeral committee and signs each changed-domain message with those keys; the accepted fixture has no private-key fixture. The two proposed evidence routes preserve or explicitly amend the scope and grant no implicit credit. Limitation: the audit does not establish that an authorized original-committee signing facility exists. No credential access, keys, builds, or simulation were used.
