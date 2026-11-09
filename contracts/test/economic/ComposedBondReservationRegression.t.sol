// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
// Dispute window (owner decision 10): earned payments are held 72 hours. Tests
// advance the clock across the window for each claim and restore it afterwards,
// so every original timeline and expectation is unchanged.

import {Test} from "forge-std/Test.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {ProviderBondRegistry} from "../../src/economic/ProviderBondRegistry.sol";
import {IProviderBondRegistry} from "../../src/economic/IProviderBondRegistry.sol";
import {MockToken, SettlementRegistryFixture, SettlementVerifierFixture} from "./ComposedSettlement.t.sol";

/// Actual native bond accounting; token and proof collaborators are explicit
/// fixtures. No hardware/ZK, live custody, signer or deployment qualification.
contract ComposedBondReservationRegressionTest is Test {
    MockToken internal token;
    ProviderBondRegistry internal bonds;
    ComposedSettlement internal settlement;
    SettlementRegistryFixture internal services;
    SettlementVerifierFixture internal verifier;
    address internal agent = address(0xA6E);
    address internal provider = address(0xB01);
    address internal secondProvider = address(0xB02);

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
        _register(provider);
        _register(secondProvider);
    }

    function _register(address who) internal {
        token.mint(who, 10_000 ether);
        vm.prank(who);
        token.approve(address(bonds), 10_000 ether);
        vm.prank(who);
        bonds.registerProvider(10_000 ether, 1_000 ether);
    }

    function _create(uint256 count) internal returns (bytes32) {
        return _createAt(settlement, count);
    }

    function _createAt(ComposedSettlement target, uint256 count) internal returns (bytes32) {
        address[] memory providers = new address[](count);
        uint256[] memory amounts = new uint256[](count);
        bytes32[] memory workloads = new bytes32[](count);
        for (uint256 i; i < count; ++i) {
            providers[i] = provider;
            amounts[i] = 1_000 ether;
            workloads[i] = keccak256("bond-accounting-fixture");
        }
        vm.prank(agent);
        return target.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("same-logical-blueprint"),
            bytes32(0), bytes32(0), workloads));
    }

    function testCreationReservesActualProviderBondCapacity() public {
        _create(1);
        IProviderBondRegistry.ProviderBond memory state = bonds.getBond(provider);
        assertEq(state.pendingSettlements, 1_000 ether);
        assertEq(state.activeRequests, 1);
    }

    function testEleventhOutstandingAllocationCannotReuseBacking() public {
        for (uint256 i; i < 10; ++i) _create(1);
        vm.expectRevert();
        _create(1);
    }

    function testDuplicateProviderEntriesCannotOversubscribeAtomically() public {
        vm.expectRevert();
        _create(11);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(bonds.getBond(provider).activeRequests, 0);
        assertEq(settlement.allocationCount(), 0);
        assertEq(token.balanceOf(agent), 100_000 ether);
        assertEq(token.balanceOf(address(settlement)), 0);
    }

    function testRegistryRejectsDuplicateActiveRequestIdentity() public {
        bonds.grantRole(bonds.ESCROW_ROLE(), address(this));
        bytes32 id = keccak256("durable-request-id");
        bonds.acceptRequest(provider, id, 1_000 ether);
        vm.expectRevert();
        bonds.acceptRequest(provider, id, 1_000 ether);
    }

    function testRegistryRejectsOtherEscrowCompletingRequest() public {
        address other = address(0xE5C);
        bonds.grantRole(bonds.ESCROW_ROLE(), address(this));
        bonds.grantRole(bonds.ESCROW_ROLE(), other);
        bytes32 id = keccak256("owned-request-id");
        bonds.acceptRequest(provider, id, 1_000 ether);
        vm.prank(other);
        vm.expectRevert();
        bonds.completeRequest(provider, id);
    }

    function testRegistryRejectsReuseAfterCompletion() public {
        bonds.grantRole(bonds.ESCROW_ROLE(), address(this));
        bytes32 id = keccak256("completed-request-id");
        bonds.acceptRequest(provider, id, 1_000 ether);
        bonds.completeRequest(provider, id);
        vm.expectRevert();
        bonds.acceptRequest(provider, id, 1_000 ether);
    }

    function _claim(bytes32 id, uint256 index, address who) internal {
        verifier.accept(settlement.getDeliveryContext(id, index));
        vm.prank(who);
        settlement.issueDeliveryChallenge(id, index);
        vm.prank(who);
        settlement.recordEarnedDeliveryV3(id, index, keccak256("output"), hex"01");
        vm.prank(who);
        vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id, index); vm.warp(block.timestamp - 72 hours);
    }

    function testClaimReleasesReservationAndCountsGrossDeliveredValueOnce() public {
        bytes32 id = _create(1);
        _claim(id, 0, provider);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(bonds.getBond(provider).activeRequests, 0);
        assertEq(bonds.getBond(provider).totalEarned, 1_000 ether);
        assertEq(token.balanceOf(provider), 999.5 ether);
        assertEq(token.balanceOf(address(0xFEE)), 0.5 ether);
        vm.prank(provider);
        vm.expectRevert();
        settlement.recordEarnedDeliveryV3(id, 0, keccak256("output"), hex"01");
        assertEq(bonds.getBond(provider).totalEarned, 1_000 ether);
    }

    function testExpiryRefundReleasesReservationWithoutDeliveryEarnings() public {
        bytes32 id = _create(1);
        vm.warp(block.timestamp + 1 hours + 1);
        vm.prank(agent);
        settlement.refundExpiredComposed(id);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(bonds.getBond(provider).activeRequests, 0);
        assertEq(bonds.getBond(provider).totalEarned, 0);
        assertEq(token.balanceOf(agent), 100_000 ether);
    }

    function testPartialClaimAndExpiryReleaseOnlyTheirOwnReservations() public {
        address[] memory providers = new address[](2);
        providers[0] = provider; providers[1] = secondProvider;
        uint256[] memory amounts = new uint256[](2);
        amounts[0] = 1_000 ether; amounts[1] = 1_000 ether;
        bytes32[] memory workloads = new bytes32[](2);
        workloads[0] = keccak256("first"); workloads[1] = keccak256("second");
        vm.prank(agent);
        bytes32 id = settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("partial"), bytes32(0), bytes32(0), workloads));
        _claim(id, 0, provider);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(bonds.getBond(secondProvider).pendingSettlements, 1_000 ether);
        vm.warp(block.timestamp + 1 hours + 1);
        vm.prank(agent);
        settlement.refundExpiredComposed(id);
        assertEq(bonds.getBond(secondProvider).pendingSettlements, 0);
        assertEq(bonds.getBond(provider).totalEarned, 1_000 ether);
        assertEq(bonds.getBond(secondProvider).totalEarned, 0);
        assertEq(token.balanceOf(agent), 99_000 ether);
    }

    function testPendingClaimKeepsOriginalRegistryAfterAdministrativeChange() public {
        bytes32 id = _create(1);
        ProviderBondRegistry replacement = new ProviderBondRegistry();
        replacement.initialize(address(this), address(token), address(0x1A5));
        settlement.setBondRegistry(address(replacement));
        assertEq(address(settlement.allocationBondRegistry(id)), address(bonds));
        _claim(id, 0, provider);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(bonds.getBond(provider).totalEarned, 1_000 ether);
        assertEq(replacement.getBond(provider).totalEarned, 0);
    }

    function testPendingRefundKeepsOriginalRegistryAfterAdministrativeChange() public {
        bytes32 id = _create(1);
        ProviderBondRegistry replacement = new ProviderBondRegistry();
        replacement.initialize(address(this), address(token), address(0x1A5));
        settlement.setBondRegistry(address(replacement));
        vm.warp(block.timestamp + 1 hours + 1);
        vm.prank(agent);
        settlement.refundExpiredComposed(id);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(replacement.getBond(provider).pendingSettlements, 0);
    }

    function testRevokedNewAdmissionRoleDoesNotStrandExpiryRefund() public {
        bytes32 id = _create(1);
        bonds.revokeRole(bonds.ESCROW_ROLE(), address(settlement));
        vm.expectRevert();
        _create(1);
        vm.warp(block.timestamp + 1 hours + 1);
        vm.prank(agent);
        settlement.refundExpiredComposed(id);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(token.balanceOf(agent), 100_000 ether);
    }

    function testOwnerMayCompleteExistingRequestAfterAdmissionRoleRevocation() public {
        bonds.grantRole(bonds.ESCROW_ROLE(), address(this));
        bytes32 id = keccak256("already-admitted-request");
        bonds.acceptRequest(provider, id, 1_000 ether);
        bonds.revokeRole(bonds.ESCROW_ROLE(), address(this));
        bonds.completeRequest(provider, id);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(bonds.requestOwner(id), address(this));
        vm.expectRevert();
        bonds.acceptRequest(provider, keccak256("new-denied-request"), 1_000 ether);
    }

    function testCancelledRequestIdentityRemainsConsumed() public {
        bonds.grantRole(bonds.ESCROW_ROLE(), address(this));
        bytes32 id = keccak256("cancelled-request");
        bonds.acceptRequest(provider, id, 1_000 ether);
        bonds.cancelRequest(provider, id);
        assertEq(bonds.getBond(provider).totalEarned, 0);
        assertEq(bonds.requestOwner(id), address(this));
        vm.expectRevert();
        bonds.acceptRequest(provider, id, 1_000 ether);
    }

    function testRegistryRejectsZeroRequestIdentity() public {
        bonds.grantRole(bonds.ESCROW_ROLE(), address(this));
        vm.expectRevert();
        bonds.acceptRequest(provider, bytes32(0), 1_000 ether);
    }

    function testRegistryRejectsZeroReservationValue() public {
        bonds.grantRole(bonds.ESCROW_ROLE(), address(this));
        vm.expectRevert();
        bonds.acceptRequest(provider, keccak256("zero-value"), 0);
    }

    function testFundingFailureLeavesNoReservationOrAllocation() public {
        agent = address(0xBAD);
        vm.expectRevert();
        _create(1);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(settlement.allocationCount(), 0);
        assertEq(token.balanceOf(address(settlement)), 0);
    }

    function testSameAllocationHashAcrossInstancesHasDistinctReservationIdentities() public {
        ComposedSettlement other = new ComposedSettlement(address(this), address(token), address(bonds),
            address(0xFEE), address(services), address(verifier), address(this));
        bonds.grantRole(bonds.ESCROW_ROLE(), address(other));
        bytes32 first = _create(1);
        bytes32 second = _createAt(other, 1);
        assertEq(first, second);
        bytes32 left = settlement.bondRequestIds(first, 0);
        bytes32 right = other.bondRequestIds(second, 0);
        assertTrue(left != right);
        assertEq(bonds.requestOwner(left), address(settlement));
        assertEq(bonds.requestOwner(right), address(other));
        assertEq(bonds.getBond(provider).pendingSettlements, 2_000 ether);
    }

    function testPausedRegistryStillPermitsOwnedExpiryRefund() public {
        bytes32 id = _create(1);
        bonds.pause();
        vm.expectRevert();
        _create(1);
        vm.warp(block.timestamp + 1 hours + 1);
        vm.prank(agent);
        settlement.refundExpiredComposed(id);
        assertEq(bonds.getBond(provider).pendingSettlements, 0);
        assertEq(token.balanceOf(agent), 100_000 ether);
    }
}
