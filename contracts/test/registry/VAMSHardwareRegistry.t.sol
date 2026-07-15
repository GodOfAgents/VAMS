// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {VAMSHardwareRegistry} from "../../src/registry/VAMSHardwareRegistry.sol";
import {IVAMSHardwareRegistry} from "../../src/interfaces/IVAMSHardwareRegistry.sol";
import {HardwareClasses} from "../../src/registry/HardwareClasses.sol";

/// @dev Minimal ERC20 mock for collateral transfers
contract MockVAMS is Test {
    string public name = "VAMS";
    string public symbol = "VAMS";
    uint8 public decimals = 18;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract VAMSHardwareRegistryTest is Test {
    VAMSHardwareRegistry public registry;
    MockVAMS public vams;

    address public owner = address(0x1);
    address public provider1 = address(0x2);
    address public provider2 = address(0x3);
    address public sentinel = address(0x4);
    address public governance = address(0x5);

    function setUp() public {
        // Deploy mock token
        vams = new MockVAMS();

        // Deploy registry behind proxy
        vm.startPrank(owner);
        VAMSHardwareRegistry impl = new VAMSHardwareRegistry();
        ERC1967Proxy proxy =
            new ERC1967Proxy(address(impl), abi.encodeCall(VAMSHardwareRegistry.initialize, (owner, address(vams))));
        registry = VAMSHardwareRegistry(address(proxy));

        // Grant roles
        registry.grantRole(registry.SENTINEL_ROLE(), sentinel);
        registry.grantRole(registry.GOVERNANCE_ROLE(), governance);
        vm.stopPrank();

        // Fund providers
        vams.mint(provider1, 500_000e18);
        vams.mint(provider2, 500_000e18);

        // Approve registry
        vm.prank(provider1);
        vams.approve(address(registry), type(uint256).max);
        vm.prank(provider2);
        vams.approve(address(registry), type(uint256).max);
    }

    // ═══════════════════ Pre-seeded Classes ═══════════════════

    function test_PreseededClasses_Count() public view {
        assertEq(registry.getRegisteredClassCount(), 11);
    }

    function test_PreseededClasses_GPU_H100_Info() public view {
        IVAMSHardwareRegistry.HardwareClassInfo memory cls = registry.getHardwareClass(HardwareClasses.GPU_H100);

        assertEq(cls.classId, HardwareClasses.GPU_H100);
        assertEq(keccak256(bytes(cls.name)), keccak256(bytes("GPU_H100")));
        assertEq(keccak256(bytes(cls.category)), keccak256(bytes("GPU")));
        assertEq(cls.minCollateral, 50_000e18);
        assertEq(cls.minBenchmarkScore, 8000);
        assertTrue(cls.isActive);
    }

    function test_PreseededClasses_TEE_SGX_Info() public view {
        IVAMSHardwareRegistry.HardwareClassInfo memory cls = registry.getHardwareClass(HardwareClasses.TEE_SGX);

        assertEq(cls.minCollateral, 30_000e18);
        assertEq(cls.minBenchmarkScore, 9000);
    }

    // ═══════════════════ Hardware Class Registration ═══════════════════

    function test_RegisterHardwareClass_Admin() public {
        bytes32 newClassId = keccak256("GPU_B200");

        vm.prank(governance);
        registry.registerHardwareClass(newClassId, "GPU_B200", "GPU", 100_000e18, 8500);

        assertEq(registry.getRegisteredClassCount(), 12);

        IVAMSHardwareRegistry.HardwareClassInfo memory cls = registry.getHardwareClass(newClassId);
        assertEq(keccak256(bytes(cls.name)), keccak256(bytes("GPU_B200")));
        assertEq(cls.minCollateral, 100_000e18);
        assertTrue(cls.isActive);
    }

    function test_RegisterHardwareClass_NonAdmin_Reverts() public {
        bytes32 newClassId = keccak256("TPU_V5");

        vm.prank(provider1);
        vm.expectRevert();
        registry.registerHardwareClass(newClassId, "TPU_V5", "TPU", 50_000e18, 8000);
    }

    function test_RegisterHardwareClass_DuplicateReverts() public {
        vm.prank(governance);
        vm.expectRevert(
            abi.encodeWithSelector(IVAMSHardwareRegistry.ClassAlreadyRegistered.selector, HardwareClasses.GPU_H100)
        );
        registry.registerHardwareClass(HardwareClasses.GPU_H100, "GPU_H100", "GPU", 50_000e18, 8000);
    }

    function test_DeactivateClass_StopsNewRegistrations() public {
        vm.prank(governance);
        registry.deactivateHardwareClass(HardwareClasses.STORAGE_HDD);

        // Try to register a node with deactivated class
        vm.prank(provider1);
        vm.expectRevert(
            abi.encodeWithSelector(IVAMSHardwareRegistry.ClassNotActive.selector, HardwareClasses.STORAGE_HDD)
        );
        registry.registerNode(HardwareClasses.STORAGE_HDD, "us-east-1", 100, 1e18, 86400);
    }

    function test_UpdateClassCollateral() public {
        vm.prank(governance);
        registry.updateClassCollateral(HardwareClasses.GPU_A100, 35_000e18);

        IVAMSHardwareRegistry.HardwareClassInfo memory cls = registry.getHardwareClass(HardwareClasses.GPU_A100);
        assertEq(cls.minCollateral, 35_000e18);
    }

    // ═══════════════════ Node Registration ═══════════════════

    function test_RegisterNode_Success() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(
            HardwareClasses.GPU_A100,
            "us-east-1",
            4, // 4 GPUs
            100e18, // 100 VAMS/hour
            86400 // 24h max booking
        );

        IVAMSHardwareRegistry.VAMSResourceNode memory node = registry.getNode(nodeId);
        assertEq(node.provider, provider1);
        assertEq(node.hwClass, HardwareClasses.GPU_A100);
        assertEq(keccak256(bytes(node.region)), keccak256(bytes("us-east-1")));
        assertEq(node.capacityUnits, 4);
        assertEq(node.reservationPrice, 100e18);
        assertEq(node.collateralStaked, 25_000e18); // A100 min collateral
        assertTrue(node.isActive);
        assertEq(node.benchmarkScore, 0); // Not yet benchmarked

        assertEq(registry.getTotalNodeCount(), 1);
        assertEq(registry.totalCollateral(), 25_000e18);
    }

    function test_RegisterNode_UnknownClass_Reverts() public {
        bytes32 unknownClass = keccak256("GPU_TOTALLY_FAKE");

        vm.prank(provider1);
        vm.expectRevert(abi.encodeWithSelector(IVAMSHardwareRegistry.ClassNotFound.selector, unknownClass));
        registry.registerNode(unknownClass, "us-east-1", 4, 100e18, 86400);
    }

    function test_RegisterNode_InvalidRegion_Reverts() public {
        vm.prank(provider1);
        vm.expectRevert(IVAMSHardwareRegistry.InvalidRegion.selector);
        registry.registerNode(HardwareClasses.CPU_EPYC, "", 8, 50e18, 86400);
    }

    function test_RegisterNode_EmitsEvent() public {
        vm.prank(provider1);
        vm.expectEmit(false, true, true, false);
        emit IVAMSHardwareRegistry.NodeRegistered(
            bytes32(0), provider1, HardwareClasses.GPU_H100, "eu-west-2", 50_000e18
        );
        registry.registerNode(HardwareClasses.GPU_H100, "eu-west-2", 8, 200e18, 172800);
    }

    function test_RegisterNode_MultipleByProvider() public {
        vm.startPrank(provider1);
        registry.registerNode(HardwareClasses.GPU_A100, "us-east-1", 4, 100e18, 86400);
        registry.registerNode(HardwareClasses.CPU_EPYC, "us-east-1", 128, 20e18, 604800);
        registry.registerNode(HardwareClasses.STORAGE_NVME, "eu-west-2", 1000, 5e18, 2592000);
        vm.stopPrank();

        bytes32[] memory nodes = registry.getNodesByProvider(provider1);
        assertEq(nodes.length, 3);
        assertEq(registry.getTotalNodeCount(), 3);
    }

    // ═══════════════════ Node Deregistration ═══════════════════

    function test_DeregisterNode_Cooldown() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(HardwareClasses.CPU_EPYC, "us-east-1", 128, 20e18, 604800);

        // Request deregistration
        vm.prank(provider1);
        registry.requestDeregistration(nodeId);

        // Try immediate execute -- should revert
        vm.prank(provider1);
        vm.expectRevert();
        registry.executeDeregistration(nodeId);

        // Warp past cooldown
        vm.warp(block.timestamp + 7 days + 1);

        // Now execute should work
        uint256 balBefore = vams.balanceOf(provider1);
        vm.prank(provider1);
        registry.executeDeregistration(nodeId);
        uint256 balAfter = vams.balanceOf(provider1);

        // Collateral returned
        assertEq(balAfter - balBefore, 10_000e18);

        // Node deactivated
        IVAMSHardwareRegistry.VAMSResourceNode memory node = registry.getNode(nodeId);
        assertFalse(node.isActive);
        assertEq(node.collateralStaked, 0);
    }

    function test_DeregisterNode_NotOwner_Reverts() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(HardwareClasses.CPU_EPYC, "us-east-1", 128, 20e18, 604800);

        vm.prank(provider2);
        vm.expectRevert();
        registry.requestDeregistration(nodeId);
    }

    // ═══════════════════ Updates ═══════════════════

    function test_UpdateCapacity_OnlyProvider() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(HardwareClasses.GPU_A100, "us-east-1", 4, 100e18, 86400);

        // Owner can update
        vm.prank(provider1);
        registry.updateCapacity(nodeId, 8);

        IVAMSHardwareRegistry.VAMSResourceNode memory node = registry.getNode(nodeId);
        assertEq(node.capacityUnits, 8);

        // Non-owner reverts
        vm.prank(provider2);
        vm.expectRevert();
        registry.updateCapacity(nodeId, 16);
    }

    function test_UpdatePrice() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(HardwareClasses.GPU_A100, "us-east-1", 4, 100e18, 86400);

        vm.prank(provider1);
        registry.updatePrice(nodeId, 150e18);

        IVAMSHardwareRegistry.VAMSResourceNode memory node = registry.getNode(nodeId);
        assertEq(node.reservationPrice, 150e18);
    }

    // ═══════════════════ Sentinel Benchmarks ═══════════════════

    function test_UpdateBenchmark_OnlySentinel() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(HardwareClasses.GPU_H100, "us-east-1", 8, 200e18, 172800);

        // Sentinel can update
        vm.prank(sentinel);
        registry.updateBenchmark(nodeId, 9200, block.timestamp);

        IVAMSHardwareRegistry.VAMSResourceNode memory node = registry.getNode(nodeId);
        assertEq(node.benchmarkScore, 9200);
        assertEq(node.lastBenchmarkAt, block.timestamp);

        // Non-sentinel reverts
        vm.prank(provider1);
        vm.expectRevert();
        registry.updateBenchmark(nodeId, 5000, block.timestamp);
    }

    // ═══════════════════ Node Health ═══════════════════

    function test_IsNodeHealthy_NoBenchmark() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(HardwareClasses.GPU_A100, "us-east-1", 4, 100e18, 86400);

        // Not yet benchmarked -- assumed healthy
        assertTrue(registry.isNodeHealthy(nodeId));
    }

    function test_IsNodeHealthy_PassingBenchmark() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(HardwareClasses.GPU_A100, "us-east-1", 4, 100e18, 86400);

        vm.prank(sentinel);
        registry.updateBenchmark(nodeId, 8000, block.timestamp);

        // Score 8000 >= minBenchmark 7500 -> healthy
        assertTrue(registry.isNodeHealthy(nodeId));
    }

    function test_IsNodeHealthy_FailingBenchmark() public {
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(HardwareClasses.GPU_A100, "us-east-1", 4, 100e18, 86400);

        vm.prank(sentinel);
        registry.updateBenchmark(nodeId, 5000, block.timestamp);

        // Score 5000 < minBenchmark 7500 -> unhealthy
        assertFalse(registry.isNodeHealthy(nodeId));
    }

    // ═══════════════════ Future Class Extensibility ═══════════════════

    function test_FutureClass_CanBeAdded() public {
        bytes32 tpuClass = keccak256("TPU_V5");

        // Register new class via governance
        vm.prank(governance);
        registry.registerHardwareClass(tpuClass, "TPU_V5", "TPU", 80_000e18, 8500);

        // Fund and register a node with the new class
        vams.mint(provider1, 100_000e18);
        vm.prank(provider1);
        bytes32 nodeId = registry.registerNode(tpuClass, "us-west-2", 16, 300e18, 86400);

        IVAMSHardwareRegistry.VAMSResourceNode memory node = registry.getNode(nodeId);
        assertEq(node.hwClass, tpuClass);
        assertEq(node.collateralStaked, 80_000e18);
    }
}
