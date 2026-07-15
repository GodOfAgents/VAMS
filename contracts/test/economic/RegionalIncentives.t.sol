// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {RegionalIncentives} from "../../src/economic/RegionalIncentives.sol";
import {IRegionalIncentives} from "../../src/economic/IRegionalIncentives.sol";

contract RegionalIncentivesTest is Test {
    RegionalIncentives public incentives;
    address public admin = address(0xAD);
    address public updater = address(0xBB);
    address public stranger = address(0xCC);

    bytes32 public constant REGION_US_EAST = keccak256("us-east-1");
    bytes32 public constant REGION_AF_SOUTH = keccak256("af-south-1");
    bytes32 public constant REGION_EU_WEST = keccak256("eu-west-1");

    function setUp() public {
        vm.startPrank(admin);
        incentives = new RegionalIncentives(admin);
        incentives.grantRole(incentives.CAPACITY_UPDATER_ROLE(), updater);
        vm.stopPrank();
    }

    // ═══════════════════ Configuration ═══════════════════

    function test_setRegionConfig() public {
        vm.prank(admin);
        incentives.setRegionConfig(
            REGION_US_EAST,
            "US East (Virginia)",
            500, // target capacity
            10_000 // 1.0x (saturated — no boost)
        );

        IRegionalIncentives.RegionConfig memory cfg = incentives.getRegionConfig(REGION_US_EAST);
        assertEq(cfg.displayName, "US East (Virginia)");
        assertEq(cfg.targetCapacity, 500);
        assertEq(cfg.bootstrapMultiplierBps, 10_000);
        assertTrue(cfg.isActive);
    }

    function test_setRegionConfig_highMultiplier() public {
        vm.prank(admin);
        incentives.setRegionConfig(
            REGION_AF_SOUTH,
            "Africa (Cape Town)",
            50, // low target
            30_000 // 3.0x bootstrap
        );

        IRegionalIncentives.RegionConfig memory cfg = incentives.getRegionConfig(REGION_AF_SOUTH);
        assertEq(cfg.bootstrapMultiplierBps, 30_000);
    }

    function test_revert_invalidMultiplier() public {
        vm.prank(admin);
        vm.expectRevert("Multiplier must be between 1.0x and 5.0x");
        incentives.setRegionConfig(REGION_US_EAST, "test", 100, 5_000); // Below 1.0x
    }

    function test_revert_zeroTarget() public {
        vm.prank(admin);
        vm.expectRevert("Target capacity must be > 0");
        incentives.setRegionConfig(REGION_US_EAST, "test", 0, 20_000);
    }

    function test_revert_unauthorized() public {
        vm.prank(stranger);
        vm.expectRevert();
        incentives.setRegionConfig(REGION_US_EAST, "test", 100, 20_000);
    }

    // ═══════════════════ Multiplier Decay ═══════════════════

    function test_multiplier_emptyRegion() public {
        _setupRegion(REGION_AF_SOUTH, "Africa", 100, 30_000);

        // 0% capacity → full bootstrap (3.0×)
        uint256 mult = incentives.getRewardMultiplier(REGION_AF_SOUTH);
        assertEq(mult, 30_000);
    }

    function test_multiplier_below50pct() public {
        _setupRegion(REGION_AF_SOUTH, "Africa", 100, 30_000);
        _updateCapacity(REGION_AF_SOUTH, 30); // 30% fill

        // Still below 50% → full bootstrap
        uint256 mult = incentives.getRewardMultiplier(REGION_AF_SOUTH);
        assertEq(mult, 30_000);
    }

    function test_multiplier_at50pct() public {
        _setupRegion(REGION_AF_SOUTH, "Africa", 100, 30_000);
        _updateCapacity(REGION_AF_SOUTH, 50); // Exactly 50%

        // At 50% threshold → still full bootstrap
        uint256 mult = incentives.getRewardMultiplier(REGION_AF_SOUTH);
        assertEq(mult, 30_000);
    }

    function test_multiplier_at75pct() public {
        _setupRegion(REGION_AF_SOUTH, "Africa", 100, 30_000);
        _updateCapacity(REGION_AF_SOUTH, 75); // 75% fill

        // Midpoint of decay: 50% through the 50—100% range
        // Expected: 30000 - (20000 * 0.5) = 20000 (2.0×)
        uint256 mult = incentives.getRewardMultiplier(REGION_AF_SOUTH);
        assertEq(mult, 20_000);
    }

    function test_multiplier_at100pct() public {
        _setupRegion(REGION_AF_SOUTH, "Africa", 100, 30_000);
        _updateCapacity(REGION_AF_SOUTH, 100); // 100% fill

        // At target → 1.0×
        uint256 mult = incentives.getRewardMultiplier(REGION_AF_SOUTH);
        assertEq(mult, 10_000);
    }

    function test_multiplier_overcapacity() public {
        _setupRegion(REGION_AF_SOUTH, "Africa", 100, 30_000);
        _updateCapacity(REGION_AF_SOUTH, 200); // 200% over-capacity

        // Over target → still 1.0× (no negative incentive)
        uint256 mult = incentives.getRewardMultiplier(REGION_AF_SOUTH);
        assertEq(mult, 10_000);
    }

    function test_multiplier_unknownRegion() public view {
        bytes32 unknownId = keccak256("mars-1");
        uint256 mult = incentives.getRewardMultiplier(unknownId);
        assertEq(mult, 10_000); // Standard rate for unknown
    }

    // ═══════════════════ Capacity Updates ═══════════════════

    function test_updateCapacity() public {
        _setupRegion(REGION_EU_WEST, "EU West", 400, 15_000);

        vm.prank(updater);
        incentives.updateCapacity(REGION_EU_WEST, 200);

        IRegionalIncentives.RegionConfig memory cfg = incentives.getRegionConfig(REGION_EU_WEST);
        assertEq(cfg.currentCapacity, 200);
    }

    function test_batchUpdateCapacity() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);
        _setupRegion(REGION_EU_WEST, "EU West", 400, 15_000);

        bytes32[] memory ids = new bytes32[](2);
        ids[0] = REGION_US_EAST;
        ids[1] = REGION_EU_WEST;

        uint256[] memory caps = new uint256[](2);
        caps[0] = 300;
        caps[1] = 100;

        vm.prank(updater);
        incentives.batchUpdateCapacity(ids, caps);

        assertEq(incentives.getRegionConfig(REGION_US_EAST).currentCapacity, 300);
        assertEq(incentives.getRegionConfig(REGION_EU_WEST).currentCapacity, 100);
    }

    // ═══════════════════ Activation ═══════════════════

    function test_deactivateRegion() public {
        _setupRegion(REGION_AF_SOUTH, "Africa", 50, 30_000);

        vm.prank(admin);
        incentives.deactivateRegion(REGION_AF_SOUTH);

        assertFalse(incentives.isRegionActive(REGION_AF_SOUTH));
        // Deactivated → standard rate
        assertEq(incentives.getRewardMultiplier(REGION_AF_SOUTH), 10_000);
    }

    function test_reactivateRegion() public {
        _setupRegion(REGION_AF_SOUTH, "Africa", 50, 30_000);

        vm.prank(admin);
        incentives.deactivateRegion(REGION_AF_SOUTH);

        vm.prank(admin);
        incentives.activateRegion(REGION_AF_SOUTH);

        assertTrue(incentives.isRegionActive(REGION_AF_SOUTH));
        assertEq(incentives.getRewardMultiplier(REGION_AF_SOUTH), 30_000);
    }

    // ═══════════════════ Enumeration ═══════════════════

    function test_enumeration() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);
        _setupRegion(REGION_EU_WEST, "EU West", 400, 15_000);
        _setupRegion(REGION_AF_SOUTH, "Africa", 50, 30_000);

        assertEq(incentives.totalRegions(), 3);
    }

    // ═══════════════════ Economic & Game-Theoretic Hardening ═══════════════════

    function test_setEconomicParams() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);

        vm.prank(admin);
        incentives.setEconomicParams(REGION_US_EAST, 1500, 5); // pHardware = 1500, providerCount = 5

        (uint256 pHardware, uint256 providerCount) = incentives.getEconomicParams(REGION_US_EAST);
        assertEq(pHardware, 1500);
        assertEq(providerCount, 5);
    }

    function test_revert_setEconomicParams_unauthorized() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);

        vm.prank(stranger);
        vm.expectRevert();
        incentives.setEconomicParams(REGION_US_EAST, 1500, 5);
    }

    function test_getPriceFloor_sufficientLiquidity() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);

        // N = 10 providers -> alpha = 1.0 (10000 BPS), P_floor should match Bid_min (2000)
        vm.prank(admin);
        incentives.setEconomicParams(REGION_US_EAST, 1500, 10);

        uint256 floor = incentives.getPriceFloor(REGION_US_EAST, 2000);
        assertEq(floor, 2000);
    }

    function test_getPriceFloor_excessLiquidity() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);

        // N = 12 providers -> alpha = 1.0 (capped), P_floor should match Bid_min (2000)
        vm.prank(admin);
        incentives.setEconomicParams(REGION_US_EAST, 1500, 12);

        uint256 floor = incentives.getPriceFloor(REGION_US_EAST, 2000);
        assertEq(floor, 2000);
    }

    function test_getPriceFloor_thinLiquidity_half() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);

        // N = 5 providers -> alpha = 0.5 (5000 BPS)
        // P_floor = 0.5 * Bid_min (2000) + 0.5 * P_hardware (1500) = 1750
        vm.prank(admin);
        incentives.setEconomicParams(REGION_US_EAST, 1500, 5);

        uint256 floor = incentives.getPriceFloor(REGION_US_EAST, 2000);
        assertEq(floor, 1750);
    }

    function test_getPriceFloor_thinLiquidity_extreme() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);

        // N = 2 providers -> alpha = 0.2 (2000 BPS)
        // P_floor = 0.2 * Bid_min (2000) + 0.8 * P_hardware (1500) = 400 + 1200 = 1600
        vm.prank(admin);
        incentives.setEconomicParams(REGION_US_EAST, 1500, 2);

        uint256 floor = incentives.getPriceFloor(REGION_US_EAST, 2000);
        assertEq(floor, 1600);
    }

    function test_getPriceFloor_noLiquidity() public {
        _setupRegion(REGION_US_EAST, "US East", 500, 10_000);

        // N = 0 providers -> alpha = 0.0 (0 BPS)
        // P_floor = P_hardware (1500)
        vm.prank(admin);
        incentives.setEconomicParams(REGION_US_EAST, 1500, 0);

        uint256 floor = incentives.getPriceFloor(REGION_US_EAST, 2000);
        assertEq(floor, 1500);
    }

    function test_getPriceFloor_unconfiguredRegion() public view {
        bytes32 unknownId = keccak256("mars-1");
        // Unknown region -> fallback to raw Bid_min (2000)
        uint256 floor = incentives.getPriceFloor(unknownId, 2000);
        assertEq(floor, 2000);
    }

    // ═══════════════════ Helpers ═══════════════════

    function _setupRegion(bytes32 id, string memory name, uint256 target, uint256 multiplier) internal {
        vm.prank(admin);
        incentives.setRegionConfig(id, name, target, multiplier);
    }

    function _updateCapacity(bytes32 id, uint256 cap) internal {
        vm.prank(updater);
        incentives.updateCapacity(id, cap);
    }
}
