# Independent integrated review: R17/R18/R19 seed-domain triad

Date: 2026-10-05
Verdict: PASS for exactly one synthetic parameter-bound transaction-simulator negative row, r2_signature_for_other_seed.
Credit boundary: no mutation-suite, original-policy, ledger-admission, Pre-Prod, live-network, or readiness credit.

## Scope and checks

I reconciled R4.1 decision B and the preserved original assertion sign_same_tuple_with_alternate_seed against the exact positive, negative, and one-guard-mutant packages, their run captures, the immutable R3 runner identity, and linked independent reviews. I did not execute Aiken, a simulator, a build, or a fixture test. No source, fixture, STATUS, or HANDOFF files were edited.

Checksums passed for the R17/R18 family and case manifests and all 15 case artifacts; R19 family and case manifests and all mutant/preserved-R18 artifacts; each R17/R18/R19 RUN.json; and the four linked pre/post-execution review records. R4.1 contract SHA-256: 238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171. R17/R18 case manifest SHA-256: d993a5d09ad5a4b533e6d6d571507b8dab15c920667b0a0fd3798d73a47661fb. R19 case manifest SHA-256: 7f1aabbecfa0eb42094e916043e037644db813dfe117249a5ed6ddf794320291.

Run JSON hashes: R17 f9a86dca6d7fed12a92fb2afb59ac77836c6b963b178403f0ef77b8c9494992f; R18 2f3d042cd4350d821b0ce91dafa4cddfdb36dc23258eefb6115b947fd764b0be; R19 ecd352f4acfb379b36a05ab623f8a25a6d5e6a8be4f9181de92cba37f3c973ba. Linked review hashes: initial byte review a17bde02f3516516a548c1a91de9534f130278e595303e4aee048d6b19b1287a; R17 post-run fb4d688f9b2aabce99665ed108d330174dd7b1af0d89c1267e59681c7df1e81c; R18 post-run a2d5d636cf1489341cc61ba30e0c7b638da223958a785219dfb6c016d1a61460; R19 pre-run mutant review 414da952b44b0353344fe5176fa3c82e7ab7a0e4425e155afa3ff250acd3de3e.

## Bytes, bindings, and invariants

Read-only Python 3.12 CBOR/OpenSSL checks independently verified each fixture's 5/5 positional PoPs, 2/2 body-bound funding witnesses, witness-to-consumed-synthetic-UTxO payment credentials, Plutus V3 script hash, sole mint-policy binding, body hash, and value conservation. No private keys were read or persisted.

| Fixture | Tx SHA-256 | Inputs SHA-256 | Outputs SHA-256 | Proof-message SHA-256 | Bound policy ID |
|---|---|---|---|---|---|
| R17 positive | 040a2fb4deff2265ec1bcc6d7f5ae78170ff3a2855cb7145729fddf6d101a555 | 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec | d137c61cbd332ec1d13900844e51ee075abb99fe4a9cd838d9ead465e2a6ca95 | dd7f979a1c9aaf8716069f6ccc7424ba9143b5c29f8ba20bf87d9d7336f95d3d | 4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76 |
| R18 negative | 53526ecc1282cb83aaf9690a74c422361f25c4229da1378bbc68d8e78405534b | 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec | c4ba70814b665c3fc0133e8c3ea4d253f27613716209da83113dd1ab9ec59048 | 5fa13e0c6240b7b75d154f152de2bf376f93d2af3dd8642c7d25f4757e2a8542 | 4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76 |
| R19 mutant | e57b3350e535bc9b880962dfcf88f1309d6df6d31461a13287f5992ca7cb74e6 | 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec | 21afa4796e0dfb8a6daa397a22200559afd4a818d932b59b39d138f13bcb5400 | 5fa13e0c6240b7b75d154f152de2bf376f93d2af3dd8642c7d25f4757e2a8542 | 08cbd325cfc8dfa702de69a77ab5564b5bc71ce8f94fde2021312fdb |

R17/R18 applied script SHA-256 is 9136d96103775a3140a77ae53ca0bc8e2bbb70265ae7aa732dad75cfcc68a170. In both, sole mint ID, applied policy ID, and V3 witness hash agree at 4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76. Bodies are identical (hash 432b080980a2e5326fd3751f3b269eb6dc2c8b1d58074f72afbf0be6109ebd11). Proof messages are 279 bytes and differ only at seed transaction-ID bytes 48–79: ab repeated 32 bytes for R17, ad repeated 32 bytes for R18; index 7 and all other bytes are equal. The applied datum/parameter seed remains ab…ab#7.

R19's source diff changes only the expected seed argument passed to authority_genesis_pop_preimage, to ad…ad with the original output index. The normal applied-seed input guard, datum/state validation, key-count/order checks, other state guards, and Ed25519 verification remain. R19 applied script SHA-256 is 1604b940210dc739ca5a6ae42ec74aa49d2e808380c05191c37a3c50f7983532; its sole mint ID, mutant policy ID, and V3 witness hash agree at 08cbd325cfc8dfa702de69a77ab5564b5bc71ce8f94fde2021312fdb. It retains the exact R18 message and proof signatures; its body hash is 0751c1cb0cdcee696f9be3bbcdad1436f104e34ba89b3461a181c1cb0be145e9.

Each transaction conserves 17,000,000 lovelace input = 16,000,000 output + 1,000,000 fee (10M authority output and 6M change). One authority NFT is minted under that transaction's own policy and conserved in the output. Collateral is absent. Funding witnesses are ephemeral test keys and bound to each exact final body.

## Execution, attribution, and disposition

All captures use runner SHA-256 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c and pinned Aiken 1.1.21 SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. R17: wrapper 0, child 0, script_accepted, target invoked, clean cleanup. R18: wrapper 0, child 1, compiled_evaluation, target invoked, clean cleanup. R19: wrapper 0, child 0, script_accepted, target invoked, clean cleanup.

R18 alone establishes only generic compiled Mint[0] rejection. Named-condition attribution follows from the accepted R17 control over the applied-seed message plus R18 rejection with valid signatures over the alternate seed, and R19's acceptance of the exact R18 message/signatures after changing only the expected proof-domain seed and rebinding the mutant. This satisfies R4.1's same-negative one-guard-counterfactual requirement for the synthetic applied-policy case.

Therefore this review supports exactly one synthetic parameter-bound transaction-simulator negative row: r2_signature_for_other_seed. R19 is an attribution control, not an independent mutation-suite row; grant no mutation-suite credit. No original-policy, full-ledger-admission, Cardano Pre-Prod, live-network, or deployment credit is supported. F05/M3 remains open; readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Evidence limitation: run records are checksummed structured runner results but retain neither raw Aiken stdout/stderr nor external attestation. The outcome is credited only within the synthetic scope and on the captured runner classifications, checksummed exact bytes, clean cleanup fields, and linked independent reviews.

Validation record: package/run/review SHA256SUMS checks passed; read-only command `diff -u cardano/validators/f05_authority_policy.ak docs/remediation/m3_f05_2a_proof_other_seed_mutant_r1_20261005/r2_signature_for_other_seed/mutant-policy-source.ak` showed the one seed-argument hunk; read-only Python CBOR/OpenSSL audit returned PASS for all three fixtures and the R17/R18 message delta.