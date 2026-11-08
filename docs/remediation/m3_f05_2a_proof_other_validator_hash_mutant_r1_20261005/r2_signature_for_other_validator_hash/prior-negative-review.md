# Independent attempt review: validator-hash negative

Review result: PASS for attempt integrity only; named-condition attribution remains PENDING. This review awards no negative-case credit.

Reviewed record: docs/remediation/m3_f05_2a_proof_other_validator_hash_negative_attempt_r1_20261005/RUN.json
RUN.json SHA-256: 5e89f1f022fcb11e3e6311cb13c0bb3bdb7821b8e44d97863d991f5673ce86c0
The record SHA256SUMS manifest passes.

## Integrity findings

- The transaction hash is b1113e0ee4172a49d7ce4a3e30a31d03b017c54cadb5546b72b60ec5c054dd2d. It matches the exact pre-reviewed negative fixture. Raw input hash 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec and raw output hash fccf32f91dd3541e33bdb9a92f61ab002bdf93ba7275a270101c70309fa044b9 also match.
- The immutable R3 runner SHA-256 is 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c; pinned Aiken SHA-256 is 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. Both match current tool bytes.
- Wrapper exit is 0; simulator child exit is 1. Classification says compiled_evaluation with target_script_invoked true. Runner result wrapper exit is 0.
- The runner source independently parses the transaction Mint map and Plutus V3 witness, requiring one mint policy and one V3 witness program. Its V3-prefixed script hash, the mint policy ID, and expected applied policy ID all equal 409712d7175aa2f7d372364919d50f55a048b83c7770a646826a1df4. The pre-execution review tied these exact transaction bytes to the independently recompiled applied script.
- Teardown is clean: child_reaped, process_group_empty, and snapshot_descriptors_closed are true; cleanup status is clean.
- Funding and conservation are inherited only through byte identity with the reviewed fixture: final-body funding signatures were verified against the transaction body hash, credentials match resolved inputs, ADA balances conserve 17,000,000 = 10,000,000 + 6,000,000 + 1,000,000 lovelace, and exactly one authority NFT is minted and preserved. No collateral is present.
- The attempt record cross-links the accepted synthetic positive-control record and pre-execution byte review. Scope correctly grants no original-policy, ledger-admission, Pre-Prod, or live-network credit. It explicitly leaves negative_case null and case_status PENDING.

## Attribution boundary

The stage compiled_evaluation is generic. The pinned classifier labels this stage only when the expected transaction ID reached script context and Mint[0], then reports the fixed generic error that the Mint[0] validator crashed or exited prematurely. The record does not retain raw simulator stdout/stderr or external attestation. This establishes a failed evaluation at the target entrypoint, not that the alternate state-validator hash was the cause.

Before awarding the negative row, obtain either:

1. Reviewer-verifiable first-failure attribution from the unmodified compiled target at Mint[0], tied to the exact compiled program bytes and this exact input; or
2. A same-negative one-guard mutant that changes only the named validator-hash condition, is separately compiled with its own policy ID, mint, and Plutus V3 witness rebound, and accepts.

Until one of those controls passes independent review, keep r2_signature_for_other_validator_hash PENDING. Do not infer named-condition causality from the generic stage or award case credit.

No simulator was run during this review. No fixture, STATUS, HANDOFF, or classification file was changed by this review.
