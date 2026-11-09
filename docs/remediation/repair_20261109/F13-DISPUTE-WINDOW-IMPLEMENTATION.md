# F13 dispute window: implementation record (2026-11-09)

Status: **IMPLEMENTED IN SOURCE; non-author review pending.** This implements
owner decision 10, which approved every parameter in
`F13-DISPUTE-WINDOW-DESIGN.md`. F13 stays REVALIDATED_OPEN: authentic
SGX/EZKL evidence (F06/F07) and independent review remain. Readiness is
unchanged: 13 findings open, 0 of 36 tracks verified, NOT READY.

## Source changes

| File | Change |
|---|---|
| `contracts/src/economic/DeliveryDisputeV1.sol` (new) | Dispute state machine. Constants: `DISPUTE_WINDOW = 72 hours`, `RESOLUTION_PERIOD = 14 days`, `BOND_BPS = 500` (rounded up). Immutable `settlement`, `resolver` and `bondToken`. Functions: `openDispute` (agent only, earned and unpaid rows, before the window ends, exact bond pulled from the caller), `resolve` (resolver only, before the deadline), `finalizeTimeout` (anyone, after the deadline), `releasable` (view used by settlement), and the `totalBondsHeld` accounting |
| `contracts/src/economic/ComposedSettlement.sol` | Constructor takes `_disputeResolver` and deploys `DeliveryDisputeV1(address(this), resolver, token)` into the immutable `disputes`. `_payEarnedDelivery` reverts with `DeliveryHeld` unless `disputes.releasable(...)` and the row is not refunded. New `refundUpheldDispute` (dispute contract only) refunds the full row to the agent and marks it terminal. The atomic `claimProviderShareV2` now reverts with `LegacyInterfaceDisabled` |
| `contracts/src/economic/IComposedSettlement.sol` | Adds `refundUpheldDispute`, plus the `DeliveryHeld` and `NotDisputeContract` errors |
| `contracts/script/DeployRestrictedTestnet.s.sol` | Passes the timelock as the dispute resolver |

### Why the settlement deploys the dispute contract

Each contract needs the other's address, and both are immutable. Deploying
the dispute contract from the settlement constructor breaks the cycle. It
adds bytes only to the settlement's initcode (31,165 B, under the 49,152 B
limit), not to its runtime.

The settlement's runtime is 24,401 B, leaving **175 B** of EIP-170 margin.
That is thin. A future change to `ComposedSettlement` will probably need to
recover space first, for example by removing the historical
`verifiedProviderProofs` write.

### Behaviours covered by the hold

The hold applies to every earned row, however it was earned:
`recordEarnedDeliveryV3`, and object-V3 completions through
`resolveObjectCompletionV3`. The `ObjectSettlementV3` suite failed with
`DeliveryHeld` until its claims waited out the window, which shows the
object path is held too.

## Tests

### New: `contracts/test/economic/DeliveryDisputeV1.t.sol` (17 tests)

These run against the real `ActionDeliveryVerifierV1` and
`RestrictedTestnetPolicyV1`, with a fixture evidence back-end.

| Design §6 item | Test |
|---|---|
| Parameters equal decision 10 | `test_parametersMatchOwnerDecision10` (includes the round-up bond on a 1-unit row) |
| No claim before the window ends; claim after | `test_paymentHeldForWholeWindowThenReleased` (boundary at `recordedAt + 72h − 1` and `+ 72h`) |
| Atomic path disabled | `test_atomicVerifyAndPayIsDisabled` |
| No dispute once the window has closed | `test_disputeAtOrAfterWindowEndRejects` |
| Only the agent can dispute | `test_onlyAgentCanDispute` (provider, stranger, resolver) |
| One dispute per row | `test_secondDisputeOnSameRowRejects` |
| Only earned, unpaid rows | `test_unearnedOrPaidRowCannotBeDisputed` |
| Exact bond required | `test_disputeRequiresExactBond` |
| Uphold: full refund plus bond, row terminal | `test_upholdRefundsFullRowAndBondAndRowIsTerminal` (no claim, no new challenge, no second resolution) |
| Reject: paid once with recorded fees, bond to provider | `test_rejectReleasesPaymentOnceAndPaysBondToProvider` |
| Only the resolver resolves | `test_onlyResolverCanResolve` (admin, provider, holder of a granted VERIFIER_ROLE, the timelock address when it is not the resolver) |
| Refund callback restricted | `test_refundCallbackOnlyFromDisputeContract` |
| Deadline: anyone finalizes, provider paid, bond back to agent | `test_timeoutReleasesPaymentAndReturnsBondToAgent` (boundary at `−1` and the exact deadline) |
| Resolver cannot decide after the deadline | `test_resolverCannotDecideAfterDeadline` |
| Pause | `test_disputeAndResolutionWorkWhilePausedButPayoutDoesNot` |
| Expiry with a dispute open | `test_expiryRefundsOnlyUnearnedRowsWhileDisputeOpen` |
| Conservation (fuzz, 256 runs) | `testFuzz_everyOutcomeConservesEscrowAndBonds`: two rows × {undisputed, upheld, rejected, timed out} × expiry-first. Exact agent and provider balances; settlement balance equals `totalEscrowed`; dispute balance equals `totalBondsHeld`; both end at zero |

`RestrictedTestnetDeployment.t.sol` now also asserts that the deployed dispute
contract is bound to the settlement, uses the timelock as resolver and uses
the VAMS token for bonds.

### Adapted: 52 existing tests across 9 files

These tests used the removed atomic path, or claimed immediately after
recording. They now record, advance the clock across the 72-hour window for
the claim, and restore the clock afterwards. Every original assertion and
timeline is unchanged. Tests that expected a rejection from the atomic call
now expect it from `recordEarnedDeliveryV3`, where the same check runs.

## Gate results (WSL D1 runner)

| Gate | Command | Result |
|---|---|---|
| Foundry | `forge test` | **1167/1167** passed across 73 suites (previously 1150) |
| Sizes | `forge build --sizes` | `ComposedSettlement` 24,401 B (175 B margin); `DeliveryDisputeV1` 4,859 B |
| Slither | CI flags: `--exclude-dependencies --exclude-informational --exclude-low --fail-high` | Exit 0; **0 High**, 62 Medium, 16 Optimization. No result in the new code |

Slither's first run flagged one High in the new code, `arbitrary-send-erc20`:
`openDispute` pulled the bond with `transferFrom(agent, ...)`. That was safe,
because `agent == msg.sender` had already been checked, but the code now
pulls from `msg.sender` directly and the finding is gone. Nothing was
suppressed.

### Runner observation (Slither)

Run from the canonical checkout (`~/code/VAMS-testnet/contracts`), Slither
reports "222 contracts analyzed, 0 results", even without dependency
exclusion. The same tree copied to `~/vams-wt-slither/contracts` reports 78–79
results. The cause is not yet determined. It is probably path-related. A
zero-result Slither run from the canonical path must not be taken as a pass.
The figures above come from the copy. Hosted CI runs from its own checkout
path.

## Invariants

- **INV-9 adjacent (reward and escrow backing).** Each row's escrow leaves
  exactly once, and bonds are accounted separately. Fuzz-tested.
- **INV-1 to INV-8 and INV-10.** No change.

## Remaining

- **Non-author review** of the source, the 52 test adaptations and the
  conservation argument.
- **Resolver signers.** The real signers behind the timelock are UNKNOWN
  (Phase 3 custody).
- **Authentic evidence** (F06/F07).
- **Hosted CI** on an exact commit.
- **Slither path discrepancy.** Investigate the canonical-path result.
- **Ledger.** The F13 rationale in `FINDINGS.json` is stale (see
  `F13-SETTLEMENT-ACCEPTANCE.md`). No status change is proposed here.
