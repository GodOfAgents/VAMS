# Asymmetric object-provider V3 implementation boundary

Date:2026-10-29. Status:integrated, unactivated;60copied-source local tests pass; authentic/native/live qualification pending.

## Design basis and scope

This implements part of the owner's StageD/F program following GCA_ACCEPTANCE,
the20261027 action/receipt ADR, SIGNER-CONTAINMENT and ADR-VDSO-001. It preserves
Polygon execution/settlement and Cardano governance/identity/insurance roles.
ObjectEffectV3 is an execution-service envelope carrying existing ActionContextV1,
not a replacement for VIR deterministic-CBOR/Keccak consensus encodings. New
object/fence domains use explicit fixed widths and SHA256 without changing old
domains or reinterpreting localV1/V2 MAC receipts as asymmetric signatures.

The protocol authenticates exact authority admission and provider execution
separately. Public authority keys cannot issue an admission; the provider holds
only its own signing handle. Effect evidence rechecks both the original admission
issuer and the provider signer; fencing acknowledgements also authenticate the
original update issuer. Historical evidence has separate APIs and never grants
new current dispatch authority. Stable logical operation identity excludes retry,
policy generation and provider/chain metadata. An altered proposal cannot replace
an existing obligation. Cross-provider migration still requires old-writer fencing
and reconciliation, not just a stable hash or a new key.

The first workload is an immutable object of at most1MiB. Inference and other
capabilities/models reject. SQL parameters are bound; table names are fixed in
public schema. Migration is explicit and fresh/version3/configuration pinned;
partial/unversioned/new-identity schemas reject. No SQLite/driver fallback,
automatic legacy adoption or DBOS schema modification occurs. Metadata version/
checksum consistency does not authenticate schema integrity, administrator trust,
runtime roles, durability or physical provider independence.

## Research mechanism, not evidence substitution

CaMeL enforces capability policies around tool calls; we apply that mechanism as
an inference to current-policy checks at the actual effect boundary. Apiary joins
function execution and operational logging with database transactions; we apply
that mechanism as an inference to cooperating provider write/receipt/dedup/fence
transactions. Their guarantees do not automatically cover VAMS or arbitrary
external providers, model reasoning, native bridge finality or universal alignment.
Sources:https://arxiv.org/abs/2503.18813v2 and https://arxiv.org/abs/2208.13068v2.

## Invariants, custody and privacy

INV1/2/7/8/9 economic/oracle controls are untouched. INV3/4 session lifetime and
whitelist remain unchanged. INV5 OMS fail-closed remains unchanged. INV6 root
identity is carried in the common context, but authentic host/actor authority
remains a qualification dependency. INV10 bridge proof/payload separation is
unchanged; no native bridge verification or ExecuteIntent/Deposit/Slash activation.
No ordinary governor, staking minter/reward, vesting, real fiat/yield activation.

Public keys are explicit constructor inputs, not named custody evidence. All real
issuer/provider/host-policy identities remain UNKNOWN. Raw key isolation/HSM/
signer-broker and independent custody review remain required. Privacy review must
cover actor/resource/operation linkage, content, signed receipts, DB/WAL/backups,
retention, observer access and deletion limits; no public read route is added.


### Asymmetric V3 object-provider candidate — 2026-10-29

A new unregistered V3 provider implementation connects unchanged ActionContextV1
and signed-receiptV3 bytes to the first immutable-object workload. Logical operation
identity is stable across retry/authority/provider/chain metadata; changed proposals
with an existing identity reject rather than being silently re-admitted. Target,
runtime, root, input, resource, integer budget/cost, policy/epoch and fence are bound.
Authority verification is public-only; provider effects/acks/absence use a separate
signer. Both the original issuer and provider signatures are rechecked on evidence.

PostgresEffectDatabaseV3 implements an explicit fresh version3 provider migration,
separate public-schema table names, metadata/checksum/configuration validation,
serializable transactions and no driver/SQLite/legacy fallback. Constructor does
no I/O. Provider code locks the same actor scope for fences and object effects,
checks current admission/policy before and after the lock, and writes unique
operation/admission/nonce, immutable content and signed record in one transaction.
Failed/uncertain commits escape without a receipt or automatic retry. Historical
object/fence-ack lookup is separate from dispatch. Fenced absence needs the exact
retained newer fence/ack and an absent operation, never a timeout inference.

Candidate evidence:60tests pass,0failure/error/skip:17protocol,36provider controlled-
driver and7existing asymmetric-primitive tests.53new tests are INCLUDED. These
use existing local WindowsPython3.12.14/cryptography50.0.2, real ECDSA with synthetic
keys and queued driver rows. They are not native PostgreSQL, independentLinux3.12,
real authority/custody/provider/observer or live proof. Two earlier draft issuer-
binding defects were reproduced as two failing regressions and corrected before
integration. LocalV2 MAC code/primitives/workflow and protocol contracts are unchanged.

The required CurrentActionPolicyV1 dependency is abstract:an authentic current
RestrictedTestnetPolicyV1/host reader is NOT implemented or qualified by this slice.
Test policy subclasses are explicit fixtures. Checking before/after a DB lock does
not establish atomic synchronization with external chain policy changes; authority/
policy generation changes need the full acknowledged provider fencing/cutover.
No live factory/CLI/HTTP/gateway route registers this candidate. It is not canary
admission, a credential broker, full GCA, or an external exactly-once claim.

Next required implementation:authority-side realPG reservations/unique operations,
issuer custody and authenticated host-policy projection, explicit versioned
coordinator/transport and reconciliation, old-writer cutover/absence obligations,
authenticated retrievable checkpoints and final evidence/settlement connection.
RealPG migration/schema/constraint/locking/concurrency/crash/commit-uncertainty and
multi-host tests remain blockers; metadata agreement is not proof of a sound DB
schema or trustworthy operator. Independent exact-byte observation remains.
The Python-only frozen object/fence vector is not cross-language qualification.
No dependency, frozen workflow, live role/key/fund/service/deployment is activated.
13findings remain open;0/36tracks verified; both chains and original A–G stay.


### V3 source integration and copied-source verification — 2026-10-29

EFFECT-V3-INTEGRATION completed10guarded paths,7new. Exact prior source/manifest is
preserved under history/effect-v3-integration01. EFFECT-V3-CANONICAL-CAPTURE checks
the entire integrated tree, exports10exact test inputs and parses Python3.12 syntax.
EFFECT-V3-CANONICAL-COPY-01 then runs the hash-identical exported inputs on existing
WindowsPython3.12.14/cryptography50.0.2:60tests pass,0failure/error/skip.53new tests
are included. No network/process attempt was observed by the worker guard. This
is supplemental copied-source crypto/controlled-driver evidence, not an independent
Linux run, actual PostgreSQL execution, authentic policy/custody or live service.

Retained pre-repair localV2 probe shows an issuer-capable dependency (1failure).
The first probe import error executed no test and is separately preserved. Draft
V3 binding regressions reproduced2failures in50tests; both were repaired before
integration. Candidate48/56/60 and copied-source60counts overlap, not cumulative.
Historical source/tool/command/output identities and initial helper variants remain.

There is no registered production route. Authenticated current host-policy source,
authority PG reservations/unique operations, coordinator/transport, custody/key
isolation, schema/DB-role/TLS/CA review and actual provider identity are unfinished.
Provider transactional semantics are source plus queued-row control tests until
real PostgreSQL demonstrates constraints, locks, migrations, concurrency, crashes
and unknown commits. Policy rechecks do not make remote chain updates atomic with
PG; acknowledged fencing/cutover and real host-policy integration still qualify
that boundary. Old-writer loss remains blocking, never automatic failover.

Historical object/fence-ack lookup authenticates both issuers and exact retained
bytes; it grants no current admission. Fenced absence requires a retained newer
acknowledged fence and no operation. Authority-side absence reconciliation and
earned claims/refunds/payment integration are still pending. Python-only frozen
wire bytes do not establish Rust/Solidity/Aiken conformance for this new envelope.
No existing local MAC/consensus encoding, protocol contract or workflow changes.
Privacy review must cover new provider content/actor/resource/receipt data and
DB/WAL/backups/retention/observer access.13open findings,0/36verified tracks remain.
