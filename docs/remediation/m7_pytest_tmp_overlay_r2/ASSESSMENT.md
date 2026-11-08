# M7 current Python workflow split after F04 expectation correction

Date: 2026-10-04
Status: local Python workflow gate PASS

## Execution

The current workflow split was rerun after the focused F04 assertion correction using Python 3.12.14, pytest 9.1.1, and the workflow-pinned Envoy 1.39.1 binary at SHA-256 `002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8`. The operator-recorded outer command is in `RUN.json`; it used network-isolated bubblewrap, a read-only host-root bind, a disposable writable overlay over the canonical checkout, a dedicated evidence bind, and temporary `/tmp`. Each child test process used nested bubblewrap with the evidence bind read-only. The exact child commands are recorded in both JSON files.

The test selectors match `.github/workflows/security-gates.yml` lines 496-499: root suite excluding the separate design file, followed by the design file. Reporter options differed from CI (`-q --tb=no` and temporary JUnit XML instead of `-v --tb=short`) so the capture could retain sanitized counters and test identifiers while deleting raw reports and output.

## Results

- Root suite: exit 0, 1,693/1,693 passed, no failures or errors.
- Separate design suite: exit 0, 10/10 passed, no failures or errors.
- `gate_pass`: true; child exit semantics match the test outcomes.
- Python inventory: 384 files, SHA-256 `03df53edb30eecbe904a23b072ac46ca33044fd9d60462f1cc8aa7ba53d1fa4b`, unchanged before/after.
- Workflow SHA-256: `baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c`, unchanged.
- Git HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`; filtered status digest `8084db4edd5d3bc3193de3f07d7028aed1c4fe64f88e5db08e0f8b83758c67ca`, unchanged.
- The former F04 stale assertion is absent after its separately reviewed test-only correction.

## Review and scope

Independent post-run review: PASS. The reviewer checked script/result hashes, tool identities, workflow selectors, counters, exits, source/workflow/Git fingerprints, and sandbox configuration. Limitations: raw JUnit/stdout/stderr were discarded, so original reports could not be independently reparsed; the outer command is wrapper-recorded metadata rather than independent process telemetry. See `REVIEW.md`.

This is local current-source Python workflow evidence only. It does not establish hosted CI, Aiken/Solidity/frontend/security scan gates, F05 ledger admission, chain rehearsal, live-network behavior, or testnet readiness. F05 remains 45/55 negative cases and 18/21 mutations in the accepted ledger; synthetic simulator evidence does not change those counts. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
