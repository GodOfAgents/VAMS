# F05.2a applied-parameter CBOR candidate family r5

Status: **candidate bytes generated; independent byte review required; tx-sim not run; no case credit**.

R5 preserves R4.1 choice C and all six original case IDs/assertions. It corrects the Mint[0] redeemer representation against the frozen accepted transaction: redeemer map key [1,0] contains direct Plutus Data (constructor-0 outer CBOR tag 121) followed by the original execution-unit pair [14,000,000, 10,000,000,000]. The structural test requires direct tag 121, rejects tag 24, compares the decoded constructor and all proof signatures to the intended redeemer recorded in the case manifest, and verifies exact baseline ExUnits.

The authority output datum retains the accepted inline envelope [1, Tag(24, serialized Plutus state)]. The test reconstructs and compares each intended state. All distinct negative, positive-control, and applicable one-guard-mutant policy applications include canonical public-only seed/key CBOR sidecars. Manifests bind their hashes, lengths, decoded values, key-vector semantics, applied policy IDs, compiled program hashes, exact builder argv/results, and Mint[0] proof signatures. Signatures and public keys are public evidence; private keys are not included.

Every feasible negative is rebound to its own alternate applied Plutus V3 policy. Mint policy ID, compiled program hash, authority NFT policy, and V3 witness match. Each candidate has body-bound ephemeral funding signatures, a bound input vector, and conserved ADA/native assets. Ephemeral private keys existed only in process memory or anonymous memfds and were never serialized.

The synthetic transaction conserves 17,000,000 lovelace as a 10,000,000-lovelace authority output, 6,000,000-lovelace sponsor/change output, and 1,000,000-lovelace fee. There are no collateral inputs or collateral return fields; collateral consumed and returned are zero. The authority singleton NFT is conserved.

For applied_genesis_parameter, datum and PoPs bind to the alternate seed; only that seed input is omitted in the negative transaction. For applied_keys_parameter, the datum retains the baseline key vector while PoPs bind to the alternate applied parameter vector. Duplicate and unsorted parameter, datum, and PoP vectors match; each includes a separately compiled/rebound one-guard mutant control.

Bad-count and bad-length remain PENDING. Policy source requires exactly five 32-byte keys and five proofs; a six-key vector or a 31-byte key cannot have verifier-accepted PoPs. No first-failure evidence at Mint[0] was collected, so no isolated guard attribution is claimed.

No transaction simulator or applied-case suite was run. Positive controls remain unexecuted candidates pending independent byte review. Evidence is synthetic and parameter-bound. No original-policy, full-ledger-admission, or live-network credit is claimed. Case-status, registry, source, and readiness records were not modified. R3 and R4 are preserved unchanged. Deployment and gated activations remain disabled.

| Original case ID | Alternate applied policy ID | Negative tx SHA-256 | Credit |
|---|---|---|---|
| applied_genesis_parameter | fc305fd82585607dc1998425cbe3bce8f43667e1ac161c448098c058 | 67a3a40a149c5972720b23c18d37bb65f4ead04f0eaae421c3f3aa6440cb1e6b | PENDING |
| applied_keys_parameter | efec0d79e496e2df81f8e3e27734c9718655dc577070c7519645fa29 | f57020cb1d5ac3a7eebf8885472c62e6c0c1c4f8f2c9f85f890beac25194413f | PENDING |
| applied_keys_bad_count | 4fa737ebb0a7133d941fc952c7fdc865272722096943196b2094fbc6 | b605624a10e16c3047b039ebbe8325c26bf72f2d8a3522f2b4da85b206c8ac76 | PENDING |
| applied_keys_bad_length | f437579f653982217de579607e0fe15a8542fb33b636f47936bc9c54 | d4770335a664afb567fdaf5f56612532a589aa2873354775549b8fcb3d29d8e2 | PENDING |
| applied_keys_duplicate | d1f886d981117ada5f4e92370e1921c1c3616ce37b558b3fc42b65b9 | 4e538bf83ddef70b48c7d3536a8f3ea1daac7151f2f8534667ff541c9f8a52ac | PENDING |
| applied_keys_unsorted | 1fb791c31f3e1ca6ca17d0329ace7c345366359fed36096c325a2e93 | e77240962aa9151cb780eed1df30f8305a8958c0d24bf48c7d8dea9bece1de50 | PENDING |

Pinned local tools: Python 3.12.14, Aiken 1.1.21+42babe5 (SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79), and OpenSSL 3.5.5. No installation or network fetch occurred.

Each case was built separately with its exact argv recorded. Focused structural verification compares datum/redeemer shapes directly with frozen valid.tx.cbor; reconstructs the intended direct Plutus Data redeemer; independently reconstructs parameter sidecars and datum state; verifies checksums, applied policy/mint/V3 linkage, funding signatures, and value conservation. The builder does not execute tx-sim.

Independent byte review is required before any simulator execution. All six cases remain PENDING.
