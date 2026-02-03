// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/economic/ProviderBondRegistry.sol";
import "../../src/economic/VAMSInsuranceFund.sol";

/**
 * @title ProviderBondRegistryTest
 * @notice Comprehensive tests for ProviderBondRegistry contract
 */
contract ProviderBondRegistryTest is BaseTest {
    ProviderBondRegistry public registry;
    VAMSInsuranceFund public insurance;
    
    // Constants
    uint256 constant MIN_BOND = 10_000 ether;
    uint256 constant COVERAGE_RATIO = 10;
    uint256 constant WITHDRAWAL_DELAY = 7 days;
    
    function setUp() public override {
        super.setUp();
        
        // Deploy insurance fund first (needed by registry)
        insurance = new VAMSInsuranceFund();
        
        // Create guardians array for insurance fund initialization
        address[] memory guardians = new address[](3);
        guardians[0] = guardian1;
        guardians[1] = guardian2;
        guardians[2] = guardian3;
        
        // Initialize with (admin, token, stakingContract, guardians)
        insurance.initialize(admin, address(token), address(0), guardians);
        vm.label(address(insurance), "InsuranceFund");
        
        // Deploy registry
        registry = new ProviderBondRegistry();
        registry.initialize(admin, address(token), address(insurance));
        vm.label(address(registry), "ProviderBondRegistry");
        
        // Grant slasher role using admin
        vm.startPrank(admin);
        registry.grantRole(registry.SLASHER_ROLE(), slasher);
        vm.stopPrank();
    }
    
    // ============ Initialization Tests ============
    
    function test_Initialize_SetsVamsToken() public view {
        assertEq(address(registry.vamsToken()), address(token));
    }
    
    function test_Initialize_SetsInsuranceFund() public view {
        assertEq(registry.insuranceFund(), address(insurance));
    }
    
    function test_Initialize_AdminHasRoles() public view {
        assertTrue(registry.hasRole(registry.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(registry.hasRole(registry.ADMIN_ROLE(), admin));
    }
    
    function test_Initialize_CorrectConstants() public view {
        assertEq(registry.MIN_BOND(), MIN_BOND);
        assertEq(registry.BOND_COVERAGE_RATIO(), COVERAGE_RATIO);
        assertEq(registry.WITHDRAWAL_DELAY(), WITHDRAWAL_DELAY);
    }
    
    // ============ Registration Tests ============
    
    function test_RegisterProvider_SetsCorrectBond() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.bondedAmount, bondAmount);
        assertEq(info.maxRequestValue, maxRequest);
        assertTrue(info.isActive);
    }
    
    function test_RegisterProvider_TransfersTokens() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        uint256 registryBalanceBefore = token.balanceOf(address(registry));
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        assertEq(token.balanceOf(address(registry)), registryBalanceBefore + bondAmount);
    }
    
    function test_RegisterProvider_EmitsEvent() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.expectEmit(true, false, false, true);
        emit IProviderBondRegistry.ProviderRegistered(provider1, bondAmount, maxRequest);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
    }
    
    function test_RegisterProvider_RevertsOnMinBond() public {
        uint256 bondAmount = MIN_BOND - 1;
        uint256 maxRequest = 100 ether;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        vm.expectRevert(abi.encodeWithSelector(
            IProviderBondRegistry.BondTooLow.selector,
            bondAmount,
            MIN_BOND
        ));
        registry.registerProvider(bondAmount, maxRequest);
    }
    
    function test_RegisterProvider_RevertsOnCoverageRatio() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount; // Too high, should be bond/10
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        vm.expectRevert(abi.encodeWithSelector(
            IProviderBondRegistry.CoverageRatioNotMet.selector,
            bondAmount,
            maxRequest,
            COVERAGE_RATIO
        ));
        registry.registerProvider(bondAmount, maxRequest);
    }
    
    function test_RegisterProvider_RevertsOnDuplicate() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        
        _fundAndApprove(provider1, address(registry), bondAmount * 2);
        
        vm.startPrank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        vm.expectRevert(abi.encodeWithSelector(
            IProviderBondRegistry.ProviderAlreadyRegistered.selector,
            provider1
        ));
        registry.registerProvider(bondAmount, maxRequest);
        vm.stopPrank();
    }
    
    // ============ Bond Management Tests ============
    
    function test_IncreaseBond_UpdatesAmount() public {
        uint256 initialBond = MIN_BOND;
        uint256 maxRequest = initialBond / COVERAGE_RATIO;
        uint256 additionalBond = 5000 ether;
        
        _fundAndApprove(provider1, address(registry), initialBond + additionalBond);
        
        vm.prank(provider1);
        registry.registerProvider(initialBond, maxRequest);
        
        vm.prank(provider1);
        registry.increaseBond(additionalBond);
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.bondedAmount, initialBond + additionalBond);
    }
    
    function test_IncreaseBond_EmitsEvent() public {
        uint256 initialBond = MIN_BOND;
        uint256 maxRequest = initialBond / COVERAGE_RATIO;
        uint256 additionalBond = 5000 ether;
        
        _fundAndApprove(provider1, address(registry), initialBond + additionalBond);
        
        vm.prank(provider1);
        registry.registerProvider(initialBond, maxRequest);
        
        vm.expectEmit(true, false, false, true);
        emit IProviderBondRegistry.BondIncreased(provider1, additionalBond, initialBond + additionalBond);
        
        vm.prank(provider1);
        registry.increaseBond(additionalBond);
    }
    
    function test_UpdateMaxRequest_ValidatesCoverage() public {
        uint256 bondAmount = MIN_BOND * 2;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        // Update to higher value (within coverage)
        uint256 newMaxRequest = bondAmount / COVERAGE_RATIO;
        
        vm.prank(provider1);
        registry.updateMaxRequestValue(newMaxRequest);
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.maxRequestValue, newMaxRequest);
    }
    
    function test_UpdateMaxRequest_RevertsIfExceedsCoverage() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        uint256 invalidMaxRequest = bondAmount; // Exceeds 10x coverage
        
        vm.prank(provider1);
        vm.expectRevert(abi.encodeWithSelector(
            IProviderBondRegistry.CoverageRatioNotMet.selector,
            bondAmount,
            invalidMaxRequest,
            COVERAGE_RATIO
        ));
        registry.updateMaxRequestValue(invalidMaxRequest);
    }
    
    // ============ Withdrawal Tests ============
    
    function test_RequestWithdrawal_SetsDelay() public {
        uint256 bondAmount = MIN_BOND * 2;
        uint256 maxRequest = (bondAmount - MIN_BOND) / COVERAGE_RATIO;
        uint256 withdrawAmount = bondAmount - MIN_BOND;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        vm.prank(provider1);
        registry.requestWithdrawal(withdrawAmount);
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.pendingWithdrawal, withdrawAmount);
        assertEq(info.withdrawalUnlockTime, block.timestamp + WITHDRAWAL_DELAY);
    }
    
    function test_ExecuteWithdrawal_TransfersAfterDelay() public {
        uint256 bondAmount = MIN_BOND * 2;
        uint256 maxRequest = (bondAmount - MIN_BOND) / COVERAGE_RATIO;
        uint256 withdrawAmount = bondAmount - MIN_BOND;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        vm.prank(provider1);
        registry.requestWithdrawal(withdrawAmount);
        
        _advanceTime(WITHDRAWAL_DELAY + 1);
        
        uint256 balanceBefore = token.balanceOf(provider1);
        
        vm.prank(provider1);
        registry.executeWithdrawal();
        
        assertEq(token.balanceOf(provider1), balanceBefore + withdrawAmount);
    }
    
    function test_ExecuteWithdrawal_RevertsBeforeDelay() public {
        uint256 bondAmount = MIN_BOND * 2;
        uint256 maxRequest = (bondAmount - MIN_BOND) / COVERAGE_RATIO;
        uint256 withdrawAmount = bondAmount - MIN_BOND;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        vm.prank(provider1);
        registry.requestWithdrawal(withdrawAmount);
        
        _advanceTime(WITHDRAWAL_DELAY - 1 hours);
        
        vm.prank(provider1);
        vm.expectRevert(abi.encodeWithSelector(
            IProviderBondRegistry.WithdrawalLocked.selector,
            block.timestamp + 1 hours
        ));
        registry.executeWithdrawal();
    }
    
    function test_CancelWithdrawal_ClearsPending() public {
        uint256 bondAmount = MIN_BOND * 2;
        // Use a smaller maxRequest to allow for partial withdrawal
        uint256 maxRequest = (bondAmount - 5000 ether) / COVERAGE_RATIO; // Account for potential withdrawal
        uint256 withdrawAmount = 5000 ether;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        vm.prank(provider1);
        registry.requestWithdrawal(withdrawAmount);
        
        vm.prank(provider1);
        registry.cancelWithdrawal();
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.pendingWithdrawal, 0);
        assertEq(info.withdrawalUnlockTime, 0);
    }
    
    // ============ Request Tracking Tests ============
    
    function test_AcceptRequest_IncreasesPending() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        uint256 requestValue = maxRequest / 2;
        bytes32 escrowId = keccak256("escrow1");
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        // Grant escrow role using admin
        vm.startPrank(admin);
        registry.grantRole(registry.ESCROW_ROLE(), user1);
        vm.stopPrank();
        
        vm.prank(user1);
        registry.acceptRequest(provider1, escrowId, requestValue);
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.pendingSettlements, requestValue);
        assertEq(info.activeRequests, 1);
    }
    
    function test_AcceptRequest_RevertsOnExceedMax() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        bytes32 escrowId = keccak256("escrow1");
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        vm.startPrank(admin);
        registry.grantRole(registry.ESCROW_ROLE(), user1);
        vm.stopPrank();
        
        vm.prank(user1);
        vm.expectRevert(abi.encodeWithSelector(
            IProviderBondRegistry.RequestValueTooHigh.selector,
            maxRequest + 1,
            maxRequest
        ));
        registry.acceptRequest(provider1, escrowId, maxRequest + 1);
    }
    
    function test_CompleteRequest_DecreasesPending() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        uint256 requestValue = maxRequest / 2;
        bytes32 escrowId = keccak256("escrow1");
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        vm.startPrank(admin);
        registry.grantRole(registry.ESCROW_ROLE(), user1);
        vm.stopPrank();
        
        vm.prank(user1);
        registry.acceptRequest(provider1, escrowId, requestValue);
        
        vm.prank(user1);
        registry.completeRequest(provider1, escrowId);
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.pendingSettlements, 0);
        assertEq(info.activeRequests, 0);
    }
    
    // ============ Slashing Tests ============
    
    function test_SlashProvider_ReducesBond() public {
        uint256 bondAmount = MIN_BOND * 2;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        uint256 slashAmount = 5000 ether;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        bytes32 escrowId = keccak256("escrow");
        
        vm.prank(slasher);
        registry.slashProvider(provider1, slashAmount, escrowId, "Service failure");
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.bondedAmount, bondAmount - slashAmount);
    }
    
    function test_SlashProvider_SplitsToInsurance() public {
        uint256 bondAmount = MIN_BOND * 2;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        uint256 slashAmount = 10000 ether;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        uint256 insuranceBalanceBefore = token.balanceOf(address(insurance));
        
        bytes32 escrowId = keccak256("escrow");
        
        vm.prank(slasher);
        registry.slashProvider(provider1, slashAmount, escrowId, "Service failure");
        
        // 50% goes to insurance
        uint256 expectedInsurance = slashAmount / 2;
        assertEq(token.balanceOf(address(insurance)), insuranceBalanceBefore + expectedInsurance);
    }
    
    function test_SlashProvider_DeactivatesIfBelowMin() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        uint256 slashAmount = 5000 ether; // Will bring bond below MIN_BOND
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        bytes32 escrowId = keccak256("escrow");
        
        vm.prank(slasher);
        registry.slashProvider(provider1, slashAmount, escrowId, "Service failure");
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertFalse(info.isActive);
    }
    
    function test_SlashProvider_EmitsEvent() public {
        uint256 bondAmount = MIN_BOND * 2;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        uint256 slashAmount = 5000 ether;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        bytes32 escrowId = keccak256("escrow");
        
        vm.expectEmit(true, true, false, true);
        emit IProviderBondRegistry.ProviderSlashed(
            provider1, 
            slashAmount, 
            escrowId,
            "Service failure"
        );
        
        vm.prank(slasher);
        registry.slashProvider(provider1, slashAmount, escrowId, "Service failure");
    }
    
    // ============ View Functions Tests ============
    
    function test_CanAcceptRequest_ReturnsTrue() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        (bool canAccept, string memory reason) = registry.canAcceptRequest(provider1, maxRequest / 2);
        assertTrue(canAccept);
        assertEq(bytes(reason).length, 0);
    }
    
    function test_CanAcceptRequest_ReturnsFalseIfInactive() public {
        (bool canAccept, string memory reason) = registry.canAcceptRequest(provider1, 100 ether);
        assertFalse(canAccept);
        assertEq(reason, "Provider not registered");
    }
    
    function test_CanAcceptRequest_ReturnsFalseIfExceedsMax() public {
        uint256 bondAmount = MIN_BOND;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        (bool canAccept, string memory reason) = registry.canAcceptRequest(provider1, maxRequest + 1);
        assertFalse(canAccept);
        assertEq(reason, "Request value exceeds provider maximum");
    }
    
    // ============ Fuzz Tests ============
    
    function testFuzz_RegisterProvider(uint256 bondAmount, uint256 maxRequestMultiple) public {
        bondAmount = bound(bondAmount, MIN_BOND, 100_000_000 ether);
        maxRequestMultiple = bound(maxRequestMultiple, COVERAGE_RATIO, COVERAGE_RATIO * 10);
        
        uint256 maxRequest = bondAmount / maxRequestMultiple;
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.bondedAmount, bondAmount);
        assertTrue(info.isActive);
    }
    
    function testFuzz_SlashProvider(uint256 slashAmount) public {
        uint256 bondAmount = MIN_BOND * 10;
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        slashAmount = bound(slashAmount, 1, bondAmount);
        
        _fundAndApprove(provider1, address(registry), bondAmount);
        
        vm.prank(provider1);
        registry.registerProvider(bondAmount, maxRequest);
        
        bytes32 escrowId = keccak256("escrow");
        
        vm.prank(slasher);
        registry.slashProvider(provider1, slashAmount, escrowId, "test");
        
        IProviderBondRegistry.ProviderBond memory info = registry.getBond(provider1);
        assertEq(info.bondedAmount, bondAmount - slashAmount);
    }
}
