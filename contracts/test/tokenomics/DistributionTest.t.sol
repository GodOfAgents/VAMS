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
        // Community: 500M (50%)
        bytes32 commId = vesting.createVestingSchedule(deployer, 500_000_000 * 1e18, IVAMSVesting.ScheduleType.COMMUNITY, true);
        IVAMSVesting.VestingSchedule memory commSchedule = vesting.getSchedule(commId);
        assertEq(commSchedule.totalAmount, 500_000_000 * 1e18, "Community should be 500M");

        // Founder: 150M (15%) - NOTE: Using Custom Schedule logic if needed, but standard FOUNDER type
        // The Deploy script uses 100M for Founder based on 'Safe Revolutionary' Plan (10%)
        // WAIT - Proposal said 15% Founder?
        // Let's check the FINAL AGREED plan in Implementation Plan.
        // "Team & Advisors (YOU): 20% (10% Founder / 10% Future)"
        // "Insiders (40%): Team (20%) + Investors (10%) + DAO Treasury (10%)"
        // "Community (60%): Community (50%) + Airdrop (10%)"
        
        // So Founder is 10% (100M). My previous comment `Founder: 150M (15%)` in the Test Plan was from the REJECTED 15% plan.
        // The FINAL ACCEPTED plan is 10% Founder (100M) + 10% Future Team (100M) = 20% Team.
        // Deploy script used 100M. Correct.
        
        bytes32 founderId = vesting.createVestingSchedule(deployer, 100_000_000 * 1e18, IVAMSVesting.ScheduleType.FOUNDER, true);
        IVAMSVesting.VestingSchedule memory founderSchedule = vesting.getSchedule(founderId);
        assertEq(founderSchedule.totalAmount, 100_000_000 * 1e18, "Founder should be 100M");

        // Future Team: 100M (10%)
        bytes32 teamId = vesting.createVestingSchedule(deployer, 100_000_000 * 1e18, IVAMSVesting.ScheduleType.TEAM, true);
        assertEq(vesting.getSchedule(teamId).totalAmount, 100_000_000 * 1e18, "Team should be 100M");

        // Investors: 100M (10%)
        bytes32 invId = vesting.createVestingSchedule(deployer, 100_000_000 * 1e18, IVAMSVesting.ScheduleType.INVESTOR, true);
        assertEq(vesting.getSchedule(invId).totalAmount, 100_000_000 * 1e18, "Investor should be 100M");

        // DAO Treasury: 100M (10%) - Using FOUNDATION type
        bytes32 treasId = vesting.createVestingSchedule(deployer, 100_000_000 * 1e18, IVAMSVesting.ScheduleType.FOUNDATION, true);
        assertEq(vesting.getSchedule(treasId).totalAmount, 100_000_000 * 1e18, "Treasury should be 100M");
    }

    function test_TreasuryVestingParameters() public {
        // DAO Treasury (Foundation Type) should have 48 month vesting now
        bytes32 treasId = vesting.createVestingSchedule(deployer, 100_000_000 * 1e18, IVAMSVesting.ScheduleType.FOUNDATION, true);
        IVAMSVesting.VestingSchedule memory schedule = vesting.getSchedule(treasId);

        uint256 expectedDuration = 48 * 30 days;
        assertEq(schedule.vestingDuration, expectedDuration, "Treasury should vest over 48 months");
    }
}
