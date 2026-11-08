# Policy reads must not preserve expired dispatch authority

Date: 2026-10-30. Status: integrated, unactivated; 143 copied-source local tests pass; native/authentic/live qualification pending.

## Design basis and discrepancy

This continues Stage D/F, GCA_ACCEPTANCE, the common action/receipt contract,
SIGNER-CONTAINMENT, AUTHORITY-V3, RENEWAL-V4 and ADR-VDSO-001. Policy must be current
before protected effects and pending work must revalidate on resume. The host
contract and current callers were read against36 preserved inputs and a full
6,668-path hash check before design. Heart-Brain research does not qualify policy.

RestrictedTestnetPolicyV1 binds exact governance runtime/delay, root/version/epoch,
domain/chain/units, budgets/capabilities/lifetime and routes. Escrow initiator
eligibility differs from provider-root delivery binding. Do not promote a generic
runtime callback to authenticated policy or reuse the initiator allowlist blindly.
Responsible-host policy/grant/actor/finality/custody readers remain unimplemented.

Current runtime code checked expiry before a policy callback but could reuse the
old timestamp afterward. Slow authenticated reads make that a real caller seam.
The six retained before01 tests all fail without errors/skips: final provider
effect, authority admission/dispatch, scope preparation, V4 renewal and backward
time. They observe actual selected signer calls and mutation statements through
controlled-driver fixtures. They do not simulate native SQL semantics.

## Repair and boundaries

After a successful scope/action policy check, re-read the configured clock, reject
backward time during that validation and recheck the exact scope/proposal interval.
Return fresh time to signing callers. After the final provider lookup reports no
old object, recheck current admission immediately before signing a new effect.
V4 renewals reuse the corrected scope validation. A still-valid delayed policy read
uses fresh receipt time; expiry during final lookup creates no selected new effect.
No timeout refund, reissue, retry, new key, route or persistent state is introduced.
Historical completion/fenced-absence remains separate from new dispatch policy.

These local checks do not make remote chain policy, application time and PG commit
atomic. Clock authenticity, native transactional deadline behavior, fencing races,
current finality, custody, actual provider cooperation and independent observation
require their original qualification campaigns. No live backend is silently enabled.
No committee signature or RPC Boolean substitutes for actual host authentication.

INV-1/2/7/8/9 underlying economic/oracle/supply/reward controls are unchanged.
INV-3/4 session lifetime/whitelists unchanged; effect-expiry enforcement improves.
INV-5 fail-closed requirements stay; INV-6 actor binding stays without a TEE claim;
INV-10 native bridge proof/payload separation is unchanged. Restricted activation
and all original A-G, dual-host and observation requirements remain mandatory.

## Verification

Candidate01 passes141 tests (six new included). Candidate02 passes143 (eight new
included), adding valid-delay timestamp and expiry-during-final-lookup coverage.
Zero failures/errors/skips; network/process audit sees zero attempts. ECDSA uses
fixture keys and SQL uses queued driver calls on local WindowsPython3.12.14 with
existing cryptography50.0.2. No native PG, independent Linux3.12, authentic policy,
clock/finality/custody, live provider or independent assurance follows. Full frozen
workflow, native campaigns, reviewers/privacy/custody and final integration remain.


### Recheck time after policy validation — 2026-10-30

The V3 authority/provider used timestamps captured before a policy callback. Six
regressions reproduced expired admission/effect signing, expired dispatch, scope/
renewal mutation and backward-clock acceptance through that seam. Successful
policy reads now finish with a fresh clock/validity check; backwards time during
validation rejects. Admission/effect receipts use the fresh timestamp, and new
provider effects recheck admission after the final retained-object lookup. V4
renewal inherits the scope check. Completed effects and fenced-absence reads
retain their separate historical reconciliation paths.

POLICY-TIME-CANDIDATE-02: 143 tests pass, zero failures/errors/skips. Earlier135 are
INCLUDED with8 timing tests; candidate141/143 overlap. Tests observe selected
signers and mutation statements, using ECDSA fixture keys and queued driver calls.
No native PostgreSQL, real policy reader, external provider, distributed-clock,
cross-chain finality or independent observation is qualified. Wall-clock checks
are not atomic remote-policy/PG commit guarantees. Source/authenticated clock and
native boundary/crash/concurrency qualification remain required.

The inspected host policy is governed by the exact48h VAMS timelock. Its escrow
initiator and proof-provider root roles must not be confused. Runtime current
policy/grant/renewal callbacks remain abstract: authentic current host policy,
actor consent/finality/custody, remote key/transport isolation and final checkpoint/
settlement integration remain. No signed-policy committee or weaker fallback was
introduced. No contract/storage/wire change, activation or new persistent field.
13findings open and0/36tracks verified; all original A-G/both-chain gates remain.


Canonical verification, 2026-10-30: POLICY-TIME-INTEGRATION completed7 guarded
paths (2new); all6,670source paths checked before exporting21exact inputs.
POLICY-TIME-CANONICAL-COPY-01 passes143tests, zero failures/errors/skips. Previous
135 are INCLUDED with8timing cases. Before01 reproduced6failures/0errors/skips;
candidate141/143 overlap. ECDSA fixture keys/queued driver calls on local Windows
Python3.12.14/cryptography50.0.2; no network/process attempt. Linux3.14 only source/
syntax validation. Contracts/Cardano/workflow/wire/storage schemas unchanged.
No nativePG, authentic host policy/clock/finality/custody, independent observation
or live qualification. No disposition promotions;13open findings/0of36verified.
