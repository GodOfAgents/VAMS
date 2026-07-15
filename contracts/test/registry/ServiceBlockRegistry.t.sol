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
    uint256 private builder1Pk = 0xB1;
    uint256 private builder2Pk = 0xB2;
    address public builder1;
    address public builder2;
    address public agent1 = address(0xA1);
    address public composerBot = address(0xCB);

    uint256 public constant STAKE = 1_000 * 1e18;

    function setUp() public {
        builder1 = vm.addr(builder1Pk);
        builder2 = vm.addr(builder2Pk);

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
        bytes32 specHash = keccak256(abi.encodePacked("spec_", "test_block"));
        IServiceBlockRegistry.ServiceBlockManifest memory manifest = _manifest(builder1);
        bytes memory signature =
            _signManifest(builder1Pk, builder1, "test_block", "celestia://vams-ns/blob123", specHash, manifest);
        vm.expectRevert("Block already registered");
        registry.registerServiceBlock(
            _registration("test_block", "TEST", "desc", specHash, "celestia://vams-ns/blob123", 1500, 0, manifest),
            signature
        );
        vm.stopPrank();
    }

    function test_register_revert_highRevenueShare() public {
        vm.startPrank(builder1);
        vams.approve(address(registry), STAKE);
        bytes32 specHash = keccak256("spec");
        IServiceBlockRegistry.ServiceBlockManifest memory manifest = _manifest(builder1);
        bytes memory signature =
            _signManifest(builder1Pk, builder1, "greedy_block", "celestia://ns/blob123", specHash, manifest);
        vm.expectRevert("Revenue share too high");
        registry.registerServiceBlock(
            _registration("greedy_block", "TEST", "desc", specHash, "celestia://ns/blob123", 6000, 0, manifest),
            signature
        );
        vm.stopPrank();
    }

    function test_register_recordsSkillOpsManifest() public {
        bytes32 blockId = _registerBlock(builder1, "skillops_block", "AI");

        IServiceBlockRegistry.ServiceBlock memory blk = registry.getServiceBlock(blockId);
        assertEq(blk.manifestHash, keccak256("manifest"));
        assertEq(blk.capabilityRoot, keccak256("capabilities"));
        assertEq(blk.permissionsBitmap, 1);
    }

    function test_register_revert_invalidManifestSigner() public {
        vm.startPrank(builder1);
        vams.approve(address(registry), STAKE);

        bytes32 specHash = keccak256("spec");
        IServiceBlockRegistry.ServiceBlockManifest memory manifest = _manifest(builder1);
        bytes memory signature =
            _signManifest(builder2Pk, builder1, "bad_sig_block", "celestia://ns/blob123", specHash, manifest);

        vm.expectRevert("Invalid manifest signature");
        registry.registerServiceBlock(
            _registration("bad_sig_block", "TEST", "desc", specHash, "celestia://ns/blob123", 1500, 0, manifest),
            signature
        );
        vm.stopPrank();
    }

    function test_register_revert_wrongRegistryReplay() public {
        ServiceBlockRegistry registry2 = new ServiceBlockRegistry(admin, address(vams));
        vm.startPrank(admin);
        registry2.grantRole(registry2.COMPOSER_ROLE(), composerBot);
        vm.stopPrank();

        vm.startPrank(builder1);
        vams.approve(address(registry2), STAKE);

        bytes32 specHash = keccak256("spec");
        IServiceBlockRegistry.ServiceBlockManifest memory manifest = _manifest(builder1);
        bytes memory signature =
            _signManifest(builder1Pk, builder1, "replay_block", "celestia://ns/blob123", specHash, manifest);

        vm.expectRevert("Invalid manifest signature");
        registry2.registerServiceBlock(
            _registration("replay_block", "TEST", "desc", specHash, "celestia://ns/blob123", 1500, 0, manifest),
            signature
        );
        vm.stopPrank();
    }

    function test_register_revert_unknownPermissionBitmap() public {
        vm.startPrank(builder1);
        vams.approve(address(registry), STAKE);

        bytes32 specHash = keccak256("spec");
        IServiceBlockRegistry.ServiceBlockManifest memory manifest = _manifest(builder1);
        manifest.permissionsBitmap = 1 << 99;
        bytes memory signature =
            _signManifest(builder1Pk, builder1, "bad_permission_block", "celestia://ns/blob123", specHash, manifest);

        vm.expectRevert("Unknown permission");
        registry.registerServiceBlock(
            _registration("bad_permission_block", "TEST", "desc", specHash, "celestia://ns/blob123", 1500, 0, manifest),
            signature
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

    function test_quarantine_blocksProvisioning() public {
        bytes32 blockId = _registerBlock(builder1, "quarantine_block", "AI");
        bytes32 reasonHash = keccak256("malicious manifest");

        vm.prank(admin);
        registry.quarantineServiceBlock(blockId, reasonHash);

        IServiceBlockRegistry.ServiceBlock memory blk = registry.getServiceBlock(blockId);
        assertTrue(blk.isQuarantined);
        assertEq(blk.quarantineReasonHash, reasonHash);

        vm.prank(composerBot);
        vm.expectRevert("Block quarantined");
        registry.recordProvision(blockId, agent1);
    }

    function test_clearQuarantine_restoresProvisioning() public {
        bytes32 blockId = _registerBlock(builder1, "clear_quarantine_block", "AI");

        vm.prank(admin);
        registry.quarantineServiceBlock(blockId, keccak256("review"));

        vm.prank(admin);
        registry.clearServiceBlockQuarantine(blockId);

        vm.prank(composerBot);
        registry.recordProvision(blockId, agent1);

        IServiceBlockRegistry.ServiceBlock memory blk = registry.getServiceBlock(blockId);
        assertFalse(blk.isQuarantined);
        assertEq(blk.quarantineReasonHash, bytes32(0));
        assertEq(blk.totalProvisions, 1);
    }

    function test_quarantine_revert_unauthorized() public {
        bytes32 blockId = _registerBlock(builder1, "unauth_quarantine_block", "AI");

        vm.prank(builder2);
        vm.expectRevert();
        registry.quarantineServiceBlock(blockId, keccak256("review"));
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

    function _registerBlock(address builder, string memory name, string memory category) internal returns (bytes32) {
        vm.startPrank(builder);
        vams.approve(address(registry), STAKE);
        bytes32 specHash = keccak256(abi.encodePacked("spec_", name));
        IServiceBlockRegistry.ServiceBlockManifest memory manifest = _manifest(builder);
        bytes32 blockId = registry.registerServiceBlock(
            _registration(
                name, category, "Test service block", specHash, "celestia://vams-ns/blob123", 1500, 0, manifest
            ),
            _signManifest(
                builder == builder1 ? builder1Pk : builder2Pk,
                builder,
                name,
                "celestia://vams-ns/blob123",
                specHash,
                manifest
            )
        );
        vm.stopPrank();
        return blockId;
    }

    function _manifest(address builder) internal pure returns (IServiceBlockRegistry.ServiceBlockManifest memory) {
        return IServiceBlockRegistry.ServiceBlockManifest({
            manifestHash: keccak256("manifest"),
            capabilityRoot: keccak256("capabilities"),
            permissionsBitmap: 1,
            manifestSigner: builder,
            manifestVersion: 1
        });
    }

    function _registration(
        string memory name,
        string memory category,
        string memory description,
        bytes32 resourceRequirementsHash,
        string memory deploymentCID,
        uint256 revenueShareBps,
        uint256 minTrustTier,
        IServiceBlockRegistry.ServiceBlockManifest memory manifest
    ) internal pure returns (IServiceBlockRegistry.ServiceBlockRegistration memory) {
        return IServiceBlockRegistry.ServiceBlockRegistration({
            name: name,
            category: category,
            description: description,
            resourceRequirementsHash: resourceRequirementsHash,
            deploymentCID: deploymentCID,
            revenueShareBps: revenueShareBps,
            minTrustTier: minTrustTier,
            manifest: manifest
        });
    }

    function _signManifest(
        uint256 privateKey,
        address builder,
        string memory name,
        string memory deploymentCID,
        bytes32 resourceRequirementsHash,
        IServiceBlockRegistry.ServiceBlockManifest memory manifest
    ) internal view returns (bytes memory) {
        bytes32 digest = registry.hashServiceBlockManifest(
            builder, name, deploymentCID, resourceRequirementsHash, manifest
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privateKey, digest);
        return abi.encodePacked(r, s, v);
    }
}
