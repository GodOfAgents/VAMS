# Independent integrated review: R20/R21/R22 other-network proof triad

Date: 2026-10-05
Verdict: PASS for exactly one synthetic `transaction_simulator` negative row for `r2_signature_for_other_network` under R4.1 choice B. R21 rejection plus R22 same-negative one-guard mutant acceptance attributes the original assertion at compiled Mint[0]. No mutation-suite credit. Original-policy, ledger-admission, live-network, and readiness credit remain false.

## Scope and integrity

Read-only review of R4.1, R2 positive/negative fixtures, R20 positive, R21 normal-policy negative, R22 one-guard mutant package/attempt, and linked pre/post reviews. No simulator, test, build, or transaction was run for this review; no source, fixture, STATUS, or HANDOFF file was changed.

`sha256sum -c SHA256SUMS` passed for all three attempt directories, mutant family and case packages, and linked R20 positive, R21 negative, R2 paired pre-execution, and R22 mutant pre-execution review directories. Key identities:

- R20 RUN.json `f83f9efb074e5b7396d395a61154adc8d716b57a3a4193119b46e03d3e531e8a`; positive review `a86e5fe5594048f9bff65f92a4dcf6f124dfe25063578d1aeeaf21a933f6c6ff`.
- R21 RUN.json `e31385db7d8c0e0b7ebc4610298813ed66373a59a736109d354db4addc9ec179`; negative review `ffa6066975cb41f950a0d6d601e2fe18384c37055ba212ba179243717d97d0fe`.
- R22 mutant RUN.json `364d859090a4d80549a63bb57b04b0f36d1d89b967cc5707e3dc784c79315eaa`.
- Mutant package FAMILY-MANIFEST.json `8a491a5fff602d324aa90ff626f2ac841870f3e2db254195c36ec955b64bd4b4`; FIXTURE-MANIFEST.json `da3ceecf49d0df01b35cff33adca4406cb99350bb324943a364064bd22bf46be`; package SHA256SUMS `36a4e0e97e4484674bed51b1d94f62d5bf786d32a8d2bb941078c475369624c0`.
- R22 pre-execution review `1d92f77fcd16b90c19ebb1330f46aa7175eea84b74e635f89120b7a0cf07b6f7`; paired normal pre-execution review `39abbb7d2a066b88604fdff52ed5a5c92409c53a92c8175278aaa5c95599118b`.
- R4.1 contract `238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171`.

R4.1 preserves case `r2_signature_for_other_network`, assertion `sign_tuple_with_another_network_magic`, and verifier property `valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message)`. Choice B allows same-negative one-guard mutant attribution with its own applied-policy/mint/V3 rebinding, for synthetic parameter-bound transaction simulation.

## Triad and attribution

R20 records wrapper/child exit 0, `script_accepted` at invoked compiled Mint[0], and clean cleanup. Positive transaction SHA-256 `ef8fedd6dfe7f6f7b266caa8126aed1408a63fe3e04adb5ef75fe49d41ce6bbf`; applied policy, sole mint policy, and Plutus V3 witness hash all bind to `13a2712cbc7b1c6f7cf48f7c3decd50b9c13e7837bd4cfc8865f496a`.

R21 records wrapper exit 0, child exit 1 at `compiled_evaluation`, target invoked at Mint[0], generic rejection, and clean cleanup. Transaction SHA-256 `2627b7ca1d85a06adac1e957eb186f3e5fd8e69a8f0fdd7b9d81b6753c7a3065`; proof-message SHA-256 `87b2d24f30ca078e33b98f6d34616d91be975e32643655f7a34466afd0731c7f`; raw-input snapshot SHA-256 `5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec`. Applied policy/mint/V3 bind to `13a2712cbc7b1c6f7cf48f7c3decd50b9c13e7837bd4cfc8865f496a`.

R22 records wrapper/child exit 0, `script_accepted` at invoked Mint[0], and clean cleanup. It uses the exact R21 network-magic-0 proof message/signatures, transaction body context, raw inputs, and negative semantics. The reviewed in-memory source mutation removes only the network-magic guard (1→0). Mutant script SHA-256 `04510ae61ebef381e23dab53913142678d33b1145c9c7594a37c1d3ecf7cbc00`; policy/mint/V3 ID `1283ba4e5c442925fb9d6d26c3376f3fdb756d091c744fdd9ccd10e7`; transaction SHA-256 `01dfefa7f51d227cd1cedecd9811244c3a27bd50675868450a75d320647d1c9f`; final body hash `112a0411bf85080838173617584a6534abc61b860657d7b0a95cfefa99ce80b`. Its raw inputs retain R21 context; outputs are rebound to the mutant policy and ephemeral funding credentials.

The pre-execution reviews verify five positional PoPs and that the only proof-message difference is network_magic bytes 43–46 (1 versus 0). Both mutant funding signatures verify over its final body hash and consumed synthetic-input credentials. Conservation is 17,000,000 lovelace inputs = 16,000,000 outputs + 1,000,000 fee; one authority NFT is conserved; no collateral or private keys persisted. R20/R21/R22 cleanup is recorded clean.

All three records use pinned R3 runner SHA-256 `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c` and pinned Aiken v1.1.21+42babe5 SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`. Structured results are transcribed; raw simulator stdout/stderr and external attestation are not retained. Conclusion is limited to checksummed synthetic simulator evidence and does not imply ledger admission.

## Credit boundary

R20 is the accepted positive control. R21 rejects at the unmodified compiled target but alone does not attribute the named guard. R22 accepts the exact R21 negative under the one-guard mutant with its own compiled policy identity and transaction binding. Together with independent pre-execution byte review, this meets R4.1 choice B for exactly one synthetic `transaction_simulator` negative row. R22 is attribution evidence, not a mutation-suite test. No original-policy, full-ledger-admission, Cardano Pre-Prod, live-network, or readiness credit is supported.

Read-only commands: `sha256sum -c SHA256SUMS` in the three attempt, mutant package/case, and linked review directories; all listed files verified OK. No simulator, test, build, source, fixture, STATUS, or HANDOFF edit was performed.
