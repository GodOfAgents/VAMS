# M7 governor unused-import warning remediation - 2026-10-03

Status: accepted after independent integrated review. G1 remains failed.

## Scope and invariant impact

Changed only `cardano/validators/governor.ak`. Removed the four imports reported unused by pinned Aiken: `Finite`, `VerificationKey`, `max_voting_duration_ms`, and `signer_threshold`. Each name appeared only in its import in the exact baseline. No validator handler, predicate, test, or governance rule changed. Governance and privileged-role semantics are unchanged; no INV-1 through INV-10 enforcement changed.

Baseline source SHA-256: `aa04f154893e8ca3a0b2856dc8032b4955b5f32cde004a14742acdc81d742de6`. Candidate source SHA-256: `f9383fce703a59a38bece4c78b107e636554e6c427671a83ac0aa6b4b96ace6e`. The baseline matches the prior accepted 73-input manifest. Baseline/candidate source snapshots and the exact diff are retained in this directory.

## Verification

Pinned Aiken: `aiken v1.1.21+42babe5`, executable SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`.

- Network-isolated `aiken build` on baseline and candidate copies: both exit 0. Generated `plutus.json` SHA-256 is `c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008` for both; every compiled script hash matches, including both governor validators.
- Network-isolated `aiken check --deny --skip-tests`: exit 1, 0 errors and 16 warnings, down from 20; no warning points to `validators/governor.ak`. Diagnostic only, not a passing gate.
- `.github/workflows/security-gates.yml` command `aiken check --deny --seed 20260711 --max-success 250`, run in a disposable bubblewrap snapshot with `--unshare-net`: exit 1; 122/122 scenarios passed, 1865 checks, 0 errors, 16 warnings. All 73 selected inputs matched canonical preflight and remained unchanged in the snapshot and canonical checkout. G1 remains failed while the required command exits nonzero.
- `git diff --check`: exit 0.

The exact raw output, build comparison, tool/workflow identity, 73-input maps, and hashes are under `docs/remediation/m7_governor_warnings_r1/`.

## Independent review

`/root/f05_warning_integrated_review`: PASS for the exact integrated source and evidence packet. The reviewer verified all evidence hashes, the exact four-import-only diff and unused-name searches, identical baseline/candidate outputs and compiled scripts, the warning reduction, exact G1 command/tool/workflow identity, and every 73-input pre/post map. The reviewer did not edit files or rerun project tools.

## Remaining blockers and evidence limits

F05 remains 45/55 negative cases and 18/21 mutations; this slice grants no case or mutation credit. `r2_signature_for_other_seed` remains blocked by the frozen `ledger_tx_sim`/exact-applied-policy requirement and its documented owner decision. Six applied-parameter variants still need an A/B/C owner decision. G1 remains failed with 16 warnings in `agent_nft.ak`, `timelock.ak`, and `governance_policies.ak`. INV-1 through INV-10, mock containment, provenance/reproducible builds, security/dependency checks, privileged governance, Cardano Pre-Prod and Polygon Amoy prerequisites, and T06/history remain unresolved. Readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. This is local compiler/test evidence only, not ledger admission or live-network evidence.

## Roadmap reassessment and next slice

M7 remains incomplete. The next bounded slice is the three warnings in `cardano/validators/timelock.ak`: the unused `Finite` and `intent_immutable` imports, plus only the unused callback parameter in `find_authority_config`. Do not rename the separate `input` binding used to locate the validator's own input. Prove compiled output unchanged and rerun the warning and G1 diagnostics before review.
