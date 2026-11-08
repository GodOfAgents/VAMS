# Independent review: applied_keys_parameter positive control R10

Status: **PASS for the recorded synthetic positive-control execution; the negative case and original case remain PENDING.** This review covers the exact R10 record and bound fixture bytes only. It does not authorize or review the negative fixture.

## Evidence checked

- R10 run record: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r10_20261005/RUN.json, SHA-256 fdd13ca0572ba92c302d0e5537ee2670520570dcf25977feb39ebebaa6a3a2c9; its SHA256SUMS verification passed.
- R5 family manifest SHA-256: 3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e; R5 root SHA256SUMS SHA-256: ad27af4dd49aac3e8d0ba570468adf5c4fc32e02b5acc3303b2f40b67e5c71f0; all entries in the R5 family checksum file verified.
- applied_keys_parameter/FIXTURE-MANIFEST.json SHA-256: c9cfa8d645dcb99fa20fa9933b88190b02027f724fba3c67d081efd0c06dac24.
- Current R3 CASE-STATUS.json SHA-256: 3369c2e2ee6ef7afbf840e1aa1ca32aae39418ccba45b13c09914083f015c54e.

## Findings

1. The exact submitted positive-control transaction, raw-input vector, and raw-output vector match the R5 case manifest, including byte lengths: transaction 97f584e0f071b774883d15237042cefddff6e7b471d58329fcb5f24a08775c7d (5,104 bytes), raw inputs 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe (73 bytes), and raw outputs 37d1a506522392074de0f58ed0bf093eb181a612c9c9118d1060eae95f911ed3 (79 bytes).
2. The invocation uses the case R4.1 decision C and alternate applied policy efec0d79e496e2df81f8e3e27734c9718655dc577070c7519645fa29. The recorded expected policy ID, compiled script hash, and sole minted policy ID agree. The runner reports child and wrapper exit code 0, target script invoked at compiled Mint[0], and script_accepted.
3. Runner cleanup is recorded clean, with the child reaped, process group empty, and snapshot descriptors closed.
4. The R5 case manifest records five valid PoPs, two valid body-bound ephemeral funding signatures, ADA and native-asset conservation, and no persisted private keys for this positive control. The R10 bytes and policy binding match that reviewed fixture record. This review did not independently rederive each signature or rerun cryptographic validation.
5. The R10 record explicitly states that its structured result was transcribed locally and that raw simulator stdout/stderr and external attestation are not retained. Therefore this is a reviewed local synthetic simulator record, not independently replayed simulator output.
6. Current CASE-STATUS.json still lists applied_keys_parameter as PENDING. Its counts remain 47/55 negative cases passing (8 pending), 43/51 transaction-simulator cases passing (8 pending), and 18/21 mutations passing (3 pending). This positive control alone does not establish the negative assertion or mutation credit. It confers no original-policy, full-ledger-admission, or live-network credit.

## Decision

Accept R10 as an independently reviewed positive-control execution under the synthetic alternate applied policy only. Keep applied_keys_parameter PENDING; do not infer negative-case or mutation credit. The next negative fixture remains outside this review scope and requires its own attribution controls and independent review.
