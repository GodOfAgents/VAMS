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

## Required Closure

1. Identify every role, address, node identity, RPC account, bot, and external
   provider that could have used the historical values.
2. Revoke or rotate all possibly affected credentials and prove that the PEM
   identities control no funded account, Safe, timelock, validator, or testnet
   role.
3. Remove obsolete generated artifacts and private-key files from every
   reachable ref using a coordinated history-rewrite procedure. Archive the
   pre-rewrite evidence privately and notify every collaborator to reclone.
4. Independently review the generated/vendor fixture groups before adding any
   path-and-rule-specific allowlist. Never allowlist the private-key findings.
5. Rerun both the complete-history and exact-worktree Gitleaks scans, followed
   by TruffleHog. Both tools must report zero unadjudicated findings.

Canary and public readiness additionally require
`credential-incident-report.json` under the operational evidence bundle. The
report is validated by `scripts/audit/credential_incident_evidence.py` against
the exact target commit and requires public, content-hashed rotation, balance,
role-impact, all-ref rewrite, collaborator/fork/cache remediation, scanner, and
named-reviewer artifacts. This adjudication document cannot satisfy that
contract by itself.

History rewriting and credential rotation are repository-owner security
actions. They are intentionally not performed automatically by the deployment
implementation task.
