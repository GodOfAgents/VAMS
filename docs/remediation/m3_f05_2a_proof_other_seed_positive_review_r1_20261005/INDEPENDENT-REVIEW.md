# Independent review: R17 positive control for r2_signature_for_other_seed

Date: 2026-10-05  
Verdict: **PASS — recorded synthetic positive-control execution is internally consistent.**  
Case disposition: **PENDING**. This review credits only the accepted synthetic alternate-policy positive control. It does not accept the negative case or grant original-policy, ledger-admission, Pre-Prod, or live-network credit.

## Scope and method

Read-only review of R17 `RUN.json`, its checksum file, the R2 fixture bytes and checksum manifests, the linked independent pre-execution byte review, and the exact R3 runner source. No simulator or test was run. No fixture, status, or handoff file was changed.

## Integrity and binding

The following checks passed:

- In `docs/remediation/m3_f05_2a_proof_other_seed_positive_attempt_r1_20261005`, `sha256sum -c SHA256SUMS` reported `RUN.json: OK`. RUN SHA-256: `f9a86dca6d7fed12a92fb2afb59ac77836c6b963b178403f0ef77b8c9494992f`; its SHA256SUMS SHA-256: `7e52358c8f17272fa94407cace60b640c29186571237bd8087cb218255dec8d9`.
- In the case directory, `sha256sum -c SHA256SUMS` reported all 15 entries OK. The family `SHA256SUMS` SHA-256 is `eccecac05b6fb9c8cd392858ff915f45cbcbf1ab4dbd5ddf6235132882f43397`; parent family manifest SHA-256 is `21fd17528569dd8ed2dddd6c7b744c621b988c8c9a45a723e68bce5abddcceb0`. `FIXTURE-MANIFEST.json` SHA-256 is `d993a5d09ad5a4b533e6d6d571507b8dab15c920667b0a0fd3798d73a47661fb`.
- The R17 fixture link to pre-execution review matches the present reviewed report SHA-256 `a17bde02f3516516a548c1a91de9534f130278e595303e4aee048d6b19b1287a`.
- R17 transaction, raw-input, raw-output, and positive proof-message hashes match the checked case files: `040a2fb4deff2265ec1bcc6d7f5ae78170ff3a2855cb7145729fddf6d101a555`, `5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec`, `d137c61cbd332ec1d13900844e51ee075abb99fe4a9cd838d9ead465e2a6ca95`, and `dd7f979a1c9aaf8716069f6ccc7424ba9143b5c29f8ba20bf87d9d7336f95d3d`, respectively.
- The applied policy ID is `4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76`; the applied script bytes hash to `9136d96103775a3140a77ae53ca0bc8e2bbb70265ae7aa732dad75cfcc68a170`. R17 reports the expected policy, sole transaction policy ID, and compiled script hash all equal. The R3 runner hash is `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c`; the pinned Aiken executable hash is `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79` (Python 3.12.14; Aiken 1.1.21+42babe5).

The runner source extracts the transaction mint map, requires exactly one policy, checks that its compiled V3 witness hash equals the requested policy ID, snapshots the bound transaction and script inputs, and invokes the simulator. Thus the recorded accepted script is the sole compiled Mint[0] purpose in this transaction. The R17 result records wrapper exit 0, simulator child exit 0, `stage=script_accepted`, and `target_script_invoked=true`.

## Positive witness and execution result

The linked pre-execution byte review independently checked the positive fixture’s signature-domain message, all five PoP signatures, and both final-body funding witnesses; it also checked policy/V3 binding, conservation, and absence of persisted private keys. R17 uses the same positive transaction and message hashes, so this recorded run is reconciled to those reviewed bytes.

R17 records clean termination and cleanup: child reaped, process group empty, and snapshot descriptors closed. Its scope and credit fields say accepted synthetic positive control only; negative case is null, mutation suite false, original policy false, ledger admission false, live network false. It preserves case ID `r2_signature_for_other_seed` and assertion `sign_same_tuple_with_alternate_seed`.

## Limits

The R17 record captures the structured runner result transcribed from scoped execution; it does not retain raw simulator stdout/stderr or an external attestation. Acceptance here is therefore limited to the checksummed record, exact artifact hashes, runner/toolchain identity, and linked pre-execution review. The negative fixture has not been accepted by this review. Keep the original case **PENDING** until its negative execution, attribution, and independent post-run review pass. No original-policy, full-ledger-admission, Pre-Prod, or live-network credit is granted.