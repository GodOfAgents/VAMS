# M7 timelock warning remediation - 2026-10-03

Status: accepted after independent integrated review. G1 remains failed.

## Scope and invariant impact

Changed only `cardano/validators/timelock.ak`: removed the unused `Finite` and `intent_immutable` imports, and renamed the unused callback parameter to `_input` only in `find_authority_config`. The separate `input` binding that locates the validator's own input remains unchanged. No validator logic, authorization predicate, redeemer branch, or test changed. Timelock authorization and delay semantics are unchanged; no INV-1 through INV-10 enforcement changed.

Baseline source SHA-256: `ec73329d402a8d32e826fb930fb66c48a378dda2795aa525944d5208ea39fae0`. Candidate SHA-256: `7a2a07f6ef576901fd7fceea059ccfe7cbafde424249a9c5a7d19bba60d4dae3`. The baseline reconstructs exactly from the preceding G1 input map.

## Verification

Pinned Aiken: `aiken v1.1.21+42babe5`, executable SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`.

- Network-isolated `aiken build` on baseline and candidate: both exit 0; generated `plutus.json` and all compiled script hashes are identical. Timelock spend/else compiled hash: `f4c00027e1c8f461b9e34d378090a665647ddbe637031f9f811bec8429428553`.
- Network-isolated `aiken check --deny --skip-tests`: exit 1, 0 errors and 13 warnings, down from 16; no warning points to `validators/timelock.ak`.
- CI command `aiken check --deny --seed 20260711 --max-success 250` in a disposable bubblewrap snapshot with `--unshare-net`: exit 1; 122/122 scenarios passed, 1865 checks, 0 errors, 13 warnings. All 73 selected inputs matched canonical preflight and remained unchanged in snapshot and canonical checkout. G1 remains failed while the required command exits nonzero.
- `git diff --check`: exit 0.

Raw outputs, build comparison, exact command/tool/workflow identity, 73-input maps and hashes are under `docs/remediation/m7_timelock_warnings_r1/`.

## Independent review

`/root/f05_warning_integrated_review`: PASS for the exact integrated source and evidence packet. The reviewer verified the exact scoped diff, preservation of the own-input binding, baseline/candidate source hashes, all build outputs, warning results, command/tool/workflow identity and every 73-input pre/post map. The reviewer did not edit files or rerun project tools.

## Remaining blockers and evidence limits

F05 remains 45/55 negative cases and 18/21 mutations; no case or mutation credit follows. `r2_signature_for_other_seed` remains blocked by the frozen `ledger_tx_sim`/exact-applied-policy requirement and its owner decision. Six applied-parameter variants still require an A/B/C owner decision. G1 remains failed with 13 warnings in `agent_nft.ak` and `governance_policies.ak`. INV-1 through INV-10, mock containment, provenance/reproducible builds, security/dependency checks, privileged governance, Cardano Pre-Prod and Polygon Amoy prerequisites, and T06/history remain unresolved. Readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. This is local compiler/test evidence only, not ledger admission or live-network evidence.

## Roadmap reassessment and next slice

M7 remains incomplete. The next bounded slice is to audit `cardano/validators/agent_nft.ak` against its current references and validator requirements before editing: its warning list includes an unused private `valid_did` helper, and the current handler's behavior must be established from source and tests. Treat any validator-behavior defect as a separate remediation from warning cleanup and obtain independent review for the exact integrated result.
