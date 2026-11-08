// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {MockToken, MockBondRegistry, SettlementRegistryFixture, SettlementVerifierFixture} from "./ComposedSettlement.t.sol";

/// Public status semantics only. Token/bond/proof collaborators are explicit fixtures.
contract CompletionStatusTest is Test {
    ComposedSettlement internal settlement;
    MockToken internal token;
    MockBondRegistry internal bonds;
    SettlementVerifierFixture internal verifier;
    address internal agent = address(0xA6E);

    function setUp() public {
        vm.warp(1_000_000);
        token = new MockToken();
        bonds = new MockBondRegistry();
        verifier = new SettlementVerifierFixture();
        settlement = new ComposedSettlement(address(this), address(token), address(bonds),
            address(0xFEE), address(new SettlementRegistryFixture()), address(verifier));
        token.mint(agent, 1_000_000 ether);
    }

    function provider(uint256 index) internal pure returns (address) {
        return address(uint160(0x1000 + index));
    }

    function create(uint256 count) internal returns (bytes32) {
        address[] memory providers = new address[](count);
        uint256[] memory amounts = new uint256[](count);
        bytes32[] memory workloads = new bytes32[](count);
        for (uint256 i; i < count; ++i) {
            providers[i] = provider(i); amounts[i] = 100 ether;
            workloads[i] = keccak256("status-fixture-workload");
            bonds.setBonded(providers[i], true);
        }
        vm.prank(agent);
        return settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("status-fixture-blueprint"), bytes32(0), bytes32(0), workloads));
    }

    function record(bytes32 id, uint256 index) internal {
        verifier.accept(settlement.getDeliveryContext(id, index));
        vm.prank(provider(index)); settlement.issueDeliveryChallenge(id, index);
        vm.prank(provider(index)); settlement.recordEarnedDeliveryV3(id, index, keccak256("output"), hex"01");
    }

    function pay(bytes32 id, uint256 index) internal {
        vm.prank(provider(index)); settlement.claimEarnedProviderShareV3(id, index);
    }

    function refund(bytes32 id) internal {
        vm.warp(settlement.getComposedAllocation(id).expiresAt + 1);
        vm.prank(agent); settlement.refundExpiredComposed(id);
    }

    function test_unknownAllocationNeverReportsFullyClaimed() public view {
        assertEq(settlement.getComposedAllocation(keccak256("unknown-allocation")).agent, address(0));
        assertFalse(settlement.isFullyClaimed(keccak256("unknown-allocation")));
    }

    function test_zeroAllocationNeverReportsFullyClaimed() public view {
        assertFalse(settlement.isFullyClaimed(bytes32(0)));
    }

    function testFuzz_unknownIdNeverReportsCompletion(bytes32 id) public {
        bytes32 existing = create(1);
        vm.assume(id != existing);
        assertFalse(settlement.isFullyClaimed(id));
    }

    function test_createdUnpaidAllocationIsIncomplete() public {
        assertFalse(settlement.isFullyClaimed(create(2)));
    }

    function test_allEarnedButUnpaidIsIncomplete() public {
        bytes32 id = create(2);
        record(id, 0); record(id, 1);
        assertFalse(settlement.isFullyClaimed(id));
        assertEq(settlement.totalEscrowed(), 200 ether);
    }

    function test_partialPaymentIsIncompleteAndFinalPaymentCompletes() public {
        bytes32 id = create(2);
        record(id, 0); record(id, 1);
        pay(id, 0);
        assertFalse(settlement.isFullyClaimed(id));
        pay(id, 1);
        assertTrue(settlement.isFullyClaimed(id));
        assertEq(settlement.totalEscrowed(), 0);
    }

    function test_fullyRefundedAllocationIsNotFullyClaimed() public {
        bytes32 id = create(2);
        refund(id);
        assertFalse(settlement.isFullyClaimed(id));
    }

    function test_paidAndRefundedMixtureIsNotFullyClaimed() public {
        bytes32 id = create(2);
        record(id, 0); pay(id, 0);
        refund(id);
        assertFalse(settlement.isFullyClaimed(id));
        assertEq(settlement.totalEscrowed(), 0);
    }

    function test_completedPaymentStaysCompleteAfterPauseAndTimeAdvance() public {
        bytes32 id = create(1);
        record(id, 0); pay(id, 0);
        settlement.pause();
        vm.warp(block.timestamp + 30 days);
        assertTrue(settlement.isFullyClaimed(id));
        assertFalse(settlement.isFullyClaimed(keccak256("another-unknown-allocation")));
    }

    function testFuzz_completionRequiresEveryProviderPaid(uint256 count, uint256 unpaid) public {
        count = bound(count, 1, 20); unpaid = bound(unpaid, 1, count);
        bytes32 id = create(count);
        for (uint256 i; i < count; ++i) record(id, i);
        for (uint256 i; i < count - unpaid; ++i) pay(id, i);
        assertFalse(settlement.isFullyClaimed(id));
        for (uint256 i = count - unpaid; i < count; ++i) {
            pay(id, i);
            assertEq(settlement.isFullyClaimed(id), i + 1 == count);
        }
    }
}
