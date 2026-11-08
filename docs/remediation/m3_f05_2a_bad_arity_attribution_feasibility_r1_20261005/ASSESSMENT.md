# F05.2a bad-arity attribution feasibility audit

Date: 2026-10-05
Status: READ-ONLY AUDIT; no fixture execution; both cases remain PENDING.
Scope: determine whether locally pinned Aiken/UPLC tooling or exact compiled bytes can yield R4.1-compliant first-failure attribution for applied_keys_bad_count and applied_keys_bad_length.

## Conclusion

Both cases are BLOCKED for R4.1 first-failure attribution with the currently available local toolchain and retained artifacts. Keep original rows applied_keys_bad_count and applied_keys_bad_length PENDING. This audit did not execute malformed negatives or mutants and did not build or run tests.

Source inspection indicates the first source-level false check in valid_ordered_keys is the exact-five-element pattern for six keys, and the first-key width predicate for the fixture containing a 31-byte key. This is source-level inference only. The available transaction simulator and R3 runner expose Mint[0] invocation and generic compiled rejection, not the named failing guard. Exact applied-script CBOR is retained, but no matching source map, evaluator trace, or other exact-program/input-bound attribution artifact was found. Source control flow alone does not satisfy R4.1.

No original-policy, full-ledger-admission, or live-network credit is granted or inferred.

## R4.1 requirement

Controlling amendment: docs/remediation/m3_f05_2a_evidence_contract_r4_1_20261005/CONTRACT-R4.1.json
SHA-256: 238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171

For these two cases, R4.1 requires that “the unmodified compiled target at Mint[0] must provide a pinned evaluator trace, source map, or equivalent independently reviewable evidence tied to the exact compiled program bytes and this input, identifying the named key-count/key-length guard as the first rejecting condition.” It says: “If first failure cannot be established or is ambiguous, retain PENDING.” It disallows guard-removal mutant acceptance as a substitute because other checks independently reject. Original IDs and assertions are preserved; no original-policy, ledger-admission, or live-network credit is allowed.

## Source ordering and exact source hashes

cardano/validators/f05_authority_policy.ak SHA-256 e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8. Mint[0] checks seed/output conditions, decodes state, then calls valid_initial_authority(state, genesis_ref, initial_keys), before constructing/verifying bootstrap PoPs (around source lines 61–69).

cardano/lib/vams/f05_authority.ak SHA-256 657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3. valid_initial_authority checks valid_ordered_keys(initial_keys) before state.ordered_keys == initial_keys (around lines 89–90). valid_ordered_keys pattern-matches exactly five keys, then checks each length equals 32 (around lines 268–282). valid_bootstrap_proofs later pattern-matches exactly five keys and proofs (around lines 136–159).

Thus source order suggests six keys fail the list-shape arm, and the 31-byte first key fails its first width predicate before later proof checks. This does not establish evaluator first failure on the exact applied bytes and input.

## Tool and evidence capability

Pinned Aiken binary: /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken
Version: aiken v1.1.21+42babe5
SHA-256: 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79

Read-only aiken tx simulate --help shows CBOR, slot, blueprint, and script-override options; no trace/source-map/verbosity option. aiken check --debug is for pretty-printing UPLC on failing native tests, not a transaction evaluator trace bound to these exact bytes and inputs.

scripts/remediation/f05_2a_tx_sim_runner_r3.py SHA-256 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c. It snapshots CBOR, verifies mint policy ID against the V3 witness hash, invokes aiken tx simulate --cbor, then reports classified stage/invocation and input hashes.
scripts/remediation/f05_2a_tx_sim_registry.py SHA-256 c03230249c7e73f6929cc944b7af3e30d98b8168f8abd184fa39332a601a394e. Its reject classification is generic: exact Mint[0] invocation markers followed by “Error failed script execution” and “Mint[0] the validator crashed / exited prematurely.” It records no internal guard trace.

The prior UPLC diagnostic at docs/remediation/m3_f05_2a_uplc_backend_r1/ASSESSMENT.md records direct aiken uplc eval failure “Default Function not found - verifySignature,” not a validator trace. No uplc or cardano-cli executable was found on PATH; a read-only filename search of /home/GodOfAgents/vams-evidence/toolchains found no standalone UPLC/Cardano evaluator binary. Existing unrelated M7 .uplc files are other mutation programs and have no source-map linkage to these two R5 exact programs.

cardano/plutus.json SHA-256 718845f253ebdfb9f1d565e34511534f6b565cf1dd898402b67109180dff6492. The R5 package retains the exact applied-policy CBOR, but this audit found no matching trace/source-map artifact bound to that program and context.

## Per-case artifacts and status

### applied_keys_bad_count

Original assertion: compile_with_six_keys_and_matching_datum.
Named property: valid_ordered_keys requires exactly five keys.
Alternate applied policy ID: 4fa737ebb0a7133d941fc952c7fdc865272722096943196b2094fbc6.
Parameter CBOR SHA-256: 793ac8c504086e4af0f663bce1497bf70fdf626e35b086afc03ab3711b4fd458.
negative.applied-policy.cbor SHA-256: 267881bd77331855ae56cccf4b5a7220072841881bb1d9128fb4eb794543ec67.
negative.tx.cbor SHA-256: b605624a10e16c3047b039ebbe8325c26bf72f2d8a3522f2b4da85b206c8ac76.
negative.raw_inputs.cbor SHA-256: 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe.
negative.raw_outputs.cbor SHA-256: f09df04c62cec887ac86589802ed1ffc6743ca2f179335f02f9bdc60937e8478.
Manifest says PoPs are infeasible for malformed shape; six keys cannot satisfy the five-key proof verifier. No R4.1 first-failure evidence found. PENDING.

### applied_keys_bad_length

Original assertion: compile_with_short_key_and_matching_datum.
Named property: bytearray.length(first) == authority_key_bytes.
Alternate applied policy ID: f437579f653982217de579607e0fe15a8542fb33b636f47936bc9c54.
Parameter CBOR SHA-256: e70fd9ebcb973ae2efed33ad9dc68f783b835863ce93f45fb9de38cb6e38b183.
negative.applied-policy.cbor SHA-256: ea58458f34f06833a83c1489e53293a1963ad3ebf6880499bca82c1dbe2e8496.
negative.tx.cbor SHA-256: d4770335a664afb567fdaf5f56612532a589aa2873354775549b8fcb3d29d8e2.
negative.raw_inputs.cbor SHA-256: 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe.
negative.raw_outputs.cbor SHA-256: 962cb64395e964d3ddefd1ff9700350228a7002532ed2cff063b7aac69c27624.
Manifest says PoPs are infeasible for malformed shape; the first key is 31 bytes and the proof verifier requires a 32-byte key. No R4.1 first-failure evidence found. PENDING.

Both manifests name f05_authority_policy.f05_authority_policy.mint / Mint[0], describe conservation and ephemeral funding-signature properties, and leave attribution unestablished. These manifest claims are not execution results.

## Commands and observed results

All inspection occurred in /home/GodOfAgents/code/VAMS-testnet. HEAD observed: 829ab544571f12efe50ecb5740f129c8acb3e16f; branch testnet/remediation-20260907; many pre-existing changes were present and left untouched.

- git status --short --branch; git rev-parse HEAD: observed branch, HEAD, and pre-existing dirty state.
- grep -nE "valid_initial_authority|valid_ordered_keys|valid_bootstrap_proofs" cardano/lib/vams/f05_authority.ak plus read-only source views: confirmed helper order and list/width patterns.
- /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken --version: aiken v1.1.21+42babe5.
- /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken tx simulate --help: only CBOR/context options, no trace/source-map option.
- /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken check --help: --debug is native-test UPLC output; no tests were run.
- Read-only inspection of runner/registry: generic failure classification only.
- command -v cardano-cli; command -v uplc; command -v aiken: no command found on PATH.
- find /home/GodOfAgents/vams-evidence/toolchains -maxdepth 4 -type f with UPLC/Plutus/Cardano CLI name filters: no standalone evaluator executable found.
- Read-only inspection of R5 manifests, prior UPLC diagnostic, and retained evidence: no R5 exact-byte/input first-failure trace/source-map record.

No malformed transaction, mutant, simulator, build, unit test, or network command was run. No fixtures, STATUS, HANDOFF, or other evidence files were modified.
