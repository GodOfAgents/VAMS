# Independent paired execution review: applied_genesis_parameter R6/R7/R9

Date: 2026-10-05

## Verdict

**PASS for paired synthetic execution attribution, limited to the single negative case `applied_genesis_parameter`.** Recommend that the designated evidence-ledger writer classify that case as a transaction-simulator PASS after reconciling this review. This review does not amend the overlay.

The accepted R6 control, rejected R7 negative, and accepted R9 one-guard mutant are bound to the retained R5 case and the exact synthetic alternate-applied-policy lineage. R7 reaches and is rejected at compiled Mint[0]; R9 removes only the named seed-input guard and is accepted at its own compiled Mint[0]. This supports the named negative-case attribution only. **Do not add mutation-suite credit**: the mutant is an attribution control, not an independently accepted mutation-suite row.

## Exact record identities

- R6 positive RUN: SHA-256 `457cb0ec423477df1d232501506e713f3ce7800210635b35535abff0b2417c8e`.
- R7 negative RUN: SHA-256 `651fc64426b0968828a597564b48ae4a6dbba68b0f5d516d37f28b8bc5924d7e`.
- R9 mutant RUN: SHA-256 `4ce6eebe967ac9cf44e57a30c3dac5242071c9d0b1ad944d65064f6b890f7b3b`; its package SHA256SUMS file is `81c65e78e5117fe4c4e2a8e1e58f59a0cbcf9d3ec0e41021415f13f96abefec4`.
- R5 family manifest: SHA-256 `3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e`; the applied_genesis_parameter case manifest is `594e9fe401253d4fa4cae33f71861ae5b45502d7098635da380c8618a96f23a6`.
- R2 mutant candidate manifest: SHA-256 `02f8dca9edac5a8bb52f39fcc9deabdfc6cf93e447a0bf170403c4ef95af61fd`; source patch: `fd6f06b112efebd2b63833d84d77b5611534fd1ef3268886859f3122e2e5ca23`.
- Prior independent pre-execution byte review: verdict PASS; review file SHA-256 `303e50a083118970f86236a598491abf224d042f25ee747f41244d16b75774ba`; its checksum file SHA-256 `780e83db5540bc407a0de6e7d6fd6970b82050799ac7b4f8994ec7eeae5a69f2`.

## Paired findings

R6 and R7 both record the R5 applied policy ID `fc305fd82585607dc1998425cbe3bce8f43667e1ac161c448098c058`, with compiled hash, expected policy, and sole minted policy ID matching. The policy bytes are the R5 case artifact, SHA-256 `66d372129d322008e8b095f87b0b7726d3020868954361578a774f4afe8e6c5d`. R6 records `script_accepted` at the intended Mint[0] entrypoint; R7 records `compiled_evaluation` rejection there. Both use Aiken `1.1.21+42babe5` and the same recorded immutable R3 runner hash. Their records identify two valid body-bound ephemeral funding signatures, conserved ADA and native assets, clean runner cleanup, and no persisted private keys.

The R2 candidate and its pre-execution review bind the R9 fixture to the exact R5 negative case: unchanged R5 genesis-reference and initial-key sidecars, exact PoP redeemer and parameter seed/key/signature lineage, and the same negative transaction semantics (the seed input is absent). The R9 patch changes just one source predicate: `count_seed_input(tx.inputs, genesis_ref) == 1` becomes `True`. R9 rebinds the compiled program, Mint policy, authority NFT, and Plutus V3 witness to mutant policy `1d20d3c373cd806fbbf9634a4840ce2cfcbeccd1ae9fd89a8ccbee83`; all recorded policy-binding values agree. The R9 record reports the two body-bound ephemeral funding signatures, ADA/native-asset conservation, clean cleanup, and `private_key_material_persisted: false`.

The exact R9 structured result is:

```json
{
  "wrapper_exit_code": 0,
  "simulator_child_exit": 0,
  "stage": "script_accepted",
  "target_script_invoked": true,
  "cleanup": "clean",
  "transaction_sha256": "7a590ae68203a4cbc0cddf3959c645d5bbd6e56a1c523b2949e05838008f06e0",
  "raw_inputs_sha256": "4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
  "raw_outputs_sha256": "7816fe012b4c206ed7cdbace0c8eaded68becf9e035d44906612b14ca39fbf03",
  "target_mint_binding": {
    "compiled_script_hash": "1d20d3c373cd806fbbf9634a4840ce2cfcbeccd1ae9fd89a8ccbee83",
    "expected_policy_id": "1d20d3c373cd806fbbf9634a4840ce2cfcbeccd1ae9fd89a8ccbee83",
    "policy_ids": ["1d20d3c373cd806fbbf9634a4840ce2cfcbeccd1ae9fd89a8ccbee83"]
  }
}
```

The prior R2 reviewer independently accepted the exact candidate bytes and source mutation, but explicitly did **not** independently rebuild the compiled mutant. This paired review also did not invoke a compiler or simulator; it checked the exact retained execution records, their digests, fixture lineage, recorded runner result, and the accepted pre-execution review. Thus the record supports synthetic attribution, with a remaining reproducibility limitation on independently rebuilding the compiled mutant.

## Credit boundary and readiness

Recommended credit: one transaction-simulator negative case, `applied_genesis_parameter`, under the synthetic alternate applied policy only. Mutation-suite credit remains unchanged. Grant no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. Captures are local structured records; raw simulator stdout/stderr and external attestation are not retained.

F05/M3 remains open. Readiness remains **NOT READY**. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Verification performed

Read-only checks; no simulator, compiler, network, installation, or fixture mutation was performed during this review.

- `sha256sum docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r6_20261005/RUN.json docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r7_20261005/RUN.json docs/remediation/m3_f05_2a_applied_genesis_mutant_attempt_r2_20261005/RUN.json` — PASS; exact hashes above.
- `cd docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005 && sha256sum -c SHA256SUMS` — PASS.
- `cd docs/remediation/m3_f05_2a_applied_genesis_mutant_r2_20261005 && sha256sum -c SHA256SUMS` — PASS.
- `cd docs/remediation/m3_f05_2a_evidence_classification_r2_20261005 && sha256sum -c SHA256SUMS` — PASS.
- `sha256sum -c docs/remediation/m3_f05_2a_applied_genesis_mutant_r2_review_r1_20261005/SHA256SUMS` from the repository root — PASS.
- `cd docs/remediation/m3_f05_2a_applied_genesis_mutant_attempt_r2_20261005 && sha256sum -c SHA256SUMS` — PASS.
