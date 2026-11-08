# Independent review: bad-arity attribution feasibility audit

Date: 2026-10-05
Review revision: r1
Canonical checkout: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

Decision: PASS for the audit package integrity and its conclusion that applied_keys_bad_count and applied_keys_bad_length must remain PENDING under R4.1 until a compliant, exact-input compiled first-failure proof becomes available. The source order is only an inference about likely first failure; it is not compiled first-failure evidence. No malformed negative or mutant was executed or credited by this audit/review.

## Scope and method

Read-only review of docs/remediation/m3_f05_2a_bad_arity_attribution_feasibility_r1_20261005/ASSESSMENT.md, its checksum, controlling R4.1 contract, validator/library source, Aiken binary identity, R3 runner/classifier, retained UPLC diagnostic, frozen R5 malformed fixtures, and the R5 case-status overlay. No tests, builds, malformed fixtures, simulators, or network operations were run. No source, fixture, STATUS, HANDOFF, or existing evidence record was changed. Only this independent review and its SHA256SUMS were written.

Exact verification commands/results:

- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_bad_arity_attribution_feasibility_r1_20261005 && sha256sum -c SHA256SUMS` — PASS: ASSESSMENT.md OK.
- `sha256sum` over each cited contract, source, tool, diagnostic, and R5 case artifact — PASS: all values match the audit's recorded identities below.
- `cd .../applied_keys_bad_count && sha256sum -c SHA256SUMS` — PASS: all 12 package entries OK.
- `cd .../applied_keys_bad_length && sha256sum -c SHA256SUMS` — PASS: all 12 package entries OK.
- Read-only Python recomputation of each parameter digest and Plutus V3 policy ID — PASS for both cases.
- Read-only source inspection of valid_initial_authority, valid_ordered_keys, valid_bootstrap_proofs, Mint[0], and the runner classifier — confirms the source ordering and generic rejection classification described below.
- Read-only comparison with R5 CASE-STATUS.json — both negative case IDs are in pending; totals are 49/55 negative cases, 45/51 transaction_simulator, and 18/21 mutations.
- A targeted search for per-case bad_count/bad_length simulator-attempt directories returned none. This does not assert that no separate valid positive control exists: R13 is a previously reviewed five-key positive control for the bad_count family, and does not establish malformed-negative rejection attribution or negative-case credit.

## Audit package and controlling identities

- ASSESSMENT.md SHA-256: `7e80bbd9bf57c78b03dc78b7cdbde48c4f92967b52cc1b1e0c0463da058c2fcc`.
- Package SHA256SUMS file SHA-256: `3a1f5376753674ecf1d6c68ae859cfec019e89377b21fc54b26cf282633c0206`.
- R4.1 contract `docs/remediation/m3_f05_2a_evidence_contract_r4_1_20261005/CONTRACT-R4.1.json`: `238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171`.
- Mint validator `cardano/validators/f05_authority_policy.ak`: `e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8`.
- Authority library `cardano/lib/vams/f05_authority.ak`: `657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3`.
- Pinned Aiken executable: `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`; the assessment records version `aiken v1.1.21+42babe5`.
- Immutable R3 runner `scripts/remediation/f05_2a_tx_sim_runner_r3.py`: `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c`.
- R3 registry/classifier `scripts/remediation/f05_2a_tx_sim_registry.py`: `c03230249c7e73f6929cc944b7af3e30d98b8168f8abd184fa39332a601a394e`.
- `cardano/plutus.json`: `718845f253ebdfb9f1d565e34511534f6b565cf1dd898402b67109180dff6492`.
- Prior UPLC backend assessment: `83eec0803f7bc30d1d1931c7d903f2dded156717527089edb031383ebaaad0fb`.

The controlling R4.1 contract requires either reviewer-verifiable first-failure attribution from the unmodified compiled target at Mint[0], tied to exact program bytes and input, or acceptance of the same negative by a separately rebound one-guard mutant. If neither establishes the named assertion, the row remains PENDING. It also requires independent byte review, exact mint/applied-policy/V3-witness identity, body-bound ephemeral funding signatures, and conservation for any execution. The audit's contract hash matches the current file.

## Exact R5 fixture identities

R5 family: `docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/`.

### applied_keys_bad_count

- ID/assertion: `applied_keys_bad_count` / `compile_with_six_keys_and_matching_datum`.
- Case manifest SHA-256: `ccb48ebdf61669d2cd07e06ebd62832b72bc4f06f92e5e476c74c7a0479174c3`.
- Applied policy ID: `4fa737ebb0a7133d941fc952c7fdc865272722096943196b2094fbc6`.
- Parameter digest: `793ac8c504086e4af0f663bce1497bf70fdf626e35b086afc03ab3711b4fd458`; recomputation from genesis-reference plus initial-key CBOR matches.
- Key-vector CBOR SHA-256: `08124a692a07be0284fe0b9ea33355f17a3642df4d42945b3e23245a2257ffa5`; six unique, 32-byte keys; the manifest records only five PoP proofs and marks PoPs infeasible for this malformed parameter.
- Negative applied-policy CBOR SHA-256: `267881bd77331855ae56cccf4b5a7220072841881bb1d9128fb4eb794543ec67); recomputed Plutus V3 policy ID matches the applied ID.
- Negative tx/input/output SHA-256: `b605624a10e16c3047b039ebbe8325c26bf72f2d8a3522f2b4da85b206c8ac76`, `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe`, `f09df04c62cec887ac86589802ed1ffc6743ca2f179335f02f9bdc60937e8478`.
- Manifest negative status: PENDING; proof status: infeasible-for-malformed-parameter.

### applied_keys_bad_length

- ID/assertion: `applied_keys_bad_length` / `compile_with_short_key_and_matching_datum`.
- Case manifest SHA-256: `8a10528d1630ab46226126127f3b0bfaa8193c8ff151d13a6451d581e7ce1d1c`.
- Applied policy ID: `f437579f653982217de579607e0fe15a8542fb33b636f47936bc9c54`.
- Parameter digest: `e70fd9ebcb973ae2efed33ad9dc68f783b835863ce93f45fb9de38cb6e38b183`; recomputation from genesis-reference plus initial-key CBOR matches.
- Key-vector CBOR SHA-256: `db8eed8996fe19e3afafa10290345f2a69c5eaff43c90611782e0114598808ff`; five unique keys, first key 31 bytes; the manifest marks PoPs infeasible for this malformed parameter.
- Negative applied-policy CBOR SHA-256: `ea58458f34f06833a83c1489e53293a1963ad3ebf6880499bca82c1dbe2e8496`; recomputed Plutus V3 policy ID matches the applied ID.
- Negative tx/input/output SHA-256: `d4770335a664afb567fdaf5f56612532a589aa2873354775549b8fcb3d29d8e2`, `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe`, `962cb64395e964d3ddefd1ff9700350228a7002532ed2cff063b7aac69c27624`.
- Manifest negative status: PENDING; proof status: infeasible-for-malformed-parameter.

Both manifests state two valid final-body-bound ephemeral funding signatures, ADA/native-asset conservation, and no persisted private keys. Those are fixture-manifest claims, not execution results. No malformed negative or mutant attempt was found or run in this audit.

## Source inference versus compiled first-failure proof

The pinned source supports the following control-flow inference:

- Mint[0] calls `valid_initial_authority` before `valid_bootstrap_proofs`.
- `valid_initial_authority` evaluates `valid_ordered_keys(initial_keys)` before datum-key equality.
- `valid_ordered_keys` pattern-matches exactly five list elements, then checks key widths. Thus a six-key input is rejected by the five-element arm; for the five-key short-key fixture, its first width predicate is false for the 31-byte first key.
- `valid_bootstrap_proofs` also requires exactly five keys and five proofs. A six-key one-guard mutant that only relaxes `valid_ordered_keys` still encounters the separate exact-five proof verifier. Relaxing only key width for the short key still passes that malformed 31-byte key to Ed25519 verification, which has no verifier-valid 32-byte-key PoP for that input.

These are source-level observations and feasibility reasoning. They do not identify the actual failed predicate in a compiled execution.

The exact R3 runner verifies the selected transaction mint policy and V3 witness hash, snapshots the selected bytes, invokes Aiken simulation, and records target invocation/stage. Its classifier maps the exact Mint[0] crash transcript only to generic `compiled_evaluation`; it does not retain or expose an internal failing `expect`, source map, or guard trace. The audit's exact-program/input-linked trace/source-map search found no matching attribution artifact. The prior UPLC assessment's direct evaluation failure was `Default Function not found - verifySignature`, not an evaluation trace for either exact R5 transaction.

Therefore, source order is not compiled first-failure proof, and generic Mint[0] rejection cannot distinguish the named arity/length assertion from another rejecting condition. For these malformed R5 shapes, the independent proof verifier also blocks a one-guard mutant from accepting the same negative while preserving the other production checks. Under the current R4.1 bar, no negative or mutation credit is supported; both rows correctly remain PENDING. Any future path must supply exact-program/input-linked evaluator/source-map evidence or a validly amended evidence contract before execution/credit is considered.

This verdict grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. F05/M3 remains open; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.