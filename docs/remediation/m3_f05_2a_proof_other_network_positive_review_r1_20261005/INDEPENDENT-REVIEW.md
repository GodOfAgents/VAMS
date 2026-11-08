# Independent review: R20 positive control for r2_signature_for_other_network

Date: 2026-10-05
Verdict: PASS for the recorded synthetic positive-control attempt and its exact-byte pre-execution review.
Case disposition: PENDING. This review accepts only a positive-control run. It grants no negative-case, mutation-suite, original-policy, ledger-admission, Cardano Pre-Prod, live-network, or readiness credit.

## Scope

Read-only review of the checksummed R20 RUN.json, exact R2 family/case fixture, linked pre-execution byte review, and pinned R3 runner/toolchain identities. No simulator, transaction, test, or build was run. No fixture, source, STATUS, or HANDOFF file was changed.

## Integrity and linked review

The following checksum checks passed:

- Family package `docs/remediation/m3_f05_2a_proof_domain_family_r2_20261005/SHA256SUMS`: FAMILY-MANIFEST.json, SUMMARY.md, and all listed case fixture entries verified OK.
- Case directory `.../r2_signature_for_other_network/SHA256SUMS`: all 15 fixture entries verified OK.
- Pre-execution review directory SHA256SUMS: INDEPENDENT-REVIEW.md verified OK.
- R20 positive attempt directory SHA256SUMS: RUN.json verified OK.

Exact record identities:
- R20 RUN.json SHA-256: `f83f9efb074e5b7396d395a61154adc8d716b57a3a4193119b46e03d3e531e8a`; its SHA256SUMS SHA-256: `f8122de183bb254cacd9f1548b15d2dbb469076aad60d0ee714b7b72098ef1e6`.
- Pre-execution INDEPENDENT-REVIEW.md SHA-256: `39abbb7d2a066b88604fdff52ed5a5c92409c53a92c8175278aaa5c95599118b`; its SHA256SUMS SHA-256: `2e5eaf85ea12b7c16c82560efc08d0dad51eb8a6b06b46f9038b5490799c7e82`.
- FAMILY-MANIFEST.json SHA-256: `0d4fe66dee3ad48f59231909bd8b0599f49da72a1f15a47c29b65618a17746ed`.
- Case FIXTURE-MANIFEST.json SHA-256: `f637a4d316313e4f1fa0810b85d58cbe0c9aee093557f4cc4107f433128c402a`.

R20 references the same pre-execution review SHA. The reviewed case ID is `r2_signature_for_other_network`, original assertion `sign_tuple_with_another_network_magic`, R4.1 proof-domain decision B, expected entrypoint `f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]`. The case manifest preserves both control statuses as PENDING pending execution/review; R20 does not itself change that disposition.

## Exact positive fixture and R20 result

R20 argv names the following positive-control files under the R2 case directory. Independently computed SHA-256 values match the R20 submitted hashes and the pre-execution review:

- Transaction CBOR: `ef8fedd6dfe7f6f7b266caa8126aed1408a63fe3e04adb5ef75fe49d41ce6bbf`.
- Raw inputs: `5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec`.
- Raw outputs: `14f8b6399c77d55fa3cf016a48b1ff47d97efa293d5e043b7d699f66d847e6c0`.
- Positive proof message: `2c5f7c1630f8f8589ba81cc726b1bc4e796ae18158d146245295389f9d217d27`.
- Applied policy script CBOR: `bd3bbef9e5ce973e4c20ec1f4c898730a3ec9ba4503c1d6d196f02e71b4ab9c1`.

R20 records wrapper exit 0, simulator child exit 0, `script_accepted`, and target invocation true. Cleanup is `clean`: child reaped, process group empty, snapshot descriptors closed. The R3 result records expected policy ID, sole transaction mint policy ID, and compiled V3 witness script hash all equal to `13a2712cbc7b1c6f7cf48f7c3decd50b9c13e7837bd4cfc8865f496a`. The pre-execution review independently computed the Plutus V3 hash from the exact applied script and confirms the same binding. Thus the recorded result is acceptance at the intended compiled Mint[0] for the exact reviewed positive bytes.

The exact argv in RUN.json invokes Python 3.12.14, `scripts/remediation/f05_2a_tx_sim_runner_r3.py` (SHA-256 `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c`), and pinned Aiken 1.1.21+42babe5 (binary SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`). This attribution is to the checksummed structured runner record: its capture note states raw simulator stdout/stderr and external attestation were not retained.

## Proofs, funding, conservation, and scope

The linked pre-execution byte review independently audited the exact candidate bytes using local Python 3.12 CBOR/OpenSSL verification without invoking simulator, tests, or a build. It verified all five positional Ed25519 PoPs against the positive 279-byte applied-network message, two final-body-bound funding signatures and their resolved input credentials, and exact conservation. The positive applied tuple uses network_magic 1; signatures are ephemeral test credentials only. No private-key material is present or persisted.

Conservation recorded by that review: 17,000,000 input lovelace = 10,000,000 authority output + 6,000,000 change + 1,000,000 fee. No native assets are in resolved inputs; exactly one authority NFT under the case applied policy is minted and conserved in the authority output; no collateral is present.

Evidence scope is synthetic test-only alternate applied policy. This is not the wrong-network negative attempt, does not establish named-condition rejection, and earns no negative-case or mutation-suite credit. Original-policy, full-ledger-admission, Cardano Pre-Prod, live-network, and readiness credit remain false.

## Read-only commands and results

- `sha256sum -c SHA256SUMS` in the family directory: all family/case artifacts verified OK.
- `sha256sum -c SHA256SUMS` in the R2 case directory: all 15 fixture entries verified OK.
- `sha256sum -c SHA256SUMS` in the pre-execution review directory: review verified OK.
- `sha256sum -c SHA256SUMS` in the R20 attempt directory: RUN.json verified OK.
- `sha256sum <R20, pre-execution review, manifest, transaction/context/proof/script, runner, Aiken files>`: hashes matched the values recorded above and the R20/pre-execution cross-references.

No simulator, transaction, build, test, or network command was run during this independent review.
