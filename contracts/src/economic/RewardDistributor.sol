// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IRewardDistributor} from "./IRewardDistributor.sol";
import {IRegionalIncentives} from "./IRegionalIncentives.sol";

/**
 * @title RewardDistributor
 * @author VAMS Protocol
 * @notice Unified provider reward distribution engine.
 * @dev Aggregates four reward components:
 *      1. Base rewards — proportional share of completed settlements
 *      2. Regional bonuses — extra from region multipliers
 *      3. Staking boosts — bonus for staked providers (tier-based)
 *      4. Builder revenue — accumulated marketplace revenue shares
 *
 *      Uses lazy-claim pattern: rewards accumulate on-chain, providers
 *      claim at their convenience. Supports epoch-based accounting.
 *
 *      Fee integration: Receives tokens from RegionAwareDEC (emissions)
 *      and directly from ComposedSettlement (fee routing).
 *
 *      Architecture Reference: Phase 4 (Economic Layer), Sprint 11
 */
contract RewardDistributor is
    IRewardDistributor,
    AccessControl,
    ReentrancyGuard,
    Pausable
{
    using SafeERC20 for IERC20;

    // ═══════════════════ Constants ═══════════════════

    bytes32 public constant KEEPER_ROLE = keccak256("KEEPER_ROLE");
    bytes32 public constant ACCUMULATOR_ROLE = keccak256("ACCUMULATOR_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    uint256 public constant BPS_DENOMINATOR = 10_000;

    // Staking boost tiers (BPS addition to base reward)
    uint256 public constant TIER_IRON_BOOST_BPS = 0;       // No boost
    uint256 public constant TIER_BRONZE_BOOST_BPS = 200;    // +2%
    uint256 public constant TIER_SILVER_BOOST_BPS = 500;    // +5%
    uint256 public constant TIER_GOLD_BOOST_BPS = 1_000;    // +10%
    uint256 public constant TIER_DIAMOND_BOOST_BPS = 2_000; // +20%

    // Staking tier thresholds (in VAMS tokens)
    uint256 public constant TIER_BRONZE_MIN = 10_000 ether;
    uint256 public constant TIER_SILVER_MIN = 50_000 ether;
    uint256 public constant TIER_GOLD_MIN = 200_000 ether;
    uint256 public constant TIER_DIAMOND_MIN = 1_000_000 ether;

    // ═══════════════════ Storage ═══════════════════

    /// @notice VAMS token
    IERC20 public vamsToken;

    /// @notice Regional incentives for multiplier lookups
    IRegionalIncentives public regionalIncentives;

    /// @notice Staking contract for tier lookups
    address public stakingContract;

    /// @notice Current epoch
    uint256 public override currentEpoch;

    /// @notice Unclaimed rewards per provider
    mapping(address => uint256) public unclaimedRewards;

    /// @notice Detailed reward breakdown per provider (current accumulation)
    mapping(address => ProviderReward) private _rewardBreakdowns;

    /// @notice Builder revenue accumulations
    mapping(address => uint256) public builderRevenue;

    /// @notice Epoch summaries
    mapping(uint256 => RewardEpoch) private _epochs;

    /// @notice Total distributed across all epochs
    uint256 public totalDistributed;

    /// @notice Total claimed by providers
    uint256 public totalClaimed;

    // ═══════════════════ Constructor ═══════════════════

    /// @notice Initialize the RewardDistributor
    /// @param admin Admin address
    /// @param _vamsToken VAMS Token address
    /// @param _regionalIncentives Regional incentives address
    /// @param _stakingContract Staking contract address
    constructor(
        address admin,
        address _vamsToken,
        address _regionalIncentives,
        address _stakingContract
    ) {
        require(admin != address(0), "Zero admin");
        require(_vamsToken != address(0), "Zero token");

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(KEEPER_ROLE, admin);
        _grantRole(ACCUMULATOR_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);

        vamsToken = IERC20(_vamsToken);
        regionalIncentives = IRegionalIncentives(_regionalIncentives);
        stakingContract = _stakingContract;
        currentEpoch = 0;
    }

    // ═══════════════════ Reward Accumulation ═══════════════════

    /// @inheritdoc IRewardDistributor
    function accumulateReward(
        address provider,
        uint256 baseReward,
        bytes32 regionId
    ) external override onlyRole(ACCUMULATOR_ROLE) whenNotPaused {
        if (provider == address(0) || baseReward == 0) revert InvalidRewardData();

        // 1. Base reward
        uint256 regionalBonus = 0;
        uint256 stakingBoost = 0;

        // 2. Regional bonus: (multiplier - 1.0) × baseReward
        if (address(regionalIncentives) != address(0) && regionId != bytes32(0)) {
            uint256 multiplierBps = regionalIncentives.getRewardMultiplier(regionId);
            if (multiplierBps > BPS_DENOMINATOR) {
                uint256 bonusBps = multiplierBps - BPS_DENOMINATOR;
                regionalBonus = (baseReward * bonusBps) / BPS_DENOMINATOR;
            }
        }

        // 3. Staking boost
        uint256 boostBps = _getStakingBoostBps(provider);
        if (boostBps > 0) {
            stakingBoost = (baseReward * boostBps) / BPS_DENOMINATOR;
        }

        // Total for this accumulation
        uint256 totalReward = baseReward + regionalBonus + stakingBoost;

        // Update provider breakdown
        ProviderReward storage breakdown = _rewardBreakdowns[provider];
        breakdown.baseReward += baseReward;
        breakdown.regionalBonus += regionalBonus;
        breakdown.stakingBoost += stakingBoost;
        breakdown.totalReward += totalReward;

        // Update claimable balance
        unclaimedRewards[provider] += totalReward;
        totalDistributed += totalReward;

        emit RewardsAccumulated(provider, baseReward, regionalBonus, stakingBoost, totalReward);
    }

    /// @inheritdoc IRewardDistributor
    function accumulateBuilderRevenue(
        address builder,
        uint256 amount
    ) external override onlyRole(ACCUMULATOR_ROLE) whenNotPaused {
        if (builder == address(0) || amount == 0) revert InvalidRewardData();

        builderRevenue[builder] += amount;
        unclaimedRewards[builder] += amount;
        totalDistributed += amount;

        _rewardBreakdowns[builder].builderRevenue += amount;
        _rewardBreakdowns[builder].totalReward += amount;

        emit BuilderRevenueAccumulated(builder, amount);
    }

    // ═══════════════════ Epoch Management ═══════════════════

    /// @inheritdoc IRewardDistributor
    function finalizeEpoch(uint256 epochId) external override onlyRole(KEEPER_ROLE) {
        RewardEpoch storage epoch = _epochs[epochId];
        if (epoch.finalized) revert EpochAlreadyFinalized(epochId);

        epoch.epochId = epochId;
        epoch.endTime = block.timestamp;
        epoch.finalized = true;

        // Start next epoch
        currentEpoch++;
        _epochs[currentEpoch] = RewardEpoch({
            epochId: currentEpoch,
            startTime: block.timestamp,
            endTime: 0,
            totalDistributed: 0,
            providerCount: 0,
            finalized: false
        });
    }

    // ═══════════════════ Claims ═══════════════════

    /// @inheritdoc IRewardDistributor
    function claimRewards() external override nonReentrant whenNotPaused {
        uint256 claimable = unclaimedRewards[msg.sender];
        if (claimable == 0) revert NoRewardsToClaim(msg.sender);

        // Reset unclaimed balance
        unclaimedRewards[msg.sender] = 0;
        totalClaimed += claimable;

        // Reset breakdown
        delete _rewardBreakdowns[msg.sender];

        // Transfer
        vamsToken.safeTransfer(msg.sender, claimable);

        emit RewardsClaimed(msg.sender, claimable, currentEpoch);
    }

    // ═══════════════════ View Functions ═══════════════════

    /// @inheritdoc IRewardDistributor
    function getUnclaimedRewards(address provider)
        external
        view
        override
        returns (uint256)
    {
        return unclaimedRewards[provider];
    }

    /// @inheritdoc IRewardDistributor
    function getRewardBreakdown(address provider)
        external
        view
        override
        returns (ProviderReward memory)
    {
        return _rewardBreakdowns[provider];
    }

    /// @inheritdoc IRewardDistributor
    function getEpochSummary(uint256 epochId)
        external
        view
        override
        returns (RewardEpoch memory)
    {
        return _epochs[epochId];
    }

    /// @notice Get the staking tier for a provider based on their stake
    /// @param provider The provider address
    /// @return String representation of the staking tier
    function getProviderTier(address provider) external view returns (string memory) {
        uint256 staked = _getStakedAmount(provider);
        if (staked >= TIER_DIAMOND_MIN) return "DIAMOND";
        if (staked >= TIER_GOLD_MIN) return "GOLD";
        if (staked >= TIER_SILVER_MIN) return "SILVER";
        if (staked >= TIER_BRONZE_MIN) return "BRONZE";
        return "IRON";
    }

    // ═══════════════════ Admin ═══════════════════

    /// @notice Update the regional incentives contract
    /// @param _ri New regional incentives address
    function setRegionalIncentives(address _ri) external onlyRole(DEFAULT_ADMIN_ROLE) {
        regionalIncentives = IRegionalIncentives(_ri);
    }

    /// @notice Update the staking contract
    /// @param _staking New staking contract address
    function setStakingContract(address _staking) external onlyRole(DEFAULT_ADMIN_ROLE) {
        stakingContract = _staking;
    }

    /// @notice Emergency withdrawal of stuck tokens
    /// @param to Address to send tokens to
    /// @param amount Amount to withdraw
    function emergencyWithdraw(address to, uint256 amount)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(to != address(0), "Zero address");
        vamsToken.safeTransfer(to, amount);
    }

    /// @notice Pause reward accumulation and claiming
    function pause() external onlyRole(PAUSER_ROLE) { _pause(); }

    /// @notice Unpause reward accumulation and claiming
    function unpause() external onlyRole(PAUSER_ROLE) { _unpause(); }

    // ═══════════════════ Internal ═══════════════════

    function _getStakingBoostBps(address provider) internal view returns (uint256) {
        uint256 staked = _getStakedAmount(provider);
        if (staked >= TIER_DIAMOND_MIN) return TIER_DIAMOND_BOOST_BPS;
        if (staked >= TIER_GOLD_MIN) return TIER_GOLD_BOOST_BPS;
        if (staked >= TIER_SILVER_MIN) return TIER_SILVER_BOOST_BPS;
        if (staked >= TIER_BRONZE_MIN) return TIER_BRONZE_BOOST_BPS;
        return TIER_IRON_BOOST_BPS;
    }

    function _getStakedAmount(address provider) internal view returns (uint256) {
        if (stakingContract == address(0)) return 0;

        // Call staking contract to get provider's staked amount
        (bool success, bytes memory data) = stakingContract.staticcall(
            abi.encodeWithSignature("getStakedAmount(address)", provider)
        );
        if (!success || data.length < 32) return 0;
        return abi.decode(data, (uint256));
    }
}
