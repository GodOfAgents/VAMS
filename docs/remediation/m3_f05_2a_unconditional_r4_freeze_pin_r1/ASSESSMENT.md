# Pin accepted R4 freeze identity in the supplemental F05 mutation probe

Date: 2026-10-03
Status: PASS for the bounded provenance and synthetic simulator scope after independent review.

## Change

Added a hard preflight check for the accepted R4 coordinator freeze SHA-256, `df7d882ad8aa26b59692c65457bf888204cfbfdc3586ce2619a99f1749115c6b`, before the probe reads the family manifest or executes Aiken. This addresses the non-blocking provenance note from the independent review of the preceding exact-context slice. The prior accepted evidence package remains preserved in its separate directory.

## Verification

The pinned, network-isolated command in `RUN.json` exited 0. It reproduced the same three supplemental outcomes: exact base `seed_missing` rejection, mutant positive acceptance, and mutant paired-negative acceptance. All calls invoked Mint[0], matched the expected policy and script hash, and cleaned up. The probe source parsed, the freeze-hash guard and whitespace checks passed, the captured JSON parsed, and `git diff --check` passed.

The run is supplemental synthetic simulator evidence only. It grants no registered mutation credit. F05 remains 45/55 negative cases and 18/21 mutations. No contract source, public harness, validator, invariant, credential, ledger or network state changed. Testnet readiness remains NOT READY, and deployment and privileged activation remain disabled.

Independent review passed; see `REVIEW.md`.
