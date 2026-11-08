# M7 full Python workflow split after INV-3/INV-4 test additions

Date: 2026-10-04
Status: local Python workflow gate PASS

## Execution and results

The current workflow split ran offline with pinned Python 3.12.14, pytest 9.1.1, and Envoy 1.39.1 at the workflow-pinned SHA-256. The outer sandbox used `bwrap --unshare-net`, a read-only host-root bind, a disposable writable overlay over the canonical checkout, temporary `/tmp`, and a dedicated evidence bind. Each test child used a nested bwrap namespace with the evidence alias read-only. `RUN.json` records the operator-invoked outer command and both exact child commands; the outer argv is wrapper-written metadata, not independent process telemetry.

The test selectors match `.github/workflows/security-gates.yml` lines 496-499: the main suite excludes only the separate design test, then the design test runs separately. Capture reporters differ from CI (`-q --tb=no` and temporary JUnit XML instead of `-v --tb=short`); raw JUnit and stdout/stderr were deleted after hashing.

- Main suite: 1,695/1,695 passed, exit 0, zero JUnit failures/errors.
- Design suite: 10/10 passed, exit 0, zero JUnit failures/errors.
- `gate_pass`: true; exit semantics match all recorded outcomes.
- Python inventory: 385 files, SHA-256 `524e46bc05c84f930643bcae0abd236c5cbf239662dd50bd33264a7f2c24d5ce`, unchanged before/after.
- Workflow SHA-256: `baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c`, unchanged.
- Git HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f` and filtered status digest `6eadd0c1cb31a6676abe39066702a6842cde3993d8128df2f55d3aa68ab82890`, unchanged.

## Independent review and limits

Independent post-run review: PASS. It verified capture/result hashes, current workflow selectors, pins, outcomes, fingerprints, and that the updated session-wallet test file is within the main suite and hashed inventory. The capture does not retain passing test IDs, so the reviewer could not independently identify each newly added case in the JUnit after the run; the separate focused session-wallet run passed 9/9. Raw output deletion and wrapper-written outer command metadata remain evidence limitations.

This establishes only a local Python test gate. It does not establish hosted CI, Solidity/Aiken/frontend/security scanner gates, F05 ledger admission, chain rehearsal, live-network behavior, or deployment readiness. F05 accepted ledger remains 45/55 negative cases and 18/21 mutations. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
