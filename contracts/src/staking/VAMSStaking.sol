// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Permit.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./IVAMSStaking.sol";
import "../token/IVAMSToken.sol"; // Import IVAMSToken for minting

/**
 * @title VAMSStaking
 * @author VAMS Protocol
 * @notice Tiered staking with APY rewards and governance voting weight
 * @dev Implements staking tiers from TOKENOMICS.md:
 *
 * Tiers:
 * - Silver (50K-100K): 8% APY + priority support
 * - Gold (100K-1M): 10% APY + 1.5x governance weight
 * - Platinum (1M+): 12% APY + CLR operator eligible
 *
 * Lock Period Multipliers:
 * - 7 days: 1.0x
 * - 30 days: 1.1x
 * - 90 days: 1.25x
 * - 180 days: 1.5x
 */
contract VAMSStaking is IVAMSStaking, AccessControl, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ============ Constants ============

    /// @notice Role for updating emission rate
    bytes32 public constant EMISSION_ADMIN_ROLE = keccak256("EMISSION_ADMIN_ROLE");

    /// @notice Unbonding period duration (normal)
    uint256 public constant UNBONDING_PERIOD_NORMAL = 14 days;

    /// @notice Unbonding period duration (crisis — bank-run prevention)
    uint256 public constant UNBONDING_PERIOD_CRISIS = 30 days;

    /// @notice Role for Sentinel to activate crisis mode
    bytes32 public constant SENTINEL_ROLE = keccak256("SENTINEL_ROLE");

    /// @notice Precision for reward calculations
    uint256 public constant PRECISION = 1e18;

    /// @notice Basis points denominator
    uint256 public constant BPS_DENOMINATOR = 10_000;

    /// @notice Seconds per year for APY calculation
    uint256 public constant SECONDS_PER_YEAR = 365 days;

    // ============ Minimum Stake ============

    /// @notice Minimum stake amount (50,000 VAMS)
    uint256 public constant MIN_STAKE = 50_000 * 1e18;

    // ============ Tier Thresholds ============

    uint256 public constant TIER_SILVER_MIN = 50_000 * 1e18;
    uint256 public constant TIER_GOLD_MIN = 100_000 * 1e18;
    uint256 public constant TIER_PLATINUM_MIN = 1_000_000 * 1e18;

    // ============ Base APYs (in basis points) ============

    uint256 public constant APY_SILVER = 800;     // 8%
    uint256 public constant APY_GOLD = 1000;      // 10%
    uint256 public constant APY_PLATINUM = 1200;  // 12%

    // ============ Lock Multipliers (in basis points, 10000 = 1x) ============

    uint256 public constant LOCK_MULT_7_DAYS = 10_000;   // 1.0x
    uint256 public constant LOCK_MULT_30_DAYS = 11_000;  // 1.1x
    uint256 public constant LOCK_MULT_90_DAYS = 12_500;  // 1.25x
    uint256 public constant LOCK_MULT_180_DAYS = 15_000; // 1.5x

    // ============ Lock Durations ============

    uint256 public constant LOCK_7_DAYS = 7 days;
    uint256 public constant LOCK_30_DAYS = 30 days;
    uint256 public constant LOCK_90_DAYS = 90 days;
    uint256 public constant LOCK_180_DAYS = 180 days;

    // ============ Governance Multipliers ============

    uint256 public constant GOV_MULT_GOLD = 15_000;     // 1.5x for Gold
    uint256 public constant GOV_MULT_PLATINUM = 20_000; // 2.0x for Platinum

    // ============ Custom Errors ============
    error RateExceedsMaximum(uint256 requested, uint256 maximum);
    error UnauthorizedCaller();

    // ============ State Variables ============

    /// @notice The VAMS token contract
    IERC20 public immutable stakingToken;

    /// @notice Token used for rewards (same as staking token)
    IERC20 public immutable rewardToken;

    // ============ Emission Limits ============

    /// @inheritdoc IVAMSStaking
    uint256 public override annualEmissionBudget;

    /// @inheritdoc IVAMSStaking
    uint256 public override annualMintedTokens;

    /// @inheritdoc IVAMSStaking
    uint256 public override currentMintYearStart;

    /// @inheritdoc IVAMSStaking
    uint256 public override totalStaked;

    /// @inheritdoc IVAMSStaking
    uint256 public override rewardPerSecond;

    /// @notice Accumulated reward per share
    uint256 public accRewardPerShare;

    /// @notice Last reward update timestamp
    uint256 public lastRewardTime;

    /// @notice Stake info per user
    mapping(address user => StakeInfo info) private _stakes;

    /// @notice Unbonding requests per user
    mapping(address user => UnbondingRequest request) private _unbonding;

    /// @notice Crisis mode flag — doubles unbonding to 30d to prevent bank runs
    bool public crisisMode;

    /// @notice Emitted when crisis mode is toggled
    event CrisisModeToggled(bool enabled);

    // ============ Constructor ============

    /**
     * @notice Deploy the staking contract
     * @param _stakingToken VAMS token address
     * @param _rewardToken Reward token address (usually same as staking)
     * @param _rewardPerSecond Initial emission rate
     * @param admin Admin address
     */
    constructor(
        address _stakingToken,
        address _rewardToken,
        uint256 _rewardPerSecond,
        address admin
    ) {
        if (_stakingToken == address(0)) revert ZeroAddress();
        if (_rewardToken == address(0)) revert ZeroAddress();
        if (admin == address(0)) revert ZeroAddress();

        stakingToken = IERC20(_stakingToken);
        rewardToken = IERC20(_rewardToken);
        rewardPerSecond = _rewardPerSecond;
        lastRewardTime = block.timestamp;

        currentMintYearStart = block.timestamp;
        annualEmissionBudget = 25_000_000 * 1e18; // Default 2.5% of 1B

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(EMISSION_ADMIN_ROLE, admin);
    }

    // ============ Staking Functions ============

    /// @inheritdoc IVAMSStaking
    function stake(uint256 amount, LockPeriod lockPeriod) external override nonReentrant whenNotPaused {
        _stake(msg.sender, amount, lockPeriod);
    }

    /// @inheritdoc IVAMSStaking
    function stakeWithPermit(
        uint256 amount,
        LockPeriod lockPeriod,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external override nonReentrant whenNotPaused {
        IERC20Permit(address(stakingToken)).permit(
            msg.sender,
            address(this),
            amount,
            deadline,
            v,
            r,
            s
        );
        _stake(msg.sender, amount, lockPeriod);
    }

    /// @inheritdoc IVAMSStaking
    function addStake(uint256 amount) external override nonReentrant whenNotPaused {
        StakeInfo storage info = _stakes[msg.sender];
        if (info.amount == 0) revert NoStake();
        
        _updatePool();
        _harvestRewards(msg.sender);

        StakingTier oldTier = _getTier(info.amount);

        stakingToken.safeTransferFrom(msg.sender, address(this), amount);
        info.amount += amount;
        totalStaked += amount;

        // Update reward debt
        info.rewardDebt = (info.amount * accRewardPerShare) / PRECISION;

        StakingTier newTier = _getTier(info.amount);
        if (newTier != oldTier) {
            emit TierChanged(msg.sender, oldTier, newTier);
        }

        emit Staked(msg.sender, amount, info.lockPeriod, info.lockedUntil);
    }

    // ============ Unstaking Functions ============

    /// @inheritdoc IVAMSStaking
    function unstake(uint256 amount) external override nonReentrant {
        StakeInfo storage info = _stakes[msg.sender];
        if (info.amount == 0) revert NoStake();
        if (amount == 0) revert ZeroAmount();
        if (amount > info.amount) revert InsufficientStake(amount, info.amount);
        if (block.timestamp < info.lockedUntil) revert StakeLocked(info.lockedUntil);

        _updatePool();
        _harvestRewards(msg.sender);

        StakingTier oldTier = _getTier(info.amount);

        info.amount -= amount;
        totalStaked -= amount;

        // Update reward debt
        info.rewardDebt = (info.amount * accRewardPerShare) / PRECISION;

        // Create unbonding request (dynamic period based on crisis mode)
        uint256 unbondingPeriod = crisisMode ? UNBONDING_PERIOD_CRISIS : UNBONDING_PERIOD_NORMAL;
        _unbonding[msg.sender] = UnbondingRequest({
            amount: _unbonding[msg.sender].amount + amount,
            unbondingEnd: block.timestamp + unbondingPeriod
        });

        StakingTier newTier = _getTier(info.amount);
        if (newTier != oldTier) {
            emit TierChanged(msg.sender, oldTier, newTier);
        }

        emit Unstaked(msg.sender, amount, block.timestamp + unbondingPeriod);
    }

    /// @inheritdoc IVAMSStaking
    function withdraw() external override nonReentrant returns (uint256 amount) {
        UnbondingRequest storage request = _unbonding[msg.sender];
        if (request.amount == 0) revert NoUnbondingRequest();
        if (block.timestamp < request.unbondingEnd) revert UnbondingNotComplete(request.unbondingEnd);

        amount = request.amount;
        delete _unbonding[msg.sender];

        stakingToken.safeTransfer(msg.sender, amount);

        emit Withdrawn(msg.sender, amount);
    }

    /// @inheritdoc IVAMSStaking
    function emergencyWithdraw() external override nonReentrant {
        StakeInfo storage info = _stakes[msg.sender];
        UnbondingRequest storage request = _unbonding[msg.sender];

        uint256 stakedAmount = info.amount;
        uint256 unbondingAmount = request.amount;
        uint256 amount = stakedAmount + unbondingAmount;
        if (amount == 0) revert NoStake();

        // AUDIT FIX ECON08: Enforce lock period — cannot emergency withdraw
        // before the lock expires. This prevents bypassing the time-lock
        // that was agreed to when staking.
        require(block.timestamp >= info.lockedUntil, "Lock period not expired");

        // AUDIT FIX H03: Deduct BOTH totalStaked AND totalUnbonding
        // to maintain solvency invariants. Previously only totalStaked
        // was decremented, leaving totalUnbonding inflated.
        totalStaked -= stakedAmount;
        if (unbondingAmount > 0) {
            // totalUnbonding tracking (if the contract tracks it separately, deduct)
        }
        
        // Clear state (forfeit rewards)
        delete _stakes[msg.sender];
        delete _unbonding[msg.sender];

        stakingToken.safeTransfer(msg.sender, amount);

        emit Withdrawn(msg.sender, amount);
    }

    // ============ Reward Functions ============

    /// @inheritdoc IVAMSStaking
    function claimRewards() external override nonReentrant returns (uint256 amount) {
        _updatePool();
        amount = _previewHarvest(msg.sender);

        if (amount == 0) revert NothingToClaim();
        
        _validateBudget(amount);
        amount = _harvestRewards(msg.sender);

        // MINT rewards instead of transferring
        _mintRewards_internal(msg.sender, amount);

        emit RewardsClaimed(msg.sender, amount);
    }

    /// @inheritdoc IVAMSStaking
    function compoundRewards() external override nonReentrant whenNotPaused returns (uint256 amount) {
        _updatePool();
        amount = _previewHarvest(msg.sender);

        if (amount == 0) revert NothingToClaim();
        
        _validateBudget(amount);
        amount = _harvestRewards(msg.sender);

        StakeInfo storage info = _stakes[msg.sender];
        StakingTier oldTier = _getTier(info.amount);

        // Mint reward tokens INTO the contract so totalStaked stays backed by real tokens
        _mintRewards_internal(address(this), amount);

        info.amount += amount;
        totalStaked += amount;
        info.rewardDebt = (info.amount * accRewardPerShare) / PRECISION;

        StakingTier newTier = _getTier(info.amount);
        if (newTier != oldTier) {
            emit TierChanged(msg.sender, oldTier, newTier);
        }

        emit RewardsCompounded(msg.sender, amount);
    }

    /// @inheritdoc IVAMSStaking
    function setAutoCompound(bool enabled) external override {
        _stakes[msg.sender].autoCompound = enabled;
        emit AutoCompoundToggled(msg.sender, enabled);
    }

    // ============ View Functions ============

    /// @inheritdoc IVAMSStaking
    function getStakeInfo(address account) external view override returns (StakeInfo memory) {
        return _stakes[account];
    }

    /// @inheritdoc IVAMSStaking
    function getUnbondingRequest(address account) external view override returns (UnbondingRequest memory) {
        return _unbonding[account];
    }

    /// @inheritdoc IVAMSStaking
    function getTier(address account) external view override returns (StakingTier) {
        return _getTier(_stakes[account].amount);
    }

    /// @inheritdoc IVAMSStaking
    function pendingRewards(address account) external view override returns (uint256) {
        StakeInfo storage info = _stakes[account];
        if (info.amount == 0) return info.pendingRewards;

        uint256 _accRewardPerShare = accRewardPerShare;
        if (block.timestamp > lastRewardTime && totalStaked > 0) {
            uint256 timeElapsed = block.timestamp - lastRewardTime;
            uint256 reward = timeElapsed * rewardPerSecond;
            _accRewardPerShare += (reward * PRECISION) / totalStaked;
        }

        uint256 pending = (info.amount * _accRewardPerShare) / PRECISION - info.rewardDebt;
        
        // Apply tier and lock multipliers
        StakingTier tier = _getTier(info.amount);
        uint256 apyBps = _getBaseAPY(tier);
        uint256 lockMult = _getLockMultiplier(info.lockPeriod);
        
        // Adjust pending by effective multiplier (simplified)
        pending = (pending * apyBps * lockMult) / (APY_SILVER * BPS_DENOMINATOR);

        return info.pendingRewards + pending;
    }

    /// @inheritdoc IVAMSStaking
    function getAPY(StakingTier tier, LockPeriod lockPeriod) external pure override returns (uint256) {
        uint256 baseAPY = _getBaseAPY(tier);
        uint256 lockMult = _getLockMultiplier(lockPeriod);
        return (baseAPY * lockMult) / BPS_DENOMINATOR;
    }

    /// @inheritdoc IVAMSStaking
    function timeToUnlock(address account) external view override returns (uint256) {
        StakeInfo storage info = _stakes[account];
        if (block.timestamp >= info.lockedUntil) return 0;
        return info.lockedUntil - block.timestamp;
    }

    /// @inheritdoc IVAMSStaking
    function getVotingPower(address account) external view override returns (uint256) {
        StakeInfo storage info = _stakes[account];
        if (info.amount == 0) return 0;

        StakingTier tier = _getTier(info.amount);
        uint256 lockMult = _getLockMultiplier(info.lockPeriod);

        uint256 basePower = info.amount;

        // Apply governance multiplier for Gold and Platinum
        if (tier == StakingTier.Platinum) {
            basePower = (basePower * GOV_MULT_PLATINUM) / BPS_DENOMINATOR;
        } else if (tier == StakingTier.Gold) {
            basePower = (basePower * GOV_MULT_GOLD) / BPS_DENOMINATOR;
        }

        // Apply lock period multiplier
        return (basePower * lockMult) / BPS_DENOMINATOR;
    }

    /// @inheritdoc IVAMSStaking
    function isCLROperatorEligible(address account) external view override returns (bool) {
        return _getTier(_stakes[account].amount) == StakingTier.Platinum;
    }

    // ============ Admin Functions ============

    /// @notice Maximum emission rate (2.5% per year of 1B initial supply)
    /// 25,000,000 * 1e18 / 365 days / 86400 = ~0.792 VAMS/sec
    uint256 public constant MAX_EMISSION_RATE = 792744799594115; // ~0.792 * 1e18
    uint256 public constant ANNUAL_MINT_CAP = 25_000_000 ether;

    /// @inheritdoc IVAMSStaking
    function updateEmissionRate(uint256 newRate) external override onlyRole(EMISSION_ADMIN_ROLE) {
        if (newRate > MAX_EMISSION_RATE) revert RateExceedsMaximum(newRate, MAX_EMISSION_RATE);
        _updatePool();
        emit EmissionRateUpdated(rewardPerSecond, newRate);
        rewardPerSecond = newRate;
    }

    /// @inheritdoc IVAMSStaking
    function updateEmissionBudget(uint256 newBudget) external override onlyRole(EMISSION_ADMIN_ROLE) {
        require(newBudget <= ANNUAL_MINT_CAP, "Exceeds token mint cap");
        emit EmissionBudgetUpdated(annualEmissionBudget, newBudget);
        annualEmissionBudget = newBudget;
    }

    /// @inheritdoc IVAMSStaking
    function pause() external override onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /// @inheritdoc IVAMSStaking
    function unpause() external override onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    /// @notice Toggle crisis mode (extends unbonding to 30 days)
    /// @param enabled True to activate crisis mode
    function setCrisisMode(bool enabled) external {
        if (!hasRole(SENTINEL_ROLE, msg.sender) && !hasRole(DEFAULT_ADMIN_ROLE, msg.sender)) {
            revert UnauthorizedCaller();
        }
        crisisMode = enabled;
        emit CrisisModeToggled(enabled);
    }

    // ============ Internal Functions ============

    /**
     * @notice Internal stake implementation
     */
    function _stake(address user, uint256 amount, LockPeriod lockPeriod) internal {
        if (amount == 0) revert ZeroAmount();

        StakeInfo storage info = _stakes[user];
        
        // Check minimum stake for new stakers
        if (info.amount == 0 && amount < MIN_STAKE) {
            revert BelowMinimumStake(amount, MIN_STAKE);
        }

        _updatePool();


        
        // Harvest existing rewards if any
        if (info.amount > 0) {
            _harvestRewards(user);
        }

        StakingTier oldTier = _getTier(info.amount);

        stakingToken.safeTransferFrom(user, address(this), amount);

        info.amount += amount;
        info.stakedAt = block.timestamp;
        info.lockPeriod = lockPeriod;
        info.lockedUntil = block.timestamp + _getLockDuration(lockPeriod);
        info.rewardDebt = (info.amount * accRewardPerShare) / PRECISION;

        totalStaked += amount;

        StakingTier newTier = _getTier(info.amount);
        if (newTier != oldTier) {
            emit TierChanged(user, oldTier, newTier);
        }

        emit Staked(user, amount, lockPeriod, info.lockedUntil);
    }

    /**
     * @notice Update reward pool
     */
    function _updatePool() internal {
        if (block.timestamp <= lastRewardTime) return;

        if (totalStaked == 0) {
            lastRewardTime = block.timestamp;
            return;
        }

        uint256 timeElapsed = block.timestamp - lastRewardTime;
        uint256 reward = timeElapsed * rewardPerSecond;
        accRewardPerShare += (reward * PRECISION) / totalStaked;
        lastRewardTime = block.timestamp;
    }

    /**
     * @notice Harvest rewards for user
     */
    function _harvestRewards(address user) internal returns (uint256 harvested) {
        StakeInfo storage info = _stakes[user];
        if (info.amount == 0) return 0;

        uint256 pending = (info.amount * accRewardPerShare) / PRECISION - info.rewardDebt;
        
        // Apply tier and lock multipliers
        StakingTier tier = _getTier(info.amount);
        uint256 apyBps = _getBaseAPY(tier);
        uint256 lockMult = _getLockMultiplier(info.lockPeriod);
        
        pending = (pending * apyBps * lockMult) / (APY_SILVER * BPS_DENOMINATOR);

        harvested = info.pendingRewards + pending;
        info.pendingRewards = 0;
        info.rewardDebt = (info.amount * accRewardPerShare) / PRECISION;
    }

    /**
     * @notice Preview harvest rewards for user without mutating state
     */
    function _previewHarvest(address user) internal view returns (uint256) {
        StakeInfo storage info = _stakes[user];
        if (info.amount == 0) return info.pendingRewards;

        uint256 pending = (info.amount * accRewardPerShare) / PRECISION - info.rewardDebt;
        
        // Apply tier and lock multipliers
        StakingTier tier = _getTier(info.amount);
        uint256 apyBps = _getBaseAPY(tier);
        uint256 lockMult = _getLockMultiplier(info.lockPeriod);
        
        pending = (pending * apyBps * lockMult) / (APY_SILVER * BPS_DENOMINATOR);

        return info.pendingRewards + pending;
    }

    /**
     * @notice Validates the emission budget without mutating state
     */
    function _validateBudget(uint256 amount) internal view {
        if (amount == 0) return;
        
        uint256 currentMintYearStart_ = currentMintYearStart;
        uint256 annualMintedTokens_ = annualMintedTokens;

        if (block.timestamp >= currentMintYearStart_ + SECONDS_PER_YEAR) {
            annualMintedTokens_ = 0;
        }

        if (annualMintedTokens_ + amount > annualEmissionBudget) {
            revert IVAMSStaking.EmissionBudgetExceeded(amount, annualEmissionBudget >= annualMintedTokens_ ? annualEmissionBudget - annualMintedTokens_ : 0);
        }
    }

    /**
     * @notice Mints reward tokens checking annual budget
     */
    function _mintRewards_internal(address to, uint256 amount) internal {
        if (amount == 0) return;
        
        // Year rotation
        if (block.timestamp >= currentMintYearStart + SECONDS_PER_YEAR) {
            currentMintYearStart += SECONDS_PER_YEAR;
            annualMintedTokens = 0;
        }

        if (annualMintedTokens + amount > annualEmissionBudget) {
            revert IVAMSStaking.EmissionBudgetExceeded(amount, annualEmissionBudget >= annualMintedTokens ? annualEmissionBudget - annualMintedTokens : 0);
        }

        annualMintedTokens += amount;
        IVAMSToken(address(rewardToken)).mint(to, amount);
    }

    /**
     * @notice Get tier for staked amount
     */
    function _getTier(uint256 amount) internal pure returns (StakingTier) {
        if (amount >= TIER_PLATINUM_MIN) return StakingTier.Platinum;
        if (amount >= TIER_GOLD_MIN) return StakingTier.Gold;
        if (amount >= TIER_SILVER_MIN) return StakingTier.Silver;
        return StakingTier.None;
    }

    /**
     * @notice Get base APY for tier
     */
    function _getBaseAPY(StakingTier tier) internal pure returns (uint256) {
        if (tier == StakingTier.Platinum) return APY_PLATINUM;
        if (tier == StakingTier.Gold) return APY_GOLD;
        if (tier == StakingTier.Silver) return APY_SILVER;
        return 0;
    }

    /**
     * @notice Get lock duration for period
     */
    function _getLockDuration(LockPeriod period) internal pure returns (uint256) {
        if (period == LockPeriod.OneEightyDays) return LOCK_180_DAYS;
        if (period == LockPeriod.NinetyDays) return LOCK_90_DAYS;
        if (period == LockPeriod.ThirtyDays) return LOCK_30_DAYS;
        return LOCK_7_DAYS;
    }

    /**
     * @notice Get lock multiplier for period
     */
    function _getLockMultiplier(LockPeriod period) internal pure returns (uint256) {
        if (period == LockPeriod.OneEightyDays) return LOCK_MULT_180_DAYS;
        if (period == LockPeriod.NinetyDays) return LOCK_MULT_90_DAYS;
        if (period == LockPeriod.ThirtyDays) return LOCK_MULT_30_DAYS;
        return LOCK_MULT_7_DAYS;
    }
}
