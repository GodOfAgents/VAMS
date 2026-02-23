// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/staking/VAMSStaking.sol";
import "../../src/staking/IVAMSStaking.sol";

/**
 * @title VAMSStakingTest
 * @notice Comprehensive tests for VAMSStaking contract
 */
contract VAMSStakingTest is BaseTest {
    VAMSStaking public staking;
    
    // Test constants
    uint256 constant MIN_STAKE = 50_000 ether;
    uint256 constant UNBONDING_PERIOD = 14 days;
    uint256 constant EMISSION_RATE = 0.2 ether;
    
    // Tier thresholds (from contract)
    uint256 constant SILVER_THRESHOLD = 100_000 ether;
    uint256 constant GOLD_THRESHOLD = 500_000 ether;
    uint256 constant PLATINUM_THRESHOLD = 1_000_001 ether;
    
    function setUp() public override {
        super.setUp();
        
        // Deploy staking contract with 4 parameters
        vm.prank(admin);
        staking = new VAMSStaking(
            address(token),   // stakingToken
            address(token),   // rewardToken (same in this case)
            EMISSION_RATE,    // rewardPerSecond
            admin             // admin
        );
        vm.label(address(staking), "VAMSStaking");
        
        // Fund staking contract for rewards
        _mintTo(address(staking), 10_000_000 ether);
    }
    
    // ============ Initialization Tests ============
    
    function test_Initialize_SetsStakingToken() public view {
        assertEq(address(staking.stakingToken()), address(token));
    }
    
    function test_Initialize_SetsRewardPerSecond() public view {
        assertEq(staking.rewardPerSecond(), EMISSION_RATE);
    }
    
    function test_Initialize_AdminHasRoles() public view {
        assertTrue(staking.hasRole(staking.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(staking.hasRole(staking.EMISSION_ADMIN_ROLE(), admin));
    }
    
    function test_Initialize_StartsUnpaused() public view {
        assertFalse(staking.paused());
    }
    
    function test_Initialize_ZeroTotalStaked() public view {
        assertEq(staking.totalStaked(), 0);
    }
    
    // ============ Staking Tests ============
    
    function test_Stake_IncreasesBalance() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        IVAMSStaking.StakeInfo memory info = staking.getStakeInfo(user1);
        assertEq(info.amount, amount);
    }
    
    function test_Stake_TransfersTokens() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        uint256 balanceBefore = token.balanceOf(address(staking));
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        assertEq(token.balanceOf(address(staking)), balanceBefore + amount);
    }
    
    function test_Stake_UpdatesTotalStaked() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        assertEq(staking.totalStaked(), amount);
    }
    
    function test_Stake_SetsLockPeriod() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.ThirtyDays);
        
        IVAMSStaking.StakeInfo memory info = staking.getStakeInfo(user1);
        assertEq(uint(info.lockPeriod), uint(IVAMSStaking.LockPeriod.ThirtyDays));
        assertEq(info.lockedUntil, block.timestamp + 30 days);
    }
    
    function test_Stake_EmitsEvent() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.expectEmit(true, false, false, true);
        emit IVAMSStaking.Staked(
            user1, 
            amount, 
            IVAMSStaking.LockPeriod.SevenDays, 
            block.timestamp + 7 days
        );
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
    }
    
    function test_Stake_RevertsOnZeroAmount() public {
        vm.prank(user1);
        vm.expectRevert(IVAMSStaking.ZeroAmount.selector);
        staking.stake(0, IVAMSStaking.LockPeriod.SevenDays);
    }
    
    function test_Stake_RevertsOnBelowMinimum() public {
        uint256 amount = MIN_STAKE - 1;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        vm.expectRevert(abi.encodeWithSelector(
            IVAMSStaking.BelowMinimumStake.selector,
            amount,
            MIN_STAKE
        ));
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
    }
    
    // ============ Tier Tests ============
    
    function test_Tier_None_Default() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        IVAMSStaking.StakingTier tier = staking.getTier(user1);
        assertEq(uint(tier), uint(IVAMSStaking.StakingTier.None));
    }
    
    function test_Tier_Silver_AtThreshold() public {
        uint256 amount = SILVER_THRESHOLD;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        IVAMSStaking.StakingTier tier = staking.getTier(user1);
        assertEq(uint(tier), uint(IVAMSStaking.StakingTier.Silver));
    }
    
    function test_Tier_Gold_AtThreshold() public {
        uint256 amount = GOLD_THRESHOLD;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        IVAMSStaking.StakingTier tier = staking.getTier(user1);
        assertEq(uint(tier), uint(IVAMSStaking.StakingTier.Gold));
    }
    
    function test_Tier_Platinum_AtThreshold() public {
        uint256 amount = PLATINUM_THRESHOLD;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        IVAMSStaking.StakingTier tier = staking.getTier(user1);
        assertEq(uint(tier), uint(IVAMSStaking.StakingTier.Platinum));
    }
    
    function test_Tier_EmitsEventOnChange() public {
        // First stake bronze
        _fundAndApprove(user1, address(staking), SILVER_THRESHOLD);
        
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        
        // Add stake to reach silver
        vm.expectEmit(true, false, false, true);
        emit IVAMSStaking.TierChanged(
            user1, 
            IVAMSStaking.StakingTier.None, 
            IVAMSStaking.StakingTier.Silver
        );
        
        vm.prank(user1);
        staking.addStake(SILVER_THRESHOLD - MIN_STAKE);
    }
    
    // ============ Unstaking Tests ============
    
    function test_Unstake_DecreasesBalance() public {
        uint256 stakeAmount = SILVER_THRESHOLD; // Need more than min for partial unstake
        uint256 unstakeAmount = 5000 ether;
        
        _fundAndApprove(user1, address(staking), stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        // Advance past lock
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        staking.unstake(unstakeAmount);
        
        IVAMSStaking.StakeInfo memory info = staking.getStakeInfo(user1);
        assertEq(info.amount, stakeAmount - unstakeAmount);
    }
    
    function test_Unstake_CreatesUnbondingRequest() public {
        uint256 stakeAmount = MIN_STAKE * 2;
        uint256 unstakeAmount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        staking.unstake(unstakeAmount);
        
        IVAMSStaking.UnbondingRequest memory request = staking.getUnbondingRequest(user1);
        assertEq(request.amount, unstakeAmount);
        assertEq(request.unbondingEnd, block.timestamp + UNBONDING_PERIOD);
    }
    
    function test_Unstake_EmitsEvent() public {
        uint256 stakeAmount = MIN_STAKE * 2;
        uint256 unstakeAmount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), stakeAmount);
        
        vm.prank(user1);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.expectEmit(true, false, false, true);
        emit IVAMSStaking.Unstaked(user1, unstakeAmount, block.timestamp + UNBONDING_PERIOD);
        
        vm.prank(user1);
        staking.unstake(unstakeAmount);
    }
    
    function test_Unstake_RevertsBeforeLockExpiry() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.ThirtyDays);
        
        // Try to unstake before lock expires
        _advanceTime(15 days);
        
        IVAMSStaking.StakeInfo memory info = staking.getStakeInfo(user1);
        
        vm.prank(user1);
        vm.expectRevert(abi.encodeWithSelector(
            IVAMSStaking.StakeLocked.selector,
            info.lockedUntil
        ));
        staking.unstake(amount);
    }
    
    function test_Unstake_RevertsIfMoreThanStaked() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        vm.expectRevert(abi.encodeWithSelector(
            IVAMSStaking.InsufficientStake.selector,
            amount + 1,
            amount
        ));
        staking.unstake(amount + 1);
    }
    
    function test_Unstake_RevertsOnZeroAmount() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        vm.expectRevert(IVAMSStaking.ZeroAmount.selector);
        staking.unstake(0);
    }
    
    // ============ Withdrawal Tests ============
    
    function test_Withdraw_TransfersTokens() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        staking.unstake(amount);
        
        // Wait for unbonding
        _advanceTime(UNBONDING_PERIOD + 1);
        
        uint256 balanceBefore = token.balanceOf(user1);
        
        vm.prank(user1);
        staking.withdraw();
        
        assertEq(token.balanceOf(user1), balanceBefore + amount);
    }
    
    function test_Withdraw_ClearsUnbondingRequest() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        staking.unstake(amount);
        
        _advanceTime(UNBONDING_PERIOD + 1);
        
        vm.prank(user1);
        staking.withdraw();
        
        IVAMSStaking.UnbondingRequest memory request = staking.getUnbondingRequest(user1);
        assertEq(request.amount, 0);
    }
    
    function test_Withdraw_EmitsEvent() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        staking.unstake(amount);
        
        _advanceTime(UNBONDING_PERIOD + 1);
        
        vm.expectEmit(true, false, false, true);
        emit IVAMSStaking.Withdrawn(user1, amount);
        
        vm.prank(user1);
        staking.withdraw();
    }
    
    function test_Withdraw_RevertsBeforeUnbonding() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        staking.unstake(amount);
        
        _advanceTime(UNBONDING_PERIOD - 1 hours); // Not enough time
        
        IVAMSStaking.UnbondingRequest memory request = staking.getUnbondingRequest(user1);
        
        vm.prank(user1);
        vm.expectRevert(abi.encodeWithSelector(
            IVAMSStaking.UnbondingNotComplete.selector,
            request.unbondingEnd
        ));
        staking.withdraw();
    }
    
    function test_Withdraw_RevertsNoRequest() public {
        vm.prank(user1);
        vm.expectRevert(IVAMSStaking.NoUnbondingRequest.selector);
        staking.withdraw();
    }
    
    // ============ Rewards Tests ============
    
    function test_ClaimRewards_TransfersEarned() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        // Advance time to accumulate rewards
        _advanceTime(1 days);
        
        uint256 pending = staking.pendingRewards(user1);
        assertTrue(pending > 0, "Should have pending rewards");
        
        uint256 balanceBefore = token.balanceOf(user1);
        
        vm.prank(user1);
        uint256 claimed = staking.claimRewards();
        
        assertTrue(claimed > 0, "Should claim rewards");
        assertEq(token.balanceOf(user1), balanceBefore + claimed);
    }
    
    function test_ClaimRewards_EmitsEvent() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(1 days);
        
        vm.expectEmit(true, false, false, false); // Don't check amount exactly
        emit IVAMSStaking.RewardsClaimed(user1, 0);
        
        vm.prank(user1);
        staking.claimRewards();
    }
    
    function test_ClaimRewards_RevertsIfNone() public {
        uint256 amount = MIN_STAKE;
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        // Try to claim immediately after staking (no rewards accumulated)
        vm.prank(user1);
        vm.expectRevert(IVAMSStaking.NothingToClaim.selector);
        staking.claimRewards();
    }
    
    // ============ Governance Power Tests ============
    
    function test_VotingPower_ScalesWithTier() public {
        // Stake bronze amount
        _fundAndApprove(user1, address(staking), MIN_STAKE);
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        
        // Stake silver amount
        _fundAndApprove(user2, address(staking), SILVER_THRESHOLD);
        vm.prank(user2);
        staking.stake(SILVER_THRESHOLD, IVAMSStaking.LockPeriod.SevenDays);
        
        uint256 bronzePower = staking.getVotingPower(user1);
        uint256 silverPower = staking.getVotingPower(user2);
        
        // Silver should have more voting power per token
        assertTrue(silverPower / SILVER_THRESHOLD >= bronzePower / MIN_STAKE);
    }
    
    function test_VotingPower_ScalesWithLockPeriod() public {
        _fundAndApprove(user1, address(staking), MIN_STAKE);
        _fundAndApprove(user2, address(staking), MIN_STAKE);
        
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        
        vm.prank(user2);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.OneEightyDays);
        
        uint256 power7Days = staking.getVotingPower(user1);
        uint256 power180Days = staking.getVotingPower(user2);
        
        assertTrue(power180Days > power7Days, "Longer lock should have more power");
    }
    
    // ============ CLR Operator Eligibility Tests ============
    
    function test_CLROperator_PlatinumOnly() public {
        // Below Silver tier (None)
        _fundAndApprove(user1, address(staking), MIN_STAKE);
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        
        assertFalse(staking.isCLROperatorEligible(user1));
        
        // Platinum tier
        _fundAndApprove(user2, address(staking), PLATINUM_THRESHOLD);
        vm.prank(user2);
        staking.stake(PLATINUM_THRESHOLD, IVAMSStaking.LockPeriod.SevenDays);
        
        assertTrue(staking.isCLROperatorEligible(user2));
    }
    
    // ============ Admin Tests ============
    
    function test_UpdateEmissionRate_Works() public {
        uint256 newRate = 0.4 ether;
        
        vm.prank(admin);
        staking.updateEmissionRate(newRate);
        
        assertEq(staking.rewardPerSecond(), newRate);
    }
    
    function test_UpdateEmissionRate_EmitsEvent() public {
        uint256 newRate = 0.4 ether;
        
        vm.expectEmit(false, false, false, true);
        emit IVAMSStaking.EmissionRateUpdated(EMISSION_RATE, newRate);
        
        vm.prank(admin);
        staking.updateEmissionRate(newRate);
    }
    
    function test_UpdateEmissionRate_OnlyAdmin() public {
        vm.prank(user1);
        vm.expectRevert();
        staking.updateEmissionRate(0.4 ether);
    }
    
    function test_Pause_BlocksStaking() public {
        vm.prank(admin);
        staking.pause();
        
        _fundAndApprove(user1, address(staking), MIN_STAKE);
        
        vm.prank(user1);
        vm.expectRevert();
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
    }
    
    function test_Unpause_EnablesStaking() public {
        vm.prank(admin);
        staking.pause();
        
        vm.prank(admin);
        staking.unpause();
        
        _fundAndApprove(user1, address(staking), MIN_STAKE);
        
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        
        IVAMSStaking.StakeInfo memory info = staking.getStakeInfo(user1);
        assertEq(info.amount, MIN_STAKE);
    }
    
    // ============ Fuzz Tests ============
    
    function testFuzz_Stake(uint256 amount) public {
        amount = bound(amount, MIN_STAKE, 10_000_000 ether);
        
        _fundAndApprove(user1, address(staking), amount);
        
        vm.prank(user1);
        staking.stake(amount, IVAMSStaking.LockPeriod.SevenDays);
        
        IVAMSStaking.StakeInfo memory info = staking.getStakeInfo(user1);
        assertEq(info.amount, amount);
    }
    
    function testFuzz_StakeUnstake(uint256 stakeAmt, uint256 unstakeAmt) public {
        stakeAmt = bound(stakeAmt, MIN_STAKE * 2, 10_000_000 ether);
        unstakeAmt = bound(unstakeAmt, 1, stakeAmt);
        
        _fundAndApprove(user1, address(staking), stakeAmt);
        
        vm.prank(user1);
        staking.stake(stakeAmt, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(7 days + 1);
        
        vm.prank(user1);
        staking.unstake(unstakeAmt);
        
        IVAMSStaking.StakeInfo memory info = staking.getStakeInfo(user1);
        assertEq(info.amount, stakeAmt - unstakeAmt);
    }
    
    function testFuzz_RewardsAccumulate(uint256 timeElapsed) public {
        timeElapsed = bound(timeElapsed, 1 hours, 365 days);
        
        _fundAndApprove(user1, address(staking), MIN_STAKE);
        
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        
        _advanceTime(timeElapsed);
        
        uint256 pending = staking.pendingRewards(user1);
        assertTrue(pending > 0, "Should accumulate rewards over time");
    }
}
