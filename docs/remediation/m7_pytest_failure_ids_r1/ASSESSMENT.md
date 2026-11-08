# Sanitized current pytest failure identities

Date: 2026-10-04

## Diagnostic result

A fresh offline rerun reproduced the accepted capture's failure counts: root suite 10 failing cases and separate design suite 1 failing case. The accepted capture had 1,683 root passes and 444 subtests passed, plus 9 design passes. The JUnit failure/error counters matched the retained case rows; both suites exited 1. The test run used pinned Python 3.12.14, pytest 9.1.1, Envoy 1.39.1, VAMS_ENV=test, and the workflow split. Source inventory, workflow hash, and Git state remained stable.

The normalized failing identities are:

- docs/remediation/m3_f04_impl_r2/test_interface_migration.py::F04InterfaceMigrationTests::test_blueprint_uses_migrated_public_schemas
- neuron/tests/test_cognitive_kernel.py::TestHormaFileSystem::test_store_and_fetch_l3_fs
- neuron/tests/test_cognitive_kernel.py::TestHormaFileSystem::test_invalidate_deletes_file
- neuron/tests/test_cognitive_kernel.py::TestHipifFolding::test_fold_completed_subtask
- neuron/tests/test_cognitive_kernel.py::TestProPlayWorldModel::test_proplay_guidance
- neuron/tests/test_cognitive_kernel.py::TestEvoMemAndVm::test_evomem_patch_tracking
- neuron/tests/test_comms.py::TestAgentComms::test_message_signing_verification
- neuron/tests/test_comms.py::TestAgentComms::test_tampered_message
- neuron/tests/test_x402_recovery.py::TestX402EscrowLifecycleIntegration::test_full_lifecycle_with_proplay_guidance
- scripts/audit/test_history_rewrite_script.py::HistoryRewriteScriptTests::test_rejects_evidence_inside_source_checkout
- docs/remediation/m3_f05_design_r2/test_design.py::F05DesignTests::test_duplicate_json_keys_rejected

No parameter values, traceback, assertion messages, raw JUnit XML, or raw pytest output are retained. The package keeps only normalized module/class/function identifiers, outcome, exception type when safe, parameter-fragment hashes, counters, and output hashes.

## Read-only source triage

Independent read-only inspection indicates that nine root failures and the one design failure require writes under the checkout: cognitive/ProPlay tests use the .data tree, communications tests append to audit.log, the history-path test creates a temporary directory inside the repository, and the duplicate-key test writes its fixture beside the test. The capture mounted the checkout read-only, so these are likely sandbox artifacts and must be rechecked with an ephemeral writable overlay.

The F04 interface test has a separate stale source assertion: accepted Aiken warning cleanup added an explicit unused-parameter binding before the False branch, while the test still expects the prior body spelling. This is a test expectation only; no validator behavior change is indicated. A focused correction is a possible later slice after the workflow-equivalent rerun confirms it is the remaining failure.

## Limits and next slice

The diagnostic identifies failing test functions, not all root causes. JUnit XML and raw output were temporary and deleted. Independent review verifies wrapper guards and internal counters but cannot reparse the deleted JUnit. This is local diagnostic evidence only; no hosted CI, ledger, testnet, or deployment readiness credit.

Next single slice: rerun the workflow pytest split with a disposable bwrap tmp-overlay on the canonical checkout. This allows tests to write while all changes are discarded at sandbox teardown and preserves the original dirty checkout.
