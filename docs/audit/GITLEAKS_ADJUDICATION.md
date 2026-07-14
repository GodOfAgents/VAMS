# Gitleaks Historical Finding Adjudication

**Scan date:** 2026-07-13

**Tool:** Gitleaks v8.30.1

**Scope:** All 82 commits reachable through `--all`; findings were fully
redacted before classification.

## Gate Result

The history scan is **blocking**. It reported 1,734 matches: 1,731 generic API
key matches and three PEM private-key matches. No baseline or allowlist has been
added because doing so before credential invalidation and owner review would
hide a real historical exposure.

## Redacted Classification

| Class | Matches | Assessment |
| --- | ---: | --- |
| Deleted Foundry output JSON | 1,604 | Generated compiler/test output. These generic-key matches require sampled reviewer confirmation before a narrow historical allowlist is permitted. |
| Tracked `.foundry/` test fixtures | 92 | Upstream test vectors and fixture material, not VAMS deployment credentials. Pin provenance and use path/rule-scoped exclusions only after independent review. |
| VAMS source and deleted demo scripts | 35 | Generic-key matches across legacy deployment helpers, configuration, and deleted JavaScript demos. Treat as potentially live until the relevant providers and owners confirm revocation. |
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

History rewriting and credential rotation are repository-owner security
actions. They are intentionally not performed automatically by the deployment
implementation task.
