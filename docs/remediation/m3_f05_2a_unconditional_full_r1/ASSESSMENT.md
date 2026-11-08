# F05.2a full-harness execution diagnosis

Date: 2026-10-03
Disposition: **diagnostic only; no case or mutation credit**

## Finding

The current public F05.2a harness exits 1 at its canonical positive bootstrap fixture control. It raises `AssertionError: canonical F05.2a bootstrap fixture rejected by compiled Plutus V3` at line 895, before the negative-case and mutation loops. No `RESULT.json` was produced. The earlier shell wrapper left a one-byte, empty `RUN.exit`; the direct rerun recorded in `RUN.json` is the authoritative exit capture.

The command used pinned Python 3.12.14 and Aiken 1.1.21+42babe5, with network access isolated and the source tree read-only. Exact command, tool versions, exit code, traceback digest, and runner/contract digests are recorded in `RUN.json`.

## Acceptance interpretation

This run proves only that this local full-harness path cannot execute its required positive control in the available evaluator environment. It does not show that the validator is defective or correct, and it does not test a negative case or mutation. The frozen mutation contract still requires the baseline positive control and every negative case for `unconditional_success`; the separate R4 supplemental probe covers only the `seed_missing` paired case and remains non-credit supplemental synthetic simulator evidence.

F05 remains **45/55 negative cases** and **18/21 mutations**. Ledger admission, rehearsal, and live-network evidence remain absent. Readiness remains **NOT READY**; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Independent review scope

Independent review is requested for the diagnosis classification and exact evidence record. No validator, contract, harness, fixture, credential, ledger, or network state was changed.
