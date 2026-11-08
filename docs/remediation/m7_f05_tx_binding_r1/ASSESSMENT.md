# F05 typed transaction mint-binding guard assessment - 2026-10-03

## Decision

Accept this bounded F05 simulator-evidence binding fix. It hardens only the local typed-CBOR evidence verifier and its regression test. It does not change the validator, compiled applied policy, ledger evidence, or case/mutation status.

## Finding and change

The failing test loaded the CBOR helper twice. Its second module instance decoded the typed transaction into Map/Tag classes that the first instance's encoder did not recognize, causing an unsupported fixture-value error. The fixture now decodes and re-encodes through the same helper instance.

That correction exposed the assertion the test was intended to exercise: duplicate policy entries in a typed mint map were collapsed by a set comprehension in `verify_mint_binding`. The verifier now requires the mint field to be a CBOR Map containing exactly one pair and requires that pair's policy ID key to be bytes before comparing the ID and witness hash. Duplicate keys therefore fail before the simulator subprocess can run.

## Verification

Pinned environment: Python 3.12.14, pytest 9.1.1; the existing Envoy 1.39.1 binary matches SHA-256 `002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8`.

- Focused contract module: 2 passed in 0.06s.
- Three directly related F05 simulator contract/runner modules: 21 passed and 15 nested subtests passed in 0.87s.
- Full root split invocation with pinned Python on PATH and Envoy configured: 1,570 passed, 5 failed, 441 nested subtests passed in 200.09s; exit 1. The F05 contract failure is resolved. Remaining failures are the M3.2b R6 dynamic dataclass loader test, the Near DA disabled sentinel test, and three R11 provenance tests.
- The separately invoked archived F05 design file: 10 passed in 0.25s.
- Fresh collection remains 1,575 root IDs plus 10 separate F05 IDs = 1,585 total. Across both executions: 1,580 passed, 5 failed; nested subtests are not extra node IDs.
- `git diff --check` passed.

A prior post-fix full run omitted the pinned Python directory from `PATH`; its history-rewrite test failed because its subprocess could not find Python. That attempt is recorded as an environment-mismatch diagnostic, not the final gate result. The corrected run above includes the workflow's Python-path setup.

## Independent review and scope

Independent source/test review PASS. The reviewer confirmed the decoder retains map pairs, duplicate policy entries are rejected before simulator execution, wrong-policy/witness cases remain rejected, and the test verifies an unbound transaction makes zero simulator calls. The reviewer did not rerun tests. Review: `REVIEW.md`.

The only files changed by this slice are `scripts/remediation/f05_2a_tx_sim_evidence_contract.py` and `scripts/remediation/test_f05_2a_tx_sim_evidence_contract.py`, both already untracked in the dirty checkout before this slice. Their SHA-256 values are recorded in `RUN.json`. The F05 validator inputs, checked-in applied script, witness, and evidence registry were not changed. INV-1 through INV-10 and mock/live runtime policy are unaffected.

F05 remains 45/55 negative cases and 18/21 mutations; this is no new case or mutation credit. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Next single slice

Reproduce and diagnose the M3.2b R6 dynamic dataclass-loader failure from the current full root Python run. Keep the change confined to its test loader unless source behavior proves defective, and retain the other four current Python failures as separate blockers.
