# INV-3 / INV-4 session-key focused validation

Date: 2026-10-04
Status: focused local suite PASS; scope limited to SDK unit behavior

## Change

Only `neuron/tests/test_sequence_wallet.py` changed. It now bounds the remaining lifetime for a newly created 24-hour session, verifies an already-expired session is denied, and verifies creation fails when `core_contracts` is unconfigured. Existing 25-hour and non-core-request rejection tests remain. `neuron/sdk/sequence_wallet.py` was not modified.

## Verification

The pinned, network-isolated focused command in `RUN.json` passed 9/9. The test file AST parse passed. `git diff --check` exited 0, but the test file is untracked and therefore not covered by that Git check; this slice did not reformat unrelated existing whitespace. Source hashes and exact command are recorded in `RUN.json`.

## Invariant scope

- INV-3: local SDK tests cover the 24-hour cap, over-cap rejection, and rejection of an already-expired session.
- INV-4: local SDK tests cover empty/unconfigured and non-core allowlist rejection.
- INV-1, INV-2, INV-5 through INV-10: not touched.

Residual limits: expiry exactly at `now == expires_at` was not tested; the current comparison is `now > expires_at`, so equality is accepted for that instant. Test addresses are synthetic, so this does not establish which real VAMS contracts the deployment configuration trusts. No live-chain/session-key behavior was tested. Independent review details are in `REVIEW.md`.

This is not full Python gate or deployment acceptance. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
