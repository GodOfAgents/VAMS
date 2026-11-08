// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";

import {IServiceBlockRegistry} from "../../src/interfaces/IServiceBlockRegistry.sol";
import {IComposedDeliveryVerifier} from "../../src/economic/IComposedDeliveryVerifier.sol";

// Explicit unit-test doubles, never deployment backends.
contract SettlementRegistryFixture {
    mapping(bytes32 => IServiceBlockRegistry.ServiceBlock) private blocks;
    function setTerms(bytes32 id, address builder, uint256 bps) external {
        IServiceBlockRegistry.ServiceBlock storage b = blocks[id];
        b.blockId = id; b.builder = builder; b.revenueShareBps = bps;
        b.isVerified = true; b.isActive = true;
        b.manifestHash = keccak256("manifest"); b.manifestVersion = 1; b.manifestSigner = builder;
    }
    function quarantine(bytes32 id) external { blocks[id].isQuarantined = true; }
    function getServiceBlock(bytes32 id) external view returns (IServiceBlockRegistry.ServiceBlock memory) {
        return blocks[id];
    }
}
contract SettlementVerifierFixture {
    mapping(bytes32 => bool) private accepted;
    bool public admit = true;
    function setAdmission(bool value) external { admit = value; }
    function challengePolicy(address, bytes32, uint256) external pure returns (bytes32, uint256, uint256) {
        return (keccak256("policy"), 1, 1);
    }
    function authorizeEscrow(address, address[] calldata, bytes32[] calldata, uint256, uint256)
        external view returns (bool) { return admit; }
    function accept(bytes32 context) external { accepted[context] = true; }
    function verifyDelivery(IComposedDeliveryVerifier.ExpectedDelivery calldata expected, bytes32 outputHash, bytes calldata proof)
        external view returns (bool, bytes32) {
        return (accepted[expected.context] && outputHash == keccak256("output") && keccak256(proof) == keccak256(hex"01"), expected.nonce);
    }
}

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
    function cancelRequest(address, bytes32) external {}
}

// ═══════════════════ Test Suite ═══════════════════

contract ComposedSettlementTest is Test {
    ComposedSettlement public settlement;
    MockToken public token;
    MockBondRegistry public bondRegistry;
    SettlementRegistryFixture internal registry;
    SettlementVerifierFixture internal verifier;

    address public admin = address(0xAD);
    address public agent = address(0xAA);
    address public provider1 = address(0xA1);
    address public provider2 = address(0xA2);
    address public provider3 = address(0xA3);
    address public builder = address(0xBB);
    address public treasuryAddr = address(0xCC);

    function setUp() public {
        token = new MockToken();
        bondRegistry = new MockBondRegistry();

        registry = new SettlementRegistryFixture();
        verifier = new SettlementVerifierFixture();
        registry.setTerms(keccak256("service-block-1"), builder, 500);
        settlement = new ComposedSettlement(
            admin,
            address(token),
            address(bondRegistry),
            treasuryAddr,
            address(registry),
            address(verifier)
        );

        vm.startPrank(admin);
        settlement.grantRole(settlement.VERIFIER_ROLE(), admin);
        vm.stopPrank();

        // Bond providers
        bondRegistry.setBonded(provider1, true);
        bondRegistry.setBonded(provider2, true);
        bondRegistry.setBonded(provider3, true);

        // Fund agent
        token.mint(agent, 1_000_000 ether);
    }

    // ═══════════════════ Helper ═══════════════════

    function _createBound(address[] memory providers, uint256[] memory amounts,
        uint256 validForSeconds, bytes32 blueprintHash, bytes32 serviceBlockId,
        uint256 expectedBps, address expectedBuilder) internal returns (bytes32) {
        // Pure expected-value construction avoids consuming caller prank on a view call.
        bytes32 terms = serviceBlockId == bytes32(0) ? bytes32(0) : _expectedTerms(
            serviceBlockId, expectedBuilder, expectedBps);
        bytes32[] memory workloads = new bytes32[](providers.length);
        for (uint256 i; i < workloads.length; ++i) workloads[i] = keccak256("expected-workload");
        return settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, validForSeconds, blueprintHash, serviceBlockId, terms, workloads));
    }

    function _expectedTerms(bytes32 id, address expectedBuilder, uint256 bps) internal view returns (bytes32) {
        return keccak256(abi.encode(block.chainid, address(registry), id, expectedBuilder, bps,
            keccak256("manifest"), uint256(1), bytes32(0), bytes32(0), uint256(0), expectedBuilder));
    }

    function _acceptProof(bytes32 id, uint256 index) internal {
        address provider = settlement.getProviderAlloc(id, index).provider;
        vm.prank(provider);
        settlement.issueDeliveryChallenge(id, index);
        verifier.accept(settlement.getDeliveryContext(id, index));
    }

    function _createAllocation2Providers() internal returns (bytes32) {
        address[] memory providers = new address[](2);
        providers[0] = provider1;
        providers[1] = provider2;

        uint256[] memory amounts = new uint256[](2);
        amounts[0] = 600 ether;
        amounts[1] = 400 ether;

        vm.prank(agent);
        return _createBound(
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
        return _createBound(
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
        bytes32 allocId = _createBound(
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
        _createBound(providers, amounts, 1 hours, bytes32(0), bytes32(0), 0, address(0));
    }

    function test_createComposedEscrow_reverts_arrayMismatch() public {
        address[] memory providers = new address[](2);
        providers[0] = provider1;
        providers[1] = provider2;
        uint256[] memory amounts = new uint256[](1);
        amounts[0] = 100 ether;

        vm.prank(agent);
        vm.expectRevert(IComposedSettlement.ArrayLengthMismatch.selector);
        _createBound(providers, amounts, 1 hours, bytes32(0), bytes32(0), 0, address(0));
    }

    // ═══════════════════ Claim Tests ═══════════════════

    function test_claimProviderShare_success() public {
        bytes32 allocId = _createAllocation2Providers();

        vm.prank(admin);
        _acceptProof(allocId, 0);

        // Provider 1 claims
        vm.prank(provider1);
        settlement.claimProviderShareV2(allocId, 0, keccak256("output"), hex"01");

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

        vm.prank(admin);
        _acceptProof(allocId, 0);
        vm.prank(provider1);
        settlement.claimProviderShareV2(allocId, 0, keccak256("output"), hex"01");

        vm.prank(admin);
        _acceptProof(allocId, 1);
        vm.prank(provider2);
        settlement.claimProviderShareV2(allocId, 1, keccak256("output"), hex"01");

        IComposedSettlement.ComposedAllocation memory alloc = settlement.getComposedAllocation(allocId);
        assertEq(uint8(alloc.status), uint8(IComposedSettlement.AllocationStatus.FULLY_CLAIMED));
        assertTrue(settlement.isFullyClaimed(allocId));
    }

    function test_claimProviderShare_independentClaims() public {
        bytes32 allocId = _createAllocation2Providers();

        vm.prank(admin);
        _acceptProof(allocId, 1);
        // Provider 2 claims first (order doesn't matter)
        vm.prank(provider2);
        settlement.claimProviderShareV2(allocId, 1, keccak256("output"), hex"01");

        IComposedSettlement.ProviderAlloc memory p2Alloc = settlement.getProviderAlloc(allocId, 1);
        assertTrue(p2Alloc.claimed);

        // Provider 1 can still claim
        IComposedSettlement.ProviderAlloc memory p1Alloc = settlement.getProviderAlloc(allocId, 0);
        assertFalse(p1Alloc.claimed);
    }

    function test_claimProviderShare_reverts_wrongProvider() public {
        bytes32 allocId = _createAllocation2Providers();

        vm.prank(admin);
        _acceptProof(allocId, 0);
        vm.prank(provider2); // Wrong provider for index 0
        vm.expectRevert(
            abi.encodeWithSelector(IComposedSettlement.ProviderMismatch.selector, provider1, provider2)
        );
        settlement.claimProviderShareV2(allocId, 0, keccak256("output"), hex"01");
    }

    function test_claimProviderShare_reverts_alreadyClaimed() public {
        bytes32 allocId = _createAllocation2Providers();

        vm.prank(admin);
        _acceptProof(allocId, 0);
        vm.prank(provider1);
        settlement.claimProviderShareV2(allocId, 0, keccak256("output"), hex"01");

        vm.prank(provider1);
        vm.expectRevert(
            abi.encodeWithSelector(IComposedSettlement.ProviderAlreadyClaimed.selector, allocId, 0)
        );
        settlement.claimProviderShareV2(allocId, 0, keccak256("output"), hex"01");
    }

    // ═══════════════════ Builder Revenue Tests ═══════════════════

    function test_claimProviderShare_withBuilderRevenue() public {
        bytes32 allocId = _createAllocationWithBuilder();

        vm.prank(admin);
        _acceptProof(allocId, 0);
        vm.prank(provider1);
        settlement.claimProviderShareV2(allocId, 0, keccak256("output"), hex"01");

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

        vm.prank(admin);
        _acceptProof(allocId, 0);
        // Provider 1 claims before expiry
        vm.prank(provider1);
        settlement.claimProviderShareV2(allocId, 0, keccak256("output"), hex"01");

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
    function test_legacyCreationAndVerifierAlwaysReject() public {
        address[] memory providers = new address[](1); providers[0] = provider1;
        uint256[] memory amounts = new uint256[](1); amounts[0] = 1 ether;
        vm.expectRevert(IComposedSettlement.LegacyInterfaceDisabled.selector);
        settlement.createComposedEscrow(providers, amounts, 1 hours, bytes32(0), bytes32(0), 10_000, builder);
        vm.prank(admin);
        vm.expectRevert(IComposedSettlement.LegacyInterfaceDisabled.selector);
        settlement.verifyProviderProof(bytes32(0), 0);
        assertEq(settlement.allocationCount(), 0);
        assertEq(token.balanceOf(address(settlement)), 0);
    }

    function test_directDeniedAdmissionAcceptsNoFunds() public {
        verifier.setAdmission(false);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        _createAllocation2Providers();
        assertEq(token.balanceOf(address(settlement)), 0);
        assertEq(settlement.allocationCount(), 0);
    }

    function test_builderMaximumPlusOneRejectsBeforeFunding() public {
        registry.setTerms(keccak256("service-block-1"), builder, 5001);
        vm.expectRevert(IComposedSettlement.InvalidServiceTerms.selector);
        _createAllocationWithBuilder();
        assertEq(settlement.allocationCount(), 0);
        assertEq(token.balanceOf(address(settlement)), 0);
    }

    function test_forgedTermsRejectBeforeFunding() public {
        registry.setTerms(keccak256("service-block-1"), address(0xBAD), 500);
        vm.expectRevert(IComposedSettlement.InvalidServiceTerms.selector);
        _createAllocationWithBuilder();
        assertEq(settlement.allocationCount(), 0);
    }

    function test_quarantinedListingRejectsBeforeFunding() public {
        registry.quarantine(keccak256("service-block-1"));
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.UnqualifiedServiceBlock.selector,
            keccak256("service-block-1")));
        _createAllocationWithBuilder();
        assertEq(token.balanceOf(address(settlement)), 0);
    }

    function test_registryChangesCannotRewriteEarnedTerms() public {
        bytes32 id = _createAllocationWithBuilder();
        bytes32 frozen = settlement.allocationTermsHash(id);
        registry.setTerms(keccak256("service-block-1"), address(0xBAD), 5000);
        _acceptProof(id, 0);
        vm.prank(provider1);
        settlement.claimProviderShareV2(id, 0, keccak256("output"), hex"01");
        assertEq(token.balanceOf(builder), 25 ether);
        assertEq(token.balanceOf(address(0xBAD)), 0);
        assertEq(settlement.allocationTermsHash(id), frozen);
    }

    function test_unverifiedOutputCannotPay() public {
        bytes32 id = _createAllocation2Providers();
        _acceptProof(id, 0);
        vm.prank(provider1);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        settlement.claimProviderShareV2(id, 0, keccak256("another-output"), hex"01");
        assertEq(token.balanceOf(provider1), 0);
        assertFalse(settlement.getProviderAlloc(id, 0).claimed);
    }

    function testFuzz_maxFeeConservesWithoutMultiplicationOverflow(uint256 amount) public {
        amount = bound(amount, 1, type(uint256).max - 1_000_000 ether);
        registry.setTerms(keccak256("service-block-1"), builder, 5000);
        token.mint(agent, amount);
        address[] memory providers = new address[](1); providers[0] = provider1;
        uint256[] memory amounts = new uint256[](1); amounts[0] = amount;
        vm.prank(agent);
        bytes32 id = _createBound(providers, amounts, 1 hours, keccak256("fuzz"),
            keccak256("service-block-1"), 5000, builder);
        _acceptProof(id, 0);
        vm.prank(provider1);
        settlement.claimProviderShareV2(id, 0, keccak256("output"), hex"01");
        assertEq(token.balanceOf(provider1) + token.balanceOf(builder) + token.balanceOf(treasuryAddr), amount);
        assertEq(token.balanceOf(address(settlement)), 0);
    }

}
