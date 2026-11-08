# Independent epoch mutant pre-execution review

Review id: m3_f05_2a_proof_other_epoch_mutant_preexecution_review_r1_20261005
Outcome: PASS for byte-level condition-isolation review
Case: r2_signature_for_other_epoch
Decision: R4.1 proof-domain B

## Source mutation and applied policy

The original case ID and assertion are preserved: r2_signature_for_other_epoch / sign_tuple_with_nonzero_epoch. The refreshed family and case checksum manifests pass, all inventoried family entries and artifact byte counts/hashes match, and the package status remains candidate-awaiting-review with execution NOT RUN.

The corrected SOURCE-DIFF.patch targets cardano/lib/vams/f05_authority.ak. Applying the exact hunk changes one expression in authority_genesis_pop_preimage: bytearray.from_int_big_endian(0, 8) becomes bytearray.from_int_big_endian(1, 8), the final eight-byte epoch field. The canonical library source SHA-256 is 657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3; the one-expression disposable mutant source hash is 5be58f7b06c1e797571b2ad32d107367fbff59dcaa4ce041654519cbc0946eef. The validator policy source is unchanged. Its canonical state-validator hash constant remains b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66.

I independently compiled a disposable copy of the mutated source with pinned Aiken v1.1.21+42babe5 (binary SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79) and the fixture public parameters. The compiled applied script bytes match mutant.applied-policy.cbor exactly: SHA-256 76e502ca5ea6d390437cb78e0b87f9217d34831d19f2324c7749434e3d5f001d. Its policy ID is 6f2cfb8a849311c6e6076b466daafe77ae5a95de9b50c62caecfafa4. The transaction mint policy ID and compiled Plutus V3 witness bind to that same ID. The state-validator hash remains the canonical value above.

The decoded authority output address is identical in the reviewed negative and mutant transactions: 70b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66. Thus the mutant changes the proof-preimage epoch argument while retaining the canonical state address and output guards.

## Proof, funding, and conservation

The mutant proof message and five PoP signatures are byte-identical to the independently reviewed normal-policy negative fixture, with the same public parameters and input references. All five Ed25519 signatures verify against that exact proof message. The copied positive-control fixture files match the previously reviewed positive control byte-for-byte, including its applied policy and transaction; its earlier execution and review records are also preserved byte-for-byte.

The mutant transaction uses fresh ephemeral funding witnesses because the prior private funding keys were not retained. Both funding signatures verify over the final mutant body hash 1572dca3f4a05e6b74c039aa4e02fc381c164b3842c681e3c1be16fd9ddfe51d, and their key hashes match the resolved funding outputs. ADA conservation is 17,000,000 = 16,000,000 + 1,000,000. Exactly one VAMS-F05-AUTH-V3 NFT is minted under the mutant policy and conserved in the transaction outputs. The package contains only public parameters, signatures, transactions, and review/run records; no private-key material is present or claimed persisted.

The package hash-links the prior normal negative attempt and review, prior positive-control attempt and review, and original pre-execution review. The normal negative had only a generic compiled_evaluation result. This mutant has not been executed, so it currently supports no causal attribution or case credit.

## Scope

PASS is limited to pre-execution bytes and build identity. No simulator was run during this review. The candidate remains synthetic under a one-guard alternate applied policy. It grants no original-policy, ledger-admission, Pre-Prod, live-network, mutation-suite, or readiness credit. No STATUS or HANDOFF record was edited.
