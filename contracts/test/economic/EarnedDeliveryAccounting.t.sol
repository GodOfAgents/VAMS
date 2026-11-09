// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
// Dispute window (owner decision 10): earned payments are held 72 hours. Tests
// advance the clock across the window for each claim and restore it afterwards,
// so every original timeline and expectation is unchanged.
import {Test} from "forge-std/Test.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {ProviderBondRegistry} from "../../src/economic/ProviderBondRegistry.sol";
import {MockToken, SettlementRegistryFixture, SettlementVerifierFixture} from "./ComposedSettlement.t.sol";

/// Real native bond/settlement arithmetic; token and proof collaborators are fixtures.
contract EarnedDeliveryAccountingTest is Test {
    MockToken internal token;
    ProviderBondRegistry internal bonds;
    ComposedSettlement internal settlement;
    SettlementRegistryFixture internal services;
    SettlementVerifierFixture internal verifier;
    address internal agent = address(0xA6E);
    address internal provider = address(0xB01);
    address internal builder = address(0xB03);
    bytes32 internal constant SERVICE = keccak256("registered-fixture-service");

    function setUp() public {
        vm.warp(1_000_000);
        token = new MockToken();
        bonds = new ProviderBondRegistry();
        bonds.initialize(address(this), address(token), address(0x1A5));
        services = new SettlementRegistryFixture();
        verifier = new SettlementVerifierFixture();
        settlement = new ComposedSettlement(address(this), address(token), address(bonds),
            address(0xFEE), address(services), address(verifier), address(this));
        bonds.grantRole(bonds.ESCROW_ROLE(), address(settlement));
        token.mint(agent, 100_000 ether);
        token.mint(provider, 10_000 ether);
        vm.prank(provider); bonds.registerProvider(10_000 ether, 1_000 ether);
    }

    function create(uint256 count, uint256 amount, uint256 bps) internal returns (bytes32) {
        services.setTerms(SERVICE, builder, bps);
        bytes32 terms = settlement.getServiceTermsHash(SERVICE);
        address[] memory providers = new address[](count);
        uint256[] memory amounts = new uint256[](count);
        bytes32[] memory workloads = new bytes32[](count);
        for (uint256 i; i < count; ++i) {
            providers[i] = provider; amounts[i] = amount; workloads[i] = keccak256("accounting-workload");
        }
        vm.prank(agent);
        return settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("blueprint"), SERVICE, terms, workloads));
    }

    function record(bytes32 id, uint256 index) internal {
        verifier.accept(settlement.getDeliveryContext(id, index));
        vm.prank(provider); settlement.issueDeliveryChallenge(id, index);
        vm.prank(provider); settlement.recordEarnedDeliveryV3(id, index, keccak256("output"), hex"01");
    }

    function pay(bytes32 id, uint256 index) internal {
        vm.prank(provider); vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id, index); vm.warp(block.timestamp - 72 hours);
    }

    function refund(bytes32 id) internal {
        vm.warp(settlement.getComposedAllocation(id).expiresAt + 1);
        vm.prank(agent); settlement.refundExpiredComposed(id);
    }

    function test_recognitionCompletesBondOnceAndMovesNoTokens() public {
        bytes32 id = create(1, 1_000 ether, 0);
        record(id, 0);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(bonds.getBond(provider).activeRequests, 0);
        assertEq(bonds.getBond(provider).totalEarned, 1_000 ether);
        assertEq(token.balanceOf(provider), 0);
        assertEq(settlement.totalEscrowed(), 1_000 ether);
        pay(id, 0);
        assertEq(bonds.getBond(provider).totalEarned, 1_000 ether);
        assertEq(token.balanceOf(provider), 999.5 ether);
    }

    function test_refundPaysOnlyUnearnedPartAndLaterEarnedClaimKeepsTerminalStatus() public {
        bytes32 id = create(3, 1_000 ether, 0);
        record(id, 0); pay(id, 0);
        record(id, 1);
        refund(id);
        assertEq(token.balanceOf(agent), 98_000 ether);
        assertEq(settlement.totalEscrowed(), 1_000 ether);
        assertEq(token.balanceOf(address(settlement)), 1_000 ether);
        assertEq(bonds.getBond(provider).activeRequests, 0);
        assertEq(bonds.getBond(provider).totalEarned, 2_000 ether);
        pay(id, 1);
        assertEq(uint256(settlement.getComposedAllocation(id).status), uint256(IComposedSettlement.AllocationStatus.EXPIRED));
        assertEq(settlement.totalEscrowed(), 0);
        assertEq(token.balanceOf(provider), 1_999 ether);
        vm.prank(agent); vm.expectRevert(); settlement.refundExpiredComposed(id);
        vm.prank(provider); vm.expectRevert(); vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id, 2); vm.warp(block.timestamp - 72 hours);
        assertEq(token.balanceOf(agent), 98_000 ether);
    }

    function test_refundedPortionCannotBecomeEarned() public {
        bytes32 id = create(1, 1_000 ether, 0);
        refund(id);
        vm.prank(provider); vm.expectRevert();
        settlement.recordEarnedDeliveryV3(id, 0, keccak256("output"), hex"01");
        assertFalse(settlement.getEarnedDeliveryV3(id, 0).accepted);
        assertEq(bonds.getBond(provider).totalEarned, 0);
    }

    function test_registryEditsCannotRewriteRecognizedBuilderTerms() public {
        bytes32 id = create(1, 1_000 ether, 5_000);
        record(id, 0);
        services.setTerms(SERVICE, address(0xBAD), 0);
        refund(id);
        pay(id, 0);
        assertEq(token.balanceOf(builder), 500 ether);
        assertEq(token.balanceOf(address(0xBAD)), 0);
        assertEq(token.balanceOf(address(0xFEE)), 0.5 ether);
        assertEq(token.balanceOf(provider), 499.5 ether);
        assertEq(settlement.totalBuilderRevenue(), 500 ether);
        assertEq(settlement.totalEscrowed(), 0);
    }

    function test_failedBondCompletionRollsBackRecordAndReplayConsumption() public {
        bytes32 id = create(1, 1_000 ether, 0);
        verifier.accept(settlement.getDeliveryContext(id, 0));
        vm.prank(provider); settlement.issueDeliveryChallenge(id, 0);
        bytes32 nonce = settlement.getExpectedDelivery(id, 0).nonce;
        vm.mockCallRevert(address(bonds), abi.encodeCall(bonds.completeRequest, (provider, settlement.bondRequestIds(id, 0))), hex"01");
        vm.prank(provider); vm.expectRevert();
        settlement.recordEarnedDeliveryV3(id, 0, keccak256("output"), hex"01");
        assertFalse(settlement.consumedDeliveryNonces(nonce));
        assertFalse(settlement.getEarnedDeliveryV3(id, 0).accepted);
        assertEq(bonds.getBond(provider).pendingSettlements, 1_000 ether);
        vm.clearMockedCalls();
        vm.prank(provider); settlement.recordEarnedDeliveryV3(id, 0, keccak256("output"), hex"01");
        pay(id, 0);
        assertEq(bonds.getBond(provider).totalEarned, 1_000 ether);
    }

    function test_expiryRefundWhilePausedRetainsEarnedBacking() public {
        bytes32 id = create(2, 1_000 ether, 0);
        record(id, 0);
        settlement.pause();
        refund(id);
        assertEq(token.balanceOf(agent), 99_000 ether);
        assertEq(settlement.totalEscrowed(), 1_000 ether);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        settlement.unpause();
        pay(id, 0);
    }

    function test_revokedAdmissionRoleDoesNotBlockEarnedPayoutOrPendingRefund() public {
        bytes32 id = create(2, 1_000 ether, 0);
        record(id, 0);
        bonds.revokeRole(bonds.ESCROW_ROLE(), address(settlement));
        refund(id);
        pay(id, 0);
        assertEq(settlement.totalEscrowed(), 0);
        assertEq(bonds.getBond(provider).totalEarned, 1_000 ether);
    }

    function testFuzz_earnedFeeConservationAndDelayedPayment(uint256 amount, uint256 bps) public {
        amount = bound(amount, 1, 1_000 ether); bps = bound(bps, 0, 5_000);
        bytes32 id = create(1, amount, bps);
        record(id, 0);
        refund(id);
        pay(id, 0);
        uint256 fee = amount * 5 / 10_000;
        uint256 share = amount * bps / 10_000;
        assertEq(token.balanceOf(provider), amount - fee - share);
        assertEq(token.balanceOf(builder), share);
        assertEq(token.balanceOf(address(0xFEE)), fee);
        assertEq(token.balanceOf(provider) + token.balanceOf(builder) + token.balanceOf(address(0xFEE)), amount);
        assertEq(settlement.totalEscrowed(), 0);
        assertEq(bonds.getBond(provider).totalEarned, amount);
    }

    function test_tinyUnitsRemainEarnedDespiteZeroRoundedFees() public {
        bytes32 id = create(1, 1, 5_000);
        record(id, 0);
        refund(id);
        assertEq(settlement.totalEscrowed(), 1);
        pay(id, 0);
        assertEq(token.balanceOf(provider), 1);
        assertEq(token.balanceOf(builder), 0);
        assertEq(token.balanceOf(address(0xFEE)), 0);
        assertEq(settlement.totalEscrowed(), 0);
    }

    function testFuzz_mixedOrderingPreservesEveryEarnedLiability(uint256 count, uint256 amount, uint256 pattern) public {
        count = bound(count, 1, 20);
        amount = bound(amount, 1, 100 ether);
        bytes32 id = create(count, amount, 5_000);
        uint256 delivered;
        uint256 alreadyPaid;
        for (uint256 i; i < count; ++i) {
            uint256 state = (pattern >> (2 * i)) % 3;
            if (state == 0) continue;
            record(id, i);
            ++delivered;
            if (state == 2) { pay(id, i); ++alreadyPaid; }
            assertEq(settlement.totalEscrowed(), (count - alreadyPaid) * amount);
            assertEq(token.balanceOf(address(settlement)), settlement.totalEscrowed());
        }
        if (alreadyPaid < count) {
            refund(id);
            assertEq(settlement.totalEscrowed(), (delivered - alreadyPaid) * amount);
            assertEq(token.balanceOf(address(settlement)), settlement.totalEscrowed());
        }
        for (uint256 i; i < count; ++i) {
            if (settlement.getEarnedDeliveryV3(id, i).accepted && !settlement.getProviderAlloc(id, i).claimed) {
                pay(id, i);
                ++alreadyPaid;
                assertEq(settlement.totalEscrowed(), (delivered - alreadyPaid) * amount);
                assertEq(token.balanceOf(address(settlement)), settlement.totalEscrowed());
            }
        }
        uint256 fee = amount * 5 / 10_000;
        uint256 share = amount * 5_000 / 10_000;
        assertEq(token.balanceOf(agent), 100_000 ether - delivered * amount);
        assertEq(token.balanceOf(provider), delivered * (amount - fee - share));
        assertEq(token.balanceOf(builder), delivered * share);
        assertEq(token.balanceOf(address(0xFEE)), delivered * fee);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(bonds.getBond(provider).activeRequests, 0);
        assertEq(bonds.getBond(provider).totalEarned, delivered * amount);
        assertEq(settlement.totalEscrowed(), 0);
        assertEq(uint256(settlement.getComposedAllocation(id).status), uint256(delivered == count
            ? IComposedSettlement.AllocationStatus.FULLY_CLAIMED : IComposedSettlement.AllocationStatus.EXPIRED));
    }
}
