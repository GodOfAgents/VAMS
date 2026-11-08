# Independent review: applied_keys_parameter R11 negative attempt

Status: **FAIL for named-condition credit; PASS only as a recorded synthetic compiled rejection.** The R11 run is bound to the selected R5 fixture and the accepted R10 positive control. It establishes rejection during compiled Mint[0] evaluation under the alternate applied policy. The evidence bundle does not independently establish which assertion caused the rejection, so the original negative case remains PENDING.

## Scope and evidence checked

- R11 `RUN.json` SHA-256: `ca0e17acffdffe5877ee6f1b6ffc2facefbbb70a89ab29c78f488b9c5da92cad`; its adjacent `SHA256SUMS` verifies.
- R10 positive-control `RUN.json` SHA-256: `fdd13ca0572ba92c302d0e5537ee2670520570dcf25977feb39ebebaa6a3a2c9`; its adjacent `SHA256SUMS` verifies.
- The earlier independent R10 review verifies and accepts the positive control only: `docs/remediation/m3_f05_2a_applied_keys_parameter_positive_review_r1_20261005/INDEPENDENT-REVIEW.md`, SHA-256 `bd72af850dae32100958c0d70ab4c5acfc1605485a8b1efab1d96eab424fd097`.
- The R5 family and selected-case fixture checksum lists both verify from their documented bases. The R5 family manifest SHA-256 is `3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e`; the selected `FIXTURE-MANIFEST.json` SHA-256 is `c9cfa8d645dcb99fa20fa9933b88190b02027f724fba3c67d081efd0c06dac24`.

## Findings

1. R11 submitted the exact R5 negative bytes: transaction `f57020cb1d5ac3a7eebf8885472c62e6c0c1c4f8f2c9f85f890beac25194413f` (5,104 bytes), raw inputs `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe` (73 bytes), and raw outputs `c36f6ae6016bdf289d87758b37b6feab4daf13be58deadff57fdae12bf562645` (79 bytes). Each matches the selected case manifest.
2. The invocation uses the R4.1 choice C alternate applied policy `efec0d79e496e2df81f8e3e27734c9718655dc577070c7519645fa29`. R11 reports the expected policy ID, compiled script hash, and sole minted policy ID equal, target script invoked at Mint[0], stage `compiled_evaluation`, child exit 1, and clean cleanup (child reaped, process group empty, descriptors closed).
3. R10 uses the same alternate policy and exact compiled binding. Its accepted positive-control fixture has transaction hash `97f584e0f071b774883d15237042cefddff6e7b471d58329fcb5f24a08775c7d`; the independent R10 review accepts that local synthetic positive-control execution. The two results therefore form a valid policy/entrypoint-matched control pair.
4. The R5 manifest records five valid PoPs, two valid body-bound ephemeral funding signatures, ADA and native-asset conservation, and no persisted private keys for each fixture. R11's submitted hashes match those reviewed fixture bytes. This review did not rederive the signatures. The private-key claim is scoped to the recorded fixture-generation process, not an audit of unrelated filesystem state.
5. Source review identifies the intended assertion in `cardano/lib/vams/f05_authority.ak`: `valid_initial_authority` checks `state.ordered_keys == initial_keys`. The negative manifest describes sorted, unique, 32-byte applied keys, while the authority datum retains the original sorted key list; the negative proof signatures are declared bound to the applied parameter key list. The generator intends that state/applied-key mismatch to be the single semantic negative condition.
6. Nevertheless, R11 records only generic compiled evaluation rejection. It retains no simulator stdout/stderr, assertion trace, or external attestation. The accepted positive control demonstrates the alternate policy can accept its matching datum, but alone does not prove the negative was rejected specifically by the equality assertion. Accordingly this review does **not** credit `compile_with_different_sorted_keys_keep_datum` yet.
7. Scope remains local synthetic alternate-policy evidence only. No original-policy, mutation-suite, full-ledger-admission, Pre-Prod, or live-network credit follows. No case status or readiness record was changed by this reviewer.

## Minimum next safe control

Prepare a narrowly scoped one-guard counterfactual for `applied_keys_parameter`: under the same applied parameter keys, change only the equality guard `state.ordered_keys == initial_keys` to `True`; create a mutant-bound transaction with valid body-bound funding witnesses and PoPs for that mutant script context, and preserve value conservation. Independently review the exact source patch, compiled artifact identity, and fixture bytes before executing that control. Acceptance of the otherwise corresponding mismatch fixture under the mutant, paired with R10 acceptance and R11 rejection under the unmodified policy, would establish the named guard attribution. Keep the case PENDING until that control and the paired evidence receive independent review.

This review authorizes no fixture execution and grants no classification credit.
