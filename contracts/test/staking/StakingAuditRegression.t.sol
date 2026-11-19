// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {VAMSToken} from "../../src/token/VAMSToken.sol";
import {IVAMSStaking} from "../../src/staking/IVAMSStaking.sol";
import {VAMSRestrictedStaking} from "../../src/staking/VAMSRestrictedStaking.sol";

/// Public-path regressions using the production token and restricted profile.
contract StakingAuditRegressionTest is Test {
    uint256 private constant USER_PK = 0xA11CE;
    uint256 private constant MIN_STAKE = 50_000 ether;

    VAMSToken private token;
    VAMSRestrictedStaking private staking;
    address private user;

    function setUp() public {
        user = vm.addr(USER_PK);
        token = new VAMSToken(address(this), address(this));
        staking = new VAMSRestrictedStaking(address(token), address(this));
        token.transfer(user, 100_000 ether);
    }

    function test_restrictedRealTokenRepeatedStakeAndPermitCannotShortenLock() public {
        _approveAndStake(MIN_STAKE, IVAMSStaking.LockPeriod.OneEightyDays);
        IVAMSStaking.StakeInfo memory initial = staking.getStakeInfo(user);

        vm.warp(block.timestamp + 1 days);
        _approveAndStake(1 ether, IVAMSStaking.LockPeriod.SevenDays);
        IVAMSStaking.StakeInfo memory afterStake = staking.getStakeInfo(user);
        assertEq(afterStake.lockedUntil, initial.lockedUntil);
        assertEq(uint256(afterStake.lockPeriod), uint256(IVAMSStaking.LockPeriod.OneEightyDays));
        assertEq(afterStake.stakedAt, initial.stakedAt);

        uint256 deadline = block.timestamp + 1 days;
        (uint8 v, bytes32 r, bytes32 s) = _permitSignature(1 ether, deadline);
        vm.prank(user);
        staking.stakeWithPermit(1 ether, IVAMSStaking.LockPeriod.SevenDays, deadline, v, r, s);

        IVAMSStaking.StakeInfo memory afterPermit = staking.getStakeInfo(user);
        assertEq(afterPermit.lockedUntil, initial.lockedUntil);
        assertEq(uint256(afterPermit.lockPeriod), uint256(IVAMSStaking.LockPeriod.OneEightyDays));
        assertEq(afterPermit.stakedAt, initial.stakedAt);

        vm.prank(user);
        vm.expectRevert(abi.encodeWithSelector(IVAMSStaking.StakeLocked.selector, initial.lockedUntil));
        staking.unstake(1 ether);

        assertEq(staking.rewardPerSecond(), 0);
        assertEq(staking.annualEmissionBudget(), 0);
        assertFalse(token.hasRole(token.MINTER_ROLE(), address(staking)));
        assertEq(staking.pendingRewards(user), 0);
    }

    function test_longerRestakeRenewsWholePositionAndShorterTypeWaitsUntilExpiry() public {
        _approveAndStake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        vm.warp(block.timestamp + 2 days);

        uint256 deadline = block.timestamp + 1 days;
        (uint8 v, bytes32 r, bytes32 s) = _permitSignature(1 ether, deadline);
        vm.prank(user);
        staking.stakeWithPermit(1 ether, IVAMSStaking.LockPeriod.NinetyDays, deadline, v, r, s);

        IVAMSStaking.StakeInfo memory renewed = staking.getStakeInfo(user);
        assertEq(renewed.lockedUntil, block.timestamp + 90 days);
        assertEq(uint256(renewed.lockPeriod), uint256(IVAMSStaking.LockPeriod.NinetyDays));
        assertEq(renewed.amount, MIN_STAKE + 1 ether);

        vm.warp(renewed.lockedUntil);
        _approveAndStake(1 ether, IVAMSStaking.LockPeriod.SevenDays);
        IVAMSStaking.StakeInfo memory reset = staking.getStakeInfo(user);
        assertEq(reset.lockedUntil, block.timestamp + 7 days);
        assertEq(uint256(reset.lockPeriod), uint256(IVAMSStaking.LockPeriod.SevenDays));
    }

    function test_nearExpiryShortRestakePreservesMaxDeadlineAndLongLockMultiplier() public {
        _approveAndStake(MIN_STAKE, IVAMSStaking.LockPeriod.OneEightyDays);
        IVAMSStaking.StakeInfo memory initial = staking.getStakeInfo(user);
        vm.warp(initial.lockedUntil - 1 days);

        _approveAndStake(1 ether, IVAMSStaking.LockPeriod.SevenDays);
        IVAMSStaking.StakeInfo memory renewed = staking.getStakeInfo(user);
        uint256 requestedEnd = block.timestamp + 7 days;

        assertEq(renewed.lockedUntil, requestedEnd, "lock must use max(existing end, new requested end)");
        assertGt(renewed.lockedUntil, initial.lockedUntil, "near-expiry top-up extends to its requested minimum");
        assertEq(
            uint256(renewed.lockPeriod),
            uint256(IVAMSStaking.LockPeriod.OneEightyDays),
            "short top-up must not lower the active lock multiplier"
        );

        vm.prank(user);
        vm.expectRevert(abi.encodeWithSelector(IVAMSStaking.StakeLocked.selector, requestedEnd));
        staking.unstake(1 ether);
    }

    function _approveAndStake(uint256 amount, IVAMSStaking.LockPeriod period) private {
        vm.prank(user);
        token.approve(address(staking), amount);
        vm.prank(user);
        staking.stake(amount, period);
    }

    function _permitSignature(uint256 amount, uint256 deadline)
        private
        view
        returns (uint8 v, bytes32 r, bytes32 s)
    {
        bytes32 permitTypeHash = keccak256(
            "Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)"
        );
        bytes32 structHash = keccak256(
            abi.encode(permitTypeHash, user, address(staking), amount, token.nonces(user), deadline)
        );
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", token.DOMAIN_SEPARATOR(), structHash));
        return vm.sign(USER_PK, digest);
    }
}
