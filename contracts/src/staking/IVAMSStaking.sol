// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSStaking
 * @author VAMS Protocol
 * @notice Interface for tiered VAMS token staking with rewards
 * @dev Implements 4 tiers from TOKENOMICS.md:
 *
 * | Tier     | Amount       | Base APY | Benefits                    |
 * |----------|--------------|----------|-----------------------------|
 * | Silver   | 50K - 99.9K  | 8%       | Priority support            |
 * | Gold     | 100K - 999.9K| 10%      | 1.5x governance weight      |
 * | Platinum | 1M+          | 12%      | CLR operator eligible       |
 */
interface IVAMSStaking {
    // ============ Enums ============

    /// @notice Staking tier based on amount
    enum StakingTier {
        None,       // < 50,000 VAMS
        Silver,     // 50,000 - 99,999
        Gold,       // 100,000 - 999,999
        Platinum    // 1,000,000+
    }

    /// @notice Lock period options
    enum LockPeriod {
        SevenDays,      // 7 days - 1.0x multiplier
        ThirtyDays,     // 30 days - 1.1x multiplier
        NinetyDays,     // 90 days - 1.25x multiplier
        OneEightyDays   // 180 days - 1.5x multiplier
    }

    // ============ Structs ============

    /// @notice User stake information
    struct StakeInfo {
        uint256 amount;             // Amount staked
        uint256 rewardDebt;         // Reward debt for calculation
        uint256 pendingRewards;     // Accumulated pending rewards
        uint256 stakedAt;           // Timestamp when staked
        uint256 lockedUntil;        // Timestamp when unlock possible
        LockPeriod lockPeriod;      // Selected lock period
        bool autoCompound;          // Auto-compound rewards
    }

    /// @notice Unbonding request
    struct UnbondingRequest {
        uint256 amount;             // Amount being unbonded
        uint256 unbondingEnd;       // When unbonding completes
    }

    // ============ Events ============

    /// @notice Emitted when tokens are staked
    event Staked(
        address indexed user,
        uint256 amount,
        LockPeriod lockPeriod,
        uint256 lockedUntil
    );

    /// @notice Emitted when unstaking is initiated
    event Unstaked(
        address indexed user,
        uint256 amount,
        uint256 unbondingEnds
    );

    /// @notice Emitted when tokens are withdrawn after unbonding
    event Withdrawn(address indexed user, uint256 amount);

    /// @notice Emitted when rewards are claimed
    event RewardsClaimed(address indexed user, uint256 amount);

    /// @notice Emitted when rewards are compounded
    event RewardsCompounded(address indexed user, uint256 amount);

    /// @notice Emitted when user's tier changes
    event TierChanged(
        address indexed user,
        StakingTier oldTier,
        StakingTier newTier
    );

    /// @notice Emitted when emission rate is updated
    event EmissionRateUpdated(uint256 oldRate, uint256 newRate);

    /// @notice Emitted when auto-compound is toggled
    event AutoCompoundToggled(address indexed user, bool enabled);

    // ============ Errors ============

    /// @notice Thrown when amount is zero
    error ZeroAmount();

    /// @notice Thrown when stake is locked
    error StakeLocked(uint256 lockedUntil);

    /// @notice Thrown when unbonding is not complete
    error UnbondingNotComplete(uint256 unbondingEnd);

    /// @notice Thrown when no unbonding request exists
    error NoUnbondingRequest();

    /// @notice Thrown when user has no stake
    error NoStake();

    /// @notice Thrown when insufficient stake for operation
    error InsufficientStake(uint256 requested, uint256 available);

    /// @notice Thrown when nothing to claim
    error NothingToClaim();

    /// @notice Thrown when address is zero
    error ZeroAddress();

    /// @notice Thrown when stake is below minimum
    error BelowMinimumStake(uint256 amount, uint256 minimum);

    // ============ Staking Functions ============

    /// @notice Stake tokens with a lock period
    /// @param amount Amount to stake
    /// @param lockPeriod Lock period selection
    function stake(uint256 amount, LockPeriod lockPeriod) external;

    /// @notice Stake with permit signature (gasless approval)
    /// @param amount Amount to stake
    /// @param lockPeriod Lock period selection
    /// @param deadline Permit deadline
    /// @param v Signature v
    /// @param r Signature r
    /// @param s Signature s
    function stakeWithPermit(
        uint256 amount,
        LockPeriod lockPeriod,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external;

    /// @notice Add to existing stake (inherits original lock)
    /// @param amount Amount to add
    function addStake(uint256 amount) external;

    // ============ Unstaking Functions ============

    /// @notice Initiate unstaking (starts unbonding period)
    /// @param amount Amount to unstake
    function unstake(uint256 amount) external;

    /// @notice Complete unstaking after unbonding period
    /// @return amount Amount withdrawn
    function withdraw() external returns (uint256 amount);

    /// @notice Emergency withdraw (forfeits pending rewards)
    function emergencyWithdraw() external;

    // ============ Reward Functions ============

    /// @notice Claim pending rewards
    /// @return amount Amount claimed
    function claimRewards() external returns (uint256 amount);

    /// @notice Compound rewards (restake pending rewards)
    /// @return amount Amount compounded
    function compoundRewards() external returns (uint256 amount);

    /// @notice Toggle auto-compound
    /// @param enabled True to enable auto-compound
    function setAutoCompound(bool enabled) external;

    // ============ Governance Functions ============

    /// @notice Get voting power for governance
    /// @param account Address to query
    /// @return power Voting power (includes tier multiplier)
    function getVotingPower(address account) external view returns (uint256 power);

    /// @notice Check if account is eligible for CLR operator
    /// @param account Address to check
    /// @return eligible True if Platinum tier
    function isCLROperatorEligible(address account) external view returns (bool eligible);

    // ============ View Functions ============

    /// @notice Get stake info for account
    /// @param account Address to query
    /// @return info Stake information
    function getStakeInfo(address account) external view returns (StakeInfo memory info);

    /// @notice Get unbonding request for account
    /// @param account Address to query
    /// @return request Unbonding request
    function getUnbondingRequest(address account) external view returns (UnbondingRequest memory request);

    /// @notice Get staking tier for account
    /// @param account Address to query
    /// @return tier Current tier
    function getTier(address account) external view returns (StakingTier tier);

    /// @notice Calculate pending rewards
    /// @param account Address to query
    /// @return rewards Pending rewards
    function pendingRewards(address account) external view returns (uint256 rewards);

    /// @notice Get current APY for tier and lock period
    /// @param tier Staking tier
    /// @param lockPeriod Lock period
    /// @return apy APY in basis points
    function getAPY(StakingTier tier, LockPeriod lockPeriod) external view returns (uint256 apy);

    /// @notice Get time until unlock
    /// @param account Address to query
    /// @return remainingSeconds Seconds until unlock (0 if unlocked)
    function timeToUnlock(address account) external view returns (uint256 remainingSeconds);

    /// @notice Get total staked in the contract
    /// @return total Total staked tokens
    function totalStaked() external view returns (uint256 total);

    /// @notice Get current emission rate
    /// @return rate Tokens per second
    function rewardPerSecond() external view returns (uint256 rate);

    // ============ Admin Functions ============

    /// @notice Update emission rate (governance only)
    /// @param newRate New tokens per second
    function updateEmissionRate(uint256 newRate) external;

    /// @notice Pause staking (emergency)
    function pause() external;

    /// @notice Unpause staking
    function unpause() external;
}
