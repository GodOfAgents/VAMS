# Independent review: applied_keys_bad_count R13 positive control

Review result: PASS for the R13 positive-control run record and its narrow synthetic evidence scope. This review does not approve or evaluate a bad-count negative execution.

## Evidence checked

- R13 record: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r13_20261005/RUN.json, SHA-256 3a6034236b53372f7c0417ab22ee2acd726cadaef0ac19637cc14d8ccb5120db.
- R13 record checksum entry verifies against its SHA256SUMS.
- R5 family SHA256SUMS: SHA-256 ad27af4dd49aac3e8d0ba570468adf5c4fc32e02b5acc3303b2f40b67e5c71f0; all 98 family entries verify when checked from the family directory.
- Selected applied_keys_bad_count fixture manifest: SHA-256 ccb48ebdf61669d2cd07e06ebd62832b72bc4f06f92e5e476c74c7a0479174c3; all 12 selected fixture-file checksum entries verify.
- R13 positive transaction SHA-256 80c6aeeb5175820f33607b35eeed626de60342eead2a557bbac091aa9820b74a; raw inputs SHA-256 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe; raw outputs SHA-256 2d85e9be4a4d2faee992d5a18ba6ff15527940129499d54ddc080f24f7c65184. All match the selected R5 manifest.

## Findings

R13 invokes the immutable R3 transaction-simulator runner with the selected R5 positive-control transaction and exact positive applied policy ID 96d26910aa178410831ade31fd6ab668bb91392d9f2b07b30a6c0892. The captured result reports wrapper exit 0, simulator child exit 0, stage script_accepted, target script invoked, and expected policy, compiled script hash, mint policy ID, and V3 policy ID bound to that same ID. Cleanup reports child reaped, process group empty, snapshot descriptors closed, and clean status.

The reviewed R5 fixture manifest records five strictly increasing unique 32-byte positive-control keys and five PoP proof signatures; two valid ephemeral funding signatures bound to the final transaction body; ADA and native-asset conservation; and no persisted private keys. Positive-control tx, input, output, and applied-policy byte hashes match the manifest and R13 capture. The family package was independently byte-reviewed before this execution; this review verifies the exact referenced package checksums and selected case evidence.

R13 is only the accepted positive control. It did not execute the six-key negative case or a mutant. It therefore does not resolve the compound-arity attribution blocker and grants no negative-case or mutation credit. applied_keys_bad_count remains PENDING. The record explicitly grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. This is local synthetic alternate-applied-policy transaction-simulator evidence only. Raw simulator stdout/stderr and external attestation are not retained, as disclosed by the record.

## Review limits

This is a read-only independent review of the R13 record, immutable R5 package bytes, prior exact-byte review basis, and current case status. The simulator was not rerun. No status or classification file was changed. F05/M3 remains open; readiness remains NOT READY; deployment and gated activations remain disabled.
