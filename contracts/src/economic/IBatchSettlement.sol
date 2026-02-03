// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IBatchSettlement
 * @author VAMS Protocol
 * @notice Interface for gas-efficient batch settlement using Merkle proofs
 * @dev Aggregates multiple payments into a single batch for ~90% gas savings
 * 
 * Architecture Reference: ARCHITECTURE_v0-3-0.md §20.2.4
 * 
 * Batch Lifecycle:
 * 1. Gateway collects payments off-chain
 * 2. Provider(s) sign batch commitment
 * 3. Merkle root submitted on-chain
 * 4. Individual payments verified via Merkle proofs
 * 5. Dispute window for fraud proofs
 * 
 * Security Model:
 * - Requires provider quorum signatures
 * - Merkle tree enables efficient fraud proofs
 * - Disputed payments settled individually
 */
interface IBatchSettlement {
    // ============ Enums ============
    
    /**
     * @notice Batch status
     */
    enum BatchStatus {
        SUBMITTED,      // Waiting for finalization
        FINALIZED,      // Past dispute window, can claim
        DISPUTED,       // Under dispute
        CANCELLED       // Batch cancelled due to fraud
    }
    
    /**
     * @notice Payment status within a batch
     */
    enum PaymentStatus {
        PENDING,        // Not yet claimed
        CLAIMED,        // Successfully claimed
        DISPUTED,       // Under dispute
        REFUNDED        // Refunded due to dispute
    }
    
    // ============ Structs ============
    
    /**
     * @notice Batch information
     * @param merkleRoot Root of payment Merkle tree
     * @param totalPayments Number of payments in batch
     * @param totalValue Sum of all payment values
     * @param submittedAt Submission timestamp
     * @param finalizedAt Finalization timestamp (0 if not finalized)
     * @param status Current batch status
     * @param submitter Gateway that submitted
     */
    struct Batch {
        bytes32 merkleRoot;
        uint256 totalPayments;
        uint256 totalValue;
        uint256 submittedAt;
        uint256 finalizedAt;
        BatchStatus status;
        address submitter;
    }
    
    /**
     * @notice Individual payment in a batch
     * @param agent Paying agent
     * @param provider Service provider
     * @param amount Payment amount
     * @param nonce Unique nonce
     * @param serviceType Service identifier
     */
    struct Payment {
        address agent;
        address provider;
        uint256 amount;
        uint256 nonce;
        bytes32 serviceType;
    }
    
    /**
     * @notice Claim record for a payment
     * @param batchId Batch containing this payment
     * @param paymentHash Hash of the payment
     * @param claimedAt Claim timestamp
     * @param status Payment status
     */
    struct PaymentClaim {
        uint256 batchId;
        bytes32 paymentHash;
        uint256 claimedAt;
        PaymentStatus status;
    }
    
    // ============ Events ============
    
    event BatchSubmitted(
        uint256 indexed batchId,
        bytes32 merkleRoot,
        uint256 totalPayments,
        uint256 totalValue,
        address indexed submitter
    );
    
    event BatchFinalized(uint256 indexed batchId);
    
    event BatchDisputed(uint256 indexed batchId, address indexed disputer);
    
    event BatchCancelled(uint256 indexed batchId, string reason);
    
    event PaymentClaimed(
        uint256 indexed batchId,
        bytes32 indexed paymentHash,
        address indexed provider,
        uint256 amount
    );
    
    event PaymentDisputed(
        uint256 indexed batchId,
        bytes32 indexed paymentHash,
        address indexed disputer
    );
    
    event PaymentRefunded(
        uint256 indexed batchId,
        bytes32 indexed paymentHash,
        address indexed agent,
        uint256 amount
    );
    
    // ============ Errors ============
    
    /// @notice Batch not found
    error BatchNotFound(uint256 batchId);
    
    /// @notice Batch not in correct status
    error InvalidBatchStatus(uint256 batchId, BatchStatus current, BatchStatus required);
    
    /// @notice Payment already claimed
    error PaymentAlreadyClaimed(bytes32 paymentHash);
    
    /// @notice Invalid Merkle proof
    error InvalidMerkleProof();
    
    /// @notice Insufficient provider signatures
    error InsufficientSignatures(uint256 provided, uint256 required);
    
    /// @notice Dispute window not expired
    error DisputeWindowActive(uint256 expiresAt);
    
    /// @notice Dispute window expired
    error DisputeWindowExpired(uint256 expiredAt);
    
    /// @notice Caller not authorized
    error UnauthorizedCaller();
    
    /// @notice Zero value provided
    error ZeroValue();
    
    // ============ Constants View ============
    
    /// @notice Dispute window duration (24 hours)
    function DISPUTE_WINDOW() external view returns (uint256);
    
    /// @notice Minimum provider signatures required
    function MIN_SIGNATURES() external view returns (uint256);
    
    /// @notice Settlement fee in basis points
    function SETTLEMENT_FEE_BPS() external view returns (uint256);
    
    // ============ View Functions ============
    
    /**
     * @notice Get batch details
     * @param batchId Batch ID
     * @return Batch struct
     */
    function getBatch(uint256 batchId) external view returns (Batch memory);
    
    /**
     * @notice Get payment claim status
     * @param paymentHash Hash of the payment
     * @return PaymentClaim struct
     */
    function getPaymentClaim(bytes32 paymentHash) external view returns (PaymentClaim memory);
    
    /**
     * @notice Compute payment hash
     * @param payment Payment struct
     * @return Hash of the payment
     */
    function computePaymentHash(Payment calldata payment) external pure returns (bytes32);
    
    /**
     * @notice Verify payment is in batch
     * @param batchId Batch ID
     * @param payment Payment to verify
     * @param merkleProof Merkle proof
     * @return True if payment is valid member of batch
     */
    function verifyPayment(
        uint256 batchId,
        Payment calldata payment,
        bytes32[] calldata merkleProof
    ) external view returns (bool);
    
    /**
     * @notice Check if batch is finalized
     * @param batchId Batch ID
     * @return True if finalized
     */
    function isFinalized(uint256 batchId) external view returns (bool);
    
    /**
     * @notice Get total batches submitted
     * @return Batch count
     */
    function totalBatches() external view returns (uint256);
    
    // ============ Gateway Functions ============
    
    /**
     * @notice Submit a new batch
     * @param merkleRoot Root of payment Merkle tree
     * @param totalPayments Number of payments
     * @param totalValue Sum of payment values
     * @param providerSignatures Signatures from providers attesting to batch
     * @return batchId New batch ID
     */
    function submitBatch(
        bytes32 merkleRoot,
        uint256 totalPayments,
        uint256 totalValue,
        bytes[] calldata providerSignatures
    ) external returns (uint256 batchId);
    
    /**
     * @notice Finalize batch after dispute window
     * @param batchId Batch to finalize
     */
    function finalizeBatch(uint256 batchId) external;
    
    // ============ Provider Functions ============
    
    /**
     * @notice Claim payment from finalized batch
     * @param batchId Batch ID
     * @param payment Payment to claim
     * @param merkleProof Merkle proof of inclusion
     */
    function claimPayment(
        uint256 batchId,
        Payment calldata payment,
        bytes32[] calldata merkleProof
    ) external;
    
    /**
     * @notice Batch claim multiple payments
     * @param batchId Batch ID
     * @param payments Array of payments
     * @param merkleProofs Array of Merkle proofs
     */
    function batchClaimPayments(
        uint256 batchId,
        Payment[] calldata payments,
        bytes32[][] calldata merkleProofs
    ) external;
    
    // ============ Dispute Functions ============
    
    /**
     * @notice Dispute a payment in a batch
     * @param batchId Batch ID
     * @param payment Disputed payment
     * @param merkleProof Merkle proof
     * @param evidence Dispute evidence
     */
    function disputePayment(
        uint256 batchId,
        Payment calldata payment,
        bytes32[] calldata merkleProof,
        bytes calldata evidence
    ) external;
    
    /**
     * @notice Dispute entire batch (fraud proof)
     * @param batchId Batch ID
     * @param evidence Fraud evidence
     */
    function disputeBatch(uint256 batchId, bytes calldata evidence) external;
    
    /**
     * @notice Resolve payment dispute
     * @param paymentHash Payment being resolved
     * @param refundAgent True to refund agent, false to pay provider
     */
    function resolvePaymentDispute(
        bytes32 paymentHash,
        bool refundAgent
    ) external;
}
