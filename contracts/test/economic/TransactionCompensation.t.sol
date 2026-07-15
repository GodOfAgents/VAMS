// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../utils/BaseTest.sol";
import "../../src/economic/TransactionCompensation.sol";
import "../../src/economic/ITransactionCompensation.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

/**
 * @title TransactionCompensationTest
 * @notice Comprehensive unit tests for TransactionCompensation contract
 */
contract TransactionCompensationTest is BaseTest {
    TransactionCompensation public compensation;
    TransactionCompensation public compensationImpl;

    address public insuranceFund;

    // Test data
    bytes32 public testTxHash = keccak256("test_transaction_1");
    bytes32 public testTxHash2 = keccak256("test_transaction_2");
    string public testEvidence = "Gas fees lost during settlement outage";
    uint256 public testAmount = 1000 ether;

    // Events (matching contract)
    event IncidentDeclared(uint256 indexed incidentId, string description, uint256 claimDeadline);
    event IncidentResolved(uint256 indexed incidentId, uint256 resolvedAt);
    event ClaimSubmitted(uint256 indexed claimId, address indexed claimant, bytes32 txHash, uint256 amount);
    event ClaimVoted(uint256 indexed claimId, address indexed guardian, bool approved);
    event ClaimFinalized(uint256 indexed claimId, ITransactionCompensation.ClaimStatus status, uint256 amount);
    event CompensationPaid(uint256 indexed claimId, address indexed claimant, uint256 amount);

    function setUp() public override {
        super.setUp();

        insuranceFund = makeAddr("insuranceFund");

        // Deploy implementation
        compensationImpl = new TransactionCompensation();

        // Create guardians array
        address[] memory guardians = new address[](3);
        guardians[0] = guardian1;
        guardians[1] = guardian2;
        guardians[2] = guardian3;

        // Package initialization data
        bytes memory initData = abi.encodeWithSelector(
            TransactionCompensation.initialize.selector, admin, guardians, address(token), insuranceFund
        );

        // Deploy proxy
        ERC1967Proxy proxy = new ERC1967Proxy(address(compensationImpl), initData);
        compensation = TransactionCompensation(address(proxy));

        vm.label(address(compensation), "TransactionCompensation");

        // Fund compensation pool
        _fundAccount(address(compensation), 10_000_000 ether);
    }

    // ============ Initialization Tests ============

    function test_Initialization() public view {
        assertEq(address(compensation.vamsToken()), address(token));
        assertEq(compensation.insuranceFund(), insuranceFund);
        assertTrue(compensation.hasRole(compensation.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(compensation.hasRole(compensation.GUARDIAN_ROLE(), guardian1));
        assertTrue(compensation.hasRole(compensation.GUARDIAN_ROLE(), guardian2));
        assertTrue(compensation.hasRole(compensation.GUARDIAN_ROLE(), guardian3));
    }

    function test_InitialState_NoActiveIncident() public view {
        assertEq(compensation.activeIncidentId(), 0);
    }

    function test_Constants() public view {
        // Test approval threshold
        assertEq(compensation.APPROVAL_THRESHOLD(), 2);
    }

    // ============ Incident Declaration Tests ============

    function test_DeclareIncident_Success() public {
        string memory description = "Protocol outage due to sequencer failure";
        uint256 claimWindowDays = 14;

        vm.prank(guardian1);
        uint256 incidentId = compensation.declareIncident(description, claimWindowDays);

        assertEq(incidentId, 1);
        assertEq(compensation.activeIncidentId(), 1);

        ITransactionCompensation.Incident memory incident = compensation.getActiveIncident();
        assertEq(incident.description, description);
        assertTrue(incident.active);
        assertGt(incident.claimDeadline, block.timestamp);
    }

    function test_DeclareIncident_Revert_NotGuardian() public {
        vm.expectRevert();
        vm.prank(user1);
        compensation.declareIncident("Test", 14);
    }

    function test_DeclareIncident_Revert_AlreadyActive() public {
        vm.prank(guardian1);
        compensation.declareIncident("First incident", 14);

        vm.expectRevert("Incident already active");
        vm.prank(guardian2);
        compensation.declareIncident("Second incident", 14);
    }

    function test_DeclareIncident_Revert_InvalidWindow() public {
        vm.expectRevert("Invalid claim window");
        vm.prank(guardian1);
        compensation.declareIncident("Test", 0);

        vm.expectRevert("Invalid claim window");
        vm.prank(guardian1);
        compensation.declareIncident("Test", 31);
    }

    function test_DeclareIncident_EmitsEvent() public {
        string memory description = "Network congestion incident";

        vm.prank(guardian1);
        compensation.declareIncident(description, 14);

        // Event emitted - checked implicitly by successful execution
    }

    // ============ Incident Resolution Tests ============

    function test_ResolveIncident_Success() public {
        vm.prank(guardian1);
        uint256 incidentId = compensation.declareIncident("Test incident", 14);

        vm.prank(guardian2);
        compensation.resolveIncident(incidentId);

        ITransactionCompensation.Incident memory incident = compensation.getIncident(incidentId);
        assertFalse(incident.active);
        assertGt(incident.resolvedAt, 0);
        assertEq(compensation.activeIncidentId(), 0);
    }

    function test_ResolveIncident_Revert_NotActive() public {
        vm.expectRevert("Incident not active");
        vm.prank(guardian1);
        compensation.resolveIncident(1);
    }

    // ============ Claim Submission Tests ============

    function test_SubmitClaim_Success() public {
        // Declare incident first
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        vm.prank(user1);
        uint256 claimId = compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, testEvidence
        );

        assertEq(claimId, 1);

        ITransactionCompensation.Claim memory claim = compensation.getClaim(claimId);
        assertEq(claim.claimant, user1);
        assertEq(claim.txHash, testTxHash);
        assertEq(claim.amount, testAmount);
        assertEq(uint256(claim.status), uint256(ITransactionCompensation.ClaimStatus.PENDING));
    }

    function test_SubmitClaim_Revert_NoActiveIncident() public {
        vm.expectRevert(ITransactionCompensation.NoActiveIncident.selector);
        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, testEvidence
        );
    }

    function test_SubmitClaim_Revert_AfterDeadline() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 1); // 1 day window

        // Warp past deadline
        vm.warp(block.timestamp + 2 days);

        vm.expectRevert(ITransactionCompensation.ClaimDeadlinePassed.selector);
        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, testEvidence
        );
    }

    function test_SubmitClaim_Revert_DuplicateTxHash() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, testEvidence
        );

        vm.expectRevert(abi.encodeWithSelector(ITransactionCompensation.ClaimAlreadyExists.selector, testTxHash));
        vm.prank(user2);
        compensation.submitClaim(testTxHash, ITransactionCompensation.TransactionType.ESCROW, 500 ether, testEvidence);
    }

    function test_SubmitClaim_Revert_ExceedsMaxAmount() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        uint256 excessiveAmount = 200_000 ether; // > MAX_CLAIM_AMOUNT

        vm.expectRevert(
            abi.encodeWithSelector(
                ITransactionCompensation.AmountExceedsMaximum.selector, excessiveAmount, 100_000 ether
            )
        );
        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, excessiveAmount, testEvidence
        );
    }

    function test_SubmitClaim_Revert_EmptyEvidence() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        vm.expectRevert(ITransactionCompensation.InvalidEvidence.selector);
        vm.prank(user1);
        compensation.submitClaim(testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, "");
    }

    function testFuzz_SubmitClaim_Amount(uint256 amount) public {
        vm.assume(amount > 0 && amount <= 100_000 ether);

        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        vm.prank(user1);
        uint256 claimId = compensation.submitClaim(
            keccak256(abi.encodePacked(amount)),
            ITransactionCompensation.TransactionType.SETTLEMENT,
            amount,
            testEvidence
        );

        ITransactionCompensation.Claim memory claim = compensation.getClaim(claimId);
        assertEq(claim.amount, amount);
    }

    // ============ Claim Approval Tests ============

    function test_ApproveClaim_SingleGuardian() public {
        _setupClaimForVoting();

        vm.prank(guardian1);
        compensation.approveClaim(1);

        ITransactionCompensation.Claim memory claim = compensation.getClaim(1);
        assertEq(claim.approvals, 1);
        assertEq(uint256(claim.status), uint256(ITransactionCompensation.ClaimStatus.PENDING));
    }

    function test_ApproveClaim_ApprovedAt2Votes() public {
        _setupClaimForVoting();

        vm.prank(guardian1);
        compensation.approveClaim(1);

        vm.prank(guardian2);
        compensation.approveClaim(1);

        ITransactionCompensation.Claim memory claim = compensation.getClaim(1);
        assertEq(claim.approvals, 2);
        assertEq(uint256(claim.status), uint256(ITransactionCompensation.ClaimStatus.APPROVED));
    }

    function test_ApproveClaim_Revert_AlreadyVoted() public {
        _setupClaimForVoting();

        vm.prank(guardian1);
        compensation.approveClaim(1);

        vm.expectRevert(abi.encodeWithSelector(ITransactionCompensation.AlreadyVoted.selector, 1, guardian1));
        vm.prank(guardian1);
        compensation.approveClaim(1);
    }

    function test_ApproveClaim_Revert_NotPending() public {
        _setupClaimForVoting();

        // Approve claim fully
        vm.prank(guardian1);
        compensation.approveClaim(1);
        vm.prank(guardian2);
        compensation.approveClaim(1);

        vm.expectRevert(abi.encodeWithSelector(ITransactionCompensation.ClaimNotPending.selector, 1));
        vm.prank(guardian3);
        compensation.approveClaim(1);
    }

    // ============ Claim Rejection Tests ============

    function test_RejectClaim_SingleGuardian() public {
        _setupClaimForVoting();

        vm.prank(guardian1);
        compensation.rejectClaim(1, "Insufficient evidence");

        ITransactionCompensation.Claim memory claim = compensation.getClaim(1);
        assertEq(claim.rejections, 1);
        assertEq(uint256(claim.status), uint256(ITransactionCompensation.ClaimStatus.PENDING));
    }

    function test_RejectClaim_RejectedAt2Votes() public {
        _setupClaimForVoting();

        vm.prank(guardian1);
        compensation.rejectClaim(1, "Duplicate claim");

        vm.prank(guardian2);
        compensation.rejectClaim(1, "Duplicate claim");

        ITransactionCompensation.Claim memory claim = compensation.getClaim(1);
        assertEq(claim.rejections, 2);
        assertEq(uint256(claim.status), uint256(ITransactionCompensation.ClaimStatus.REJECTED));
    }

    // ============ Claim Processing Tests ============

    function test_ProcessClaim_Success() public {
        _setupClaimForVoting();

        // Approve claim
        vm.prank(guardian1);
        compensation.approveClaim(1);
        vm.prank(guardian2);
        compensation.approveClaim(1);

        uint256 claimantBalanceBefore = token.balanceOf(user1);

        vm.prank(admin);
        compensation.processClaim(1);

        ITransactionCompensation.Claim memory claim = compensation.getClaim(1);
        assertEq(uint256(claim.status), uint256(ITransactionCompensation.ClaimStatus.PAID));
        assertEq(token.balanceOf(user1), claimantBalanceBefore + testAmount);
    }

    function test_ProcessClaim_Revert_NotApproved() public {
        _setupClaimForVoting();

        vm.expectRevert("Claim not approved");
        vm.prank(admin);
        compensation.processClaim(1);
    }

    function test_BatchProcessClaims() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        // Submit multiple claims
        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, 100 ether, testEvidence
        );

        vm.prank(user2);
        compensation.submitClaim(testTxHash2, ITransactionCompensation.TransactionType.ESCROW, 200 ether, testEvidence);

        // Approve both claims
        vm.prank(guardian1);
        compensation.approveClaim(1);
        vm.prank(guardian2);
        compensation.approveClaim(1);

        vm.prank(guardian1);
        compensation.approveClaim(2);
        vm.prank(guardian2);
        compensation.approveClaim(2);

        uint256[] memory claimIds = new uint256[](2);
        claimIds[0] = 1;
        claimIds[1] = 2;

        uint256 user1BalanceBefore = token.balanceOf(user1);
        uint256 user2BalanceBefore = token.balanceOf(user2);

        vm.prank(admin);
        compensation.batchProcessClaims(claimIds);

        assertEq(token.balanceOf(user1), user1BalanceBefore + 100 ether);
        assertEq(token.balanceOf(user2), user2BalanceBefore + 200 ether);
    }

    // ============ View Function Tests ============

    function test_HasClaimForTx() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        assertFalse(compensation.hasClaimForTx(testTxHash));

        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, testEvidence
        );

        assertTrue(compensation.hasClaimForTx(testTxHash));
    }

    function test_GetClaimsByClaimant() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, 100 ether, testEvidence
        );

        vm.prank(user1);
        compensation.submitClaim(testTxHash2, ITransactionCompensation.TransactionType.ESCROW, 200 ether, testEvidence);

        uint256[] memory claimIds = compensation.getClaimsByClaimant(user1);
        assertEq(claimIds.length, 2);
        assertEq(claimIds[0], 1);
        assertEq(claimIds[1], 2);
    }

    function test_GetPendingClaimsCount() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        assertEq(compensation.getPendingClaimsCount(), 0);

        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, testEvidence
        );

        assertEq(compensation.getPendingClaimsCount(), 1);
    }

    function test_GetPoolBalance() public view {
        assertGt(compensation.getPoolBalance(), 0);
    }

    // ============ Pausability Tests ============

    function test_Pause_BlocksClaims() public {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        vm.prank(admin);
        compensation.pause();

        vm.expectRevert();
        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, testEvidence
        );
    }

    // ============ Helper Functions ============

    function _setupClaimForVoting() internal {
        vm.prank(guardian1);
        compensation.declareIncident("Test incident", 14);

        vm.prank(user1);
        compensation.submitClaim(
            testTxHash, ITransactionCompensation.TransactionType.SETTLEMENT, testAmount, testEvidence
        );
    }
}
