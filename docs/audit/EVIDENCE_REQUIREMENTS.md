# VAMS Green-Signal Evidence Requirements

No evidence file should be created with invented addresses, receipts, reviewers,
timestamps, or approvals. Missing evidence remains missing and readiness fails.

## Repository Evidence Contract

All evidence belongs under `docs/audit/evidence/` and must reference the exact
release commit. `assurance-index.json` maps every applicable track to one or more
repository-relative artifacts and SHA-256 hashes. The signed aggregate manifest
must bind those files before promotion.

## Canary Inputs

| File | Required contents |
| --- | --- |
| `audit-evidence.json/.sig/.pem` | Successful exact-commit gates and valid Cosign identity |
| `assurance-index.json` | G0-G4 tracks verified, owner reviewer, zero blocking findings, artifact hashes |
| `polygon-amoy-rehearsal.json` | 3-of-5 governance/treasury, separate 2-of-3 emergency, 48-hour delay, role-removal and rollback evidence |
| `cardano-preprod-rehearsal.json` | Equivalent multisig/timelock parameters, validator artifacts, rollback evidence |
| `runtime-integration.json` | External Gateway checks, real Celestia/Near submission and retrieval receipts, excluded mock/incomplete routes |
| `privacy-review.json` | Approved inventory, retention, redaction, publisher coverage, public-content review, zero blockers |

## Public Inputs

Public promotion replaces rehearsal manifests with deployed manifests and adds:

| File | Required contents |
| --- | --- |
| `closed-canary-report.json/.sig/.pem` | At least seven consecutive days, no stop condition, all seven drills passed |
| `independent-reviews.json` | Approved Solidity, Aiken, economics, Gateway/SDK, privacy, and AI-safety reports with zero blockers |
| `polygon-amoy-deployment.json` | Verified addresses, transactions, bytecode, owners, thresholds, role transfers, rollback |
| `cardano-preprod-deployment.json` | Script hashes, transactions, multisig ownership, parameters, rollback |

Every `Pending` field in `contracts/CONTRACTS.md` must be replaced with verified
facts before public promotion. The 14-day public soak is a post-onboarding gate
for incentives or increased exposure, not permission to bypass the seven-day
closed canary.
