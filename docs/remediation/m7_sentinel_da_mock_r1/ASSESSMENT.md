# Sentinel test-local DA publisher boundary correction - 2026-10-03

## Decision

Accept the sentinel test correction. The test patched the retired `sentinel.da_publisher.DAPublisher.publish_report`, while production Sentinel calls the current `PerformanceAuditLog.publish_sentinel_report`. Under the workflow's `VAMS_ENV=test`, the unpatched latency route correctly refuses Near DA because Near is not live-capable. The test now stubs the current async publication boundary locally, supplies the response fields consumed by Sentinel, and asserts the call uses `DAProtocol.NEAR_DA`.

No production DA configuration, adapter, environment variable, runtime mock mode, or live protocol eligibility changed. The patch does not enable Near DA outside this test.

## Verification

Pinned Python 3.12.14 / pytest 9.1.1; `VAMS_ENV=test`; existing checksum-verified Envoy 1.39.1:

- Final formatted sentinel test module: 12 passed in 3.85s.
- Exact workflow root split invocation: 1,572 passed, 3 failed, 441 nested subtests passed in 210.25s; exit 1. The root contains 1,575 pytest items. The sentinel failure is resolved. The three remaining failures are the R11 provenance tests listed in `RUN.json`.
- Separate archived F05 design invocation under the same workflow environment: 10 passed in 0.29s.
- Combined split: 1,585 unique node IDs, 1,582 passed and 3 failed; 441 nested subtests are additional observations, not node IDs.
- `git diff --check` passed.

The full root run occurred after the sentinel behavior change and before a formatting-only wrap of its mock response. The final formatted module was rerun afterward and passed 12/12. The exact workflow environment matters: an earlier diagnostic run omitted `VAMS_ENV=test` and failed at runtime-policy initialization. Earlier root totals that omitted the workflow variable are diagnostic only and are superseded by this run.

## Independent review

Independent review PASS. The reviewer confirmed the test patches the exact async method Sentinel awaits, asserts exactly one call routed to Near DA, and does not change DA enablement or mock/live policy. Reviewer did not rerun tests; execution results above are from the writer. Review: `REVIEW.md`.

Only `neuron/tests/test_sentinel.py` changed. No API, production behavior, invariant enforcement, or F05 case/mutation status changed. F05 remains 45/55 negative cases and 18/21 mutations with no new credit.

## Current blockers and next slice

The exact Python root gate remains FAIL on three R11 provenance tests. Testnet readiness remains NOT READY: required evidence, security/governance, Cardano Pre-Prod, Polygon Amoy, provenance/reproducibility, and T06 hosted-history/provider gates remain unresolved. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice: reproduce and diagnose `R11BoundaryTests.test_authoritative_mutation_detected` only. Keep its remediation separate from the two other failing R11 tests until the source of each is understood.
