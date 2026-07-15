# Gitleaks Historical Finding Adjudication

**Scan date:** 2026-07-15

**Closure contract added:** 2026-07-15

**Tool:** Gitleaks v8.30.1

**Scope:** Complete-history `git --log-opts=--all`; findings were fully redacted
before classification. Findings occur in 15 commits.

## Gate Result

The history scan is **blocking**. It reported 1,740 matches: 1,737 generic API
key matches and three PEM private-key matches. No baseline or allowlist has been
added because doing so before credential invalidation and owner review would
hide a real historical exposure.

## Redacted Classification

| Class | Matches | Assessment |
| --- | ---: | --- |
| Generic API-key matches | 1,737 | Concentrated in deleted Foundry output JSON, tracked upstream `.foundry/` fixtures, legacy deployment/demo helpers, and current cryptographic fixtures. Every path group still requires sampled independent review before any narrow path/rule adjudication is accepted. |
| Deleted node identity PEM files | 3 | Confirmed private-key material committed in historical paths `node_identity.pem` and `neuron/node_identity.pem`. These identities are presumed compromised. |

This classification records paths, rules, and counts only. It intentionally
does not reproduce matched values.

## Protected CI Corroboration

GitHub Actions run `29413794423` scanned the PR merge result on 2026-07-15.
The complete-history Gitleaks job scanned 62 commits and reported 869 redacted
matches. This count uses the CI ref enumeration and is not treated as a
replacement for the earlier 1,740-match local inventory until an independent
review reconciles the two sanitized reports.

The same run executed TruffleHog 3.95.9 with
`--results=verified,unknown,unverified`. Its sanitized report recorded 20
findings: one verified and 19 unverified. The verified detector was `Infura` at
historical path `simulate-request-v3.mjs`, line 6, commit
`1321f91586784d218ebc11126de588fbcf649ec6`. No credential value is retained in
this document. Because the provider verified the credential during CI, it is
presumed compromised and active until revocation evidence proves otherwise.

## Required Closure

1. Immediately revoke the verified Infura credential through the owning
   provider account, rotate dependent applications through a vault, review
   access/billing logs, and retain only sanitized revocation and impact proof.
2. Identify every role, address, node identity, RPC account, bot, and external
   provider that could have used the historical values.
3. Revoke or rotate all possibly affected credentials and prove that the PEM
   identities control no funded account, Safe, timelock, validator, or testnet
   role.
4. Remove obsolete generated artifacts, private-key files, and the obsolete
   `simulate-request-v3.mjs` path from every
   reachable ref using a coordinated history-rewrite procedure. Retain only
   sanitized ref inventories and incident evidence; use an encrypted disposable
   mirror for the rewrite and notify every collaborator to reclone.
5. Independently review the generated/vendor fixture groups before adding any
   path-and-rule-specific allowlist. Never allowlist the private-key findings.
6. Rerun both the complete-history and exact-worktree Gitleaks scans, followed
   by all-category TruffleHog. The final schema-bound scans must report zero
   findings.

Canary and public readiness additionally require
`credential-incident-report.json` under the operational evidence bundle. The
report is validated by `scripts/audit/credential_incident_evidence.py` against
the exact target commit and requires public, content-hashed rotation,
account-derived balance or cryptographic non-applicability proof, role-impact,
all-ref rewrite, collaborator/fork/cache remediation, scanner, and
named-reviewer artifacts. This adjudication document cannot satisfy that
contract by itself.

History rewriting and credential rotation are repository-owner security
actions. They are intentionally not performed automatically by the deployment
implementation task.
