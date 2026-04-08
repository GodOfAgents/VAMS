// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IRewardDistributor
 * @author VAMS Protocol
 * @notice Interface for the unified provider reward distribution system.
 * @dev Aggregates regional emission bonuses, builder revenue shares, and
 *      staking boosts into a single claimable reward pool.
 *
 *      Architecture Reference: Phase 4 (Economic Layer), Sprint 11
 */
interface IRewardDistributor {
    // ═══════════════════ Structs ═══════════════════

    /// @notice Summary of a completed reward epoch
    struct RewardEpoch {
        uint256 epochId;
        uint256 startTime;
        uint256 endTime;
        uint256 totalDistributed;
        uint256 providerCount;
        bool finalized;
    }

    /// @notice Reward breakdown for a single provider
    struct ProviderReward {
        uint256 baseReward;          // Share of settled escrows
        uint256 regionalBonus;       // Extra from region multiplier
        uint256 stakingBoost;        // Extra from staking tier
        uint256 builderRevenue;      // Accumulated builder share
        uint256 totalReward;         // Sum of all components
    }

    // ═══════════════════ Events ═══════════════════

    event RewardsAccumulated(
        address indexed provider,
        uint256 baseReward,
        uint256 regionalBonus,
        uint256 stakingBoost,
        uint256 totalReward
    );

    event RewardsClaimed(
        address indexed provider,
        uint256 amount,
        uint256 epochsCovered
    );

    event EpochRewardsDistributed(
        uint256 indexed epochId,
        uint256 totalDistributed,
        uint256 providerCount
    );

    event BuilderRevenueAccumulated(
        address indexed builder,
        uint256 amount
    );

    // ═══════════════════ Errors ═══════════════════

    error NoRewardsToClaim(address provider);
    error EpochAlreadyFinalized(uint256 epochId);
    error InvalidRewardData();

    // ═══════════════════ Functions ═══════════════════

    /// @notice Accumulate rewards for a provider (called by keeper or settlement contracts)
    /// @param provider Provider address
    /// @param baseReward Base reward from settlements
    /// @param regionId Region for multiplier lookup
    function accumulateReward(
        address provider,
        uint256 baseReward,
        bytes32 regionId
    ) external;

    /// @notice Accumulate builder revenue share
    /// @param builder Builder address
    /// @param amount Revenue share amount
    function accumulateBuilderRevenue(
        address builder,
        uint256 amount
    ) external;

    /// @notice Finalize an epoch's reward distribution
    /// @param epochId Epoch to finalize
    function finalizeEpoch(uint256 epochId) external;

    /// @notice Provider claims all accumulated, unclaimed rewards
    function claimRewards() external;

    /// @notice Get unclaimed reward balance for a provider
    function getUnclaimedRewards(address provider) external view returns (uint256);

    /// @notice Get detailed reward breakdown for a provider
    function getRewardBreakdown(address provider) external view returns (ProviderReward memory);

    /// @notice Get epoch summary
    function getEpochSummary(uint256 epochId) external view returns (RewardEpoch memory);

    /// @notice Get current epoch ID
    function currentEpoch() external view returns (uint256);
}
