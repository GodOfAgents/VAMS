# Root pytest collection remediation

## Change and verified result

Root pytest uses importlib mode so same-named historical evidence modules load with unique names. Three exact sibling import paths cover the observed local imports: the F05 design validator, F04 fixture helper, and scripts/audit helper modules. Only `pytest.ini` was changed as implementation; frozen evidence modules and the pre-existing `conftest.py` were not edited.

The source-bound runner executed collection and the full suite on the current dirty checkout. Collection exited 0 with 1,596 tests. Full pytest exited 0 with 1,596 passed and 441 subtests passed in 241.55 seconds. A hash over all Python files plus pytest.ini/conftest.py was identical before and after execution. Exact command, output digests, pins, and source-tree digest are in RUN.json and RESULT.json.

Earlier counts (1,585 through 1,595) were invalidated by concurrent edits in the dirty working tree; the earlier no-PATH failure is retained as historical context and is superseded by this stable source-bound run.

## Scope limits

This establishes root pytest collection and Python test execution only. It does not add F05 negative or mutation credit, and establishes no simulator admission, ledger admission, Cardano Pre-Prod, or live-network evidence. All unrelated working-tree changes were preserved.

Readiness remains NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. Independent review PASS for collection and the bound test evidence.
