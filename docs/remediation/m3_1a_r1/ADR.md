# ADR: F01 authenticated insurance-custody state machine

Date: 2026-09-25
Status: design baseline frozen for M3.1b; not implemented
Scope: Cardano `insurance_fund` only

## Context

The current validator accepts four redeemers through local predicates but does
not authenticate one fund state, require a continuing output, conserve the
controlled value, persist claims or approvals, bind a payout destination, or
consume a durable replay identity. `ClaimDatum` is defined but unused.
`verify_bridge_proof` checks only byte lengths; structural bridge bytes are not
authenticated proof.

This ADR freezes the implementable custody contract for the next slice. It does
not change validators, shared types, blueprints, deployment state, or trust
authority.

## Authenticated fund state

The validator is parameterized by one `fund_policy_id` and `fund_asset_name`.
A one-shot minting policy consumes a configured genesis `OutputReference` and
mints exactly one fund-state token. Initialization creates one validator output
containing that token and the initial datum. Normal transitions require:

1. the spent fund input contains exactly one state token;
2. mint under the state policy is zero;
3. exactly one output at the same validator credential contains exactly one
   state token;
4. no other output contains that token; and
5. the continuing output has one inline, schema-valid fund datum.

This token, not output position or an off-chain indexer, identifies the state.
It is never burned by an ordinary transition. A future migration must be an
explicit, separately reviewed validator/mint-policy operation.

## Datum model

M3.1b introduces versioned types equivalent to:

```text
FundDatumV2 {
  schema_version, total_balance, next_claim_nonce, pending_claims,
  policy_epoch, max_payout_bps, approval_threshold, guardians
}

ClaimRecord {
  claim_id, claim_nonce, claimant_vkh, payout_address, amount,
  evidence_hash, submitted_at, expires_at, policy_epoch, approvers
}
```

`schema_version` is fixed for the script version. `guardians`,
`approval_threshold`, `policy_epoch`, and `max_payout_bps` are immutable in
M3.1b: every continuing datum repeats them exactly. Guardians are unique,
non-empty key hashes; the threshold is within `1..length(guardians)`; and
`max_payout_bps` is fixed at or below 5,000. No governance-update redeemer is
introduced.

`pending_claims` is bounded to 64 records and each approver list is bounded by
the guardian count. Settled, cancelled and expired claims are removed, while
`next_claim_nonce` only increases and cannot be reused. The claim identity is a
domain-separated `blake2b_256` digest of the state asset, `policy_epoch`, nonce,
claimant key hash, payout address, amount, evidence hash, submission time and
expiry. The validator derives it; the submitter does not choose it.

## Value and datum conservation

Let `I` be the complete value of the authenticated fund input and `O` the
complete value of its unique continuing output. Let `ada(x)` be lovelace and
`tokens(x)` all non-lovelace assets including the state token.

- Every input datum satisfies `total_balance = ada(I)`.
- Every output datum satisfies `total_balance = ada(O)`.
- Submit, approve, cancel and expire require `O = I`.
- Payout of `p` requires `ada(O) = ada(I) - p` and
  `tokens(O) = tokens(I)`.
- Fees and unrelated value changes are funded by other inputs; they cannot be
  taken from the fund implicitly.

A payout requires the claimant's net transaction lovelace increase—outputs to
the exact payout address minus inputs controlled by that address—to be at least
the immutable claim amount. It also requires one designated payout output at
that exact address with exactly the claim amount and no non-lovelace assets.
This prevents claimant-funded change from masquerading as the payout.

The amount is positive, at least 1 ADA, no greater than the stored amount or
current balance, and no greater than
`floor(current_balance * max_payout_bps / 10_000)`. The bound is checked at
submission and payout.

## Claim lifecycle and time

Submission includes the claimant key, exact payout address and 32-byte evidence
hash, requires the claimant signature and current nonce, and respects the claim
capacity. Its validity range has finite bounds spanning at most five minutes.
`submitted_at` is the lower bound and expiry is exactly seven days later.

Approval consumes and recreates the fund state unchanged in value, ends no
later than expiry, and adds exactly one signing guardian not already recorded.
Approval count is the on-chain unique approver-list length; an indexer is never
authoritative.

Payout is permissionless after persisted approvals reach the immutable
threshold. It occurs before expiry, pays the immutable address and amount,
removes the claim, decrements the pending count, and preserves the monotonic
nonce. Repeated payout fails because no pending record exists and the nonce
cannot be reused.

Cancellation before expiry requires the claimant signature and removes the
claim without moving value. Expiry is permissionless only when the finite lower
bound is at or after expiry; it also removes the claim without moving value.
Neither transition can lower the nonce or recreate a settled identity.

## Transition matrix

| Transition | Consumed state / asset | Datum before -> after | Value equation | Authorization | Mint / burn | Required outputs; recipient / amount | Time | Replay identity | Expected rejection cases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Genesis initialization | Configured one-shot seed input; no prior fund state | None -> valid `FundDatumV2`, nonce 0, empty claims, immutable guardian policy | Initial datum balance equals exact output lovelace | Seed input consumed; parameters fixed by mint policy | Mint exactly one fund-state token | Exactly one fund output with token and inline datum | Finite initialization interval | One-shot seed `OutputReference` | Missing/duplicate seed, wrong mint amount/name, multiple state outputs, malformed datum, invalid/duplicate guardians or threshold |
| Deposit | Authenticated fund state; bridge authority unresolved | No successful M3.1b transition | No equation accepted until authorization exists | **Fail closed**: structural `bridge_proof` bytes do not authorize | Zero | None in M3.1b | N/A | Future authenticated bridge message/nonce | Any current proof bytes, missing authority, replayed message, wrong payload/amount/domain |
| Claim submission | One fund input with singleton state token | Increment nonce/pending count; append one derived immutable claim | `O = I`; datum balances equal actual lovelace | Exact claimant key signs | Zero | One canonical fund output; no payout | Finite range <= 5 minutes; expiry = lower bound + 7 days | Derived claim digest plus monotonic nonce | Missing/multiple continuation, state-token substitution, changed policy, wrong nonce/identity, duplicate identity, malformed evidence, invalid amount/address/interval, full claim set |
| Guardian approval | One fund input; referenced pending claim | Add one previously absent guardian | `O = I` | Exactly one authorized guardian approval added; unrelated signer alone is insufficient | Zero | One canonical fund output; no payout | Finite upper bound <= expiry | `(claim_id, policy_epoch, guardian_vkh)` | Unknown/wrong claim, duplicate approver, non-guardian, guardian/threshold mutation, expired claim, any value change |
| Payout | One fund input; pending unexpired claim with threshold approvals | Remove claim; decrement pending count; preserve nonce/policy | `ada(O) = ada(I) - amount`; non-ADA assets preserved; claimant net gain >= amount | Persisted approvals meet immutable threshold; execution permissionless | Zero | One fund output plus exact payout output to stored address for stored amount | Finite range ending on/before expiry | Claim removed; nonce non-reusable | Missing/multiple continuation, reduced/redirected fund beyond exact amount, datum mismatch, insufficient approvals, recipient/amount substitution, excessive payout, claimant-funded fake payout, expired/unknown/already-paid claim, invalid interval |
| Claim cancellation | One fund input; pending claim | Remove claim; decrement pending count; preserve nonce/policy | `O = I` | Claimant signs | Zero | One canonical fund output; no payout | Finite range before expiry | Claim consumed; nonce not reused | Non-claimant, unknown/already-settled claim, value change, policy mutation, invalid interval |
| Claim expiry | One fund input; pending claim | Remove claim; decrement pending count; preserve nonce/policy | `O = I` | Permissionless cleanup | Zero | One canonical fund output; no payout | Finite lower bound >= expiry | Claim consumed; nonce not reused | Premature expiry, unknown/already-settled claim, value change, policy mutation, invalid interval |

## F01/F05 dependency decision

The local custody and claim state machine can be implemented independently of
F05, but the cross-chain `Deposit` transition cannot be enabled or used as F01
closure evidence independently. `vams/icb.verify_bridge_proof` only checks
lengths and does not authenticate origin, payload, finality, amount or replay.
This ADR does not choose a bridge signer, Mithril verifier, Rosen authority,
minting authority or governance role.

M3.1b may implement the authenticated fund state and local claim transitions
while making `Deposit` reject unconditionally. F01 remains `REVALIDATED_OPEN`
until either F05 supplies a separately reviewed bridge-message contract covering
domain, amount, finality and replay, or the owner approves a different deposit
trust model in a new ADR. Structural bridge bytes must never be described as
authenticated proof.

## Migration and deployment consequences

The type changes alter datum/redeemer CBOR and the validator program. The new
state-token minting policy and validator produce new policy/script hashes and
addresses; the existing `plutus.json` cannot be reused. Future migration must
identify the old state input, prove its full value, create the new singleton
state exactly once, conserve complete value, and use an independently reviewed
authority. Repository evidence shows no deployed state to migrate.

Off-chain work must add typed builders for genesis, submit, approve, payout,
cancel and expire; query the singleton state token; construct exact inline
datums; calculate net claimant value; set bounded intervals; and reject stale
epochs. Deployment records must bind source and blueprint hashes, policy ID,
script hash/address, genesis input, initial datum, funded UTXO, transaction ID
and multisig policy. An indexer may discover state but cannot authorize it.

## M3.1b native test contract

Tests invoke the public validator with realistic `Transaction` contexts and
actual inputs, outputs, values, datums, mint, signers, intervals and state
asset. Helper-only assertions are insufficient. Required cases include:

- one valid genesis and each enabled transition;
- missing or multiple continuing fund outputs;
- substituted, missing, duplicated, minted or burned state asset;
- reduced/redirected fund value and altered non-ADA assets;
- input/output datum balance mismatches;
- guardian, threshold, payout-cap or policy-epoch mutation;
- duplicate approval and unrelated signer without guardian authority;
- wrong claim nonce or identity;
- payout recipient or amount substitution and claimant-funded fake payout;
- excessive payout at submission and after balance changes;
- expired approval/payout, premature expiry and invalid intervals;
- repeated payout, cancellation or expiry;
- claim-capacity overflow; and
- every structural or unauthorized deposit proof rejected while bridge
  authority remains unresolved.

No permanently failing characterization test belongs in M3.1a.

## Invariant impact

INV-1 and INV-3 through INV-9 are not changed by this design-only slice.
INV-2 executable yield-cap enforcement is unchanged; the proposed custody
equations do not replace the 30% yield invariant. INV-10 is preserved:
`bridge_proof` and `payload_hash` remain distinct and structural non-empty bytes
are not accepted as authenticated evidence. Mock-mode behavior is untouched.
