# M7 current Python workflow split under disposable overlay

Date: 2026-10-04
Status: executed; Python gate FAIL on one identified assertion

## Scope and execution

The current workflow test split was run offline with pinned Python 3.12.14, pytest 9.1.1, and the locally pinned Envoy 1.39.1 binary (SHA-256 `002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8`). The outer bubblewrap command used a read-only host root, a disposable writable overlay over the canonical checkout, a dedicated persistent evidence bind under outer `/tmp`, and an unshared network namespace. Each pytest child ran in a nested bubblewrap namespace; the checkout resolved to the outer overlay, `/tmp` remained shared for temporary JUnit XML, and the persistent evidence alias was read-only.

The outer command recorded from the operator session was:

```text
bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --dir /tmp/vams-evidence --bind /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_pytest_tmp_overlay_r1 /tmp/vams-evidence --overlay-src /home/GodOfAgents/code/VAMS-testnet --tmp-overlay /home/GodOfAgents/code/VAMS-testnet --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B /tmp/vams-evidence/run_pytest_snapshot.py
```

The capture followed the workflow split: root suite with `--ignore=docs/remediation/m3_f05_design_r2/test_design.py`, then the design suite separately. It used `pytest -q --tb=no -p no:cacheprovider` and temporary JUnit reports to retain normalized test identifiers and counters without retaining raw output. The exact nested child commands and JUnit hashes are in `RESULT.json` and `RUN.json`. The RUN outer argv is wrapper-written metadata, not independent process telemetry.

## Results

- Main suite: 1,693 test cases; 1,692 passed and 1 failed; child exit 1; JUnit declared one failure and zero errors.
- Separate design suite: 10 passed; child exit 0; zero failures/errors.
- The sole failure is `docs.remediation.m3_f04_impl_r2.test_interface_migration.F04InterfaceMigrationTests.test_blueprint_uses_migrated_public_schemas`.
- The previous nine root and one design failures no longer reproduce with the writable disposable overlay. The failure-ID analysis attributed those to tests attempting checkout writes under the earlier read-only mount; that attribution is supported by this run's changed outcomes, but raw tracebacks were not retained.
- Python source inventory: 383 files, digest `1a8ca6aa80e7b5cfcc0e61977cddd4791f9df297a76127bdc2e778a95d64a4c1`, unchanged during execution.
- Workflow SHA-256: `baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c`, unchanged.
- Git HEAD and filtered status digest unchanged: `829ab544571f12efe50ecb5740f129c8acb3e16f` / `ca6a50a0caf0fb18f6fea44fed38017ebe543d13f2698afa9990e3ba17e33d39`.
- Capture/result hashes and exact structured results are bound in `RUN.json` and `RESULT.json`.

Current `agent_nft.ak` binds `_unused_bootstrap_ref = bootstrap_ref` before returning `False`; the test still requires the older contiguous `{ False }` body. Source triage confirms the legacy mint path remains fail-closed. A test-only expectation correction is the next bounded slice; it must not modify validator behavior or decide the separate F04 normative identity-entrypoint question.

## Acceptance and limits

Independent post-run review: PASS with evidence limitations. The reviewer recomputed the result JSON hash, capture-script hash, live source/workflow/Git fingerprints, pinned tool identities, JUnit counters, and exit semantics. Raw JUnit/stdout/stderr were deleted, so the reviewer could not independently reparse the original XML or inspect the assertion traceback. Outer command metadata is wrapper-recorded rather than independent process telemetry. See `REVIEW.md`.

This records local current-source Python test execution only. The Python gate remains FAIL. No F05 case or mutation credit, hosted CI, ledger admission, chain rehearsal, live-network, or deployment evidence is gained. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
