// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../src/economic/HardwareCommitment.sol";
import "../../src/economic/ProviderBondRegistry.sol";
import "../../src/registry/VAMSHardwareRegistry.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockVAMS is ERC20 {
    constructor() ERC20("VAMS", "VAMS") {}
    
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract HardwareCommitmentTest is Test {
    HardwareCommitment public hwCommitment;
    ProviderBondRegistry public bondRegistry;
    VAMSHardwareRegistry public hwRegistry;
    MockVAMS public token;

    address admin = address(1);
    address provider = address(2);
    bytes32 classId = keccak256("TEST_CLASS");
    bytes32 nodeId;

    function setUp() public {
        token = new MockVAMS();
        token.mint(provider, 100_000e18);

        // Deploy Registry
        hwRegistry = new VAMSHardwareRegistry();
        hwRegistry.initialize(admin);
        
        // Setup hardware class
        vm.prank(admin);
        hwRegistry.registerHardwareClass(classId, "TEST", "GPU", 5000e18, 5000);

        // Deploy Bond Registry
        bondRegistry = new ProviderBondRegistry();
        bondRegistry.initialize(admin, address(token), address(10)); // dummy insurance

        // Deploy Hardware Commitment
        hwCommitment = new HardwareCommitment();
        hwCommitment.initialize(admin, address(hwRegistry), address(bondRegistry));

        // Let HW Commitment manipulate Bond Registry locks
        vm.prank(admin);
        bondRegistry.grantRole(bondRegistry.HARDWARE_COMMITMENT_ROLE(), address(hwCommitment));

        vm.startPrank(provider);
        token.approve(address(bondRegistry), type(uint256).max);
        
        // 1. Bond 20k to Provider Bond
        bondRegistry.registerProvider(20_000e18, 1000e18);
        
        // 2. Register a Node to HW Registry
        token.approve(address(hwRegistry), type(uint256).max);
        nodeId = hwRegistry.registerNode(classId, "US", 1, 1e18, 90 days);
        vm.stopPrank();
    }

    function test_CreateCommitment_LocksBond() public {
        vm.startPrank(provider);
        
        bytes32[] memory nodes = new bytes32[](1);
        nodes[0] = nodeId;

        // Base collateral for this node class is 5000
        bytes32 cid = hwCommitment.createCommitment(nodes, 30 days, 9900);
        
        // Verify locked in bond
        IProviderBondRegistry.ProviderBond memory bond = bondRegistry.getBond(provider);
        assertEq(bond.hardwareCollateralLocked, 5000e18); // 30 day = 1.0x

        // Verify commitment state
        HardwareCommitment.HardwareCommitment memory c = hwCommitment.getCommitment(cid);
        assertEq(c.collateral, 5000e18);
        assertTrue(c.isActive);

        vm.stopPrank();
    }

    function test_CreateCommitment_DurationDiscount() public {
        vm.startPrank(provider);
        bytes32[] memory nodes = new bytes32[](1);
        nodes[0] = nodeId;

        bytes32 cid = hwCommitment.createCommitment(nodes, 90 days, 9900);
        
        IProviderBondRegistry.ProviderBond memory bond = bondRegistry.getBond(provider);
        assertEq(bond.hardwareCollateralLocked, 4000e18); // 90 day = 0.8x of 5000

        vm.stopPrank();
    }

    function test_Withdrawal_RevertsIfCutsIntoLock() public {
        vm.startPrank(provider);
        bytes32[] memory nodes = new bytes32[](1);
        nodes[0] = nodeId;
        hwCommitment.createCommitment(nodes, 30 days, 9900);

        // Total bond = 20k. Locked = 5k.
        // If we try to withdraw 16k, leaving 4k bond < 5k lock, it should revert.
        vm.expectRevert("Withdrawal cuts into locked hardware collateral");
        bondRegistry.requestWithdrawal(16_000e18);
        vm.stopPrank();
    }
    
    function test_EndCommitment_BeforeExpiry_Reverts() public {
        vm.startPrank(provider);
        bytes32[] memory nodes = new bytes32[](1);
        nodes[0] = nodeId;
        bytes32 cid = hwCommitment.createCommitment(nodes, 30 days, 9900);
        
        // Pass 15 days
        vm.warp(block.timestamp + 15 days);
        
        vm.expectRevert(
            abi.encodeWithSelector(
                IHardwareCommitment.CommitmentNotExpired.selector, 
                cid, 
                block.timestamp, 
                block.timestamp + 15 days
            )
        );
        hwCommitment.endCommitment(cid);
        vm.stopPrank();
    }

    function test_EndCommitment_AfterExpiry_UnlocksBond() public {
        vm.startPrank(provider);
        bytes32[] memory nodes = new bytes32[](1);
        nodes[0] = nodeId;
        bytes32 cid = hwCommitment.createCommitment(nodes, 30 days, 9900);

        // Pass 31 days
        vm.warp(block.timestamp + 31 days);
        
        hwCommitment.endCommitment(cid);
        
        // Verify unlocked
        IProviderBondRegistry.ProviderBond memory bond = bondRegistry.getBond(provider);
        assertEq(bond.hardwareCollateralLocked, 0);

        vm.stopPrank();
    }
}
