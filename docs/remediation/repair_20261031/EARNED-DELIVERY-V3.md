# Recognized delivery and earned settlement

Status: source candidate with 22 focused local native tests passing. Authentic
proofs, independent review, full qualification and deployment remain pending.
Integration and later native results are recorded separately under EARNED-23.

Earned-delivery repair, 2026-10-31: separate proof recognition from payment
in ComposedSettlement. recordEarnedDeliveryV3 accepts an exact action-bound proof
only under the current policy and unexpired challenge, consumes its replay identity
and completes the original bond reservation once. It moves no tokens. The fixed
output, replay identity, recognition time and fee recipient form an on-chain earned
record. claimEarnedProviderShareV3 pays only that record, to the original provider
and registry-snapshotted builder terms, including after policy changes or expiry.
Pending evidence still requires current-policy validation; protocol pause still
blocks recognition and payouts. Legacy unbound setters/claims remain disabled.

Expiry refunds exclude earned unpaid portions, preserving exact token backing.
Mixed refunded/paid allocations retain EXPIRED status, so refund cannot run twice;
if every provider is paid the status is FULLY_CLAIMED. Failed payment leaves a prior
earned record and its funding intact. V2 remains an atomic verification/payment
route; retaining recognition across payment failure requires the two V3 calls.

Baseline runtime regression reproduces the absent interface. Candidate focused
22native Solidity tests pass, including one256-run fuzz case, with actual policy/
router/timelock and native bond accounting where specified. Proof/backend/token
collaborators are explicitly scoped fixtures. Native canonical/full/sizes/security
results must be read from the matching EARNED-23 run records; no focused result
alone qualifies production proofs, custody, remote execution or either testnet.

This repairs only deliveries recognized on chain while their challenge and current
policy are valid. Late off-chain receipt reconciliation, unavailable providers,
authentic DCAP/EZKL, native bridge and effect/payment recovery remain incomplete.
No receipt/action/VIR/governance version is reinterpreted. Changed non-upgradeable
contracts require new instances and fresh source/runtime-linked release evidence.
The public earned record adds privacy-review inputs; it is not privacy acceptance.
All restrictions and original A--G/BOTH-chain requirements stay. No finding/track
promotion, provider contact, actual signing/funds/roles/deployment is authorized.

Design and accounting

The owner-selected design requires current-policy revalidation for pending work
and a distinct earned-claim path for completed work. The prior implementation and
repair_20261027/ADR.md explicitly identified the missing path: verification and
payment were inseparable. A failing runtime regression reached an unrecognized
recording selector; it establishes feature absence, not a live theft exploit.

Only the existing immutable verifier can establish the new earned record. The
same exact provider, workload, output, context, nonce, policy epoch/version and
challenge checks apply. Recognition is provider-authorized and completes its
original native bond reservation atomically with replay consumption. There is
no administrative certification setter, score substitute or new trust fallback.

Let G be all escrowed gross portions still owed or refundable and E the earned,
unpaid subset. The token balance must cover G and G must cover E. Recognition of
amount A leaves G unchanged and increases E by A. Payment reduces G and E by A;
refund reduces G only by unearned amounts. Builder/protocol/provider distributions
retain the existing floor rounding, 5,000bps maximum and 5bps protocol fee, with
exact conservation. Builder revenue is paid directly, never credited again to
RewardDistributor. Earned treasury identity is snapshotted at recognition.

Recognition, payment and refund use reentrancy guards. Duplicate recognition,
replacement challenges, duplicate payment and refund-after-refund reject. A failed
bond completion rolls back recognition and replay consumption. A failed later
payment rolls back its transfers/counters while preserving the earlier earned
record. Native EVM rollback evidence does not establish remote exactly-once effects.

Compatibility and migration

Existing request/ActionContextV1/proof-envelope/receipt/VIR/governance encodings and
constructor arguments stay unchanged. AllocationStatus numeric values stay fixed;
EXPIRED now means unearned expiry refund is processed and can coexist with earned
unpaid records. Clients must inspect provider claim and earned status to determine
the remainder. V2 still verifies and pays atomically. V3 exposes recording and
payment separately. Non-upgradeable instances must be deployed anew under later
scoped authority; rebuild source/runtime identities and ABI-dependent clients.
No storage-layout or proxy migration acceptance is inferred.

Privacy and remaining entry inputs

The new public EarnedDeliveryV3 has five declared fields: outputHash, replayKey,
recordedAt, feeTreasury and accepted, indexed by allocationId/providerIndex.
Publication exposes linkable receipt commitments, timing, recipients and status
before payout. All seven field/index dispositions, accountable operator, retention
and independent reviewer acceptance are UNKNOWN. This is a new review addendum;
the earlier privacy20 inventory/212 unreviewed rows retain their original scope.
Do not classify commitments or faucet use as public-data consent.

Genuine hardware/workload verification, actor-key custody and reviewed host policy
sources remain prerequisites for live eligibility. Recording must occur under a
still-valid current policy and challenge. A completed off-chain effect without
timely on-chain recognition requires the still-missing authenticated reconciliation
protocol; do not replay expired proof or silently widen authority to pay it. Both
chains, native bridge/DA/PG/provider recovery, complete frozen gates, actual custody,
independent assurance and observation remain required. F13/F12/F16 remain open.

Local evidence includes actual RestrictedTestnetPolicyV1/ActionDeliveryVerifierV1
and timelock callers with a noncryptographic backend fixture, and separate actual
ProviderBondRegistry accounting with token/proof fixtures. These scopes are not
combined into authentic proof, independent review or operational qualification.
