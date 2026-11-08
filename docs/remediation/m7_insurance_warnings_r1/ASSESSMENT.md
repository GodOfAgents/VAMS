# M7 insurance validator warning remediation - 2026-10-03

Status: accepted after independent integrated review. G1 remains failed.

## Scope and invariant impact

Changed only `cardano/validators/insurance_fund.ak`. The mint handler's one-case `when redeemer is` became `let InitializeFund = redeemer` followed by the identical `validate_genesis(...)` call. The test helper parameter `after` became `_after` because `run_test_spend` validates the supplied transaction and does not read that parameter. No validator predicate, test transaction, datum, or function body changed. INV-2 insurance capital/yield behavior is unchanged; the validator's compiled output is byte-identical across baseline and candidate.

Baseline source SHA-256: `3762236d38359a75f45f7a1b2c5f16843fbd0b95ecdf478aa8e8f8c8511e0930`. Candidate SHA-256: `184d5c19c65037ee37999af0988166dca2d28a2e2772e268e1c1738a382ecf5f`. The baseline reconstructs exactly from the prior 73-input G1 manifest. Source snapshots and the exact two-line-scope diff are retained in this directory.

## Verification

Pinned Aiken: `aiken v1.1.21+42babe5`, executable SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`.

- `aiken build` on baseline and candidate copies: both exit 0. Both generated `plutus.json` files have SHA-256 `c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008`; compiled code SHA-256 is `f706581ca7b5c2807bed395c6088d230fd0fc1e7e3a03709f18b5264dc67908c`. Dependencies resolved from the existing local cache.
- `aiken check --deny --skip-tests` in a disposable bubblewrap snapshot with `--unshare-net`: exit 1, 0 errors and 20 warnings; no warning points to `validators/insurance_fund.ak`. This is a diagnostic, not a passing gate.
- `.github/workflows/security-gates.yml` command `aiken check --deny --seed 20260711 --max-success 250` in a disposable bubblewrap snapshot with `--unshare-net`: exit 1; 122/122 test scenarios passed, 1865 checks, 0 errors, 20 warnings. All 73 selected inputs matched canonical preflight and remained unchanged in the snapshot and canonical checkout. G1 remains failed because `--deny` exits nonzero while warnings remain.
- `git diff --check`: exit 0.

Raw outputs, tool/workflow identity, 73-input maps, and content hashes are under `docs/remediation/m7_insurance_warnings_r1/`.

## Independent review

`/root/f05_warning_integrated_review`: PASS for the exact integrated source and evidence packet. The reviewer checked the baseline and candidate hashes, the two warning-only edits, identical build outputs, 20-warning diagnostics, exact G1 command and tool/workflow identity, and every 73-input pre/post map. The reviewer did not edit files or rerun project tools.

## Remaining blockers and evidence limits

F05 remains 45/55 negative cases and 18/21 mutations; this slice grants no case or mutation credit. The `r2_signature_for_other_seed` case remains blocked by the frozen `ledger_tx_sim`/exact-applied-policy evidence requirement and its documented owner decision. Six applied-parameter variants still require an A/B/C owner decision. G1 is failed with 20 warnings remaining in `agent_nft.ak`, `governor.ak`, `timelock.ak`, and `governance_policies.ak`. INV-1 through INV-10, mock containment, provenance/reproducible builds, security/dependency checks, privileged governance, Cardano Pre-Prod and Polygon Amoy prerequisites, and T06/history remain unresolved. Readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. These local results are not ledger admission or live-network evidence.

## Roadmap reassessment and next slice

M7 remains incomplete. The next bounded slice is the four unused imports in `cardano/validators/governor.ak`. Verify every imported name has no use, preserve all governance predicates, compare baseline/candidate compiled output, and rerun the pinned warning and G1 diagnostics before independent review.
