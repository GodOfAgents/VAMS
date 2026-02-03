// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../utils/BaseTest.sol";
import "../../src/economic/VAMSFeeCollector.sol";
import "../../src/economic/IVAMSFeeCollector.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

/**
 * @title VAMSFeeCollectorTest
 * @notice Comprehensive unit tests for VAMSFeeCollector contract
 */
contract VAMSFeeCollectorTest is BaseTest {
    VAMSFeeCollector public feeCollector;
    VAMSFeeCollector public feeCollectorImpl;
    
    address public stakingContract;
    address public insuranceFund;
    
    // Events (matching interface)
    event FeesCollected(address indexed from, address indexed token, uint256 amount);
    event FeesDistributed(address indexed token, uint256 burned, uint256 toStaking, uint256 toTreasury, uint256 toInsurance);
    event DistributionUpdated(IVAMSFeeCollector.DistributionPhase phase, uint256 burnBps, uint256 stakingBps, uint256 treasuryBps, uint256 insuranceBps);
    event AutoDistributeThresholdUpdated(uint256 oldThreshold, uint256 newThreshold);
    event TokenSupportUpdated(address indexed token, bool supported);
    
    function setUp() public override {
        super.setUp();
        
        // Create additional addresses
        stakingContract = makeAddr("stakingContract");
        insuranceFund = makeAddr("insuranceFund");
        
        // Deploy implementation
        feeCollectorImpl = new VAMSFeeCollector();
        
        // Package initialization data (5 params, no burnAddress - contract uses constant)
        bytes memory initData = abi.encodeWithSelector(
            VAMSFeeCollector.initialize.selector,
            admin,
            address(token),
            treasury,
            stakingContract,
            insuranceFund
        );
        
        // Deploy proxy
        ERC1967Proxy proxy = new ERC1967Proxy(address(feeCollectorImpl), initData);
        feeCollector = VAMSFeeCollector(address(proxy));
        
        vm.label(address(feeCollector), "FeeCollector");
        
        // Fund test accounts
        _fundAccount(admin, 1_000_000 ether);
        _fundAccount(user1, 1_000_000 ether);
    }
    
    // ============ Initialization Tests ============
    
    function test_Initialization() public view {
        assertEq(address(feeCollector.vamsToken()), address(token));
        assertEq(feeCollector.treasury(), treasury);
        assertEq(feeCollector.stakingContract(), stakingContract);
        assertEq(feeCollector.insuranceFund(), insuranceFund);
        assertTrue(feeCollector.hasRole(feeCollector.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(feeCollector.hasRole(feeCollector.FEE_COLLECTOR_ROLE(), admin));
        assertTrue(feeCollector.hasRole(feeCollector.FEE_DISTRIBUTOR_ROLE(), admin));
    }
    
    function test_InitialPhase_IsPhase1() public view {
        assertEq(uint256(feeCollector.getCurrentPhase()), uint256(IVAMSFeeCollector.DistributionPhase.PHASE_1));
    }
    
    function test_Phase1Distribution_Is100PercentBurn() public view {
        IVAMSFeeCollector.Distribution memory dist = feeCollector.getDistribution();
        
        assertEq(dist.burnBps, 10000); // 100%
        assertEq(dist.stakingBps, 0);
        assertEq(dist.treasuryBps, 0);
        assertEq(dist.insuranceBps, 0);
    }
    
    function test_DefaultThreshold() public view {
        assertEq(feeCollector.autoDistributeThreshold(), 10_000 ether);
    }
    
    function test_VAMSToken_SupportedByDefault() public view {
        assertTrue(feeCollector.isTokenSupported(address(token)));
    }
    
    // ============ Fee Collection Tests ============
    
    function test_CollectFees_Success() public {
        uint256 amount = 1000 ether;
        
        // Admin can collect by default
        vm.prank(admin);
        token.approve(address(feeCollector), amount);
        
        vm.prank(admin);
        feeCollector.collectFees(amount);
        
        assertEq(feeCollector.accumulatedFees(), amount);
    }
    
    function test_CollectTokenFees_Success() public {
        uint256 amount = 1000 ether;
        
        vm.prank(admin);
        token.approve(address(feeCollector), amount);
        
        vm.prank(admin);
        feeCollector.collectTokenFees(address(token), amount);
        
        assertEq(feeCollector.getAccumulatedFees(address(token)), amount);
    }
    
    function test_CollectFees_RevertWithoutRole() public {
        uint256 amount = 1000 ether;
        
        vm.prank(user1);
        token.approve(address(feeCollector), amount);
        
        vm.expectRevert();
        vm.prank(user1);
        feeCollector.collectFees(amount);
    }
    
    function test_CollectFees_RevertZeroAmount() public {
        vm.expectRevert(IVAMSFeeCollector.ZeroAmount.selector);
        vm.prank(admin);
        feeCollector.collectFees(0);
    }
    
    function test_CollectFees_RevertUnsupportedToken() public {
        address unsupported = makeAddr("unsupported");
        
        vm.expectRevert(abi.encodeWithSelector(IVAMSFeeCollector.TokenNotSupported.selector, unsupported));
        vm.prank(admin);
        feeCollector.collectTokenFees(unsupported, 1000);
    }
    
    function test_CollectFees_EmitsEvent() public {
        uint256 amount = 500 ether;
        
        vm.prank(admin);
        token.approve(address(feeCollector), amount);
        
        vm.expectEmit(true, true, true, true);
        emit FeesCollected(admin, address(token), amount);
        
        vm.prank(admin);
        feeCollector.collectFees(amount);
    }
    
    function testFuzz_CollectFees(uint256 amount) public {
        // Keep amount in reasonable range to avoid threshold auto-distribution
        vm.assume(amount > 0 && amount < 9000 ether);
        
        // Fund admin with more tokens
        token.mint(admin, amount);
        
        vm.prank(admin);
        token.approve(address(feeCollector), amount);
        
        vm.prank(admin);
        feeCollector.collectFees(amount);
        
        assertEq(feeCollector.accumulatedFees(), amount);
    }
    
    // ============ Fee Distribution Tests ============
    
    function test_DistributeFees_Phase1_100PercentBurn() public {
        uint256 feeAmount = 5_000 ether;
        
        // Collect fees
        vm.prank(admin);
        token.approve(address(feeCollector), feeAmount);
        vm.prank(admin);
        feeCollector.collectFees(feeAmount);
        
        uint256 burnBalanceBefore = token.balanceOf(feeCollector.BURN_ADDRESS());
        
        vm.prank(admin);
        feeCollector.distributeFees();
        
        // In Phase 1, 100% should go to burn
        assertEq(token.balanceOf(feeCollector.BURN_ADDRESS()), burnBalanceBefore + feeAmount);
        assertEq(feeCollector.accumulatedFees(), 0);
    }
    
    function test_DistributeFees_Phase2() public {
        // Transition to Phase 2
        vm.prank(admin);
        feeCollector.transitionToPhase(IVAMSFeeCollector.DistributionPhase.PHASE_2);
        
        uint256 feeAmount = 5_000 ether;
        
        // Collect fees
        vm.prank(admin);
        token.approve(address(feeCollector), feeAmount);
        vm.prank(admin);
        feeCollector.collectTokenFees(address(token), feeAmount);
        
        uint256 burnBefore = token.balanceOf(feeCollector.BURN_ADDRESS());
        uint256 stakingBefore = token.balanceOf(stakingContract);
        uint256 treasuryBefore = token.balanceOf(treasury);
        uint256 insuranceBefore = token.balanceOf(insuranceFund);
        
        vm.prank(admin);
        feeCollector.distributeFees();
        
        // Phase 2: 40% burn, 30% staking, 20% treasury, 10% insurance
        assertEq(token.balanceOf(feeCollector.BURN_ADDRESS()), burnBefore + 2000 ether);
        assertEq(token.balanceOf(stakingContract), stakingBefore + 1500 ether);
        assertEq(token.balanceOf(treasury), treasuryBefore + 1000 ether);
        assertEq(token.balanceOf(insuranceFund), insuranceBefore + 500 ether);
    }
    
    function test_DistributeFees_RevertNoFees() public {
        vm.expectRevert(IVAMSFeeCollector.NoFeesToDistribute.selector);
        vm.prank(admin);
        feeCollector.distributeFees();
    }
    
    function test_DistributeFees_EmitsEvent() public {
        uint256 feeAmount = 1000 ether;
        
        vm.prank(admin);
        token.approve(address(feeCollector), feeAmount);
        vm.prank(admin);
        feeCollector.collectFees(feeAmount);
        
        vm.expectEmit(true, true, true, true);
        emit FeesDistributed(address(token), feeAmount, 0, 0, 0);
        
        vm.prank(admin);
        feeCollector.distributeFees();
    }
    
    // ============ Phase Transition Tests ============
    
    function test_TransitionToPhase2() public {
        vm.prank(admin);
        feeCollector.transitionToPhase(IVAMSFeeCollector.DistributionPhase.PHASE_2);
        
        assertEq(uint256(feeCollector.currentPhase()), uint256(IVAMSFeeCollector.DistributionPhase.PHASE_2));
        
        IVAMSFeeCollector.Distribution memory dist = feeCollector.getDistribution();
        
        assertEq(dist.burnBps, 4000);      // 40%
        assertEq(dist.stakingBps, 3000);   // 30%
        assertEq(dist.treasuryBps, 2000);  // 20%
        assertEq(dist.insuranceBps, 1000); // 10%
    }
    
    function test_TransitionToPhase3() public {
        vm.prank(admin);
        feeCollector.transitionToPhase(IVAMSFeeCollector.DistributionPhase.PHASE_3);
        
        assertEq(uint256(feeCollector.currentPhase()), uint256(IVAMSFeeCollector.DistributionPhase.PHASE_3));
        
        IVAMSFeeCollector.Distribution memory dist = feeCollector.getDistribution();
        
        assertEq(dist.burnBps, 3000);      // 30%
        assertEq(dist.stakingBps, 3500);   // 35%
        assertEq(dist.treasuryBps, 2500);  // 25%
        assertEq(dist.insuranceBps, 1000); // 10%
    }
    
    function test_TransitionPhase_RevertNotAdmin() public {
        vm.expectRevert();
        vm.prank(user1);
        feeCollector.transitionToPhase(IVAMSFeeCollector.DistributionPhase.PHASE_2);
    }
    
    function test_TransitionPhase_EmitsEvent() public {
        vm.expectEmit(true, true, true, true);
        emit DistributionUpdated(
            IVAMSFeeCollector.DistributionPhase.PHASE_2,
            4000, 3000, 2000, 1000
        );
        
        vm.prank(admin);
        feeCollector.transitionToPhase(IVAMSFeeCollector.DistributionPhase.PHASE_2);
    }
    
    // ============ Custom Distribution Tests ============
    
    function test_UpdateDistribution_CustomValues() public {
        uint256 burnBps = 2500;     // 25%
        uint256 stakingBps = 4000;  // 40%
        uint256 treasuryBps = 2000; // 20%
        uint256 insuranceBps = 1500; // 15%
        
        vm.prank(admin);
        feeCollector.updateDistribution(burnBps, stakingBps, treasuryBps, insuranceBps);
        
        assertEq(uint256(feeCollector.currentPhase()), uint256(IVAMSFeeCollector.DistributionPhase.CUSTOM));
        
        IVAMSFeeCollector.Distribution memory dist = feeCollector.getDistribution();
        
        assertEq(dist.burnBps, burnBps);
        assertEq(dist.stakingBps, stakingBps);
        assertEq(dist.treasuryBps, treasuryBps);
        assertEq(dist.insuranceBps, insuranceBps);
    }
    
    function test_UpdateDistribution_RevertInvalidTotal_Over100() public {
        // Total > 100%
        vm.expectRevert(abi.encodeWithSelector(IVAMSFeeCollector.InvalidDistribution.selector, 11000));
        vm.prank(admin);
        feeCollector.updateDistribution(5000, 3000, 2000, 1000); // 110%
    }
    
    function test_UpdateDistribution_RevertInvalidTotal_Under100() public {
        // Total < 100%
        vm.expectRevert(abi.encodeWithSelector(IVAMSFeeCollector.InvalidDistribution.selector, 8000));
        vm.prank(admin);
        feeCollector.updateDistribution(2000, 2000, 2000, 2000); // 80%
    }
    
    // ============ Token Support Tests ============
    
    function test_SetTokenSupport_Add() public {
        address newToken = makeAddr("newToken");
        
        vm.prank(admin);
        feeCollector.setTokenSupport(newToken, true);
        
        assertTrue(feeCollector.isTokenSupported(newToken));
    }
    
    function test_SetTokenSupport_Remove() public {
        address newToken = makeAddr("newToken");
        
        vm.prank(admin);
        feeCollector.setTokenSupport(newToken, true);
        assertTrue(feeCollector.isTokenSupported(newToken));
        
        vm.prank(admin);
        feeCollector.setTokenSupport(newToken, false);
        assertFalse(feeCollector.isTokenSupported(newToken));
    }
    
    function test_SetTokenSupport_RevertZeroAddress() public {
        vm.expectRevert(IVAMSFeeCollector.ZeroAddress.selector);
        vm.prank(admin);
        feeCollector.setTokenSupport(address(0), true);
    }
    
    function test_SetTokenSupport_EmitsEvent() public {
        address newToken = makeAddr("newToken");
        
        vm.expectEmit(true, true, true, true);
        emit TokenSupportUpdated(newToken, true);
        
        vm.prank(admin);
        feeCollector.setTokenSupport(newToken, true);
    }
    
    // ============ Auto-Distribute Threshold Tests ============
    
    function test_SetAutoDistributeThreshold() public {
        uint256 newThreshold = 50_000 ether;
        
        vm.prank(admin);
        feeCollector.setAutoDistributeThreshold(newThreshold);
        
        assertEq(feeCollector.autoDistributeThreshold(), newThreshold);
    }
    
    function test_SetAutoDistributeThreshold_EmitsEvent() public {
        uint256 oldThreshold = feeCollector.autoDistributeThreshold();
        uint256 newThreshold = 50_000 ether;
        
        vm.expectEmit(true, true, true, true);
        emit AutoDistributeThresholdUpdated(oldThreshold, newThreshold);
        
        vm.prank(admin);
        feeCollector.setAutoDistributeThreshold(newThreshold);
    }
    
    function test_AutoDistribute_TriggersOnThreshold() public {
        // Set a low threshold
        vm.prank(admin);
        feeCollector.setAutoDistributeThreshold(100 ether);
        
        uint256 burnBefore = token.balanceOf(feeCollector.BURN_ADDRESS());
        
        // Collect fees that exceed threshold
        vm.prank(admin);
        token.approve(address(feeCollector), 150 ether);
        vm.prank(admin);
        feeCollector.collectFees(150 ether);
        
        // Fees should have been auto-distributed
        assertEq(feeCollector.accumulatedFees(), 0);
        assertEq(token.balanceOf(feeCollector.BURN_ADDRESS()), burnBefore + 150 ether);
    }
    
    // ============ Pausability Tests ============
    
    function test_Pause_BlocksDistribution() public {
        // Collect some fees first
        vm.prank(admin);
        token.approve(address(feeCollector), 1000 ether);
        vm.prank(admin);
        feeCollector.collectFees(1000 ether);
        
        // Pause
        vm.prank(admin);
        feeCollector.pause();
        
        // Try to distribute
        vm.expectRevert();
        vm.prank(admin);
        feeCollector.distributeFees();
    }
    
    function test_Unpause_AllowsDistribution() public {
        // Collect some fees first
        vm.prank(admin);
        token.approve(address(feeCollector), 1000 ether);
        vm.prank(admin);
        feeCollector.collectFees(1000 ether);
        
        // Pause then unpause
        vm.prank(admin);
        feeCollector.pause();
        
        vm.prank(admin);
        feeCollector.unpause();
        
        // Should work now
        vm.prank(admin);
        feeCollector.distributeFees();
        
        assertEq(feeCollector.accumulatedFees(), 0);
    }
    
    // ============ Admin Functions Tests ============
    
    function test_SetTreasury() public {
        address newTreasury = makeAddr("newTreasury");
        
        vm.prank(admin);
        feeCollector.setTreasury(newTreasury);
        
        assertEq(feeCollector.treasury(), newTreasury);
    }
    
    function test_SetStakingContract() public {
        address newStaking = makeAddr("newStaking");
        
        vm.prank(admin);
        feeCollector.setStakingContract(newStaking);
        
        assertEq(feeCollector.stakingContract(), newStaking);
    }
    
    function test_SetInsuranceFund() public {
        address newInsurance = makeAddr("newInsurance");
        
        vm.prank(admin);
        feeCollector.setInsuranceFund(newInsurance);
        
        assertEq(feeCollector.insuranceFund(), newInsurance);
    }
    
    function test_EmergencyWithdraw() public {
        // First fund the collector
        token.mint(address(feeCollector), 5000 ether);
        
        uint256 treasuryBefore = token.balanceOf(treasury);
        
        vm.prank(admin);
        feeCollector.emergencyWithdraw(address(token), treasury, 5000 ether);
        
        assertEq(token.balanceOf(treasury), treasuryBefore + 5000 ether);
    }
    
    // ============ View Function Tests ============
    
    function test_GetSupportedTokens() public view {
        address[] memory tokens = feeCollector.getSupportedTokens();
        assertEq(tokens.length, 1);
        assertEq(tokens[0], address(token));
    }
    
    function test_GetTotalAccumulatedFees() public {
        // Collect fees
        vm.prank(admin);
        token.approve(address(feeCollector), 5000 ether);
        vm.prank(admin);
        feeCollector.collectFees(5000 ether);
        
        assertEq(feeCollector.getTotalAccumulatedFees(), 5000 ether);
    }
    
    function test_GetAutoDistributeThreshold() public view {
        assertEq(feeCollector.getAutoDistributeThreshold(), 10_000 ether);
    }
}
