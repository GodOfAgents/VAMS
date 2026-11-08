# Independent epoch negative-attempt review

Review id: m3_f05_2a_proof_other_epoch_negative_review_r1_20261005
Outcome: PASS for attempt integrity only; named epoch attribution withheld
Case: r2_signature_for_other_epoch

The RUN.json SHA-256 is 02ac3c54834047e6a0fedb1b107bec7e37539b5b07ad0cd63998f936b1509d01; its adjacent SHA256SUMS verifies. The submitted transaction, raw input, and raw output hashes match the exact negative fixture bytes. Transaction SHA-256 is 38bbf76af57957881095dc42a0004ab1caa8a4a43065228066dbd7407eaa37f3.

The wrapper exited 0 and simulator child exited 1. The structured result is generic compiled_evaluation with target_script_invoked true at the R3 runner boundary. This does not identify which validator condition failed and does not by itself establish that the nonzero-epoch condition caused rejection.

The expected policy id, sole transaction policy id, and compiled script hash all match 704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad. Runner and pinned Aiken hashes match their executable bytes. Cleanup reports child reaped, process group empty, snapshot descriptors closed, status clean.

The attempt links the pre-execution byte review SHA-256 73bad0f80d3d4f137f1d00987c5294ff893994beb134e292fd4e6c5d4c6eb073 and the positive-control review SHA-256 24fd754d809519e81601c17ce96cace9d5cb23b9c62e4f4c0f2eb0822a683377. The pre-execution review verified final-body-bound ephemeral funding signatures, ADA and NFT conservation, exact policy/mint/V3 binding, and no persisted private keys. This attempt matches those reviewed fixture bytes.

No negative-case credit is assigned here. The case remains pending independent attribution through the planned same-negative one-expression mutant triad. Mutation-suite, original-policy, ledger-admission, and live-network credit remain false. Evidence is synthetic under an alternate applied policy only.

Evidence limitation: raw simulator stdout/stderr and external execution attestation are not retained; this review relies on the structured R3 result, exact submitted hashes, pinned runner/tool hashes, target mint binding, linked fixture review, and clean teardown. No transaction was run during this review, and no status or classification record was edited.
