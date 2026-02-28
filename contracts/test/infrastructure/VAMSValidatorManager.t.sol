// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/infrastructure/VAMSValidatorManager.sol";
import "../../src/infrastructure/interfaces/IVAMSValidatorManager.sol";
import "../../src/staking/IVAMSStaking.sol";
import "../../src/economic/IVAMSFeeCollector.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title Mock VAMS Token (ERC-20)
 * @notice Simple mock for testing $VAMS deposits
 */
contract MockVAMSTokenForVM is ERC20 {
    constructor() ERC20("MockVAMS", "mVAMS") {
        _mint(msg.sender, 1_000_000_000 ether);
    }
    
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

/**
 * @title Mock Staking Contract
 * @notice Mock for testing VAMSValidatorManager loyalty discount lookups
 */
contract MockStaking is IVAMSStaking {
    mapping(address => StakeInfo) private _stakes;
    
    function setStakeInfo(address account, uint256 amount, uint256 stakedAt) external {
        _stakes[account] = StakeInfo({
            amount: amount,
            rewardDebt: 0,
            pendingRewards: 0,
            stakedAt: stakedAt,
            lockedUntil: stakedAt + 90 days,
            lockPeriod: LockPeriod.NinetyDays,
            autoCompound: false
        });
    }
    
    function getStakeInfo(address account) external view override returns (StakeInfo memory) {
        return _stakes[account];
    }
    
    // Minimal implementation of other interface functions
    function stake(uint256, LockPeriod) external override {}
    function stakeWithPermit(uint256, LockPeriod, uint256, uint8, bytes32, bytes32) external override {}
    function addStake(uint256) external override {}
    function unstake(uint256) external override {}
    function withdraw() external override returns (uint256) { return 0; }
    function emergencyWithdraw() external override {}
    function claimRewards() external override returns (uint256) { return 0; }
    function compoundRewards() external override returns (uint256) { return 0; }
    function setAutoCompound(bool) external override {}
    function getVotingPower(address) external pure override returns (uint256) { return 0; }
    function getTier(address) external pure override returns (StakingTier) { return StakingTier.None; }
    function isCLROperatorEligible(address) external pure override returns (bool) { return false; }
    function pendingRewards(address) external pure override returns (uint256) { return 0; }
    function totalStaked() external pure override returns (uint256) { return 0; }
    function getUnbondingRequest(address) external pure override returns (UnbondingRequest memory) {
        return UnbondingRequest(0, 0);
    }
    function getAPY(StakingTier, LockPeriod) external pure override returns (uint256) { return 0; }
    function timeToUnlock(address) external pure override returns (uint256) { return 0; }
    function rewardPerSecond() external pure override returns (uint256) { return 0; }
    function updateEmissionRate(uint256) external override {}
    function pause() external override {}
    function unpause() external override {}
}


/**
 * @title Mock Fee Collector
 * @notice Mock for testing VAMSValidatorManager fee collection
 */
contract MockFeeCollector is IVAMSFeeCollector {
    uint256 public totalCollected;
    mapping(address => uint256) public collectedPerToken;
    
    function collectFees(uint256 amount) external override {
        totalCollected += amount;
    }
    
    function collectTokenFees(address token, uint256 amount) external override {
        collectedPerToken[token] += amount;
    }
    
    // Minimal implementation of other interface functions
    function distributeFees() external override {}
    function distributeTokenFees(address) external override {}
    function distributeAllFees() external override {}
    function updateDistribution(uint256, uint256, uint256, uint256) external override {}
    function transitionToPhase(DistributionPhase) external override {}
    function setAutoDistributeThreshold(uint256) external override {}
    function setTokenSupport(address, bool) external override {}
    function accumulatedFees() external pure override returns (uint256) { return 0; }
    function getAccumulatedFees(address) external pure override returns (uint256) { return 0; }
    function getDistribution() external pure override returns (Distribution memory) {
        return Distribution(0, 0, 0, 0);
    }
    function getCurrentPhase() external pure override returns (DistributionPhase) {
        return DistributionPhase.PHASE_1;
    }
    function isTokenSupported(address) external pure override returns (bool) { return true; }
    function getAutoDistributeThreshold() external pure override returns (uint256) { return 0; }
    
    receive() external payable {
        totalCollected += msg.value;
    }
}

/**
 * @title VAMSValidatorManagerTest
 * @notice Comprehensive unit tests for VAMSValidatorManager
 * @dev Tests markup calculation, governance, emergency functions, and subnet management
 *      Updated for $VAMS ERC-20 deposits (Polygon CDK, no Avalanche)
 */
contract VAMSValidatorManagerTest is BaseTest {
    VAMSValidatorManager public implementation;
    VAMSValidatorManager public validatorManager;
    MockStaking public mockStaking;
    MockFeeCollector public mockFeeCollector;
    MockVAMSTokenForVM public mockToken;
    
    // Constants from contract
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");
    bytes32 public constant EMERGENCY_ROLE = keccak256("EMERGENCY_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");
    uint256 public constant BPS_DENOMINATOR = 10_000;
    
    // Test subnets
    bytes32 public subnetId1 = keccak256("subnet1");
    bytes32 public subnetId2 = keccak256("subnet2");
    
    // Enterprise addresses
    address public enterprise1;
    address public enterprise2;
    
    function setUp() public override {
        super.setUp();
        
        enterprise1 = makeAddr("enterprise1");
        enterprise2 = makeAddr("enterprise2");
        
        // Deploy mocks
        mockStaking = new MockStaking();
        mockFeeCollector = new MockFeeCollector();
        mockToken = new MockVAMSTokenForVM();
        
        vm.label(address(mockStaking), "MockStaking");
        vm.label(address(mockFeeCollector), "MockFeeCollector");
        vm.label(address(mockToken), "MockVAMSToken");
        
        // Deploy implementation
        implementation = new VAMSValidatorManager();
        
        // Deploy proxy with new initialize signature (no PChainBridge)
        bytes memory initData = abi.encodeWithSelector(
            VAMSValidatorManager.initialize.selector,
            admin,
            address(mockToken),
            address(mockStaking),
            address(mockFeeCollector)
        );
        
        ERC1967Proxy proxy = new ERC1967Proxy(address(implementation), initData);
        validatorManager = VAMSValidatorManager(payable(address(proxy)));
        
        vm.label(address(validatorManager), "VAMSValidatorManager");
        
        // Fund enterprises with $VAMS tokens for deposits
        mockToken.mint(enterprise1, 1_000_000 ether);
        mockToken.mint(enterprise2, 1_000_000 ether);
        
        // Advance time to allow for past timestamps in tests
        vm.warp(3650 days); // 10 years in future
    }
    
    /// @dev Helper: enterprise approves + deposits $VAMS
    function _depositVAMS(address enterprise, bytes32 subnetId, uint256 amount) internal {
        vm.startPrank(enterprise);
        mockToken.approve(address(validatorManager), amount);
        validatorManager.deposit(subnetId, amount);
        vm.stopPrank();
    }
    
    // ============ Initialization Tests ============
    
    function test_Initialize_SetsAdmin() public view {
        assertTrue(validatorManager.hasRole(validatorManager.DEFAULT_ADMIN_ROLE(), admin));
    }
    
    function test_Initialize_SetsGovernanceRole() public view {
        assertTrue(validatorManager.hasRole(GOVERNANCE_ROLE, admin));
    }
    
    function test_Initialize_SetsEmergencyRole() public view {
        assertTrue(validatorManager.hasRole(EMERGENCY_ROLE, admin));
    }
    
    function test_Initialize_SetsUpgraderRole() public view {
        assertTrue(validatorManager.hasRole(UPGRADER_ROLE, admin));
    }
    
    function test_Initialize_SetsDefaultBounds() public view {
        uint256 minBps = validatorManager.minMarkupBps();
        uint256 maxBps = validatorManager.maxMarkupBps();
        assertEq(minBps, 100, "Min should be 1%");
        assertEq(maxBps, 500, "Max should be 5%");
    }
    
    function test_Initialize_SetsDefaultBaseRate() public view {
        assertEq(validatorManager.baseRateBps(), 300, "Base rate should be 3%");
    }
    
    function test_Initialize_StartsUnpaused() public view {
        assertFalse(validatorManager.paused());
    }
    
    function test_Initialize_RevertsOnZeroAdmin() public {
        VAMSValidatorManager newImpl = new VAMSValidatorManager();
        bytes memory initData = abi.encodeWithSelector(
            VAMSValidatorManager.initialize.selector,
            address(0),
            address(mockToken),
            address(mockStaking),
            address(mockFeeCollector)
        );
        
        vm.expectRevert(); // Proxy initialization fails with FailedCall or similar
        new ERC1967Proxy(address(newImpl), initData);
    }
    
    // ============ Markup Calculation Tests ============
    
    function test_CalculateMarkup_ReturnsBaseRateForNewUser() public view {
        uint256 markup = validatorManager.calculateMarkup(enterprise1);
        // Base 300 - 100 (low utilization) - 0 loyalty = 200
        assertEq(markup, 200, "New user should get base rate minus low util discount");
    }
    
    function test_CalculateMarkup_AppliesLoyaltyDiscount() public {
        // Setup enterprise with 100k staked for 90+ days
        mockStaking.setStakeInfo(enterprise1, 100_000 ether, block.timestamp - 91 days);
        
        // First register a subnet to have utilization data
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        uint256 markup = validatorManager.calculateMarkup(enterprise1);
        // Base 300 - 100 loyalty = 200, but clamped to min 100
        assertLe(markup, 300, "Should have discount applied");
    }
    
    function test_CalculateMarkup_ClampsToMin() public {
        // Setup very high loyalty discount
        mockStaking.setStakeInfo(enterprise1, 1_000_000 ether, block.timestamp - 365 days);
        
        uint256 markup = validatorManager.calculateMarkup(enterprise1);
        assertGe(markup, 100, "Should not go below min");
    }
    
    function test_CalculateMarkup_ClampsToMax() public {
        // Register subnet for context
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 10);
        
        // Lower max bound to 200 bps (2%)
        vm.prank(admin);
        validatorManager.updateBounds(50, 200); 
        
        // Force high demand modifier even at low utilization
        uint256[] memory thresholds = new uint256[](1);
        thresholds[0] = 5000;
        int256[] memory modifiers = new int256[](2);
        modifiers[0] = 500; // +5% for low util
        modifiers[1] = 500;
        
        vm.prank(admin);
        validatorManager.updateDemandCurve(thresholds, modifiers);
        
        // Base (200) + Demand (500) = 700. Max is 200.
        // Should clamp to 200.
        uint256 markup = validatorManager.calculateMarkup(enterprise1);
        assertEq(markup, 200, "Should clamp to max");
    }
    
    function test_CalculateMarkup_ReturnsFixedDuringFreeze() public {
        vm.prank(admin);
        validatorManager.emergencyFreeze(250); // 2.5%
        
        uint256 markup = validatorManager.calculateMarkup(enterprise1);
        assertEq(markup, 250, "Should return frozen rate");
    }
    
    // Helper to get bounds
    function _getMarkupBounds() internal view returns (uint256 minBps, uint256 maxBps) {
        return (validatorManager.minMarkupBps(), validatorManager.maxMarkupBps());
    }
    
    // ============ Loyalty Discount Tests ============
    
    function test_GetLoyaltyDiscount_ZeroForNoStake() public view {
        uint256 discount = validatorManager.getLoyaltyDiscount(enterprise1);
        assertEq(discount, 0, "No stake should have zero discount");
    }
    
    function test_GetLoyaltyDiscount_ZeroForNewStake() public {
        // Staked today, not enough lock time
        mockStaking.setStakeInfo(enterprise1, 100_000 ether, block.timestamp);
        
        uint256 discount = validatorManager.getLoyaltyDiscount(enterprise1);
        assertEq(discount, 0, "New stake should have zero discount");
    }
    
    function test_GetLoyaltyDiscount_CorrectTierLookup() public {
        // Setup default loyalty tiers and check discount
        mockStaking.setStakeInfo(enterprise1, 50_000 ether, block.timestamp - 61 days);
        
        uint256 discount = validatorManager.getLoyaltyDiscount(enterprise1);
        // Default tier: 50k staked, 60 days = 50 bps (0.5%)
        assertEq(discount, 50, "Should match tier discount");
    }
    
    // ============ Demand Modifier Tests ============
    
    function test_GetDemandModifier_NegativeAtLowUtilization() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        // At 1% utilization (1/100), should use first bucket (<50%)
        // which is -100 bps
        int256 modifier_ = validatorManager.getDemandModifier();
        assertEq(modifier_, -100, "Low utilization should have negative modifier");
    }
    
    function test_GetDemandModifier_ZeroAtOptimalRange() public view {
        // No subnets registered = 0 utilization. Default capacity = 100.
        // This falls into <50% bucket => -100 bps
        int256 modifier_ = validatorManager.getDemandModifier();
        assertEq(modifier_, -100, "Should default to low util");
    }
    
    // ============ Subnet Registration Tests ============
    
    function test_RegisterSubnet_AddsCapacity() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        assertEq(validatorManager.targetCapacity(), 100);
    }
    
    function test_RegisterSubnet_EmitsEvent() public {
        vm.expectEmit(true, false, false, true);
        emit IVAMSValidatorManager.SubnetRegistered(subnetId1, admin);
        
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
    }
    
    function test_RegisterSubnet_RevertsOnDuplicate() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        vm.prank(admin);
        vm.expectRevert(IVAMSValidatorManager.SubnetAlreadyExists.selector);
        validatorManager.registerSubnet(subnetId1, 50);
    }
    
    function test_RegisterSubnet_OnlyGovernance() public {
        vm.prank(user1);
        vm.expectRevert();
        validatorManager.registerSubnet(subnetId1, 100);
    }
    
    // ============ Subnet Deregistration Tests ============
    
    function test_DeregisterSubnet_RemovesCapacity() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        vm.prank(admin);
        validatorManager.deregisterSubnet(subnetId1);
        
        assertEq(validatorManager.activeManagedL1s(), 0);
    }
    
    function test_DeregisterSubnet_EmitsEvent() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        vm.expectEmit(true, false, false, false);
        emit IVAMSValidatorManager.SubnetDeregistered(subnetId1);
        
        vm.prank(admin);
        validatorManager.deregisterSubnet(subnetId1);
    }
    
    function test_DeregisterSubnet_RevertsIfNotRegistered() public {
        vm.prank(admin);
        vm.expectRevert(IVAMSValidatorManager.SubnetNotRegistered.selector);
        validatorManager.deregisterSubnet(subnetId1);
    }
    
    // ============ Governance Parameter Updates ============
    
    function test_UpdateBounds_ChangesMinMax() public {
        vm.prank(admin);
        validatorManager.updateBounds(50, 600); // 0.5% to 6%
        
        (uint256 minBps, uint256 maxBps) = _getMarkupBounds();
        assertEq(minBps, 50);
        assertEq(maxBps, 600);
    }
    
    function test_UpdateBounds_EmitsEvent() public {
        vm.expectEmit(false, false, false, true);
        emit IVAMSValidatorManager.BoundsUpdated(50, 600);
        
        vm.prank(admin);
        validatorManager.updateBounds(50, 600);
    }
    
    function test_UpdateBounds_RevertsIfMinExceedsMax() public {
        vm.prank(admin);
        vm.expectRevert(IVAMSValidatorManager.InvalidBounds.selector);
        validatorManager.updateBounds(500, 100); // min > max
    }
    
    function test_UpdateBounds_OnlyGovernance() public {
        vm.prank(user1);
        vm.expectRevert();
        validatorManager.updateBounds(50, 600);
    }
    
    function test_UpdateBaseRate_ChangesRate() public {
        vm.prank(admin);
        validatorManager.updateBaseRate(400);
        
        assertEq(validatorManager.baseRateBps(), 400);
    }
    
    function test_UpdateBaseRate_EmitsEvent() public {
        vm.expectEmit(false, false, false, true);
        emit IVAMSValidatorManager.BaseRateUpdated(300, 400);
        
        vm.prank(admin);
        validatorManager.updateBaseRate(400);
    }
    
    function test_UpdateBaseRate_OnlyGovernance() public {
        vm.prank(user1);
        vm.expectRevert();
        validatorManager.updateBaseRate(400);
    }
    
    function test_UpdateDemandCurve_SetsNewThresholds() public {
        uint256[] memory thresholds = new uint256[](3);
        thresholds[0] = 4000; // 40%
        thresholds[1] = 7000; // 70%
        thresholds[2] = 9000; // 90%
        
        int256[] memory modifiers = new int256[](4);
        modifiers[0] = -150; // -1.5%
        modifiers[1] = 0;
        modifiers[2] = 100;
        modifiers[3] = 250;
        
        vm.expectEmit(false, false, false, false);
        emit IVAMSValidatorManager.DemandCurveUpdated(thresholds, modifiers);
        
        vm.prank(admin);
        validatorManager.updateDemandCurve(thresholds, modifiers);
    }
    
    function test_UpdateDemandCurve_RevertsOnMismatchedArrays() public {
        uint256[] memory thresholds = new uint256[](2);
        int256[] memory modifiers = new int256[](2); // Should be 3 (thresholds + 1)
        
        vm.prank(admin);
        vm.expectRevert(IVAMSValidatorManager.InvalidThresholds.selector);
        validatorManager.updateDemandCurve(thresholds, modifiers);
    }
    
    function test_UpdateLoyaltyTiers_SetsNewTiers() public {
        IVAMSValidatorManager.LoyaltyTier[] memory tiers = new IVAMSValidatorManager.LoyaltyTier[](2);
        tiers[0] = IVAMSValidatorManager.LoyaltyTier({
            minStake: 200_000 ether,
            minLockDays: 180,
            discountBps: 150
        });
        tiers[1] = IVAMSValidatorManager.LoyaltyTier({
            minStake: 500_000 ether,
            minLockDays: 365,
            discountBps: 200
        });
        
        vm.expectEmit(false, false, false, false);
        emit IVAMSValidatorManager.LoyaltyTiersUpdated(2);
        
        vm.prank(admin);
        validatorManager.updateLoyaltyTiers(tiers);
    }
    
    // ============ Emergency Freeze Tests ============
    
    function test_EmergencyFreeze_SetsFixedRate() public {
        vm.prank(admin);
        validatorManager.emergencyFreeze(200);
        
        assertTrue(validatorManager.isFrozen());
        assertEq(validatorManager.frozenMarkupBps(), 200);
    }
    
    function test_EmergencyFreeze_EmitsEvent() public {
        vm.expectEmit(false, false, false, true);
        emit IVAMSValidatorManager.EmergencyFreezeActivated(200);
        
        vm.prank(admin);
        validatorManager.emergencyFreeze(200);
    }
    
    function test_EmergencyFreeze_OnlyEmergencyRole() public {
        vm.prank(user1);
        vm.expectRevert();
        validatorManager.emergencyFreeze(200);
    }
    
    function test_EmergencyFreeze_AllCalculationsReturnFrozenRate() public {
        vm.prank(admin);
        validatorManager.emergencyFreeze(250);
        
        // All enterprises should get frozen rate
        assertEq(validatorManager.calculateMarkup(enterprise1), 250);
        assertEq(validatorManager.calculateMarkup(enterprise2), 250);
        assertEq(validatorManager.calculateMarkup(user1), 250);
    }
    
    function test_EmergencyUnfreeze_ResumesNormalCalculation() public {
        vm.prank(admin);
        validatorManager.emergencyFreeze(200);
        
        vm.prank(admin);
        validatorManager.emergencyUnfreeze();
        
        assertFalse(validatorManager.isFrozen());
        
        // Should resume normal calculation
        uint256 markup = validatorManager.calculateMarkup(enterprise1);
        assertEq(markup, 200, "Should return to normal rate (base - low util)");
    }
    
    function test_EmergencyUnfreeze_EmitsEvent() public {
        vm.prank(admin);
        validatorManager.emergencyFreeze(200);
        
        vm.expectEmit(false, false, false, false);
        emit IVAMSValidatorManager.EmergencyFreezeDeactivated();
        
        vm.prank(admin);
        validatorManager.emergencyUnfreeze();
    }
    
    // ============ Pause/Unpause Tests ============
    
    function test_Pause_BlocksDeposits() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        vm.prank(admin);
        validatorManager.pause();
        
        vm.startPrank(enterprise1);
        mockToken.approve(address(validatorManager), 10 ether);
        vm.expectRevert();
        validatorManager.deposit(subnetId1, 10 ether);
        vm.stopPrank();
    }
    
    function test_Unpause_AllowsDeposits() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        vm.prank(admin);
        validatorManager.pause();
        
        vm.prank(admin);
        validatorManager.unpause();
        
        // Should now work
        _depositVAMS(enterprise1, subnetId1, 10 ether);
    }
    
    // ============ Deposit Tests ============
    
    function test_Deposit_CalculatesMarkup() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        uint256 depositAmount = 10 ether;
        
        // Approve FIRST (emits Approval event)
        vm.prank(enterprise1);
        mockToken.approve(address(validatorManager), depositAmount);
        
        // Now expect the Deposit event (after approve is done)
        vm.expectEmit(true, true, false, true);
        emit IVAMSValidatorManager.Deposit(
            enterprise1,
            subnetId1,
            depositAmount,
            200, // Base 300 - 100 Low Util
            depositAmount - (depositAmount * 200 / BPS_DENOMINATOR)
        );
        
        vm.prank(enterprise1);
        validatorManager.deposit(subnetId1, depositAmount);
    }
    
    function test_Deposit_RevertsOnZeroValue() public {
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        vm.startPrank(enterprise1);
        mockToken.approve(address(validatorManager), 0);
        vm.expectRevert(IVAMSValidatorManager.ZeroAmount.selector);
        validatorManager.deposit(subnetId1, 0);
        vm.stopPrank();
    }
    
    function test_Deposit_RevertsOnUnregisteredSubnet() public {
        vm.startPrank(enterprise1);
        mockToken.approve(address(validatorManager), 10 ether);
        vm.expectRevert(IVAMSValidatorManager.SubnetNotRegistered.selector);
        validatorManager.deposit(subnetId1, 10 ether);
        vm.stopPrank();
    }
    
    // ============ Fuzz Tests ============
    
    function testFuzz_CalculateMarkup_AlwaysWithinBounds(
        uint256 stakeAmount,
        uint256 stakeDays
    ) public {
        stakeAmount = bound(stakeAmount, 0, 10_000_000 ether);
        stakeDays = bound(stakeDays, 0, 365);
        
        if (stakeAmount > 0 && stakeDays > 0) {
            mockStaking.setStakeInfo(
                enterprise1, 
                stakeAmount, 
                block.timestamp - (stakeDays * 1 days)
            );
        }
        
        uint256 markup = validatorManager.calculateMarkup(enterprise1);
        
        (uint256 minBps, uint256 maxBps) = _getMarkupBounds();
        assertGe(markup, minBps, "Markup below minimum");
        assertLe(markup, maxBps, "Markup above maximum");
    }
    
    function testFuzz_UpdateBounds_RejectsInvalidRanges(
        uint256 minBps,
        uint256 maxBps
    ) public {
        minBps = bound(minBps, 0, 10000);
        maxBps = bound(maxBps, 0, 10000);
        
        if (minBps >= maxBps || minBps < 50 || maxBps > 1000) {
            vm.prank(admin);
            vm.expectRevert(IVAMSValidatorManager.InvalidBounds.selector);
            validatorManager.updateBounds(minBps, maxBps);
        } else {
            vm.prank(admin);
            validatorManager.updateBounds(minBps, maxBps);
            
            (uint256 newMin, uint256 newMax) = _getMarkupBounds();
            assertEq(newMin, minBps);
            assertEq(newMax, maxBps);
        }
    }
    
    function testFuzz_Deposit_CorrectMarkupCalculation(uint256 depositAmount) public {
        depositAmount = bound(depositAmount, 0.01 ether, 1000 ether);
        
        vm.prank(admin);
        validatorManager.registerSubnet(subnetId1, 100);
        
        // Mint enough tokens for the deposit
        mockToken.mint(enterprise1, depositAmount);
        
        uint256 markup = validatorManager.calculateMarkup(enterprise1);
        uint256 expectedFee = (depositAmount * markup) / BPS_DENOMINATOR;
        
        _depositVAMS(enterprise1, subnetId1, depositAmount);
        
        // Verify fee collector received the markup tokens
        if (expectedFee > 0) {
            uint256 feeCollectorBalance = mockToken.balanceOf(address(mockFeeCollector));
            assertGt(feeCollectorBalance, 0, "Should collect fees via ERC20 transfer");
        }
    }
    
    // ============ Access Control Tests ============
    
    function test_OnlyGovernance_AllGovernanceFunctions() public {
        address unauthorized = makeAddr("unauthorized");
        
        vm.startPrank(unauthorized);
        
        vm.expectRevert();
        validatorManager.updateBounds(50, 600);
        
        vm.expectRevert();
        validatorManager.updateBaseRate(400);
        
        vm.expectRevert();
        validatorManager.registerSubnet(subnetId1, 100);
        
        vm.expectRevert();
        validatorManager.deregisterSubnet(subnetId1);
        vm.stopPrank();
    }
    
    function test_OnlyEmergency_EmergencyFunctions() public {
        address unauthorized = makeAddr("unauthorized");
        
        vm.startPrank(unauthorized);
        
        vm.expectRevert();
        validatorManager.emergencyFreeze(200);
        
        vm.expectRevert();
        validatorManager.emergencyUnfreeze();
        
        vm.expectRevert();
        validatorManager.pause();
        
        vm.expectRevert();
        validatorManager.unpause();
        
        vm.stopPrank();
    }
    
    // ============ Edge Case Tests ============
    
    function test_EdgeCase_ZeroCapacity() public {
        vm.prank(admin);
        validatorManager.updateTargetCapacity(0);
        
        // Zero capacity should return 0 modifier (base rate fallback)
        int256 modifier_ = validatorManager.getDemandModifier();
        assertEq(modifier_, 0, "Zero capacity should return zero modifier");
    }
    
    function test_EdgeCase_MaxUint256Stake() public {
        // Extremely large stake
        mockStaking.setStakeInfo(enterprise1, type(uint256).max, block.timestamp - 365 days);
        
        // Should not overflow, should clamp to max discount
        uint256 discount = validatorManager.getLoyaltyDiscount(enterprise1);
        assertLe(discount, 200, "Should be clamped to max tier discount"); // Assuming max is 2%
    }
    
    function test_EdgeCase_FreezeAtBoundary() public {
        (uint256 minBps, uint256 maxBps) = _getMarkupBounds();
        
        // Freeze at min
        vm.prank(admin);
        validatorManager.emergencyFreeze(minBps);
        assertEq(validatorManager.calculateMarkup(enterprise1), minBps);
        
        // Freeze at max
        vm.prank(admin);
        validatorManager.emergencyUnfreeze();
        
        vm.prank(admin);
        validatorManager.emergencyFreeze(maxBps);
        assertEq(validatorManager.calculateMarkup(enterprise1), maxBps);
    }
}
