# Gitleaks Historical Finding Adjudication

**Local scan date:** 2026-07-15

**Latest protected CI scan:** run `29416245559`, 2026-07-15

**Tool:** Gitleaks v8.30.1

## Gate Result

The history scan is **blocking**. No baseline or allowlist has been accepted.
The earlier local complete-history inventory reported 1,740 matches across 15
finding-bearing commits: 1,737 generic API-key matches and three private-key
matches. The underlying sanitized local report is not in the repository, so
those counts cannot yet be independently reconciled path by path.

Protected CI run `29416245559` scanned the PR merge SHA
`e2526ffb0e42540d13a82b75d06f60b293159622` with:

```text
gitleaks git . --redact=100 --report-format json \
  --report-path raw-gate/gitleaks-report.json --log-opts=--all --exit-code 1
```

It reported 869 fully redacted matches across 27 paths and nine
finding-bearing commits: 867 `generic-api-key` and two `private-key` findings.
The raw gate bound the report to SHA-256
`9aad228b9ae34c08e48fc14f5bc859f3785f493e7d1781813781f4672334417e`.
No matched value is reproduced here.

## Exact Protected-CI Path Classification

These counts are derived from the sanitized run `29416245559` artifact and
sum exactly to 869.

| Group | Sanitized paths | Matches | Status |
| --- | --- | ---: | --- |
| Deleted Foundry output | `contracts/test_output_cmd.json`, `contracts/clean_output.json` | 802 | Generated output; remove from rewritten history rather than baseline globally. |
| Upstream Foundry fixtures | Eleven paths under `.foundry/` | 46 | Requires independent path-and-rule sampling before a narrow allowlist is considered. |
| Current Neuron source/configuration | `neuron/secp256k1.py`, `neuron/config.py`, `neuron/eth_client/sequence_wallet.py` | 6 | Requires independent review; no allowlist accepted. |
| Legacy provider helpers | `simulate-request.mjs`, `simulate-request-v2.mjs`, `simulate-request-v3.mjs`, `register-agent.mjs`, `verify-escrow.mjs` | 9 | Blocking; correlated with Infura/Polygon TruffleHog detections and targeted for removal. |
| Historical deployment helpers | `EmergencyLockdown.s.sol`, `DeployX402.s.sol`, `RegisterAgent.s.sol` | 3 | Requires independent review of environment-variable references. |
| Historical Telegram bot | `telegram-bot/bot.js` | 1 | Requires owner review and provider-side token status evidence before disposition. |
| PEM identity paths | `node_identity.pem`, `neuron/node_identity.pem` | 2 | Confirmed private-key paths; never allowlist. Rotation, impact review, and history removal are mandatory. |

The difference between the earlier 1,740 local findings and the 869 CI
findings likely reflects different reachable-ref sets, but that is an
inference—not an adjudication. Preserve both inventories and reconcile them
after the coordinated all-ref rewrite.

## TruffleHog Correlation

Run `29413794423` recorded one verified Infura finding and 19 unverified
findings. The verified item was at historical path `simulate-request-v3.mjs`,
line 6, commit `1321f91586784d218ebc11126de588fbcf649ec6`.

The later protected run `29416245559` recorded the same 20 sanitized detector
events as unverified: zero verified and 20 unverified. This is consistent with
the provider credential no longer verifying, but it does **not** prove the
revocation time, affected project, replacement, access/billing impact, or
reviewer acceptance. Those facts require separate sanitized provider evidence.
See [TRUFFLEHOG_TRIAGE.md](TRUFFLEHOG_TRIAGE.md).

## Required Closure

1. Revoke or rotate every provider credential found in the five legacy helper
   paths. Retain only a non-sensitive provider/project fingerprint, UTC
   revocation time, access and billing review interval, impact disposition, and
   reviewer identity.
2. Record all three historical PEM finding occurrences, then derive the two
   unique public-key fingerprints from public representations—not from raw
   private PEM bytes. Rotate/decommission both keys and record replacement
   public fingerprints.
3. Prove each unique PEM identity controls no deployment signer, funded account,
   node, provider, Safe, timelock, or validator role. Record Polygon Amoy and
   Cardano Pre-Prod account-derived checks or cryptographic non-applicability.
4. Use the disposable-mirror procedure in
   [CREDENTIAL_INCIDENT_RUNBOOK.md](CREDENTIAL_INCIDENT_RUNBOOK.md). Do not run
   a rewrite in a working clone and do not push without explicit approval.
5. Reconcile open generic findings. Independently review vendor/current-source
   candidates before any exact path-and-rule allowlist. Never allowlist the PEM
   or legacy provider-helper findings.
6. Coordinate every ref, fork, open PR, cached GitHub view, and collaborator
   clone. Collaborators must discard old clones and reclone.
7. Rerun complete-history Gitleaks and all-category TruffleHog. Both final
   schema-bound reports must contain zero findings.
8. Only then create `credential-incident-report.json` in the protected
   operational evidence bundle. Every referenced artifact must exist, be
   non-empty, and match its declared SHA-256.

No credential-incident closure report is committed in the repository. Missing
external evidence remains missing, and readiness remains **NO-GO**.
