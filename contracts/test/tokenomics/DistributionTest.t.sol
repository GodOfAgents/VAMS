// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../src/token/VAMSToken.sol";
import "../../src/vesting/VAMSVesting.sol";
import "../../src/vesting/IVAMSVesting.sol";

contract DistributionTest is Test {
    VAMSToken token;
    VAMSVesting vesting;
    address deployer;

    function setUp() public {
        deployer = address(this);

        // 1. Deploy Token
        token = new VAMSToken(deployer, deployer);

        // 2. Deploy Vesting
        vesting = new VAMSVesting(address(token), deployer);

        // 3. Fund Vesting (Total 900M for distribution test)
        token.approve(address(vesting), 900_000_000 * 1e18);
    }

    function test_TotalSupply() public {
        assertEq(token.totalSupply(), 1_000_000_000 * 1e18, "Total Supply should be 1B");
    }

    function test_SovereignDistribution() public {
        // Community: 400M (40%)
        bytes32 commId =
            vesting.createVestingSchedule(deployer, 400_000_000 * 1e18, IVAMSVesting.ScheduleType.COMMUNITY, true);
        IVAMSVesting.VestingSchedule memory commSchedule = vesting.getSchedule(commId);
        assertEq(commSchedule.totalAmount, 400_000_000 * 1e18, "Community should be 400M");

        // Founder: 120M (12%)
        bytes32 founderId =
            vesting.createVestingSchedule(deployer, 120_000_000 * 1e18, IVAMSVesting.ScheduleType.FOUNDER, true);
        IVAMSVesting.VestingSchedule memory founderSchedule = vesting.getSchedule(founderId);
        assertEq(founderSchedule.totalAmount, 120_000_000 * 1e18, "Founder should be 120M");

        // Future Team: 130M (13%)
        bytes32 teamId =
            vesting.createVestingSchedule(deployer, 130_000_000 * 1e18, IVAMSVesting.ScheduleType.TEAM, true);
        assertEq(vesting.getSchedule(teamId).totalAmount, 130_000_000 * 1e18, "Team should be 130M");

        // Early Investors: 50M (5%)
        bytes32 earlyInvId =
            vesting.createVestingSchedule(deployer, 50_000_000 * 1e18, IVAMSVesting.ScheduleType.EARLY_INVESTOR, true);
        assertEq(vesting.getSchedule(earlyInvId).totalAmount, 50_000_000 * 1e18, "Early Investor should be 50M");

        // Regular Investors: 80M (8%)
        bytes32 regInvId =
            vesting.createVestingSchedule(deployer, 80_000_000 * 1e18, IVAMSVesting.ScheduleType.REG_INVESTOR, true);
        assertEq(vesting.getSchedule(regInvId).totalAmount, 80_000_000 * 1e18, "Regular Investor should be 80M");

        // DAO Treasury: 120M (12%) - Using FOUNDATION type
        bytes32 treasId =
            vesting.createVestingSchedule(deployer, 120_000_000 * 1e18, IVAMSVesting.ScheduleType.FOUNDATION, true);
        assertEq(vesting.getSchedule(treasId).totalAmount, 120_000_000 * 1e18, "Treasury should be 120M");
    }

    function test_TreasuryVestingParameters() public {
        // DAO Treasury (Foundation Type) should have 48 month vesting now
        bytes32 treasId =
            vesting.createVestingSchedule(deployer, 120_000_000 * 1e18, IVAMSVesting.ScheduleType.FOUNDATION, true);
        IVAMSVesting.VestingSchedule memory schedule = vesting.getSchedule(treasId);

        uint256 expectedDuration = 48 * 30 days;
        assertEq(schedule.vestingDuration, expectedDuration, "Treasury should vest over 48 months");
    }
}
