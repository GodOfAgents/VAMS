# F13 dispute window: design proposal (2026-11-09)

Status: **DESIGN ONLY: awaiting owner approval of the parameters in §3.**
No source has changed. This is a high-risk economic change (settlement
timing, refunds, INV-9-adjacent backing), so it is implemented only after
approval, with targeted tests and non-author review.

## 1. Problem

`ComposedSettlement` declares `AllocationStatus.DISPUTED`, but nothing sets
it. Today a verified delivery is earned, and payable, immediately; through
`claimProviderShareV2` it is even paid in the same transaction. The
agent has no way to contest a delivery that passed the evidence check, for
example a correct proof of the wrong work, or evidence later shown to be
compromised. The audit's F13 repair requires "a complete refund/dispute
lifecycle".

## 2. Constraints found

- **Contract size.** `ComposedSettlement` is 23,689 B at runtime, leaving
  only **887 B** under the EIP-170 limit. The dispute state machine cannot
  live inside it. The settlement change has to be a small hook.
- **No slashing.** Owner decision (tokenomics R1): Slash activation stays
  disabled on this profile, so a dispute can only refund or release. It
  never touches provider bonds.
- **No new custodians.** Signer identities are UNKNOWN. The only governed
  authority planned for Polygon is the 3-of-5 Safe behind the 48-hour
  timelock (decision 5 multisig model). No new arbiter keys are invented.
- **Precedent.** `X402EscrowManager` uses a 72-hour window, a
  `RESOLVER_ROLE` and split resolution. It grants the resolver role to the
  admin key, and it has no resolution deadline, so an unresolved dispute
  locks funds forever. This design keeps the 72-hour window and closes both
  gaps.
- **No outside callers.** Nothing outside the tests calls
  `claimProviderShareV2`. Neuron, gateway and frontend do not use it.

## 3. Parameters (owner to approve; recommendation first)

| # | Decision | Recommendation | Alternative |
|---|---|---|---|
| P1 | Dispute window after a delivery is earned | **72 hours**, matching X402 | 24 hours: faster provider payment, less time to detect bad work |
| P2 | Who resolves | **Governance timelock** (3-of-5 Safe + 48 h), set once at deployment | A separate resolver multisig (needs new named signers) |
| P3 | Dispute bond paid by the agent | **5% of the row amount** in VAMS. Returned if upheld or timed out; paid to the provider if rejected | No bond: easier to grief providers with free disputes |
| P4 | Resolution deadline | **14 days** after the dispute opens. Covers the 48-hour timelock plus Safe coordination | 7 days |
| P5 | Outcome if the deadline passes | **Provider is paid** (the evidence was verified) **and the bond goes back to the agent** (the agent is not punished for resolver inaction) | Refund the agent |
| P6 | Outcomes | **Binary**: uphold (full row refund) or reject (normal payment). Split outcomes deferred | X402-style split (more size and fee-rounding cases) |

## 4. Lifecycle

```text
                 record (evidence verified)
  LOCKED row ───────────────────────────────▶ EARNED (held)
                                               │        │
                       agent: dispute (≤ P1,   │        │ P1 elapses, no dispute
                       posts P3 bond)          ▼        ▼
                                         DISPUTED     RELEASABLE ──▶ provider claims (fees as recorded)
                     resolver: uphold ┌──────┴──────┐ resolver: reject, or P4 deadline passes
                                      ▼             ▼
                 REFUNDED: row amount to agent,   RELEASABLE: provider claims;
                 bond back to agent               bond to provider (reject) or to agent (timeout)
```

Rules:

1. **Earning starts the hold.** Every earned delivery is held for P1 from
   `recordedAt`. That covers `recordEarnedDeliveryV3`, the
   `claimProviderShareV2` path and `resolveObjectCompletionV3`. The atomic
   `claimProviderShareV2` becomes record-only, or reverts with
   `LegacyInterfaceDisabled`. Instant payment cannot coexist with a window.
2. **Who can dispute, and when.** Only the allocation's agent, only while
   the row is earned, unpaid and unrefunded, and only before
   `recordedAt + P1`. One dispute per row. Opening a dispute works while
   paused, so a pause cannot run out the agent's window.
3. **Uphold.** The row is marked refunded. The full row amount (no
   protocol or builder fee) goes back to the agent, and the bond is
   returned. The row is terminal: it can never be paid.
4. **Reject or timeout.** The row becomes releasable. The provider claims
   with the fee terms and treasury fixed at recording (unchanged
   behaviour). The bond goes to the provider on rejection, or back to the
   agent on timeout. Anyone may trigger the timeout finalization.
5. **Expiry.** Allocation expiry never refunds an earned or disputed row
   (unchanged). Disputes and resolution do not depend on expiry.
6. **Conservation (INV-9 adjacent).** Each row's escrowed amount leaves the
   contract exactly once, to the provider side (payout plus fees) or to the
   agent. Bonds are held in the dispute contract, separately from escrow,
   and each bond leaves exactly once.

## 5. Implementation shape

- **New `DeliveryDisputeV1` contract.**
  - Immutable settlement address, resolver (the timelock), and P1, P3 and
    P4.
  - Holds bonds and per-row dispute state.
  - Reads the settlement's existing views: `getEarnedDeliveryV3`,
    `getComposedAllocation`, `getProviderAlloc`.
  - Exposes `releasable(allocationId, index)`.
- **`ComposedSettlement` hook**, sized to fit the 887 B margin:
  - A new immutable `disputes` constructor argument.
  - `_payEarnedDelivery` reverts unless `disputes.releasable(...)`.
  - A new `refundUpheldDispute(id, index)`, callable only by `disputes`. It
    marks the row refunded, reduces `totalEscrowed` and transfers the row
    amount to the agent.
  - The atomic V2 claim body is replaced by a revert, which recovers bytes.
    If the margin is still short, remove the historical
    `verifiedProviderProofs` write. Size is measured with
    `forge build --sizes` before acceptance.
- **Interface changes.** `IComposedSettlement` gains `refundUpheldDispute`
  and the `DeliveryHeld` / `DeliveryRefunded` errors. The constructor
  signature changes, so every test setup and both deploy scripts are
  updated mechanically. `ComposedSettlement` is non-upgradeable, so this is
  a new deployment, which suits the testnet (nothing is deployed yet).
- **Existing tests.** Tests that claim immediately after earning will warp
  past P1. Their expectations are otherwise kept.

## 6. Acceptance tests (to write with the implementation)

- **Holds and windows**
  - No claim before P1. A claim succeeds after P1 with no dispute.
  - A dispute after P1 is rejected.
  - A dispute by anyone other than the agent is rejected.
  - A second dispute on the same row is rejected.
- **Bond**
  - A dispute without the exact P3 bond is rejected.
- **Outcomes**
  - Uphold refunds the full row and returns the bond. The provider can
    never claim, re-earn or re-challenge.
  - Reject releases the row and pays the bond to the provider. The provider
    is paid once, with the recorded fees.
  - Resolution by anyone other than the resolver is rejected, including an
    admin or holder of the old VERIFIER_ROLE.
  - Before P4, timeout finalization is rejected. After P4, anyone can
    finalize: the provider is paid and the bond returned to the agent.
- **Pause and expiry**
  - A dispute opened while paused is accepted.
  - Payout stays blocked while paused, as today.
  - Expiry with an earned, disputed row refunds only the unearned rows.
- **Other paths**
  - Object V3 completions are held and disputable the same way.
- **Conservation (fuzz)**
  - Over random sequences of earn, dispute, resolve, timeout, claim and
    expiry, contract balances always equal `totalEscrowed` plus held bonds.
  - Every row exits exactly once.
- **Size**
  - `ComposedSettlement` stays under EIP-170 with recorded margin.

## 7. What this does not do

- No slashing or bond-registry change (owner decision).
- No split outcomes.
- No change to the evidence check.
- Real SGX/EZKL evidence remains F06/F07.
- The resolver's real signers remain UNKNOWN until the Phase 3 custody
  inputs arrive. Until then, resolution can be exercised only in tests.
