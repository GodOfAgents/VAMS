// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IRegionAwareDEC
 * @author VAMS Protocol
 * @notice Interface for the Region-Aware Dynamic Emission Controller.
 * @dev Allocates epoch emission budgets proportionally across geographic
 *      regions using live multipliers from RegionalIncentives.
 *
 *      Architecture Reference: Phase 4 (Economic Layer), Sprint 9
 */
interface IRegionAwareDEC {
    // ═══════════════════ Structs ═══════════════════

    /// @notice Per-region emission allocation for an epoch
    struct RegionEmissionAlloc {
        bytes32 regionId;           // Region identifier
        uint256 weightedCapacity;   // currentCapacity × multiplierBps
        uint256 allocationBps;      // Share of epoch budget (in BPS of total)
        uint256 emittedThisEpoch;   // Tokens emitted for this region in current epoch
    }

    /// @notice Summary of a completed epoch
    struct EpochSummary {
        uint256 epochId;
        uint256 startTime;
        uint256 endTime;
        uint256 totalEmitted;
        uint256 regionCount;
    }

    // ═══════════════════ Events ═══════════════════

    /// @notice Emitted when region allocations are recalculated
    event RegionAllocationsUpdated(
        uint256 indexed epochId,
        uint256 totalWeightedCapacity,
        uint256 regionCount
    );

    /// @notice Emitted when epoch emissions are distributed
    event EpochEmissionsDistributed(
        uint256 indexed epochId,
        uint256 totalEmitted,
        address indexed rewardDistributor
    );

    /// @notice Emitted when the region cap is updated
    event RegionCapUpdated(uint256 oldCapBps, uint256 newCapBps);

    /// @notice Emitted when the reward distributor address is updated
    event RewardDistributorUpdated(address indexed oldDistributor, address indexed newDistributor);

    // ═══════════════════ Errors ═══════════════════

    /// @notice Thrown when epoch has not elapsed yet
    error EpochNotElapsed(uint256 currentTime, uint256 nextEpochAt);

    /// @notice Thrown when no regions are configured
    error NoActiveRegions();

    /// @notice Thrown when region cap is invalid
    error InvalidRegionCap(uint256 capBps);

    // ═══════════════════ Functions ═══════════════════

    /// @notice Set the RegionalIncentives contract address
    function setRegionalIncentives(address _regionalIncentives) external;

    /// @notice Set the DynamicEmissionController address
    function setEmissionController(address _dec) external;

    /// @notice Set the RewardDistributor address
    function setRewardDistributor(address _rewardDistributor) external;

    /// @notice Set the maximum allocation share for any single region (in BPS)
    /// @param capBps Max BPS a single region can receive (e.g. 3000 = 30%)
    function setRegionCap(uint256 capBps) external;

    /// @notice Calculate per-region emission allocations based on current multipliers
    /// @return allocations Array of RegionEmissionAlloc for all active regions
    function calculateRegionAllocations()
        external
        view
        returns (RegionEmissionAlloc[] memory allocations);

    /// @notice Distribute epoch emissions to the RewardDistributor
    /// @dev Can only be called once per epoch by KEEPER_ROLE
    /// @return totalEmitted Total tokens distributed this epoch
    function distributeEpochEmissions() external returns (uint256 totalEmitted);

    /// @notice Get the emission allocation for a specific region in the current epoch
    function getRegionAllocation(bytes32 regionId)
        external
        view
        returns (RegionEmissionAlloc memory);

    /// @notice Get the total emission budget for the current epoch
    function getEpochEmissionBudget() external view returns (uint256);

    /// @notice Get the current epoch ID
    function currentEpoch() external view returns (uint256);

    /// @notice Get the epoch duration in seconds
    function epochDuration() external view returns (uint256);

    /// @notice Get the region allocation cap in BPS
    function regionCapBps() external view returns (uint256);
}
