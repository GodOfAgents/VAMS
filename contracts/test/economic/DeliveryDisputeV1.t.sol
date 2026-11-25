// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {VAMSToken} from "../../src/token/VAMSToken.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {DeliveryDisputeV1} from "../../src/economic/DeliveryDisputeV1.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {IComposedDeliveryVerifier} from "../../src/economic/IComposedDeliveryVerifier.sol";
import {ActionContextV1} from "../../src/trust/ActionContextV1.sol";
import {RestrictedTestnetPolicyV1} from "../../src/trust/RestrictedTestnetPolicyV1.sol";
import {ActionDeliveryVerifierV1} from "../../src/trust/ActionDeliveryVerifierV1.sol";
import {VAMSTimelockController} from "../../src/governance/VAMSTimelockController.sol";

import {DeliveryDisputeFixture} from "./DeliveryDisputeFixture.sol";

/// Dispute window acceptance (owner decision 10, amended by 10a). Shared fixture:
/// DeliveryDisputeFixture.sol.
contract DeliveryDisputeV1Test is DeliveryDisputeFixture {
    // ---- window ---------------------------------------------------------------

    function test_parametersMatchOwnerDecision10() public view {
        assertEq(disputes.DISPUTE_WINDOW(), 72 hours);
        assertEq(disputes.RESOLUTION_PERIOD(), 14 days);
        assertEq(disputes.BOND_BPS(), 500);
        assertEq(disputes.resolver(), resolver);
        assertEq(disputes.settlement(), address(settlement));
        assertEq(address(disputes.bondToken()), address(token));
        assertEq(disputes.bondFor(ROW), BOND);
        assertEq(disputes.bondFor(1), 1); // rounds up: no free dispute on a tiny row
    }

    function test_paymentHeldForWholeWindowThenReleased() public {
        bytes32 id = create(1); earn(id, 0);
        uint256 recorded = settlement.getEarnedDeliveryV3(id, 0).recordedAt;
        vm.warp(recorded + 72 hours - 1);
        vm.prank(provider);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.DeliveryHeld.selector, id, 0));
        settlement.claimEarnedProviderShareV3(id, 0);
        vm.warp(recorded + 72 hours);
        claim(id, 0);
        assertEq(token.balanceOf(provider), PAYOUT);
        assertEq(token.balanceOf(TREASURY), FEE);
        assertBacking();
    }

    function test_atomicVerifyAndPayIsDisabled() public {
        bytes32 id = create(1);
        vm.prank(provider);
        vm.expectRevert(IComposedSettlement.LegacyInterfaceDisabled.selector);
        settlement.claimProviderShareV2(id, 0, keccak256("output"), hex"01");
    }

    function test_disputeAtOrAfterWindowEndRejects() public {
        bytes32 id = create(1); earn(id, 0);
        vm.warp(settlement.getEarnedDeliveryV3(id, 0).recordedAt + 72 hours);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.DisputeWindowClosed.selector, id, 0));
        dispute(id, 0);
    }

    function test_onlyAgentCanDispute() public {
        bytes32 id = create(1); earn(id, 0);
        address[3] memory others = [provider, stranger, resolver];
        for (uint256 i; i < others.length; ++i) {
            vm.prank(others[i]);
            vm.expectRevert(DeliveryDisputeV1.NotAgent.selector);
            disputes.openDispute(id, 0, keccak256("reason"));
        }
    }

    function test_secondDisputeOnSameRowRejects() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.NotDisputable.selector, id, 0));
        dispute(id, 0);
    }

    function test_unearnedOrPaidRowCannotBeDisputed() public {
        bytes32 id = create(2);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.NotDisputable.selector, id, 1));
        dispute(id, 1);
        earn(id, 0);
        vm.warp(block.timestamp + 72 hours); claim(id, 0);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.NotDisputable.selector, id, 0));
        dispute(id, 0);
    }

    function test_disputeRequiresExactBond() public {
        bytes32 id = create(1); earn(id, 0);
        token.approve(address(disputes), BOND - 1);
        vm.expectRevert();
        dispute(id, 0);
        token.approve(address(disputes), BOND);
        uint256 before = token.balanceOf(address(this));
        dispute(id, 0);
        assertEq(before - token.balanceOf(address(this)), BOND);
        assertEq(disputes.totalBondsHeld(), BOND);
        assertBacking();
    }

    // ---- outcomes -------------------------------------------------------------

    function test_upholdRefundsFullRowAndBondAndRowIsTerminal() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        uint256 before = token.balanceOf(address(this));
        vm.prank(resolver); disputes.resolve(id, 0, true);
        assertEq(token.balanceOf(address(this)) - before, ROW + BOND);
        assertEq(token.balanceOf(provider), 0);
        assertEq(token.balanceOf(TREASURY), 0);
        assertTrue(settlement.refundedProviderShareV3(id, 0));
        vm.warp(block.timestamp + 30 days);
        vm.prank(provider);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.DeliveryHeld.selector, id, 0));
        settlement.claimEarnedProviderShareV3(id, 0);
        vm.prank(provider);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        settlement.issueDeliveryChallenge(id, 0);
        vm.prank(resolver);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.DisputeNotOpen.selector, id, 0));
        disputes.resolve(id, 0, false);
        assertBacking();
        assertEq(settlement.totalEscrowed(), 0);
    }

    function test_rejectReleasesPaymentOnceAndPaysBondToProvider() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        vm.prank(provider);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.DeliveryHeld.selector, id, 0));
        settlement.claimEarnedProviderShareV3(id, 0);
        vm.prank(resolver); disputes.resolve(id, 0, false);
        assertEq(token.balanceOf(provider), BOND);
        claim(id, 0);
        assertEq(token.balanceOf(provider), BOND + PAYOUT);
        assertEq(token.balanceOf(TREASURY), FEE);
        vm.prank(provider);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.ProviderAlreadyClaimed.selector, id, 0));
        settlement.claimEarnedProviderShareV3(id, 0);
        assertBacking();
    }

    function test_onlyResolverCanResolve() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        settlement.grantRole(settlement.VERIFIER_ROLE(), stranger);
        address[4] memory others = [address(this), provider, stranger, address(timelock)];
        for (uint256 i; i < others.length; ++i) {
            vm.prank(others[i]);
            vm.expectRevert(DeliveryDisputeV1.NotResolver.selector);
            disputes.resolve(id, 0, true);
        }
    }

    function test_refundCallbackOnlyFromDisputeContract() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        address[3] memory others = [address(this), resolver, provider];
        for (uint256 i; i < others.length; ++i) {
            vm.prank(others[i]);
            vm.expectRevert(IComposedSettlement.NotDisputeContract.selector);
            settlement.refundUpheldDispute(id, 0);
        }
    }

    // ---- deadline ---------------------------------------------------------------

    /// Owner decision 10a (supersedes P5): timeout releases the payment and transfers the
    /// posted bond to the recorded provider. Demonstrated here: balances only. Whether this
    /// deters a freeze depends on bond size and ownership (not evaluated by this test).
    function test_timeoutReleasesPaymentAndForfeitsBondToProvider() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        uint256 opened = disputes.getDispute(id, 0).openedAt;
        vm.warp(opened + 14 days - 1);
        vm.prank(stranger);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.ResolutionPeriodActive.selector, id, 0));
        disputes.finalizeTimeout(id, 0);
        vm.warp(opened + 14 days);
        uint256 agentBefore = token.balanceOf(address(this));
        uint256 providerBefore = token.balanceOf(provider);
        vm.prank(stranger); disputes.finalizeTimeout(id, 0);
        assertEq(token.balanceOf(address(this)), agentBefore, "agent bond is not returned");
        assertEq(token.balanceOf(provider) - providerBefore, BOND, "provider receives the bond");
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.TIMED_OUT));
        claim(id, 0);
        assertEq(token.balanceOf(provider) - providerBefore, BOND + PAYOUT);
        assertEq(disputes.totalBondsHeld(), 0);
        assertBacking();
    }

    /// The forfeit goes to the provider recorded when the dispute opened, whoever finalizes.
    function test_timeoutBondGoesToRecordedProviderRegardlessOfCaller() public {
        bytes32 id = create(2); earn(id, 0); earn(id, 1); dispute(id, 1);
        vm.warp(disputes.getDispute(id, 1).openedAt + 14 days);
        uint256 p2 = token.balanceOf(provider2);
        uint256 caller = token.balanceOf(stranger);
        vm.prank(stranger); disputes.finalizeTimeout(id, 1);
        assertEq(token.balanceOf(provider2) - p2, BOND);
        assertEq(token.balanceOf(stranger), caller);
        vm.prank(stranger);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.DisputeNotOpen.selector, id, 1));
        disputes.finalizeTimeout(id, 1);
    }

    function test_resolverCannotDecideAfterDeadline() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        vm.warp(disputes.getDispute(id, 0).openedAt + 14 days);
        vm.prank(resolver);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.ResolutionPeriodEnded.selector, id, 0));
        disputes.resolve(id, 0, true);
    }

    // ---- pause and expiry ---------------------------------------------------------

    function test_disputeAndResolutionWorkWhilePausedButPayoutDoesNot() public {
        bytes32 id = create(2); earn(id, 0); earn(id, 1);
        settlement.pause();
        dispute(id, 0);
        vm.prank(resolver); disputes.resolve(id, 0, true);
        vm.warp(block.timestamp + 72 hours);
        vm.prank(provider2);
        vm.expectRevert();
        settlement.claimEarnedProviderShareV3(id, 1);
        settlement.unpause();
        claim(id, 1);
        assertEq(token.balanceOf(provider2), PAYOUT);
        assertBacking();
    }

    function test_expiryRefundsOnlyUnearnedRowsWhileDisputeOpen() public {
        bytes32 id = create(2); earn(id, 0); dispute(id, 0);
        vm.warp(settlement.getComposedAllocation(id).expiresAt + 1);
        uint256 before = token.balanceOf(address(this));
        settlement.refundExpiredComposed(id);
        assertEq(token.balanceOf(address(this)) - before, ROW); // row 1 only
        assertEq(settlement.totalEscrowed(), ROW);
        vm.prank(resolver); disputes.resolve(id, 0, true);
        assertEq(token.balanceOf(address(this)) - before, 2 * ROW + BOND);
        assertEq(settlement.totalEscrowed(), 0);
        assertBacking();
    }

    // ---- conservation ---------------------------------------------------------------

    /// Each row takes one path: undisputed, upheld, rejected or timed out.
    /// Every row's escrow and every bond leave exactly once, and contract
    /// balances always equal their recorded liabilities.
    function testFuzz_everyOutcomeConservesEscrowAndBonds(uint8 outcome0, uint8 outcome1, bool expireFirst) public {
        bytes32 id = create(2); earn(id, 0); earn(id, 1);
        uint8[2] memory outcomes = [outcome0 % 4, outcome1 % 4];
        uint256 agentStart = token.balanceOf(address(this));
        for (uint256 i; i < 2; ++i) if (outcomes[i] != 0) dispute(id, i);
        assertBacking();
        if (expireFirst) {
            vm.warp(settlement.getComposedAllocation(id).expiresAt + 1);
            uint256 beforeRefund = token.balanceOf(address(this));
            settlement.refundExpiredComposed(id); // both rows earned: expiry refunds nothing
            assertEq(token.balanceOf(address(this)), beforeRefund);
        }
        for (uint256 i; i < 2; ++i) {
            if (outcomes[i] == 1) { vm.prank(resolver); disputes.resolve(id, i, true); }
            if (outcomes[i] == 2) { vm.prank(resolver); disputes.resolve(id, i, false); }
        }
        vm.warp(block.timestamp + 14 days);
        for (uint256 i; i < 2; ++i) if (outcomes[i] == 3) disputes.finalizeTimeout(id, i);
        uint256 expectedAgent = agentStart;
        uint256 expectedProviders;
        for (uint256 i; i < 2; ++i) {
            if (outcomes[i] == 1) {
                expectedAgent += ROW;
            } else {
                claim(id, i);
                // Rejected (2) and timed-out (3) disputes both forfeit the bond to the provider.
                bool forfeited = outcomes[i] == 2 || outcomes[i] == 3;
                expectedProviders += PAYOUT + (forfeited ? BOND : 0);
                if (forfeited) expectedAgent -= BOND;
            }
        }
        assertEq(token.balanceOf(address(this)), expectedAgent);
        assertEq(token.balanceOf(provider) + token.balanceOf(provider2), expectedProviders);
        assertEq(token.balanceOf(address(settlement)), 0);
        assertEq(settlement.totalEscrowed(), 0);
        assertEq(disputes.totalBondsHeld(), 0);
        assertBacking();
    }
}
