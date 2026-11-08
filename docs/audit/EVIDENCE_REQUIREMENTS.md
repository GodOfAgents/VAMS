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
The closure report uses schema `4.0.1`: two PEM occurrences bind to two
permanently decommissioned identities with no replacements, while the separate
Infura record preserves `exact_revocation_time_unavailable=true` and a
content-hashed dashboard observation. Review mode is `architect-owner`, not
independent review.

## Canary Inputs

| File | Required contents |
| --- | --- |
| `audit-evidence.json` + `audit-evidence.sigstore.json` | Successful exact-commit gates and the Sigstore bundle produced and verified by the current workflow; the workflow's certificate-identity pattern remains subject to the open T05 review |
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
| `closed-canary-report.json` + `closed-canary-report.sigstore.json` | At least seven consecutive days, no stop condition, all seven drills passed; the bundle is verified by the public-stage workflow |

The schema1.0.0 canary report must include timezone-aware RFC3339 `started_at`
and `ended_at`. The interval must span at least seven elapsed days, end no later
than validation time, and cover the integer `consecutive_days` claim without
rounding fractional timestamps. Extra boolean drills remain allowed. These are
consistency checks, not proof of actual operation, observer independence or clock
accuracy; signed runtime/drill/operator evidence and independent assurance remain.
No completed observation requirement is added to restricted canary admission.

| `independent-reviews.json` | Approved Solidity, Aiken, economics, Gateway/SDK, privacy, and AI-safety reports with zero blockers |
| `polygon-amoy-deployment.json` | Verified addresses, transactions, bytecode, owners, thresholds, role transfers, rollback |
| `cardano-preprod-deployment.json` | Script hashes, transactions, multisig ownership, parameters, rollback |

Every `Pending` field in `contracts/CONTRACTS.md` must be replaced with verified
facts before public promotion. The 14-day public soak is a post-onboarding gate
for incentives or increased exposure, not permission to bypass the seven-day
closed canary.


## Cardano governance v2 package

Cardano rehearsal/deployment manifests use schema2.0.0 and the package contract in
`scripts/audit/cardano_governance_release.py`. Polygon also requires version2.0.0 with the explicit restricted-testnet-v1 package. Do not reuse old Cardano v1 source/artifacts.
Each Cardano artifact binds exact serialized Plutusv3 bytes; cardano_build binds all
current source/test/dependency inputs, compiler/runner identities and six retained
records: build, native tests, applied parameters, ledger, budgets and review.
The aggregate must bind every direct reference, including binary scripts. All
actual files and claimed results require authentic qualification and review;
format/hash agreement is not proof that a compiler, ledger or reviewer ran.
See `../remediation/repair_20261028/RELEASE-BINDING.md`. Missing values remain
UNKNOWN; no fixture may be placed in release evidence as an authentic result.


## Polygon restricted release package

Both Polygon canary and public manifests require deployment schema2.0.0,
release_profile=restricted-testnet-v1, chain_identifier=80002 and restricted_evm.
The canary set includes the four core contracts with VAMSRestrictedStaking, plus
ServiceBlockRegistry, ProviderBondRegistry, RestrictedTestnetPolicyV1,
ActionDeliveryVerifierV1, AutomataSgxActionVerifierV1, EzklActionVerifierV1 and
ComposedSettlement. Ordinary VAMSStaking, VAMSVesting and VAMSGovernor cannot be
substituted. Public-stage additional artifacts and actual deployment requirements
remain; this migration does not retire their security tracks.

The package binds constructor/configuration observations, restricted role
memberships (including the exact settlement ESCROW_ROLE and no minter/slasher),
zero emissions/rewards and disabled vesting/buyback/delegation/token-governor,
Deposit/Slash/ExecuteIntent/real-fiat/real-yield activation. Its six distinct records
cover build, state readback, activation tests, qualified DCAP, qualified EZKL and
insurance custody under docs/audit/evidence/polygon-restricted-v1/. The signed
aggregate must bind every direct record's exact bytes. Historical schemas remain
archived; old manifests are historical evidence, not current admission inputs.

These checks compare declarations and retained file hashes. They do not execute
contracts, compile or authenticate proof verifiers, establish collateral/model/
key validity, authenticate a readback operator/reviewer, or approve proxy migration.
Current-source full gates, independently accepted proof/runtime/custody/privacy
evidence and both-chain rehearsals remain mandatory. Do not insert synthetic
fixture records as authentic evidence. Provider/model/custody identities remain
UNKNOWN until reviewed manifests establish them. See the repair ADR.

### Selected profile configuration identity

The checked-in `testnet-profile.json` version1.0.0 has an exact typed contract in
`scripts/audit/restricted_profile_v1.py`. Audit-program validation, concentration
evaluation and the synthetic campaign reject missing/unknown fields, altered
selected values or wrong JSON types. This binds configuration identity only;
actual governance, provider independence, exposure controls and elapsed days need
their own evidence. General policy caps/minima can allow stricter alternatives,
but an alternate configuration requires a reviewed version rather than silent
reinterpretation of this selected profile. Threshold comparison semantics stay.
