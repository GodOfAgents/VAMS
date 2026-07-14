# VAMS Green-Signal Evidence Requirements

No evidence file should be created with invented addresses, receipts, reviewers,
timestamps, or approvals. Missing evidence remains missing and readiness fails.

## Repository Evidence Contract

All evidence belongs under `docs/audit/evidence/` and must reference the exact
release commit. `assurance-index.json` maps every applicable track to one or more
repository-relative artifacts and SHA-256 hashes. The signed aggregate manifest
must bind those files before promotion.

The complete Git history must also pass Gitleaks and TruffleHog. The blocking
historical private-key findings recorded in `docs/audit/GITLEAKS_ADJUDICATION.md`
require credential rotation, role-impact review, coordinated history cleanup,
and a clean rescan; an unconditional baseline is not acceptable evidence.

## Canary Inputs

| File | Required contents |
| --- | --- |
| `audit-evidence.json/.sig/.pem` | Successful exact-commit gates and valid Cosign identity |
| `assurance-index.json` | G0-G4 tracks verified, owner reviewer, zero blocking findings, artifact hashes |
| `polygon-amoy-rehearsal.json` | 3-of-5 governance/treasury, separate 2-of-3 emergency, 48-hour delay, role-removal and rollback evidence |
| `cardano-preprod-rehearsal.json` | Equivalent multisig/timelock parameters, validator artifacts, rollback evidence |
| `runtime-integration.json` | External Gateway checks, real Celestia/Near submission and retrieval receipts, excluded mock/incomplete routes |
| `privacy-review.json` | Approved inventory, retention, redaction, publisher coverage, public-content review, zero blockers |

`runtime-integration.json` uses schema version `2.0.0`. Every Gateway check
must bind a non-empty repository evidence artifact and SHA-256 digest. The file
must contain exactly one Celestia Mocha and one Near Testnet receipt, distinct
submitter and retrieval-observer identities, `mock_mode=false`, provider-native
inclusion references, and retrieved payload bytes whose artifact SHA-256 equals
the submitted payload SHA-256. Current VDSO Celestia/Near adapters, Avail,
EigenDA, and every mock/incomplete integration remain listed in
`excluded_live_routes`.

`privacy-review.json` also uses schema version `2.0.0`. Boolean approvals alone
are invalid: a named human reviewer and organization must bind separate data
inventory, retention, redaction-test, public-content, and publisher-inventory
artifacts. `docs/audit/privacy-publisher-inventory.json` is checked against
publisher symbols discovered from the DA, Sentinel, and VDSO source trees so a
new sink cannot bypass review by omission.

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
