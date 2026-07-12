// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {RegionAwareDEC} from "../../src/economic/RegionAwareDEC.sol";
import {IRegionAwareDEC} from "../../src/economic/IRegionAwareDEC.sol";
import {RegionalIncentives} from "../../src/economic/RegionalIncentives.sol";
import {IRegionalIncentives} from "../../src/economic/IRegionalIncentives.sol";

// ═══════════════════ Mock Contracts ═══════════════════

contract MockVAMSToken {
    mapping(address => uint256) public balances;
    mapping(address => mapping(address => uint256)) public allowances;

    function mint(address to, uint256 amount) external {
        balances[to] += amount;
    }

    function balanceOf(address account) external view returns (uint256) {
        return balances[account];
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        balances[msg.sender] -= amount;
        balances[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(balances[from] >= amount, "Insufficient balance");
        balances[from] -= amount;
        balances[to] += amount;
        return true;
    }

    function approve(address, uint256) external pure returns (bool) {
        return true;
    }
}

contract MockDEC {
    uint256 public currentEmissionRate;

    constructor(uint256 _rate) {
        currentEmissionRate = _rate;
    }

    function setRate(uint256 _rate) external {
        currentEmissionRate = _rate;
    }
}

// ═══════════════════ Test Suite ═══════════════════

contract RegionAwareDECTest is Test {
    RegionAwareDEC public dec;
    RegionalIncentives public ri;
    MockVAMSToken public token;
    MockDEC public mockDEC;

    address public admin = address(0xAD);
    address public keeper = address(0xEE);
    address public rewardDist = address(0xDD);

    // Region IDs
    bytes32 public US_EAST = keccak256("us-east-1");
    bytes32 public EU_WEST = keccak256("eu-west-1");
    bytes32 public AF_SOUTH = keccak256("af-south-1");
    bytes32 public AP_SOUTH = keccak256("ap-south-1");

    uint256 public constant TOTAL_SUPPLY = 1_000_000_000 ether;

    function setUp() public {
        // Deploy dependencies
        token = new MockVAMSToken();
        ri = new RegionalIncentives(admin);
        mockDEC = new MockDEC(200); // 2% annual

        // Deploy RegionAwareDEC
        dec = new RegionAwareDEC(
            admin,
            address(token),
            address(ri),
            address(mockDEC),
            TOTAL_SUPPLY
        );

        // Configure roles
        vm.startPrank(admin);
        dec.grantRole(dec.KEEPER_ROLE(), keeper);
        dec.setRewardDistributor(rewardDist);

        // Configure regions
        ri.setRegionConfig(US_EAST, "US East", 500, 10_000); // 1.0x
        ri.setRegionConfig(EU_WEST, "EU West", 400, 10_000); // 1.0x
        ri.setRegionConfig(AF_SOUTH, "Africa South", 50, 30_000); // 3.0x
        ri.setRegionConfig(AP_SOUTH, "Asia Pacific South", 150, 25_000); // 2.5x

        // Set capacities — US_EAST at target, EU_WEST at 75%, AF_SOUTH at 20%, AP_SOUTH at 40%
        ri.updateCapacity(US_EAST, 500);   // 100% → multiplier = 1.0x
        ri.updateCapacity(EU_WEST, 300);   // 75%  → multiplier = 1.5x (decay)
        ri.updateCapacity(AF_SOUTH, 10);   // 20%  → multiplier = 3.0x (full bootstrap)
        ri.updateCapacity(AP_SOUTH, 60);   // 40%  → multiplier = 2.5x (full bootstrap)
        vm.stopPrank();

        // Fund DEC with tokens for emission distribution
        token.mint(address(dec), 100_000_000 ether);
    }

    // ═══════════════════ Allocation Tests ═══════════════════

    function test_calculateRegionAllocations_producesCorrectAllocations() public view {
        IRegionAwareDEC.RegionEmissionAlloc[] memory allocs = dec.calculateRegionAllocations();

        assertEq(allocs.length, 4, "Should have 4 active regions");

        // Verify weighted capacities:
        // US_EAST:  500 capacity × 10000 multiplier = 5,000,000
        // EU_WEST:  300 capacity × midDecay multiplier
        // AF_SOUTH: 10 capacity × 30000 multiplier = 300,000
        // AP_SOUTH: 60 capacity × 25000 multiplier = 1,500,000

        // All allocation BPS should sum reasonably close to 10000
        uint256 totalBps = 0;
        for (uint256 i = 0; i < allocs.length; i++) {
            totalBps += allocs[i].allocationBps;
            assertTrue(allocs[i].weightedCapacity > 0, "Weighted capacity must be positive");
        }

        // Due to integer rounding, total may be slightly less than 10000
        assertTrue(totalBps <= 10_000, "Total BPS must not exceed 10000");
        assertTrue(totalBps >= 9_500, "Total BPS should be close to 10000");
    }

    function test_calculateRegionAllocations_appliesRegionCap() public {
        // Set a very low cap
        vm.prank(admin);
        dec.setRegionCap(2_000); // 20% cap

        IRegionAwareDEC.RegionEmissionAlloc[] memory allocs = dec.calculateRegionAllocations();

        for (uint256 i = 0; i < allocs.length; i++) {
            assertTrue(
                allocs[i].allocationBps <= 2_000,
                "No region should exceed the 20% cap"
            );
        }
    }

    function test_calculateRegionAllocations_emptyRegions() public {
        // Deploy fresh RI with no regions configured
        RegionalIncentives emptyRI = new RegionalIncentives(admin);
        vm.prank(admin);
        dec.setRegionalIncentives(address(emptyRI));

        IRegionAwareDEC.RegionEmissionAlloc[] memory allocs = dec.calculateRegionAllocations();
        assertEq(allocs.length, 0, "Should return empty for no regions");
    }

    function test_calculateRegionAllocations_allRegionsAtTarget() public {
        // Set all regions to 100%+ capacity → all multipliers = 1.0x
        vm.startPrank(admin);
        ri.updateCapacity(US_EAST, 600);
        ri.updateCapacity(EU_WEST, 500);
        ri.updateCapacity(AF_SOUTH, 100);
        ri.updateCapacity(AP_SOUTH, 200);
        vm.stopPrank();

        IRegionAwareDEC.RegionEmissionAlloc[] memory allocs = dec.calculateRegionAllocations();

        // All multipliers should be 1.0x, so allocation is proportional to raw capacity
        assertEq(allocs.length, 4);

        // Regions with higher capacity should get larger allocation
        // US_EAST (600) should have highest weighted capacity
        uint256 maxWeighted = 0;
        bytes32 maxRegion;
        for (uint256 i = 0; i < allocs.length; i++) {
            if (allocs[i].weightedCapacity > maxWeighted) {
                maxWeighted = allocs[i].weightedCapacity;
                maxRegion = allocs[i].regionId;
            }
        }
        assertEq(maxRegion, US_EAST, "US East should have highest allocation at saturation");
    }

    function test_calculateRegionAllocations_singleActiveRegion() public {
        // Deactivate all but one
        vm.startPrank(admin);
        ri.deactivateRegion(EU_WEST);
        ri.deactivateRegion(AF_SOUTH);
        ri.deactivateRegion(AP_SOUTH);
        vm.stopPrank();

        IRegionAwareDEC.RegionEmissionAlloc[] memory allocs = dec.calculateRegionAllocations();
        assertEq(allocs.length, 1, "Only 1 active region");

        // Single region gets capped at regionCapBps (default 3000 = 30%)
        assertTrue(
            allocs[0].allocationBps <= dec.regionCapBps(),
            "Single region should be capped"
        );
    }

    // ═══════════════════ Epoch Distribution Tests ═══════════════════

    function test_distributeEpochEmissions_success() public {
        // Advance time past epoch duration
        vm.warp(block.timestamp + 7 days + 1);

        vm.prank(keeper);
        uint256 emitted = dec.distributeEpochEmissions();

        assertTrue(emitted > 0, "Should emit tokens");
        assertEq(dec.currentEpoch(), 1, "Epoch should increment");

        // Reward distributor should have received tokens
        assertTrue(
            token.balanceOf(rewardDist) > 0,
            "RewardDistributor should receive tokens"
        );
    }

    function test_distributeEpochEmissions_reverts_beforeEpochElapsed() public {
        vm.prank(keeper);
        vm.expectRevert();
        dec.distributeEpochEmissions();
    }

    function test_distributeEpochEmissions_multipleEpochs() public {
        // Epoch 1
        vm.warp(block.timestamp + 7 days + 1);
        vm.prank(keeper);
        uint256 emitted1 = dec.distributeEpochEmissions();
        assertEq(dec.currentEpoch(), 1);

        // Epoch 2
        vm.warp(block.timestamp + 7 days + 1);
        vm.prank(keeper);
        uint256 emitted2 = dec.distributeEpochEmissions();
        assertEq(dec.currentEpoch(), 2);

        assertTrue(emitted1 > 0 && emitted2 > 0, "Both epochs should emit");
    }

    function test_distributeEpochEmissions_reverts_noActiveRegions() public {
        // Deactivate all regions
        vm.startPrank(admin);
        ri.deactivateRegion(US_EAST);
        ri.deactivateRegion(EU_WEST);
        ri.deactivateRegion(AF_SOUTH);
        ri.deactivateRegion(AP_SOUTH);
        vm.stopPrank();

        vm.warp(block.timestamp + 7 days + 1);

        vm.prank(keeper);
        vm.expectRevert(IRegionAwareDEC.NoActiveRegions.selector);
        dec.distributeEpochEmissions();
    }

    // ═══════════════════ Emission Budget Tests ═══════════════════

    function test_getEpochEmissionBudget_usesGlobalRate() public view {
        uint256 budget = dec.getEpochEmissionBudget();

        // 2% annual on 1B tokens = 20M annual
        // Weekly = 20M / 52.18 ≈ ~383,141 tokens
        // Allow reasonable range
        assertTrue(budget > 300_000 ether, "Budget too low");
        assertTrue(budget < 500_000 ether, "Budget too high");
    }

    function test_getEpochEmissionBudget_respondsToRateChange() public {
        uint256 budgetBefore = dec.getEpochEmissionBudget();

        // Double emission rate
        mockDEC.setRate(400); // 4%
        uint256 budgetAfter = dec.getEpochEmissionBudget();

        // Budget should approximately double
        assertTrue(budgetAfter > budgetBefore * 18 / 10, "Budget should increase");
        assertTrue(budgetAfter < budgetBefore * 22 / 10, "Budget increase should be ~2x");
    }

    // ═══════════════════ Access Control Tests ═══════════════════

    function test_distributeEpochEmissions_reverts_nonKeeper() public {
        vm.warp(block.timestamp + 7 days + 1);

        vm.prank(address(0xBEEF));
        vm.expectRevert();
        dec.distributeEpochEmissions();
    }

    function test_setRegionCap_reverts_nonAdmin() public {
        vm.prank(address(0xBEEF));
        vm.expectRevert();
        dec.setRegionCap(2_000);
    }

    function test_setRegionCap_reverts_invalidCap() public {
        vm.startPrank(admin);

        // Too low
        vm.expectRevert(abi.encodeWithSelector(IRegionAwareDEC.InvalidRegionCap.selector, 100));
        dec.setRegionCap(100);

        // Too high
        vm.expectRevert(abi.encodeWithSelector(IRegionAwareDEC.InvalidRegionCap.selector, 3_001));
        dec.setRegionCap(3_001);

        // INV-1 boundary remains configurable at exactly 30%.
        dec.setRegionCap(3_000);
        assertEq(dec.regionCapBps(), 3_000);

        vm.stopPrank();
    }

    // ═══════════════════ View Helpers ═══════════════════

    function test_timeUntilNextEpoch() public view {
        uint256 timeLeft = dec.timeUntilNextEpoch();
        assertTrue(timeLeft > 0, "Should have time remaining");
        assertTrue(timeLeft <= 7 days, "Should not exceed epoch duration");
    }

    function test_epochSummary_afterDistribution() public {
        vm.warp(block.timestamp + 7 days + 1);
        vm.prank(keeper);
        dec.distributeEpochEmissions();

        IRegionAwareDEC.EpochSummary memory summary = dec.getEpochSummary(1);
        assertEq(summary.epochId, 1);
        assertTrue(summary.totalEmitted > 0);
        assertEq(summary.regionCount, 4);
    }
}
