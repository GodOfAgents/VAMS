# T06 credential and history blocker audit - 2026-10-03

Status: blocked on external incident evidence and separately authorized coordinated history operations. Read-only reconciliation only; no secret scan, credential access/change, repository history operation, vendor change, or network request was performed.

## Current requirements and source records

- `docs/audit/control-matrix.json` SHA-256 `28b9146bb2ace970c19441ab4cd8ee4f91937d56acf4f178b3639f5b4f493cf4` marks T06 partial under G1 and requires Gitleaks, TruffleHog, and default-credential evidence.
- `docs/audit/GITLEAKS_ADJUDICATION.md` SHA-256 `a3a7becb536acf32e2f66ae51704af036c38901205ce4524aac76ae82ea62f44` says current-tree findings adjudication does not satisfy complete-history Gitleaks or T06 credential-incident closure. The protected history run remains blocking; the local M0.4 gate only establishes its scoped current-tree vendor baseline.
- `docs/audit/TRUFFLEHOG_TRIAGE.md` SHA-256 `3fd4ac823c348c6d26fb488ee7c94b76d0a2052dc67eb6c6057fcf8d3b036017` records 20 unverified findings in the latest sanitized artifact and an earlier verified Infura event. It requires credential/provider impact evidence and a zero-finding protected scan after an approved history rewrite.
- `docs/audit/CREDENTIAL_INCIDENT_RUNBOOK.md` SHA-256 `094fe9814f5ca6058109cbd234f31106bf8df6d8f26a04b46a387e9750926c4b` defines credential/provider impact proof, key-role impact checks, an encrypted external rewrite root, hosted ref/fork/PR/ruleset inventory, staged local rewrite approval, and separate approval for the exact remote rewritten ref set.

No current provider dashboard or hosted GitHub state was available or checked. A scan result changing from verified to unverified does not prove provider credential revocation, permanent PEM identity decommission, or absence of past access/billing impact. Sanitized historical scanner records are not live provider evidence.

## Independent review

Read-only review by `/root/f05_other_seed_blocker_review`: PASS for the cited T06 control and blocker records. The reviewer confirmed that repository-only work cannot supply provider revocation/impact evidence, current hosted ref inventory, the encrypted external rewrite mirror, coordination across clones/forks, or exact remote rewrite approval. The reviewer performed no secret scan, made no changes, and did not verify current provider or GitHub state.

## Current readiness diagnostic

`python3 scripts/audit/audit_program.py validate` exited 0: 36 tracks and the testnet profile valid.

`python3 scripts/audit/audit_program.py readiness --stage canary` exited 1. It reports unresolved/partial tracks T01-T35 (0/35 fully verified), a dirty working tree, missing or empty `audit-evidence.json` and `audit-evidence.sigstore.json`, missing `assurance-index.json`, missing Polygon Amoy and Cardano Pre-Prod rehearsal manifests, missing `runtime-integration.json`, and missing `privacy-review.json`. The exact stdout/stderr and command/exit code are retained in `READINESS-RESULT.json`; its SHA-256 is in `EVIDENCE-SHA256.json`. No readiness artifact was fabricated. The checkout has extensive user work and is intentionally preserved, so the clean-tree criterion cannot be satisfied by discarding those changes.

## Smallest external prerequisites and boundary

T06 cannot be closed by another repository-only source edit. The responsible operators must provide sanitized, content-bound provider credential revocation/impact evidence and permanent PEM identity decommission/role-impact evidence; Architect/owner-approved incident-only preparation; encrypted external mirror and current hosted refs/forks/PRs/rulesets; and a coordinated rewrite window. After independent local rewrite review and zero-finding complete-history scans, remote history mutation still needs its own exact-ref approval. No credential or history action is authorized by this audit.

T06 remains partial. F05 remains 45/55 negative cases and 18/21 mutations; the proof-domain and six applied-parameter decisions remain unresolved. F04's separate normative validator-path decision is pending. M7 and all mandatory deployment gates remain open; readiness NOT READY and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
