## 2026-11-05: inactive V3 heartbeat authority producer

The new non-upgradeable V3 source reads the pinned timelock generation/commitment, policy projection and mandatory custody adapter. Policy configuration computes its digest from those current reads and rolls back on failure. The source checks an explicit expected chain ID at construction and every read. One-time policy binding checks the source's actual policy and timelock instances. Custody reads have a fixed 50,000-gas cap, copy only 96 bytes, require exactly 96 returned bytes, and reject noncanonical integer words. A real custody implementation and its gas envelope remain UNKNOWN; synthetic fixtures supply no custody authority.

The exact isolated M82-plus-four-file R6 candidate passed 1,141 Solidity methods in 71 suites, including 24 focused methods, with zero failures/skips. Source runtime/creation sizes are 19,657/34,182 bytes; policy sizes are 4,944/13,879. Three unchanged-source BEFORE regressions reproduced wrong-chain reads, wrong-policy source binding and trailing custody data acceptance. Two earlier baseline fixture failures were corrected by placing revert expectations at execute; original receipts remain. Independent manual Python ABI vectors agree with Solidity for all three new digest domains. Combined canonical checks follow integration separately.

The original source-only design's keccak256 wording is superseded for this NEW V3 family by SHA-256 over fixed bytes32 ASCII domains and ordered static ABI words. Existing V1/V2 source and wire bytes are unchanged. Profile/config/snapshot preimages contain 25/19/23 words respectively; the profile excludes its stored digest, and configuration commits policy root/version/epoch through the profile projection. The first native JSON comparison failed solely on preserved Windows CRLF versus Linux LF transport; the separately frozen LF copy then reproduced byte-for-byte. No digest/preimage content changed.

The producer remains inactive, with no V3 consumer or live profile. A future consumer must independently pin the actual source/policy classes AND reviewed instances, revalidate current digest, and bind its own registry identity. Actual custody/challenge/finality, enrollment/migration, gateway/client and Cardano-native authority remain unfinished. The M82 full-tree secret gate is FAIL; focused scanning does not replace full source/history/TruffleHog. No finding or track is closed. INV-1--INV-10 enforcement and restricted disablements are unchanged. Full A-G, both chains, 13 open findings, 0/36 verified tracks and actual seven-/fourteen-day observation remain: NOT READY. Details: docs/remediation/repair_20261105/HEARTBEAT-AUTHORITY-PRODUCER-V3.md. Historical content follows unchanged.

## 2026-11-05: inactive timelock authority-generation prerequisite

The separate V3 operation-aware timelock records a monotonic generation and chained commitment for effective role membership, role-admin and minimum-delay changes. Restoring earlier permissions or delay does not restore the old generation. No-op or failed changes and ordinary schedule/cancel/execute lifecycle do not advance this global generation; per-operation epochs remain separate. Frozen VAMS/V1/V2 sources and existing wire encodings are unchanged.

The 48-hour floor and self-call restriction remain inherited. V3 observes delay changes through the pinned OpenZeppelin execution hook because the VAMS updateDelay implementation is non-virtual. Each batch target records its transition before the next target executes, and a later failure rolls back the batch. The constructor commitment includes the actual controller self-admin member; it is instance-specific.

The exact isolated M81-plus-V3 candidate passed 1,117 Solidity tests in 70 suites, zero failures/skips, including 17 focused cases. V3 measures 8,473 runtime and 11,830 creation bytes. A separately retained source-factory probe reproduces the V2 missing-generation failure and passes against V3; it is not included in the 1,117 and is not a readiness gate. Prior two compiler failures executed zero tests and remain preserved. Local fixtures and AI source review do not supply authentic custody or live authority.

V3 is not configured into the existing V2 registry/policy, whose runtime pins must continue rejecting it. Authentic authority/custody/challenge/finality producers, reviewed rebinding, enrollment/migration, gateway/client wiring and the Cardano-native counterpart remain unfinished. No profile, role or route is activated. The M81 full secret gate remains FAIL; structural artifact checks clear no findings. Full A-G, both chains, independent assurance and actual seven-/fourteen-day observation remain required. Thirteen findings remain open, zero tracks verified, zero promotions: NOT READY. Details: docs/remediation/repair_20261105/HEARTBEAT-AUTHORITY-GENERATION.md. Historical content follows unchanged.

## 2026-11-05: inactive atomic heartbeat consent consumer

The separate, non-upgradeable schema-2 EVM prototype relays bounded canonical bytes through the exact singleton Timelock operation. Normal replacement requires OLD+NEW body-key consent; lost-key recovery requires observed governance delay of at least 48 hours plus NEW-key consent. The callback revalidates current policy/authority/challenge facts, operation epoch and exact calldata, then applies principal generation/nonce compare-and-set atomically. Queue cancellation and identical requeue invalidate prior challenge epochs. Existing V1 encodings and code remain unchanged.

The repair pins the known policy implementation, bounds signed principal duration from notBefore to expiresAt, and supports only an explicitly configured zero-grace profile. A stateless pinned router shares canonical codec logic without granting authority. No profile is configured by default. Production enrollment/migration, authenticated current-state and challenge/finality producers, gateway/client wiring and the Cardano counterpart remain required; test-only seeding and synthetic providers supply local fixtures only.

Exact isolated source80-plus-component checks passed the unchanged EVM size limits, 20 focused methods and 1,100 full Solidity methods in 69 suites; the 20 are included. The registry measures 19,070 runtime/47,768 creation bytes, and the test seed harness 19,743/48,459. These are local native results, with synthetic authority and no accepted per-operation gas budget, authentic authority, live proof or operational qualification. Combined canonical checks follow integration separately. The full current-tree secret gate remains failed; scanner findings, history/TruffleHog and the full frozen workflow remain outstanding.

No live profile, authority, role, route, economic parameter or deployment is activated. Full A-G, both Polygon Amoy and Cardano Pre-Prod, 13 open findings, zero verified tracks, independent assurance and actual seven-/fourteen-day observations remain: NOT READY. Details: docs/remediation/repair_20261105/HEARTBEAT-ATOMIC-CONSUMER.md. Historical content follows unchanged.
## 2026-11-05: complete-secret address exception

The generic-api-key exception now applies to a complete captured 20-byte EVM address on the same four approved paths. A longer secret containing an address-shaped prefix remains detectable. Default detectors, the rule selector and AND condition remain. The M0.4 gate changes only its configuration-hash pin; first-party findings still fail.

The bounded fixture regression demonstrated the old configuration mismatch, then passed with the exact corrected candidate. Its strict paired oracle covers 97 baseline and 67 configured observations across 11 generated files; these are source-oracle cardinalities matched by the CLI, not test-method counts or retained raw-report counts. The scanner source, report schema/redaction/columns, binary and raw main streams are bound in the retained evidence. Original failures and historical source identities remain.

This repair does not adjudicate the prior M78 full-tree FAIL (638 first-party matches across 68 files), scan source history, cover TruffleHog or establish full CI. Full current-source gates must run after integration; readiness remains NOT READY, 13 findings open and 0/36 tracks verified. Runtime authority, role grants and both-chain deployment remain unchanged. Details: docs/remediation/repair_20261105/SCANNER-ADDRESS-CAPTURE.md. Historical content follows unchanged.

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

## Stable requirement-driven alignment allocation — 2026-11-04

Present nonempty skill/cognitive requirements select fixed 0.10 alignment
budgets regardless of prefilled custom alignment weights. Absent axes receive
zero during dynamic scoring; the four base dimensions retain their proportions.
Proportions are divided by the positive base sum before multiplication, avoiding
overflow for valid tiny finite base weights. Nonpositive base sum rejects.
Static no-requirement behavior and configured objects remain unchanged. Ten
actual-module unit methods pass locally; earlier nine-method R1 evidence remains
separate and is not added to that count. Full pytest/composer/provider qualification
is unrun. Scoring confers no admission, effect, proof or payment authority.

Compute each base coefficient as (component / base_sum) * remaining. For
finite nonnegative valid weights its proportion is bounded before multiplication,
whereas remaining / base_sum can overflow for positive subnormal sums. This
implements the same v0.8 formula. Invalid nonfinite/negative configurations remain
a separately identified follow-up. All INV-1--INV-10 enforcement is unchanged.

## Legacy gateway request and direct-call containment — 2026-11-04

An exported ASGI app may receive HTTP without lifespan, and embedded callers can
invoke its handlers directly. Enforce the existing non-live decision at both
request middleware (before limiter) and all handler boundaries. Reparse strict
effective mode/mock flags and compare both bound startup/runtime policies; never
reuse stale policy as authority. Constant503 refusal avoids reflecting configuration.
No new mode override, live route, credential or mock promotion follows. Preserve
local behavior and existing startup checks. Eleven actual-function fixture methods
pass after34failed baseline assertions; five real-ASGI methods and fullframework
qualification are unrun. All invariant/restricted controls and fullA--G/BOTHchains
scope remain; independent review and actual native/operator evidence stay separate.

## Purpose-separated body-key signature check — 2026-11-04

Bind each required key role to a separate domain/algorithm/role plus exact
witness digest, then ECDSA/SHA256 once. The witness already binds the acyclic
base, operation/ETA/challenge/times/mode/role mask. Verify the exact record
digest and its role-specific ID/generation/policy before cryptography. One
call checks only that role's body key. This provides a component for future
consent consumption, with no native authority or issuer privileges of its own.

Four literal cases use an independent TLV encoder and public fixture keys;
Python/OpenSSL signatures pass full-key Solidity arithmetic. Local13Python
methods and14focused/1077combined VM tests are separate counts;1063prior tests
are included. Actual chain MODEXP/gas, independent human crypto review, finalized
authority/history, challenge/freshness and operational consent remain unqualified.
The fixed native test environment propagates no historical RPC/credential fields.
Earlier broadly inherited env fields were audited as EMPTY; originals are kept.

New formats remain proposed, with Rust/Aiken conformance/fullwire acceptance
unrun. No governance execution, nativeCardano producer/reader, consent store,
atomic nonce use, M2 proof/mTLS or protected route is enabled. Preserve all
INV1--INV10 enforcement, restricted disablements, fullA--G/BOTHchains,13open/
0of36verified/NOT READY and actual7-/14-day observation/independent assurance.

## Purpose-separated consent data and exact-byte evidence — 2026-11-04

Queue only immutable base intent/CAS/predecessor/salt, then bind a later witness
to the derived actual timelock operation/ETA and authenticated fresh challenge.
Putting the operation ID into its own queued base would create a hash cycle.
This slice implements data representation only; no witness signature or native
state verification, issuer privilege, consent-store mutation or protected effect.

The strict ordered TLV frames have distinct version2domains, fixed widths and
SHA256computed once over exact binary bytes. Python/Solidity memory/calldata
decoders agree with6independently encoded literal pairs. Opaque digest zeroes
are ordinary32byte values. Presence uses generation, not a digest's bit pattern;
identity and enrollment-sentinel rules remain distinct. UInt64policy profile is
PrincipalV1-compatible; wider native getter values require rejection, not casts.
Sequence/nonce producers still need explicit versioned implementations.

Local15stdlib/8focused/1063combined overlay passes are separate evidence. Native
compile-only failures and four-/one-failure campaigns remain retained. The test
harness, not the data oracle or codec, needed explicit bytes1casts, exact copied
witnesses, fresh memory structs and an external invalid-encoder call boundary.
All16valid seed literals now match the independent fixture; invalid-input tests
first prove valid baselines through memory and calldata. This repairs vacuous
negative coverage rather than weakening the expected result. Native code-size
and raw warnings/streams remain separately bound; a standalone internal-library
stub is not the cost of a relying consumer.

No native authentication follows from parsing or structural matching. Actual
timelock context, nonce/CAS/current authority checks, signed old+new rotation or
governance+new recovery, challenge/finality/freshness, actual key custody and
caller/route/mTLS enforcement remain. V1policy and registry both pin the base
timelock; new consent integration needs a fresh reviewed pair and runtime helper.
Rust/Aiken byte conformance and full protocol/wire acceptance remain unrun.
All INV1--INV10 enforcement and restricted disablements remain unchanged. Full
A--G/Amoy AND CardanoPre-Prod,13open0of36verified/NOT READY and actual7-/14-day
observation/independent assurance requirements remain; no live authority added.

## Acyclic consent and exact active operation — 2026-11-04

Including an operation ID in a base intent that appears in that operation's
calldata creates a hash cycle. Exact ETA is also known only after scheduling.
Separate immutable queued base intent/CAS/predecessor/salt from a later witness
over base-intent digest, actual operation ID/ETA, challenge and consent role set.
Freshness cannot follow solely from a future-dated signature timestamp.

A ready singleton does not prove that it is the actual parent call: identical
target calldata can occur inside a separate ready batch while the singleton also
remains ready. The new inactive timelock variant publishes exact active ID and
batch mode around inherited execution, forbids nesting, and clears/rolls back
context. Actual relying callers must still require the pinned timelock sender.
Synthetic producer/consumer tests demonstrate both the readiness-only design
counterexample and context/caller denials. This is not a claim of an existing
deployed V1 exploit: V1 is unactivated, unsigned data state, not consent authority.

The48hour constructor/schedule/update floor, inherited roles and predecessor
checks remain. Ordinary non-consent batches work; nested execution is explicitly
unsupported in the new instance. Existing base instances are unchanged. Source
review caught and fixed the missing forwarding constructor and incomplete caller
fixtures before native compilation. Inherited errors use their declaring type
and exact encoded arguments. Local14focused/1055combined VM passes include the
prior1041; sizes and compiler warnings are retained separately.

Private PID/network namespaces, die-with-parent and owned-process timeout cleanup
bound the local campaign. Timeout status reports leader reaping only, requires
inspection and forbids automatic retry; no descendant-reaping observation or
forced-timeout campaign is claimed. The original unsubmitted helper drafts remain.

The current registry pins the original base timelock runtime and will reject this
subclass. A fresh independently reviewed consent-gated registry/profile pair and
actual custody remain open. This does not solve material-authority A-to-B-to-A,
native finalized-state authentication, actual consent/challenge policy, mTLS,
provider evidence, native Cardano, human assurance or fullworkflow qualification.
All INV1--INV10 enforcement/restricted disablements remain; partialF08/T10/T31
source evidence is not acceptance. FullA--G/Amoy AND CardanoPre-Prod,13open0of36
verified/NOT READY and real7-/14-day observation requirements remain.

## Raw full-key ECDSA compatibility and local evidence — 2026-11-03

Current Python wire verification accepts raw64r||s, low-S, full64byte x||y and
SHA256digest semantics. Two ecrecover parity attempts miss overflow recovery
points, and address-only comparison is not full-key verification. Preserve the
complete input domain. The new component adapts retained OpenZeppelin Jacobian/
Shamir math to secp256k1 with a=0/b=7 and checked MODEXP inverses. Equal, opposite
and infinity paths remain explicit. It is new cryptographic code, not inherited
assurance from P256 or a substitute for node consent/current native authority.

An independently constructed affine fixture builder checked59public vectors
(40positive/19negative) through the existing actual Python crypto backend. This
includes joint and separate R/Q x-coordinate overflow, low-S boundaries, malformed
data, opposite-generator and infinity cases. Some mathematical digests have no
known canonical-message preimage/private key; no key-possession claim follows.
Native tests compare memory/calldata APIs to those literals, inject6MODEXPfaults,
and use256synthetic signer fuzz runs. Rebased local full1041PASS includes source70's
973plus68methods. Python3methods verify the exported vectors and message/digest
parity without double hashing. No real operator keys/signing are involved.

Initial Yul arity and stack-depth compiler failures remain retained. Source
refactoring preserved the frozen0.8.24/non-viaIR settings and raw input domain.
The source70overlay harness is3,283runtime/3,312initcode bytes. Local gas probes
are264,351ordinary and55,774joint-overflow in the earlier source69overlay; neither
is a worst-case/target-chain bound. Re-measure integrated callers. Human crypto
assurance, consent lifetime/withdrawal/rotation/recovery policy, authentic monotonic
authority cutover, native finalized-state readers, scoped node routes/client,
mTLS, Cardano and fulloperational gates remain. Caller binding must prevent an
arbitrary digest/key validity Boolean from becoming a policy or authority claim.
All INV-1--INV-10 controls/restricted disablements remain unchanged. PartialF08/
T07/T10/T31/T33 evidence is not track acceptance. FullA--G/BOTHchains/13open/
0of36verified/NOT READY and actual7-/14-day observation requirements remain.

## Governed heartbeat state producer and evidence scope — 2026-11-03

The source70 prototype implements the accepted local registry state machine
against the already frozen PrincipalV1 codec and policy-runtime artifact. Exact
timelock identity/delay, canonical record/CAS/generation, current policy snapshots,
half-open validity, tombstones and separate pause-only access are exercised through
real local contract callers. Expected deployment configuration remains external
trust input. Synthetic Safe-shaped contracts and Foundry impersonation qualify
role routing only; actual Safe code/owners/quorum, custody and role manifests do
not follow from them. No ordinary token governor proposer is introduced.

R1 compiled8/9tests; an argument's SHA256precompile consumed an armed prank/revert
expectation before the intended registry call. Precomputing canonical bytes fixes
that harness error. Subsequent retained failures identified an inherited selector,
legacy admin-role API and a test stack-depth issue. CorrectedR6 passes21focused
methods and973fullSolidity cases with0fail/skip; build sizes exits0 with warnings,
10,889runtime/30,321initcode bytes. The settings remain Solidity0.8.24, optimizer200,
non-viaIR, offline/FFI disabled in private tmpfs. Counts and original source trees
remain separate; historical passes are never summed with current results.

This component does not authenticate node consent, TLS certificates, native
finality or actual approved governance. Those remain enrollment/effect blockers.
Any future relying consumer must validate the complete consent/current-state/
policy chain before protected effects; a role or persisted boolean cannot replace
verification. Existing M2v1 and PrincipalV1 bytes remain. The EVM prototype creates
no Cardano exclusion and does not enable ExecuteIntent, rewards, deposits, yield,
ordinary token governor or any other restricted activation. INV-1--INV-10 controls
are unchanged. Partial F08/T31/T33/G3 local evidence is not track acceptance.
FullA--G/BOTHchains/13open/0of36verified/NOT READY and real7-/14-day observations
remain. No acquisition/provider/realkey/signing/funding/deployment/R28/Slot08/Aiken
action occurred; all signing fixtures remain explicitly synthetic local tests.

## Signed pending-approval data preparation — 2026-11-03

M2 middleware already authenticates POST /heartbeat and consumes the outer nonce;
missing handler Depends was not a bypass. M2v1 lacks principal/policy generations,
so same-second epoch or key/policy changes need a separately versioned signed
inner payload and a trusted migration, rather than a timestamp-only cutoff.
This slice freezes only the unsigned data contract. Payload text digest binds
the exact ASCII VAMS-HB2: envelope; structural matching recomputes node identity
and compares exact principal digest/generation, policy root/version/epoch and
outer nonce/timestamps. It grants no rights and performs no protected effect.

The chosen source descriptor commits EVM chain/genesis context and registry/
policy addresses/code identities. It cannot detect proxies, approve caller-
supplied identities or prove current state. Cardano scheme remains unsupported
pending its own authenticated producer/reader. Native consumers must enforce
finality/current policy and fencing at mutation; encoding alone does not offer
instantaneous chain/database atomicity. Outer nonce consumption on later denial
is security bookkeeping, not a node/effect update. No live route is changed.

Bounds precede parsing; strict types reject coercion and malformed lengths/order.
Numeric observations use explicit i64 or finite IEEE754f64 tags and preserve
negative zero; no canonical-byte comparison may rely on Python float equality.
Credit score remains an integer. Opaque bytes32 hashes are not narrowed by an
invented zero restriction; identity/nonzero constraints remain on actual identity
fields. A root-authored independent reference builder freezes domains and exact
preimages without importing candidate modules.29local stdlib cases cover these
contracts, malformed data, exact bits, actual M2 timestamp validator parity
at0/2^63-1 and rejection of upper-half u64 values, plus changed-generation/source/outer-tuple
structural mismatch. No signature/native-current-state/live replay claim follows.

Existing PrincipalV1/M2v1/action/effect/settlement bytes and INV-1--INV-10 controls
are unchanged. This is partial F08/T31/T33 and G3 evidence only, not assurance.
No economics, governance delay, restrictions or provider proof is activated.
FullA--G/BOTHchains/18findings13open/0of36verified/NOT READY remain. Human custody,
privacy/security review, real operators/providers and actual7-/14-day observation
cannot be supplied by these codecs. No signing/installation/provider/deployment/
R29/Slot08/Aiken action occurs in this slice.

## Gateway dashboard correctness and text boundary — 2026-11-03

Source inspection traced receive_heartbeat's NodeInfo creation to dashboard row
rendering. Both populated row branches referenced last_seen_formatted, but the
class exposed it only as a dictionary key from to_dict. Actual nodes therefore
raised AttributeError before a populated response. Row strings also inserted
unescaped node_id/network text; this was a latent sink behind the crash, not an
observed unauthenticated or live XSS bypass. The selected repair addresses both:
one computed property reuses the existing datetime formatter, to_dict reuses it,
and escape_html(str(value)) handles textual cells in both branches. Local html
response variable precludes importing the module under the name html.

Eight regression methods exercise actual NodeInfo/dashboard AST with a fixed
clock and HTMLResponse fixture. Real-node cases reproduce the missing property;
a complete row-interface fixture isolates HTML interpolation without claiming
that original broken real-node rendering reached the browser. HTMLParser checks
no injected img/svg/script/b/i tags and preserves visible literal text. Tests
retain empty/default/order/numeric/Unicode behavior and pin unchanged route
decorators and other authentication/handler AST. Both candidate local platforms
pass8withzeroexternal I/O. The first fixture used asyncio.run, whose Windows
loop allocated blocked local sockets; its failure is preserved. Directly driving
the no-await renderer avoids loop sockets without relaxing the I/O guard.

Two full-ASGI regressions were added to the existing gateway test class, keeping
every original method unchanged. They are NOT RUN. Full vendor/pytest/ingress,
CSP/privacy/operator and native qualification remain required. F08/T31 plus UI
boundary requirements remain open. All INV-1--INV-10 enforcement, economics,
48hgovernance, restricted disablements and frozen encodings are unchanged.
No provider/acquisition/signing/deployment/R28/Slot08/Aiken action occurred.
FullA--G/BOTH chains/13open/0of36verified/NOT READY. Actual7closed/14public days
and independent assurance remain; local display tests cannot replace them.

## Authenticate the policy implementation with a pinned runtime — 2026-11-03

The registry design previously checked code presence and getter linkage, which
cannot distinguish an impostor that suppresses policy-generation invalidation.
Adopt an exact source/tool-bound runtime template for RestrictedTestnetPolicyV1.
Its immutables prevent directly treating type(...).runtimeCode as deployed code.
Capture actual compiler output/AST/immutableReferences, patch only all14known
32-byte words for governance/hostDomain/budgetUnit, and compare extcodehash and
length before any policy getter. Missing bindings reject. This helper has no
authority/storage/issuer/signature or external getter behavior.

The18transitive source contents, compiler/settings/artifact hashes and all14
reference ranges were independently checked. Tests use actual local policy and
48hTimelock instances plus malformed/shape/altered-code negatives. The first
test draft failed compilation for one missing parenthesis; its result is retained
and the test-only correction is separate. Six focused cases and the952-case full
candidate suite pass, with6included. Build-size success is not a clean scanner
gate or proof that a future registry fits EIP170/EIP3860. The fake-getter case
short-circuits on length; static source review establishes no external calls.

Expected immutable values still need approved custody/profile/deployment roots;
provenance constants alone do not establish that approval. Actual finalized
storage, enrollment consent, expiry/revocation/generation, scoped routes and client
are not implemented. A future signed payload must bind the exact principal
snapshot while preserving M2v1 bytes, including same-second policy cutovers.
Cardano authority/reader is separately required. No ordinary-provider key can
issue governance; no committee/RPC fallback or unknown input is promoted.

F08/T31 and privacyT33 remain open; INV-1--INV-10 enforcement, economics,
48hgovernance and restricted disabled activations remain unchanged. FullA--G/BOTH
chains/13open/0of36verified/NOT READY; all required full/native/operator/privacy
gates, authentic proofs/providers/observers/custody, rehearsals and actual7closed/
14public days remain. No acquisition, provider, real signing/funding/roles,
deployment, R28, Slot08 or Aiken action occurred in this local dependency slice.

## Pure Solidity heartbeat principal wire dependency — 2026-11-03

Port the frozen Python HeartbeatPrincipalV1 to a pure Solidity library before
implementing the EVM governed registry. Preserve all18fields, domains, integer
widths, identity derivation and accepted-value rules. Do not reinterpret M2,
ActionContext, object-grant or receipt formats. Query is exactly empty. Audience
varies; the617-byte vector is not a universal frame length. Native raw node-ID
derivation is omitted to avoid silently changing UTF-8/no-normalization behavior.

The calldata wrapper checks the1024-byte total before copying to memory; the
ordered bounded decoder rejects truncation, alternate IDs/widths and trailing
data. All reconstructed field values are exact, so canonical re-encoding equals
accepted input. Field constraints and tuple hashes are structural: all-zero64-byte
keys retain Python shape semantics and do not verify curve validity or possession.
There is no state, role, issuer, current-policy, revocation, ownership or privacy
guarantee. The library is not wired into a runtime or deployment.

Sixteen new native Foundry methods include two256-run fuzz tests, independent
Python603/617/730-byte digest references and adversarial boundary cases. Full
candidate suite946PASS includes those16; focused/source/size/scan/canonical
receipts remain distinct. New data dependencies have no fabricated before-defect
run. The root M2 enrollment gap remains demonstrated by its prior source audit.

F08/T31 and privacyT33 remain open. INV-1--INV-10 enforcement, registry-authoritative
fees, solvency, restricted zero rewards/emissions,48-hour governance and disabled
Deposit/Slash activation/ExecuteIntent/fiat/yield/minter/governor/vesting/buyback/
delegation are unchanged. Cardano remains required with its native authority and
reader; the EVM codec is no substitute. Custody, policy/current-state authenticity,
operator/privacy approval, all required gates and actual7closed/14public days
remain blocking. No new authority or external-service/installation/signing/
funding/deployment/R28/Slot08/Aiken invocation occurred in this slice.

## Scoped heartbeat principal data dependency — 2026-11-03

The root M2 audit found no shared enrollment relationship among the M2 signer,
certificate fingerprint, body key and node_id. Existing ActionContext/object
grants/receipts cannot be repurposed as HTTP credentials. Adopt existing M2 bytes
and governance epoch principles; introduce a separately versioned unsigned
HeartbeatPrincipalV1 record first, followed by a governed registry, authenticated
current-state resolver, explicit route authorization and a distinct scoped client.

The18-field bounded codec binds all four identity inputs, host/service, audience,
exact POST /heartbeat/empty query and policy root/version/epoch/generation/time.
Record IDs are derived under a separate domain from host/service/scoped node-ID
commitment. They identify node slots and remain stable under credential/policy
rotation; replacement needs governance, generation advance and stale-record
revocation. No issuer or ownership is inferred from the hash. Unsalted identifiers
are guessable/linkable; host scoping does not establish anonymity or privacy
acceptance. Native/registry authorities and actual public bindings remain UNKNOWN.

R1's opaque-ID mismatch was rejected before integration and preserved. R2's
oversized text allocated about1MB before rejection; pre-length guards now bound
temporary copying without changing accepted values or the617byte vector. The13
checks include an independent byte builder, extracted existing M2 DID/audience
parity, decoder/type/tuple/time boundaries and allocation regression. No registry,
issuer signature, route authorization, framework, native state or live service
is exercised. Constructing data or matching time/tuple fields grants no authority.

F08/T31 and privacy T33 retain complete acceptance requirements. All INV-1--10
enforcement paths, fees, restricted economics,48-hour governance and disabled
activations remain unchanged. The next source slices must authenticate current
governance and revocation before resolving a node key or permitting mutation;
provider keys and fixtures cannot issue authority. FullA--G/BOTH chains,13open/
0of36verified/NOT READY, full/native gates, real proof/provider/observer/custody/
privacy/independent assurance, rehearsals and7closed-/14public-day requirements
remain. No installation, provider, real key/signing/funding/role/deployment or
R28/Slot08/Aiken action is authorized or performed by this data dependency.

## Heartbeat falsey-key body-signature correction — 2026-11-03

The actual root handler selected a first-contact public_key, then gated signature
verification with `if pub_key_hex and ...`. Empty/non-string falsey values could
therefore reach node insertion or update without body verification. Outer M2 and
the live certificate check were still prerequisites; no overall M2/mTLS bypass
was established. A valid outer request is not a substitute for the node signature.

Require a non-empty string selected key and unconditional successful verification
before mutation. Preserve all other server AST, cached-key priority, payload/key/
signature encodings, status/error behavior and M2/replay/certificate controls.
Eight extracted-handler/actual-NodeInfo cases use the unchanged actual crypto
module with ephemeral synthetic keys. Before control retained seven failures;
after all eight pass. Positive and wrong-key/cached-key controls retain exact
body-byte signing behavior. No real user key, credential file or service was used.
Two full-ASGI tests were added without altering existing test methods; they are
NOT RUN. The supplement does not import the gateway application or exercise
framework/M2/ingress/certificate enforcement, native Linux312 or a live operator.

F08/M2 and T31/G3 remain open for complete auth, replay, scope, mTLS and abuse
qualification. T31 maps indirectly to INV-5/INV-6, but this change does not qualify
OMS/TEE root enforcement; all INV-1--10 enforcement paths retain their criteria.
First keys remain self-asserted; M2 signer/certificate/node identity enrollment,
least privilege and the root client are separate unresolved requirements. Node
state remains process-local and cannot be treated as durable admission evidence.
Fees, restricted economics,48-hour governance, disabled activations, full A--G/
BOTH chains and real7closed-/14public-day requirements remain. No acquisition,
provider, real signing/funding/role/deployment/R28/Slot08/Aiken action is implied.

## SDK accessor runtime-denial precedence — 2026-11-03

The public custom-transport seam could raise an observed _PhalaRuntimeDriftError
from response.headers/items or response.raw/read, restore ambient policy, then
propagate the denial. Two broad accessor catches converted it to provider_error;
the outer cleanup saw restored policy and returned a diagnostic report. In a
multi-provider call that let the next diagnostic dispatch proceed. Reports stayed
invalid/non-authoritative; no authentic proof or protected-effect bypass was
established. The TrustProvider comparator already preserved its private guard.

Add only explicit private-error rethrows in those two handlers. The original
outer consumer retains close-once attempts and private-denial priority, including
control exceptions during cleanup. Preserve all other SDK AST, byte/encoding/read
limits, report/quorum/root/session semantics and ordinary provider error behavior.
The before67-case campaign reproduced15failing callback/control subcases; after
67cases pass on Linux314 and Windows312, including the previous64 unchanged cases
and3new regression methods. All transports/bytes/vendor/ABI symbols are fixtures.
No actual provider, quote, hardware, native HTTP or deployed caller is qualified.

INV-6 containment is affected; authentic root/workload/hardware binding remains
open. INV-1--5/7--10 controls, fees, restricted economics,48-hour governance and
disabled activations remain unchanged. Existing F06/F12/F16 and applicable T04/
T05/T23/T27/T33 requirements retain acceptance criteria. FullA--G/BOTHchains,
13open/0of36verified/NOT READY. M2client/fullnative workflow/provider/custody/
privacy/independentassurance and actual7closed-/14public-day requirements remain.
No acquisition/provider/credentials/signing/funding/roles/deployment/R28/Slot08/
Aiken execution or new authority is implied by this repair.

## Direct legacy GatewayClient actual-process policy — 2026-11-03

The existing client derived authority from an optional caller map, so a matching
local map could mask actual production or missing mode. Its five request methods
did not revalidate after construction. Four retained fake-transport reproductions
established client-side dispatch/adoption, including an extracted-parent case;
they did not establish actual server acceptance. Existing legacy server live
startup refusal and root gateway M2 route requirements establish the compatible
boundary: bind actual process policy, treat supplied policy/map as assertions,
and refuse this legacy client in live modes before Requests session creation.
Do not promote the unsupported legacy protocol or invent an M2 replacement.

Recheck after URL preparation before session creation; all five public methods
guard entry, pre-dispatch after argument preparation, and response/status/JSON
adoption. A private fixed-message denial survives broad catches; parser and
callback diagnostics are never formatted by the added handlers. Preserve local
paths, payloads, timeouts, no-redirect behavior, ordinary failure results and
frozen configuration. These stage checks cannot undo a dispatched request or
atomically fence environment changes during serialization/transport. Real provider
authorization, ingress/M2 authentication and durable replay are separate controls.

Replace unsafe tests that blessed caller-map override/live legacy success with
pre-session denial. Matching local fixture maps establish matching actual mode;
keep pure URL snapshot tests and immutable fields. The security pytest changes
only its old live-positive test to live refusal; that pytest gate was NOT RUN.
The runtime AST read now explicitly uses UTF8 for Windows portability. The first
Windows combined run's one encoding error is retained separately. New regressions
failed against old source; the 137-case fixture campaign includes92prior+17runtime
+13privacy+15new cases, with memory-only Requests/crypto/storage and extracted
parent methods. No full vendor, actual Requests adapter, ASGI, native or live
authentication behavior is qualified. Frozen dependencies and approved runner
requirements remain unchanged; failing/missing required gates remain blockers.

INV-6 indirect runtime/identity containment remains affected; authentic binding
stays open. INV-1--5/7--10 controls, fees, restricted economics,48-hour governance
and disabled activation paths remain unchanged. F06/F12/F16 and T04/T05/T10/T11/
T15/T23/T27/T33 retain acceptance criteria. FullA--G/BOTHchains/13open/0of36verified/
NOT READY, all native/authentic/operator/privacy assurance and real7closed-canary/
14public-observation days remain. No acquisition/provider/credentials/signing/
funding/role/deployment/R28/Slot08/Aiken authority is expanded or exercised.

## Neuron lifecycle runtime and identity continuity — 2026-11-03

Defects reproduced with actual method bodies and memory-only collaborators:
stale Neuron objects could reach credential/signing/heartbeat/workflow effects;
failed existing-key reads/parses entered generation and wb overwrite. Source60
only checked the constructor. Source61 reuses its immutable binding and checks
actual policy plus effective mock choice at operation/stage boundaries. A private
fixed-message guard distinguishes this instance's denial from collaborator errors,
survives resource-close/control exceptions and stops fallback/retry. This does
not fence concurrent process mutation, qualify every diagnostic route or replace
provider admission, revocation, reconciliation and settlement controls.

Key creation is permitted only on an opening-time absent path and an uninitialized
instance; all other opening/read/parse errors reject. Generate and serialize under
current policy, create exclusively with a 0600 POSIX mode request, check write
length, flush and close, then adopt the generated key. Never overwrite or unlink
another creator or an incomplete file. Incomplete files need explicit recovery.
No actual private key was read or generated in the local tests. PEM/public-key/
signature formats and the actual crypto module remain unchanged. Native ACLs,
durability/crash behavior, fsync, custody and rotation remain separate acceptance.

The first candidate's six reproduced callback/cleanup/loop gaps were corrected.
Non-author review then found a breaker-callback seam; both true/false branches
now recheck policy immediately after the callback and before the next provider
stage. Its four mode/flag regression subcases failed before this correction.
The 92-case campaign includes 67 prior cases and 25 new lifecycle cases; files,
crypto, storage, dispatch and optional demo-engine collaborators are fixtures.
Separate 64 TEE and 82 provider campaigns retain their limitations. Full vendor
imports, native workflow/SQLite/PostgreSQL and authentic/live effects remain open.
The standalone legacy GatewayClient's caller-policy and stale-dispatch gap is
independently reproduced and tracked next; this parent repair does not close it.

INV-6 containment is affected, authentic root/workload/hardware binding remains
open. INV-1--5/7--10 controls, fees, restricted economics, 48-hour governance and
disabled activations remain unchanged. F06/F12/F16 and applicable T04/T05/T10/
T11/T15/T23/T27/T33 retain their full acceptance criteria. Full A--G, both chains,
13 open/0 of 36 verified/NOT READY, all native/authentic/operator/privacy assurance
and real 7 closed-canary/14 public-observation days remain. No R28/Slot08/Aiken,
acquisition, provider, signing, funding, role or deployment authority is expanded.

## Neuron constructor policy authority — 2026-11-03

Defect: the public constructor selected policy from caller environ and applied its
live ban to that substituted mode. A controlled reproduction of the actual init
body reached a storage collaborator tripwire in7of10cases (six live override cases
and one missing-process-mode override);3directlivecalls rejected. No real storage,
provider, credential, network or protected effect was executed by that reproduction.

Load actual process policy first. Require supplied RuntimePolicy/map assertions
to match actual mode and registered effective mock flags; validate map completeness
and explicit-vs-configured mock conflicts without granting it authority. Keep the
matching map for ordinary configuration. Apply the existing live-startup rejection
before collaborators, bind actual policy/effective mock fields, and revalidate both
immediately before NeuronStorage. This catches prefix callbacks, including an added
false mock flag conflicting with a previously allowed explicit local mock choice.
No new flags or global-policy changes; matching explicit/implicit local fixtures stay.

New tests compile the actual constructor and immutable-field declaration with
counted storage/provider/compute/trust/wallet/gateway/payment/signal collaborators.
They test zero collaborator initialization on rejected inputs and positive complete
initialization/configuration forwarding for valid local cases. Optional AgentOS/
DBOS branches, full Neuron imports, real dependencies/storage/providers/effects
remain unqualified. Legacy injected-environment tests now establish matching actual
mode/flags with their assertions unchanged. All other Neuron methods stay unchanged;
later method drift and dynamic/deployed callers require separate audit, not inference.

INV-6 remains affected through actual runtime/proof containment, authentic root/
workload/hardware binding open. INV-1--5/7--10 enforcement, restricted economics,
48hgovernance and disabled activations unchanged. F06/F12/F16 and applicable
T04/T05/T10/T11/T15/T23/T27/T33 keep full acceptance criteria. Full A--G/BOTHchains,
native/fullworkflow, authentic proof/provider/operator/privacy/assurance and real
7closed-/14public-day requirements remain. No acquisition/provider/signing/funding/
role/deployment/R28/Slot08/Aiken action is authorized or performed by this repair.

## Legacy TrustProvider resource policy — 2026-11-03

Source58 acquired responses only after Requests' default eager download, and
Automata called unbounded response.json. Stream/no-redirects at each actual caller
allows policy/status/cleanup control before body consumption. Phala/Marlin and
non200 consume none. Reuse the accepted source56 engineering policy: Automata200
only, absent/identity content encoding, raw.read(decode_content=False), requests
at mostmin(8,192,remaining+1), reject malformed/oversized chunks, append no more
than65,536bytes, require empty-read EOF, ignore Content-Length. Parse strictUTF8
JSON with the existing JSON-RPC envelope/result checks; no new duplicate-key or
non-finite policy. This is a local compatibility limit, not a native/provider cap.

Preserve cleanup/private runtime-drift priority, control propagation and fixed
ordinary errors. Required peer-review adoption rule: retain parsed chain ID only
after successful close/final current-policy check; any offline pass clears it.
The 33 prior source58 assertions remain; only local transport fixture mechanics
change for raw bytes. Added tests use actual providers->manager->extracted actual
CLI, raw-size/encoding/EOF/short-read/malformed/clock/close/control/drift adversaries.
Full Neuron/vendor imports, real HTTP buffering/headers/DNS/CPU/deadlines/totalheap,
authentic provider/TEE/root/workload and live operations remain unqualified.

INV-6 containment/provenance stays affected with authentic binding still open;
INV-1--5/7--10 enforcement and restricted economics/48hgovernance unchanged. F06/
F12/F16,T04/T05/T10/T11/T15/T23/T27/T33 acceptance remains. All18findings/36tracks
retain status; full A--G/BOTHchains/native/assurance/7closed-/14publicdays retained.
No install/provider/credentials/signing/funding/deployment/R28/Slot08/Aiken action.

## Legacy TrustManager alternate entry points — 2026-11-03

Defects: standalone truthy mock selection bypassed process policy; status/cache/
name-only selection and CLI display erased simulation provenance; a public
parameterless Phala method emitted constant quote-shaped strings. The known Neuron
constructor already rejected live startup, so this is not evidence of a deployed
proof-to-settlement exploit. The complete textual caller inventory is not dynamic
or deployed type-flow proof.

Bind manager and providers to actual process policy, freeze effective references,
authorize strict boolean mock selection with existing NEURON_MOCK_MODE rules, and
recheck before/after callbacks and cache/list derivation. Build passes off-cache;
clear stale/partial cache on failed policy/callback boundaries. The manager copies
and normalizes provider metadata, never authorizes from provider-supplied verified
markers, and always rejects the unbound proof compatibility method before transport.

Preserve local fixture status/latencies with simulated=true, scope=fixture and
non-authoritative classification. Real diagnostic observations have no capacity
or eligibility authority; get_healthy_providers intentionally returns []. Keep
Automata chain-ID data only as an unverified observation. Actual Layer-4 UI requires
expected provenance, labels simulated/HTTP/unknown results unverified and supplies
no green TEE signal. Public TrustInfo positional fields remain in their original
order; additive fields and to_dict/list markers describe the limited evidence.

Tests must cover direct constructors/methods, invalid/live mode, strict selection,
fresh policy/flag changes, malicious metadata, failed later callbacks, stale cache,
the actual producer->manager->extracted actual UI path and no proof/transport on
unavailable proof calls. These synthetic tests do not import the complete Neuron
application or qualify native dependencies, real providers, hardware or attestation.
The legacy diagnostic body/resource budget remains a separate repair. Process
environment checks are not atomic provider fencing or authenticated policy state.

INV-6 is affected through containment: no fabricated attestation becomes usable;
authentic current root/workload/hardware binding remains unqualified. INV-1--5 and
INV-7--10 enforcement is unchanged, with no fresh qualification claimed. F06/F12/F16,
T04/T05/T10/T11/T15/T23/T27/T33 retain their full criteria; no findings/track status,
economic/48hgovernance restriction or disabled activation changes. Full A--G, BOTH
chains, native workflow, independent assurance and real7-/14-day observation remain.
No provider identities, hardware/verifier/model inputs, custody or human approvals
are fabricated, and no install/provider/signing/funding/deployment authority expands.

## TEE target HTTP reachability probes — 2026-11-03

Engineering resource/privacy/claim correction; NOT READY. Phala, standalone Marlin and
Automata SDK health methods request streamed, no-redirect responses and inspect only
status. They do not read JSON/content/text/raw bodies or iterators. Each acquired response
gets one cleanup attempt before result adoption; a request failing before acquisition
has no returned response to close. Ordinary request/status/close errors are fixed
offline/provider_error output, without provider exception text or repr. Local control
events propagate after cleanup. Phala retains current actual-runtime checks and private
drift precedence over cleanup failures; the standalone clients gain no new policy claim.

Exact integer statuses100--599 are required before formatting. Phala/Marlin2xx means
healthy HTTP reachability;1xx/3xx/4xx/5xx is degraded. Automata retains its exact200 rule;
its JSON-RPC body is not interpreted. Redirect-dependent endpoints may now show degraded.
URLs, RPC request payload, timeouts, constructors and target technology descriptors are
preserved. latency_ms uses monotonic request-to-status time, excluding body and cleanup.
Every result adds verification_scope=http_reachability and
evidence_classification=non-authoritative; legacy result keys remain.

The actual Neuron SDK panel labels endpoint observations as unverified and the TEE
section as HTTP reachability only. Technology is a target description. Missing/mismatched
provenance produces unknown/unverified display rather than a green legacy status. Both
Celestia and TEE panel exception handlers use fixed messages; Bittensor's prior bounded
handler remains. No website status can admit work, establish capacity, certify an enclave,
authenticate a verifier/chain, or close a release gate. No guessed verifier endpoint or
stronger health protocol is introduced.

Caller-owned session defaults may still attach their own Authorization/cookies/proxy
configuration to public health endpoints. This repair does not inspect or strip those
settings and makes no general credential-isolation claim. SDK-owned Phala bearer scope
from source55 remains unchanged. Avoiding unused body consumption does not qualify HTTP
headers, DNS, socket/lower-layer buffering, deadlines, CPU or total peak memory. Real
Requests/urllib3, endpoint identity/redirect behavior, custody/privacy and operational
availability remain unqualified; existing package/native-runner gaps remain.

Synthetic tests exercise actual producers through check_all_tee_health into the extracted
actual Neuron panel with local transport and fake unrelated providers. They do not import
the full Neuron package or establish a deployed caller graph/independent observer. The
prior provider/wallet campaign must be rebound to the changed Neuron source; historical
passes alone do not cover this display. Legacy standalone SDK structure tests now use
local transports with their existing assertions unchanged. Full pytest/native CI remains
pending. Source56 diagnostic body limits/helpers, source54/55 policy/credential/report
controls, root/quorum/layout and all other Neuron behavior remain.

INV-1--INV-10 executable controls unchanged; authentic INV-6 qualification remains open.
Primary F12/F16,T04/T05/T23/T27/T33; native proof/provider/operational tracks retain full
criteria. Economic/48hgovernance/restricted-profile controls unchanged. Full A--G and BOTH
Polygon Amoy/Cardano Pre-Prod retained;13open/0of36verified,NOT READY. Actual tools,
verifier/hardware/fixed workload,DA/observer,custody/privacy/security,dual-chain rehearsals
and7closed/14public actual-day evidence remain required. No acquisition/provider contact/
real credentials/signing/funding/roles/deployment/R28/Slot08/Aiken action occurred.
Historical evidence retains its own exact source/time/scope and counts are not added.

## Legacy TEE diagnostic response-body budget — 2026-11-02

Engineering resource repair; NOT READY. SGX/Nitro diagnostic POSTs request a streamed,
identity-encoded response and disable redirects. Non-200 status, including redirects,
returns provider_status without reading the body. The consumer accepts at most65,536
raw body octets after transfer framing and before content decoding, using read requests
of at most8,192bytes with decode_content=False. It observes EOF before accepting an
exact-limit body and rejects the first over-limit byte without appending it. It does
not trust Content-Length or use response.json/content/text/iter_content as a fallback.
Nonidentity or malformed Content-Encoding is rejected before body reads. Bounded bytes
are decoded as strict UTF-8 and parsed only after EOF; prior response shape checks stay.

These fixed values are a local diagnostic compatibility restriction, not a provider,
hardware, quote or workload maximum. They do not qualify complete process peak memory,
HTTP headers, DNS, deadlines, CPU or lower-layer buffering. Quote inputs, non-live Phat
business outputs, public metadata and health calls retain their separate unresolved
resource requirements. Caller timeouts, real dependencies and provider behavior still
require native qualification; this guard supplies no authenticated verifier or trust.

Every acquired diagnostic response enters cleanup before the first post-return runtime
check, gets one close attempt before claim adoption, and is followed by a fresh runtime
check. Checks after reads precede buffer appends. Local control/cancellation is preserved
and propagates after cleanup; private runtime drift takes precedence over cleanup
failures. Close failure prevents claim adoption but does not prove connection release. Oversize/unsupported encoding
and malformed responses produce fixed bounded errors; provider details, body content,
URLs and credentials are not included. Source55 request-local credential scope and
caller-owned session defaults remain; source54 live-dispatch refusal, ambient policy,
report non-authority, plugin rejection, fixture root checks/quorum/layout are preserved.

Focused tests use synthetic raw-byte streams and local close/read counters. Existing
34test assertion bodies remain unchanged; response fixtures gained raw/header/close
interfaces. These fixtures are not Requests/urllib3/native HTTP or an independent
operational observer. Legacy full pytest/vendor runs remain pending. Design references:
https://requests.readthedocs.io/en/latest/user/advanced/#body-content-workflow
https://requests.readthedocs.io/en/latest/api/#requests.Response.raw
https://urllib3.readthedocs.io/en/stable/reference/urllib3.response.html
Documentation page versions are not installed-version or provenance evidence.

INV-1--INV-10 enforcement unchanged; authentic INV-6 acceptance remains unqualified.
Primary F06/F12/F16 and T04/T05/T23/T27/T33; related authentic proof/manual/formal tracks
retain all requirements. Economic/48hgovernance/restricted controls are unchanged.
Full A--G and BOTH Polygon Amoy/Cardano Pre-Prod retained;13open/0of36verified,NOT READY.
Native/authentic verifier, hardware, fixed workload, DA/observer, custody/privacy/security,
both-chain rehearsals and7closed/14public actual-day evidence remain required. No provider
contact, package acquisition, credentials, signing, funding, roles, deployment or reserved
R28/Slot08/Aiken use occurred. Historical results retain their original source/scope.

## Phala SDK credential request scope — 2026-11-02

Engineering credential-disclosure repair; NOT READY. The SDK no longer installs
its Phala API key on the shared HTTP session. It supplies a request-local Bearer
header only on the configured Phala SGX claim POST and permitted non-live Phat
contract POST. Marlin/Nitro POST, public metadata GET and health GET receive no
SDK-owned Phala credential. Reusing a transport across new client instances does
not overwrite either client's selected key. Non-secret content headers remain.
Both Phala POST routes disable redirects; a3xx response remains an explicit failed
provider result. This changes redirect-dependent compatibility and requires real
provider testing before qualification. No alternative provider or trust fallback.

Caller-owned transport defaults are left untouched. This repair does not certify
custom transports, pre-existing session credentials/cookies, netrc/proxies, endpoint
trust or the real HTTP library. Construct fresh clients/transports after updating;
old objects are not retroactively revoked or sanitized. Provider identities and
credential custody/handling still require reviewed operator/privacy evidence.
Never treat endpoint configuration or an API key as action authorization.

Source54 ambient policy/current-runtime checks, live/mock direct-dispatch refusal,
RPC report non-authority, plugin fail-closed behavior, root/session fixture checks
and exact quorum remain. New tests model session/request header merging using
synthetic tokens and local transports; they observe the explicit redirect option,
not a live server or real redirect-chain behavior. Full vendor/pytest/native gates,
authentic verifier/hardware/workload and current action binding remain unqualified.
Response/input resource limits are a separate unresolved requirement; no provider
size or latency bound is invented by this credential fix.

INV-1--INV-10 controls are unchanged; INV-6 authentic qualification remains open.
F06/F12/F16 and privacy/security tracks require their full existing acceptance.
All economic and48-hour governance/restricted-profile controls remain. Full A--G
and BOTH Polygon Amoy/Cardano Pre-Prod retained;13open/0of36verified, NOT READY.
No real credential, provider contact, acquisition, R28/Slot08/Aiken, signing,
funding, role or deployment action occurred. Earlier evidence retains its original
source/time/scope and is not added to new test counts.

## Legacy Python TEE authentication and action boundary — 2026-11-02

Engineering containment repair; NOT READY. `PhalaTEE.call_phat_contract` and
`execute_python_in_enclave` reject live modes before protected argument reads,
serialization or dispatch. A runtime address and API key do not authorize an
action. Direct mock contract calls also reject without HTTP. Explicit local
script simulation and non-live real-transport compatibility remain non-authoritative.
The old ECDH/confidentiality description is withdrawn: this client implements no
such protocol. An actual application caller for these methods remains unestablished.

Actual process `os.environ` supplies mode and registered mock policy. A supplied
policy/configuration mapping must match it. Supplied `environ` maps deliberately
require valid `VAMS_ENV` and the same enabled registered mock flags; partial
endpoint-only maps reject (use typed endpoint arguments or actual environment).
This is a documented legacy constructor compatibility restriction. Neither can grant local authority to
a live process, and explicit mock selection must match the ambient flag. Effective
policy/mock references are immutable. Fresh checks precede inputs, transport and
result adoption. Checks can reject subsequent work but cannot undo a prior locally
permitted effect or provide atomic fencing against concurrent environment changes.

Legacy SGX/Nitro RPC responses never establish validity or live evidence, even
with HTTP200, `valid:true`, matching root/report data and measurements. A parsed
Boolean is exposed separately as `provider_claim_valid`; malformed/missing binding
fields remain malformed. `usable_as_live_evidence` is always false for this report
protocol, including caller-created objects. Non-mock `TEEProofPlugin` generation
returns invalid/empty rejected output before quote/client/ABI callbacks; verification
returns false before proof inspection. An injected client's claimed trust cannot
authorize it. Local fixtures preserve proof type/layout, SHA3 binding and root-EOA/
session-key checks; their validity remains simulation only. The legacy multi-TEE
helper requires exact integer threshold2 and cannot promote real provider claims.
This does not change the separate Automata DCAP plus EZKL-first backend decision.

Focused SDK/plugin/collector tests use explicit local transports and vendor-symbol,
Keccak and versioned encoding fixtures. They are not native EVM ABI/Keccak, authentic
quotes, hardware, signatures, or independent operational observations. Legacy tests
now select actual ambient fixture policy and reject fabricated live reports. Full
pytest/vendor imports and the frozen native workflow remain pending. The scanner's
TEE oracle must reject unsafe variants; no unrelated guards or workflow are relaxed.

INV-6 is affected: unauthenticated root acceptance is removed, but authentic current
root/action/workload verification still requires qualification. INV-1--5/7--10 and
all economic,48-hour governance and restricted activation controls are unchanged.
F06/F07/F12/F16; T04/T05/T10/T11/T15/T23/T27/T33 remain subject to their full criteria.
Qualified Automata hardware/verifier/collateral/TCB, fixed ONNX/EZKL model/VK, native
bridge, DA/observer, approved runner, custody and human privacy/security manifests
remain UNKNOWN. No fallback, provider contact, credential/signing/funding/deployment,
acquisition or R28/Slot08/Aiken action is authorized by this source repair. Preserve
full A--G and BOTH Polygon Amoy/Cardano Pre-Prod,13open/0of36verified,7actual closed
and14public observation days. Historical evidence retains its original source/scope.

## Named Bittensor wallet setup boundary — 2026-11-02

Engineering containment repair; NOT READY. The constructor binds its optional
wallet name/hotkey selection. When the SDK is available, named-wallet setup rejects
live mode before provider or wallet construction; missing/invalid mode fails through
central policy. Direct _init_subtensor calls use the same boundary. Selection and
effective runtime configuration are checked again before wallet creation and before
adopting its returned object. Setup rejects selector drift; assigning public
fields alone is not a supported identity reconfiguration. Health reports the bound
adopted-wallet label or none, not a changed public label. Construct a new client
for another explicit selection.

No-wallet read-only setup is preserved and cannot promote a callback-injected wallet
name into wallet creation. The unavailable-SDK constructor remains harmless and
constructs no wallet. Controlled test/local/demo setup retains explicit selection
and existing hotkey behavior. Prior wallet references are not implicitly cleared or
revoked. Only the method-private bounded drift rejection escapes the provider catch;
provider public safety/configuration errors retain fixed-warning/disconnected results.
The source52 inference guard is unchanged; the health wallet label is corrected.

Local82cases PASS:11new wallet-boundary cases +71prior INCLUDED. Final before
control82tests/24failedsubcases/0errors retained separately. Actual constructors,
setup/query methods and existing SDK/Sentinel behavior use local vendor/provider/
account/DA/challenge collaborators.0network/process/uncontrolleddependency events;
56AF_UNIX event-loop sockets counted separately. A callback may already construct
a locally permitted wallet object before a later check rejects adoption; tests
record that event instead of claiming it never occurred. These process reads do
not provide atomic fencing against concurrent environment changes.

Source demonstrates a wallet factory call, not whether the real vendor eagerly or
lazily reads key material. No real key, signature, vendor wallet/provider operation,
custody or authentic action approval was exercised. Full vendor imports, approved
independent Linux312/full CI and authentic inference remain required. No new ambient
secret load, signing backend, operator or trust fallback was added. The existing
research mapping remains source52 evidence, not a reproduced security guarantee.

F12/F16 primary; T04/T05/T23/T27/T33. INV-1--INV-10 enforcement unchanged; no economic,
session, proof-root or bridge-control change. Full A--G/BOTH Polygon Amoy and Cardano
Pre-Prod retained:13open/0of36verified,0stagepromotions/actualdays. UNKNOWN native/
provider/observer/workload/custody/privacy/security inputs and all R28/Slot08/Aiken,
acquisition/service/signing/funding/deployment limits remain. Earlier entries retain
their original source/time scope; local passes do not establish release acceptance.

## Direct inference admission boundary — 2026-11-02

Engineering containment repair; NOT READY. Bittensor query_miner now rejects live
modes before time, prompt, wallet, metagraph or transport access. Missing/invalid
modes fail centrally. This corrects the earlier retained-connected-inference
description for the unbound public entrypoint: observations remain read-only, but
live inference needs an authenticated action-bound backend and qualifying workload.
No actual application caller was established by the manifest-covered text inventory.
The public compatibility method cannot accept caller ALLOW metadata as authority.

Controlled test/local/demo behavior remains. Effective runtime configuration is
rechecked before dendrite creation, Synapse prompt release and query dispatch.
A changed configuration stops the next stage; prior locally permitted activity
cannot be undone. Only the method-private bounded drift error escapes the provider
catch. A provider raising public safety/configuration errors retains a bounded
failed InferenceResult. Method signature and read-only methods are unchanged.
This checks runtime configuration, not authenticated governed policy epochs.

Local71cases PASS:10new direct-route/drift cases plus61prior cases INCLUDED.
Final before control71tests/24subcase failures/0errors is retained. Earlier69-case
controls retain their own source/test identities; the initial four harness errors
were missing adjacent unchanged Neuron source, supplied without weakening tests.
Actual SDK/Sentinel classes and extracted Neuron health use controlled vendor,
account/provider/DA/challenge collaborators.0network/process/uncontrolled-dependency
events;56AF_UNIX event-loop sockets counted separately. Local effect counters prove
the denied-entry boundary, not independent operational observation or real inference.
Full SDK imports/pytest, approved independent Linux312/native gates remain pending.

The research decision is recorded once in repair_20261027/
research-inference-policy-20261102.md. It adopts control placement, not a paper's
guarantees or a completed capability interpreter. Common action codecs and local
object protocols are not repurposed as inference authority. Authentic fixed ONNX/
EZKL, provider/admission/current-policy, protected effects, receipts/recovery and
settlement remain required, with no automatic trust fallback or milestone exclusion.

F12/F16 primary; F06/F07/F13 authentic proof/action acceptance remains open.
T04/T05/T23/T27/T33;INV-1--INV-10 enforcement unchanged. Full A--G and BOTH Polygon
Amoy/Cardano Pre-Prod retained:13open/0of36verified, no stage promotion or real days.
All provider/custody/privacy/assurance UNKNOWN inputs and R28/Slot08/Aiken,
acquisition/service/signing/funding/deployment limits remain. Earlier entries retain
their original source/time scope and are not fresh release acceptance.

## Sentinel selected-account identity repair — 2026-11-02

Engineering source; NOT READY. HardwareRegistryClient initializes its selected
account to None and exposes a read-only account_address. A local Sentinel supplied
with signing material uses that selected account address for operator_address and
report sentinelId; it never uses Web3's unrelated default account. Missing, malformed
or zero identity fails explicitly before DA/challenge construction. No supplied
material retains the existing zero placeholder without reading account_address.
Live Sentinel construction still rejects before registry/provider setup. SLA
submission remains unavailable and a requested SLA still makes audit_node false.

This corrects the former registry.web3 attribute mismatch without creating a signer
fallback, setting a default account or authenticating ownership/custody. An address
parsed by a local package does not prove provider, operator or governance identity.
The SDK account_address is None when parsing/configuration is unavailable; Sentinel
does not turn that absence into a different account. Existing contract/read and
local-publication interfaces remain; no wire/signature/proof version changes.

Local61cases PASS:9new selected-identity cases,19existing Sentinel publication cases
and33provider/research cases INCLUDED. Before control61cases had13errors at the
missing property/interface paths; preserved separately. Actual SDK/Sentinel classes
use controlled vendor, account, DA and challenge collaborators. Network/process and
uncontrolled dependency construction events are zero;56local AF_UNIX event-loop
wakeup sockets are separately counted. No real account parsing, credential, signature,
provider/DA publication, native chain, full runtime import or custody proof occurred.
The hash helper remains a fixed lookup and full required pytest/CI remains pending.

F09/F12/F16 and T04/T05/T23/T27/T33 retain acceptance limits; real operator identity,
proof/effect/settlement and privacy assurance remain required. INV-1--INV-10 controls,
restricted disablements and full A--G/BOTH Polygon Amoy and Cardano Pre-Prod scope
remain unchanged.13open/0of36verified, no gate promotion or observation days.
All acquisition/service/signing/funding/deployment/R28/Slot08/Aiken limits remain.
Earlier source/evidence entries retain original time and scope.

## Provider fallback and plugin diagnostics repair — 2026-11-02

Engineering source; NOT READY. Disconnected or failed Bittensor subnet/miner reads
and the offline hardware catalogue authorize their fixture producers through the
central runtime policy. Staging/testnet/production and missing/unknown modes reject
instead of returning fabricated capacity. Local/test/demo fixtures remain available
and carry simulated=true/non-authoritative provenance in records, dictionaries and
hardware summaries. Connected reads remain provider observations, not verified proof.

Hardware fixture IDs now use the same Keccak helper as the SDK's on-chain lookup;
SHA3-256 is not a substitute. The eleven class names match HardwareClasses.sol.
Collateral conversion uses integer multiplication by 10**18 with unchanged nominal
amounts. Display floats remain display-only. No registry terms, fees, rewards,
settlement, supply, staking or custody behavior changes in this slice.

Bittensor health now reports a failed block read as degraded rather than healthy
with zero. The compatibility get_block_number() zero-on-error behavior remains.
The actual Neuron health panel requests counts only after healthy status and labels
them as a simulation or an unverified provider observation. Bittensor caught-error
diagnostics are fixed text. The plugin collector's failure handler neither formats
the exception nor invokes a failed plugin's name callback, and continues collection.
Successful result/proof/metadata and plugin collection/submission separation remain.

Fresh local33tests PASS,0fail/error/skip/network/process:18provider/caller cases plus
15research/trust cases (the prior13 INCLUDED). Before control33tests produced
51subcase failures and1error for the targeted defects; retained separately. Actual
SDK methods and the extracted actual Neuron health method use controlled provider
and vendor symbols. Native Cast produced11class vectors plus the known empty-hash
control in13offline calls; the SDK test uses those fixed values as an explicit
eth_utils symbol fixture. This is not actual eth_utils/Web3/Bittensor import/ABI,
provider/chain/finality qualification, native runner acceptance or full pytest/CI.

Connected inference dispatch is preserved. Protected effects still require
authenticated admission under policy, provider cooperation and valid receipts.
This local campaign establishes no live execution or deployment qualification.
Human review, privacy acceptance and the outstanding external qualification inputs
remain required.

Primary F09/F16 containment/privacy repairs; F12 actual admission/effect evidence
remains open. T04/T05/T23/T27/T33 retain their required qualification boundaries.
INV-1--INV-10 controls unchanged; INV-6 root identity and INV-10 proof/payload
separation remain required. Full A--G/Polygon Amoy AND Cardano Pre-Prod retained:
13open/0of36verified. R28/Slot08/Aiken, acquisition, services, signing, funding and
deployment limits unchanged. Earlier entries retain original source/time scope.

## Research fixtures and unavailable trust submission — 2026-11-02

Integrated engineering source; NOT READY. Parallel search and fixture serialization
now authorize mock use through the central runtime policy at method entry. The
legacy collector has the same outer guard, so its placeholder SGX/identity bytes
cannot escape in staging/testnet/production. Missing/unknown runtime modes reject.
The separate plugin collection method is unchanged; no constructor-wide ban added.

Local result metadata identifies simulation, non-authoritative evidence and the
fixed confidence as fixture-only. The new local envelope discriminator is
vams.parallel-research-simulation.v1; its result_count/fixture_digest/created_at
fields describe a fixture. Old unversioned JSON is not reinterpreted as this
format or as a signed proof/receipt. Raw query text is no longer printed.

Both public submission stubs now raise bounded unavailable failures instead of
printing completion. Existing ZKML and non-authoritative TEE denials remain; all
remaining bundles also reject before signer/RPC/transaction activity. The collection
constructor no longer reads VAMS_PRIVATE_KEY or creates an ambient signer/account;
legacy attributes remain None. Provider-specific initialization remains separate.
An authentic typed action/actor-root-bound backend and finality receipt are still
unimplemented/unqualified; no signer or trust-model fallback was introduced.

Final13focused cases PASS/0fail/error/skip/network/process. They execute actual
client code with explicit vendor/Web3/Phala/plugin symbol fixtures; neither full
vendor imports nor authentic proofs, real provider initialization or transactions
were exercised. Constructor tests use vendor fixtures and an ambient-key-read
tripwire, not actual credentials. Before control13tests/44subcase failures/12errors
is retained; prototype12-case results retain their own source/test identities.
Existing full SDK pytest and actual provider/chain/custody qualification remain.

F09/F12/F16 and T04/T05/T23/T27/T33 trace this SDK/evidence repair; F06/F07/F13
authentic proof/action-binding acceptance remains open. INV-1--INV-10 underlying
controls unchanged, including INV-6 root identity and INV-10 proof/payload separation.
Full A--G/Polygon Amoy AND Cardano Pre-Prod retained:13open/0of36verified.
No custody/provider/privacy/assurance, native runner or readiness gate is cleared.
R28/Slot08/Aiken/acquisition/services/signing/funding/deployment limits unchanged.
Earlier entries retain their original source/time and evidence scope.

## Gateway revocation and SDK error boundaries — 2026-11-02

Integrated engineering source; NOT READY. Gateway replay decisions now use the
maximum of request time, wall time and the durable clock watermark inside the
existing write transaction. Tolerated clock rollback cannot undo an effective
signer revocation or extend expiry. Excess rollback and malformed stored time
still fail closed. Scheduled revocation, skew/retention limits, schema, namespace,
wire format and custody policy are unchanged. Connections explicitly close after
their existing transaction context and if connection setup fails.

The X402 retry and outer interrupt exception boundaries emit fixed safe failure
text. Arbitrary exception/failed-result detail is not logged or returned there;
known local expiry/dispute text, retry/status behavior and successful business
result/proof/provider/cost fields are preserved. Live X402 remains disabled.

Non-author source reviews accept both repairs with limits. Focused local checks:
5SDK cases and7gateway cases PASS, separately bound and not added to historical
counts. Gateway checks use real local WindowsSQLite/signature/auth code with a
synthetic Request/FastAPI import symbols; SDK uses synthetic MMU/provider objects.
These do not qualify full ASGI/ingress, Linux, PostgreSQL, provider effects, log
destinations or privacy approval. Required full gates remain outstanding.

INV-1--INV-10 underlying controls and restricted disablements remain; no economic
activation, new role, service restart, signing/funding or deployment occurred.
Privacy inventory remains unapproved, including pending wider SDK field/sink
review. Cardano upper-bound-v1 timing is already integrated source; native/ledger
qualification is still missing, not a newly unresolved source decision.
Full A--G/Polygon Amoy AND Cardano Pre-Prod retained:13open/0of36verified.
Earlier entries retain their original source/time and evidence scope.

## PG5 replication-role source correction — 2026-11-02

Integrated as inactive/unqualified engineering source; NOT READY. Both the
runtime full-schema guard and explicit migration preflight require the selected
runtime and migration principals to have NOREPLICATION, alongside their prior
forbidden elevated attributes. Missing/malformed values reject as bounded errors.
The shared membership guard preserves denial of all runtime memberships and
rejects a replication-capable role anywhere in either principal's conservative
membership traversal. It does not rely on rolinherit or grant-option assumptions.
No role, grant, table, DDL, live factory or migration was created or altered.

The privilege profile explicitly binds forbidden attributes and migration-role
replication membership denial into MIGRATION5. Prior META/CHECK manifests reject
under the changed profile; no old schema/receipt/state adoption is performed.
The source46 snapshot/session protocol, TLS, role/schema/owner/key/CHECK/ACL/FK/
trigger/RLS controls and bounded UNKNOWN/no retry remain intact. V3/V4 unchanged.

Final combined110local fixture tests PASS/0fail/error/skip/network/process, with
98prior checks INCLUDED. Same-test before control110tests/41subtest failures/
4errors; the errors are old malformed-membership IndexErrors, preserved as
failure evidence. Original108/27failure and108PASS campaigns retain their
earlier test/source identities. Controlled catalogs/driver doubles are not real
PG18 role graphs, replication exposure, MVCC, native integration or qualification.

Actual runtime/migration role and membership manifests, HBA/replication/publication/
slot/cluster configuration, session affinity, server/driver/CA identities and
approved PG18 role mutation/concurrency/restart/WAL/restore campaigns remain
UNKNOWN/unqualified. Source review cannot prove what privileges exist on a host.
No authentic funding/proof/provider/custody/privacy/assurance or readiness gate
is cleared. Full A--G/Polygon Amoy AND Cardano Pre-Prod retained;13open/0of36
verified. R28/Slot08/Aiken/acquisition/service/signing/funding/deployment limits
unchanged. Earlier entries retain original source/time and evidence scope.

## PG5 snapshot-order source correction — 2026-11-02

Integrated as inactive/unqualified engineering source; NOT READY. Runtime schema
verification acquires all eight fixed SUE relation locks before its first SELECT,
including role-only queries. Migration uses a dedicated direct connection and
autocommit session serialization; the blocking lock statement's snapshot ends
before fresh inspection and a new protected SERIALIZABLE transaction.

Existing schemas lock before transactional PID/role/catalog reads. Empty schemas
validate the principal/backend and create all eight tables atomically without
IF NOT EXISTS or partial adoption; own DDL remains visible, and collisions reject.
Backend identity is checked after the wait and before commit. The session lock
spans commit and is released only by closing that dedicated connection. Timeout,
commit or close uncertainty produces bounded UNKNOWN/no retry. No grants, table
lock strength, protected isolation or role/schema controls were weakened.

MIGRATION5 now binds this versioned session/snapshot protocol. An old META profile
rejects rather than being silently adopted. Preserve old schemas, data, encodings,
receipts and source evidence; any actual state migration requires its own reviewed
protocol. This source change executes no database migration or privilege change.

Runtime before-control:86tests/1failure. Migration before-control:94tests/5failures.
Final combined local checks:98PASS/0fail/error/skip/IO (prior86/85 INCLUDED).
These use controlled driver/cursor doubles, not PostgreSQL MVCC or a live race.
Non-author review accepts the named source repair only. Original owner-authorized
findings/reports remain unchanged, with their historical source bindings.

PID equality cannot prove a direct dedicated session or rule out a proxy/pool.
Actual approved PG18 two-session runtime-DDL and fresh/existing migration tests,
correct changed-control rejection/post-lock visibility, session affinity, role/
schema/query-plan/contention/restart/WAL/UNKNOWN behavior and privacy acceptance
remain unqualified. Server/driver/CA/operator/role manifests remain UNKNOWN. The
replication-role profile follow-up remains separate; no extra privileges granted.
No native funding/provider/proof/custody/assurance or readiness gate is cleared.
Full A--G scope for Polygon Amoy AND Cardano Pre-Prod is retained,13open findings/
0of36verified. Live constructors, factory/route/startup exclusions and existing
R28/Slot08/Aiken/acquisition/service/signing/funding/deployment limits remain.
Earlier snapshot-open entries below retain their original source/time scope.

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

## 2026-11-02 - Candidate reservation, immutable work and attempt history

Keep the user's hold-until-authenticated-resolution decision unchanged. Unreachable
providers can keep funds locked indefinitely; no timeout cutoff/adjudicator exists.
Native logical work commits immutable postcondition,input/resource,budget unit and
cost. Its stable operation ID survives retries; each native allocation attempt
appends exact predecessor/proposal/admission commitments instead of replacing an
old row. Signed absence must not regress policy or change root at the same version.

Storage5 is a fresh explicit schema version, not a signed-receipt wire upgrade.
Its actual canonical authority generation uses
`SHA256("VAMS:AUTHORITY-GENERATION:v5\0" || scope.canonical_bytes())`; the signed
proposal authority_context_id is grouping metadata, never a lease or grant.
Current-host policy must independently authenticate the exact scope/resources/
cumulative ceiling before signing and on actual dispatch paths. Delegates cannot
widen it. Initial local reservation and budget debit are atomic; aggregate accounting
must not be wired to an independent writer lacking this same per-attempt reservation.
Terminal completion is retained without payment or a local funding marker. Unknown
funding stays lookup-only, and unresolved old generations cannot consume new budgets.
The journal never authenticates chain finality or changes SETTLEMENTS5.

Schema/catalog checking pins exact source/privilege fingerprints, owner/runtime
principals, verify-full TLS and expected compiled PG18 CHECK definitions from an
independently reviewed build. A live database cannot supply its own expected checks.
MAINTAIN preserves SHARE UPDATE EXCLUSIVE locks without UPDATE on immutable facts;
its maintenance/DoS risk still needs native operational review. No real grants or
database migration were executed. Installation/cutover/retry and authentic native
funding/host/provider mechanisms remain implementation work, not invented endpoints.

Current candidate:927Solidity tests/58suites PASS,0fail/skip (900prior INCLUDED),
offline size gate PASS:ComposedSettlement23,429bytes,ActionDeliveryVerifierV1
18,067bytes under unchanged24576EIP-170limit. Bindings/raw streams:
LATE-44-FULL-04.json and LATE-44-SIZES-07.json in the retained source44 workspace.
Source45:69supplemental Windows3.12 tests PASS,0fail/error/skip, catalog and
transaction doubles with actual public-fixture signature verification; zero
network/process events. Not independent Linux3.12 or real PostgreSQL evidence.
FUNDED-ATTEMPTS-45-11.json / FUNDED-SOURCE-REVIEW-45-R7.json bind exact source.

Source preparation only; NOT integrated, deployed, activated or accepted.
Canonical43 remains 6,735 paths / manifest5a56888dc13d6b0b254c6e8aa9be6f0dbb26a7b55b9f3d75796c974c59e84759.
Full A--G / Polygon Amoy AND Cardano Pre-Prod remains NOT READY;13findings open,
0of36tracks verified. Existing profile,48hgovernance, INV1--10 and restricted
economic disablements remain. Local fixtures are not authentic/live assurance.

Still implement scope5 installation/renewal/cutover and native-resolved successor
admission, paid coordinator and direct-provider enforcement, and authentic host/
native funding-finality backends. Qualify real PG18 schema/roles/locking/concurrency/
restart/WAL; provider effects and retention; all required CI/scans, authentic DCAP/
EZKL/bridge and DA independent retrieval. Custody, observers, providers, approved
runners and independent privacy/security assurance remain UNKNOWN/unqualified.
R28/Slot08/Aiken/acquisition/service/deployment authority is unchanged. Source44/45
integration remains held for the linked runtime repair and combined checks.

# Action, settlement and receipt repair contract

Date: 2026-10-27. Status: implementation review draft. The owner selected the
design direction; independent implementation review, authentic backend
qualification and release approval remain pending. No deployment is authorized.

## Intent and discrepancies

Preserve restricted faucet-only Polygon Amoy **and** Cardano Pre-Prod, modular
Service Blocks, hybrid verifiable memory and the Immortal Execution direction.
The research repair design at `docs/audit/investigation-20261026/ARXIV-REPAIR-DESIGN.md`
motivates mechanisms and tests; papers do not establish VAMS deployment evidence.

The corrected design constrains emergency reward recovery as well as accrual;
reads registry-authoritative fees; uses integer transaction amounts; requires a
consistent 48-hour Cardano delay; and separates asymmetric receipt verification
from signing authority. Policy or authority changes invalidate pending approvals.

Historical code admitted fabricated TEE hashes, caller-supplied fee terms and
role-set proof Booleans. Historical local MAC receipts and score thresholds do
not establish production authority. The repairs below replace selected boundaries;
they do not claim that every runtime, bridge or governance gap is repaired.

## Registry terms, funding and exits

`ComposedSettlement` has immutable registry and delivery-verifier dependencies.
V2 creation reads the actual listing, requiring matching ID, a nonzero builder,
active/verified status, no quarantine and a manifest identity. The expected terms
hash must match the observed builder, fee, manifest and permission commitments.
Accepted allocation terms are snapshotted. Service Block ID zero yields zero
builder recipient, fee and terms commitment.

Builder fee is bounded at 5,000bps and protocol fee stays at 5bps. For gross
provider allocation \(A\), the calculation uses overflow-safe `Math.mulDiv`:

\[
B=\lfloor A b/10000\rfloor,\quad P=\lfloor A\cdot5/10000\rfloor,
\quad V=A-B-P,\quad V+B+P=A.
\]

Escrow and reward accrual require exact incoming token transfers. Reward pending
liability is cumulative credits minus cumulative claims; claims/accrual require
backing, and emergency withdrawal is limited to surplus. Settlement pays builders
directly, without crediting the distributor again for that payment.

Both staking withdrawal paths use matured unbonding. Recovery cannot bypass a
14-day normal or 30-day crisis request or shorten an existing crisis deadline.
Restricted staking enforces zero emission rate and annual budget in code. The
restricted deployment omits ordinary governor/vesting and its proposer grant.
Full activation, custody and economic acceptance remains separate.

## Canonical action and current policy

`ActionContextV1` uses the ASCII domain `VAMS:ACTION-CONTEXT:v1` followed by NUL,
then 21 fixed 32-byte ABI words. Thirteen bytes32 fields bind actor root, provider,
runtime, model, host/domain, workflow, logical intent, action, inputs, policy root,
target, nonce and budget unit. Eight unsigned integers bind root scheme, authority
epoch, policy version, capabilities, budget, issued time, expiry and chain ID.
SHA256 is used; floats, JSON normalization and SHA3 substitutions are excluded.

The 695-byte fixture in `action-context-v1.json` has SHA256
`efd6951ca159fbf351df14023724120c4e70a01ac4941a03933d770de5699573`.
Scheme 1 encodes a left-zero-padded 20-byte EVM root; scheme 2 encodes a
left-zero-padded 28-byte Cardano identity. Current Solidity policy/proof routes
accept scheme 1 only. Rust/Aiken codec source is not native qualification or
Cardano authorization. Existing VIR and local protocol version encodings remain.

`RestrictedTestnetPolicyV1` accepts changes through the exact VAMS timelock runtime
with at least 48 hours. Nothing is initially authorized. Eligibility is the exact
workload/provider/target tuple. Initiator and eligibility edits advance policy and
authority generations. Checks include current root/version/epoch, host/chain,
units, capabilities, budget and time. Actual custody and host manifests are UNKNOWN.

Direct escrow admission applies policy before funds move. Provider-issued delivery
challenges bind the exact allocation/index/provider/agent/terms/token/amount/workload
and current policy generation, with at most ten-minute validity. Claims must match
the issued challenge, logical intent and action; current policy and a qualified
backend must accept. Replay consumption and payment occur atomically. New challenges
invalidate earlier pending ones. Expired allocations retain their refund path.

Complete interception before credential release, signing, dispatch and resume is
unfinished. On-chain delivery recognition and earned-claim payment now have
separate V3 entrypoints; only delivery recognized under current policy before
expiry survives later revocation for payment. Expiry refunds preserve its backing.
Late off-chain receipt reconciliation and full remote effect/payment recovery
remain unimplemented/unqualified; see repair_20261031/EARNED-DELIVERY-V3.md. Sentinel
scores remain observational. Bounded policy is not universal conscience assurance.

## Proof schemes and backend qualification

`ActionDeliveryVerifierV1` selects an explicit pinned backend, validates expected
context/current policy and rejects unknown, false or reverting backends. Strict
ABI-envelope equality rejects trailing or alternative encodings at the router and
adapters. A primitive verifier result alone grants no authority.

`AutomataSgxActionVerifierV1` supports SGX DCAP v3 through a read-only
IQuoteVerifier-shaped boundary. Constructor pins cover backend/router code hashes,
runtime, enclave/signer measurements, minimum SVN and TCB evaluation. Each call
revalidates the exact quote version/router link with bounded canonical getter
responses; see repair_20261101/DCAP-BACKEND-BINDING.md. Verified
report data and a root EOA signature bind context, root, quote and output. DEBUG
enclaves reject. TDX, Nitro, ARM and unsupported quote schemes do not fall back.

Upstream source/build/ABI/dependency identities, compatible hardware, qualified
collateral, TCB/freshness/revocation policy and authentic quotes remain UNKNOWN.
Codehash equality alone does not authenticate a verifier, collateral source or
its upgradeable dependencies. Tests use fabricated DCAP outcomes for boundary
coverage; they are not authentic attestation evidence.

`EzklActionVerifierV1` pins model/circuit commitments and verifier runtime. Its
fixed public layout is 22 instances: eight action-digest u32 limbs, four input
fields, eight context-copy limbs and two output fields. SHA256 of fixed ABI arrays
commits the tensors; the root signature binds context/output/proof/circuit identity.
The actual ONNX model, quantization, circuit/VK/SRS and authentic proof are UNKNOWN.
Qualification must demonstrate that every context/input/output mutation invalidates
the compiled relation. An unused public input is not binding merely because the
adapter supplied it. Other workloads remain ineligible.

Native bridge checkpoint authentication, application inclusion, destination
authorization and durable replay remain separate required work. Actual Mocha/Near
publication/archive and independent exact-byte retrieval remain unqualified. No
committee, mock or structural fallback is selected for an infeasible backend.

## Receipts, migration and privacy

`neuron/signed_receipts.py` introduces v3 secp256k1 ECDSA-SHA256 receipts with low-S
64-byte r||s signatures through `cryptography`. A public-only verifier cannot sign.
Distinct purposes cover admission, fencing update/acknowledgement, effect and fenced
absence; scope binds issuer key, subject, provider, authority/policy generation,
fence and validity. A self-signed key does not establish an authorized issuer.
Historical effect authentication grants no new effect authority.

Production PostgreSQL schemas/migration, provider-atomic effect/deduplication/fencing,
cutover acknowledgement, independent observation and durable recovery are unfinished.
Local v2 MAC receipts must not be reinterpreted as v3 signatures. Explicit schema
versions and migrations are required. An indeterminate outcome stays indeterminate
until authenticated reconciliation; unreachable old writers block unsafe migration.

The Python transaction builder uses explicit integer units, authentic registration
IDs and chain/runtime observations. Display quotes are non-authoritative. V2
creation/claim interfaces replace old unbound creation/claim/proof setters, which
reject. Relayed settled evidence is attributed to its provider root and awards no
unqualified score. Changed non-upgradeable contracts require new instances.

The aggregator's two new mappings consume reserved slots 58–59; its gap moves from
58/43 slots to 60/41 slots with the same exclusive end at 101. Compiler comparison
preserves all ten previous storage entries against the local preserved baseline.
Initializer, unauthorized-upgrade and current-to-current proxy state tests are
separate evidence. None certifies an unknown deployed implementation or live custody.

Context roots, signatures, quotes and commitments can link activity. The fixed
EZKL interface exposes four raw input fields and two output fields in transaction
calldata. ZK verification does not hide those public values. The external additive
privacy inventory is UNREVIEWED: field dispositions, recipients, retention,
database/WAL/backups, keystore and observer review remain required.

## Evidence and invariant disposition

Raw evidence remains outside the checkout under
`C:/Users/aseem/VAMS-mono/VAMS-implementation-20261027`.
The `resume01-*` records retain pre-repair failures, focused/full tests, build sizes
and old/current compiled layouts, including the initial command-formatting failure.
The final full result is `resume01-contracts-final.json`; do not add overlapping
suite counts. Build warnings are retained, not silently suppressed.

INV-6 is affected by the TEE/root repair but authentic backend assurance is still
blocking. INV-9 is affected by funded rewards/backing/recovery and staking exit
repairs, with rewards disabled. INV-1/2/3/4/5/7/8/10 retain their existing controls;
none is promoted to live verification by this slice. Supply remains capped at
\(1\times10^9\); real yield/fiat, Deposit, Slash activation and ExecuteIntent stay
disabled. Cardano's delay amendment does not close authenticated governance defects.

No finding or track status is promoted. Independent Linux Python 3.12, full native,
scanner/frontend/Envoy/operational gates and independent review remain required.
Closed-canary admission requires both chains and all 35 applicable tracks; public
promotion needs all 36, independent assurance and at least seven actual consecutive
closed-canary days, followed by the required 14-day public observation.

### 2026-11-01 owner decision: late-effect liability reservation

The user selected “Reserve funds until authenticated resolution” for completed
work whose receipt arrives after expiry. A future admission/settlement protocol
must reserve admitted obligations before dispatch and retain backing until
authenticated completion or fenced absence. Expiry, timeout or an unreachable
provider alone cannot authorize refund of that reserved amount. An unreachable
provider may keep funds unavailable; no emergency adjudication/release rule,
finite cutoff or provider-timestamp trust is implied by this decision.

Current ComposedSettlement protects only previously recognized earned records;
the required on-chain admission reservation and authenticated terminal-resolution
path are NOT_IMPLEMENTED/NOT_QUALIFIED. Existing code behavior above is historical
implementation scope, not completion of this newly selected requirement. Preserve
current-policy validation for pending work, separate completed claims/refunds,
registry terms, exact conservation and all authentic proof requirements. Actual
host/finality protocol and provider/custody/terminal evidence remain unbound. No
live route, funding, deployment or trust-model fallback is authorized.
