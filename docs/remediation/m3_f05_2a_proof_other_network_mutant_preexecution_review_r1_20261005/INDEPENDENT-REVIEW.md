# Independent pre-execution review: R2 other-network one-guard mutant

Date: 2026-10-05
Verdict: PASS — the exact mutant candidate is byte-consistent and eligible for one bounded simulator execution after this review.
Execution status: NOT RUN; mutant control remains PENDING. This report grants no mutation-suite, original-policy, ledger-admission, Pre-Prod, or live-network credit.

## Scope and integrity

Read-only review of the exact package docs/remediation/m3_f05_2a_proof_other_network_mutant_r1_20261005/r2_signature_for_other_network/, its R21 normal negative basis, the linked R21 execution and pre-execution review, canonical source, and runner/toolchain pins. A local Python 3.12 CBOR/OpenSSL audit verified proofs, funding, bindings, and conservation. No Aiken simulator, tests, or build ran. No candidate, source, STATUS, or HANDOFF files were edited; only this review and SHA256SUMS were written.

Family and case SHA256SUMS checks passed for every listed file. Exact identities:
- FAMILY-MANIFEST.json SHA-256: 8a491a5fff602d324aa90ff626f2ac841870f3e2db254195c36ec955b64bd4b4
- family SHA256SUMS SHA-256: 36a4e0e97e4484674bed51b1d94f62d5bf786d32a8d2bb941078c475369624c0
- FIXTURE-MANIFEST.json SHA-256: da3ceecf49d0df01b35cff33adca4406cb99350bb324943a364064bd22bf46be
- case SHA256SUMS SHA-256: 0c4a9a9825b12539b7481f94db9be4cb97175a16a0eb2626772aad4aa16f75c0
- SOURCE-MUTATION.patch SHA-256: 0c11a07b9047df4dd760fe98e26e929ab3118a31e7846a558c7ac12cc8e05e4d

R21 normal negative RUN.json SHA-256 is e31385db7d8c0e0b7ebc4610298813ed66373a59a736109d354db4addc9ec179 and its checksum file passes. The linked R21 negative independent review SHA-256 is ffa6066975cb41f950a0d6d601e2fe18384c37055ba212ba179243717d97d0fe. The normal-pair pre-execution review SHA-256 is 39abbb7d2a066b88604fdff52ed5a5c92409c53a92c8175278aaa5c95599118b; its checksum passes.

## Source mutation and exact R21 reuse

The canonical source cardano/lib/vams/f05_authority.ak hashes to the manifest's normal-source SHA-256 657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3. An in-memory replacement occurs exactly once: bytearray.from_int_big_endian(1, 4) becomes bytearray.from_int_big_endian(0, 4) in authority_genesis_pop_preimage. The resulting in-memory source SHA-256 matches the mutant-source identity 4e664296a620d1703e3319d25304793ce2c90ed00e0bac1bd594cd45280313bf. No source file was changed. The mutation is limited to the expected network_magic field; all other guards and Ed25519 verification remain.

The mutant package's preserved r21-negative transaction, policy bytes, seed/key parameter CBOR, proof-message bytes, and raw-input snapshot compare byte-for-byte with the R21 normal-policy negative fixture. The original proof-message SHA-256 is 87b2d24f30ca078e33b98f6d34616d91be975e32643655f7a34466afd0731c7f; raw-input SHA-256 is 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec. The exact five R21 negative PoP signatures are reused in the mutant redeemer.

## Compiled identity, proof, funding, and conservation

The R21 normal applied script is 3467 bytes, SHA-256 bd3bbef9e5ce973e4c20ec1f4c898730a3ec9ba4503c1d6d196f02e71b4ab9c1; derived V3 policy ID is 13a2712cbc7b1c6f7cf48f7c3decd50b9c13e7837bd4cfc8865f496a. The mutant applied script is 3467 bytes, SHA-256 04510ae61ebef381e23dab53913142678d33b1145c9c7594a37c1d3ecf7cbc00; derived V3 policy ID is 1283ba4e5c442925fb9d6d26c3376f3fdb756d091c744fdd9ccd10e7. In each transaction, the sole mint policy equals that fixture's derived applied ID and its Plutus V3 witness hash equals the same ID. Normal and mutant compiled artifacts differ; the state-validator hash remains b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66.

The builder source and manifest record normal and mutant compilation using pinned Aiken 1.1.21+42babe5. The pinned Aiken executable hash was independently checked: 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. Compilation was not rerun because this is a pre-execution review and no build was authorized. Runner hash is 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c; pinned Python is 3.12.14 with executable hash aa01d96348989f33ed998b42c83e98593b41dba83914d9899730b90c36f2e5c9; OpenSSL is 3.5.5.

All five ordered applied-key PoPs independently verify against the exact R21 network-magic-0 message for both normal and mutant transactions. The mutant has two fresh funding witnesses; both verify over its final transaction body hash 112a0411bf85080838173617584a6534abc61b8606576d7b0a95cfefa99ce80b, and their public keys match the two consumed synthetic UTxO credentials. The raw-input references remain exact R21 bytes. The mutant body is semantically identical to the R21 negative body after substituting the mutant policy ID back to the original policy ID; only the required policy/output-asset rebinding changes. Mutant raw outputs use fresh ephemeral funding-key credentials.

Normal and mutant value accounting passes independently: 17,000,000 lovelace inputs = 16,000,000 outputs + 1,000,000 fee; the authority output is 10,000,000 and change is 6,000,000. Exactly one authority NFT under the respective policy is minted and conserved; collateral is absent. The package contains only public keys/signatures/CBOR and source-diff evidence; no private keys are persisted.

## Disposition

This package passes independent pre-execution byte review and is eligible for one bounded R3 simulator attempt using only the exact reviewed bytes. Its manifest correctly remains tx-sim-not-run, status PENDING, and credit null. Execute the accepted mutant positive control only after this review; any failure before Mint[0] invocation must stop the slice. A later mutant acceptance would support attribution of the R21 network-magic negative only after independent post-run review. No mutation-suite credit is inferred. Evidence is synthetic alternate-applied-policy scope only.