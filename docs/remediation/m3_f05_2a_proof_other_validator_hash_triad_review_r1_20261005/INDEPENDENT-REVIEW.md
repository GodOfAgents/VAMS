# Independent integrated triad review

Review id: m3_f05_2a_proof_other_validator_hash_triad_review_r1_20261005
Case: r2_signature_for_other_validator_hash
Decision basis: R4.1 proof-domain choice B
Outcome: PASS for one synthetic transaction_simulator negative attribution row

## Scope and evidence

This review independently checks the retained positive control, normal-policy negative, one-expression mutant pre-execution review, and mutant attempt record. It does not execute a transaction, edit case classification, or update STATUS or HANDOFF.

The mutant attempt RUN.json SHA-256 is 7bde6d12d63430142e0ec155c48e568159122bbc9092fbed0249e30b55eb9a57; its adjacent SHA256SUMS verifies RUN.json. The wrapper and simulator child both exited 0. The structured runner result is script_accepted with target_script_invoked true and Mint[0] targeted. The expected policy id, sole transaction policy id, and compiled script hash all equal f69665acd72650e6789b38151419ac429ae83782cfffe45d91496f7b. Cleanup reports child reaped, process group empty, snapshot descriptors closed, status clean.

Submitted transaction SHA-256 is d4950fb424627e5492589643e078f2239cd2661f4133b7d6276a978b097b7821. Raw input and output SHA-256 values are 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec and a3993e8db5134ee6ae9329a366ae66d6706a08ac3174720317359d85faa4cefd. These match the reviewed mutant fixture bytes. Runner SHA-256 is 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c. Pinned Aiken SHA-256 is 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.

The pre-execution review SHA-256 is 6880c4be08b833e41796c0a4dba4203f4ee9615e525883d31db315712ab0d890. It reviewed the one-expression source mutation to the state-validator-hash argument of authority_genesis_pop_preimage, unchanged canonical output guards, the rebuilt mutant policy/mint/V3 binding, and the transaction fixture. It also verified the same wrong-hash PoP message, signatures, and input/state references as the normal-policy negative; fresh ephemeral funding signatures bound to the final body; and value/NFT conservation. The targeted five-test suite and independent build passed as recorded in that pre-execution review. Policy rebinding necessarily changes the policy id and V3 witness/body hash; fresh ephemeral funding keys also change resolved funding outputs. Those expected differences do not alter the PoP message/signatures or input/state semantics under test.

The normal-policy negative RUN.json SHA-256 is 5e89f1f022fcb11e3e6311cb13c0bb3bdb7821b8e44d97863d991f5673ce86c0; its separate attempt review SHA-256 is e6c7e441db3a25392f49f44a25af158fb465ff1df17118172e56b6c935cf3e3d. Its generic compiled_evaluation result alone did not establish named-condition attribution. The original-policy positive-control RUN.json SHA-256 is 18b04228b885bc428441aab701fa100f7dd280d53efd4a87d4fef4b3375d1e6d; its independent review SHA-256 is 5d31f9251a73343eef9d8641031bd80691582b8d471caeabf2a02f69a6bd4bed. The positive control is accepted only for its original applied policy.

## Attribution and limits

The triad supports exactly one negative row for r2_signature_for_other_validator_hash under the synthetic transaction_simulator evidence class: the wrong-hash proof fails in the normal-policy attempt, while the single-condition PoP-preimage mutant accepts the same proof/message/signatures and state/input references under its separately compiled and consistently rebound alternate policy. The original-policy positive control establishes that the harness can accept the valid control. Attribution relies on the reviewed compiled mutant and structured runner result, not on a generic failure label.

This grants no mutation-suite credit. It grants no original-policy negative, full-ledger admission, Cardano Pre-Prod, or live-network credit. No deployment readiness is implied. No classification, STATUS, or HANDOFF record is changed by this review.

The retained RUN record captures the exact structured R3 result but not raw simulator stdout/stderr or an external execution attestation. The execution claim is therefore limited to the immutable input hashes, pinned tool/runner hashes, structured exit/result and target binding, and clean teardown retained in the record.
