# Independent paired-attribution review: applied_genesis_parameter

Date: 2026-10-05

## Verdict

**FAIL - paired attribution is not established.** Keep the original `applied_genesis_parameter` case PENDING. Grant no mutation-suite credit. The recorded mutant acceptance does not establish that the R7 normal-policy rejection was caused by removing the named seed-input guard because the R7 and R8 fixtures do not share applied initial-key parameters or policy identity.

## Reviewed records and integrity

The following stored RUN records were inspected:

- R6 positive: `docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r6_20261005/RUN.json`, SHA-256 `457cb0ec423477df1d232501506e713f3ce7800210635b35535abff0b2417c8e`.
- R7 negative: `docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r7_20261005/RUN.json`, SHA-256 `651fc64426b0968828a597564b48ae4a6dbba68b0f5d516d37f28b8bc5924d7e`.
- R8 one-guard mutant attempt: `docs/remediation/m3_f05_2a_applied_genesis_mutant_attempt_r1_20261005/RUN.json`, SHA-256 `1ba9e5ca8e2aee64ace71e4a4f7c5c3683ce689bf877440de308d8c622489b17`. Its SHA256SUMS index is `0e882d678b08ed026b94a8f1b2c6bd7677634e6c3e8f93740648ed0c33385fd2`.
- R8 reviewed candidate manifest: `docs/remediation/m3_f05_2a_applied_genesis_mutant_r1_20261005/FIXTURE-MANIFEST.json`, SHA-256 `b699a7e044ca2fcf7314932cf35bb318eabe52bd113a355405b361879807ed5f`. Its SHA256SUMS index is `d18907483afcbae4b8f9fbe28611702f8841d00df5c591ff20f6085ec5181aba`.
- R5 family manifest: `docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/FAMILY-MANIFEST.json`, SHA-256 `3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e`; root SHA256SUMS index SHA-256 `ad27af4dd49aac3e8d0ba570468adf5c4fc32e02b5acc3303b2f40b67e5c71f0`.

Read-only verification used:

```sh
cd /home/GodOfAgents/code/VAMS-testnet
cd docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r6_20261005 && sha256sum -c SHA256SUMS
cd ../m3_f05_2a_applied_parameter_sim_attempt_r7_20261005 && sha256sum -c SHA256SUMS
cd ../m3_f05_2a_applied_genesis_mutant_attempt_r1_20261005 && sha256sum -c SHA256SUMS
cd ../m3_f05_2a_applied_genesis_mutant_r1_20261005 && sha256sum -c SHA256SUMS
cd ../m3_f05_2a_applied_parameter_family_r5_20261005/applied_genesis_parameter && sha256sum -c SHA256SUMS
```

All listed file checks passed. The independently supplied expected R8 structured runner result matches the stored R8 result fields. No simulator was run for this review.

## Attribution mismatch

R5/R6/R7 use the applied initial-keys SHA-256 `9b604d528d46f510b808d00ad985e498522a7d60595823ce016adb647ff9556f` and alternate applied policy ID `fc305fd82585607dc1998425cbe3bce8f43667e1ac161c448098c058`.

R8 uses a different initial-keys SHA-256, `e29d73ad4b9ee55ebb5a093e16f97d582e23c34fd2c5ae8e2ca91be8a10a6a14`, normal policy ID `3c74bddc66d6a48cf20bbb1d37a241e29ffebd8c1f2468edafb216ba`, and mutant policy ID `3a79876afa3121d9fb65d21ce32bcd0e5daa1e1e8477cea652114125`. The negative and mutant transactions therefore do not share the same applied-policy/key identity; their transaction and output hashes also differ. The R8 patch changes only `expect count_seed_input(tx.inputs, genesis_ref) == 1` to `expect True`, but that source-level one-guard fact does not cure the fixture identity mismatch.

Each individual attempt record reports Mint[0] target invocation, a sole mint bound to its own V3 script witness, two valid body-bound ephemeral funding signatures, ADA/native-asset conservation, clean cleanup, and no persisted private key material. Those per-record claims do not prove cross-record pairing when the applied parameters differ.

## Credit and readiness

The records support only their recorded local synthetic executions under their respective alternate policies. They grant no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. Because named-condition attribution is not established, keep the negative case PENDING; award no mutation-suite credit. F05/M3 remains open, readiness remains NOT READY, and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Review limitations

The attempt records state that exact structured runner results were transcribed into local records; raw simulator stdout/stderr and external attestation are not retained. This review checked stored checksums and compared the evidence/manifests and source patch; it did not rerun the simulator, access a network, decode and independently re-verify every transaction signature, or repeat the funding/PoP cryptographic checks. Accordingly, per-fixture execution claims remain bounded by the retained local records.
