# Independent epoch positive-control attempt review

Review id: m3_f05_2a_proof_other_epoch_positive_review_r1_20261005
Outcome: PASS for positive-control attempt integrity only
Case: r2_signature_for_other_epoch

The attempt record RUN.json SHA-256 is 932b2a1898482efd7326a667e345e3f129a861bfe2de1218dcdad43fbaae6093; its adjacent SHA256SUMS verifies. The submitted transaction hash matches the exact pre-reviewed positive-control.tx.cbor fixture: 28818f0e4fa862fff96dfc935d0479fc81e623cdd84930b60138fd74a7829f68. Submitted raw input and output hashes also match the reviewed fixture files.

The structured record reports wrapper exit 0 and simulator child exit 0, with stage script_accepted and target_script_invoked true. Mint binding is consistent: the expected policy id, sole transaction policy id, and compiled script hash are 704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad. The record runner hash is 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c and pinned Aiken hash is 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. Both match the executable bytes. Teardown is clean: child reaped, process group empty, snapshot descriptors closed.

The RUN record links the independent pre-execution review hash 73bad0f80d3d4f137f1d00987c5294ff893994beb134e292fd4e6c5d4c6eb073. Credit remains limited to an accepted synthetic positive control under the alternate applied policy. The negative case is null; mutation-suite, original-policy, ledger-admission, and live-network credit are false. Case status remains pending the negative attempt and attribution review.

Evidence limitation: raw simulator stdout/stderr and external execution attestation are not retained; this review relies on the structured R3 result, exact submitted hashes, pinned runner/tool hashes, binding record, and teardown data. No transaction was run during this review, and no status or classification record was edited.
