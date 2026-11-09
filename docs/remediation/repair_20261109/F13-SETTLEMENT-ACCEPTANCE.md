# F13 settlement: source revalidation and acceptance map (2026-11-09)

Status: **SOURCE-SIDE ACCEPTANCE MAPPED; TWO ITEMS OPEN.** No settlement
source changed today. F13 stays REVALIDATED_OPEN. Readiness is unchanged:
13 findings open, 0 of 36 tracks verified, NOT READY.

## Ledger discrepancy (flag for the findings owner)

The `FINDINGS.json` F13 rationale is stale. It still says `verifyProviderProof`
is a VERIFIER_ROLE-authorized Boolean with no proof binding, citing
`829ab54`. In the current source,
`contracts/src/economic/ComposedSettlement.sol`:

- `verifyProviderProof` always reverts with `LegacyInterfaceDisabled`, and
  VERIFIER_ROLE is checked nowhere.
- Payment requires an on-chain challenge (`issueDeliveryChallenge`) and a
  proof accepted by the immutable `deliveryVerifier`.
- `ActionDeliveryVerifierV1.verifyDelivery` checks that the proof context
  matches the challenge:
  - provider, intent and workload;
  - amount, nonce, issue and expiry times;
  - policy root, version and authority epoch;
  - the target settlement contract.

  It also checks that the action hash commits to the chain, contract,
  allocation, provider, token, amount and workload.
- `RestrictedTestnetPolicyV1.authorizes` also checks the chain ID, host
  domain, budget unit, lifetime and the eligible route.
- The verifier then requires the pinned SGX or EZKL back-end to verify the
  output hash, and returns a replay key that the settlement consumes once.

This record proposes no status change. The rationale text should be updated
by the findings owner after review.

## Acceptance map (current source, Foundry, Linux D1 runner)

The full suite has 1150 tests: 72 suites, 1150 passed, 0 failed. That is the
1141 previous tests plus the 9 new tests in
`test/economic/ComposedSettlementF13Acceptance.t.sol`. All rows below use
the real verifier and policy with a noncryptographic back-end fixture,
except where noted.

| Audit acceptance item | Evidence (test) | Result |
|---|---|---|
| Invalid proof rejects | `SettlementActionPolicy: test_falseBackendProducesZeroTransfer`, `test_noncanonicalOuterProofCannotPay`; `EarnedDeliveryPolicy: test_recordRejectsFalseAndMalformedEvidence` | PASS |
| Stale proof rejects | `SettlementActionPolicy: test_previousChallengeCannotAuthorizeAfterReplacement`, `test_expiredChallengeCannotPayAndRefundRemainsAvailable`, `test_stillUnexpiredChallengeInvalidatedByTimelockedPolicyChange`; `EarnedDeliveryPolicy: test_expiredChallengeCannotBecomeEarned` | PASS |
| Wrong intent rejects | `test_wrongWorkloadAmountRootAndJobProduceZeroTransfers` (job); **new** `test_wrongIntentWithCurrentNonceCannotPay`, `test_proofFromOneAllocationCannotPayAnother` | PASS |
| Wrong provider rejects | `EarnedDeliveryPolicy: test_recordRejectsWrongActor`, `test_earnedClaimCannotRedirectToRelayer`; `ComposedSettlement: test_claimProviderShare_reverts_wrongProvider`; **new** `test_strangerCannotReplaceProvidersChallenge` | PASS |
| Wrong amount rejects | `test_wrongWorkloadAmountRootAndJobProduceZeroTransfers` (budget) | PASS |
| Wrong domain rejects | **new** `test_proofDeclaringAnotherChainCannotPay`, `test_proofTargetingAnotherSettlementCannotPay`, `test_proofFromOneDeploymentCannotPayAnother` | PASS |
| Valid delivery paid once | `test_applicationPolicyPipelineWithFixtureBackend`, `EarnedDeliveryPolicy: test_earnedRecordCannotBeReplacedOrChallengedAgain`; **new** `test_paidRowCannotBeChallengedOrPaidAgain` | PASS |
| Unauthorized verifiers cannot approve | `ComposedSettlement: test_legacyCreationAndVerifierAlwaysReject`; **new** `test_grantedVerifierRoleCannotApproveOrPay` | PASS |
| Every allowed fee configuration leaves a bounded payout | `ComposedSettlement: test_builderMaximumPlusOneRejectsBeforeFunding`, `testFuzz_maxFeeConservesWithoutMultiplicationOverflow`; `EarnedDeliveryAccounting: testFuzz_earnedFeeConservationAndDelayedPayment`, `test_tinyUnitsRemainEarnedDespiteZeroRoundedFees` | PASS |
| Expiry preserves refund | `test_expiredChallengeCannotPayAndRefundRemainsAvailable`; `EarnedDeliveryAccounting: test_expiryRefundWhilePausedRetainsEarnedBacking`; `ObjectSettlementV3` absence refunds; **new** `test_expiryRefundWorksWhilePausedAfterStaleChallenge` | PASS |
| Immutable or governed evidence policy | `deliveryVerifier` is immutable; the verifier pins policy, SGX and EZKL code hashes; policy changes go through the 48-hour timelock (`test_stillUnexpiredChallengeInvalidatedByTimelockedPolicyChange`) | PASS (source) |
| Strict configuration bounds | `MAX_BUILDER_BPS = 5000`; builder share plus fee ≤ 10,000 checked before funding; `MIN/MAX_VALIDITY`; `MAX_PROVIDERS = 20` | PASS (source) |

## Open items

1. **Authentic evidence, external.** Output-hash binding is enforced by the
   SGX or EZKL back-end, and every test here uses a fixture back-end. Real
   DCAP and EZKL verification is F06/F07. Until then, F13 cannot claim
   authentic proof settlement.
2. **Dispute lifecycle: owner decision.** `AllocationStatus.DISPUTED` exists
   and blocks claims, but nothing sets it, so there is no dispute path.
   Today's lifecycle covers:
   - expiry refund of unearned rows;
   - authenticated-absence refunds;
   - earned liabilities that survive expiry and pause.

   No agent-initiated dispute of an evidence-verified delivery exists. Two
   options:
   - **(a)** Declare disputes out of scope for the restricted profile, where
     payment requires authenticated evidence and there is no optimistic
     window. Document DISPUTED as reserved and unreachable.
   - **(b)** Design a bounded dispute window with refund and slashing rules.
     That is an economic change (INV-9 adjacent) needing a design and a
     review.

## Invariants

No source change. INV-9-adjacent settlement backing is exercised by the
existing accounting suites and was not altered.
