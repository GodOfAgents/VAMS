// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IHardwareCommitment
 * @notice Enforces time-locked collateral commitments for active hardware nodes.
 *         Providers must commit their hardware for minimum durations to prevent
 *         hit-and-run network registration.
 */
interface IHardwareCommitment {

    struct HardwareCommitment {
        address provider;            // Operator address
        bytes32[] nodeIds;           // The specific nodes locked in this commitment
        uint256 collateral;          // Total $VAMS locked (after multipliers applied)
        uint256 commitmentStart;     // Block timestamp
        uint256 commitmentEnd;       // Target hardware unlock time
        uint256 minUptimeBps;        // Required uptime (e.g. 9950 = 99.5%)
        bool isActive;               // Check if commitment hasn't been closed/slashed
        uint256 totalSlashed;        // Record of any fines executed during term
    }

    // ============ Events ============

    event CommitmentCreated(bytes32 indexed commitmentId, address indexed provider, uint256 durationSeconds, uint256 collateral);
    event CommitmentExtended(bytes32 indexed commitmentId, uint256 newEndTimestamp, uint256 internalCollateralAdded);
    event CommitmentEnded(bytes32 indexed commitmentId, address indexed provider, uint256 collateralReturned);
    event CommitmentSlashed(bytes32 indexed commitmentId, uint256 slashAmount, string reason);

    // ============ Custom Errors ============

    error CommitmentNotExpired(bytes32 commitmentId, uint256 currentTime, uint256 endTime);
    error CommitmentInactive(bytes32 commitmentId);
    error UnauthorizedProvider(address caller, address owner);
    error InsufficientProviderBond(address provider, uint256 required, uint256 available);
    error NodeNotOwnedByProvider(bytes32 nodeId, address provider);
    error ZeroNodeCommitment();

    // ============ Core Functions ============

    /**
     * @notice Locks hardware nodes into a time-based commitment.
     * @param nodeIds Array of registered nodes to commit
     * @param durationSeconds Minimum lock period
     * @param minUptimeBps Expected SLA threshold (bps)
     * @return commitmentId Unique ID for this pledge
     */
    function createCommitment(bytes32[] calldata nodeIds, uint256 durationSeconds, uint256 minUptimeBps) external returns (bytes32 commitmentId);

    /**
     * @notice Extends an active commitment, applying potential new scalar multipliers
     * @param commitmentId ID of the commitment
     * @param additionalSeconds How much longer to pledge
     */
    function extendCommitment(bytes32 commitmentId, uint256 additionalSeconds) external;

    /**
     * @notice Safely closes a commitment after duration expiry, returning clean SLA score
     * @param commitmentId ID of the commitment
     */
    function endCommitment(bytes32 commitmentId) external;

    /**
     * @notice Invoked directly by SLAEnforcer if one of the underlying nodes vanishes early
     * @param commitmentId The pledge ID housing the node
     * @param penaltyBps Penalty percentage against total collateral
     */
    function slashCommitment(bytes32 commitmentId, uint256 penaltyBps) external;

    // ============ View Functions ============

    function getCommitment(bytes32 commitmentId) external view returns (HardwareCommitment memory);
    function getProviderCommitments(address provider) external view returns (bytes32[] memory);
    function isNodeCommitted(bytes32 nodeId) external view returns (bool, bytes32 timestamp);

}
