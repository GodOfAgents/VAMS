# Independent review: R21 negative attempt for r2_signature_for_other_network

Date: 2026-10-05
Verdict: PASS for the recorded bounded execution and generic compiled-evaluation rejection only.
Case disposition: PENDING. The named wrong-network condition is not attributed by this result; retain PENDING until an independently reviewed one-guard mutant demonstrates first-failure attribution. No mutation-suite, original-policy, full-ledger-admission, Pre-Prod, live-network, or readiness credit.

## Scope and integrity

Read-only review of the checksummed R21 RUN record, exact R2 fixture/R4.1 contract, linked pre-execution review, R20 positive control and its independent review, and runner/toolchain identities. No simulator, test, or build was run; no fixture or STATUS/HANDOFF file was changed.

R4.1 contract SHA-256: 238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171. R2 family manifest SHA-256: 0d4fe66dee3ad48f59231909bd8b0599f49da72a1f15a47c29b65618a17746ed. Case manifest SHA-256: f637a4d316313e4f1fa0810b85d58cbe0c9aee093557f4cc4107f433128c402a. Original case ID and assertion remain r2_signature_for_other_network / sign_tuple_with_another_network_magic; R4.1 decision B.

R21 RUN.json SHA-256: e31385db7d8c0e0b7ebc4610298813ed66373a59a736109d354db4addc9ec179. Its SHA256SUMS SHA-256: f51d32b1799f25fb9e56dc3a13db2aa520a997d3fc7953f9343e26928caad9b9. R21 checksum passes. R2 family/case, R20 attempt, R20 review and pre-execution review checksum sweeps also pass.

## R21 recorded execution

Exact argv uses Python 3.12.14 at /home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12, runner /home/GodOfAgents/code/VAMS-testnet/scripts/remediation/f05_2a_tx_sim_runner_r3.py, pinned Aiken /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken, negative.tx.cbor, negative.raw_inputs.cbor, negative.raw_outputs.cbor, and policy ID 13a2712cbc7b1c6f7cf48f7c3decd50b9c13e7837bd4cfc8865f496a. Runner SHA-256: 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c. Aiken 1.1.21+42babe5 SHA-256: 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.

R21 records wrapper exit 0, simulator child exit 1, stage compiled_evaluation, target_script_invoked true. Expected policy ID, compiled script hash and sole transaction mint policy ID are all 13a2712cbc7b1c6f7cf48f7c3decd50b9c13e7837bd4cfc8865f496a. Applied script SHA-256: bd3bbef9e5ce973e4c20ec1f4c898730a3ec9ba4503c1d6d196f02e71b4ab9c1. Cleanup is recorded clean (child reaped, process group empty, snapshot descriptors closed). Negative tx SHA-256: 2627b7ca1d85a06adac1e957eb186f3e5fd8e69a8f0fdd7b9d81b6753c7a3065. Proof message SHA-256: 87b2d24f30ca078e33b98f6d34616d91be975e32643655f7a34466afd0731c7f. Raw input/output SHA-256: 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec / 14f8b6399c77d55fa3cf016a48b1ff47d97efa293d5e043b7d699f66d847e6c0.

This establishes rejection at compiled Mint[0], but only generic compiled evaluation, not named-condition attribution. RUN says its structured result was transcribed and raw simulator stdout/stderr and external attestation were not retained; acceptance is limited to this recorded scope.

## Cross-links and pre-execution evidence

R21 links R20 positive RUN SHA-256 f83f9efb074e5b7396d395a61154adc8d716b57a3a4193119b46e03d3e531e8a and positive review SHA-256 a86e5fe5594048f9bff65f92a4dcf6f124dfe25063578d1aeeaf21a933f6c6ff. Both match. R20 records wrapper 0, child 0 and script_accepted at compiled Mint[0], same applied/mint/V3 identity. Positive tx SHA-256: ef8fedd6dfe7f6f7b266caa8126aed1408a63fe3e04adb5ef75fe49d41ce6bbf.

R21 links pre-execution review SHA-256 39abbb7d2a066b88604fdff52ed5a5c92409c53a92c8175278aaa5c95599118b; its checksum passes. It reports five positional PoPs verified against the corresponding proof messages; two final-body-bound funding signatures verified with matching consumed-input credentials; same transaction body, inputs and outputs for controls; proof messages differ only in network magic (applied 1, negative signed 0); and ADA conservation of 17,000,000 = 10,000,000 authority output + 6,000,000 change + 1,000,000 fee. One authority NFT is conserved, with no collateral. Keys are ephemeral test credentials; no private key is persisted. R21 also records valid funding signatures, conservation, and no persisted private keys.

The R21 record correctly grants no negative-case credit and leaves the case PENDING awaiting an independently reviewed one-guard mutant. Evidence is synthetic alternate applied-policy only; no original-policy, ledger-admission, or live-network inference.

## Read-only commands

- (cd docs/remediation/m3_f05_2a_proof_other_network_negative_attempt_r1_20261005 && sha256sum -c SHA256SUMS): RUN.json OK.
- sha256sum -c SHA256SUMS in R2 family, case, R20 attempt, R20 review, and pre-execution review directories: all listed files OK.
- sha256sum over the R21 RUN/SHA256SUMS, R20 RUN/review, pre-execution review, R4.1 contract, manifests and negative/positive fixture bytes: hashes match recorded values.

No simulator, test, build, transaction, or network command was run for this review.
