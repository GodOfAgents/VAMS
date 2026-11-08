# Independent pre-execution byte review: R2 proof signed for other seed

Date: 2026-10-05
Review revision: r1
Canonical checkout: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

Decision: PASS for positive-control execution eligibility. The exact positive/negative R4.1 B package is byte-consistent, correctly bound to one alternate applied policy, and the PoP domain change is isolated to the seed hash in the signed message. Both proof sets and final-body funding witnesses verify cryptographically. The positive control is eligible for the next bounded simulator run at compiled Mint[0]. No simulator was run in this review. The negative remains PENDING until its execution and independent attribution review.

## Scope and verification

Read-only review of `docs/remediation/m3_f05_2a_proof_domain_family_r1_20261005/r2_signature_for_other_seed/`, its family manifest, R4.1 contract, frozen registry, relevant generator/test source, validator library/policy, and the compiled policy/transactions. No simulator, tests, builds, or network operations were run. No fixture, source, STATUS, or HANDOFF file was edited. Only this review report and its SHA256SUMS were written.

Commands and results:

- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_proof_domain_family_r1_20261005/r2_signature_for_other_seed && sha256sum -c SHA256SUMS` — PASS: all 15 listed entries OK.
- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_proof_domain_family_r1_20261005 && sha256sum -c SHA256SUMS` — PASS: FAMILY-MANIFEST.json OK.
- Read-only `sha256sum` checks for R4.1 contract, frozen registry, builder/test source, Aiken executable, validator source, family/case manifests, and selected positive/negative artifacts — all hashes match the recorded identities below.
- Read-only Python audit of the exact CBOR transactions and raw inputs/outputs, plus OpenSSL Ed25519 verification using anonymous in-memory descriptors — PASS: 5/5 PoPs and 2/2 funding witnesses per transaction; transaction-body bytes equal; policy/script/Mint/V3 binding matches; ADA/native value checks pass. No private keys were read from or written to files.

## Contract, case, and tool identities

- R4.1 contract `docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json`: SHA-256 `238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171`.
- Frozen registry `docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json`: SHA-256 `98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d`.
- The controlling owner decision is proof-domain choice B, and the original registry row remains `r2_signature_for_other_seed` / `sign_same_tuple_with_alternate_seed`.
- Family manifest SHA-256: `b83dca7ff9a70b312d442e621036964d690b8be0436a7421aac7c929d1d5c471`; family SHA256SUMS file: `21fd17528569dd8ed2dddd6c7b744c621b988c8c9a45a723e68bce5abddcceb0`.
- Case manifest SHA-256: `d993a5d09ad5a4b533e6d6d571507b8dab15c920667b0a0fd3798d73a47661fb`; case SHA256SUMS file: `eccecac05b6fb9c8cd392858ff915f45cbcbf1ab4dbd5ddf6235132882f43397`.
- Generator `scripts/remediation/build_f05_2a_proof_other_seed_r1.py`: `45b445d36ee57ac7e06436bb6af529f9c1b16f45950cbea09b6dace0a05e3324`.
- Structural verifier source `scripts/remediation/test_f05_2a_proof_other_seed_r1.py`: `ae8214579c84b96e0c20abc05aad7dfd51e108abeac9b784eb4bd7391741abbd`. This review independently checked the bytes; it did not execute the test module.
- Authority library `cardano/lib/vams/f05_authority.ak`: `657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3`.
- Mint policy `cardano/validators/f05_authority_policy.ak`: `e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8`.
- Pinned Aiken executable SHA-256: `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`; the package records version `aiken v1.1.21+42babe5` and Python `3.12.14`.

The original case ID/assertion and security property are preserved. The package explicitly says no execution or credit yet, targets `f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]`, and is scoped to a synthetic alternate applied policy with no original-policy, full-ledger-admission, Pre-Prod, or live-network credit.

## Applied policy and transaction identity

Both candidates use the same five strictly sorted, unique 32-byte applied committee keys and applied seed reference `ab` repeated 32 bytes at output index 7. The parameter CBOR hash is `d3c9a2aeb2a47eecd7e004bb5c65cd569b9a569b6980ca5e752f48a07996cc9e`.

Both applied-policy CBOR files are exactly 3467 bytes with SHA-256 `9136d96103775a3140a77ae53ca0bc8e2bbb70265ae7aa732dad75cfcc68a170`. Their computed Plutus V3 policy ID, using `blake2b(0x03 || script_cbor, digest_size=28)`, is `4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76`. Both transaction bodies have the same canonical bytes and body hash `432b080980a2e5326fd3751f3b269eb6dc2c8b1d58074f72afbf0be6109ebd11`. For each transaction, the sole mint policy ID equals the applied policy ID and the Plutus V3 witness script hash equals that same ID. The policy seed, parameter key set, datum, body, and target mint are therefore common to the positive and negative candidates.

Exact selected transaction/vector/message hashes:

| Artifact | Positive control SHA-256 | Negative SHA-256 |
| --- | --- | --- |
| Transaction CBOR | `040a2fb4deff2265ec1bcc6d7f5ae78170ff3a2855cb7145729fddf6d101a555` | `53526ecc1282cb83aaf9690a74c422361f25c4229da1378bbc68d8e78405534b` |
| Raw inputs CBOR | `5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec` | `5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec` |
| Resolved raw outputs CBOR | `d137c61cbd332ec1d13900844e51ee075abb99fe4a9cd838d9ead465e2a6ca95` | `c4ba70814b665c3fc0133e8c3ea4d253f27613716209da83113dd1ab9ec59048` |
| 279-byte proof message | `dd7f979a1c9aaf8716069f6ccc7424ba9143b5c29f8ba20bf87d9d7336f95d3d` | `5fa13e0c6240b7b75d154f152de2bf376f93d2af3dd8642c7d25f4757e2a8542` |

The raw input references are identical. Resolved raw output snapshots differ because each contains ephemeral funding-key credentials, but both preserve the same reference/value context and their own vkey witnesses match those credentials.

## Signed message and cryptographic findings

I independently reconstructed the 279-byte R2 preimage from the production source's domain and fixed-width tuple: domain `VAMS-F05-AUTHORITY-GENESIS-POP-V1\0`; chain code 2, chain ID 0, network magic 1, address network ID 0; seed reference; state validator hash `b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66`; five keys in applied order; epoch 0.

The positive message uses seed hash `ab` repeated 32 bytes; the negative message uses `ad` repeated 32 bytes at byte offsets 48–79. Every other byte is identical, including tuple/domain fields, seed index 7, validator hash, key count/list, and epoch. The applied policy parameter and transaction datum retain the `ab` seed in both cases. This is the named changed condition: the negative PoPs sign the same tuple under the alternate seed while the target policy expects the applied `ab` seed.

I decoded each exact transaction's Mint[0] redeemer and independently verified every positional Ed25519 proof against the applied public keys and its stored/reconstructed message: positive 5/5 PASS and negative 5/5 PASS. All proof signatures are 64 bytes. The positive/negative proof-signature lists differ, while each set verifies only under its own 279-byte message.

The two final-body funding vkey witnesses in each transaction also verify over the BLAKE2b-256 hash of that exact transaction body: positive 2/2 PASS; negative 2/2 PASS. Each pair of funding public keys matches the two resolved input payment credentials. The package contains public keys/signatures, policy/transaction/data CBOR, and proof-message bytes only; no private key files or private key material are persisted. The builder uses test-only Ed25519 keys in anonymous `memfd` descriptors and closes signer descriptors.

## Value conservation

I independently summed the resolved input/output values and mint/output assets for both exact transactions:

- ADA: 17,000,000 input lovelace = 16,000,000 output lovelace + 1,000,000 fee. Output lovelace consists of the 10,000,000 authority output and 6,000,000 change.
- Native assets: no native assets are present in the resolved inputs; exactly one authority NFT under applied policy `4df3f2980f5fb625605e3198278670cbc9cb01535b6bbe3ee5d16e76` is minted and exactly one is present in the authority output. Both transactions conserve all native assets.
- Collateral is absent and reported as zero.

These are local synthetic fixture bytes, not ledger-admission results.

## Eligibility and limits

The package passes the independent byte, applied-policy/Mint/V3 binding, message-domain, PoP signature, funding-witness, and conservation checks. The accepted positive-control transaction is eligible for the next simulator execution through the pinned R3 runner at compiled Mint[0], subject to recording and independently reviewing that run. This review does not execute the positive control or negative.

The negative remains PENDING until its compiled Mint[0] result and independent condition-attribution review are complete. The package and R4.1 decision grant no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. F05/M3 remains open; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.