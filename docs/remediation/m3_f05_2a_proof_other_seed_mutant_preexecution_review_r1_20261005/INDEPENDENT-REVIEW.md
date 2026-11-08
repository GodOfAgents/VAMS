# Independent pre-execution review: R18-bound seed-domain mutant

Date: 2026-10-05  
Verdict: **PASS — condition-isolated mutant candidate is eligible for one controlled simulator execution.**  
Execution status: **NOT RUN**. This review grants no case, mutation-suite, original-policy, ledger-admission, Pre-Prod, or live-network credit.

## Scope and method

Read-only review of the exact mutant package, its checksums, source diff, builder and structural-verifier source, R18 attempt and independent review, and original R2 fixture. Independently reproduced the normal and mutant Aiken compilation in temporary storage using the pinned executable; independently decoded the mutant transaction, verified its final-body funding signatures and value conservation. No simulator or package test was run. No fixture, source, STATUS, or HANDOFF file was changed. Only this standalone review report and checksum were written.

## Checksum and provenance results

- In `docs/remediation/m3_f05_2a_proof_other_seed_mutant_r1_20261005`, `sha256sum -c SHA256SUMS` reported `FAMILY-MANIFEST.json: OK`.
- In its `r2_signature_for_other_seed` case directory, `sha256sum -c SHA256SUMS` reported all 15 entries OK. Case `SHA256SUMS` SHA-256: `157c73633aaed51d911e86a624b4807914328f8c67bf914a487274c8a6deda47`; `FIXTURE-MANIFEST.json` SHA-256: `7f1aabbecfa0eb42094e916043e037644db813dfe117249a5ed6ddf794320291`; parent `FAMILY-MANIFEST.json` SHA-256: `d2fd6ca522894dbb8274a87d7ef395c7b0e16e74e9761ab2cf44e29abca0e697`.
- The package’s R18 RUN reference matches SHA-256 `2f3d042cd4350d821b0ce91dafa4cddfdb36dc23258eefb6115b947fd764b0be`; its independent-review reference matches `a2d5d636cf1489341cc61ba30e0c7b638da223958a785219dfb6c016d1a61460`.
- Builder SHA-256: `d18cb0236d6ab8b9836a818ff4905ea8faec72a81a1212c1f0dc6d2ae6e13154`. Structural verifier SHA-256: `73d9bfa1cc1f8073f64ae0577d871bf42c2f87084b93acd98a1ae8d9e7ca92f8`. These sources were inspected, not executed.
- The package preserves case ID `r2_signature_for_other_seed`, assertion `sign_same_tuple_with_alternate_seed`, R4.1 decision B, and targets `f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]`.

## Exact condition change and compiler reproduction

The package’s `SOURCE-DIFF.patch` changes only the first argument to `authority_genesis_pop_preimage`: the applied `genesis_ref` is replaced in that proof-message call by a fixed alternate transaction ID `ad…ad` and the same output index. No other validator expression changes. The normal seed-input guard, datum/state validation against applied seed `ab…ab#7`, key count/order checks, asset/output checks, and Ed25519 signature verification remain. This isolates the proof signature’s seed domain from the authority state and applied policy seed.

The following read-only checks passed:

- In a `TemporaryDirectory`, I called the existing deterministic compile helper with the case’s five applied keys and seed parameter `ab…ab#7`. Normal compiled bytes exactly equal R18’s applied script: SHA-256 `9136d96103775a3140a77ae53ca0bc8e2bbb70265ae7aa732dad75cfcc68a170`; policy ID `4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76`.
- I copied the source tree into temporary storage, applied the exact one-argument diff, verified the resulting source equals the packaged `mutant-policy-source.ak`, and compiled it with the same parameters. Bytes exactly equal the packaged mutant script: SHA-256 `1604b940210dc739ca5a6ae42ec74aa49d2e808380c05191c37a3c50f7983532`; derived Plutus V3 policy ID `08cbd325cfc8dfa702de69a77ab5564b5bc71ce8f94fde2021312fdb`. The state-validator hash remained `b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66`.
- The compiler executable was the pinned Aiken 1.1.21+42babe5 binary, SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`. Temporary compilation completed; no build output was written into the repository.

Thus both normal R18 compilation and the separate rebound mutant script/policy identity reproduce exactly.

## Preserved R18 proof inputs and mutant binding

The mutant package preserves R18’s applied parameter CBOR hash `d3c9a2aeb2a47eecd7e004bb5c65cd569b9a569b6980ca5e752f48a07996cc9e`, five public keys, exact five PoP signatures, and exact 279-byte negative proof message (SHA-256 `5fa13e0c6240b7b75d154f152de2bf376f93d2af3dd8642c7d25f4757e2a8542`). The packaged mutant proof-message bytes and all five Mint[0] PoP signatures compare byte-for-byte equal to R18. The pre-execution review for R18 independently verified these five signatures against the alternate `ad…ad#7` message; no new or persisted signing keys are involved.

The transaction is rebound to the mutant policy: its sole mint-map policy ID is `08cbd325cfc8dfa702de69a77ab5564b5bc71ce8f94fde2021312fdb`; its sole Plutus V3 witness is exactly the mutant applied script bytes; and the Mint[0] redeemer remains the R18 bootstrap redeemer. The mutant transaction SHA-256 is `e57b3350e535bc9b880962dfcf88f1309d6df6d31461a13287f5992ca7cb74e6`; raw-input SHA-256 remains R18’s `5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec`; mutant resolved raw-output SHA-256 is `21afa4796e0dfb8a6daa397a22200559afd4a818d932b59b39d138f13bcb5400`. The mutant body hash is `0751c1cb0cdcee696f9be3bbcdad1436f104e34ba89b3461a181c1cb0be145e9`.

## Fresh funding witnesses and conservation

I decoded the exact mutant transaction and resolved input outputs. Both final-body Ed25519 funding witnesses verify over the final transaction body hash, and each public key’s Blake2b-224 hash matches its corresponding input payment credential. These are fresh body-bound witnesses for the rebound transaction.

The actual values satisfy `17,000,000 = 16,000,000 + 1,000,000` lovelace: two resolved inputs total 17M, outputs total 16M (10M authority output and 6M change), and fee is 1M. There are no native assets in the resolved inputs; the sole minted authority NFT under the mutant policy appears exactly once in outputs. No private key material is present in the package; funding keys are ephemeral per the reviewed builder design.

## Eligibility and limits

This is a condition-isolated, separately applied-policy mutant candidate and is **eligible for one controlled simulator run** through the pinned R3 runner at compiled Mint[0], using only the exact reviewed bytes. Eligibility means the negative control may now be run once to test whether changing only the proof-domain seed guard accepts the R18 signatures. It does not establish acceptance before that run. Preserve the simulator result and require independent post-run review before assigning R4.1 named-condition negative credit.

The mutant package itself records `tx-sim-not-run`, mutant control PENDING, negative-case credit null, mutation-suite credit null, and original-policy/ledger/live credit false. R18’s generic compiled rejection remains non-attributive until the mutant control succeeds and is independently reviewed. F05/M3 remains open; readiness remains NOT READY; deployment and gated activations remain disabled.