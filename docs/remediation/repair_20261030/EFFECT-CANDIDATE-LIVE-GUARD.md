# Unqualified effect-candidate live-startup containment

Date2026-10-30. Status: integrated startup containment;155local tests pass; authentic host backend/live qualification incomplete.

The existing V3 provider and V3/storage4 authority are explicitly unactivated
candidates. Their policy classes are interfaces, implemented only by local test
fixtures in this source. A fresh constructor nevertheless accepted those fixtures
when VAMS_ENV was staging, testnet or production. Checking for a subclass did not
authenticate responsible-host state, governance custody, deployed code/finality,
revocation or issuer enrollment. Existing mode-change tests constructed in test
mode before changing the environment, so they did not cover fresh live startup.

Nine before regressions reproduce constructor acceptance: provider, authority3,
authority4 x three live modes. No actual live effect, database or provider was
invoked. Construction alone is the demonstrated gap; neither a database exploit
nor live policy enforcement is claimed.

Both source constructors now reject live RuntimePolicy immediately after strict
central mode parsing. Authority4 inherits the authority3 boundary. Rejection is
before signer verification, policy callbacks, clock use or database work. The
existing test/local/demo modes remain available. No permissive environment flag,
self-declared qualification bit, fixture enrollment or RPC Boolean can enable this
version. Runtime mode immutability and subsequent change detection remain.

Twelve focused cases separate all nine live denials and preserve the three local
component types across test/local/demo. Local callback tripwires observe zero
database connection/migration, signing, policy and clock callbacks during startup.
These are controlled in-process fixture observations, not operationally separate
zero-effect or PostgreSQL evidence. The surrounding155tests pass, including the
previous143 crypto/queued-driver cases. Candidate01 had one missing frozen-vector
input, retained with its raw failure; an exact manifest-matching retained vector
was copied without changing tests or acquiring dependencies. Candidate02 passes
all155with no failures/errors/skips. Counts overlap, not additive.

This is containment of a direct startup path. It does not implement the missing
authenticated current-host policy reader or meet StageD/F acceptance. Future live
admission needs a reviewed native host/code/governance/finality binding, exact
current policy generation/root/routes/bounds/actor revocation, enrolled distinct
authority/provider keys, actor consent and grant membership through real callers.
It also needs explicit pending-approval invalidation/cutover, isolated credential
release, current validation before signing/dispatch/settlement, provider-enforced
deduplication/fencing, native PG and crash/restart/partition/recovery qualification.
Unknown/stale/unavailable inputs must reject, without committee/RPC trust fallback.
Actual manifests, public custody identities and independent reviewers remain UNKNOWN.
Removing this guard or setting a mode alone supplies none of that assurance.

The research mechanism is bounded capability enforcement and control/data
separation in [CaMeL](https://arxiv.org/abs/2503.18813v2). Applying that boundary
to VAMS is a design inference; the paper does not authenticate VAMS policy or
prove native/live safety, universal conscience or independent assurance.

No receipt/action/scope bytes, SQL schema, nonce, fence, budget, payout or economic
rule changes. Existing local earned-effect/absence/refund reconciliation behavior
remains and passes its tests. No qualified live deployment or prior live state
was established; an unactivated candidate is not a live recovery backend. Existing
separate diagnostics/contract claims are not changed. ReceiptVerifier remains
public-only and provider keys do not gain authority signing rights.

INV1/2/7/8/9 underlying economics/oracle/supply/reward controls are unchanged;
budgets are not backing. INV3/4 session expiry/whitelist, INV5 OMS fail-closed,
INV6 actor-root proof binding and INV10 separate bridge proof/payload requirements
remain unchanged. This adds no authentic TEE/ZK/bridge/DA evidence or privacy/custody
acceptance. Restricted economics and Deposit/Slash/ExecuteIntent/fiat/yield remain
disabled. No Aiken/Slot08/R28, install/download, provider contact, external service,
real signing/custody/role change or deployment occurred. AllA-G/BOTHchain and35/36
track,7canary/14public-day requirements remain.13open findings/0verified tracks.


Canonical verification2026-10-30: EFFECT-CANDIDATE-INTEGRATION-18 completed7guarded
paths/2new, retaining preceding dirty files/fullmanifest. Fresh capture checked
all6,685paths and bound37inputs. EFFECT-CANDIDATE-18-CANONICAL-01 passes155local
Python3.12/cryptography50.0.2 tests, zero failures/errors/skips, exit0:12startup
cases plus143previous crypto/controlled-driver cases. Ninebefore failures showed
fresh live construction accepting fixture policies; all nine now reject before
database/migration/signing/policy/clock callbacks. Nonlive test/local/demo remains.
This is local constructor/fixture evidence, not independent live zero-effect,
authenticated policy, real PostgreSQL, TLS/remote key or recovery qualification.

Focused Gitleaks8.30.1 scanned8exact current diff/config inputs offline, exit0 and
empty report. It is not the complete source/history or other frozen scanner gate.
Exact source/tool/package hashes, commands, raw output/exits and limitations are
retained in the EFFECT-CANDIDATE-18 records. Native/fullLinux pytest/Bandit and
other frozen gates remain unrun; this local suite is not CI parity. No need to
repeat untouched Solidity/Cardano checks merely to increase a count. Existing
Cardano141cases remainNOT_RUN; its reference25and Solidity820retain their own scope.

Candidate01's one missing vector input/error remains retained; a matching existing
frozen vector was supplied without test changes or dependency acquisition, and
Candidate02/canonical155pass. An accidentally reused historical capture-helper
filename was recovered byte-for-byte against its original SHA256 from this chat's
retained tool text; transcript content was never executed. The rejected capture
stopped before source reads/writes; canonical source and old results were intact.
New capture paths are distinct. No outstanding process, uncertain retry or bypass.

Current host policy/root/revocation/issuer/custody/finality reader remains missing.
This guard is containment, not its implementation. AllA-G and BOTHchains remain;
13open findings/0of36verified tracks. NoAiken/Slot08/R28/install/download/provider/
external service/real signing/roles/deployment or restricted activation occurred.
