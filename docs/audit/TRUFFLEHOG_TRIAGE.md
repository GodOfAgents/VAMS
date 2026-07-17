# TruffleHog Sanitized Finding Triage

**Latest protected run:** `29416245559`

**PR merge SHA:** `e2526ffb0e42540d13a82b75d06f60b293159622`

**Scanner:** TruffleHog 3.95.9

**Command:** `trufflehog git "file://$PWD" --json --fail --no-update --results=verified,unknown,unverified`

## Gate Result

The gate is **blocking**. The sanitized artifact contains 20 findings: zero
verified and 20 unverified. An earlier protected run, `29413794423`, recorded
one of the Infura events as verified. The later verification result is not a
substitute for provider revocation, replacement, or impact evidence.

The latest sanitized artifact is bound to SHA-256
`1d667e251af6f60a1b71c57b9d06343ea0ce75b041c7f2078947b12e2f51cce9`.
It contains detector, verification status, commit, path, and line only. No raw
candidate value is retained here.

## Exact Sanitized Findings

| # | Detector | Status | Historical path | Line | Commit | Disposition |
| ---: | --- | --- | --- | ---: | --- | --- |
| 1 | URI | Unverified | `neuron/tests/test_gateway_client_security.py` | 32 | `31929a24419a9b7b9d8954cbea2df9fe1cb77a68` | Open: review test fixture. |
| 2 | Postgres | Unverified | `neuron/tests/test_vdso_postgres.py` | 197 | `babe45e22430b754eadbb98d2269afb3430c4ca6` | Open: review test DSN fixture. |
| 3 | Postgres | Unverified | `neuron/tests/test_vdso_postgres.py` | 201 | `babe45e22430b754eadbb98d2269afb3430c4ca6` | Open: review test DSN fixture. |
| 4 | Postgres | Unverified | `neuron/.env.example` | 23 | `0161faebfba436fd3140d94dd0b9dbc91744f1bb` | Open: review example-only DSN. |
| 5 | Postgres | Unverified | `neuron/docs/WORKFLOW_ENGINE.md` | 43 | `0161faebfba436fd3140d94dd0b9dbc91744f1bb` | Open: review documentation fixture. |
| 6 | Postgres | Unverified | `neuron/dbos_config.py` | 34 | `0161faebfba436fd3140d94dd0b9dbc91744f1bb` | Open: review configuration fallback. |
| 7 | Infura | Unverified | `simulate-request-v2.mjs` | 6 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: provider evidence and history removal required. |
| 8 | Infura | Unverified | `simulate-request-v3.mjs` | 6 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: verified in earlier run; provider evidence and removal required. |
| 9 | Infura | Unverified | `simulate-request.mjs` | 6 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: provider evidence and history removal required. |
| 10 | Infura | Unverified | `register-agent.mjs` | 8 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: provider evidence and history removal required. |
| 11 | Infura | Unverified | `verify-escrow.mjs` | 6 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: provider evidence and history removal required. |
| 12 | Polygon | Unverified | `register-agent.mjs` | 8 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: same legacy provider URI; remove from history. |
| 13 | Polygon | Unverified | `simulate-request-v2.mjs` | 6 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: same legacy provider URI; remove from history. |
| 14 | Polygon | Unverified | `simulate-request-v3.mjs` | 6 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: same legacy provider URI; remove from history. |
| 15 | Polygon | Unverified | `simulate-request.mjs` | 6 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: same legacy provider URI; remove from history. |
| 16 | Polygon | Unverified | `verify-escrow.mjs` | 6 | `1321f91586784d218ebc11126de588fbcf649ec6` | Blocking: same legacy provider URI; remove from history. |
| 17 | URI | Unverified | `.foundry/crates/anvil/src/cmd.rs` | 413 | `174dbaa0393897107b9eafd283224d23a47572aa` | Open: independently review upstream fixture. |
| 18 | URI | Unverified | `.foundry/crates/anvil/src/cmd.rs` | 746 | `174dbaa0393897107b9eafd283224d23a47572aa` | Open: independently review upstream fixture. |
| 19 | Circle | Unverified | `.foundry/crates/forge/tests/fixtures/backtraces/ForkBacktrace.t.sol` | 11 | `174dbaa0393897107b9eafd283224d23a47572aa` | Open: independently review upstream fixture. |
| 20 | Etherscan | Unverified | `.foundry/crates/test-utils/src/rpc.rs` | 87 | `174dbaa0393897107b9eafd283224d23a47572aa` | Open: independently review upstream fixture. |

## Triage Rules

- `verified`, `unknown`, and `unverified` results all block release evidence.
- No finding may be closed from detector shape or path name alone.
- Legacy provider helpers are removed from history after credential rotation.
- Test, documentation, configuration, and upstream candidates require sampled
  human review before any exact path-and-detector allowlist is proposed.
- Raw candidate values, tokens, DSNs, and private material must never be copied
  into Git, chat, tickets, or committed evidence.
- The incident remains open until the protected post-rewrite scan emits zero
  findings and the content-hashed provider/identity evidence is accepted.

## Required Reviewer Output

For each non-provider candidate, the reviewer must record the detector, path,
commit, line, classification, rationale, reviewer, UTC timestamp, and a hash of
the sanitized source observation. Provider and PEM findings additionally
require revocation/replacement and role-impact evidence.
