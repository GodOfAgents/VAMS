// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";

// ═══════════════════ Mock Contracts ═══════════════════

contract MockToken {
    mapping(address => uint256) public balances;

    function mint(address to, uint256 amount) external {
        balances[to] += amount;
    }

    function balanceOf(address account) external view returns (uint256) {
        return balances[account];
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balances[msg.sender] >= amount, "Insufficient");
        balances[msg.sender] -= amount;
        balances[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(balances[from] >= amount, "Insufficient");
        balances[from] -= amount;
        balances[to] += amount;
        return true;
    }

    function approve(address, uint256) external pure returns (bool) { return true; }
}

contract MockBondRegistry {
    mapping(address => bool) public bonded;

    function setBonded(address provider, bool _bonded) external {
        bonded[provider] = _bonded;
    }

    function canAcceptRequest(address provider, uint256) external view returns (bool, string memory) {
        return (bonded[provider], bonded[provider] ? "" : "Not bonded");
    }

    // Stubs for interface compliance
    function acceptRequest(address, bytes32, uint256) external {}
    function completeRequest(address, bytes32) external {}
}

// ═══════════════════ Test Suite ═══════════════════

contract ComposedSettlementTest is Test {
    ComposedSettlement public settlement;
    MockToken public token;
    MockBondRegistry public bondRegistry;

    address public admin = address(0xAD);
    address public agent = address(0xAA);
    address public provider1 = address(0xP1);
    address public provider2 = address(0xP2);
    address public provider3 = address(0xP3);
    address public builder = address(0xBB);
    address public treasuryAddr = address(0xTT);

    function setUp() public {
        token = new MockToken();
        bondRegistry = new MockBondRegistry();

        settlement = new ComposedSettlement(
            admin,
            address(token),
            address(bondRegistry),
            treasuryAddr
        );

        // Bond providers
        bondRegistry.setBonded(provider1, true);
        bondRegistry.setBonded(provider2, true);
        bondRegistry.setBonded(provider3, true);

        // Fund agent
        token.mint(agent, 1_000_000 ether);
    }

    // ═══════════════════ Helper ═══════════════════

    function _createAllocation2Providers() internal returns (bytes32) {
        address[] memory providers = new address[](2);
        providers[0] = provider1;
        providers[1] = provider2;

        uint256[] memory amounts = new uint256[](2);
        amounts[0] = 600 ether;
        amounts[1] = 400 ether;

        vm.prank(agent);
        return settlement.createComposedEscrow(
            providers,
            amounts,
            1 hours,
            keccak256("test-blueprint"),
            bytes32(0), // no service block
            0,          // no builder share
            address(0)
        );
    }

    function _createAllocationWithBuilder() internal returns (bytes32) {
        address[] memory providers = new address[](2);
        providers[0] = provider1;
        providers[1] = provider2;

        uint256[] memory amounts = new uint256[](2);
        amounts[0] = 500 ether;
        amounts[1] = 500 ether;

        vm.prank(agent);
        return settlement.createComposedEscrow(
            providers,
            amounts,
            1 hours,
            keccak256("builder-blueprint"),
            keccak256("service-block-1"),
            500, // 5% builder share
            builder
        );
    }

    // ═══════════════════ Creation Tests ═══════════════════

    function test_createComposedEscrow_success() public {
        bytes32 allocId = _createAllocation2Providers();

        IComposedSettlement.ComposedAllocation memory alloc = settlement.getComposedAllocation(allocId);
        assertEq(alloc.agent, agent);
        assertEq(alloc.totalAmount, 1000 ether);
        assertEq(alloc.providerCount, 2);
        assertEq(alloc.claimedCount, 0);
        assertEq(uint8(alloc.status), uint8(IComposedSettlement.AllocationStatus.LOCKED));

        // Check token transfer
        assertEq(token.balanceOf(address(settlement)), 1000 ether);
    }

    function test_createComposedEscrow_3providers() public {
        address[] memory providers = new address[](3);
        providers[0] = provider1;
        providers[1] = provider2;
        providers[2] = provider3;

        uint256[] memory amounts = new uint256[](3);
        amounts[0] = 300 ether;
        amounts[1] = 400 ether;
        amounts[2] = 300 ether;

        vm.prank(agent);
        bytes32 allocId = settlement.createComposedEscrow(
            providers, amounts, 2 hours, keccak256("3p"), bytes32(0), 0, address(0)
        );

        IComposedSettlement.ComposedAllocation memory alloc = settlement.getComposedAllocation(allocId);
        assertEq(alloc.providerCount, 3);
        assertEq(alloc.totalAmount, 1000 ether);
    }

    function test_createComposedEscrow_reverts_zeroProviders() public {
        address[] memory providers = new address[](0);
        uint256[] memory amounts = new uint256[](0);

        vm.prank(agent);
        vm.expectRevert(IComposedSettlement.ZeroProviders.selector);
        settlement.createComposedEscrow(providers, amounts, 1 hours, bytes32(0), bytes32(0), 0, address(0));
    }

    function test_createComposedEscrow_reverts_arrayMismatch() public {
        address[] memory providers = new address[](2);
        providers[0] = provider1;
        providers[1] = provider2;
        uint256[] memory amounts = new uint256[](1);
        amounts[0] = 100 ether;

        vm.prank(agent);
        vm.expectRevert(IComposedSettlement.ArrayLengthMismatch.selector);
        settlement.createComposedEscrow(providers, amounts, 1 hours, bytes32(0), bytes32(0), 0, address(0));
    }

    // ═══════════════════ Claim Tests ═══════════════════

    function test_claimProviderShare_success() public {
        bytes32 allocId = _createAllocation2Providers();

        // Provider 1 claims
        vm.prank(provider1);
        settlement.claimProviderShare(allocId, 0);

        IComposedSettlement.ProviderAlloc memory pAlloc = settlement.getProviderAlloc(allocId, 0);
        assertTrue(pAlloc.claimed);
        assertTrue(pAlloc.claimedAt > 0);

        // Provider should have received payout minus fee
        uint256 expectedFee = (600 ether * 5) / 10_000; // 0.03 ether
        uint256 expectedPayout = 600 ether - expectedFee;
        assertEq(token.balanceOf(provider1), expectedPayout);
        assertEq(token.balanceOf(treasuryAddr), expectedFee);

        // Allocation should be partially claimed
        IComposedSettlement.ComposedAllocation memory alloc = settlement.getComposedAllocation(allocId);
        assertEq(uint8(alloc.status), uint8(IComposedSettlement.AllocationStatus.PARTIALLY_CLAIMED));
    }

    function test_claimProviderShare_allClaimed() public {
        bytes32 allocId = _createAllocation2Providers();

        vm.prank(provider1);
        settlement.claimProviderShare(allocId, 0);

        vm.prank(provider2);
        settlement.claimProviderShare(allocId, 1);

        IComposedSettlement.ComposedAllocation memory alloc = settlement.getComposedAllocation(allocId);
        assertEq(uint8(alloc.status), uint8(IComposedSettlement.AllocationStatus.FULLY_CLAIMED));
        assertTrue(settlement.isFullyClaimed(allocId));
    }

    function test_claimProviderShare_independentClaims() public {
        bytes32 allocId = _createAllocation2Providers();

        // Provider 2 claims first (order doesn't matter)
        vm.prank(provider2);
        settlement.claimProviderShare(allocId, 1);

        IComposedSettlement.ProviderAlloc memory p2Alloc = settlement.getProviderAlloc(allocId, 1);
        assertTrue(p2Alloc.claimed);

        // Provider 1 can still claim
        IComposedSettlement.ProviderAlloc memory p1Alloc = settlement.getProviderAlloc(allocId, 0);
        assertFalse(p1Alloc.claimed);
    }

    function test_claimProviderShare_reverts_wrongProvider() public {
        bytes32 allocId = _createAllocation2Providers();

        vm.prank(provider2); // Wrong provider for index 0
        vm.expectRevert(
            abi.encodeWithSelector(IComposedSettlement.ProviderMismatch.selector, provider1, provider2)
        );
        settlement.claimProviderShare(allocId, 0);
    }

    function test_claimProviderShare_reverts_alreadyClaimed() public {
        bytes32 allocId = _createAllocation2Providers();

        vm.prank(provider1);
        settlement.claimProviderShare(allocId, 0);

        vm.prank(provider1);
        vm.expectRevert(
            abi.encodeWithSelector(IComposedSettlement.ProviderAlreadyClaimed.selector, allocId, 0)
        );
        settlement.claimProviderShare(allocId, 0);
    }

    // ═══════════════════ Builder Revenue Tests ═══════════════════

    function test_claimProviderShare_withBuilderRevenue() public {
        bytes32 allocId = _createAllocationWithBuilder();

        vm.prank(provider1);
        settlement.claimProviderShare(allocId, 0);

        // 500 ether × 5% builder = 25 ether
        // 500 ether × 0.05% fee = 0.025 ether
        // Provider gets 500 - 25 - 0.025 = 474.975 ether
        uint256 builderBal = token.balanceOf(builder);
        assertEq(builderBal, 25 ether, "Builder should receive 5% share");

        uint256 providerBal = token.balanceOf(provider1);
        uint256 expectedFee = (500 ether * 5) / 10_000;
        uint256 expectedPayout = 500 ether - 25 ether - expectedFee;
        assertEq(providerBal, expectedPayout, "Provider payout incorrect");
    }

    // ═══════════════════ Refund Tests ═══════════════════

    function test_refundExpiredComposed_fullRefund() public {
        bytes32 allocId = _createAllocation2Providers();

        // Advance past expiry
        vm.warp(block.timestamp + 2 hours);

        uint256 agentBefore = token.balanceOf(agent);

        vm.prank(agent);
        settlement.refundExpiredComposed(allocId);

        uint256 agentAfter = token.balanceOf(agent);
        assertEq(agentAfter - agentBefore, 1000 ether, "Full refund expected");

        IComposedSettlement.ComposedAllocation memory alloc = settlement.getComposedAllocation(allocId);
        assertEq(uint8(alloc.status), uint8(IComposedSettlement.AllocationStatus.EXPIRED));
    }

    function test_refundExpiredComposed_partialRefund() public {
        bytes32 allocId = _createAllocation2Providers();

        // Provider 1 claims before expiry
        vm.prank(provider1);
        settlement.claimProviderShare(allocId, 0);

        // Advance past expiry
        vm.warp(block.timestamp + 2 hours);

        uint256 agentBefore = token.balanceOf(agent);

        vm.prank(agent);
        settlement.refundExpiredComposed(allocId);

        uint256 agentAfter = token.balanceOf(agent);
        // Only provider 2's 400 ether should be refunded
        assertEq(agentAfter - agentBefore, 400 ether, "Partial refund for unclaimed providers");
    }

    function test_refundExpiredComposed_reverts_notExpired() public {
        bytes32 allocId = _createAllocation2Providers();

        vm.prank(agent);
        vm.expectRevert(
            abi.encodeWithSelector(IComposedSettlement.AllocationNotExpired.selector, allocId)
        );
        settlement.refundExpiredComposed(allocId);
    }

    // ═══════════════════ View Tests ═══════════════════

    function test_getAgentAllocations() public {
        _createAllocation2Providers();
        _createAllocationWithBuilder();

        bytes32[] memory allocs = settlement.getAgentAllocations(agent);
        assertEq(allocs.length, 2);
    }
}
