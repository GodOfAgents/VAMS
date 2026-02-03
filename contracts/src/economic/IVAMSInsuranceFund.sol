// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSInsuranceFund
 * @author VAMS Protocol
 * @notice Interface for the VAMS Insurance Fund
 * @dev Handles claims from slashed operators/agents with hybrid governance
 */
interface IVAMSInsuranceFund {
    // ============ Enums ============
    
    enum ClaimStatus {
        PENDING,    // Awaiting guardian/DAO review
        APPROVED,   // Approved, ready for payout
        REJECTED,   // Claim rejected
        PAID        // Payout executed
    }
    
    enum CoverageTier {
        NONE,       // No coverage (stake < 10K)
        AGENT,      // 10K+ stake, 50% coverage
        OPERATOR,   // 100K+ stake, 75% coverage
        PROTOCOL    // Protocol-level coverage, 100%
    }
    
    // ============ Structs ============
    
    struct Claim {
        bytes32 agentId;           // Related agent ID
        address claimant;          // Who submitted the claim
        uint256 amount;            // Requested amount
        uint256 submittedAt;       // Submission timestamp
        uint256 resolvedAt;        // Resolution timestamp
        ClaimStatus status;        // Current status
        string reason;             // Claim reason/evidence
        uint8 approvalCount;       // Guardian approvals received
    }
    
    // ============ Events ============
    
    event Deposited(address indexed from, uint256 amount);
    event SlashingReceived(address indexed slasher, uint256 amount);
    event ClaimSubmitted(bytes32 indexed claimId, address indexed claimant, uint256 amount);
    event ClaimApproved(bytes32 indexed claimId, address indexed guardian);
    event ClaimRejected(bytes32 indexed claimId, address indexed guardian, string reason);
    event ClaimPaid(bytes32 indexed claimId, address indexed claimant, uint256 amount);
    event CoverageUpdated(address indexed account, CoverageTier tier);
    
    // ============ Errors ============
    
    error InsufficientFunds(uint256 requested, uint256 available);
    error ClaimNotFound(bytes32 claimId);
    error ClaimAlreadyResolved(bytes32 claimId);
    error ClaimWindowExpired(bytes32 claimId);
    error NotClaimant(address caller, address claimant);
    error AlreadyApproved(bytes32 claimId, address guardian);
    error NoCoverage(address account);
    error ZeroAmount();
    error ZeroAddress();
    
    // ============ External Functions ============
    
    /**
     * @notice Deposit VAMS tokens into the insurance fund
     * @param amount Amount to deposit
     */
    function deposit(uint256 amount) external;
    
    /**
     * @notice Receive slashed funds (called by VAMSSlasher)
     * @param amount Amount received from slashing
     */
    function receiveSlashedFunds(uint256 amount) external;
    
    /**
     * @notice Submit an insurance claim
     * @param agentId Related agent ID
     * @param amount Requested claim amount
     * @param reason Reason for the claim
     * @return claimId Unique claim identifier
     */
    function submitClaim(
        bytes32 agentId,
        uint256 amount,
        string calldata reason
    ) external returns (bytes32 claimId);
    
    /**
     * @notice Approve a claim (Guardian in Phase 1-2, DAO in Phase 3+)
     * @param claimId Claim to approve
     */
    function approveClaim(bytes32 claimId) external;
    
    /**
     * @notice Reject a claim with reason
     * @param claimId Claim to reject
     * @param reason Rejection reason
     */
    function rejectClaim(bytes32 claimId, string calldata reason) external;
    
    /**
     * @notice Execute payout for approved claim
     * @param claimId Approved claim ID
     */
    function executePayout(bytes32 claimId) external;
    
    // ============ View Functions ============
    
    /**
     * @notice Get claim details
     * @param claimId Claim identifier
     * @return Claim struct
     */
    function getClaim(bytes32 claimId) external view returns (Claim memory);
    
    /**
     * @notice Get coverage tier for an account
     * @param account Account to check
     * @return CoverageTier
     */
    function getCoverageTier(address account) external view returns (CoverageTier);
    
    /**
     * @notice Get total fund balance
     * @return Total VAMS balance in fund
     */
    function totalFundBalance() external view returns (uint256);
    
    /**
     * @notice Check if guardian has approved a claim
     * @param claimId Claim ID
     * @param guardian Guardian address
     * @return True if approved
     */
    function hasApproved(bytes32 claimId, address guardian) external view returns (bool);
}
