// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IX402NonceRegistry
 * @author VAMS Protocol
 * @notice Interface for preventing double-spend in x402 micropayments
 * @dev Tracks used nonces and receipt hashes to prevent replay attacks
 *
 * Architecture Reference: ARCHITECTURE_v0-3-0.md §20.2.1
 *
 * Security Model:
 * - Each agent has a monotonically increasing nonce
 * - Each receipt (agent + nonce + amount + provider) has unique hash
 * - Both nonce AND receipt hash must be unused for valid payment
 */
interface IX402NonceRegistry {
    // ============ Structs ============

    /**
     * @notice Information about a consumed nonce
     * @param used Whether the nonce has been consumed
     * @param receiptHash Hash of the receipt that consumed this nonce
     * @param consumedAt Timestamp when nonce was consumed
     * @param escrowId Associated escrow ID (if applicable)
     */
    struct NonceInfo {
        bool used;
        bytes32 receiptHash;
        uint256 consumedAt;
        bytes32 escrowId;
    }

    // ============ Events ============

    /**
     * @notice Emitted when a nonce is consumed
     * @param agent Agent whose nonce was consumed
     * @param nonce The nonce value
     * @param receiptHash Hash of the associated receipt
     * @param escrowId Associated escrow (bytes32(0) if none)
     */
    event NonceConsumed(address indexed agent, uint256 indexed nonce, bytes32 receiptHash, bytes32 escrowId);

    /**
     * @notice Emitted when a settlement contract is authorized
     * @param settler Address authorized for settlement
     */
    event SettlerAuthorized(address indexed settler);

    /**
     * @notice Emitted when a settlement contract is deauthorized
     * @param settler Address deauthorized
     */
    event SettlerDeauthorized(address indexed settler);

    // ============ Errors ============

    /// @notice Nonce has already been used
    error NonceAlreadyUsed(address agent, uint256 nonce);

    /// @notice Receipt has already been claimed
    error ReceiptAlreadyClaimed(bytes32 receiptHash);

    /// @notice Signature verification failed
    error InvalidSignature();

    /// @notice Caller is not authorized to consume nonces
    error UnauthorizedCaller();

    /// @notice Agent has insufficient escrow balance
    error InsufficientEscrow(uint256 required, uint256 available);

    /// @notice Zero address provided
    error ZeroAddress();

    // ============ View Functions ============

    /**
     * @notice Check if a nonce is valid (unused)
     * @param agent Agent address
     * @param nonce Nonce value to check
     * @return True if nonce has not been used
     */
    function isNonceValid(address agent, uint256 nonce) external view returns (bool);

    /**
     * @notice Check if a receipt hash has been claimed
     * @param receiptHash Hash to check
     * @return True if receipt has been claimed
     */
    function isReceiptClaimed(bytes32 receiptHash) external view returns (bool);

    /**
     * @notice Verify a payment receipt without consuming it
     * @dev Used by providers before delivering service
     * @param agent Agent address
     * @param nonce Payment nonce
     * @param amount Payment amount
     * @param signature Agent's signature on (agent, nonce, amount)
     * @return valid True if receipt is valid and unclaimed
     * @return reason Human-readable reason if invalid
     */
    function verifyReceipt(address agent, uint256 nonce, uint256 amount, bytes calldata signature)
        external
        view
        returns (bool valid, string memory reason);

    /**
     * @notice Get the next available (unused) nonce for an agent
     * @dev Searches sequentially from 0
     * @param agent Agent address
     * @return Next unused nonce value
     */
    function getNextNonce(address agent) external view returns (uint256);

    /**
     * @notice Get the highest used nonce for an agent
     * @param agent Agent address
     * @return Highest nonce that has been used (0 if none)
     */
    function getHighestUsedNonce(address agent) external view returns (uint256);

    /**
     * @notice Get detailed info about a specific nonce
     * @param agent Agent address
     * @param nonce Nonce value
     * @return NonceInfo struct with usage details
     */
    function getNonceInfo(address agent, uint256 nonce) external view returns (NonceInfo memory);

    /**
     * @notice Check if an address is authorized to consume nonces
     * @param settler Address to check
     * @return True if authorized
     */
    function isAuthorizedSettler(address settler) external view returns (bool);

    // ============ State-Changing Functions ============

    /**
     * @notice Consume a nonce (mark as used)
     * @dev Only callable by authorized settlement contracts
     * @param agent Agent address
     * @param nonce Nonce value
     * @param receiptHash Unique receipt hash
     * @param escrowId Associated escrow ID (bytes32(0) if none)
     */
    function consumeNonce(address agent, uint256 nonce, bytes32 receiptHash, bytes32 escrowId) external;

    /**
     * @notice Batch consume multiple nonces
     * @dev Gas-efficient for batch settlements
     * @param agents Array of agent addresses
     * @param nonces Array of nonce values
     * @param receiptHashes Array of receipt hashes
     * @param escrowIds Array of escrow IDs
     */
    function batchConsumeNonces(
        address[] calldata agents,
        uint256[] calldata nonces,
        bytes32[] calldata receiptHashes,
        bytes32[] calldata escrowIds
    ) external;

    // ============ Admin Functions ============

    /**
     * @notice Authorize a settlement contract to consume nonces
     * @param settler Address to authorize
     */
    function authorizeSettler(address settler) external;

    /**
     * @notice Remove authorization from a settlement contract
     * @param settler Address to deauthorize
     */
    function deauthorizeSettler(address settler) external;
}
