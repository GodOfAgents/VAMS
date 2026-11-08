# Cardano governance release-package binding

Date: 2026-10-28. Status: source/package-consistency implementation; authentic
native qualification, custody, independent review and deployment remain pending.

## Observed mismatch and versioned migration

The old readiness checker required legacy governor/timelock artifacts and accepted
two signatures for Cardano intent cancellation. The selected governance v2 uses
three-of-five governance cancellation and a48-hour Queue. The separate two-of-three
pause authority does not gain intent-cancellation power. Two new regressions expose
both old admission errors on the preserved checker; no deployment is performed.

Cardano deployment metadata now requires schema2.0.0. The exact old schema is
retained at docs/audit/schemas/history/deployment-manifest-1.0.0.schema.json;
historical Cardano v1 records remain historical and are inadmissible. Existing v1
validator/action encodings and the old blueprint are not reinterpreted or changed.
Current required artifacts are the authority, governor, timelock and three policies
from governance_v2 plus the established insurance and agent-registry artifacts.
Applied authority and governance-custody metadata must agree.

The package records exact compiler/runner identities and all current Aiken lib/
validator sources, tests and locked project/dependency inputs. Source-map omission,
mutation or addition requires a new package. Every applied artifact carries an
exact binary-script reference under docs/audit/evidence/cardano-v2/. Hash checks
bind those bytes to the recorded artifact, CBOR digest and Plutusv3 script identity.
Build, native-test, applied-parameter, ledger, budget and review records are required
nonempty hash-bound references. No such authentic records were fabricated here.
The aggregate manifest now includes and requires these direct binary/record
references, preventing an unsigned file replacement under a signed wrapper.

## Meaning and limits of these checks

This validates package consistency. It does not evaluate UPLC, run Aiken, authenticate
a named runner/reviewer, prove that claimed compiler output came from source, decode
applied parameters, validate ledger signatures/genesis or independently observe
chain state. The existing required Aiken/full gates, signed aggregate, custody,
source-to-build reproduction, parameter/ledger checks and independent review remain
necessary. Merely writing a runner ID, positive report or matching hash does not
qualify it. All actual runner/custody/reviewer/applied identities remain UNKNOWN.

Opaque synthetic byte fixtures deliberately test metadata behavior only; even
their passing result is not a deployable or native-valid script. The original
required commands, audit-track gates, observations and authorizations are unchanged.
No readiness or finding promotion follows from this package check.

The [ledger source](https://cardano-ledger.cardano.intersectmbo.org/cardano-ledger-core/src/Cardano.Ledger.Plutus.Language.html)
hashes the language tag and original script bytes; Plutusv3 uses tag03. The
[CIP-57 blueprint](https://cips.cardano.org/cip/CIP-57) distinguishes compiled code
from source/schema metadata. Data-only cross-checking reproduced all26 declared
hashes in the retained historical blueprint, not the new governance source.

Governance-v2 artifact addresses must be the canonical stake-less script address
for their exact script hash, using the [CIP-19](https://cips.cardano.org/cip/CIP-19)
type7/network0 profile and [Bech32](https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki)
encoding. The published CIP-19 enterprise-script test vector is an independent
encoding check. The shared testnet address tag does not distinguish Pre-Prod from
Preview; approved genesis/network-magic and actual ledger evidence remain required.

## Remaining deployment design work

Polygon's existing v1 release contract is still stale: it requires ordinary
governor/vesting artifacts and that governor's proposer grant, despite the restricted
deployment removing them. That mismatch is not silently relaxed here. Its explicit
restricted-profile migration and actual registry/policy/verifier/settlement
deployment/dependency bindings remain a separate repair. Likewise, Cardano package
checks do not supply qualified build artifacts, native81-obligation coverage,
ledger/budget results, custody appointments or a signed dual-chain rehearsal.

Full Python/scanner gates and independent schema validation remain pending;
jsonschema is unavailable in the retained supplemental Windows runtime and no
dependency is installed. Source/JSON parsing and internal-reference checks have a
narrower scope. Raw source-bound test commands/output/exits/hashes stay outside the
checkout in VAMS-implementation-20261028/RELEASE-* captures.

INV1-10 and all economic/activation restrictions are unchanged. This is release
evidence validation, not an on-chain authority change. ExecuteIntent remains
disabled. F02/F03 remain open; thirteen findings and all36 tracks remain unverified.


Local release-checker evidence:45 metadata fixture tests pass,0 failures/errors/
skips (RELEASE-CANDIDATE-03). The preserved checker failed both new retirement/
cancellation regressions. Independent CIP-19 address-vector and26 retained
blueprint hash checks cover encoding/checksum recipes only. No native Aiken,
ledger, build provenance, signature, custody or live qualification is claimed.
Canonical integration and a source-bound metadata rerun are retained separately.
