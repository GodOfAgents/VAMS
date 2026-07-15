// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IComposedSettlement
 * @author VAMS Protocol
 * @notice Interface for multi-provider composed payment settlement.
 * @dev Handles escrow locking and per-provider claims for blueprints
 *      that span multiple hardware providers via the Resource Composer.
 *
 *      Hybrid model: single escrow lock, per-provider Merkle claim.
 *
 *      Architecture Reference: Phase 4 (Economic Layer), Sprint 10
 */
interface IComposedSettlement {
    // ═══════════════════ Enums ═══════════════════

    enum AllocationStatus {
        LOCKED,
        PARTIALLY_CLAIMED,
        FULLY_CLAIMED,
        EXPIRED,
        DISPUTED
    }

    // ═══════════════════ Structs ═══════════════════

    /// @notice A single provider's allocation within a composed request
    struct ProviderAlloc {
        address provider; // Provider address
        uint256 amount; // Payment amount for this provider
        bool claimed; // Whether this provider has claimed
        uint256 claimedAt; // Timestamp of claim (0 if unclaimed)
    }

    /// @notice A composed allocation spanning multiple providers
    struct ComposedAllocation {
        bytes32 allocationId; // Unique identifier
        address agent; // Requesting agent
        uint256 totalAmount; // Total escrowed amount
        uint256 providerCount; // Number of providers in the allocation
        uint256 claimedCount; // Providers that have successfully claimed
        bytes32 blueprintHash; // Hash of the blueprint that was composed
        bytes32 serviceBlockId; // Associated service block (0 if raw blueprint)
        uint256 createdAt; // Lock timestamp
        uint256 expiresAt; // Expiry timestamp
        AllocationStatus status; // Current status
        uint256 builderRevShareBps; // Builder revenue share in basis points
        address builderAddress; // Builder who receives revenue share
    }

    // ═══════════════════ Events ═══════════════════

    event ComposedEscrowCreated(
        bytes32 indexed allocationId,
        address indexed agent,
        uint256 totalAmount,
        uint256 providerCount,
        uint256 expiresAt
    );

    event ProviderShareClaimed(
        bytes32 indexed allocationId, address indexed provider, uint256 payout, uint256 fee, uint256 builderShare
    );

    event ComposedEscrowRefunded(bytes32 indexed allocationId, address indexed agent, uint256 refundedAmount);

    event ComposedEscrowDisputed(bytes32 indexed allocationId, address indexed disputer);

    // ═══════════════════ Errors ═══════════════════

    error AllocationNotFound(bytes32 allocationId);
    error AllocationNotClaimable(bytes32 allocationId);
    error AllocationNotExpired(bytes32 allocationId);
    error ProviderAlreadyClaimed(bytes32 allocationId, uint256 index);
    error ProviderMismatch(address expected, address actual);
    error InvalidProviderIndex(uint256 index, uint256 maxIndex);
    error ArrayLengthMismatch();
    error ZeroProviders();
    error AmountMismatch(uint256 expected, uint256 actual);

    // ═══════════════════ Functions ═══════════════════

    /// @notice Create a composed escrow for multiple providers
    /// @param providers Array of provider addresses
    /// @param amounts Array of amounts per provider
    /// @param validForSeconds Duration before expiry
    /// @param blueprintHash Hash of the composed blueprint
    /// @param serviceBlockId Service block ID (bytes32(0) if raw)
    /// @param builderRevShareBps Builder's revenue share in BPS
    /// @param builderAddress Builder's address for revenue share
    /// @return allocationId Unique ID for the allocation
    function createComposedEscrow(
        address[] calldata providers,
        uint256[] calldata amounts,
        uint256 validForSeconds,
        bytes32 blueprintHash,
        bytes32 serviceBlockId,
        uint256 builderRevShareBps,
        address builderAddress
    ) external returns (bytes32 allocationId);

    /// @notice Provider claims their share of a composed allocation
    /// @param allocationId The allocation to claim from
    /// @param providerIndex Index of the provider in the allocation
    function claimProviderShare(bytes32 allocationId, uint256 providerIndex) external;

    /// @notice Refund expired and unclaimed portions to the agent
    /// @param allocationId The expired allocation
    function refundExpiredComposed(bytes32 allocationId) external;

    /// @notice Get a composed allocation's details
    function getComposedAllocation(bytes32 allocationId) external view returns (ComposedAllocation memory);

    /// @notice Get a specific provider's allocation
    function getProviderAlloc(bytes32 allocationId, uint256 providerIndex) external view returns (ProviderAlloc memory);

    /// @notice Check if all providers in an allocation have claimed
    function isFullyClaimed(bytes32 allocationId) external view returns (bool);
}
