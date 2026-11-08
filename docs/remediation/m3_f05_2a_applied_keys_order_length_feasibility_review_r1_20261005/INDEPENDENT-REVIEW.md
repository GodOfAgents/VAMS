# Independent feasibility audit: applied keys length and order

Date: 2026-10-05
Audit revision: r1
Canonical checkout: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f
Scope: read-only source/manifest audit of R5 cases applied_keys_bad_length and applied_keys_unsorted. No validator test, transaction simulator, or chain operation was run. No source, fixture, status, handoff, or classification file was edited by this audit.

## Conclusion

- `applied_keys_bad_length`: **not eligible for a valid-PoP one-guard mutant triad**. Its R5 applied parameter has five keys, but key 1 is 31 bytes. The one-guard candidate would remove the 32-byte key-length part of `valid_ordered_keys`; `valid_bootstrap_proofs` still verifies each 64-byte signature against the same malformed public key. The manifest itself classifies PoP as infeasible for this malformed shape. Do not represent the current signatures as verifier-valid PoPs. If the goal is to test the malformed-length boundary, the minimum honest evidence path is a versioned, independently reviewed compound-failure amendment retaining this case ID/assertion and explicitly allowing invalid/unverifiable PoP semantics for this synthetic negative, while still requiring body-bound ephemeral funding signatures, value conservation, an accepted positive control, exact applied-policy/Mint[0] binding, and attributable compiled rejection. The amendment must make no original-policy, ledger-admission, or live-network claim. Without that amendment, leave the row PENDING and do not run the malformed negative as though it were a valid-PoP isolated guard test.
- `applied_keys_unsorted`: **eligible for a valid-PoP one-guard mutant triad**, subject to the existing independent-byte-review-before-execution gate. The five distinct keys are all 32 bytes. Their unsorted order is identical in the applied parameter and datum, and the five PoPs are recorded as valid signatures bound to that exact applied parameter. The preimage encodes the key count and concatenates keys in their supplied order. A test-only mutant can remove only the strict-increasing comparisons in `valid_ordered_keys`; the list arity, key sizes, datum equality, proof count, and signature checks remain. The R5 package includes the negative, positive control, and one-guard-mutant candidate, all with body-bound ephemeral funding signatures and conservation claims. This audit does not independently rederive signatures or validate exact bytes; the fixture package's review and its checksums are separate evidence gates and must be rechecked before execution.

Recommended order, respecting one family at a time: (1) independently byte-review and, if accepted, execute/review the unsorted positive control; (2) execute/review the unsorted negative under its exact applied policy; (3) execute/review its one-guard mutant under its mutant policy; (4) obtain paired attribution review before any classification overlay. Keep all rows PENDING until the required controls, run evidence, and independent review support credit. Treat all resulting credit as synthetic alternate-policy transaction-simulator evidence only.

## Source and fixture basis

Source identities at audit time:

- `cardano/lib/vams/f05_authority.ak`: SHA-256 `657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3`.
- `cardano/validators/f05_authority_policy.ak`: SHA-256 `e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8`.
- R5 family manifest: SHA-256 `3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e`.
- Bad-length fixture manifest: SHA-256 `8a10528d1630ab46226126127f3b0bfaa8193c8ff151d13a6451d581e7ce1d1c`.
- Unsorted fixture manifest: SHA-256 `bf84b96865bb89860a25f1cbf6a9799419a17b7b71bf6249c21fabe128a27c96`.

Relevant predicates and dependencies:

- `valid_initial_authority` calls `valid_ordered_keys(initial_keys)` then requires `state.ordered_keys == initial_keys` (source lines 79-93; key checks at 89-90).
- `valid_ordered_keys` pattern-matches exactly five keys, requires each key to have `authority_key_bytes` bytes, then requires four strictly increasing big-endian comparisons (lines 268-282). Its fallback is false.
- `authority_genesis_pop_preimage` commits to the domain tuple, genesis reference, state validator hash, key count, `encoded_ordered_keys(keys)`, and epoch (lines 95-133). `encoded_ordered_keys` concatenates five keys in their current order and returns empty bytes for any other arity (lines 284-295).
- `valid_bootstrap_proofs` pattern-matches exactly five keys and five proofs, checks 64-byte proof lengths, and verifies each positional key/message/signature triple (lines 135-159).
- The mint entrypoint invokes `valid_initial_authority` before `valid_bootstrap_proofs` (validator source lines 61-69). Thus source order alone does not prove actual failure attribution; executed compiled-entrypoint evidence and paired mutant acceptance remain required.

### R5 bad-length fixture

The unchanged case ID and assertion are `applied_keys_bad_length` / `compile_with_short_key_and_matching_datum`. The negative applied parameter and datum agree on five keys, with byte lengths `[31, 32, 32, 32, 32]`; the list is unique and strictly increasing under the manifest's reported comparison. The negative's applied policy ID is `f437579f653982217de579607e0fe15a8542fb33b636f47936bc9c54`. The manifest records five proof byte strings but marks PoP infeasible-for-malformed-parameter. Its prior positive control is a five-key, 32-byte-per-key case under policy `71a4061d5abbdb44d0457e9b30dfd36d72d434f3930c10827f605331`.

A key-length-only source mutation can remove the explicit 32-byte predicate, but cannot make the current negative semantically prove acceptance with verifier-valid PoPs: the original malformed public key remains the input to Ed25519 verification. Altering the proof verifier to skip verification or normalizing/replacing the key would be additional guard/fixture changes and would no longer isolate the named malformed-length condition. Therefore no valid-PoP one-guard acceptance control exists for the R5 bytes.

The manifest records two body-bound ephemeral funding signatures, ADA/native-asset conservation, no persisted private keys, alternate-policy binding, and the synthetic scope. These are candidate manifest claims, not a run result; the package's hashes verified. They do not solve PoP validity or first-failure attribution.

### R5 unsorted fixture

The unchanged case ID and assertion are `applied_keys_unsorted` / `compile_with_unsorted_keys_and_matching_datum`. The negative uses five unique 32-byte keys in a non-increasing order; the exact same vector hash appears for the applied parameter and datum. The negative applied policy ID is `1fb791c31f3e1ca6ca17d0329ace7c345366359fed36096c325a2e93`. Its manifest records five valid PoP signatures bound to this applied parameter. The candidate mutant is separately compiled/rebound as policy `cdeb5869ebdf5f07cac1d70896a2a3ead191357b5c4331ec7d8e1ff2`, with guard label `remove_key_order_guard`; it preserves the same unsorted key vector, proof-signature bytes, seed, raw inputs, and count, while having its own output/transaction and compiled policy.

The one-guard hypothesis is structurally feasible: the mutant removes only the four strict-order comparisons; all five keys remain 32 bytes; the state equals the initial key list; both lists have exactly five elements; PoPs verify against a message that commits to the unsorted vector. The manifest records body-bound ephemeral funding signatures and ADA/native conservation separately for negative, positive, and mutant candidates, with no private keys persisted. These are not execution outcomes. The manifest reports two funding signatures and final-body binding for each candidate; exact bytes still need independent review and simulator execution.

## Verification and evidence boundary

Commands run (read-only except creation of this audit report):

1. `git status --short --branch` and `git rev-parse HEAD` in the canonical checkout: branch/HEAD above; extensive pre-existing dirty state observed and preserved.
2. `grep -RInE "valid_ordered_keys|valid_bootstrap_proofs|authority_genesis_pop_preimage|encoded_ordered_keys" cardano/validators cardano/lib/vams`, targeted `sed`/numbered reads of the two source files: located source references described above.
3. `sha256sum -c SHA256SUMS` from each R5 case directory: all 12 bad-length and all 18 unsorted package entries reported OK.
4. `sha256sum` over both source files and all cited manifests: values recorded above.

No Aiken check/test, Python structural test, transaction-simulator call, signature re-derivation, or external verification was performed. No credit is awarded. Original case IDs/assertions, R4.1 choice C, alternate-policy scope, pending state, and all existing records are unchanged by this audit. Do not infer original-policy, ledger-admission, Cardano Pre-Prod, or live-network evidence. F05/M3 remains OPEN; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
