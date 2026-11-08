# Direct runtime containment for local effect helpers

Date:2026-10-29. Status:integrated;86local regression tests pass; production/full/live qualification pending.

## Design basis and discrepancy

The owner's StageD/F plan and GCA_ACCEPTANCE require direct-route enforcement and
explicit evidence versions. ADR-VDSO-001 requires current authority, one writer,
acknowledged fencing and durable reconciliation. SIGNER-CONTAINMENT already
distinguishes API runtime guards from a process-isolated external signer. The
Heart/Brain research intent is preserved: validity of a credential does not grant
permission for a denied effect, and Sentinel observations do not grant authority.

Tracing the actual callers found V3 asymmetric primitives are not connected to
local V1/V2 execution. ObjectProvider guarded only its environment factory;
direct construction and retained direct methods could open SQLite in live mode.
HttpObjectProvider and PostgresAuthorityRepository also lacked those boundaries.
CLI/coordinator entry checks did not protect their direct public methods. These
classes therefore cannot be promoted as production adapters.

## Repair and compatibility

LocalEffectRuntimeBoundary uses existing strict runtime_safety policy and freezes
the initial runtime snapshot. Construction rejects live or malformed configuration
before path/permission/database/client/credential work. Each protected public and
low-level connection/request method reloads and compares the current configuration.
All registered mock flags are parsed centrally. Supported explicit nonlive modes
remain local/test/demo. A changed mode or mock flag requires a fresh object;
there is no production-enable switch or fallback. WSGI rejects before body/auth/
storage with a generic403 and no-store. The provider factory checks before keys.

No action policy, SQL schema, transaction-control ownership, receipt encoding,
version number, durable uniqueness or completed-effect reconciliation semantics
change. V1/V2 MAC receipts retain their exact local identity. V3 signatures are
not reinterpreted or automatically substituted. The existing PG repository class
identity remains unchanged for V2 exact-type composition. No dependency, public
network backend, workflow relaxation, new persisted personal data or secret is
introduced. Source AST equivalence after removing declared runtime additions
checks the legacy SQL/commit/rollback/action/wire implementation.

## Scope and next production slice

This is trusted-process runtime API containment, not isolation from arbitrary code
with a raw key, monkeypatching, object.__setattr__, concurrent environment mutation
or independent authority/provider identities. It also is not RestrictedTestnetPolicyV1
validation: that still must be authenticated and enforced before credentials,
signing, dispatch and settlement in the production protocol. Production work must
connect V3 public admission/fence/provider signatures with separate issuer keys,
real PG reservations, atomic provider dedup/current fencing/effect, acknowledged
revocation cutover and authenticated indeterminate reconciliation/checkpoints.
Unavailable old writers must prevent unsafe authority migration. Earned claims,
refunds and completed-effect reconciliation retain separate authorization paths.

## Invariant and privacy impact

INV1/2/7/8/9 economic/oracle state is untouched. INV3/4 session validity/whitelist,
INV5 fail-closed OMS, INV6 actor-root proof binding and INV10 bridge proof/payload
separation remain unchanged. No deposit, slash, ExecuteIntent, fiat, yield, reward
or governor activation. No live key/service/funds/role/deployment action occurs.
The existing effect-module/database/WAL/backup/observer privacy review still needs
an appointed reviewer; the repair adds no stored fields or logging of credentials.


### Local effect helper runtime containment — 2026-10-29

ObjectProvider, HttpObjectProvider and PostgresAuthorityRepository now bind the
strict central runtime configuration before constructor I/O and recheck it on
public/direct effect, authentication, request and connection paths. Explicit
local/test/demo operation remains; staging/testnet/production, missing/unknown
modes and malformed registered mock flags reject. A retained object's mode or
mock configuration cannot drift in place. The normal runtime snapshot assignment
is frozen. WSGI denial occurs before reading/authenticating a request or opening
storage, with a generic no-store403. CLI provider checks also precede key parsing.

Candidate evidence:86tests pass,0failure/error/skip, including40new in-process
boundary spies,12existing actual loopback/SQLite tests,21proposal,10authority-scope
and3composition tests. Counts overlap18/22focused runs and are not additive.
Canonical verification follows. No SQL, commit/rollback ownership, receipt/schema
version, HMAC encoding or action/payload bytes changed; a guarded AST comparison
checks the legacy repository/client body after removing only runtime additions.

This closes a local-only promotion bypass. It does not connect asymmetric V3
receipts, authenticate live policy, isolate hostile code with raw credentials,
qualify PostgreSQL, establish provider cutover/exactly-once, or complete GCA.
Existing local V1/V2 MAC receipts remain local. Normal in-process immutability is
not a security boundary against arbitrary Python execution or concurrent external
environment mutation. Production service identities, authority keys, provider
cooperation, acknowledged fencing, durable reconciliation and independent
observation remain required. No new persisted data, dependency or workflow change.

The existing seven pytest controlled-driver transaction tests remain NOT RUN here:
Linux Python3.14 has neither pytest nor psycopg2. No substitutes were injected and
no dependencies acquired. Real approved independent LinuxPython3.12/PostgreSQL is
still UNKNOWN. Local SQLite fixtures and SQL doubles are not live/PG assurance.
Other frozen gates/scanners, native Aiken/ledger/budgets, authentic proofs/bridge/DA,
custody/privacy/reviewer and actual both-chain observations remain outstanding.
No official finding or track promotion;13open findings and0/36verified tracks.


### Local effect containment — canonical verification, 2026-10-29

EFFECT-INTEGRATION completed9guarded paths,4new, preserving all dirty source and
before files. EFFECT-CANONICAL-01:86tests pass,0failures/errors/skips, exit0:
40new boundary-spy tests,12actual loopback/SQLite tests,21proposal,10authority and
3composition tests. Source/tool/command/raw outputs are bound and unchanged.
18/22focused and candidate86counts overlap. The loopback worker permits only its
own ephemeral fixture servers;13binds/23connections,0blocked attempts. This is not
an operationally independent observer. No PostgreSQL service, external provider,
real signing key, production role or deployment was accessed.

The seven existing pytest transaction-control tests were NOT RUN:the existing
LinuxPython3.14 environment lacks pytest and psycopg2. No substitute runner/driver
or dependency acquisition was used. Full independentLinuxPython3.12 and PostgreSQL
qualification, scanners and frozen workflow remain pending. Solidity/Cardano/
workflow source is unchanged by this runtime/doc slice. The earlier791/47native
Solidity suite and size build retain their exact historical full-source identity;
they are not new executions against this documentation/runtime tree.

The new shared guard confines the local helpers to their initial explicit
local/test/demo configuration. It is separate from authenticated action policy.
Constructor arguments may already contain keys supplied by callers; this does not
establish an isolated credential-release broker. Trusted local process API checks
cannot isolate arbitrary code with raw secrets. Production V3 receipt integration,
current-policy enforcement at every protected boundary, durable PG/provider
dedup/fencing/acknowledged cutover and separate completed-effect reconciliation
remain next implementation/qualification work. V1/V2 encodings remain local and
unchanged; schemas are not silently reinterpreted. No finding/track is promoted.
