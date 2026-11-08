# F05.2a applied-parameter CBOR candidate family r4

Status: **candidate bytes generated; independent byte review required; tx-sim not run; no case credit**.

This version preserves R4.1 choice C and all six original case IDs and assertions. It corrects two typed-transaction parser-shape defects identified during runner-context audit. The authority output datum preserves the accepted inline-datum envelope [1, Tag(24, serialized Plutus state)]; the tests decode that state and compare it with the intended seed, keys, and fixed fields. The Mint[0] redeemer preserves the baseline two-element pair [Tag(24, serialized redeemer), execution units]; tests compare its shape and exact execution-unit budget with frozen valid.tx.cbor.

All distinct negative, positive-control, and applicable one-guard-mutant policy applications include canonical public-only seed/key parameter CBOR sidecars. Manifests bind sidecar hashes, lengths, decoded values, key-vector semantics, applied policy IDs, and compiled program hashes. Exact per-case builder argv and results are recorded.

Every feasible negative is rebound to its own alternate applied Plutus V3 policy. Mint policy ID, compiled program hash, authority NFT policy, and V3 witness match. Each candidate has body-bound ephemeral funding signatures, a bound input vector, and conserved ADA/native assets. Ephemeral private keys exist only in process memory or anonymous memfds and were never serialized.

The synthetic transaction conserves 17,000,000 lovelace as a 10,000,000-lovelace authority output, 6,000,000-lovelace sponsor/change output, and 1,000,000-lovelace fee. There are no collateral inputs or collateral return fields; collateral consumed and returned are zero. The authority singleton NFT is conserved.

For applied_genesis_parameter, datum and PoPs bind to the alternate seed; only that seed input is omitted in the negative transaction. For applied_keys_parameter, the datum retains the baseline key vector while PoPs bind to the alternate applied parameter vector. Duplicate and unsorted parameter, datum, and PoP vectors match; each includes a separately compiled and rebound one-guard mutant control.

Bad-count and bad-length remain PENDING. Policy source requires exactly five 32-byte keys and five proofs; a six-key vector or a 31-byte key cannot have verifier-accepted PoPs. No first-failure evidence at Mint[0] was collected, so no isolated guard attribution is claimed.

No transaction simulator or applied-case suite was run. Positive controls remain unexecuted candidates pending independent byte review. Evidence remains synthetic and parameter-bound. No original-policy, full-ledger-admission, or live-network credit is claimed. Case-status, registry, source, and readiness records were not modified. R3 remains unchanged. Deployment and gated activations remain disabled.

| Original case ID | Alternate applied policy ID | Negative tx SHA-256 | Credit |
|---|---|---|---|
| applied_genesis_parameter | 4b64c9df3b101b64e4db14aea97399db74a259cdc85b3e533d8cec3d | 626bff54fff97b850aaab016ac9b8236ac17e95e193c71cafccd0c69c9591835 | PENDING |
| applied_keys_parameter | dbeffc03bd7d3472be36c62b7998ad2a2b1beac1d7fe9bbde128ec91 | a206577c2c69ddba857affe02e47638efd4c77944226fdbcc2f964f7eadc0bd6 | PENDING |
| applied_keys_bad_count | 9e59b6c94a1fdb51c5f40a9270abb64f061895fa7eab02c778bb121d | 455435ebd0ac2d05ed0f1da4d21ce7a3135cd99649957bea842f0123a97879c4 | PENDING |
| applied_keys_bad_length | 9d2a10b372918f5cbb5acf05e4a4e329a252b8bca1d733e271810ac8 | 80d4661c5a08340767e6a459053dc54e70192facf684f181a167e3a0555e79de | PENDING |
| applied_keys_duplicate | d3503cc596d7ee63c650a57a3bb1e34b6250d0ee7d3434baaaa2eeed | 3c483c3c298b0d40bc0a593ccfad6269989fb4be5130d5ce6b2a17b39a64e977 | PENDING |
| applied_keys_unsorted | 157dfbeb40a25d795f926722bc5bb003eccc6187f520ea5c63d87bac | eabd872c8e011e7a8d43c33ab91af801291677b547b31750e378602764ee8452 | PENDING |

Pinned local tools: Python 3.12.14, Aiken 1.1.21+42babe5 (SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79), and OpenSSL 3.5.5. No installation or network fetch occurred.

Each case was built separately with its recorded exact argv. Focused structural verification reconstructs every parameter sidecar; compares datum/redeemer envelopes and execution units with frozen valid.tx.cbor; decodes intended state; verifies checksums, policy/mint/V3 linkage, funding signatures, and value conservation. The builder does not execute tx-sim.

Independent byte review is required before any simulator execution. All six cases remain PENDING.
