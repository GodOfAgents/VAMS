// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {VAMSToken} from "../../src/token/VAMSToken.sol";
import {VAMSVesting} from "../../src/vesting/VAMSVesting.sol";
import {IVAMSVesting} from "../../src/vesting/IVAMSVesting.sol";

contract MockGmvOracleForVesting {
    enum Mode {
        ReturnValue,
        RevertCall,
        ShortReturn,
        TrailingReturn
    }

    Mode public mode;
    uint256 public value;

    function configure(Mode newMode, uint256 newValue) external {
        mode = newMode;
        value = newValue;
    }

    function currentGmv() external view returns (uint256) {
        if (mode == Mode.RevertCall) revert("oracle unavailable");
        if (mode == Mode.ShortReturn) {
            assembly ("memory-safe") {
                mstore(0, 1)
                return(31, 1)
            }
        }
        if (mode == Mode.TrailingReturn) {
            assembly ("memory-safe") {
                mstore(0, 1)
                mstore(32, 2)
                return(0, 64)
            }
        }
        return value;
    }
}

/// @notice Regressions for dormant vesting schedule math, GMV failure handling,
/// and locked-token conservation. This suite does not activate vesting.
contract VestingAuditRegressionTest is Test {
    uint256 internal constant ONE_MONTH = 30 days;
    uint256 internal constant TEAM_THRESHOLD = 100;

    VAMSToken internal token;
    VAMSVesting internal vesting;
    MockGmvOracleForVesting internal oracle;

    function setUp() public {
        token = new VAMSToken(address(this), address(this));
        vesting = new VAMSVesting(address(token), address(this));
        oracle = new MockGmvOracleForVesting();

        // The test exercises the real capped VAMS token. Exempt only this
        // test vesting instance so large planned allocations can be prefunded.
        token.addExemptAddress(address(vesting));
        token.approve(address(vesting), type(uint256).max);
    }

    function test_PostCliffScheduleDurationsAndAppendixSnapshots() public {
        // These are the linear time-vested schedule amounts. TEAM and
        // FOUNDATION release remains separately blocked until their existing
        // GMV threshold is satisfied; this test does not define 50/50 tranches.
        uint256 unit = 1e18;
        bytes32 communityId = _create(IVAMSVesting.ScheduleType.COMMUNITY, 400_000_000 * unit, address(this));
        bytes32 architectId = _create(IVAMSVesting.ScheduleType.ARCHITECT, 120_000_000 * unit, address(this));
        bytes32 teamId = _create(IVAMSVesting.ScheduleType.TEAM, 130_000_000 * unit, address(this));
        bytes32 earlyId = _create(IVAMSVesting.ScheduleType.EARLY_INVESTOR, 50_000_000 * unit, address(this));
        bytes32 regularId = _create(IVAMSVesting.ScheduleType.REG_INVESTOR, 80_000_000 * unit, address(this));
        bytes32 foundationId = _create(IVAMSVesting.ScheduleType.FOUNDATION, 120_000_000 * unit, address(this));

        _assertStoredDuration(architectId, 12, 48);
        _assertStoredDuration(teamId, 12, 36);
        _assertStoredDuration(earlyId, 6, 18);
        _assertStoredDuration(regularId, 12, 30);
        _assertStoredDuration(foundationId, 6, 48);
        _assertStoredDuration(communityId, 0, 60);

        uint256 start = vesting.tgeTimestamp();
        vm.warp(start + 24 * ONE_MONTH);
        assertEq(vesting.vestedAmount(communityId), 160_000_000 * unit, "community M24");
        assertEq(vesting.vestedAmount(architectId), 30_000_000 * unit, "architect M24");
        assertEq(vesting.vestedAmount(teamId), (130_000_000 * unit * 12) / 36, "team M24");
        assertEq(vesting.vestedAmount(earlyId), 50_000_000 * unit, "early investors M24");
        assertEq(vesting.vestedAmount(regularId), 32_000_000 * unit, "regular investors M24");
        assertEq(vesting.vestedAmount(foundationId), 45_000_000 * unit, "treasury M24");

        vm.warp(start + 36 * ONE_MONTH);
        assertEq(vesting.vestedAmount(communityId), 240_000_000 * unit, "community M36");
        assertEq(vesting.vestedAmount(architectId), 60_000_000 * unit, "architect M36");
        assertEq(vesting.vestedAmount(teamId), (130_000_000 * unit * 24) / 36, "team M36");
        assertEq(vesting.vestedAmount(earlyId), 50_000_000 * unit, "early investors M36");
        assertEq(vesting.vestedAmount(regularId), 64_000_000 * unit, "regular investors M36");
        assertEq(vesting.vestedAmount(foundationId), 75_000_000 * unit, "treasury M36");
    }

    function test_ArchitectCliffAndCompletionBoundaries() public {
        _assertScheduleBoundaries(IVAMSVesting.ScheduleType.ARCHITECT, 12, 48);
    }

    function test_TeamCliffAndCompletionBoundaries() public {
        _assertScheduleBoundaries(IVAMSVesting.ScheduleType.TEAM, 12, 36);
    }

    function test_EarlyInvestorCliffAndCompletionBoundaries() public {
        _assertScheduleBoundaries(IVAMSVesting.ScheduleType.EARLY_INVESTOR, 6, 18);
    }

    function test_RegularInvestorCliffAndCompletionBoundaries() public {
        _assertScheduleBoundaries(IVAMSVesting.ScheduleType.REG_INVESTOR, 12, 30);
    }

    function test_FoundationCliffAndCompletionBoundaries() public {
        _assertScheduleBoundaries(IVAMSVesting.ScheduleType.FOUNDATION, 6, 48);
    }

    function test_CommunityCompletionBoundaries() public {
        _assertScheduleBoundaries(IVAMSVesting.ScheduleType.COMMUNITY, 0, 60);
    }

    function test_RevokeClearsAllRemainingLockedAccountingAndConservesTokens() public {
        uint256 amount = 1_000 ether;
        bytes32 scheduleId = vesting.createCustomSchedule(address(0xBEEF), amount, 0, 100 days, 0, true);
        assertEq(vesting.totalLocked(), amount, "initial locked balance");

        vm.warp(vesting.tgeTimestamp() + 40 days);
        assertEq(vesting.release(scheduleId), 400 ether, "first release");
        assertEq(vesting.totalLocked(), 600 ether, "locked after first release");

        vm.warp(vesting.tgeTimestamp() + 60 days);
        vesting.revoke(scheduleId);

        IVAMSVesting.VestingSchedule memory schedule = vesting.getSchedule(scheduleId);
        assertTrue(schedule.revoked, "schedule marked revoked");
        assertEq(schedule.releasedAmount, 600 ether, "beneficiary total released");
        assertEq(token.balanceOf(address(0xBEEF)), 600 ether, "vested tokens reach beneficiary");
        assertEq(token.balanceOf(address(this)), token.INITIAL_SUPPLY() - 600 ether, "unvested tokens return to admin");
        assertEq(token.balanceOf(address(vesting)), 0, "vesting holds no residual tokens");
        assertEq(vesting.totalLocked(), 0, "all outstanding locked amount cleared");
    }

    function test_GmvConfigurationMissingDeniesEveryReleaseAndRevokePath() public {
        bytes32 scheduleId = _createTeamSchedule(address(this));
        _warpTeamToHalfVested();
        vesting.setGmvThreshold(TEAM_THRESHOLD);
        // Oracle intentionally remains unset.
        _expectEveryGatedPathToRevert(scheduleId);
    }

    function test_ZeroGmvThresholdDeniesEveryReleaseAndRevokePath() public {
        bytes32 scheduleId = _createTeamSchedule(address(this));
        _warpTeamToHalfVested();
        vesting.setGmvOracle(address(oracle));
        _expectEveryGatedPathToRevert(scheduleId);
    }

    function test_RevertingShortAndBelowThresholdOracleDenyEveryPath() public {
        bytes32 scheduleId = _createTeamSchedule(address(this));
        _warpTeamToHalfVested();
        vesting.setGmvOracle(address(oracle));
        vesting.setGmvThreshold(TEAM_THRESHOLD);

        oracle.configure(MockGmvOracleForVesting.Mode.RevertCall, TEAM_THRESHOLD);
        _expectEveryGatedPathToRevert(scheduleId);

        oracle.configure(MockGmvOracleForVesting.Mode.ShortReturn, TEAM_THRESHOLD);
        _expectEveryGatedPathToRevert(scheduleId);

        oracle.configure(MockGmvOracleForVesting.Mode.TrailingReturn, TEAM_THRESHOLD);
        _expectEveryGatedPathToRevert(scheduleId);

        oracle.configure(MockGmvOracleForVesting.Mode.ReturnValue, TEAM_THRESHOLD - 1);
        _expectEveryGatedPathToRevert(scheduleId);
    }

    function test_PrecliffTeamRevokeFailsClosedWithoutOracleAndPreservesAccounting() public {
        _assertPrecliffRevokeFailureModes(IVAMSVesting.ScheduleType.TEAM);
    }

    function test_PrecliffFoundationRevokeFailsClosedWithoutOracleAndPreservesAccounting() public {
        _assertPrecliffRevokeFailureModes(IVAMSVesting.ScheduleType.FOUNDATION);
    }

    function test_GmvEqualityAllowsAllPublicReleasePathsAndRevokeTransfer() public {
        vesting.setGmvOracle(address(oracle));
        vesting.setGmvThreshold(TEAM_THRESHOLD);
        oracle.configure(MockGmvOracleForVesting.Mode.ReturnValue, TEAM_THRESHOLD);

        bytes32 directId = _createTeamSchedule(address(0x101));
        bytes32 batchId = _createTeamSchedule(address(0x102));
        bytes32 allId = _createTeamSchedule(address(this));
        bytes32 revokeId = _createTeamSchedule(address(0x104));
        _warpTeamToHalfVested();

        assertEq(vesting.release(directId), 500 ether, "direct release at threshold");
        bytes32[] memory ids = new bytes32[](1);
        ids[0] = batchId;
        assertEq(vesting.batchRelease(ids), 500 ether, "batch release at threshold");
        assertEq(vesting.releaseAll(), 500 ether, "releaseAll at threshold");
        vesting.revoke(revokeId);

        assertEq(token.balanceOf(address(0x101)), 500 ether, "direct beneficiary paid");
        assertEq(token.balanceOf(address(0x102)), 500 ether, "batch beneficiary paid");
        assertEq(token.balanceOf(address(0x104)), 500 ether, "revoke beneficiary paid vested share");
        IVAMSVesting.VestingSchedule memory revokedSchedule = vesting.getSchedule(revokeId);
        assertEq(revokedSchedule.releasedAmount, 500 ether, "revoke records vested release");
        assertEq(vesting.totalLocked(), 1_500 ether, "only three unrevoked halves remain locked");

        // Keep the otherwise-unused schedule identifier live in the test's
        // expected state assertions and prove it remains individually queryable.
        assertEq(vesting.vestedAmount(allId), 500 ether, "releaseAll schedule vested amount");
    }

    function _assertStoredDuration(bytes32 scheduleId, uint256 cliffMonths, uint256 linearMonths) internal view {
        IVAMSVesting.VestingSchedule memory schedule = vesting.getSchedule(scheduleId);
        assertEq(schedule.cliffDuration, cliffMonths * ONE_MONTH, "stored cliff");
        assertEq(schedule.vestingDuration, (cliffMonths + linearMonths) * ONE_MONTH, "stored total duration");
    }

    function _assertScheduleBoundaries(
        IVAMSVesting.ScheduleType scheduleType,
        uint256 cliffMonths,
        uint256 linearMonths
    ) internal {
        uint256 amount = 10_000 ether;
        bytes32 scheduleId = _create(scheduleType, amount, address(this));
        uint256 start = vesting.tgeTimestamp();
        uint256 cliffAt = start + cliffMonths * ONE_MONTH;
        uint256 completeAt = start + (cliffMonths + linearMonths) * ONE_MONTH;

        if (cliffMonths > 0) {
            vm.warp(cliffAt - 1);
            assertEq(vesting.vestedAmount(scheduleId), 0, "nothing before cliff");
        }
        vm.warp(cliffAt);
        assertEq(vesting.vestedAmount(scheduleId), 0, "zero unlock at cliff");

        vm.warp(completeAt - 1);
        assertLt(vesting.vestedAmount(scheduleId), amount, "not fully vested before completion");
        vm.warp(completeAt);
        assertEq(vesting.vestedAmount(scheduleId), amount, "fully vested at completion");
    }

    function _create(IVAMSVesting.ScheduleType scheduleType, uint256 amount, address beneficiary)
        internal
        returns (bytes32)
    {
        return vesting.createVestingSchedule(beneficiary, amount, scheduleType, true);
    }

    function _createTeamSchedule(address beneficiary) internal returns (bytes32) {
        return _create(IVAMSVesting.ScheduleType.TEAM, 1_000 ether, beneficiary);
    }

    function _warpTeamToHalfVested() internal {
        vm.warp(vesting.tgeTimestamp() + 30 * ONE_MONTH);
    }

    function _expectEveryGatedPathToRevert(bytes32 scheduleId) internal {
        vm.expectRevert();
        vesting.release(scheduleId);

        bytes32[] memory ids = new bytes32[](1);
        ids[0] = scheduleId;
        vm.expectRevert();
        vesting.batchRelease(ids);

        vm.expectRevert();
        vesting.releaseAll();

        vm.expectRevert();
        vesting.revoke(scheduleId);
    }

    function _assertPrecliffRevokeFailureModes(IVAMSVesting.ScheduleType scheduleType) internal {
        address beneficiary = address(0xBEEF);
        bytes32 scheduleId = _create(scheduleType, 1_000 ether, beneficiary);
        uint256 lockedBefore = vesting.totalLocked();
        uint256 vestingBalanceBefore = token.balanceOf(address(vesting));
        uint256 adminBalanceBefore = token.balanceOf(address(this));
        uint256 beneficiaryBalanceBefore = token.balanceOf(beneficiary);
        assertEq(vesting.vestedAmount(scheduleId), 0, "schedule is pre-cliff");

        vesting.setGmvThreshold(TEAM_THRESHOLD);

        // An unset oracle is not treated as permission to refund the schedule.
        vesting.setGmvOracle(address(0));
        _expectPrecliffRevokeDeniedAndUnchanged(
            scheduleId, beneficiary, lockedBefore, vestingBalanceBefore, adminBalanceBefore, beneficiaryBalanceBefore
        );

        vesting.setGmvOracle(address(oracle));
        oracle.configure(MockGmvOracleForVesting.Mode.RevertCall, TEAM_THRESHOLD);
        _expectPrecliffRevokeDeniedAndUnchanged(
            scheduleId, beneficiary, lockedBefore, vestingBalanceBefore, adminBalanceBefore, beneficiaryBalanceBefore
        );

        oracle.configure(MockGmvOracleForVesting.Mode.ShortReturn, TEAM_THRESHOLD);
        _expectPrecliffRevokeDeniedAndUnchanged(
            scheduleId, beneficiary, lockedBefore, vestingBalanceBefore, adminBalanceBefore, beneficiaryBalanceBefore
        );

        oracle.configure(MockGmvOracleForVesting.Mode.TrailingReturn, TEAM_THRESHOLD);
        _expectPrecliffRevokeDeniedAndUnchanged(
            scheduleId, beneficiary, lockedBefore, vestingBalanceBefore, adminBalanceBefore, beneficiaryBalanceBefore
        );

        oracle.configure(MockGmvOracleForVesting.Mode.ReturnValue, TEAM_THRESHOLD - 1);
        _expectPrecliffRevokeDeniedAndUnchanged(
            scheduleId, beneficiary, lockedBefore, vestingBalanceBefore, adminBalanceBefore, beneficiaryBalanceBefore
        );
    }

    function _expectPrecliffRevokeDeniedAndUnchanged(
        bytes32 scheduleId,
        address beneficiary,
        uint256 lockedBefore,
        uint256 vestingBalanceBefore,
        uint256 adminBalanceBefore,
        uint256 beneficiaryBalanceBefore
    ) internal {
        vm.expectRevert();
        vesting.revoke(scheduleId);

        IVAMSVesting.VestingSchedule memory schedule = vesting.getSchedule(scheduleId);
        assertFalse(schedule.revoked, "failed revoke marked schedule revoked");
        assertEq(schedule.releasedAmount, 0, "failed revoke changed released accounting");
        assertEq(vesting.totalLocked(), lockedBefore, "failed revoke changed locked accounting");
        assertEq(token.balanceOf(address(vesting)), vestingBalanceBefore, "failed revoke moved vesting tokens");
        assertEq(token.balanceOf(address(this)), adminBalanceBefore, "failed revoke refunded admin");
        assertEq(token.balanceOf(beneficiary), beneficiaryBalanceBefore, "failed revoke paid beneficiary");
    }
}
