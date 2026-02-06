// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/routing/VAMSRouter.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

/**
 * @title GovernancePhaseTransitionTest
 * @notice Tests for VAMS governance phase transitions (1→4)
 * @dev Tests the progressive decentralization mechanism in VAMSUpgradeableBase
 * 
 * Phases:
 * - Phase 1: Deployer EOA (testnet)
 * - Phase 2: Team Multisig (guarded mainnet)
 * - Phase 3: DAO Timelock (decentralized)
 * - Phase 4: Immutable (optional, permanent)
 */
contract GovernancePhaseTransitionTest is BaseTest {
    VAMSRouter public router;
    VAMSRouter public implementation;
    
    // Addresses for governance
    address public multisig;
    address public daoTimelock;
    
    // Events
    event GovernancePhaseAdvanced(uint8 indexed oldPhase, uint8 indexed newPhase);
    event OwnershipTransferredToMultisig(address indexed multisig);
    event OwnershipTransferredToDAO(address indexed daoTimelock);
    event UpgradeabilityRenounced(uint256 indexed timestamp);
    event ManualRoutingDisabled(string reason);
    
    function setUp() public override {
        super.setUp();
        
        // Create governance addresses
        multisig = makeAddr("teamMultisig");
        daoTimelock = makeAddr("daoTimelock");
        
        // Deploy implementation
        implementation = new VAMSRouter();
        
        // Deploy proxy and initialize
        address[] memory guardians = new address[](3);
        guardians[0] = guardian1;
        guardians[1] = guardian2;
        guardians[2] = guardian3;
        
        bytes memory initData = abi.encodeWithSelector(
            VAMSRouter.initialize.selector,
            admin,
            guardians
        );
        
        ERC1967Proxy proxy = new ERC1967Proxy(
            address(implementation),
            initData
        );
        
        router = VAMSRouter(address(proxy));
        vm.label(address(router), "VAMSRouter");
    }
    
    // ============ Initial State Tests ============
    
    function test_Initialize_StartsAtPhase1() public view {
        assertEq(router.governancePhase(), 1, "Should start at Phase 1");
    }
    
    function test_Initialize_AdminHasRoles() public view {
        assertTrue(router.hasRole(router.DEFAULT_ADMIN_ROLE(), admin), "Admin should have DEFAULT_ADMIN_ROLE");
        assertTrue(router.hasRole(router.UPGRADER_ROLE(), admin), "Admin should have UPGRADER_ROLE");
    }
    
    function test_Initialize_IsUpgradeable() public view {
        assertTrue(router.isUpgradeable(), "Should be upgradeable in Phase 1");
    }
    
    function test_Initialize_PhaseDescription() public view {
        assertEq(router.getGovernancePhaseDescription(), "Phase 1: Deployer EOA");
    }
    
    function test_Initialize_TimelockIsZero() public view {
        assertEq(router.timelockController(), address(0), "Timelock should be zero in Phase 1");
    }
    
    // ============ Phase 1 → 2 (EOA → Multisig) ============
    
    function test_Phase1ToPhase2_Success() public {
        vm.prank(admin);
        
        vm.expectEmit(true, true, false, false);
        emit GovernancePhaseAdvanced(1, 2);
        
        vm.expectEmit(true, false, false, false);
        emit OwnershipTransferredToMultisig(multisig);
        
        router.transferToMultisig(multisig);
        
        assertEq(router.governancePhase(), 2, "Should be Phase 2");
        assertEq(router.getGovernancePhaseDescription(), "Phase 2: Team Multisig");
    }
    
    function test_Phase1ToPhase2_RevokesPreviousAdmin() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        assertFalse(router.hasRole(router.DEFAULT_ADMIN_ROLE(), admin), "Admin role should be revoked from EOA");
        assertFalse(router.hasRole(router.UPGRADER_ROLE(), admin), "Upgrader role should be revoked from EOA");
    }
    
    function test_Phase1ToPhase2_GrantsMultisigRoles() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        assertTrue(router.hasRole(router.DEFAULT_ADMIN_ROLE(), multisig), "Multisig should have DEFAULT_ADMIN_ROLE");
        assertTrue(router.hasRole(router.UPGRADER_ROLE(), multisig), "Multisig should have UPGRADER_ROLE");
    }
    
    function test_Phase1ToPhase2_RevertsOnZeroAddress() public {
        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSignature("InvalidAddress()"));
        router.transferToMultisig(address(0));
    }
    
    function test_Phase1ToPhase2_RevertsIfNotAdmin() public {
        vm.prank(user1);
        vm.expectRevert();
        router.transferToMultisig(multisig);
    }
    
    // ============ Phase 2 → 3 (Multisig → DAO) ============
    
    function test_Phase2ToPhase3_Success() public {
        // First transition to Phase 2
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        // Then transition to Phase 3
        vm.prank(multisig);
        
        vm.expectEmit(true, true, false, false);
        emit GovernancePhaseAdvanced(2, 3);
        
        vm.expectEmit(true, false, false, false);
        emit OwnershipTransferredToDAO(daoTimelock);
        
        router.transferToDAO(daoTimelock);
        
        assertEq(router.governancePhase(), 3, "Should be Phase 3");
        assertEq(router.getGovernancePhaseDescription(), "Phase 3: DAO Governance");
    }
    
    function test_Phase2ToPhase3_SetsTimelockController() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        assertEq(router.timelockController(), daoTimelock, "Timelock should be set");
    }
    
    function test_Phase2ToPhase3_GrantsDAORoles() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        assertTrue(router.hasRole(router.DEFAULT_ADMIN_ROLE(), daoTimelock), "DAO should have DEFAULT_ADMIN_ROLE");
        assertTrue(router.hasRole(router.UPGRADER_ROLE(), daoTimelock), "DAO should have UPGRADER_ROLE");
    }
    
    function test_Phase2ToPhase3_RevokesMultisigRoles() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        assertFalse(router.hasRole(router.DEFAULT_ADMIN_ROLE(), multisig), "Multisig admin role should be revoked");
        assertFalse(router.hasRole(router.UPGRADER_ROLE(), multisig), "Multisig upgrader role should be revoked");
    }
    
    function test_Phase2ToPhase3_RevertsOnZeroAddress() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        vm.expectRevert(abi.encodeWithSignature("InvalidAddress()"));
        router.transferToDAO(address(0));
    }
    
    function test_Phase2ToPhase3_RevertsIfNotAdmin() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(user1);
        vm.expectRevert();
        router.transferToDAO(daoTimelock);
    }
    
    // ============ Phase 3 → 4 (DAO → Immutable) ============
    
    function test_Phase3ToPhase4_Success() public {
        // Transition through phases
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        // Renounce upgradeability
        vm.prank(daoTimelock);
        
        vm.expectEmit(true, true, false, false);
        emit GovernancePhaseAdvanced(3, 4);
        
        vm.expectEmit(true, false, false, false);
        emit UpgradeabilityRenounced(block.timestamp);
        
        router.renounceUpgradeability();
        
        assertEq(router.governancePhase(), 4, "Should be Phase 4");
        assertEq(router.getGovernancePhaseDescription(), "Phase 4: Immutable");
    }
    
    function test_Phase3ToPhase4_RevokesUpgraderRole() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        vm.prank(daoTimelock);
        router.renounceUpgradeability();
        
        assertFalse(router.hasRole(router.UPGRADER_ROLE(), daoTimelock), "DAO upgrader role should be revoked");
    }
    
    function test_Phase3ToPhase4_NotUpgradeable() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        vm.prank(daoTimelock);
        router.renounceUpgradeability();
        
        assertFalse(router.isUpgradeable(), "Should not be upgradeable in Phase 4");
    }
    
    function test_Phase3ToPhase4_RevertsIfNotAdmin() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        vm.prank(user1);
        vm.expectRevert();
        router.renounceUpgradeability();
    }
    
    // ============ Skip Phase Tests ============
    
    function test_SkipPhase_1To3_Reverts() public {
        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSignature("InvalidPhaseTransition(uint8,uint8)", 1, 3));
        router.transferToDAO(daoTimelock);
    }
    
    function test_SkipPhase_1To4_Reverts() public {
        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSignature("InvalidPhaseTransition(uint8,uint8)", 1, 4));
        router.renounceUpgradeability();
    }
    
    function test_SkipPhase_2To4_Reverts() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        vm.expectRevert(abi.encodeWithSignature("InvalidPhaseTransition(uint8,uint8)", 2, 4));
        router.renounceUpgradeability();
    }
    
    // ============ Backward Transition Tests ============
    
    function test_BackwardTransition_2To1_Reverts() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        // Phase 2 admin cannot go back to Phase 1
        vm.prank(multisig);
        vm.expectRevert(abi.encodeWithSignature("InvalidPhaseTransition(uint8,uint8)", 2, 2));
        router.transferToMultisig(admin);
    }
    
    function test_BackwardTransition_3To2_Reverts() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        // Phase 3 admin cannot go back to Phase 2
        vm.prank(daoTimelock);
        vm.expectRevert(abi.encodeWithSignature("InvalidPhaseTransition(uint8,uint8)", 3, 2));
        router.transferToMultisig(multisig);
    }
    
    // ============ Phase 4 Upgrade Blocking Tests ============
    
    function test_Phase4_CannotUpgrade() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        vm.prank(daoTimelock);
        router.renounceUpgradeability();
        
        // Deploy a new implementation
        VAMSRouter newImpl = new VAMSRouter();
        
        // DAO no longer has UPGRADER_ROLE, so upgrade should fail
        vm.prank(daoTimelock);
        vm.expectRevert();
        router.upgradeToAndCall(address(newImpl), "");
    }
    
    function test_Phase4_CannotRenounceAgain() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        vm.prank(daoTimelock);
        router.renounceUpgradeability();
        
        // Try to renounce again
        vm.prank(daoTimelock);
        vm.expectRevert(abi.encodeWithSignature("UpgradeabilityAlreadyRenounced()"));
        router.renounceUpgradeability();
    }
    
    // ============ Manual Routing Disabled in Phase 3+ ============
    
    function test_ManualRouting_AllowedInPhase1() public {
        assertTrue(router.isManualRoutingAllowed(), "Manual routing should be allowed in Phase 1");
    }
    
    function test_ManualRouting_AllowedInPhase2() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        assertTrue(router.isManualRoutingAllowed(), "Manual routing should be allowed in Phase 2");
    }
    
    function test_ManualRouting_DisabledInPhase3() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        assertFalse(router.isManualRoutingAllowed(), "Manual routing should be disabled in Phase 3");
    }
    
    function test_ManualRouting_DisabledInPhase4() public {
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        vm.prank(daoTimelock);
        router.renounceUpgradeability();
        
        assertFalse(router.isManualRoutingAllowed(), "Manual routing should be disabled in Phase 4");
    }
    
    // ============ Full Governance Flow Test ============
    
    function test_FullGovernanceFlow() public {
        // Phase 1: EOA admin
        assertEq(router.governancePhase(), 1);
        assertTrue(router.hasRole(router.UPGRADER_ROLE(), admin));
        assertTrue(router.isManualRoutingAllowed());
        
        // Phase 1 → 2: Transfer to Multisig
        vm.prank(admin);
        router.transferToMultisig(multisig);
        
        assertEq(router.governancePhase(), 2);
        assertTrue(router.hasRole(router.UPGRADER_ROLE(), multisig));
        assertFalse(router.hasRole(router.UPGRADER_ROLE(), admin));
        assertTrue(router.isManualRoutingAllowed());
        
        // Phase 2 → 3: Transfer to DAO
        vm.prank(multisig);
        router.transferToDAO(daoTimelock);
        
        assertEq(router.governancePhase(), 3);
        assertTrue(router.hasRole(router.UPGRADER_ROLE(), daoTimelock));
        assertFalse(router.hasRole(router.UPGRADER_ROLE(), multisig));
        assertFalse(router.isManualRoutingAllowed()); // Manual routing disabled
        assertEq(router.timelockController(), daoTimelock);
        
        // Phase 3 → 4: Renounce upgradeability
        vm.prank(daoTimelock);
        router.renounceUpgradeability();
        
        assertEq(router.governancePhase(), 4);
        assertFalse(router.hasRole(router.UPGRADER_ROLE(), daoTimelock));
        assertFalse(router.isUpgradeable());
        assertFalse(router.isManualRoutingAllowed());
    }
}
