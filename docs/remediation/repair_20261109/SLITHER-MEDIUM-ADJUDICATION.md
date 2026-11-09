# Slither medium findings: full adjudication (2026-11-09)

Status: **62 of 62 medium findings reviewed against source. 0 defects
found.** Author review only; non-author review pending. Readiness is
unchanged: 13 findings open, 0 of 36 tracks verified, NOT READY.

## Run

- Slither 0.11.5, the CI flags `--exclude-dependencies
  --exclude-informational --exclude-low`.
- Tree: commit `c0d422c` contracts, copied to `~/vams-wt-slither`. Run from
  the canonical path, Slither silently reports 0 results.
- Result: 0 High, 62 Medium, 16 Optimization.
- Report SHA-256
  `c78da6b7e2e9d213c29a4d0bb5a41db895303caf524da76d138f4b10587ae7b2`. The raw
  report is retained on the runner only: it is 1.4 MB and contains local
  paths. CI produces its own `slither-report.json`.

The ledger CI uploads with the report, `contracts/slither-adjudications.yml`,
previously covered 18 mediums from an older scope. It now lists every one of
the 62 at its current file and line, with a status and reason.

## Groups

| Detector | Count | Disposition | Key check |
|---|---|---|---|
| unused-return | 21 | false positive | `EffectReceiptV3.verify` returns `(ok, digest)` and does not revert, so every caller was traced. The three "ignored" calls in `ObjectEffectV3` return the result to callers that check `ok`. `verifyObjectAbsenceV3` returns `absence()`'s result. A discarded `issuer()` flag yields issuer `bytes32(0)`, which `_validExpected` rejects. |
| uninitialized-local | 20 | intended default | Decoder structs returned empty on failure; counters starting at 0; try/catch results assigned before use, with zero rejected |
| incorrect-equality | 15 | expected guard | The same 15 zero, empty and enum guards as the earlier review, at shifted lines |
| reentrancy-no-eth | 5 | protected | `nonReentrant` on all four economic entry points, and an explicit relay guard on `HeartbeatAtomicConsentRegistryV2`. The refund loop marks each row before its external call |
| divide-before-multiply | 1 | exact arithmetic | INV-2 cap: `q*3000 + floor(r*3000/10000)` equals `floor(B*3000/10000)` exactly for `B = q*10000 + r` |

## Optimizations (16, not applied)

All are gas-only:

- `VAMSToken` is upgradeable.
- The `VAMSStaking` suggestion comes from `VAMSRestrictedStaking`. It deploys
  with reward rate 0 and budget 0 and overrides both setters to accept only
  zero, so restricted-testnet rewards cannot be activated (consistent with
  INV-9).
- The Heartbeat and Timelock V3 values are constructor-bound configuration
  and code-hash pins. Changing them alters runtime bytecode, so that belongs
  in a separate reviewed change.

## Not covered

- Informational and low findings, which CI excludes.
- Formal verification and fuzzing beyond the existing Foundry suite.
- Independent audit (D7).
