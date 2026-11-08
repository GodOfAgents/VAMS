# M7 pytest collection split assessment - 2026-10-03

## Decision

Accept the collection repair as a complete, disjoint split of the collected pytest node IDs. The Python test gate remains FAIL because the root invocation executed six failing test items. This record gives no readiness, case, or mutation credit.

## Change

The pytest step in `.github/workflows/security-gates.yml` now runs the root suite with the exact archived F05 design file excluded, then runs that exact file separately. Both invocations use the same Envoy environment variable and the default pytest import mode. No global pytest configuration or import-mode change was added, and no frozen evidence package was modified.

## Verification

Pinned environment: Python 3.12.14, pytest 9.1.1.

Fresh collection in the canonical checkout:

- `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pytest --collect-only -q --ignore=docs/remediation/m3_f05_design_r2/test_design.py` exited 0: 1,575 collected in 6.49s.
- `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pytest --collect-only -q docs/remediation/m3_f05_design_r2/test_design.py` exited 0: 10 collected in 0.10s.
- The separately executed exact F05 file exited 0: 10 passed in 0.26s.

The prior full root execution, using the same pinned interpreter and default import mode, exited 1 after 204.88s: 1,569 passed and 6 failed among 1,575 collected items. Pytest also reported 441 passing subtests; these are nested subtests and do not add collected node IDs. Across both executions the partition is 1,585 collected node IDs, 1,579 passing and 6 failing. The root gate is therefore still FAIL.

The six root failures were:

1. `docs/remediation/m3_2b_r6/test_binding_guard.py::BindingGuardTests::test_guard_removal_mutation_fails_closed`: its dynamically loaded dataclass module was absent from `sys.modules`.
2. `neuron/tests/test_sentinel.py::TestSentinelNode::test_audit_node_success`: Near DA protocol disabled.
3. `scripts/remediation/test_f05_2a_tx_sim_evidence_contract.py::test_binding_runner_rejects_wrong_policy_and_unbound_false_positive`: CBOR helper rejected an unsupported fixture value.
4. `scripts/remediation/test_m3_1b_r9_provenance.py::test_authoritative_mutation_detected`: authoritative project hash mismatch.
5. `scripts/remediation/test_m3_1b_r9_provenance.py::test_cleanup_after_injected_failure_and_network_boundary`: stale expected source contract.
6. `scripts/remediation/test_m3_1b_r9_provenance.py::test_f04_forward_manifest_rebinds_current_lock_without_false_continuity`: `StopIteration`.

`git diff --check` passed. Current Git state remains 127 dirty entries. No Solidity, Cardano, runtime, frontend, credential, deployment, vendor, or evidence fixture changes are part of this slice.

## Independent review

Independent review PASS for the workflow hunk, arithmetic, and partition structure. The reviewer confirmed the root command excludes only the exact F05 file and the second command invokes that file, so the two invocations cover all 1,585 node IDs without overlap or omission. The reviewer did not rerun the tests. Review record: `REVIEW.md`.

## Readiness and next slice

Readiness remains NOT READY. F05 remains 45/55 negative cases and 18/21 mutations. The F05 A/B/C applied-parameter choice, signature-domain choices, F04 normative path choice, T06 provider/history evidence, six Python failures, and other deployment gates remain open. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice: diagnose and remediate the F05 CBOR simulator helper failure listed above, without changing policy semantics or granting case credit until targeted acceptance and independent review pass.
