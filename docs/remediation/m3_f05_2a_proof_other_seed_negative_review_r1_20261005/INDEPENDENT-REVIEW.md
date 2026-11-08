# Independent review: R18 negative execution for r2_signature_for_other_seed

Date: 2026-10-05  
Verdict: **PASS for execution integrity and compiled Mint[0] rejection; FAIL/PENDING for named-condition attribution.**  
Case disposition: **PENDING** under R4.1 proof-domain decision B. R18 does not earn negative-case credit.

## Scope and method

Read-only review of the checksummed R18 record; exact R2 case fixture and manifests; linked pre-execution byte review; R17 positive attempt and independent review; R3 runner and validator guard/source. No simulator, mutant, or test was executed in this review. No fixture, STATUS, or HANDOFF file was changed. The only write is this standalone independent review record.

## Integrity, fixture, and positive-control reconciliation

- In `docs/remediation/m3_f05_2a_proof_other_seed_negative_attempt_r1_20261005`, `sha256sum -c SHA256SUMS` reported `RUN.json: OK`. R18 RUN SHA-256: `2f3d042cd4350d821b0ce91dafa4cddfdb36dc23258eefb6115b947fd764b0be`; attempt SHA256SUMS SHA-256: `5a1fc8560b6d35769d61be2138a8c1bfafd50116f1b308a66de1808437ea58f7`.
- In the R2 case directory, `sha256sum -c SHA256SUMS` reported all 15 fixture entries OK. Case checksum-file SHA-256: `eccecac05b6fb9c8cd392858ff915f45cbcbf1ab4dbd5ddf6235132882f43397`; family checksum-file SHA-256: `21fd17528569dd8ed2dddd6c7b744c621b988c8c9a45a723e68bce5abddcceb0`; case manifest SHA-256: `d993a5d09ad5a4b533e6d6d571507b8dab15c920667b0a0fd3798d73a47661fb`.
- R18 transaction/input/output/proof-message hashes match the negative fixture bytes: `53526ecc1282cb83aaf9690a74c422361f25c4229da1378bbc68d8e78405534b`, `5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec`, `c4ba70814b665c3fc0133e8c3ea4d253f27613716209da83113dd1ab9ec59048`, and `5fa13e0c6240b7b75d154f152de2bf376f93d2af3dd8642c7d25f4757e2a8542`.
- The linked pre-execution review SHA-256 matches `a17bde02f3516516a548c1a91de9534f130278e595303e4aee048d6b19b1287a`; its case manifest confirms both positive and negative PoP sets (5/5 each) and body-bound funding witnesses (2/2 each) verify, ADA/native value is conserved, and no private keys persisted. The exact message differs only in the seed hash at bytes 48–79: positive uses `ab` repeated 32 bytes, negative signatures use `ad` repeated 32 bytes. The applied policy parameters, datum, and transaction body retain seed `ab`.
- The linked R17 positive attempt checksum passed and its RUN SHA-256 matches R18’s reference: `f9a86dca6d7fed12a92fb2afb59ac77836c6b963b178403f0ef77b8c9494992f`. The independent positive-review SHA-256 also matches R18: `fb4d688f9b2aabce99665ed108d330174dd7b1af0d89c1267e59681c7df1e81c`. R17 accepted the positive proof fixture at the same synthetic applied policy and transaction-body hash `432b080980a2e5326fd3751f3b269eb6dc2c8b1d58074f72afbf0be6109ebd11).

## Execution and policy binding

R18 records wrapper exit 0, child exit 1, `stage=compiled_evaluation`, `target_script_invoked=true`, and clean cleanup (child reaped, process group empty, snapshot descriptors closed). The pinned runner hash is `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c`; the pinned Aiken executable hash is `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79` (Python 3.12.14; Aiken 1.1.21+42babe5). The applied script hash is `9136d96103775a3140a77ae53ca0bc8e2bbb70265ae7aa732dad75cfcc68a170`, with policy ID `4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76`. R18 reports that expected policy ID, sole transaction mint policy, and compiled V3 witness hash agree.

The immutable R3 runner binds exactly one transaction mint policy to its compiled V3 script hash. The frozen case manifest identifies the intended entrypoint as `f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]`. Therefore this record supports a clean rejection during evaluation of the intended compiled Mint[0] script under the synthetic applied policy.

## Attribution finding and mutant eligibility

R18’s `compiled_evaluation` stage is generic: it establishes that the target compiled script was invoked and rejected, but does not identify which validator assertion failed first. It is not equivalent to a named-condition result. The source validates multiple earlier conditions before `valid_bootstrap_proofs(..., bootstrap_message)`; the fixture and R17 positive control make the proof-domain guard the expected failing condition, but that remains source/fixture inference, not recorded compiled first-failure evidence. R18 itself labels named-condition attribution as pending. Thus it does not establish rejection attributable to `sign_same_tuple_with_alternate_seed`, and the original case remains PENDING.

A separately rebound, one-guard signature-domain mutant is **eligible for preparation and independent pre-execution byte review**, not for execution based on this review alone. Its reviewed bytes must show exactly one narrowly scoped change to the seed-domain proof guard, recomputed applied script/policy and transaction Mint[0] binding, preservation of every other validator condition, and an accepted mutant control at the intended Mint[0]. A successful mutant run plus independent post-run review would then support attribution to the named seed-domain guard. No mutant was executed here, and this eligibility is not credit.

## Scope limits

Evidence is synthetic and tied only to alternate applied policy `4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76`. R18’s capture note says raw simulator stdout/stderr and external attestation were not retained. No original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit is granted. F05/M3 remains open; deployment and gated activations remain disabled.