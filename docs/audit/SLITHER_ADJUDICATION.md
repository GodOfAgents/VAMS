# Slither and callback/lifecycle review

Updated 2026-11-14. The final local candidate reports **0 High, 60 Medium and
28 Optimization** findings with unchanged detector configuration/exclusions.
All 60 current Medium identities and their implicated source hashes match the
previous non-author-reviewed source. The prior checkpoint equality warning is
no longer reported; no new Medium identity appeared. Per-ID records remain in
[`contracts/slither-adjudications.yml`](../../contracts/slither-adjudications.yml).
Optimization findings are counted, not adjudicated in this slice.

## Reproduced checkpoint defects and repair

New lifecycle tests exposed two gaps that the earlier source-only review did
not establish: a challenger-win arbitration could pay the same bond pool again
using other roots' balances; deposit token callbacks could take duplicate bonds
for one submitted root or challenge slot. These are manual lifecycle findings,
not defects inferred merely from an equality warning.

`StateCheckpointRegistryV2` now records dispute consumption separately from root
validity before payout. Invalid roots stay `finalized == false`; successful
operator resolutions remain finalized. Both payouts are exact-once, and failed
token transfers roll state back for retry. All four mutating entrypoints share
`nonReentrant`; submission/challenge state is reserved before token calls.
Bond amounts, deadlines, arbitrator permissions and the six-field checkpoint
getter tuple are unchanged. A new `disputeResolved(root)` getter is additive.
The configured token remains immutable. Unsupported fee-on-transfer/malicious
token deployments are not qualified by these tests.

The legacy ERC-8004 entrypoint remains retired and unconditionally rejects
unqualified attestation registration. No previously deployed immutable instance
is patched by editing this source. Restricted deployment scripts do not select
the checkpoint prototype; no live role, route, slashing or payout is activated.

## Executed regressions and reviews

- 25 new methods: checkpoint lifecycle/token callbacks (13), composed settlement
  callbacks (6), two-phase workflow callbacks/lifecycle (4), nested V3 relay (2).
- Four focused suites: 38 passed, 0 failed/skipped. Full suite: 1,267 passed in
  86 suites, 0 failed/skipped. Counts overlap and must not be summed.
- Final checkpoint tests on old source: 8 passed, 5 failed for replay/deposit
  and payout callback behavior. On repaired source, all 13 pass.
- Both new Heartbeat tests fail when the relay guard is removed only in a private
  offline mutant. The recovery oracle distinguishes the exact reentry denial from
  later signature/read-only failures.
- Size gate passes with warnings retained. StateCheckpoint runtime: 4,224 bytes;
  unchanged ComposedSettlement: 24,401 bytes, only 175 bytes EIP-170 headroom.

Non-author AI source review covers the final checkpoint implementation and the
workflow tests; non-author test review covers the unchanged composed/Heartbeat
tests and strengthened recovery oracle. The checkpoint reviewer authored its
test file and excluded it from review; the primary separately inspected the
test oracles and executed all suites. Two other workers exhausted credits before
their final closeout and were not retried or substituted. These are explicit
authorship/execution limits, not whole-patch independent or human assurance.

The workflow tests characterize authorized callback abort as permitted: every
escrow remains registered and refundable after its expiry, just as for abort
immediately after initiation. A source-only concern about stranded value was
not reproduced. Tests also cover callback-induced preparation followed by a
later escrow failure, full rollback and successful retry. The escrow boundary is
synthetic; actual X402 custody/refund integration remains separate.

Exact commands, failures, streams, source/tool hashes and review records:
[callback/lifecycle repair evidence](../remediation/repair_20261113/CALLBACK-LIFECYCLE-REGRESSIONS.md).
The earlier [source-only review](../remediation/repair_20261113/NONAUTHOR-SLITHER-REVIEW.md)
retains its historical findings and is superseded for these requested gaps.

INV-6 containment and other core invariant enforcement remain unchanged. The
checkpoint repair protects exact-once bond liabilities without changing economic
policy. Zero rewards/emissions, no staking minter, inactive vesting/buyback/
distributions/delegation/slashing/token governor, and frozen-unset DEC parameters
remain approved. Both chains and authentic provider/custody/DCAP, human assurance,
full release gates and actual observation requirements remain. **NOT READY**.
