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

/// Dispute window acceptance (owner decision 10) against the real
/// ActionDeliveryVerifierV1 and RestrictedTestnetPolicyV1. The evidence backend
/// is a noncryptographic fixture; authentic SGX/EZKL evidence is F06/F07.
contract DisputeAcceptingBackendFixture {
    function verifyAction(ActionContextV1.Context calldata, bytes32, bytes calldata) external pure returns (bool) {
        return true;
    }
}
contract DisputeBondFixture {
    function canAcceptRequest(address, uint256) external pure returns (bool, string memory) { return (true, ""); }
    function acceptRequest(address, bytes32, uint256) external {}
    function completeRequest(address, bytes32) external {}
    function cancelRequest(address, bytes32) external {}
}
contract DisputeUnusedRegistryFixture {}

contract DeliveryDisputeV1Test is Test {
    VAMSToken internal token;
    ComposedSettlement internal settlement;
    DeliveryDisputeV1 internal disputes;
    RestrictedTestnetPolicyV1 internal policy;
    VAMSTimelockController internal timelock;
    ActionContextV1.Context internal template;
    address internal provider;
    address internal provider2;
    address internal resolver;
    address internal stranger;
    uint256 internal governanceNonce;
    bytes32 internal workload;
    uint256 internal constant ROW = 100 ether;
    uint256 internal constant BOND = 5 ether; // ceil(5% of ROW)
    uint256 internal constant PAYOUT = 99.95 ether; // ROW minus 5 bps fee, no builder
    uint256 internal constant FEE = 0.05 ether;
    address internal constant TREASURY = address(0xFEE);

    function govern(bytes memory data) internal {
        bytes32 salt = bytes32(++governanceNonce);
        timelock.schedule(address(policy), 0, data, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        timelock.execute(address(policy), 0, data, bytes32(0), salt);
    }

    function setUp() public {
        vm.chainId(80002);
        provider = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-PROVIDER-1")));
        provider2 = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-PROVIDER-2")));
        resolver = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-RESOLVER")));
        stranger = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-STRANGER")));
        token = new VAMSToken(address(this), address(this));
        address[] memory members = new address[](1); members[0] = address(this);
        timelock = new VAMSTimelockController(48 hours, members, members, address(this));
        policy = new RestrictedTestnetPolicyV1(address(timelock), keccak256("amoy-fixture"), keccak256("faucet-base-units"));
        DisputeAcceptingBackendFixture backend = new DisputeAcceptingBackendFixture();
        ActionDeliveryVerifierV1 router = new ActionDeliveryVerifierV1(address(policy), address(policy).codehash,
            address(backend), address(backend).codehash, address(backend), address(backend).codehash);
        settlement = new ComposedSettlement(address(this), address(token), address(new DisputeBondFixture()),
            TREASURY, address(new DisputeUnusedRegistryFixture()), address(router), resolver);
        disputes = settlement.disputes();
        token.approve(address(settlement), type(uint256).max);
        token.approve(address(disputes), type(uint256).max);
        template.runtimeId = keccak256("runtime"); template.modelId = keccak256("model");
        template.workflowId = keccak256("workflow"); template.inputHash = keccak256("exact-input");
        template.hostDomain = policy.hostDomain(); template.budgetUnit = policy.budgetUnit();
        template.target = bytes32(uint256(uint160(address(settlement)))); template.rootScheme = 1;
        template.chainId = block.chainid; template.capabilities = 4; template.budget = ROW;
        workload = ActionContextV1.workloadHash(template);
        govern(abi.encodeCall(policy.configure, (keccak256("policy"), 1, 1, 4, 2 * ROW, 1 hours)));
        govern(abi.encodeCall(policy.setEligibility, (workload, bytes32(uint256(uint160(provider))), template.target, true)));
        govern(abi.encodeCall(policy.setEligibility, (workload, bytes32(uint256(uint160(provider2))), template.target, true)));
        govern(abi.encodeCall(policy.setInitiator, (address(this), true)));
    }

    // ---- helpers ------------------------------------------------------------

    function create(uint256 rows) internal returns (bytes32 id) {
        address[] memory providers = new address[](rows);
        uint256[] memory amounts = new uint256[](rows);
        bytes32[] memory workloads = new bytes32[](rows);
        for (uint256 i; i < rows; ++i) {
            providers[i] = i == 0 ? provider : provider2; amounts[i] = ROW; workloads[i] = workload;
        }
        id = settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("blueprint"), bytes32(0), bytes32(0), workloads));
    }

    function who(uint256 index) internal view returns (address) {
        return index == 0 ? provider : provider2;
    }

    function earn(bytes32 id, uint256 index) internal {
        address p = who(index);
        vm.prank(p); settlement.issueDeliveryChallenge(id, index);
        IComposedDeliveryVerifier.ExpectedDelivery memory e = settlement.getExpectedDelivery(id, index);
        ActionContextV1.Context memory c = template;
        c.actorRoot = bytes32(uint256(uint160(p))); c.providerId = c.actorRoot;
        c.actionHash = e.context; c.intentId = id; c.nonce = e.nonce; c.issuedAt = e.issuedAt;
        c.expiresAt = e.expiresAt; c.policyRoot = e.policyRoot; c.policyVersion = e.policyVersion;
        c.authorityEpoch = e.authorityEpoch;
        vm.prank(p); settlement.recordEarnedDeliveryV3(id, index, keccak256("output"), abi.encode(c, uint8(1), hex"01"));
    }

    function claim(bytes32 id, uint256 index) internal {
        vm.prank(who(index)); settlement.claimEarnedProviderShareV3(id, index);
    }

    function dispute(bytes32 id, uint256 index) internal {
        disputes.openDispute(id, index, keccak256("reason"));
    }

    function assertBacking() internal view {
        assertEq(token.balanceOf(address(settlement)), settlement.totalEscrowed());
        assertEq(token.balanceOf(address(disputes)), disputes.totalBondsHeld());
    }

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

    function test_timeoutReleasesPaymentAndReturnsBondToAgent() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        uint256 opened = disputes.getDispute(id, 0).openedAt;
        vm.warp(opened + 14 days - 1);
        vm.prank(stranger);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.ResolutionPeriodActive.selector, id, 0));
        disputes.finalizeTimeout(id, 0);
        vm.warp(opened + 14 days);
        uint256 before = token.balanceOf(address(this));
        vm.prank(stranger); disputes.finalizeTimeout(id, 0);
        assertEq(token.balanceOf(address(this)) - before, BOND);
        claim(id, 0);
        assertEq(token.balanceOf(provider), PAYOUT);
        assertBacking();
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
                expectedProviders += PAYOUT + (outcomes[i] == 2 ? BOND : 0);
                if (outcomes[i] == 2) expectedAgent -= BOND;
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
