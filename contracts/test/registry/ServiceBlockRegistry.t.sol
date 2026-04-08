// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {ServiceBlockRegistry} from "../../src/registry/ServiceBlockRegistry.sol";
import {IServiceBlockRegistry} from "../../src/interfaces/IServiceBlockRegistry.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @dev Mock VAMS token for testing
contract MockVAMS is ERC20 {
    constructor() ERC20("VAMS", "VAMS") {
        _mint(msg.sender, 1_000_000 * 1e18);
    }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract ServiceBlockRegistryTest is Test {
    ServiceBlockRegistry public registry;
    MockVAMS public vams;

    address public admin = address(0xAD);
    address public builder1 = address(0xB1);
    address public builder2 = address(0xB2);
    address public agent1 = address(0xA1);
    address public composerBot = address(0xCB);

    uint256 public constant STAKE = 1_000 * 1e18;

    function setUp() public {
        vm.startPrank(admin);

        vams = new MockVAMS();
        registry = new ServiceBlockRegistry(admin, address(vams));

        // Grant composer role
        registry.grantRole(registry.COMPOSER_ROLE(), composerBot);

        // Fund builders
        vams.transfer(builder1, 10_000 * 1e18);
        vams.transfer(builder2, 10_000 * 1e18);

        vm.stopPrank();
    }

    // ═══════════════════ Registration ═══════════════════

    function test_registerServiceBlock() public {
        bytes32 blockId = _registerBlock(builder1, "llama_inference", "AI");

        IServiceBlockRegistry.ServiceBlock memory blk = registry.getServiceBlock(blockId);
        assertEq(blk.name, "llama_inference");
        assertEq(blk.category, "AI");
        assertEq(blk.builder, builder1);
        assertEq(blk.revenueShareBps, 1500); // 15%
        assertTrue(blk.isActive);
        assertFalse(blk.isVerified);
        assertEq(blk.stakedAmount, STAKE);
    }

    function test_register_deductsStake() public {
        uint256 before = vams.balanceOf(builder1);
        _registerBlock(builder1, "test_block", "TEST");
        assertEq(vams.balanceOf(builder1), before - STAKE);
    }

    function test_register_revert_duplicate() public {
        _registerBlock(builder1, "test_block", "TEST");

        vm.startPrank(builder1);
        vams.approve(address(registry), STAKE);
        vm.expectRevert("Block already registered");
        registry.registerServiceBlock(
            "test_block", "TEST", "desc",
            keccak256("spec"), "celestia://ns/blob123",
            1500, 0
        );
        vm.stopPrank();
    }

    function test_register_revert_highRevenueShare() public {
        vm.startPrank(builder1);
        vams.approve(address(registry), STAKE);
        vm.expectRevert("Revenue share too high");
        registry.registerServiceBlock(
            "greedy_block", "TEST", "desc",
            keccak256("spec"), "celestia://ns/blob123",
            6000, // 60% > 50% max
            0
        );
        vm.stopPrank();
    }

    // ═══════════════════ Verification ═══════════════════

    function test_verifyServiceBlock() public {
        bytes32 blockId = _registerBlock(builder1, "verified_block", "AI");

        vm.prank(admin);
        registry.verifyServiceBlock(blockId);

        assertTrue(registry.getServiceBlock(blockId).isVerified);
    }

    function test_verify_revert_unauthorized() public {
        bytes32 blockId = _registerBlock(builder1, "test_block", "AI");

        vm.prank(builder2); // Not a verifier
        vm.expectRevert();
        registry.verifyServiceBlock(blockId);
    }

    // ═══════════════════ Revenue Share ═══════════════════

    function test_calculateBuilderRevenue() public {
        bytes32 blockId = _registerBlock(builder1, "revenue_block", "AI");

        uint256 usageFees = 100 * 1e18;
        uint256 builderShare = registry.calculateBuilderRevenue(blockId, usageFees);

        // 15% of 100 = 15
        assertEq(builderShare, 15 * 1e18);
    }

    // ═══════════════════ Provisioning ═══════════════════

    function test_recordProvision() public {
        bytes32 blockId = _registerBlock(builder1, "provision_block", "AI");

        vm.prank(composerBot);
        registry.recordProvision(blockId, agent1);

        assertEq(registry.getServiceBlock(blockId).totalProvisions, 1);

        vm.prank(composerBot);
        registry.recordProvision(blockId, agent1);

        assertEq(registry.getServiceBlock(blockId).totalProvisions, 2);
    }

    function test_provision_revert_unauthorized() public {
        bytes32 blockId = _registerBlock(builder1, "test_block", "AI");

        vm.prank(agent1); // Not COMPOSER_ROLE
        vm.expectRevert();
        registry.recordProvision(blockId, agent1);
    }

    // ═══════════════════ Deactivation & Stake ═══════════════════

    function test_deactivateServiceBlock() public {
        bytes32 blockId = _registerBlock(builder1, "deactivate_block", "AI");

        vm.prank(builder1);
        registry.deactivateServiceBlock(blockId);

        assertFalse(registry.getServiceBlock(blockId).isActive);
    }

    function test_withdrawStake_afterLockPeriod() public {
        bytes32 blockId = _registerBlock(builder1, "withdraw_block", "AI");

        vm.prank(builder1);
        registry.deactivateServiceBlock(blockId);

        // Fast forward past lock period
        vm.warp(block.timestamp + 91 days);

        uint256 before = vams.balanceOf(builder1);
        vm.prank(builder1);
        registry.withdrawStake(blockId);

        assertEq(vams.balanceOf(builder1), before + STAKE);
        assertEq(registry.getServiceBlock(blockId).stakedAmount, 0);
    }

    function test_withdrawStake_revert_tooEarly() public {
        bytes32 blockId = _registerBlock(builder1, "early_block", "AI");

        vm.prank(builder1);
        registry.deactivateServiceBlock(blockId);

        // Only 30 days — not enough
        vm.warp(block.timestamp + 30 days);

        vm.prank(builder1);
        vm.expectRevert("Stake still locked");
        registry.withdrawStake(blockId);
    }

    // ═══════════════════ Enumeration ═══════════════════

    function test_enumeration() public {
        _registerBlock(builder1, "block_a", "AI");
        _registerBlock(builder1, "block_b", "STORAGE");
        _registerBlock(builder2, "block_c", "DEFI");

        assertEq(registry.totalBlocks(), 3);
    }

    // ═══════════════════ Helpers ═══════════════════

    function _registerBlock(
        address builder,
        string memory name,
        string memory category
    ) internal returns (bytes32) {
        vm.startPrank(builder);
        vams.approve(address(registry), STAKE);
        bytes32 blockId = registry.registerServiceBlock(
            name,
            category,
            "Test service block",
            keccak256(abi.encodePacked("spec_", name)),
            "celestia://vams-ns/blob123",
            1500, // 15% revenue share
            0     // No trust tier requirement
        );
        vm.stopPrank();
        return blockId;
    }
}
