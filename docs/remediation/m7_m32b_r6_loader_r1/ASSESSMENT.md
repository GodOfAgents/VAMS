# M3.2b R6 dynamic test-loader correction assessment - 2026-10-03

## Decision

Accept the one-line test-loader correction. Python 3.12 dataclasses require a dynamically executed module to be present in `sys.modules` while its classes are defined. The R6 test now registers the module before `exec_module`. The R6 binding guard, mutation, subprocess arguments, and test assertions are unchanged.

## Verification

Pinned Python 3.12.14 and pytest 9.1.1:

- Focused R6 file: `pytest -v --tb=short docs/remediation/m3_2b_r6/test_binding_guard.py` with the pinned Python directory on PATH; exit 0, 2 passed in 23.72s.
- Full root CI-split invocation with pinned Python and checksum-verified Envoy: exit 1, 1,571 passed, 4 failed, 441 nested subtests passed in 200.47s. The corrected R6 test passes in the full run. Remaining failures are one Near DA sentinel test and three R11 provenance tests.
- The separate F05 design file remains at its last verified result: 10 passed under the same pinned Python/Envoy configuration. Together with the 1,575 root items, the current observed partition is 1,585 node IDs: 1,581 pass and 4 fail. Nested subtests are not additional node IDs.
- `git diff --check` passed. Worktree dirty-entry count remains 127.

## Independent review

Independent review PASS: the module registration is placed between `module_from_spec` and `exec_module`, where dataclasses need it. The reviewer confirmed the R6 guard logic and test meaning are unchanged. Review limitation: the target file is pre-existing untracked work, so Git could not provide a tracked baseline diff; the pre-edit and post-edit file hashes are in `RUN.json`. The reviewer did not rerun tests; the 2-pass result is the writer's captured execution.

## Scope and readiness

Only `docs/remediation/m3_2b_r6/test_binding_guard.py` changed; it was already untracked before this slice. This is test-loader plumbing only. No validator, protocol guard, evidence status, invariant control, credential, or deployment behavior changed.

F05 remains 45/55 negative cases and 18/21 mutations with no new credit. The Python root gate remains FAIL and readiness remains NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Next single slice

Diagnose `neuron/tests/test_sentinel.py::TestSentinelNode::test_audit_node_success`, whose current failure reports that the Near DA protocol is disabled. Establish whether the test needs an explicitly local-only fixture or whether a product path is defective; do not enable live/mock promotion to make the test pass.
