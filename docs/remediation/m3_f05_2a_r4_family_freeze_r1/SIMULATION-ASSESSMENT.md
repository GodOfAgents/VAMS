# F05 R4 seed-reference family transaction-simulator execution

Date: 2026-10-03
Status: three frozen cases produced the expected target rejection; independent result review PASS.

## Scope

After the coordinator freeze and independent pre-simulation family approval, ran only the three exact frozen negative cases: seed_missing, seed_datum_hash, and seed_datum_index. No positive-control replay, validator source edit, manifest status/count update, ledger submission, or live-network action occurred.

## Verification

The first harness attempt exited 1 at a version-string assertion before any simulator invocation. The pinned binary reports aiken v1.1.21+42babe5; the assertion expected a leading v. The first attempt's stdout, stderr, and exit status are preserved as FIRST-ATTEMPT.*.

After correcting the assertion to the observed pinned version, the exact network-isolated command in SIMULATION-RUN.json exited 0. For each case the snapshot wrapper exited 0, the simulator child exited 1, the classifier reported compiled_evaluation with target_script_invoked=true, policy binding matched 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731 at Mint[0], submitted transaction/raw-input/raw-output hashes matched the freeze, and teardown was clean.

The three simulator child exit-1 outcomes are expected validator rejections, not wrapper failures. The exact per-case hashes and classifications are in SIMULATOR.stdout and SIMULATION-RUN.json.

## Evidence limits

This is synthetic local Aiken transaction-simulator evidence only. It is not ledger admission or live-network evidence. The reviewer independently replayed all three exact frozen transactions and passed the classifications, policy binding, captured hashes, and teardown. This is accepted synthetic simulator evidence. The repository's accepted CASE-STATUS overlay already lists these three IDs as PASS under seed_reference_and_datum_binding, so this supplemental replay advances no count. The frozen family manifests remain unchanged as the pre-execution snapshot. Current accepted F05 remains 45/55 negatives and 18/21 mutations. No INV-1 through INV-10 enforcement or mock-mode behavior changed. Testnet readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Independent integrated result review: PASS for synthetic simulator scope only. See docs/remediation/m3_f05_2a_r4_family_freeze_r1/SIMULATION-REVIEW.md.
