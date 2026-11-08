# Restricted service producer and atomic registry birth

Date:2026-10-29. Status:integrated; local native construction tests pass; authentic/full/live qualification pending.

## Design basis and discrepancy

The selected restricted profile requires eleven actual protocol artifacts. The
old DeployTestnet produces only token, restricted staking, timelock and Sentinel.
The release-checker migration already requires the registry/policy/proof/settlement
dependencies. The source producer must construct those dependencies without
inventing the UNKNOWN external verifier/model/insurance/custody configuration.
This follows the owner's staged repair plan and prior action/settlement/proof ADR.

## Construction, authority and lifecycle

DeployRestrictedTestnet reuses core construction/authority checks through protected
script hooks; the original core run/rehearse ABI and behavior remain. The new
target's inherited default entry points reject and require explicit typed
ServiceConfiguration. Public preflight checks chain80002, nonzero domain/unit/
measurement/runtime/model/circuit identities, code-bearing pinned dependencies and
SGXv3 version/router shape. Production signing material is read only after public
configuration and Safe identity checks. No private key or live identity is embedded.

FreshProviderBondRegistry deploys and initializes the unchanged actual registry
inside its constructor. This eliminates the public uninitialized interval without
adding a proxy, reinitializer, legacy adoption or selfdestruct. The helper retains
only an immutable registry address. The initializer signature/body and every
protocol storage layout remain unchanged. This is a fresh-instance design, not
approval of any existing ownerless record or deployed proxy migration.

The producer creates service registry, policy, SGX/EZKL adapters, delivery router
and settlement with actual constructor links. Only settlement receives ESCROW_ROLE.
Registry admin/pause move to the timelock; deployer admin/pause are removed. Fresh
service and settlement admin/verifier roles belong to the timelock. No minter,
slasher, hardware or Sentinel bond role is granted. Read-only postconditions run
outside the production broadcast scope, matching the existing core ceremony.

The policy has zero root/version/epoch/capabilities/budget/lifetime and admits no
work until later authorized governance configures qualified routes. The producer
does not deploy ordinary governor/vesting/buyback/economic-delegation/reward
activation, or enable insurance Deposit/Slash, bridge ExecuteIntent, fiat or yield.
Existing token voting primitives are not an ordinary governor/protocol authority.
All protocol economic caps, fees, reward guards and bridge-proof separation remain.

## Evidence, limitations and next gate

Local rehearseRestricted uses the same creation/handoff/checks without reading a
key or invoking broadcast. Rehearsal has single-transaction rollback; production
broadcast comprises multiple transactions. It is not globally atomic/idempotent:
operator-approved manifests, transaction reconciliation, partial-deployment handling
and independent observations are still required. Never retry an uncertain run.
Runtime code pins do not bind mutable proxy implementation/state, genuine DCAP
collateral/freshness or EZKL model/circuit constraints by themselves. Authentic
qualification and complete custody/role reconstruction remain independent gates.

The fixture verifier exposes SGX constructor metadata only; it supplies no authentic
quote verification. The EZKL fixture returns false for all proofs. Fixtures never
become release evidence, provider manifests or deployed configuration. No network,
signing key, role/fund transaction or production script run was executed.

INV-1 through INV-10 protocol source/control semantics are unchanged. Deployment
backing/reward/role restrictions are affected and tested; local results cannot close
the corresponding live invariants or findings. Public release/source/privacy/
independent assurance and Polygon Amoy AND Cardano Pre-Prod remain in scope.


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
