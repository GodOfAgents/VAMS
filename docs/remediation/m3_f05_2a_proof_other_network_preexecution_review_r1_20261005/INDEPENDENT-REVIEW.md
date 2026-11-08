# Independent pre-execution byte review: R2 other-network proof domain

Date: 2026-10-05
Verdict: PASS — exact positive/negative candidate package is eligible for its bounded simulator execution under R4.1 choice B.
Execution status: NOT RUN; both controls remain PENDING. This review grants no negative-case, mutation-suite, original-policy, ledger-admission, Pre-Prod, or live-network credit.

## Scope

Read-only review of docs/remediation/m3_f05_2a_proof_domain_family_r2_20261005/, its R4.1 contract row, exact CBOR and proof-message bytes, applied-policy identity, and pinned runner/toolchain files. A local Python 3.12 CBOR/OpenSSL audit verified signatures and value accounting; it did not invoke the Aiken simulator, tests, or a build. No package, source, STATUS, or HANDOFF file was changed; only this review and SHA256SUMS were written.

## Integrity and preserved contract

Family SHA256SUMS and case SHA256SUMS passed; all family and case artifacts verified. FAMILY-MANIFEST.json SHA-256: 0d4fe66dee3ad48f59231909bd8b0599f49da72a1f15a47c29b65618a17746ed. Case FIXTURE-MANIFEST.json SHA-256: f637a4d316313e4f1fa0810b85d58cbe0c9aee093557f4cc4107f433128c402a. Family SHA256SUMS file SHA-256: 454c26bc84a3735f4974ab1788c6f22915d38c3004c2c8653db1a745ac763ffa.

R4.1 contract SHA-256 238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171 records proof-domain choice B. The original ID r2_signature_for_other_network and assertion sign_tuple_with_another_network_magic are preserved, as is verifier property valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message). Expected entrypoint is f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]. Both control statuses are PENDING; package status says candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit.

## Parameter, proof-domain, and transaction checks

The applied tuple in the package is chain_code=2, chain_id=0, network_magic=1, address_network_id=0. The applied seed is ab repeated 32 bytes at output index 7; the applied committee has five ordered, unique 32-byte public keys. The positive and negative use identical applied policy bytes, parameter CBOR, datum, transaction body, raw-input snapshot, and raw-output snapshot.

The two 279-byte proof messages differ only at bytes 43–46: positive network_magic is 00000001; negative is 00000000. All other bytes match. Thus the applied policy/transaction semantics retain network_magic 1 while the negative PoPs sign the tuple with only network_magic changed to 0.

| Fixture | Transaction SHA-256 | Raw inputs SHA-256 | Raw outputs SHA-256 | Proof message SHA-256 |
|---|---|---|---|---|
| Positive control | ef8fedd6dfe7f6f7b266caa8126aed1408a63fe3e04adb5ef75fe49d41ce6bbf | 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec | 14f8b6399c77d55fa3cf016a48b1ff47d97efa293d5e043b7d699f66d847e6c0 | 2c5f7c1630f8f8589ba81cc726b1bc4e796ae18158d146245295389f9d217d27 |
| Negative candidate | 2627b7ca1d85a06adac1e957eb186f3e5fd8e69a8f0fdd7b9d81b6753c7a3065 | 5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec | 14f8b6399c77d55fa3cf016a48b1ff47d97efa293d5e043b7d699f66d847e6c0 | 87b2d24f30ca078e33b98f6d34616d91be975e32643655f7a34466afd0731c7f |

Both transaction bodies have BLAKE2b-256 hash 2271b189b371ad1bd20735535042d4f58345dd8fae9f75e70c293479e00169cd. For each candidate, the sole transaction mint policy ID, applied policy ID, and Plutus V3 witness hash agree at 13a2712cbc7b1c6f7cf48f7c3decd50b9c13e7837bd4cfc8865f496a. Recomputing blake2b(0x03 || applied_script_cbor, 28 bytes) produces that ID. Applied script SHA-256 is bd3bbef9e5ce973e4c20ec1f4c898730a3ec9ba4503c1d6d196f02e71b4ab9c1.

The exact positive PoPs verify 5/5 against the positive message and the exact negative PoPs verify 5/5 against the negative message under the applied keys. Each final-body funding-witness set verifies 2/2 against its transaction body hash, and those public-key credentials match the consumed synthetic UTxO payment credentials. ADA balances are conserved: 17,000,000 input = 10,000,000 authority output + 6,000,000 change + 1,000,000 fee. Exactly one authority NFT under the applied policy is minted and conserved in output. No collateral is present. Only public keys, signatures, and public CBOR artifacts are packaged; no private-key material is present or persisted, consistent with the manifest’s ephemeral-key declaration.

## Toolchain and disposition

Runner scripts/remediation/f05_2a_tx_sim_runner_r3.py SHA-256 is 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c. Pinned Aiken executable is aiken v1.1.21+42babe5, SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. Pinned Python is 3.12.14, executable SHA-256 aa01d96348989f33ed998b42c83e98593b41dba83914d9899730b90c36f2e5c9. OpenSSL is 3.5.5.

This passes pre-execution byte review and makes the positive control and negative candidate eligible for the bounded R3 simulator sequence. Execute the accepted positive first; if it fails before target invocation, stop. Keep both cases PENDING until simulator results and independent post-run review establish the required result and attribution. Evidence remains synthetic alternate-applied-policy scope only; no original-policy, ledger-admission, Pre-Prod, or live-network inference is allowed.