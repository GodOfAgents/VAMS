# Independent pre-execution byte review: validator-hash proof-domain case

Review status: PASS for pre-execution fixture integrity. This is not simulator acceptance, negative-case credit, mutation credit, ledger admission, or live-network evidence.

Reviewed candidate: docs/remediation/m3_f05_2a_proof_other_validator_hash_r1_20261005/r2_signature_for_other_validator_hash/.

No fixture bytes were edited. No simulator, transaction submission, status or classification change, or deployment action occurred.

## Governing identity

- R4.1 contract SHA-256: 238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171; decision B.
- Preserved case: r2_signature_for_other_validator_hash; assertion sign_tuple_with_another_state_validator_hash.
- Expected target: cardano/validators/f05_authority_policy.ak#f05_authority_policy.mint, compiled Plutus V3 Mint[0].
- Verifier property: valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message); expected negative behavior is rejection at compiled Mint[0].
- Source hashes match the family manifest: cardano/lib/vams/f05_authority.ak = 657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3; cardano/validators/f05_authority_policy.ak = e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8.

## Checks performed

The family and case SHA256SUMS manifests pass. Their byte lengths and SHA-256 values cover every fixture artifact. The family manifest covers all package files and binds the R4.1 contract and source hashes.

Pinned tool: Aiken v1.1.21+42babe5, SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.

I independently recompiled the policy from the exact seed-reference and ordered-key CBOR in a network-isolated temporary workspace with the canonical checkout read-only. Reconstructed parameter CBOR equals both fixture parameter files. Recompiled program bytes equal the fixture applied-policy bytes, SHA-256 8002a87a2f9b285197518bd865c7da7afae26b5362a0683d7a1c723716424dbd. Derived policy ID is 409712d7175aa2f7d372364919d50f55a048b83c7770a646826a1df4. The compiled state-validator hash equals the pinned source constant b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66.

Exact focused byte-only test command:

    bwrap --unshare-net --ro-bind / / --dev-bind /dev /dev --proc /proc --tmpfs /tmp --setenv PYTHONDONTWRITEBYTECODE 1 --setenv PYTHONHASHSEED 0 --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B -m pytest -p no:cacheprovider -v --tb=short scripts/remediation/test_f05_2a_proof_other_validator_hash_r1.py

Result: 5 passed in 0.34s on Python 3.12.14 and pytest 9.1.1. Tests read fixture bytes and use OpenSSL only for Ed25519 signature verification; they do not invoke tx-sim.

Byte-level findings:

- Positive and negative proof messages are each 279 bytes. They match at every byte except offsets 82-109, the 28-byte state-validator-hash field. Positive uses the derived applied hash; negative uses cd repeated 28 bytes. Seed, network magic, epoch, committee keys, ordering, and every other message byte are identical.
- Both fixtures use the same five distinct, lexicographically ordered 32-byte committee public keys. All five positive signatures verify over the positive message, and all five negative signatures verify over the altered negative message.
- Both transactions bind the mint map policy ID, compiled applied-policy identity, and Plutus V3 witness script hash to 409712d7175aa2f7d372364919d50f55a048b83c7770a646826a1df4. The V3 witness contains the exact independently recompiled program bytes.
- Transaction body, resolved raw inputs, raw outputs, datum, mint, and funding witnesses are byte-identical. The only transaction-witness change is the Mint[0] proof list. Both final-body funding witness sets contain two valid ephemeral Ed25519 signatures over the body hash and resolve to the input credentials.
- ADA conservation is 17,000,000 = 10,000,000 + 6,000,000 + 1,000,000 lovelace (inputs = authority output + change + fee). Native-asset conservation holds: exactly one authority NFT is minted and preserved in the authority output. No collateral is present.
- The package contains no persisted private-key material. The builder creates committee and funding signing keys ephemerally in anonymous memfds and closes them after signing.

## Execution boundary

The fixture records both positive and negative status as PENDING and says execution NOT RUN. The package contains no simulator run record. Positive-control cryptographic validity and structural acceptance conditions pass this pre-execution review; actual simulator acceptance remains untested. Negative named-condition attribution also remains pending until the separately required execution and attribution controls are reviewed. Evidence is synthetic, test-only alternate-applied-policy evidence with no original-policy, ledger-admission, Cardano Pre-Prod, or live-network credit.

Next eligible step: run the positive control first under the authorized synthetic simulator workflow, then proceed through the required negative and attribution controls with separate result review. Do not award case credit from this pre-execution review.
