# Governed object eligibility and bounded actor consent

Date:2026-10-30. Status:integrated;820native Solidity tests/sizes and12copied-source codec checks pass;authentic runtime/live qualification pending.

## Design and versioning

This implements a missing StageD policy data contract, following GCA_ACCEPTANCE,
the action/signer/authority/renewal ADRs, VDSO's dual-host boundaries and the owner's
research repair design. CaMeL motivates enforced capabilities/control-data separation;
it does not prove VAMS alignment. The research document is external Windows design
context, not a canonical source artifact; its exact copy/hash is retained separately.

The previous generic authorizes(Context) could return true for object/signing routes
without an actor/resource/issuer grant. The before fixture reproduces two view-level
failures; it does not claim an actual external effect was executed. The generic API
now accepts only settlement capability4. Object callers migrate explicitly to the
typed grant method; signing2 remains ineligible until its broker qualifies. Existing
escrow initiator and provider delivery-root roles remain distinct and unchanged.

GovernedObjectGrantV1 is a new domain/codec, not ReceiptV3 or a changed action/scope
format. Canonical bytes are ASCII domain+NUL, fixed32-byte words for policy address,
chain/domain/unit, exact identities/issuer roles/nonce and integer limits/count,
then the raw sorted resource words. SHA256 hashes bytes. The actor signs this exact
hashed message with canonical65-byte r||s||v ECDSA (v27/28, lowS), not an EIP191
prefixed message, transaction or existing local MAC receipt. No live signing path
or SDK raw-key use is enabled. Contract code uses existing pinned OpenZeppelin ECDSA.

The leaf hashes a distinct leaf domain and grant digest. Positioned proof nodes
hash a distinct node domain, left and right children; path length<=32 and no unused
index bits. Single-leaf proof is empty/index0. A consent is not sufficient without
governed membership; membership does not let governance impersonate the actor.
policyRoot remains governed by the exact VAMS48h timelock. The typed object method
gives that root an explicit versioned grant-membership interpretation; existing
settlement context/receipt bytes do not change. A monotonic per-grant revocation
mapping preserves actor stop authority without allowing wider rights or global
generation changes. It is checked by both typed views and must be authenticated
by the eventual current-host reader alongside root/configuration.

## Bounds and current authorization

Grant actor/provider/runtime/workflow/intent/target and both issuer IDs are exact.
The expected issuer pair must come from the real configured runtime identity.
No self-signed witness enrolls its own key. Resources are sorted, unique, nonzero,
bounded1-64; scopes may narrow that set. Integer cumulative ceiling and per-action
cost cannot widen host bounds, scope lifetime<=600s and active window<=24h. A future
window can be consented before the48h governance delay; consent age is distinct
from the active window and does not bypass timelock/session restrictions.

Current context root/version/epoch, chain/host/unit, route, lifetime/capability/budget
checks intersect those grant bounds. Object action hash binds stable V3 operation,
resource, exact input, cost and fence; wrong commitments reject. Scope digest remains
byte-identical to the PythonV3 golden. Eligibility is read-only: it does not consume
a nonce/operation, reserve funds, establish provider fencing or allow duplicate
dispatch. Those durable mechanisms remain necessary. Cumulative accounting must
not reset after a new grant; storage4 already retains the stable head's spending.

Governance changes invalidate pending context generations. It may retain a bounded
consent in a new root only within its original window; current generation validation
is still required. This does not reissue an old operation or permit host/provider/
issuer migration. Historical effect/absence/earned-claim/refund paths stay separate.

## Evidence, invariants and limitations

Candidate01 failed compilation on explicit signed/unsigned casts; exact source and
output retained. Candidate02 compiles and passes25native tests (one256-case budget
fuzz test included), zero failures/skips. Python codec passes12tests without external
dependencies/I/O/signing. They test actual local consent/timelock/membership and
current-policy algorithms with public synthetic identities, not actual custody or
runtime host authentication. Frozen Python/Solidity grant/Merkle and existingV3
scope digests agree; native Rust/Aiken/other wire campaigns remain pending.

No native chain state/finality/code/governance reader or approved host/key manifest
exists yet. This view must not be promoted to that reader or used with an untrusted
RPC Boolean. Remote credential/key isolation, authority/provider cooperation, native
PG/clock/TLS/crash/fencing/restore campaigns and independent zero-effect observation
remain. No committee replaces native bridge verification. Polygon code does not
govern Cardano-owned state. Changed non-upgradeable policy needs a fresh separately
authorized instance and exact code/constructor/runtime binding.

INV1/2/7/8/9 economic/oracle/supply/reward controls are unchanged; eligibility budgets
are not token backing. INV3/4 session24h/whitelist stay; this is not a session grant.
INV5 fail-closed remains. INV6 root identity remains, not authentic TEE qualification.
INV10 proof/payload separation unchanged. Deposit/Slash/ExecuteIntent/fiat/yield/
rewards/minter/ordinary governor/vesting/buyback/delegation stay restricted. No key
or private workload is stored. Revealed actor/resource/intent/issuer/consent/ceiling
linkage and observer/retention require outstanding privacy acceptance. All A-G,
dual-chain35/36track gates, independent assurance and actual7-/14day observation
remain. Native/fixture counts never establish readiness or close official findings.


### Governed object grants and actor consent — 2026-10-30

RestrictedTestnetPolicyV1 now has explicit typed object/scope authorization. A
versioned grant binds actor/provider/runtime/workflow/intent/target, distinct
authority/provider issuer IDs, sorted1-64resources, cumulative budget/per-action
cost, <=600s scopes, <=24h active window and nonce. Its SHA256 digest binds the
exact host policy contract/chain/domain/unit. Canonical low-S root-EOA consent
and positioned SHA256 membership in the timelock-governed current policyRoot
are both required. Delegated issuers cannot create or widen that governed root.

New checks intersect the grant with current policy generation/routes/bounds, exact
resource subset and V3 action/operation commitments. The generic authorizes(Context)
is now settlement-capability4-only; unbound capability1 and unsupported signing2
must reject. Runtime callers must use the typed object path with issuer IDs from
their actual configured identity, not supplied by the witness. Existing settlement
checks stay separate. Action/scope/ReceiptV3 bytes are unchanged; a new monotonic
per-grant revocation mapping lets each actor disable only its own exact consent.

Focused native candidate29tests and Python public codec12tests pass. Native cases
use local actor consent/one-member governance fixtures, not actual3-of-5 custody,
live signing, chain finality, remote effects or independent assurance. Original
unbound capability1/2 view behavior was reproduced in2failing native regressions.
Python/Solidity grant and positioned-Merkle vectors plus existing scopeV3 digest
agree; Rust/Aiken/new receipt wire qualification remains separate. Full canonical
native suite/size gates and copied-source codec verification follow integration.

This is a source eligibility predicate, not an authenticated runtime host reader,
spending ledger, provider fence acknowledgement, execution proof or settlement.
Native current-state/finality/code/governance/custody authentication, issuer key
enrollment, remote key boundary, actual policy/PG serialization and completed-effect/
checkpoint/settlement integration remain. No committee/RPC fallback or live route.
New non-upgradeable policy instances require a separately authorized reviewed
deployment; no existing address upgrade is implied. Cardano domains remain native.
Grant/consent/resource/issuer/cumulative-budget linkage requires privacy review.
All A-G/both-chain gates stay;13open findings/0of36verified tracks, no promotions.


Owner revocation amendment,2026-10-30: only the actual grant root EOA can permanently
revoke its exact domain-bound digest. The new revokedObjectGrants mapping is
monotonic and repeated revocation is idempotent. It cannot be cleared by governance
root reuse. Global policyVersion/authorityEpoch do not change on actor revocation,
so other actors' grants cannot be invalidated by unrelated revocation. Typed views
check the flag each time; native runtime readers must authenticate this current
flag with the same root/config source. This is revoke-only, not broader authority,
system pause, provider migration, key recovery or token delegation activation.

The first25-test candidate/full816-test result remains historical evidence. One
new native regression reproduced the absent owner path (26tests/1failure/0skips).
Candidate03 passes29focused tests, including4owner cases; Python codec12 remains
passing. Current full canonical suite/sizes follow this source amendment. New
mapping/event requires privacy review of consent-digest/root linkage. Changed
non-upgradeable policy needs a new separately authorized instance, with no proxy
adoption/migration claim. Full A-G/native/live/independent requirements remain.


Canonical final verification,2026-10-30: OBJECT-GRANT-CANONICAL-FULL-02 passes820
Solidity tests/48suites, zero failures/skips;29new grant tests INCLUDED with791
previous tests. The earlier816-test first draft and25/29focused campaigns overlap.
Offline build--sizes exits0; RestrictedTestnetPolicyV1 runtime9,982bytes/init17,322.
OBJECT-GRANT-CODEC-CANONICAL-02 passes12Python3.12 public codec tests with zero
failures/errors/skips and no network/process attempts. Seven exact inputs exported
after checking all6,676source paths. Python/Solidity grant and positioned-Merkle
bytes plus existing scopeV3 digest agree; Rust/Aiken/other wire checks remain.
Existing143runtime tests retain their original result and matching source hashes;
they were not rerun or added to820/12. Cardano/workflow/other protocol sources stay.

The hash-verified existing Gitleaks8.30.1 focused current-grant scan exits0 with an
empty redacted report. This scans8exact source/vector/config inputs, NOT complete
history or the frozen full CI gate. Slither/Bandit/Semgrep/pip-audit/TruffleHog,
independent Linux3.12/native PG/Rust/frontend/Envoy/SBOM/signing and other frozen
qualification remain pending. No dependency, network, real key/signing/fund/role/
deployment, Aiken/Slot08 or R28 action occurred. Native signatures/timelock identities
are explicit VM fixtures, not actual3-of-5 governance/custody or live acceptance.

The owner-only revocation method was added after one failing26-case native probe;
29focused cases now cover revocation, root reuse, idempotence and unrelated-actor
isolation. Earlier cast compile error and UTF-8 preparation/missing-plan stops are
retained, not erased or relabelled success. The preparation failures touched staged
docs only; canonical integration followed a completed hash-guarded preparation.
No official disposition promotions:13findings remain open,0of36tracks verified.


## Public interface migration

- `authorizes(Context)`: settlement capability4 only; generic object/signing routes reject.
- `objectGrantDigestV1(Grant)`: exact SHA256 consent message; the digest grants no authority.
- `authorizesObjectV1(Proposal,Witness,authorityIssuer,providerIssuer)`: current eligibility,
  with actual configured issuer IDs, action binding, consent, membership and revocation.
- `authorizesObjectScopeV1(Scope,Witness,authorityIssuer,providerIssuer)`: same current
  grant plus narrowed resource/cost/shared-ceiling/lifetime/fence bounds.
- `revokeObjectGrantV1(Grant)`: root-actor transaction permanently disables only that digest.
- `revokedObjectGrants(digest)`: current monotonic flag, authenticated by the runtime
  reader from the same native state/finality source as policy/configuration.

These methods do not issue an admission, return a credential, dispatch an effect,
settle funds or replace native finality verification. The actual runtime reader
and caller/credential integration remain required. A raw view result from an
untrusted RPC, a fixture callback, self-signed issuer or stale consent is insufficient.
