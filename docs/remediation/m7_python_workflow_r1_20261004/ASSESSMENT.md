# M7 current Python workflow gate — 2026-10-04

The exact current Python workflow ran once against a fresh writable snapshot after the accepted R11 Cardano source/blueprint refresh. The snapshot was isolated with bwrap --unshare-net and the canonical source mount was read-only. Canonical HEAD was 829ab544571f12efe50ecb5740f129c8acb3e16f on testnet/remediation-20260907. The 6,849-row source inventory and Git status were unchanged. Snapshot changes were limited to audit.log and two pytest cache files.

The root Python command failed: 1,696 passed, 444 subtests passed, and four failed. Three failures assert superseded F04 registry-mint behavior and require the policy-anchor authority choice plus a versioned reviewed design. The fourth was a runner PATH issue; the exact history-rewrite test passed in a separate pinned-toolchain isolated rerun after setting PATH and PYTHON_BIN. This targeted pass does not change the root workflow result. The separate F05 design command passed 10 tests.

Exact root command: VAMS_ENVOY_BIN=/home/GodOfAgents/vams-evidence/toolchains/envoy-1.39.1/envoy /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pytest -v --tb=short --ignore=docs/remediation/m3_f05_design_r2/test_design.py. Exit 1; output SHA-256 3d477cb1cb84e69a83cac9091f9d9a2e215c546333cda57617714f5292d3a0c7.

Exact F05 design command: VAMS_ENVOY_BIN=/home/GodOfAgents/vams-evidence/toolchains/envoy-1.39.1/envoy /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pytest -v --tb=short docs/remediation/m3_f05_design_r2/test_design.py. Exit 0; 10 passed; output SHA-256 1278ea5ed3c8177623a90ea62140dbbe5e76b0aab2af4e35de005a0d3178f04d.

Exact targeted command: PATH=/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin PYTHON_BIN=/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pytest -v --tb=short scripts/audit/test_history_rewrite_script.py::HistoryRewriteScriptTests::test_execute_rejects_empty_replacement_values. Exit 0; one passed in 0.32 seconds.

Unresolved failures:
- docs/remediation/m3_f04_impl_r2/test_interface_migration.py::F04InterfaceMigrationTests::test_blueprint_uses_migrated_public_schemas
- docs/remediation/m3_f04_impl_r4/test_supplemental_entrypoints.py::SupplementalMatrixTests::test_each_new_case_has_an_explicit_contract_guard
- docs/remediation/m3_f04_impl_r4/test_supplemental_entrypoints.py::SupplementalMatrixTests::test_every_supplemental_case_against_applied_public_entrypoint

Do not restore registry-side minting or guess a policy ID to satisfy these tests. The current authority gate is docs/remediation/m7_f04_policy_anchor_gate_r1_20261004/ANCHOR-DECISION.md.

Workflow/Python/pytest/Envoy/bwrap hashes, timestamps, raw captures, and detailed command arguments are recorded in RUN.json and the raw manifests. Workflow SHA-256 baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c; Python SHA-256 aa01d96348989f33ed998b42c83e98593b41dba83914d9899730b90c36f2e5c9; pytest SHA-256 f3da0bf69becc0870ff998a0ad8c509522d4855c9a1d0290e3e2ddbf130ec7a5; Envoy SHA-256 002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8; bwrap SHA-256 0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0. Independent review is in REVIEW.md.

This is local test evidence, not hosted CI, ledger, chain, or live-network evidence. No source, tests, dependencies, credentials, toolchain, or Git refs changed. F05 remains 45/55 accepted negative classifications and 18/21 mutations. T06/history, M0.4/Gitleaks disposition, security/dependency/reproducibility/invariant gates, and both chain prerequisites remain open. Readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Independent review verified 7,560 of 7,561 raw workflow manifest entries. The sole mismatch is the expected pytest write to snapshot/.pytest_cache/v/cache/lastfailed: manifest digest cee5869b7ed2ce4808a2879af55e210889c0e237d4e07bfafe43b76edd195f85, post-run digest a19280ce6454e4a64be7708506e3e3716622e375ed433f6989131401db6277dc. The captured source-inventory delta records this cache change. All PATH-recheck manifest entries verify. Review: REVIEW.md.
