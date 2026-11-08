# Independent post-run review: validator-hash positive control

Review status: PASS for the executed synthetic positive-control record. This review does not accept the negative case, a mutation, original-policy behavior, ledger admission, Pre-Prod, or live-network behavior.

Reviewed record: docs/remediation/m3_f05_2a_proof_other_validator_hash_positive_attempt_r1_20261005/RUN.json
RUN.json SHA-256: 18b04228b885bc428441aab701fa100f7dd280d53efd4a87d4fef4b3375d1e6d
Its SHA256SUMS manifest passes and RUN.json parses as valid JSON.

The run record matches the separately accepted pre-execution review SHA-256 7a29a359240fe715c5ec9405c551dfc31ab40f90c39755205f616387d1b0adf4. The fixture transaction SHA-256 is 8eb0a4f8b11c30231d1788ab3399823a542c7ae86e75bc1902aa452f527f0f4b, identical to the pre-reviewed positive-control transaction. Raw-input and raw-output hashes also match the fixture: 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec and fccf32f91dd3541e33bdb9a92f61ab002bdf93ba7275a270101c70309fa044b9.

Recorded execution evidence:

- Immutable R3 runner SHA-256 is 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c, matching the current runner source. Pinned Aiken SHA-256 is 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- Wrapper exit is 0 at both invocation and runner-result levels. Simulator child exit is 0.
- Stage is script_accepted and target_script_invoked is true. The current classifier source requires the expected transaction ID, script-context/Mint[0] invocation, and a successful resource result with no traces for this stage.
- The runner source independently parses the transaction mint and Plutus V3 witness, requires one mint policy and one V3 script, hashes the script with the Plutus V3 prefix, and compares it to the expected policy ID. The recorded policy_ids, compiled_script_hash, and expected_policy_id all equal 409712d7175aa2f7d372364919d50f55a048b83c7770a646826a1df4. The pre-execution review independently recompiled and byte-matched this exact script.
- Teardown is clean: child_reaped, process_group_empty, and snapshot_descriptors_closed are true; status is clean.

Scope is correctly constrained. The record credits an accepted synthetic positive control only. It leaves negative_case null, mutation_suite false, original_policy false, ledger_admission false, and live_network false; case_status remains PENDING. No over-credit is present.

Caveat: raw simulator stdout/stderr and external attestation were not retained. This review independently verifies the structured runner result and all recorded hashes/bindings, not an external replay.

No simulator was run during this review. No fixture, STATUS, HANDOFF, or classification file was changed by this review.
