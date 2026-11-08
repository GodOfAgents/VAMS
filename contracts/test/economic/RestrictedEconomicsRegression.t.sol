// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {VAMSToken} from "../../src/token/VAMSToken.sol";
import {VAMSStaking} from "../../src/staking/VAMSStaking.sol";
import {IVAMSStaking} from "../../src/staking/IVAMSStaking.sol";
import {RewardDistributor} from "../../src/economic/RewardDistributor.sol";
import {VAMSRestrictedStaking} from "../../src/staking/VAMSRestrictedStaking.sol";

/// Uses the production token, with no initial distributor surplus.
contract RestrictedEconomicsRegressionTest is Test {
    VAMSToken internal token;
    RewardDistributor internal distributor;
    address internal constant PROVIDER = address(0x1234);
    address internal constant EMPTY_ACCUMULATOR = address(0x5678);

    function setUp() public {
        token = new VAMSToken(address(this), address(this));
        distributor = new RewardDistributor(address(this), address(token), address(0), address(0));
        distributor.grantRole(distributor.ACCUMULATOR_ROLE(), address(this));
        token.approve(address(distributor), type(uint256).max);
    }

    function test_builderCreditRequiresIncomingFunding() public {
        distributor.grantRole(distributor.ACCUMULATOR_ROLE(), EMPTY_ACCUMULATOR);
        vm.prank(EMPTY_ACCUMULATOR);
        vm.expectRevert();
        distributor.accumulateBuilderRevenue(PROVIDER, 100 ether);
        assertEq(distributor.getUnclaimedRewards(PROVIDER), 0);
        assertEq(distributor.totalDistributed(), 0);
    }

    function test_emergencyWithdrawalCannotTakePendingBacking() public {
        distributor.accumulateReward(PROVIDER, 100 ether, bytes32(0));
        vm.expectRevert();
        distributor.emergencyWithdraw(address(this), 100 ether);
        assertEq(token.balanceOf(address(distributor)), 100 ether);
        assertEq(distributor.getUnclaimedRewards(PROVIDER), 100 ether);
    }

    function test_fundedProviderCanClaimExactlyOnce() public {
        distributor.accumulateReward(PROVIDER, 100 ether, bytes32(0));
        vm.prank(PROVIDER);
        distributor.claimRewards();
        assertEq(token.balanceOf(PROVIDER), 100 ether);
        assertEq(token.balanceOf(address(distributor)), 0);
        vm.prank(PROVIDER);
        vm.expectRevert();
        distributor.claimRewards();
    }

    function test_fundedBuilderCreditPreservesLiabilitiesThroughClaim() public {
        distributor.accumulateBuilderRevenue(PROVIDER, 100 ether);
        assertEq(distributor.pendingLiabilities(), 100 ether);
        assertEq(token.balanceOf(address(distributor)), 100 ether);
        vm.prank(PROVIDER);
        distributor.claimRewards();
        assertEq(distributor.pendingLiabilities(), 0);
        assertEq(token.balanceOf(PROVIDER), 100 ether);
    }

    function test_onlySurplusCanBeRecovered() public {
        distributor.accumulateBuilderRevenue(PROVIDER, 100 ether);
        token.transfer(address(distributor), 23 ether);
        vm.expectRevert();
        distributor.emergencyWithdraw(address(this), 24 ether);
        distributor.emergencyWithdraw(address(this), 23 ether);
        assertEq(token.balanceOf(address(distributor)), distributor.pendingLiabilities());
        vm.prank(PROVIDER);
        distributor.claimRewards();
        assertEq(token.balanceOf(PROVIDER), 100 ether);
    }

    function test_restrictedEmissionsCannotBeActivatedByAdmin() public {
        VAMSRestrictedStaking restricted = new VAMSRestrictedStaking(address(token), address(this));
        vm.expectRevert(VAMSRestrictedStaking.RestrictedRewardsDisabled.selector);
        restricted.updateEmissionRate(1);
        vm.expectRevert(VAMSRestrictedStaking.RestrictedRewardsDisabled.selector);
        restricted.updateEmissionBudget(1);
        assertEq(restricted.rewardPerSecond(), 0);
        assertEq(restricted.annualEmissionBudget(), 0);
        assertFalse(restricted.rewardsEnabled());
        assertFalse(token.hasRole(token.MINTER_ROLE(), address(restricted)));
    }

    function _stake() internal returns (VAMSStaking staking) {
        staking = new VAMSStaking(address(token), address(token), 0, address(this));
        token.transfer(PROVIDER, 50_000 ether);
        vm.startPrank(PROVIDER);
        token.approve(address(staking), type(uint256).max);
        staking.stake(50_000 ether, IVAMSStaking.LockPeriod.SevenDays);
        vm.stopPrank();
        vm.warp(staking.getStakeInfo(PROVIDER).lockedUntil);
    }

    function test_emergencyExitCannotBypassPendingUnbonding() public {
        VAMSStaking staking = _stake();
        vm.prank(PROVIDER);
        staking.unstake(50_000 ether);
        vm.prank(PROVIDER);
        vm.expectRevert();
        staking.emergencyWithdraw();
        assertEq(staking.getUnbondingRequest(PROVIDER).amount, 50_000 ether);
        assertEq(token.balanceOf(PROVIDER), 0);
    }

    function test_emergencyExitRequiresUnbondingRequest() public {
        VAMSStaking staking = _stake();
        vm.prank(PROVIDER);
        vm.expectRevert();
        staking.emergencyWithdraw();
        assertEq(staking.getStakeInfo(PROVIDER).amount, 50_000 ether);
    }

    function testFuzz_matureRecoveryWorksWhilePaused(bool crisis) public {
        VAMSStaking staking = _stake();
        staking.setCrisisMode(crisis);
        vm.prank(PROVIDER);
        staking.unstake(50_000 ether);
        uint256 end = staking.getUnbondingRequest(PROVIDER).unbondingEnd;
        assertEq(end, block.timestamp + (crisis ? 30 days : 14 days));
        staking.pause();
        vm.warp(end - 1);
        vm.prank(PROVIDER);
        vm.expectRevert();
        staking.emergencyWithdraw();
        vm.warp(end);
        vm.prank(PROVIDER);
        staking.emergencyWithdraw();
        assertEq(token.balanceOf(PROVIDER), 50_000 ether);
        assertEq(staking.getUnbondingRequest(PROVIDER).amount, 0);
    }

    function test_partialRecoveryPreservesActiveStake() public {
        VAMSStaking staking = _stake();
        vm.prank(PROVIDER);
        staking.unstake(25_000 ether);
        vm.warp(staking.getUnbondingRequest(PROVIDER).unbondingEnd);
        vm.prank(PROVIDER);
        staking.emergencyWithdraw();
        assertEq(staking.getStakeInfo(PROVIDER).amount, 25_000 ether);
        assertEq(staking.totalStaked(), 25_000 ether);
        assertEq(token.balanceOf(PROVIDER), 25_000 ether);
    }

    function test_normalUnbondingCannotShortenExistingCrisisRequest() public {
        VAMSStaking staking = _stake();
        staking.setCrisisMode(true);
        vm.prank(PROVIDER);
        staking.unstake(25_000 ether);
        uint256 originalEnd = staking.getUnbondingRequest(PROVIDER).unbondingEnd;
        staking.setCrisisMode(false);
        vm.warp(block.timestamp + 1 days);
        vm.prank(PROVIDER);
        staking.unstake(25_000 ether);
        assertEq(staking.getUnbondingRequest(PROVIDER).unbondingEnd, originalEnd);
    }
}
