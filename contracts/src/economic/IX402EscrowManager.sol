// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IX402EscrowManager
 * @author VAMS Protocol
 * @notice Interface for HTLC-based atomic escrow in x402 settlements
 * @dev Agents lock funds before service, providers claim after delivery
 * 
 * Architecture Reference: ARCHITECTURE_v0-3-0.md §20.2.2
 * 
 * Escrow Lifecycle:
 * 1. Agent locks escrow with provider address and optional HTLC hashlock
 * 2. Provider delivers service
 * 3a. Provider claims with service proof (and preimage if HTLC)
 * 3b. OR Agent refunds after expiry
 * 3c. OR Either party disputes
 * 
 * Security Model:
 * - Escrow locked BEFORE service delivery (prevents non-payment)
 * - HTLC ensures atomicity in multi-hop scenarios
 * - Service proofs required for claims (TEE attestation or ZKML)
 * - 72-hour dispute window for quality issues
 */
interface IX402EscrowManager {
    // ============ Enums ============
    
    /**
     * @notice Escrow status
     */
    enum EscrowStatus {
        LOCKED,     // Funds locked, awaiting service
        CLAIMED,    // Provider claimed after delivery
        REFUNDED,   // Agent refunded after expiry
        DISPUTED,   // Under dispute resolution
        RESOLVED    // Dispute resolved
    }
    
    /**
     * @notice Service proof type
     */
    enum ProofType {
        TEE,            // TEE attestation (hardware trust)
        DETERMINISTIC,  // Hash of deterministic output
        ZKML            // ZK proof of correct inference
    }
    
    // ============ Structs ============
    
    /**
     * @notice Escrow details
     * @param agent Agent who locked funds
     * @param provider Service provider
     * @param amount Escrowed amount
     * @param nonce Unique nonce for this escrow
     * @param createdAt Lock timestamp
     * @param expiresAt Expiry timestamp
     * @param hashlock HTLC hashlock (bytes32(0) for basic escrow)
     * @param status Current status
     * @param serviceType Type of service requested
     */
    struct Escrow {
        address agent;
        address provider;
        uint256 amount;
        uint256 nonce;
        uint256 createdAt;
        uint256 expiresAt;
        bytes32 hashlock;
        EscrowStatus status;
        bytes32 serviceType;
    }
    
    /**
     * @notice Service delivery proof
     * @param requestHash Hash of the service request
     * @param responseHash Hash of the service response
     * @param attestation TEE attestation or ZKML proof bytes
     * @param proofType Type of proof (TEE, deterministic, ZKML)
     */
    struct ServiceProof {
        bytes32 requestHash;
        bytes32 responseHash;
        bytes attestation;
        ProofType proofType;
    }
    
    /**
     * @notice Dispute details
     * @param escrowId Disputed escrow
     * @param disputer Who initiated dispute
     * @param evidence Dispute evidence
     * @param filedAt When dispute was filed
     * @param resolved Whether dispute is resolved
     */
    struct Dispute {
        bytes32 escrowId;
        address disputer;
        bytes evidence;
        uint256 filedAt;
        bool resolved;
    }
    
    // ============ Events ============
    
    event EscrowLocked(
        bytes32 indexed escrowId,
        address indexed agent,
        address indexed provider,
        uint256 amount,
        uint256 expiresAt,
        bytes32 serviceType
    );
    
    event EscrowClaimed(
        bytes32 indexed escrowId, 
        address indexed provider, 
        uint256 amount,
        ProofType proofType
    );
    
    event EscrowRefunded(
        bytes32 indexed escrowId, 
        address indexed agent, 
        uint256 amount
    );
    
    event EscrowDisputed(
        bytes32 indexed escrowId, 
        address indexed disputer,
        bytes evidence
    );
    
    event DisputeResolved(
        bytes32 indexed escrowId, 
        address indexed winner, 
        uint256 agentRefund,
        uint256 providerPayout
    );
    
    event EscrowExtended(
        bytes32 indexed escrowId,
        uint256 oldExpiry,
        uint256 newExpiry
    );
    
    event ServiceProofApproved(
        bytes32 indexed escrowId,
        address indexed verifier
    );
    
    // ============ Errors ============
    
    /// @notice Escrow not found
    error EscrowNotFound(bytes32 escrowId);
    
    /// @notice Escrow not in claimable state
    error EscrowNotClaimable(bytes32 escrowId, EscrowStatus status);
    
    /// @notice Escrow not refundable (not expired or wrong status)
    error EscrowNotRefundable(bytes32 escrowId);
    
    /// @notice Escrow cannot be disputed
    error EscrowNotDisputable(bytes32 escrowId);
    
    /// @notice Escrow has expired
    error EscrowExpired(bytes32 escrowId);
    
    /// @notice Escrow has not yet expired
    error EscrowNotExpired(bytes32 escrowId, uint256 expiresAt);
    
    /// @notice Service proof is invalid
    error InvalidServiceProof();
    
    /// @notice HTLC hashlock mismatch
    error InvalidHashlock(bytes32 provided, bytes32 expected);
    
    /// @notice Caller is not escrow party
    error NotEscrowParty(address caller);
    
    /// @notice Provider not registered in bond registry
    error ProviderNotRegistered(address provider);
    
    /// @notice Insufficient token balance
    error InsufficientBalance(uint256 required, uint256 available);
    
    /// @notice Zero address
    error ZeroAddress();
    
    /// @notice Zero amount
    error ZeroAmount();
    
    /// @notice Invalid validity period
    error InvalidValidityPeriod(uint256 provided, uint256 min, uint256 max);
    
    /// @notice Dispute already exists
    error DisputeAlreadyExists(bytes32 escrowId);
    
    /// @notice Dispute window expired
    error DisputeWindowExpired(bytes32 escrowId);
    
    /// @notice Only resolver can resolve disputes
    error UnauthorizedResolver();
    
    // ============ Constants View ============
    
    /// @notice Minimum escrow validity (5 minutes)
    function MIN_VALIDITY() external view returns (uint256);
    
    /// @notice Maximum escrow validity (24 hours)
    function MAX_VALIDITY() external view returns (uint256);
    
    /// @notice Dispute window after claim (72 hours)
    function DISPUTE_WINDOW() external view returns (uint256);
    
    /// @notice Settlement fee in basis points (0.05% = 5 bps)
    function SETTLEMENT_FEE_BPS() external view returns (uint256);
    
    // ============ View Functions ============
    
    /**
     * @notice Get escrow details
     * @param escrowId Escrow identifier
     * @return Escrow struct
     */
    function getEscrow(bytes32 escrowId) external view returns (Escrow memory);
    
    /**
     * @notice Get dispute details
     * @param escrowId Escrow identifier
     * @return Dispute struct
     */
    function getDispute(bytes32 escrowId) external view returns (Dispute memory);
    
    /**
     * @notice Get all escrow IDs for an agent
     * @param agent Agent address
     * @return Array of escrow IDs
     */
    function getAgentEscrows(address agent) external view returns (bytes32[] memory);
    
    /**
     * @notice Get all escrow IDs for a provider
     * @param provider Provider address
     * @return Array of escrow IDs
     */
    function getProviderEscrows(address provider) external view returns (bytes32[] memory);
    
    /**
     * @notice Check if escrow is claimable
     * @param escrowId Escrow identifier
     * @return True if claimable
     */
    function isClaimable(bytes32 escrowId) external view returns (bool);
    
    /**
     * @notice Check if escrow is refundable
     * @param escrowId Escrow identifier
     * @return True if refundable
     */
    function isRefundable(bytes32 escrowId) external view returns (bool);
    
    /**
     * @notice Calculate escrow ID from parameters
     * @param agent Agent address
     * @param provider Provider address
     * @param nonce Escrow nonce
     * @param timestamp Creation timestamp
     * @return Escrow ID
     */
    function computeEscrowId(
        address agent,
        address provider,
        uint256 nonce,
        uint256 timestamp
    ) external pure returns (bytes32);
    
    // ============ Agent Functions ============
    
    /**
     * @notice Lock funds in escrow before requesting service
     * @param provider Provider address
     * @param amount Amount to lock
     * @param nonce Unique nonce for this escrow
     * @param validForSeconds Escrow validity period
     * @param hashlock HTLC hashlock (bytes32(0) for basic escrow)
     * @param serviceType Type of service requested
     * @return escrowId Unique escrow identifier
     */
    function lockEscrow(
        address provider,
        uint256 amount,
        uint256 nonce,
        uint256 validForSeconds,
        bytes32 hashlock,
        bytes32 serviceType
    ) external returns (bytes32 escrowId);
    
    /**
     * @notice Refund expired escrow to agent
     * @param escrowId Escrow to refund
     */
    function refundExpiredEscrow(bytes32 escrowId) external;
    
    /**
     * @notice Extend escrow expiry (by agent only, before expiry)
     * @param escrowId Escrow to extend
     * @param additionalSeconds Additional time
     */
    function extendEscrow(bytes32 escrowId, uint256 additionalSeconds) external;
    
    // ============ Provider Functions ============
    
    /**
     * @notice Claim escrow after service delivery
     * @param escrowId Escrow to claim
     * @param serviceProof Proof of service delivery
     * @param preimage HTLC preimage (bytes32(0) if no hashlock)
     */
    function claimEscrow(
        bytes32 escrowId,
        ServiceProof calldata serviceProof,
        bytes32 preimage
    ) external;
    
    // ============ Dispute Functions ============
    
    /**
     * @notice Dispute an escrow (by agent or provider)
     * @param escrowId Escrow to dispute
     * @param evidence Dispute evidence
     */
    function disputeEscrow(bytes32 escrowId, bytes calldata evidence) external;
    
    /**
     * @notice Resolve a dispute (guardian/DAO only)
     * @param escrowId Disputed escrow
     * @param winner Winner of dispute (agent or provider)
     * @param agentRefund Amount to refund to agent
     * @param providerPayout Amount to pay to provider
     */
    function resolveDispute(
        bytes32 escrowId,
        address winner,
        uint256 agentRefund,
        uint256 providerPayout
    ) external;
}
