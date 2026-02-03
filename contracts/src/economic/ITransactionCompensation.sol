// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ITransactionCompensation
 * @author VAMS Protocol
 * @notice Interface for disaster recovery compensation claims
 * @dev Handles compensation for transactions that failed due to protocol outages
 */
interface ITransactionCompensation {
    // ============ Enums ============

    /// @notice Status of a compensation claim
    enum ClaimStatus {
        PENDING,    // Submitted, awaiting guardian review
        APPROVED,   // Approved by guardian quorum
        REJECTED,   // Rejected by guardians
        PAID,       // Compensation paid out
        EXPIRED     // Claim window expired
    }

    /// @notice Type of failed transaction
    enum TransactionType {
        SETTLEMENT,     // x402 settlement failure
        ESCROW,         // Escrow operation failure
        STAKE,          // Staking operation failure
        WITHDRAWAL,     // Withdrawal failure
        OTHER           // Other transaction type
    }

    // ============ Structs ============

    /// @notice Compensation claim details
    struct Claim {
        address claimant;           // Who submitted the claim
        bytes32 txHash;             // Failed transaction hash
        TransactionType txType;     // Type of failed transaction
        uint256 amount;             // Requested compensation amount
        uint256 submittedAt;        // When claim was submitted
        uint256 processedAt;        // When claim was processed
        ClaimStatus status;         // Current status
        uint256 approvals;          // Number of guardian approvals
        uint256 rejections;         // Number of guardian rejections
        string evidence;            // IPFS/Arweave URI for evidence
        string resolution;          // Resolution notes
    }

    /// @notice Incident declaration
    struct Incident {
        uint256 declaredAt;         // When incident was declared
        uint256 resolvedAt;         // When incident was resolved
        uint256 claimDeadline;      // Deadline for claims
        string description;         // Incident description
        bool active;                // Whether incident is active
    }

    // ============ Events ============

    /// @notice Emitted when an incident is declared
    event IncidentDeclared(
        uint256 indexed incidentId,
        string description,
        uint256 claimDeadline
    );

    /// @notice Emitted when an incident is resolved
    event IncidentResolved(uint256 indexed incidentId, uint256 resolvedAt);

    /// @notice Emitted when a claim is submitted
    event ClaimSubmitted(
        uint256 indexed claimId,
        address indexed claimant,
        bytes32 txHash,
        uint256 amount
    );

    /// @notice Emitted when a guardian votes on a claim
    event ClaimVoted(
        uint256 indexed claimId,
        address indexed guardian,
        bool approved
    );

    /// @notice Emitted when a claim is finalized
    event ClaimFinalized(
        uint256 indexed claimId,
        ClaimStatus status,
        uint256 paidAmount
    );

    /// @notice Emitted when compensation is paid
    event CompensationPaid(
        uint256 indexed claimId,
        address indexed recipient,
        uint256 amount
    );

    // ============ Errors ============

    /// @notice Thrown when claim already exists for tx
    error ClaimAlreadyExists(bytes32 txHash);

    /// @notice Thrown when no active incident
    error NoActiveIncident();

    /// @notice Thrown when claim deadline passed
    error ClaimDeadlinePassed();

    /// @notice Thrown when claim not found
    error ClaimNotFound(uint256 claimId);

    /// @notice Thrown when claim not pending
    error ClaimNotPending(uint256 claimId);

    /// @notice Thrown when already voted
    error AlreadyVoted(uint256 claimId, address guardian);

    /// @notice Thrown when insufficient funds
    error InsufficientFunds(uint256 required, uint256 available);

    /// @notice Thrown when amount exceeds maximum
    error AmountExceedsMaximum(uint256 amount, uint256 maximum);

    /// @notice Thrown when invalid evidence
    error InvalidEvidence();

    // ============ Incident Management ============

    /// @notice Declare a protocol incident
    /// @param description Incident description
    /// @param claimWindowDays How many days claims can be submitted
    /// @return incidentId The incident ID
    function declareIncident(
        string calldata description,
        uint256 claimWindowDays
    ) external returns (uint256 incidentId);

    /// @notice Resolve an incident
    /// @param incidentId Incident to resolve
    function resolveIncident(uint256 incidentId) external;

    // ============ Claim Management ============

    /// @notice Submit a compensation claim
    /// @param txHash Failed transaction hash
    /// @param txType Type of transaction
    /// @param amount Requested amount
    /// @param evidence Evidence URI (IPFS/Arweave)
    /// @return claimId The claim ID
    function submitClaim(
        bytes32 txHash,
        TransactionType txType,
        uint256 amount,
        string calldata evidence
    ) external returns (uint256 claimId);

    /// @notice Guardian approves a claim
    /// @param claimId Claim to approve
    function approveClaim(uint256 claimId) external;

    /// @notice Guardian rejects a claim
    /// @param claimId Claim to reject
    /// @param reason Rejection reason
    function rejectClaim(uint256 claimId, string calldata reason) external;

    /// @notice Process an approved claim (pay out)
    /// @param claimId Claim to process
    function processClaim(uint256 claimId) external;

    /// @notice Batch process multiple approved claims
    /// @param claimIds Array of claim IDs
    function batchProcessClaims(uint256[] calldata claimIds) external;

    // ============ View Functions ============

    /// @notice Get claim details
    /// @param claimId Claim ID
    /// @return claim Claim details
    function getClaim(uint256 claimId) external view returns (Claim memory claim);

    /// @notice Get active incident
    /// @return incident Active incident details
    function getActiveIncident() external view returns (Incident memory incident);

    /// @notice Get incident by ID
    /// @param incidentId Incident ID
    /// @return incident Incident details
    function getIncident(uint256 incidentId) external view returns (Incident memory incident);

    /// @notice Check if user has pending claim for tx
    /// @param txHash Transaction hash
    /// @return exists Whether claim exists
    function hasClaimForTx(bytes32 txHash) external view returns (bool exists);

    /// @notice Get claims by claimant
    /// @param claimant Claimant address
    /// @return claimIds Array of claim IDs
    function getClaimsByClaimant(address claimant) external view returns (uint256[] memory claimIds);

    /// @notice Get total pending claims
    /// @return count Number of pending claims
    function getPendingClaimsCount() external view returns (uint256 count);

    /// @notice Get total compensation paid
    /// @return total Total compensation paid
    function getTotalCompensationPaid() external view returns (uint256 total);

    /// @notice Get approval threshold
    /// @return threshold Required guardian approvals
    function getApprovalThreshold() external view returns (uint256 threshold);
}
