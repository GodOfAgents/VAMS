// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IRegionalIncentives
 * @author VAMS Protocol
 * @notice Interface for the on-chain regional reward multiplier system.
 * @dev Incentivizes providers to deploy in underserved regions by
 *      modifying reward distributions via bootstrap multipliers.
 *
 *      Architecture Reference: Phase 3 (Intelligence Layer), Sprint 7
 */
interface IRegionalIncentives {
    // ═══════════════════ Structs ═══════════════════

    /// @notice Configuration for a geographic region
    struct RegionConfig {
        bytes32 regionId; // keccak256("us-east-1")
        string displayName; // "US East (Virginia)"
        uint256 targetCapacity; // Target capacity units
        uint256 bootstrapMultiplierBps; // Max reward multiplier (10000 = 1.0x, 30000 = 3.0x)
        uint256 currentCapacity; // Live capacity from HardwareRegistry
        bool isActive;
    }

    // ═══════════════════ Events ═══════════════════

    event RegionConfigured(
        bytes32 indexed regionId, string displayName, uint256 targetCapacity, uint256 bootstrapMultiplierBps
    );

    event RegionCapacityUpdated(
        bytes32 indexed regionId, uint256 oldCapacity, uint256 newCapacity, uint256 currentMultiplierBps
    );

    event RegionDeactivated(bytes32 indexed regionId);
    event RegionActivated(bytes32 indexed regionId);

    // ═══════════════════ Functions ═══════════════════

    /// @notice Set or update a region's configuration
    function setRegionConfig(
        bytes32 regionId,
        string calldata displayName,
        uint256 targetCapacity,
        uint256 bootstrapMultiplierBps
    ) external;

    /// @notice Update the current capacity for a region
    function updateCapacity(bytes32 regionId, uint256 newCapacity) external;

    /// @notice Batch update capacities for multiple regions
    function batchUpdateCapacity(bytes32[] calldata regionIds, uint256[] calldata capacities) external;

    /// @notice Deactivate a region (multiplier returns 1.0x)
    function deactivateRegion(bytes32 regionId) external;

    /// @notice Reactivate a previously deactivated region
    function activateRegion(bytes32 regionId) external;

    /// @notice Get the current reward multiplier for a region (in BPS)
    /// @return multiplierBps The reward multiplier (10000 = 1.0x)
    function getRewardMultiplier(bytes32 regionId) external view returns (uint256 multiplierBps);

    /// @notice Get full region configuration
    function getRegionConfig(bytes32 regionId) external view returns (RegionConfig memory);

    /// @notice Check if a region is configured and active
    function isRegionActive(bytes32 regionId) external view returns (bool);
}
