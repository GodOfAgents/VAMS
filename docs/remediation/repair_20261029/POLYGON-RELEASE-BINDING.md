# Restricted Polygon release binding

Status: integrated; local package checks pass; release qualification remains incomplete.
Date: 2026-10-29. Decision basis: the owner's staged implementation plan and
registry-authoritative, restricted-economics, Automata/EZKL decisions.

## Defect and correction

The retained `DeployTestnet.s.sol` uses `VAMSRestrictedStaking`, omits ordinary
token governance/vesting and grants the proposer role to the governance Safe.
The retained audit program instead required ordinary staking/governor/vesting
and an ordinary-governor proposer grant. It also omitted provider-bond, service
registry and proof-policy dependencies from canary admission. The two retained
before-checker regressions demonstrate acceptance of that legacy package/grant.

The candidate requires deployment schema `2.0.0` and explicit
`restricted-testnet-v1` for Polygon Amoy chain `80002`. Cardano keeps its distinct
authenticated governance-v2 package and schema `2.0.0`. The immediately preceding
mixed schema is preserved byte-for-byte in the history directory; the older v1
history remains untouched. Old manifests keep historical meaning and reject as
new admission inputs. This is a versioned migration, not a waiver of missing gates.

The required Polygon canary set is token, restricted staking, timelock, Sentinel,
service registry, bond registry, restricted policy, action delivery router,
SGX/EZKL adapters and composed settlement. The public set preserves every other
previously required public artifact and adds these dependencies; the three
incompatible ordinary staking/governor/vesting entries are replaced/retired.
This does not retire security tracks or qualify inactive public components.
The current four-contract deploy script does not yet deploy that full service
stack. An honest package must keep failing until its real dependencies exist.

## Constructor, role and activation contract

`restricted_evm` binds constructor/configuration observations to the actual
declared artifacts and authorities: token, timelock, treasury, bond/service
registries, delivery router, policy and adapter code identities. These labels are
typed package fields, not an assertion that each is an identically named RPC
getter. Backend/router measurements and runtime/model/circuit identities are
explicit external qualification inputs. No provider configuration is invented.

The role inventory requires timelock-controlled token/registry/settlement
administration, no token minter, the exact composed settlement as the sole bond
registry escrow, and no slasher/hardware/sentinel bond-role activation. Timelock
roles retain self administration, governance-Safe proposer/canceller and open
execution, with deployer administration removed; extra proposer evidence rejects.
Existing separate pause-only authority requirements remain. These inventories
are declarations to be independently reconstructed from authenticated observations;
a nonenumerable AccessControl role cannot be proven complete by one `hasRole` call.

Activation observations require integer-zero rewards/emissions and disabled
staking minter/rewards, vesting, buyback, delegation, ordinary token governor,
Deposit, Slash activation, ExecuteIntent, real fiat and real yield. Booleans,
floats, missing fields or future switches cannot silently replace that contract.
Exposure, concentration, minimum-provider and observation limits remain unchanged.

Six distinct, nonempty, hash-bound records cover build, state readback, activation
tests, authentic DCAP qualification, authentic fixed-model EZKL qualification and
insurance custody. They stay under `docs/audit/evidence/polygon-restricted-v1/`;
path traversal, Windows drive forms, substitutions, empty files and scope reuse
reject. Both readiness and aggregate generation include direct references.
This work does not change signing code or authenticate the records' authors.

## Assurance limits and migration

Package equality, declared code hashes and SHA256 file integrity do not prove
source-to-bytecode compilation, deployed code/initializer/state, genuine hardware
or circuit execution, valid collateral/TCB/freshness, custody, qualified runners,
independent review or on-chain observations. Arbitrary nonempty fixture records
can satisfy consistency tests; they cannot satisfy the separate assurance gates.
All focused positive fixtures are explicitly synthetic and temporary, and none
is written as authentic evidence in the canonical release evidence directory.

The actual reviewed hardware/verifier/model/key, insurance recipient, custodians,
observer and approved runner remain UNKNOWN. No changed non-upgradeable contract
is imported into an old instance. Old ownerless active bond-registry requests
require separately reviewed provenance/drain/migration; this checker does not
approve a deployed proxy upgrade or make that legacy state recoverable.

Full source/build/role/state/activation/proof/insurance evidence, independent
acceptance and actual both-chain rehearsal remain stage requirements. The service
deployment/configuration producer still needs implementation; constructor and
ESCROW_ROLE readbacks must then be checked against its actual postconditions.

## Evidence and invariant impact

`POLYGON-BEFORE-01`: two regressions fail on the retained checker, zero errors.
`POLYGON-CANDIDATE-01`: 38 focused metadata tests pass, zero failures/errors/skips.
`POLYGON-CANDIDATE-WIDE-01`: 80 tests attempted, 78 pass, zero assertion failures,
two environment errors: unavailable Windows symlink privilege and Git executable/
checkout metadata for the existing complete-gate generation test. Three complete-
canonical-tree tests were explicitly excluded from this supplemental harness.
The errors/exclusions remain pending; the run is not reported as a full pass.
The later schema/reference/package review is recorded separately. JSON-Schema
engine validation remains pending; parsing and resolving local references is not
schema validation. These are Windows Python3.12 supplemental checks, not the
approved independent Linux workflow or a native Cardano/Solidity run.

The candidate changes release admission and test metadata only. INV-9 restrictions
and registry-backed settlement are reflected more accurately; INV-1 through INV-10
requirements and current protocol implementations remain unchanged. No economic
cap, emission, fee, timelock, credential, bridge or proof rule is weakened. Local
767-test Solidity evidence remains source-specific, not a new gate run for this
slice. No official finding or audit track is promoted.

Runtime/provider/observer and permanent on-chain link privacy review remains
required. No privileged deployment, key use, signing, live role/fund operation,
provider contact, dependency acquisition, Aiken/Slot08 or reserved R28 execution
was performed. Earlier canonical access review failed because workspace credits were exhausted.
The owner restored credits; fresh all-path guards, integration and canonical checks
then passed. Retained candidate plans keep their historical pre-integration identity.


### Restricted Polygon release binding — canonical verification, 2026-10-29

The explicit schema2.0.0/restricted-testnet-v1 migration is integrated. It binds
restricted staking and the complete registry/policy/proof/settlement artifact set,
constructor/configuration observations, exact escrow-role inventory and disabled
economic/action activation. Ordinary governor/vesting/proposer requirements are
retired for this profile; other public-stage artifacts and Cardano-v2 remain.
Direct build/readback/activation/DCAP/EZKL/insurance record bytes enter the signed
aggregate. Historical schemas retain their original bytes and source identities.

Canonical metadata suite:83 tests pass,0 failures/errors/skips, none excluded.
Canonical JSON-Schema meta-validation and17 positive/adversarial cases pass using
the existing hash-recorded jsonschema4.19.2 environment. This exposed and corrected
the old exact-six-role schema rule: restricted timelock evidence requires exactly
five records and rejects missing/extra records. JSON numeric0.0 needs the separate
exact application-type check; the schema/application distinction is tested.
Source remained unchanged during both commands. All outputs/exits/runtime/package
identities are retained in POLYGON-LINUX-CANONICAL-01 and POLYGON-SCHEMA-CANONICAL-01.
The former Windows errors/exclusions and initial schema failures remain historical
evidence; the full Linux metadata run covers the same cases without exclusion.

These are Python3.14 package/fixture checks, not independent Python3.12 CI parity,
native protocol compilation, authentic proofs, observed chain/custody or independent
assurance. No new Solidity/Aiken/ledger/live/provider execution was performed. The
earlier767 Solidity tests retain their own unchanged contract-source identity.
No official finding/track is promoted;0/36 tracks verified and13 open findings
remain. The owner restored credits and normal canonical review access succeeded;
the earlier review failure is historical, not a standing access prohibition.

NEXT: implement the full service deployment/configuration producer and verify its
actual constructor/role/disabled-activation postconditions. The current core script
still deploys four contracts only. Bond registry initialization must be atomic;
separate broadcast deployment and initialization would permit takeover. Do not
invent verifier/model/insurance/custody identifiers or treat codehash declarations
as their qualification. Keep governance81-obligation coverage/native qualification,
full action interception, real PG/provider fencing/recovery, authentic proof/native
bridge/Mocha/Near/independent observer, full frozen gates/privacy/assurance and real
both-chain7-/14-day observation in scope. All scoped restrictions remain: no
Aiken/Slot08/R28, installs/downloads, providers, signing/funds/roles/deployment.


### Full restricted service producer — local native candidate, 2026-10-29

DeployRestrictedTestnet extends the preserved core producer with typed explicit
backend/model/custody inputs and the full eleven-artifact service topology.
FreshProviderBondRegistry creates and initializes the actual fresh registry in
one constructor transaction; the helper receives no role and has no callable
factory/administrative surface. No proxy/storage/initializer change or legacy
owner adoption is introduced. Registry escrow authority goes only to the exact
settlement; registry administration/pause are handed to the48-hour timelock and
bootstrap deployer roles are removed. Policy starts with no admission authority;
zero rewards/emissions/no minter and the absent ordinary governor/vesting remain.

Native focused candidate:24 tests pass,0failures/skips. A retained before probe
demonstrates the old producer creates4contracts rather than the required11.
Two additional regressions reproduced missing SGX-version/router preflight; those
now reject before any creation/key read. All tests use explicit Safe/backend/
insurance fixtures; the EZKL fixture rejects all proofs and no genuine proof is
claimed. Script run/broadcast, key access and external services were not invoked.
Canonical integration/full tests/build sizes and all authentic release gates follow.

This closes source construction/postcondition gaps only. Codehash agreement and
constructor-interface shape do not qualify custody, hardware, collateral, model/
key, runner or independent review. The live broadcast path creates multiple
transactions; whole-rehearsal rollback is not whole-production atomicity or
deployment retry safety. Reconcile partial/uncertain broadcasts separately; never
retry unknown outcomes. Actual identities remain UNKNOWN. Both-chain governance,
policy/runtime, PG/provider recovery, authentic proofs/bridge/DA, privacy/assurance
and actual observation requirements remain. No official finding/track is promoted.


### Full restricted service producer — canonical verification, 2026-10-29

The full eleven-artifact producer and atomic fresh bond-registry bootstrap are
integrated. Canonical Solidity:791tests/47suites pass,0failures/skips, exit0. The
24focused producer tests are included, not additive. Offline build--sizes exits0;
warnings and exact source/tool/command/output identities are retained in
DEPLOYMENT-CANONICAL-FULL-01 and DEPLOYMENT-CANONICAL-SIZES-01. All contracts/src
files, including the registry initializer, are unchanged by this script/test slice.
Compiled size bounds pass for the atomic bootstrap, registry and settlement.

These are local native VM results with explicit Safe/backend/insurance fixtures.
No script run/broadcast, real signing/funds/roles, provider or external service was
invoked; no authentic DCAP/EZKL/custody evidence is implied. The old4<11probe and
two preflight failures are retained separately. Read-only configuration preflight
now rejects unsupported SGX versions/router identities before any creation/key read.
Code/runtime pins still do not authenticate collateral, mutable proxy state, model
constraints or custodians. Live multi-transaction execution/partial reconciliation
and independent readbacks require a separately authorized reviewed ceremony.

The earlier83metadata tests/17schema cases retain their separate source/scope.
Full frozen scanners/independentLinuxPython3.12/Rust/frontend/Envoy/SBOM/signing,
authorized Aiken/native ledger/budgets, governance81-obligation coverage, complete
policy/credential/dispatch enforcement, completed-effect reconciliation, real PG/
provider fencing/recovery, authentic bridge/DA/observer, privacy/custody/independent
assurance and actual both-chain7-/14-day observations remain.13open findings and
0/36verified tracks remain; neither local suite nor this construction slice is
closed-canary admission. All disabled/restricted paths and scoped authorizations
remain. No Aiken/Slot08/R28, installation/download, provider contact or deployment.
