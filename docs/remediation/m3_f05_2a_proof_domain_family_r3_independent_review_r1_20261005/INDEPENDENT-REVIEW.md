# Independent pre-execution byte review

Review id: m3_f05_2a_proof_domain_family_r3_independent_review_r1_20261005
Outcome: PASS
Case: r2_signature_for_other_epoch
Decision: R4.1 proof-domain B

## Findings

The original registry assertion is preserved exactly as sign_tuple_with_nonzero_epoch for r2_signature_for_other_epoch. The fixture package remains candidate/pending and states tx-sim not run. Its exact inventoried file set matches FAMILY-MANIFEST.json. Root and case SHA256SUMS and every family manifest byte/hash entry verified; source file hashes match the family manifest. No RUN or attempt artifact exists.

The positive and negative proof messages are each 279 bytes and match the canonical R2 preimage for the applied seed, state-validator hash, and ordered five-key committee except the named epoch field. Exactly bytes 271 through 278 differ: positive 0000000000000000, negative 0000000000000001. The applied datum and policy parameters retain epoch 0. This is the single intended condition: committee proofs over a nonzero-epoch message against the epoch-0 applied message domain.

Both transactions use the same test-only alternate applied policy. I independently rebuilt it from the package public genesis reference and ordered public keys with pinned Aiken v1.1.21+42babe5 (binary SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79). Rebuilt script SHA-256 14bc2862bca0933da246c0fdd77d703fc174a9ed2a4ee46a492fd3b07a81bd74 and policy id 704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad match the package exactly. The policy id matches the sole mint policy key, and the transaction carries the same applied script as its Plutus V3 witness. The state-validator hash also matches the compiled result.

All ten committee signatures verify against their respective exact proof messages. Each transaction has two valid funding signatures over the final body hash; funding key hashes match the resolved funding outputs. Positive and negative fixtures have identical body, inputs, outputs, and funding witness set; only the PoP redeemer witness differs. ADA conservation is 17,000,000 = 10,000,000 + 6,000,000 + 1,000,000. Exactly one VAMS-F05-AUTH-V3 NFT is minted under the applied policy and preserved in the authority output. The retained package contains only public parameters, signatures, and transaction fixtures; private-key material is not persisted.

Key fixture hashes: positive transaction 28818f0e4fa862fff96dfc935d0479fc81e623cdd84930b60138fd74a7829f68; negative transaction 38bbf76af57957881095dc42a0004ab1caa8a4a43065228066dbd7407eaa37f3; shared raw inputs 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec; shared raw outputs e92e5834ea46162f0d9db7320b5bb6abb5fc4bf31b23d5d358c0a571555f09d7.

## Scope

This is a byte and build review only. No simulator or transaction execution was run. Both positive control and negative remain pending. The evidence is synthetic and uses an alternate applied policy; it grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. No source, fixture, classification, STATUS, or HANDOFF file was changed by this review.
