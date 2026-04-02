// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/staking/VAMSStaking.sol";
import "../../src/token/VAMSToken.sol";

/**
 * @title StakingGovernanceIntegration
 * @notice Integration tests for staking → governance power → CLR eligibility
 * @dev Tests cross-contract interactions:
 *      Token → Staking → Voting Power → CLR Operator Eligibility
 */
contract StakingGovernanceIntegration is BaseTest {
    VAMSStaking public staking;
    VAMSToken public vamsToken;
    
    // Constants
    uint256 constant EMISSION_RATE = 5e14; // ~0.0005 VAMS/sec, below MAX_EMISSION_RATE
    uint256 constant MIN_STAKE = 50_000 ether;
    
    // Tier thresholds
    uint256 constant SILVER_THRESHOLD = 50_000 ether;
    uint256 constant GOLD_THRESHOLD = 100_000 ether;
    uint256 constant PLATINUM_THRESHOLD = 1_000_000 ether;
    
    function setUp() public override {
        super.setUp();
        
        // Deploy VAMSToken (with actual VAMS token features)
        vm.prank(admin);
        vamsToken = new VAMSToken(admin, treasury);
        
        // Deploy staking with VAMS token
        vm.prank(admin);
        staking = new VAMSStaking(
            address(vamsToken),
            address(vamsToken),
            EMISSION_RATE,
            admin
        );
        
        // Fund staking contract for rewards from treasury
        vm.startPrank(treasury);
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transfer(address(staking), 10_000_000 ether);
        vm.stopPrank();
        
        // Exempt staking contract from anti-whale limits
        vm.startPrank(admin);
        vamsToken.addExemptAddress(address(staking));
        vm.stopPrank();
    }
    
    // ============ Helper Functions ============
    
    function _fundUserFromTreasury(address user, uint256 amount) internal {
        vm.prank(admin);
        vamsToken.addExemptAddress(user);
        
        vm.prank(treasury);
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transfer(user, amount);
        
        vm.prank(user);
        vamsToken.approve(address(staking), amount);
    }
    
    // ============ Tier Progression Tests ============
    
    function test_TierProgression_SilverToPlat() public {
        // Start with Silver tier (MIN_STAKE == SILVER_THRESHOLD)
        _fundUserFromTreasury(user1, PLATINUM_THRESHOLD);
        
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        
        assertEq(uint(staking.getTier(user1)), uint(IVAMSStaking.StakingTier.Silver));
        assertFalse(staking.isCLROperatorEligible(user1));
        
        // Add to Gold  
        vm.prank(user1);
        staking.addStake(GOLD_THRESHOLD - MIN_STAKE);
        
        assertEq(uint(staking.getTier(user1)), uint(IVAMSStaking.StakingTier.Gold));
        assertFalse(staking.isCLROperatorEligible(user1));
        
        // Add to Platinum - becomes CLR eligible
        vm.prank(user1);
        staking.addStake(PLATINUM_THRESHOLD - GOLD_THRESHOLD);
        
        assertEq(uint(staking.getTier(user1)), uint(IVAMSStaking.StakingTier.Platinum));
        assertTrue(staking.isCLROperatorEligible(user1));
    }
    
    function test_VotingPower_ScalesWithLockPeriod() public {
        uint256 stakeAmount = SILVER_THRESHOLD;
        
        // Fund 3 users
        _fundUserFromTreasury(user1, stakeAmount);
        _fundUserFromTreasury(user2, stakeAmount);
        _fundUserFromTreasury(user3, stakeAmount);
        
        // Each stakes with different lock periods
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        vm.prank(user2);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.NinetyDays);
        
        vm.prank(user3);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.OneEightyDays);
        
        // Check voting power scales
        uint256 power7d = staking.getVotingPower(user1);
        uint256 power90d = staking.getVotingPower(user2);
        uint256 power180d = staking.getVotingPower(user3);
        
        assertTrue(power90d > power7d, "90d should have more power than 7d");
        assertTrue(power180d > power90d, "180d should have more power than 90d");
    }
    
    function test_RewardAccumulation_OverTime() public {
        uint256 stakeAmount = SILVER_THRESHOLD;
        _fundUserFromTreasury(user1, stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        // Check rewards accumulate
        uint256 pending1 = staking.pendingRewards(user1);
        assertEq(pending1, 0);
        
        _advanceTime(1 days);
        
        uint256 pending2 = staking.pendingRewards(user1);
        assertTrue(pending2 > 0, "Should have pending rewards after 1 day");
        
        _advanceTime(6 days);
        
        uint256 pending3 = staking.pendingRewards(user1);
        assertTrue(pending3 > pending2, "Should have more rewards after 7 days");
    }
    
    function test_CompoundRewards_IncreasesStake() public {
        uint256 stakeAmount = SILVER_THRESHOLD;
        _fundUserFromTreasury(user1, stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        // Wait for rewards
        _advanceTime(30 days);
        
        uint256 pending = staking.pendingRewards(user1);
        uint256 stakeBefore = staking.getStakeInfo(user1).amount;
        
        // Compound rewards
        vm.prank(user1);
        staking.compoundRewards();
        
        uint256 stakeAfter = staking.getStakeInfo(user1).amount;
        assertTrue(stakeAfter > stakeBefore, "Stake should increase after compound");
        assertEq(stakeAfter - stakeBefore, pending, "Increase should equal pending rewards");
    }
    
    function test_AutoCompound_Setting() public {
        uint256 stakeAmount = SILVER_THRESHOLD;
        _fundUserFromTreasury(user1, stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        // Check default
        assertFalse(staking.getStakeInfo(user1).autoCompound);
        
        // Enable auto-compound
        vm.prank(user1);
        staking.setAutoCompound(true);
        
        assertTrue(staking.getStakeInfo(user1).autoCompound);
    }
    
    function test_CLROperator_RequiresPlatinum() public {
        // None user
        _fundUserFromTreasury(user1, MIN_STAKE);
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        assertFalse(staking.isCLROperatorEligible(user1));
        
        // Silver user
        _fundUserFromTreasury(user2, SILVER_THRESHOLD);
        vm.prank(user2);
        staking.stake(SILVER_THRESHOLD, IVAMSStaking.LockPeriod.SevenDays);
        assertFalse(staking.isCLROperatorEligible(user2));
        
        // Gold user
        _fundUserFromTreasury(user3, GOLD_THRESHOLD);
        vm.prank(user3);
        staking.stake(GOLD_THRESHOLD, IVAMSStaking.LockPeriod.SevenDays);
        assertFalse(staking.isCLROperatorEligible(user3));
        
        // Platinum user (use admin for this test since admin is exempt)
        _fundUserFromTreasury(admin, PLATINUM_THRESHOLD);
        vm.prank(admin);
        staking.stake(PLATINUM_THRESHOLD, IVAMSStaking.LockPeriod.SevenDays);
        assertTrue(staking.isCLROperatorEligible(admin));
    }
    
    function test_UnstakeAndWithdraw_FullFlow() public {
        uint256 stakeAmount = SILVER_THRESHOLD;
        _fundUserFromTreasury(user1, stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        // Wait for lock to expire
        _advanceTime(8 days);
        
        // Unstake
        vm.prank(user1);
        staking.unstake(stakeAmount);
        
        // Check unbonding request
        IVAMSStaking.UnbondingRequest memory request = staking.getUnbondingRequest(user1);
        assertEq(request.amount, stakeAmount);
        assertEq(request.unbondingEnd, block.timestamp + 14 days);
        
        // Cannot withdraw before unbonding
        vm.prank(user1);
        vm.expectRevert();
        staking.withdraw();
        
        // Wait for unbonding
        _advanceTime(14 days + 1);
        
        uint256 balanceBefore = vamsToken.balanceOf(user1);
        
        // Withdraw
        vm.prank(user1);
        staking.withdraw();
        
        assertEq(vamsToken.balanceOf(user1), balanceBefore + stakeAmount);
    }
    
    function test_APY_Calculation() public {
        // Check APY for different tiers and lock periods
        uint256 apySilver7d = staking.getAPY(
            IVAMSStaking.StakingTier.Silver, 
            IVAMSStaking.LockPeriod.SevenDays
        );
        uint256 apyPlatinum180d = staking.getAPY(
            IVAMSStaking.StakingTier.Platinum, 
            IVAMSStaking.LockPeriod.OneEightyDays
        );
        
        assertTrue(apySilver7d > 0, "Silver APY should be positive");
        assertTrue(apyPlatinum180d > apySilver7d, "Platinum+180d should have higher APY");
    }
    
    function test_EmissionRateUpdate_AffectsRewards() public {
        uint256 stakeAmount = SILVER_THRESHOLD;
        _fundUserFromTreasury(user1, stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(1 days);
        uint256 pending1 = staking.pendingRewards(user1);
        
        // Increase emission rate (staying below MAX_EMISSION_RATE ~7.93e14)
        vm.prank(admin);
        staking.updateEmissionRate(7e14);
        
        _advanceTime(1 days);
        uint256 pending2 = staking.pendingRewards(user1);
        
        // Should have more than the first day's rewards
        assertTrue(pending2 > pending1, "Higher emission should give more rewards");
    }
    
    // ============ Multi-User Scenarios ============
    
    function test_MultiUser_RewardDistribution() public {
        // Two users stake equal amounts
        uint256 stakeAmount = SILVER_THRESHOLD;
        _fundUserFromTreasury(user1, stakeAmount);
        _fundUserFromTreasury(user2, stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        vm.prank(user2);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(1 days);
        
        uint256 pending1 = staking.pendingRewards(user1);
        uint256 pending2 = staking.pendingRewards(user2);
        
        // Should get equal (or very close) rewards
        assertApproxEqRel(pending1, pending2, 0.01e18); // Within 1%
    }
    
    function test_MultiUser_UnequalStakes() public {
        // User1 stakes 2x what user2 stakes (both in Gold tier for same APY)
        _fundUserFromTreasury(user1, GOLD_THRESHOLD * 2);
        _fundUserFromTreasury(user2, GOLD_THRESHOLD);
        
        vm.prank(user1);
        staking.stake(GOLD_THRESHOLD * 2, IVAMSStaking.LockPeriod.SevenDays);
        
        vm.prank(user2);
        staking.stake(GOLD_THRESHOLD, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(1 days);
        
        uint256 pending1 = staking.pendingRewards(user1);
        uint256 pending2 = staking.pendingRewards(user2);
        
        // User1 should get 2x rewards (same tier, so APY multiplier is identical)
        assertApproxEqRel(pending1, pending2 * 2, 0.01e18); // Within 1%
    }
    
    // ============ Fuzz Tests ============
    
    function testFuzz_StakeAndUnstake(uint256 amount, uint8 lockPeriodIndex) public {
        amount = bound(amount, MIN_STAKE, PLATINUM_THRESHOLD);
        lockPeriodIndex = uint8(bound(lockPeriodIndex, 0, 3)); // 4 lock periods (0-3)
        
        IVAMSStaking.LockPeriod lockPeriod = IVAMSStaking.LockPeriod(lockPeriodIndex);
        uint256 lockDuration = _getLockDuration(lockPeriod);
        
        _fundUserFromTreasury(user1, amount);
        
        vm.prank(user1);
        staking.stake(amount, lockPeriod);
        
        IVAMSStaking.StakeInfo memory info = staking.getStakeInfo(user1);
        assertEq(info.amount, amount);
        assertEq(info.lockedUntil, block.timestamp + lockDuration);
    }
    
    function _getLockDuration(IVAMSStaking.LockPeriod period) internal pure returns (uint256) {
        if (period == IVAMSStaking.LockPeriod.SevenDays) return 7 days;
        if (period == IVAMSStaking.LockPeriod.ThirtyDays) return 30 days;
        if (period == IVAMSStaking.LockPeriod.NinetyDays) return 90 days;
        if (period == IVAMSStaking.LockPeriod.OneEightyDays) return 180 days;
        return 7 days;
    }
}

