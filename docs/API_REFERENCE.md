## 2026-11-05: normal-rotation body-key pair component

`verify_normal_rotation_signature_pair` (Python) and `verifyNormalRotationSignaturePair` (Solidity) require OLD and NEW body-key signatures over the identical canonical base intent and witness. Missing, malformed, swapped, wrong-key and split-witness signatures reject; enrollment and lost-key recovery reject through this normal-only API. Existing one-role APIs, digest domains and encodings remain unchanged.

The isolated M78-plus-payload candidate passed 1,080 Solidity tests across 67 suites (including 17 focused signature methods), the size check, and 16 actual-module Python cryptography methods. Counts overlap and are not added. These are local synthetic-key tests; Python uses the installed Ubuntu 3.14 snapshot with package initialization bypassed, not the independent Python 3.12/full-framework gate. Earlier compiler and unbound-runtime failures remain retained. Combined-source checks follow integration separately.

This component grants no authority and changes no registry or live route. Atomic consent use, current authority/policy readers, challenge/freshness/lifecycle policy, node-scoped gateway/client enforcement, Cardano-native acceptance and full qualification remain pending. The full A-G/both-chain objective, restricted disablements, 13 open findings and 0/36 verified tracks remain: NOT READY. Details: `docs/remediation/repair_20261105/HEARTBEAT-NORMAL-CONSENT-PAIR.md`. Historical text follows unchanged.

## Composer provision error mapping (2026-11-04)

`VAMSResourceComposer.provision()` now maps a `ValueError` raised by the
scorer to the fixed `ComposerError` message `Invalid scoring input or
configuration`. The catch is limited to the scorer call. The existing outer
`ComposerError` handler increments `failed_simulations` once; allocator,
policy-guard, result-construction and cause-chaining behavior are otherwise
unchanged. This is diagnostic boundary handling: it does not change scoring,
allocation policy, transaction values, provider dispatch, or settlement.

The accompanying isolated standard-library fixture has five methods. Against
the M77 composer baseline plus the M77 scorer, models and allocator, BEFORE
recorded five methods, zero assertion failures, two errors, zero skips, native
test exit 1 and evidence-validation exit 0. AFTER recorded five passes with
zero failures, errors, skips or protected I/O. The fixture AST-extracts the
provision method and `ComposerError`; it stubs the runtime policy guard and
instance ID generation. These results are not full Composer imports,
ASGI/framework/provider tests, or live qualification. Counts are not combined
with the separate canonical 18-method campaign.

This documentation records the source change and the preparation-time evidence
identity. Current integration and gate status is recorded by the exact source
manifest and checkpoint; this note does not replace them. The separate source
and test package contains two new paths and awaits integration/evidence
reconciliation. INV-1 through INV-10 enforcement remains unchanged. F11/F14
prerequisites and tracks T07/T22/T24 remain; all A–G work and both chains stay
in scope. There remain 13 open findings and 0 of 36 verified tracks; readiness
remains NOT READY. No deployment, key release, signing, funding, provider or
chain action is authorized by this source change.
## Prepared repair77 — finite scorer configuration (2026-11-04)

The isolated repair rejects negative, NaN/infinite, boolean and nonnumeric
configuration weights. It validates all six fields before summing, safely rejects
oversized integers, and revalidates mutable configuration at every public score
entry, including empty candidate input. Invalid configuration raises ValueError;
valid nonnegative configurations retain the existing 0.001 sum tolerance,
fixed 0.10 requested alignment budgets, ratio-first normalization, subnormal
handling and static zero-base behavior. These are off-chain ranking weights;
integer transaction amounts, registry terms and protocol economics are unchanged.

On identical isolated test modules, the retained source76 scorer produced 31
assertion failures and 13 errors across 18 methods. Its native exit remains 1;
the separate capture validator's zero exit means valid evidence, not a passing
suite. The repaired source passed 18 methods (10 retained requirement methods and
8 validation methods), with zero failures, errors, skips or protected I/O.
Package initializers were bypassed. These results are neither canonical repair77
results nor full pytest/framework/provider/ASGI/live qualification. Counts from
different source campaigns are not added together.

This package is prepared and unintegrated. Source76 remains canonical until the
owner integrates and verifies the complete package. All 18 findings, 13 open
findings and 36 tracks with zero verified remain; full A--G and both chains stay
in scope and readiness remains NOT READY. No invariant enforcement, live role,
restricted-profile disablement or external execution authority changes.

The caller audit found no unsafe allocation/dispatch fallthrough. The separate
ComposerError mapping/failure-counter follow-up is outstanding and is outside
this package. Independent runner, authentic proof, provider/observer, custody,
privacy/security assurance, full gates and real observation evidence remain due.

Historical documentation follows unchanged.

## CandidateScorer requirement weight contract — 2026-11-04

Present nonempty skill/cognitive requirements select fixed 0.10 alignment
budgets regardless of prefilled custom alignment weights. Absent axes receive
zero during dynamic scoring; the four base dimensions retain their proportions.
Proportions are divided by the positive base sum before multiplication, avoiding
overflow for valid tiny finite base weights. Nonpositive base sum rejects.
Static no-requirement behavior and configured objects remain unchanged. Ten
actual-module unit methods pass locally; earlier nine-method R1 evidence remains
separate and is not added to that count. Full pytest/composer/provider qualification
is unrun. Scoring confers no admission, effect, proof or payment authority.

CandidateScorer.score and ScorerWeights signatures are unchanged.

## Legacy Neuron gateway runtime refusal — 2026-11-04

neuron.gateway.server.app reparses strict effective runtime policy on every HTTP
request before request-client access, rate limiting or route dispatch. Missing,
malformed, unknown, live, mock-invalid or startup/runtime-policy drift returns503
with {"detail":"Legacy neuron gateway runtime is unavailable."}. All five direct
handlers independently reject with LiveModeSafetyError before state/request access.
Strict test/local/demo behavior remains non-authoritative; home reads validated
effective policy. Lifespan/start_server live refusals remain. This does not add
authentication, replay, mTLS or live support; the root gateway is separate.
Five real-ASGI regressions/full framework gates remain unrun in this local lane.

## Proposed HeartbeatConsentSignaturesV2 — inactive key-check helper

Python verify_body_key_signature takes keyword-only canonical base_raw,
witness_raw, principal_raw, integer role and raw64 signature. It returns one
body-key signature check. body_key_statement returns the proposed signed bytes.
Solidity verifyBodyKeySignature takes the corresponding calldata parameters;
it rejects input frames above1024bytes and non64byte signatures before copying.
Each decoder and structural binding is checked before full-point ECDSA.

Statement bytes are ASCII VAMS:GATEWAY:HEARTBEAT-CONSENT-SIGNATURE:v2 followed by
NUL, algorithm byte01, role byte01(old) or02(new), then SHA256(canonical witness).
ECDSA applies SHA256 once to that complete statement. Python verify_message
and Solidity RawSecp256k1V1.verifyDigest use the same exact resulting digest;
no Ethereum address recovery, DER/high-S acceptance, or implicit rehash fallback.
This is a proposed statement, not an accepted full wire/profile freeze.

New role binds the complete proposed principal digest, ID, generation and policy
root/version/epoch; old role is available only in normal mode and binds the
exact predecessor digest/ID/generation. Opaque digests retain their full32byte
domain. A consumer must require BOTH normal signatures over identical base and
witness, enforce any distinct-key policy, and verify actual current native facts.
No Boolean here authorizes enrollment, dispatch, credential release or settlement.

The helpers have no clock/current-state/store and cannot authenticate an operation,
ETA, post-ETA challenge,48hgovernance, nonce consumption, issuer, M2-key possession,
certificate or mTLS. A valid signature over fabricated native facts remains only
a key signature. Native reader, fresh versioned registry/policy/runtime helper,
consent store, policy/freshness/revocation and actual route consumers remain due.
Cardano native consent is not represented by this EVM-scheme helper.

## Proposed HeartbeatConsentV2 unsigned data — unactivated

Python HeartbeatConsentBaseIntentV2 and HeartbeatConsentWitnessV2 provide strict
canonical_bytes/from_bytes/digest; Solidity HeartbeatConsentV2 provides bounded
memory/calldata decode, canonical bytes and SHA256digest helpers. The two fixed
purpose domains end in v2 plus NUL, followed by u16BE field count and ordered
u8tag/u16BE-length TLVs. Base18fields/453bytes; witness8fields/190bytes; parser cap
1024bytes. Unknown, duplicated/reordered, wrong-width, trailing, truncated and
unsupported-mode/source frames reject. The scheme is explicitly EVM1, not a
native Cardano enrollment protocol. Existing V1/M2/PayloadV2 bytes do not change.

The base binds source digest, timelock address/code, authority configuration and
change sequence, policy snapshot, principal/record digests, generation CAS,
consent nonce, predecessor/salt and mode. It excludes derived operation ID, ETA,
challenge and signatures. The separate witness binds the base digest, actual
operation ID/ETA, opaque post-ETA challenge, issue/expiry and role set. Normal
rotation selects old+new keys; enrollment/recovery selects new key. Actual lost-
key recovery also requires48hgovernance, which this data codec does not verify.

Opaque32byte digests include zero; absence must be a separate explicit status.
Positive replacement generation distinguishes an existing record even when its
digest is zero. Principal/policy identities and timelock locators keep existing
nonzero rules. UInt64policy values match PrincipalV1; actual uint256policy getters
must be range-checked before conversion. New sequence/nonce widths are proposed
u64 data choices, not existing native-producer guarantees.

matches_base_data/matchesBaseData checks declared data only. It does not identify
the native operation, authenticate a challenge, check policy/current authority,
verify signatures, consume nonces, enforce consent TTL, or authorize any effect.
Timestamp order is not proof that signing occurred after ETA. Native challenge,
timing/grace/withdrawal policy and authoritative readers remain required. Python/
Solidity parity is local evidence; Rust/Aiken conformance and protocol acceptance
remain unrun. Do not use a decoder or structural Boolean as an authorization gate.

## OperationAwareVAMSTimelockControllerV1 — inactive variant

The new constructor forwards minDelay,proposers,executors,admin to the existing
VAMSTimelockController; the48hour floor remains. activeOperationContext() returns
(bool active,bytes32 operationId,bool batch). Idle is(false,zero,false). During
target calls the ID is the inherited hashOperation or hashOperationBatch of the
exact target/value/data/predecessor/salt tuple. Only inherited authorized/open
executors may execute. Any nested execute/executeBatch reverts. Successful
completion clears context; target/parent failure rolls it back atomically.

The getter is public observation, not authorization. A relying registry must
independently require the exact pinned timelock caller, compare the actual active
operation ID to its canonical intent/witness, reject batch when the protocol
requires a single operation, and enforce current policy, authority, CAS, nonce,
consent and challenge. Merely checking that a singleton is ready does not identify
the operation currently invoking the target. A relay cannot replace direct
timelock caller authorization.

This is a new instance type, not an upgrade or automatic drop-in replacement.
The current data-only principal registry pins the original base timelock runtime
and rejects this new subclass. A separately reviewed fresh consent-gated registry/
profile pair, with exact inherited dependency/runtime bindings, remains required.
No existing unsigned record, M2 or PrincipalV1/PayloadV2 wire encoding changes.

## RawSecp256k1V1: digest verification only — 2026-11-03

verifyDigest(bytes32 digest, bytes memory publicKey, bytes memory signature) and
verifyDigestCalldata(bytes32 digest, bytes calldata publicKey, bytes calldata
signature) return a mathematical ECDSA validity Boolean. The calldata entry checks
exact64byte widths before copying. Keys are full affine x||y; signatures are raw
r||s, with0<r<n and0<s<=n/2. Points must be on secp256k1 and coordinates <p;
valid coordinates >=n remain supported. Verification uses full-point Jacobian/
Shamir arithmetic and x(R)modn, retaining x(R)=r+n cases. It uses no Ethereum
address comparison, recovery-id profile, ERC2098 unpacking or P256 native route.

The implementation requires MODEXP0x05: exact probe output and checked scalar/
field inverse identities fail closed on unsupported or incorrect responses.
The SHA256digest must be constructed from the caller's exact canonical protocol
preimage. A valid signature over a caller-selected digest/key does not establish
enrollment consent, policy/epoch, nonce freshness, key custody, certificate/native
state or permission. Never replace a bound protocol check with this primitive's
Boolean. A signature's existence alone is not an issuer or capability grant.

The implementation is a NEW arithmetic adaptation of retained OpenZeppelin
P256.verifySolidity, with secp256k1 parameters and a=0 formulas, not a qualified
P256 implementation relabeled. Independent crypto review, actual target MODEXP/
gas qualification, signed consent protocol and actual relying callers remain.
Public fixtures include mathematical digest tuples with no known message
preimage/private key; they are conformance data, not enrollment/custody evidence.

## GovernedHeartbeatPrincipalRegistryV1: inactive data producer — 2026-11-03

The constructor binds policy, expected VAMS timelock, host/service domains, budget
unit, chain ID and an emergency Safe identity. It checks the exact pinned policy
runtime with its three immutable values, timelock runtime and >=48h delay, and
the supplied emergency proxy/singleton identity plus three-owner/two-threshold
shape. These expected values require a reviewed deployment profile and custody;
constructor checks do not approve caller-supplied identities.

registerPrincipal creates generation1 only in an empty slot with predecessor0/0.
replacePrincipal requires the exact previous digest/generation and next generation
for the same host/service/node commitment. Both accept only bounded canonical
PrincipalV1 data and the current policy root/version/epoch and validity window.
revokePrincipal compares the current predecessor/policy snapshot and stores a
permanent next-generation tombstone, retaining the old canonical record. Every
write and unpause requires the exact timelock and deployment chain. Writes require
unpaused state; unpause checks the expected current policy snapshot. The registry
starts paused. Only the configured emergency address can pause; elapsed time and
Sentinel never resume it. Governance can use scheduled atomic batches for recovery.

principalState returns canonical record, digest, generation, tombstone and active.
Here active is ONLY a structural/policy/time classification. It is not node-key
consent, certificate validity, signer possession, approved authority, finality or
permission to perform a protected effect. No gateway/settlement/client consumer
is wired to this component. Raw records are unsigned; source71 cryptographic
preparation is separate and unqualified. Existing heartbeat/M2 bytes and behavior
remain intact. Cardano requires its own native producer and authenticated reader.

## Heartbeat data contracts: authority source v1 and payload v2 — 2026-11-03

HeartbeatAuthoritySourceV1 encodes seven ordered TLVs after
VAMS:GATEWAY:AUTHORITY-SOURCE:v1\0 and a u16 field count. Widths are
1/32/20/32/20/32/2 bytes: scheme, network context, registry address/code hash,
policy address/code hash and registry schema. Only EVM scheme1/schema1 is
implemented. Network context is SHA256(VAMS:GATEWAY:EVM-NETWORK:v1\0 ||
uint256BE chain ID || genesis hash). Supplied identifiers are data; a reviewed
native reader must authenticate the network/deployment/code/current state and
non-proxy status. Cardano remains required; unsupported schemes reject.

HeartbeatPayloadV2 encodes13ordered TLVs after
VAMS:GATEWAY:HEARTBEAT-PAYLOAD:v2\0 and u16count. Fields bind authority-source
digest, exact principal digest, principal ID/generation, policy root/version,
authority epoch, node ID, body public key, M2 nonce/issued/expiry and observations.
payload_text is VAMS-HB2: plus strict lowercase hex. digest hashes that exact
ASCII text; canonical_binary_digest hashes the distinct binary frame. Payload
and observation bounds are8192/4096bytes before parsing. M2 timestamps use eight-byte unsigned big-endian wire values restricted to
exact integers in [0,2^63-1], preserving the actual outer M2v1 validator. Timestamp
lifetime is positive and <=300seconds; this is not a current-time check.

HeartbeatObservationsV1 requires u64block height, optional bounded UTF8 text,
integer credit score, tagged i64/finitef64 cost/profile observations, <=32skills
and <=64strictly byte-ordered unique profile keys. Booleans/NaN/infinity and
coercion reject; finite negative zero preserves its exact IEEE754 bits. Integer
zero, positive floating zero and negative floating zero have distinct frame
digests. These floats are telemetry, not settlement token amounts. Opaque source
and principal digests accept every bytes32 value; policy root/principal ID and
other identity fields enforce their documented nonzero constraints.

matches_record_data checks structural equality to a supplied PrincipalV1 plus
the expected source/M2 tuple. It does not resolve/authenticate that record,
consume replay state, verify signatures, establish finalized freshness, choose
a migration cutover, authorize a route or mutate nodes. Existing M2 v1 and
heartbeat handler behavior remain unchanged. No legacy fallback is enabled by
these APIs. The617byte PrincipalV1 reference and existing encodings are retained.

## Gateway NodeInfo presentation — 2026-11-03

NodeInfo.last_seen_formatted is a computed property using the existing local
datetime %H:%M:%S format. NodeInfo.to_dict() retains its existing key and value;
the property is not a new stored dataclass field. The HTML dashboard now renders
real populated rows and escapes node_id/network/uptime/formatted-time text in
both online/offline branches. Signed or certificate-authenticated node text is
still untrusted HTML. Numeric grouping, defaults and row order are unchanged.

GET / retains its existing M2-protected route and middleware. The change adds no
issuer, node enrollment, source reader, replay protocol, role or signing format.
Eight extracted actual NodeInfo/dashboard checks pass on local Windows312 and
Linux314 with clock/HTMLResponse fixtures. Two new full-ASGI regressions test
signed heartbeat registration followed by dashboard rendering; they are NOT RUN
in this environment. Full framework/ingress/privacy/operational gates remain.

## RestrictedPolicyRuntimeV1 code identity — 2026-11-03

The internal Solidity helper expectedCodeHash(governance,hostDomain,budgetUnit)
patches all14immutable-reference words in the exact9982-byte runtime captured
from RestrictedTestnetPolicyV1. It returns zero for a missing expected binding.
matches(policy,governance,hostDomain,budgetUnit) compares exact code length and
extcodehash with that template and makes no policy getter calls. There is no
caller-supplied expected hash and no mutable template or binding setter.

The template is pinned to solc0.8.24+commit.e11b9ed9, optimizer200/non-viaIR,
Cancun/IPFS metadata and exact18transitive source inputs. Its SHA256 is
bd317c3c7a648b079daf6a62b83aaffab14f454ddb1014cd14228925e0148b1d.
This SHA256 binds compiler bytes; extcodehash uses Keccak256 of patched code.
Source/tool/artifact constants are provenance labels, not executed provenance
validation. A changed compiler, policy, metadata or binding fails exact matching
and needs reviewed regeneration/requalification, never automatic acceptance.

Expected addresses/domains/budget unit remain caller-supplied trust inputs. Code
identity does not approve them, authenticate governance custody, prove current
storage/finality, grant roles, or verify node possession. A registry must validate
the exact timelock and approved bindings separately before using policy getters.
Actual deployment/configuration/custody remain UNKNOWN. The helper is inactive,
unwired and EVM-specific; Cardano native authority/reader remains required.

## HeartbeatPrincipalV1 Solidity data API — 2026-11-03

contracts/src/trust/HeartbeatPrincipalV1.sol exposes internal pure Record,
valid(), canonicalBytes(), digest(), tryDecode(), tryDecodeCalldata() and
principalIdFor(). The Record carries the same 18 fields and exact domain/ordered
ID/u16be framing as gateway.heartbeat_principal_v1. Five integer fields are
uint64 and encode to exactly eight big-endian bytes. Only POST /heartbeat and
empty query are representable. The M2 DID must encode the exact 64-byte key in
lowercase hex; key shape does not prove a curve point or possession. There are
no external calls, state writes, issuer checks, current-policy reads or roles.

External raw-byte ingress must call tryDecodeCalldata or check the 1024-byte
bound before a memory copy. The memory helper cannot undo caller allocation.
Both reject invalid bytes with false and a zero record; canonical typed encoding
rejects invalid fields. Exact widths, ordered IDs and unchanged bytes make the
accepted frame canonical; tests compare re-encoding to the original preimage.
Each field is bounded by 256 bytes; accepted audience varies from 1 to 128 ASCII
bytes. The fixture's 617 bytes are one example, not a fixed record length.
Independent Python references cover lengths603/617/730 and matching SHA-256.

principalIdFor hashes the principal-ID domain/NUL and exact host/service/node
commitments. It only constructs data, including for zero inputs; valid() rejects
missing identities. Raw node-ID UTF-8 derivation is intentionally absent here.
Use the separately specified Python exact-byte commitment until an equivalent
native implementation is reviewed. No normalization or anonymous identity is
implied. A matching digest, interval or key tuple grants no enrollment rights.

The library is not connected to a registry, gateway handler, provider, client or
deployment. An authenticated current authority source, governance/custody, stale
epoch and revocation checks, node route scope and native BOTH-chain evidence are
still required. Never use these pure functions as an authorization decision.

## HeartbeatPrincipalV1 unsigned data — 2026-11-03

gateway.heartbeat_principal_v1 defines unsigned immutable data, canonical_bytes(),
digest, from_bytes(), interval_contains() and matches_request_binding(). None of
these authenticates an issuer, checks current governance/revocation, enrolls a
node, grants a role, or authorizes a request. The gateway does not consult this
new record yet. Shape-valid keys are not ownership or elliptic-curve proofs.

The domain is VAMS:GATEWAY:HEARTBEAT-PRINCIPAL:v1 followed by NUL. Encoding uses
u16be field count18, then ordered u8 ID/u16be length/value. Fields1--18 are:
principal_id,node_id_commitment,m2_signer_did,m2_signer_public_key,
certificate_fingerprint,body_public_key,host_domain,service_domain,audience,
method,path,query,policy_root,policy_version,authority_epoch,principal_generation,
not_before,expires_at. Integer fields use exact u64be; positive generations/
versions and half-open validity are required. No implicit truncation is allowed.
Bytes32 identities are nonzero; keys are64bytes, fingerprint32bytes. DID and
audience follow existing M2 v1 syntax. Only POST /heartbeat with empty query is
representable. Fields are bounded256bytes and total encoding1024bytes. Strict
decoding rejects truncation, extra/alternative fields, widths and trailing bytes.

node_id_commitment hashes NODE_ID_DOMAIN || host32 || service32 || u16be UTF8
length || exact UTF8, using VAMS:GATEWAY:NODE-ID:v1 plus NUL. Node IDs are1--256
UTF8bytes without ASCII controls; no trim, case or Unicode normalization occurs.
principal_id hashes PRINCIPAL_ID_DOMAIN || host32 || service32 || nodeCommit32,
using VAMS:GATEWAY:HEARTBEAT-PRINCIPAL-ID:v1 plus NUL. It identifies a node slot,
not a person: credential/policy rotation preserves the ID. Reassignment requires
governed generation advance and revocation/supersession of old records. Host or
service changes change the ID. Hashes remain guessable/linkable and are not
anonymous; public registry/privacy acceptance is still required.

The synthetic617byte vector has SHA256
bd695fde4585901bcbc2870cb07d2e0bafd597643d06556905f891129c097a3c.
It is a format vector, not a credential, enrollment or native authority proof.
Unsigned time/tuple checks must never replace an authenticated current registry
read and role decision. Issuer custody, registry deployment/finality, M2/mTLS
integration and actual node authorization remain UNKNOWN or unimplemented.

## Root heartbeat body-key requirement — 2026-11-03

POST /heartbeat requires a non-empty string public key selected from the cached
node key, or from the first-contact payload when no cached key exists. The body
signature must verify over the exact UTF8 payload bytes before insertion or any
counter, block or timestamp update. Empty/non-string keys and failed verification
return HTTP403 Invalid heartbeat signature. Missing first-contact key retains
its existing HTTP403 behavior. Cached keys retain priority over supplied keys.
Public-key/raw-signature formats and outer M2/replay/client-certificate checks
remain unchanged; an outer administrator signature cannot replace the node's
body signature. A first-contact key is still self-asserted, not enrollment proof.

Node state is process-local; an ok response is not a durable admission receipt.
The M2 administrator, certificate identity, node key and node_id are still not
joined by an approved scoped-principal registry. Ordinary nodes must not receive
administrator credentials. A distinct authenticated client and least-privilege
authority/enrollment design remain open; no fallback to legacy routes is added.

## PhalaTEE diagnostic accessor denial — 2026-11-03

verify_sgx_quote/verify_nitro_quote preserve _PhalaRuntimeDriftError raised while
reading response.headers/items or response.raw/read. The acquired response still
receives one close attempt before the denial propagates, including if cleanup
throws a control exception after restoring the environment. verify_multi_tee
therefore aborts before dispatching a later diagnostic provider. Ordinary accessor
exceptions still return the fixed provider_error classification with invalid,
non-authoritative reports. Existing byte/read limits, credentials, report fields,
root/session distinctions, quote/quorum encodings and authentic-verifier absence
are unchanged. This does not establish normal Requests accessor behavior, a
deployed consumer, atomic process fencing or authentic proof/effect authority.

## Legacy GatewayClient runtime contract — 2026-11-03

GatewayClient(base_url, runtime_policy=None, environ=None) derives authority from
actual os.environ. Supplied typed RuntimePolicy/complete mapping values must
match that policy. Missing/malformed actual mode or registered flags reject;
caller inputs cannot repair or replace them. Policy errors use fixed sanitized
text and suppress caught diagnostics. Actual policy is rechecked after URL
preparation immediately before Requests session construction.

This client implements the legacy /agents/register, /agents/{id}/deregister,
/heartbeat and /tasks routes. The legacy server already refuses staging/testnet/
production; this client now rejects these modes before session construction,
including valid HTTPS URLs. It does not implement the root gateway's M2 request
envelope, durable replay or applicable mTLS contract. That authenticated client
remains required work; no legacy request or simple payload signature substitutes.

All five operations recheck actual policy at entry and immediately before their
transport call, after local URL/body preparation, then after response/status/JSON
callbacks before acknowledgment or state adoption. Private runtime denials escape
generic offline/empty-result catches. Unchanged non-live failures and wire shapes
remain supported. base_url/runtime_policy remain immutable. Pure URL validation
uses the bound snapshot; operational dispatch requires fresh policy separately.
Checks do not atomically fence concurrent mutation or roll back a request already
started. Session serialization, native transport/body/resource bounds and actual
M2/server acceptance remain separate qualification requirements.

## VamsNeuron lifecycle and identity failure behavior — 2026-11-03

load_or_generate_identity(), _generate_new_identity(), sign_telemetry(),
send_heartbeat(), run_workflow_demo() and run() revalidate actual os.environ
against the instance's frozen policy and effective mock selection at their
entry and defined stage boundaries. Missing/malformed/changed runtime selection
and all live modes reject with a private fixed-message RuntimeError subtype.
The private denial propagates through broad catches and resource cleanup; it is
not converted to a successful fallback, heartbeat retry or workflow continuation.
These checks do not provide atomic protection against concurrent environment
mutation or replace provider-side authorization/fencing. Shutdown remains usable.

Only FileNotFoundError from opening the exact identity path can start first-time
generation, and only while the instance has no existing identity. Read, decode,
permission and parse failures reject without opening that path for overwrite.
Creation uses exclusive xb with an owner-only POSIX mode request of 0600; a
concurrent creator wins without overwrite or speculative unlink. Generated key
adoption follows successful write/flush/close and policy validation. Failed or
partial files remain fail-closed and need explicit operator recovery; there is
no crash-atomic persistence, fsync, Windows ACL or custody qualification claim.
The secp256k1/SEC1 PEM and heartbeat payload/signature encodings remain unchanged.

The direct legacy GatewayClient has a separate policy-binding/dispatch gap under
active repair. Node method checks do not qualify that client, its server auth,
native DBOS/SQLAlchemy/SQLite behavior or real protected effects.

## VamsNeuron constructor runtime assertions — 2026-11-03

VamsNeuron(..., environ=None, policy=None) reads actual process os.environ first.
Missing/malformed VAMS_ENV or registered mock flags reject before initialization.
A supplied policy must be a RuntimePolicy instance equal to actual policy. A
supplied environ must be a complete valid runtime-policy assertion with matching
mode and effective registered flags; partial configuration-only maps reject.
The map remains available for ordinary configuration after its assertion passes.
Runtime selection never comes from credentials, caller maps or policy objects.

mock_mode=None retains ambient selection; explicit selections must be booleans
and satisfy both actual and supplied-map NEURON_MOCK_MODE conflict rules. Explicit
local mock selection without a flag remains supported. All actual live modes
(staging/testnet/production) still reject before storage/provider initialization.
Policy and effective mock selection are checked again immediately before
NeuronStorage, including conflicts caused by prefix callbacks. Effective fields
remain immutable. This is a startup snapshot check, not atomic environment fencing
or proof that every later method, child provider or protected effect is qualified.

## Legacy TrustProvider response budget — 2026-11-03

The three legacy get_status calls use stream=True and allow_redirects=False;
redirect responses are degraded without a follow-up request. Phala/Marlin read
status only. Automata's HTTP200 chain-ID observation requires absent or exactly
identity Content-Encoding, raw reads with decode_content=False, at most65,536
body bytes and8,192bytes per read request. Exact EOF is required even at the cap;
Content-Length does not affect the budget. Strict UTF-8 JSON retains the existing
JSON-RPC2.0/exact integerid1/hex-result checks. Other JSON parsing semantics stay.
The identity/UTF-8/body limit is a diagnostic compatibility restriction, not a
provider format maximum. No .json/.content/.text/iterator fallback is used.

Read, encoding, parse, status, clock or cleanup failures return fixed offline/
provider_error with observations=None. Runtime drift and control exceptions retain
their existing cleanup/propagation behavior; chain ID is adopted only after close
and final policy validation succeed. Every acquired response gets one close attempt.
latency_ms retains request-through-status/JSON time, excluding close. Header/DNS/
socket/internal buffering, total heap, CPU and deadlines remain unqualified, as do
real HTTP packages, endpoint identity, hardware and authentic evidence. Caller-owned
session credentials/cookies/proxies remain untouched; no isolation claim is added.

## Legacy Layer-4 trust diagnostics — 2026-11-03

TrustManager(mock_mode=False), create_trust_manager and standalone providers require
a valid actual process VAMS_ENV. Explicit mock_mode must be an exact boolean and
agree with NEURON_MOCK_MODE when that registered flag is present. Missing/malformed
mode, live mock use and policy drift reject; effective policy/mock references are
immutable. No caller-supplied mode or policy override is accepted by this API.

check_all_status() and list_providers() are diagnostic APIs. Trailing defaulted
TrustInfo fields simulated, verification_scope, evidence_classification and
observations preserve original positional construction. to_dict/list output always
sets usable_as_live_evidence=false. Local fixture health remains simulated;
website/RPC responses are non-authoritative observations without capacity claims.
Automata's chain ID is a provider observation, not authenticated chain identity.
The manager normalizes provider metadata and only adopts a complete checked pass.
get_healthy_providers() retains its signature but returns [] until actual provider
qualification exists. It must not be used to admit work from HTTP reachability.

PhalaProvider.generate_proof() and the base compatibility method raise
LiveModeSafetyError("authentic_verifier_unavailable") without quote fields or
transport. Use of the separate TEEProofPlugin local fixture remains non-authoritative.
This repair does not bound the legacy diagnostic response body or qualify real
Requests, provider/hardware/verifier identity, root/workload binding or effects.

## HTTP-only health observations — 2026-11-03

PhalaTEE.check_health, MarlinOyster.check_health and AutomataMultiProver.check_health
request stream=True/allow_redirects=False and inspect no response body. They attempt
close once only when a response was acquired, before returning. Close/status/request
failures return fixed offline/provider_error; local cancellation propagates after cleanup.
Phala's fresh-runtime checks/private drift precedence remain.

Every result adds verification_scope="http_reachability" and
evidence_classification="non-authoritative". Legacy status/provider/latency/error/target
technology keys remain. Only exact integer HTTP statuses100--599 are formatted.
Phala/Marlin2xx is healthy, other valid statuses degraded; Automata only200 is healthy.
Redirect-dependent endpoints may change to degraded. latency_ms now measures monotonic
request-to-status time, excluding body/cleanup; URLs/payloads/timeouts are unchanged.

The Neuron SDK panel identifies unverified endpoint observations and HTTP-only TEE target
reachability; missing/mismatched provenance is displayed as unknown. Raw exceptions are
not formatted in its Celestia or TEE handlers. These observations do not certify TEE,
verifier, JSON-RPC, capacity, chain correctness or qualified availability.

Caller session auth/cookies/proxies are not inspected or stripped. Their isolation,
native HTTP behavior/header/time/memory bounds, endpoint custody/privacy and authentic
proof/provider qualification remain open. Source56 body limits and all prior root/trust/
credential/profile restrictions remain. Full vendor/native tests and both-chain evidence
are still required; NOT READY.

## SGX/Nitro diagnostic body limits — 2026-11-02

verify_sgx_quote and verify_nitro_quote use streamed, identity-only responses and refuse
redirects. The local accepted JSON-body limit is65,536raw octets after transfer framing;
raw.read requests are at most8,192bytes and explicitly disable content decoding. An
exact-limit body needs EOF; one byte over the limit rejects. Content-Length does not
authorize acceptance, allocation or rejection. The client does not fall back to unbounded
Response.json/content/text/iter_content. Unsupported compressed/malformed encoding rejects
before reading; strict UTF-8/JSON and the existing claim-shape checks still apply.

New fixed errors: provider_response_too_large and unsupported_content_encoding. Existing
provider_status/malformed_response/provider_unavailable/provider_error remain bounded.
Missing/incompatible raw readers or close failures fail closed. Cleanup is attempted
once for each acquired response; runtime is revalidated after that attempt before result
adoption. Local control/cancellation propagates after cleanup instead of becoming an
ordinary provider error; private runtime drift takes precedence over cleanup failures.
A failed close does not establish connection release. No provider body or ordinary
provider exception detail enters error results.

Returned reports remain non-authoritative and unusable as live evidence. Phala bearer
scope stays request-local; Nitro receives no SDK key. Synthetic header/stream tests do
not qualify real HTTP. These local body limits do not set quote-input, business-output,
metadata/health, header, deadline, CPU or full-memory limits. Authentic provider/verifier/
workload and full vendor/native qualification remain required; both chains stay NOT READY.

## Phala request-local authorization — 2026-11-02

The SDK's `phat_api_key`/`PHALA_API_KEY` is no longer a shared-session default.
Only `verify_sgx_quote` and a permitted non-live `call_phat_contract` attach it in
request-local headers to the configured Phala URL. Both POSTs set
`allow_redirects=False`;3xx responses fail instead of being followed. Nitro/Marlin,
public metadata and health requests do not receive this SDK-owned header. This
preserves non-secret content negotiation and separate keys across new clients
sharing one transport. Caller-owned default headers remain the caller's responsibility.

This is a credential-routing correction, not endpoint/credential-custody assurance.
Use fresh clients/transports after an update; existing objects are not scrubbed.
Real HTTP redirects, custom transport/default auth/cookies/proxies/netrc, provider
identity/privacy and full vendor/native tests remain unqualified. Live direct action
dispatch is still unavailable, provider JSON is still non-authoritative and API keys
still create no action authority. Existing source54 interfaces/restrictions remain.

## Legacy TEE compatibility interfaces — 2026-11-02

`PhalaTEE` and `TEEProofPlugin` bind actual process mode/mock policy; `runtime_policy`,
`environ` and `mock_mode` arguments are compatibility assertions, not authority.
A supplied `environ` map is deliberately a complete policy assertion: it must
state valid `VAMS_ENV` and represent the same enabled registered mock flags as
the process. Partial endpoint-only maps reject; use typed endpoint arguments or
omit the map to use actual environment configuration. This tightens the legacy
constructor contract. Set actual `VAMS_ENV` and `PHALA_MOCK_MODE` explicitly for local fixtures. Conflicting
or missing security configuration rejects before session construction. Effective
mode/mock references cannot be reassigned; ambient drift raises a bounded error.

`call_phat_contract` rejects live and mock use; `execute_python_in_enclave` rejects
live use before serialization. Local script fixtures remain simulated; non-live
real transport is unqualified. Neither API promises enclave confidentiality.
No replacement authentic live dispatch interface is supplied by this containment.

`AttestationReport.provider_claim_valid: Optional[bool]` is a trailing optional field
also present in `to_dict`. It records only a parsed provider claim. RPC-derived
`is_valid` is false and classification non-authoritative; malformed binding data
does not create a claim. Legacy `usable_as_live_evidence` always returns false.
Non-mock plugin generation returns invalid/empty evidence with
`reason=authentic_verifier_unavailable`, `root_binding=unverified`; verification
returns false before decoding. The local simulated wire layout/type ID are preserved.
`verify_multi_tee(required=2)` accepts only exact integer2; booleans, floats and other
thresholds reject before inspecting quotes. Its local quorum is not live authority.

Authentic qualified verifier/action/provider/workload integration, full vendor/ABI/
native tests and independent evidence remain required. NOT READY for either chain.

## Explicit Bittensor wallet setup — 2026-11-02

With the vendor SDK available, `BittensorSubnet(wallet_name=..., wallet_hotkey=...)`
rejects live named-wallet setup with LiveModeSafetyError before Subtensor or wallet
factory access. Missing/invalid runtime mode raises the central configuration error.
The constructor-bound selection and current mode/mock configuration are rechecked
before wallet creation and before returned-object adoption; drift raises a bounded
RuntimeConfigurationError subtype during setup. Assigning public selector fields
does not reconfigure the selected identity; construct another client instead.
Health output uses the bound name only when a wallet reference exists, otherwise
none; mutable public labels cannot claim that a new wallet was adopted.

No-wallet read-only setup and harmless unavailable-SDK construction remain; a
callback cannot inject a wallet into a constructor bound to no selection. Controlled
test/local/demo wallet setup retains its parameters. Existing wallet references
are not revoked by this change. Public provider safety errors remain bounded
connection failures. Prior locally permitted construction cannot be undone by a
later adoption check, and these process reads are not an atomic external fence.

The source52 unbound live-inference rejection remains unchanged. Wallet construction
is not action authority or custody proof; actual vendor key-read timing, authentic
admission/provider/workload/proof/receipt/recovery/settlement remain unqualified.

## Unbound Bittensor inference compatibility entrypoint — 2026-11-02

`BittensorSubnet.query_miner()` retains its signature but rejects staging/testnet/
production at entry with LiveModeSafetyError until authenticated action-bound
admission and a qualified inference backend exist. Missing/invalid runtime modes
raise the central configuration error. Rejection precedes prompt, credential,
provider and transport access; caller ALLOW metadata cannot enable the route.
This supersedes the earlier retained-live-dispatch description. Read-only connected
subnet/miner/health observations remain available and unverified.

Controlled test/local/demo inference retains response and bounded failure results.
Runtime mode/mock configuration is rechecked before transport construction, prompt
release and query dispatch. Drift raises a bounded RuntimeConfigurationError subtype
instead of authorizing the next stage. Provider-origin public safety errors remain
ordinary bounded failed results. These checks are not governed-policy/epoch approval
or authentic effect/proof receipts, and cannot undo a prior locally allowed stage.

The full inference Service Block still requires the fixed workload, actual policy/
actor/provider bindings, verified evidence, durable admission/effect/reconciliation
and settlement. Unbound rejection is containment, not a qualified replacement.

## Local Sentinel selected-account address — 2026-11-02

`HardwareRegistryClient.account_address` is a read-only optional address from the
explicitly selected account. It is None when no account was parsed/configured; it
does not return Web3's default account and provides no custody or identity proof.
`VAMSSentinelNode` with supplied signing material requires a nonzero20byte hexadecimal
address from that property, or raises a bounded RuntimeConfigurationError before
DA/challenge construction. Without supplied material, the local zero placeholder is
preserved without reading the property. Live construction still fails before SDK
initialization, and SLA submission remains unavailable. A report's sentinelId is
local attribution, not a signature, proof, authorization or payment claim.

## Provider observations, local fixtures and bounded diagnostics — 2026-11-02

`BittensorSubnet` subnet/miner fallback producers and `HardwareRegistryClient`'s
offline catalogue are local/test/demo-only. Central runtime policy rejects live
or invalid modes before producing fixtures, including after an upstream read error.
Successful connected reads remain available as unverified provider observations.
SubnetInfo, MinerInfo, InferenceResult and HardwareClassInfo preserve existing
positional fields and add defaulted simulated/evidence_classification fields.
Fixture records and hardware summaries expose simulation/non-authoritative labels;
connected records and summaries say provider-observation, without proof assurance.

Offline hardware class IDs use Solidity-compatible Keccak via the existing helper,
and collateral base units use exact integers. No SHA3-256 compatibility assumption
or transaction amount constructed from the display floats is supported. Actual
eth_utils, Web3 ABI, registered contract/code identity and chain state qualification
remain required; fixed-vector local test doubles do not provide that evidence.

`check_health()` reports a block-read exception as degraded; `get_block_number()`
retains zero on failure for compatibility. Neuron's SDK health panel asks for subnet
counts only after healthy status and labels their provenance. Failure diagnostics
use fixed text instead of arbitrary provider errors. `collect_plugin_proofs()`
continues other plugins after a failure without formatting that exception or making
another failed-plugin callback. Successful proof data and metadata are unchanged;
collection does not authenticate evidence or submit a transaction.

Connected inference dispatch is preserved, but production admission, policy and
effect/settlement receipts remain unqualified and cannot be inferred from the new
observation fields. These local repairs supply no provider, key, role, signing,
deployment authority or privacy approval.

## Local research fixtures and trust submission — 2026-11-02

`ParallelWebClient.search()` and `generate_proof_of_research()` are simulation-only.
They reject live and invalid runtime modes before input inspection, logging, delay
or serialization. `TrustAggregatorClient.collect_available_proofs()` is likewise
non-live-only. `collect_plugin_proofs()` retains its separate plugin interface;
collecting a result does not authenticate it or submit a transaction.

`ParallelResult` preserves its original six positional fields and adds defaulted
simulated/evidence_classification/confidence_classification fields. The fixed0.98
score is fixture-only. The local byte envelope uses schema
`vams.parallel-research-simulation.v1`, simulated=true, non-authoritative evidence,
fixture-only confidence, result_count, fixture_digest, provider=local_parallel_fixture
and created_at. It is a new local format, not a signed proof, receipt or Merkle proof;
old unversioned fixture JSON is not automatically adopted or reinterpreted.

`submit_bundle()` and `submit_plugin_bundle()` raise `LiveModeSafetyError` instead
of returning a successful no-op or printing completion. Existing ZKML/simulated-TEE
denials remain; every otherwise accepted-shape bundle is still unavailable because
authenticated action/actor-root-bound submission and finality receipts are absent.
No bundle can cause these methods to sign or broadcast. A caller must handle that
failure; no fallback submission route is supplied. Out-of-tree callers may need
to adapt to this corrected failure behavior.

The collection client no longer loads VAMS_PRIVATE_KEY/SignerFactory from ambient
configuration; private_key, signer and account remain None. Web3/provider setup and
plugin discovery remain separate and are not qualified by local vendor fixtures.
An approved typed submission implementation, public chain/contract/finality and
custody bindings remain required. No keys or deployment authority are requested.

## Failure detail and durable revocation — 2026-11-02

`InterruptResult.error` remains present. A raised outer interrupt handler now
returns `interrupt_handler_failed`. Exhausted X402 retries preserve the existing
`All attempts exhausted` prefix but replace untrusted internal exception or
failed-provider detail with fixed text. The existing local expiry and HTLC
preimage-dispute messages remain; successful result/proof/metadata are unchanged.
Callers must not depend on arbitrary provider exception strings. This is a local
error-boundary repair, not live escrow support or a privacy approval.

Durable gateway revocation/expiry checks retain persisted monotonic time across
tolerated wall-clock rollback and restart. A previously effective revocation
stays effective; excessive rollback or malformed storage time fails closed.
Authentication bytes, nonce namespace, scheduled revocation and HTTP outcome
mapping remain unchanged. There is no new public revocation-management route or
operator appointment. Host-local SQLite remains a single-host boundary.

## Current engineering source integration — 2026-11-02

Integrated engineering component: inactive and unqualified; NOT READY.
The integration journal and current source manifest identify this exact source
and the post-integration combined checks. No live factory, route registration,
database migration, chain deployment, role grant, funding or operator approval is
created by source integration. V5 runtime constructors continue to reject live
mode, and existing local V3/V4 protocols and deployed instances are untouched.

Component evidence:930local Solidity tests/58suites and85supplemental Windows312
signature/catalog/transaction-double checks; earlier927/69 are INCLUDED, not added.
Native retry policy version/root floors, bounded256attempt lifecycle and indexed
closure/budget projection are repaired locally. Fresh immutable settlement/verifier
instances together are required for the extended internal/getter ABI; signed V3
wire and logical-work/attempt domains are unchanged. No old-state adoption.

Authentic current-host/native funding-finality, native-gated same-ID successors/
renewal, paid coordinator AND direct-provider effects, actual PG18/query plans/
roles/concurrency/restart/WAL, proof/provider/DA/custody/privacy/human assurance,
both-chain rehearsals and actual observation days remain unresolved. Local terminal
states are not native financial resolution. All A--G scope for Polygon Amoy AND
Cardano Pre-Prod is retained,13findings open/0of36verified; no stage promotion.
Historical entries below retain their original source/time and pre-integration
labels. Current source integration supersedes those old integration labels only.

## 2026-11-02 - Preserve acknowledged policy across native object retries

The native candidate now persists the policy version/root acknowledged during
fenced absence. A same-operation retry must preserve that floor: no lower version,
and no changed root at an equal version. Current governed policy, actor consent,
strict epoch/fence advance and immutable logical work still independently apply.
AdmissionFacts carries the exact proposal policy fields from the stateless verifier.
This matches the retained Python successor rule; an issuer cannot drop an
acknowledged future policy merely because on-chain epoch advanced independently.

Two actual-policy VM regressions fail before repair by accepting incompatible
retries. The repaired full campaign passes930tests/58suites,0fail/skip (prior927
INCLUDED); a positive equal-version/same-root retry passes. Offline sizes PASS:
ComposedSettlement23689bytes,ActionDeliveryVerifierV118126bytes under unchanged
24576EIP-170limit. Exact commands/source/tool bindings and raw outputs:
LATE-44-RETRY-POLICY-BEFORE-01.json,LATE-44-FULL-05.json,LATE-44-SIZES-08.json.
Non-author source/result review accepts this named local defect repair only.

ObjectOperationV3 getter and internal AdmissionFacts return layouts are extended.
Deploy a fresh immutable settlement/verifier pair together with newly bound code/
ABI identities; no old-state upgrade/adoption or existing deployed ABI compatibility
is claimed. Signed V3 receipt bytes/domains, native attempt/logical-work digests,
integer registry fees, original actor/payee, backing and terminal semantics remain.
No new native funding/finality, physical storage truth, provider custody or live
authorization follows. The85local Python lifecycle checks retain their unchanged
R9 source scope. Current source remains unintegrated and NOT READY; all A--G scope
for Polygon Amoy AND Cardano Pre-Prod is retained,13open findings/0of36verified.
Earlier entries below retain original source/time scopes and historical counts.

## 2026-11-02 - Local authority5 lifecycle candidate

Source45/R9 now implements fresh scope installation, exact provider-acknowledged
activation, policy revalidation, cutover/refresh, acknowledged revocation and
same-host renewal. Each closure authenticates every bounded current-generation
attempt history and its exact cumulative budget projection. Renewal preserves
spent budget and all prior work/attempt/event/completion records.

The source supports at most256attempts per generation, including zero-cost work;
later generations retain the logical-work mission and cumulative spend. The new
required UNIQUE(scope_id,generation_id,operation_id,attempt_id) index supplies the
capacity-query prefix and closure ordering. Exact catalog enforcement and revised
MIGRATION5 bind that access path and the limit. Eight table/column sets and signed
V3 receipt bytes remain unchanged. Existing candidate manifests are not adopted.
Actual PG18 schema/role/query-plan/contention/performance/restart/WAL qualification
and independently compiled CHECK provenance remain UNKNOWN/unqualified.

85supplemental local Windows312 signature/catalog/transaction-double tests PASS,
0fail/error/skip and0network/process events (prior69 INCLUDED). Exact source,
commands, failed iterations, raw streams and snapshots: FUNDED-ATTEMPTS-45-19.json
and LIFECYCLE-SOURCE-REVIEW-45-R9.json in the retained implementation workspace.
Independent source review accepts local preparation only. Solidity bytes remain
those of the927-test/58-suite VM candidate; no new native test count is inferred.

Local revoked/absent/completed states do NOT establish native funding or financial
resolution. Native-funding-gated renewal/same-ID successor admission, actual paid
coordinator AND every direct-provider effect route, authentic current host policy,
native finality, migrations and settlement remain unfinished/unqualified. These
classes cannot run in live mode. No production effects, payment/refund, scope
custody, dual-chain operations or real observation days are established here.
Full A--G scope for Polygon Amoy AND Cardano Pre-Prod is retained; NOT READY,
unintegrated,13open findings and0of36verified. No R28/Slot08/Aiken/acquisition/
service/signing/funding/deployment authority changes. Earlier entries below keep
their original source/time evidence scope; R7 lifecycle-pending descriptions are
superseded by this local component, without clearing their native/backend gaps.

Internal unactivated `PostgresScopeAuthorityV5` adds `prepare_scope`,
`activate_scope`, `begin_revocation`, `refresh_unacknowledged_cutover`,
`record_fence_ack`, `complete_revocation`, `prepare_renewal` and `read_scope`.
The CurrentRenewalPolicyV1 callback receives the complete previous ScopeStateV5
including cumulative spent budget and the retained acknowledgement (`ack`).
An existing signature is returned only after transaction context exit; unknown
commit/close returns no credential and never retries. These are local protocol
primitives, not native funding authorization or new public HTTP endpoints.

## Unactivated object reservation and storage5 source interfaces

`admitObjectV3`, `resolveObjectCompletionV3`, `resolveObjectAbsenceV3` and
`refundAbsentObjectV3` bind exact typed original bytes and native row commitments.
Admission actor and caller equal the funder, and providerId is the row's EVM payee.
Cost units are separate from exact token units. Each new attempt stores the stable
logical work and previous attempt; prior rows remain retrievable. Expiry/outage
does not release admitted funds. Anyone can relay completion; only the original
provider claims payment. Absence requires authority update, provider acknowledgement
and purpose5receipt, strict epoch/fence advance and policy continuity. Only the
funder refunds principal. Pause permits reconciliation, blocks new admission/payment.
ABI invocation bound8192bytes; signed V3 domains/bytes remain unchanged.

`PostgresInitialAttemptAuthorityV5.reserve_initial_attempt(proposal,row)` is an
unactivated internal local budget/admission API. It requires an existing exact
active canonical scope with provider acknowledgement plus current host policy;
one transaction writes work, attempt, reserved event and budget debit. It neither
creates that governed scope nor proves native funding. Existing initial lookup
returns the stored signature; uncertain/terminal entries cannot reissue.

`PostgresAttemptJournalV5.read_attempt`, `accept_effect`, `accept_absence` and
`mark_funding_unknown` retain versioned history and authenticated terminal issuer
statements. Completion is permanent independently of payment. Returned
`native_verified` is always False. No provider dispatch, refund/payment, arbitrary
funding Boolean, automatic retry, schema adoption or new HTTP route exists here.
FencedAbsencePayloadV5 retains exact V3 fence/receipt encodings. New schema5
requires explicit migration roles, exact compiled CHECK manifest and configuration;
actual PG18 compiler/provenance identities remain UNKNOWN. Historical V3/V4 schemas
and local MAC receipts are never reinterpreted as this production-signature version.

Source preparation only; NOT integrated, deployed, activated or accepted.
Canonical43 remains 6,735 paths / manifest5a56888dc13d6b0b254c6e8aa9be6f0dbb26a7b55b9f3d75796c974c59e84759.
Full A--G / Polygon Amoy AND Cardano Pre-Prod remains NOT READY;13findings open,
0of36tracks verified. Existing profile,48hgovernance, INV1--10 and restricted
economic disablements remain. Local fixtures are not authentic/live assurance.

# VAMS Gateway API Reference

**Gateway source:** `gateway/server.py`
**Gateway version:** v0.2.0-alpha
**Lifecycle:** Implemented API surface; live deployment pending
**Last verified:** 2026-09-24

This document describes the routes implemented by the root Gateway FastAPI
application. The application has no `/api/v1` prefix. Identity, Coinme, Trails,
and payout clients live in the Neuron SDK; they are not Gateway HTTP routes and
must not be advertised as such.

## Security Boundary

Direct Gateway startup binds to loopback. Envoy 1.39.1 using
`gateway/envoy.testnet.yaml` is the sole supported public ingress for staging,
testnet, and production. Live requests must arrive from a loopback proxy peer
with the exact `envoy-1.39.1-v1` marker authored by that ingress. The marker is
transport provenance, not a credential: the M2 signature, durable replay and
revocation checks, and route-specific mTLS identity policy still apply.

Envoy terminates TLS, requires a verified client certificate, removes all
client-supplied forwarding, ingress, and certificate-assertion headers, and
authors the reviewed replacements before forwarding only to loopback Uvicorn.
Direct or incorrectly marked live Uvicorn traffic rejects before M2
authentication, nonce reservation, request-triggered work, or handler execution.
Explicit test/local/demo modes retain direct access as non-live behavior.

The root application uses one closed M2 route ledger. `public` routes need no
request envelope. `authenticated_read` and `privileged_state_change` routes
require all of these single-valued headers:

`X-VAMS-Auth-Version`, `X-VAMS-Auth-Algorithm`,
`X-VAMS-Auth-Audience`, `X-VAMS-Auth-Signer`, `X-VAMS-Auth-Nonce`,
`X-VAMS-Auth-Issued-At`, `X-VAMS-Auth-Expires-At`, and
`X-VAMS-Auth-Signature`.

In live modes the version-1 signature binds the trusted ingress-normalized
semantic request: exact uppercase method, normalized path and query bytes,
forwarded body SHA-256, configured audience, signer, nonce, issue time, expiry,
version, and algorithm. Protected body methods accept only a bounded,
declared-length `application/json` body. Transfer encoding,
multipart/streaming bodies, duplicate security headers, ambiguous targets,
legacy auth headers, and automatic trailing-slash alternatives reject before
the handler. A nonce is durably consumed before handler execution and remains
consumed if the handler fails. Staging, testnet, and production require an
explicit absolute `GATEWAY_AUTH_REPLAY_DB`; `GATEWAY_AUTH_AUDIENCE` and
`GATEWAY_ADMIN_DID` are also mandatory authentication inputs.

The HTTP/1 acceptance contract follows RFC 9112. Framing that could alter
message boundaries or create another upstream request rejects at Envoy.
Obsolete folding is acceptable only when Envoy replaces it with spaces before
interpretation and forwards exactly one unambiguous request with unchanged
method, target, security-header meaning, body bytes, request count, and replay
identity. Equivalent optional whitespace is accepted only under that same
security-equivalence rule. The qualified 1.39.1 configuration rejects both
duplicate-identical and comma-equivalent content lengths before upstream;
they are not normalized by the VAMS profile. Normalization that changes an
authenticated value fails M2 authentication.

## Health And Nodes

| Method | Route | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/` | authenticated read | Render the local status page. |
| `GET` | `/health` | public | Return health and sanitized runtime classification. |
| `POST` | `/heartbeat` | privileged change | Register or refresh node telemetry; live mode also requires reviewed mTLS proxy headers. |
| `GET` | `/nodes` | authenticated read | List known nodes. |

The static SPA does not call `/nodes`. It has no M2 signing authority and shows
an explicit unavailable state rather than promoting a `401`, network failure,
malformed response, or simulated data as live telemetry. A future browser-safe
projection may be provided only by a separately reviewed server-side BFF/session
service with least-privilege M2 authority; no such service exists today.

## Resource Composition

| Method | Route | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/compose` | privileged change | Demo-only local simulation; no provider execution. |
| `DELETE` | `/compose/{instance_id}` | privileged change | Remove a local simulation; no settlement or provider release. |
| `GET` | `/compose/instances` | authenticated read | Inspect non-authoritative local records, including simulations. |
| `GET` | `/compose/blueprints` | public | List static planning templates; no registry verification. |

## Service And Economics Status

| Method | Route | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/services/blocks` | public | Demo-only synthetic declarations, not registry evidence. |
| `GET` | `/services/macros` | public | Demo-only static macros, not registry evidence. |
| `GET` | `/economics/status` | authenticated read | Return economics status data. |
| `GET` | `/economics/epochs` | authenticated read | List tracked economic epochs. |
| `GET` | `/economics/epochs/{epoch_id}` | authenticated read | Return one economic epoch. |
| `GET` | `/economics/estimate-apr` | public | Return a read-only estimate with no durable or external effect. |

## Data Availability Status

| Method | Route | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/da/status` | authenticated read | Return configured DA route status. |
| `GET` | `/da/anchors` | authenticated read | Return locally known DA anchors. |

## VDSO Canary Routes

The mounted VDSO router uses the same root M2 authentication and durable replay
boundary. Its separate intent signer/ownership checks still run afterward.

| Method | Route | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/v1/vdso/intents/simulate` | privileged change | Simulate a signed VDSO intent. |
| `POST` | `/v1/vdso/intents` | privileged change | Submit a signed VDSO intent. |
| `GET` | `/v1/vdso/intents/{intent_id}` | authenticated read | Read one intent. |
| `GET` | `/v1/vdso/objects/{object_id}` | authenticated read | Read one VDSO object. |
| `GET` | `/v1/vdso/adapters` | authenticated read | List configured adapters. |
| `POST` | `/v1/vdso/sidecars` | privileged change | Upload a ciphertext sidecar commitment. |
| `GET` | `/v1/vdso/sidecars/{content_hash}` | authenticated read | Read a sidecar commitment. |
| `POST` | `/v1/vdso/disclosures/verify` | privileged change | Verify a disclosure request. |

## Framework-Only And Disabled Surfaces

FastAPI's `GET`/`HEAD` documentation routes `/openapi.json`, `/docs`,
`/docs/oauth2-redirect`, and `/redoc` are explicitly classified as
framework-only. `OPTIONS` is permitted only as framework/CORS preflight and
cannot invoke an application handler. No WebSocket route is registered; all
WebSocket attempts are denied. `HEAD` is otherwise disabled unless the exact
route/method pair appears in the closed ledger.

## SDK-Only Integrations

`OMSIdentityVerifier`, `TrailsClient`, `CoinmeClient`, and the DA SDKs are
client libraries under `neuron/sdk/` and `neuron/payments/`. Their defaults are
mock-safe for local development and fail closed when a live environment is
configured without explicit credentials and non-mock integrations. They do not
provide public Gateway routes until separately implemented, tested, and added
to this reference.

## Legacy Neuron Gateway

`neuron/gateway/server.py` is a separate lightweight agent-facing service with
`/agents/register`, `/heartbeat`, `/tasks/pending`, and
`/tasks/{task_id}/result`. It is not a substitute for the root Gateway and has
its own deployment and security review requirements.

## Composed settlement earned-delivery interface

These contract calls require a newly qualified ComposedSettlement instance; they
do not add a gateway endpoint or enable frontend wallet transactions.

| Call | Authorization and result |
| --- | --- |
| `recordEarnedDeliveryV3(allocationId,index,outputHash,proof)` | Original provider; exact current-policy/challenge-bound verifier acceptance; consumes replay identity and records earned delivery without payment. |
| `claimEarnedProviderShareV3(allocationId,index)` | Original provider; requires an existing earned record and pays the fixed provider/builder/fee terms once, even after policy change or allocation expiry. |
| `getEarnedDeliveryV3(allocationId,index)` | Valid allocation/index; returns output hash, replay identity, recognition time, fee treasury and accepted flag. This is on-chain recognition, not a provider's signed effect receipt. |
| `refundExpiredComposed(allocationId)` | Original agent after expiry; refunds only unpaid portions without an accepted delivery record. Earned backing remains escrowed. |

Protocol pause blocks recognition and both claim routes. The V2 proof-and-payment
call remains atomic; if its payment reverts, its recognition also reverts. Use the
separate V3 calls when recognition must persist across later payment failure.
Neither a role grant nor the historical verifiedProviderProofs flag can manufacture
an earned record. A stale off-chain proof cannot be converted into earned state
after revocation or expiry. The old unbound creation/claim/proof setters reject.
See docs/remediation/repair_20261031/EARNED-DELIVERY-V3.md for status and limitations.

`ComposedSettlement.isFullyClaimed(allocationId)` returns `false` for unknown IDs.
It returns `true` only after every provider in an existing allocation is paid.
Accepted delivery without payment, partial payment, expiry refund and mixed
payment/refund do not establish that condition. The Boolean ABI is unchanged.
