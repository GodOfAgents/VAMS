// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../utils/BaseTest.sol";
import "../../src/economic/OutageRecoveryManager.sol";
import "../../src/economic/IOutageRecoveryManager.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

/**
 * @title OutageRecoveryManagerTest
 * @notice Comprehensive unit tests for OutageRecoveryManager contract
 */
contract OutageRecoveryManagerTest is BaseTest {
    OutageRecoveryManager public recoveryManager;
    OutageRecoveryManager public recoveryManagerImpl;

    // Events
    event OutageDeclared(uint256 indexed outageId, address indexed guardian, string reason);
    event EmergencyModeActivated(uint256 indexed outageId, uint256 activatedAt);
    event EmergencyWithdrawalRequested(
        uint256 indexed requestId, address indexed requester, address token, uint256 amount
    );
    event EmergencyWithdrawalProcessed(uint256 indexed requestId, address indexed requester, uint256 amount);
    event RecoveryProven(uint256 indexed outageId, bytes proof);
    event EmergencyModeDeactivated(uint256 indexed outageId, uint256 deactivatedAt);

    function setUp() public override {
        super.setUp();

        // Deploy implementation
        recoveryManagerImpl = new OutageRecoveryManager();

        // Create guardians array
        address[] memory guardians = new address[](3);
        guardians[0] = guardian1;
        guardians[1] = guardian2;
        guardians[2] = guardian3;

        // Create supported tokens array
        address[] memory supportedTokens = new address[](1);
        supportedTokens[0] = address(token);

        // Package initialization data
        bytes memory initData =
            abi.encodeWithSelector(OutageRecoveryManager.initialize.selector, admin, guardians, supportedTokens);

        // Deploy proxy
        ERC1967Proxy proxy = new ERC1967Proxy(address(recoveryManagerImpl), initData);
        recoveryManager = OutageRecoveryManager(address(proxy));

        vm.label(address(recoveryManager), "OutageRecoveryManager");

        // Fund recovery pool
        _fundAccount(address(recoveryManager), 10_000_000 ether);
    }

    // ============ Initialization Tests ============

    function test_Initialization() public view {
        assertTrue(recoveryManager.hasRole(recoveryManager.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(recoveryManager.hasRole(recoveryManager.GUARDIAN_ROLE(), guardian1));
        assertTrue(recoveryManager.hasRole(recoveryManager.GUARDIAN_ROLE(), guardian2));
        assertTrue(recoveryManager.hasRole(recoveryManager.GUARDIAN_ROLE(), guardian3));
        assertEq(uint256(recoveryManager.systemState()), uint256(IOutageRecoveryManager.SystemState.NORMAL));
    }

    function test_InitialState_IsNormal() public view {
        assertEq(uint256(recoveryManager.getSystemState()), uint256(IOutageRecoveryManager.SystemState.NORMAL));
    }

    function test_SupportedToken_IsSet() public view {
        assertTrue(recoveryManager.supportedTokens(address(token)));
    }

    function test_Constants() public view {
        assertEq(recoveryManager.DECLARATION_THRESHOLD(), 2);
        assertEq(recoveryManager.OUTAGE_GRACE_PERIOD(), 24 hours);
        assertEq(recoveryManager.EMERGENCY_DURATION(), 7 days);
        assertEq(recoveryManager.MAX_WITHDRAWAL_BPS(), 1000); // 10%
    }

    // ============ Outage Declaration Tests ============

    function test_DeclareOutage_FirstGuardian() public {
        string memory reason = "Sequencer failure detected";

        vm.prank(guardian1);
        recoveryManager.declareOutage(reason);

        assertEq(uint256(recoveryManager.getSystemState()), uint256(IOutageRecoveryManager.SystemState.OUTAGE_DECLARED));
        assertEq(recoveryManager.activeOutageId(), 1);

        IOutageRecoveryManager.OutageRecord memory outage = recoveryManager.getActiveOutage();
        assertEq(outage.reason, reason);
        assertEq(outage.declaringGuardians, 1);
        assertEq(uint256(outage.state), uint256(IOutageRecoveryManager.SystemState.OUTAGE_DECLARED));
    }

    function test_DeclareOutage_SecondGuardian() public {
        vm.prank(guardian1);
        recoveryManager.declareOutage("Outage reason");

        vm.prank(guardian2);
        recoveryManager.declareOutage("Confirming outage");

        IOutageRecoveryManager.OutageRecord memory outage = recoveryManager.getActiveOutage();
        assertEq(outage.declaringGuardians, 2);
    }

    function test_DeclareOutage_Revert_NotGuardian() public {
        vm.expectRevert();
        vm.prank(user1);
        recoveryManager.declareOutage("User cannot declare");
    }

    function test_DeclareOutage_Revert_AlreadyDeclared() public {
        vm.prank(guardian1);
        recoveryManager.declareOutage("First declaration");

        vm.expectRevert(abi.encodeWithSelector(IOutageRecoveryManager.AlreadyDeclared.selector, guardian1));
        vm.prank(guardian1);
        recoveryManager.declareOutage("Second from same guardian");
    }

    function test_DeclareOutage_EmitsEvent() public {
        string memory reason = "Network congestion";

        vm.expectEmit(true, true, true, true);
        emit OutageDeclared(1, guardian1, reason);

        vm.prank(guardian1);
        recoveryManager.declareOutage(reason);
    }

    function test_HasGuardianDeclared() public {
        assertFalse(recoveryManager.hasGuardianDeclared(guardian1));

        vm.prank(guardian1);
        recoveryManager.declareOutage("Test");

        assertTrue(recoveryManager.hasGuardianDeclared(guardian1));
        assertFalse(recoveryManager.hasGuardianDeclared(guardian2));
    }

    // ============ Emergency Mode Activation Tests ============

    function test_ActivateEmergencyMode_Success() public {
        // Declare outage with 2 guardians
        vm.prank(guardian1);
        recoveryManager.declareOutage("Outage");
        vm.prank(guardian2);
        recoveryManager.declareOutage("Confirm");

        // Wait for grace period
        vm.warp(block.timestamp + 25 hours);

        recoveryManager.activateEmergencyMode();

        assertEq(uint256(recoveryManager.getSystemState()), uint256(IOutageRecoveryManager.SystemState.EMERGENCY_MODE));

        IOutageRecoveryManager.OutageRecord memory outage = recoveryManager.getActiveOutage();
        assertGt(outage.emergencyStartAt, 0);
    }

    function test_ActivateEmergencyMode_Revert_NotDeclared() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                IOutageRecoveryManager.InvalidSystemState.selector,
                IOutageRecoveryManager.SystemState.NORMAL,
                IOutageRecoveryManager.SystemState.OUTAGE_DECLARED
            )
        );
        recoveryManager.activateEmergencyMode();
    }

    function test_ActivateEmergencyMode_Revert_InsufficientDeclarations() public {
        vm.prank(guardian1);
        recoveryManager.declareOutage("Only one guardian");

        vm.warp(block.timestamp + 25 hours);

        vm.expectRevert("Insufficient declarations");
        recoveryManager.activateEmergencyMode();
    }

    function test_ActivateEmergencyMode_Revert_GracePeriodNotElapsed() public {
        vm.prank(guardian1);
        recoveryManager.declareOutage("Outage");
        vm.prank(guardian2);
        recoveryManager.declareOutage("Confirm");

        // Only 12 hours - not enough
        vm.warp(block.timestamp + 12 hours);

        vm.expectRevert();
        recoveryManager.activateEmergencyMode();
    }

    function test_GetGracePeriodRemaining() public {
        vm.prank(guardian1);
        recoveryManager.declareOutage("Outage");
        vm.prank(guardian2);
        recoveryManager.declareOutage("Confirm");

        uint256 remaining = recoveryManager.getGracePeriodRemaining();
        assertEq(remaining, 24 hours);

        vm.warp(block.timestamp + 12 hours);
        remaining = recoveryManager.getGracePeriodRemaining();
        assertEq(remaining, 12 hours);

        vm.warp(block.timestamp + 13 hours);
        remaining = recoveryManager.getGracePeriodRemaining();
        assertEq(remaining, 0);
    }

    // ============ Emergency Withdrawal Tests ============

    function test_RequestEmergencyWithdraw_Success() public {
        _activateEmergencyMode();

        uint256 poolBalance = token.balanceOf(address(recoveryManager));
        uint256 maxWithdrawal = (poolBalance * 1000) / 10_000; // 10%
        uint256 withdrawAmount = maxWithdrawal / 2;

        vm.prank(user1);
        uint256 requestId = recoveryManager.requestEmergencyWithdraw(address(token), withdrawAmount);

        assertEq(requestId, 1);

        IOutageRecoveryManager.WithdrawalRequest memory request = recoveryManager.getWithdrawalRequest(requestId);
        assertEq(request.requester, user1);
        assertEq(request.token, address(token));
        assertEq(request.amount, withdrawAmount);
        assertEq(uint256(request.status), uint256(IOutageRecoveryManager.WithdrawalStatus.APPROVED));
    }

    function test_RequestEmergencyWithdraw_Revert_NotEmergencyMode() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                IOutageRecoveryManager.InvalidSystemState.selector,
                IOutageRecoveryManager.SystemState.NORMAL,
                IOutageRecoveryManager.SystemState.EMERGENCY_MODE
            )
        );
        vm.prank(user1);
        recoveryManager.requestEmergencyWithdraw(address(token), 1000 ether);
    }

    function test_RequestEmergencyWithdraw_Revert_ExceedsLimit() public {
        _activateEmergencyMode();

        uint256 poolBalance = token.balanceOf(address(recoveryManager));
        uint256 maxWithdrawal = (poolBalance * 1000) / 10_000; // 10%
        uint256 excessiveAmount = maxWithdrawal + 1;

        vm.expectRevert(
            abi.encodeWithSelector(
                IOutageRecoveryManager.InsufficientBalance.selector, address(token), excessiveAmount, maxWithdrawal
            )
        );
        vm.prank(user1);
        recoveryManager.requestEmergencyWithdraw(address(token), excessiveAmount);
    }

    function test_RequestEmergencyWithdraw_Revert_UnsupportedToken() public {
        _activateEmergencyMode();

        address unsupportedToken = makeAddr("unsupported");

        vm.expectRevert("Token not supported");
        vm.prank(user1);
        recoveryManager.requestEmergencyWithdraw(unsupportedToken, 1000 ether);
    }

    function test_RequestEmergencyWithdraw_Revert_AfterDuration() public {
        _activateEmergencyMode();

        // Warp past emergency duration
        vm.warp(block.timestamp + 8 days);

        vm.expectRevert(IOutageRecoveryManager.EmergencyDurationExpired.selector);
        vm.prank(user1);
        recoveryManager.requestEmergencyWithdraw(address(token), 100 ether);
    }

    // ============ Withdrawal Processing Tests ============

    function test_ProcessWithdrawal_Success() public {
        _activateEmergencyMode();

        uint256 withdrawAmount = 50_000 ether;

        vm.prank(user1);
        uint256 requestId = recoveryManager.requestEmergencyWithdraw(address(token), withdrawAmount);

        uint256 balanceBefore = token.balanceOf(user1);

        vm.prank(user1);
        recoveryManager.processWithdrawal(requestId);

        assertEq(token.balanceOf(user1), balanceBefore + withdrawAmount);

        IOutageRecoveryManager.WithdrawalRequest memory request = recoveryManager.getWithdrawalRequest(requestId);
        assertEq(uint256(request.status), uint256(IOutageRecoveryManager.WithdrawalStatus.PROCESSED));
    }

    function test_ProcessWithdrawal_ByOperator() public {
        _activateEmergencyMode();

        vm.prank(user1);
        uint256 requestId = recoveryManager.requestEmergencyWithdraw(address(token), 50_000 ether);

        uint256 balanceBefore = token.balanceOf(user1);

        // Admin (has OPERATOR_ROLE) can process anyone's withdrawal
        vm.prank(admin);
        recoveryManager.processWithdrawal(requestId);

        assertGt(token.balanceOf(user1), balanceBefore);
    }

    function test_ProcessWithdrawal_Revert_NotRequester() public {
        _activateEmergencyMode();

        vm.prank(user1);
        uint256 requestId = recoveryManager.requestEmergencyWithdraw(address(token), 50_000 ether);

        // user2 can't process user1's withdrawal
        vm.expectRevert(abi.encodeWithSelector(IOutageRecoveryManager.NotRequester.selector, user2, user1));
        vm.prank(user2);
        recoveryManager.processWithdrawal(requestId);
    }

    // ============ Cancel Withdrawal Tests ============

    function test_CancelWithdrawal_Success() public {
        _activateEmergencyMode();

        vm.prank(user1);
        uint256 requestId = recoveryManager.requestEmergencyWithdraw(address(token), 50_000 ether);

        vm.prank(user1);
        recoveryManager.cancelWithdrawal(requestId);

        IOutageRecoveryManager.WithdrawalRequest memory request = recoveryManager.getWithdrawalRequest(requestId);
        assertEq(uint256(request.status), uint256(IOutageRecoveryManager.WithdrawalStatus.CANCELLED));
    }

    function test_CancelWithdrawal_Revert_NotRequester() public {
        _activateEmergencyMode();

        vm.prank(user1);
        uint256 requestId = recoveryManager.requestEmergencyWithdraw(address(token), 50_000 ether);

        vm.expectRevert(abi.encodeWithSelector(IOutageRecoveryManager.NotRequester.selector, user2, user1));
        vm.prank(user2);
        recoveryManager.cancelWithdrawal(requestId);
    }

    // ============ Recovery Tests ============

    function test_ProveRecovery() public {
        _activateEmergencyMode();

        bytes memory proof = abi.encodePacked(keccak256("block_hash_proof"));

        vm.expectEmit(true, true, true, true);
        emit RecoveryProven(1, proof);

        vm.prank(guardian1);
        recoveryManager.proveRecovery(proof);
    }

    function test_DeactivateEmergencyMode() public {
        _activateEmergencyMode();

        vm.prank(guardian1);
        recoveryManager.deactivateEmergencyMode();

        assertEq(uint256(recoveryManager.getSystemState()), uint256(IOutageRecoveryManager.SystemState.NORMAL));
        assertEq(recoveryManager.activeOutageId(), 0);
    }

    function test_DeactivateEmergencyMode_Revert_NotEmergencyMode() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                IOutageRecoveryManager.InvalidSystemState.selector,
                IOutageRecoveryManager.SystemState.NORMAL,
                IOutageRecoveryManager.SystemState.EMERGENCY_MODE
            )
        );
        vm.prank(guardian1);
        recoveryManager.deactivateEmergencyMode();
    }

    // ============ Admin Function Tests ============

    function test_AddSupportedToken() public {
        address newToken = makeAddr("newToken");

        assertFalse(recoveryManager.supportedTokens(newToken));

        vm.prank(admin);
        recoveryManager.addSupportedToken(newToken);

        assertTrue(recoveryManager.supportedTokens(newToken));
    }

    function test_RemoveSupportedToken() public {
        vm.prank(admin);
        recoveryManager.removeSupportedToken(address(token));

        assertFalse(recoveryManager.supportedTokens(address(token)));
    }

    function test_DepositToPool() public {
        uint256 depositAmount = 1000 ether;
        uint256 balanceBefore = token.balanceOf(address(recoveryManager));

        vm.prank(user1);
        token.approve(address(recoveryManager), depositAmount);

        vm.prank(user1);
        recoveryManager.depositToPool(address(token), depositAmount);

        assertEq(token.balanceOf(address(recoveryManager)), balanceBefore + depositAmount);
    }

    function test_WithdrawFromPool_NormalState() public {
        uint256 withdrawAmount = 1000 ether;
        uint256 treasuryBalanceBefore = token.balanceOf(treasury);

        vm.prank(admin);
        recoveryManager.withdrawFromPool(address(token), treasury, withdrawAmount);

        assertEq(token.balanceOf(treasury), treasuryBalanceBefore + withdrawAmount);
    }

    function test_WithdrawFromPool_Revert_NotNormalState() public {
        _activateEmergencyMode();

        vm.expectRevert("Not in normal state");
        vm.prank(admin);
        recoveryManager.withdrawFromPool(address(token), treasury, 1000 ether);
    }

    // ============ View Function Tests ============

    function test_GetPoolBalance() public view {
        assertGt(recoveryManager.getPoolBalance(address(token)), 0);
    }

    function test_GetEmergencyTimeRemaining() public {
        assertEq(recoveryManager.getEmergencyTimeRemaining(), 0); // Not in emergency

        _activateEmergencyMode();

        uint256 remaining = recoveryManager.getEmergencyTimeRemaining();
        assertEq(remaining, 7 days);

        vm.warp(block.timestamp + 3 days);
        remaining = recoveryManager.getEmergencyTimeRemaining();
        assertEq(remaining, 4 days);
    }

    function test_GetPendingWithdrawals() public {
        _activateEmergencyMode();

        vm.prank(user1);
        recoveryManager.requestEmergencyWithdraw(address(token), 50_000 ether);

        vm.prank(user1);
        recoveryManager.requestEmergencyWithdraw(address(token), 25_000 ether);

        uint256[] memory pending = recoveryManager.getPendingWithdrawals(user1);
        assertEq(pending.length, 2);
    }

    // ============ Helper Functions ============

    function _activateEmergencyMode() internal {
        // Declare with 2 guardians
        vm.prank(guardian1);
        recoveryManager.declareOutage("Outage");
        vm.prank(guardian2);
        recoveryManager.declareOutage("Confirm");

        // Wait for grace period
        vm.warp(block.timestamp + 25 hours);

        // Activate
        recoveryManager.activateEmergencyMode();
    }
}
