// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./interfaces/IVAMSValidatorManager.sol";
import "../staking/IVAMSStaking.sol";
import "../economic/IVAMSFeeCollector.sol";

/**
 * @title VAMSValidatorManager
 * @author VAMS Protocol
 * @notice Manages $VAMS ERC-20 deposits for VAMS L3 Validium validators on Polygon CDK
 * @dev DAO sets parameters (bounds, base rate, tiers), algorithm calculates per-deposit markup
 *
 * ## Bounded DAO Model
 * - DAO controls: min/max bounds, base rate, demand curve, loyalty tiers
 * - Algorithm calculates: per-deposit rate within DAO-set bounds
 * - Emergency: DAO can freeze to fixed rate
 *
 * ## Markup Formula
 * EffectiveMarkup = clamp(min, max, BaseRate + DemandModifier - LoyaltyDiscount)
 */
contract VAMSValidatorManager is
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard,
    UUPSUpgradeable,
    IVAMSValidatorManager
{
    using SafeERC20 for IERC20;

    // ============ Roles ============

    /// @notice Role for governance actions (parameter updates)
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");

    /// @notice Role for emergency actions (freeze/unfreeze)
    bytes32 public constant EMERGENCY_ROLE = keccak256("EMERGENCY_ROLE");

    /// @notice Role for contract upgrades
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    // ============ State: DAO-Controlled Parameters ============

    /// @notice Minimum markup in basis points (floor)
    uint256 public override minMarkupBps;

    /// @notice Maximum markup in basis points (ceiling)
    uint256 public override maxMarkupBps;

    /// @notice Base rate in basis points
    uint256 public override baseRateBps;

    /// @notice Target capacity for utilization calculation
    uint256 public override targetCapacity;

    /// @notice Demand curve thresholds (utilization breakpoints in bps)
    uint256[] private _demandThresholds;

    /// @notice Demand curve modifiers (bps adjustments per threshold)
    int256[] private _demandModifiers;

    /// @notice Loyalty tiers array
    LoyaltyTier[] private _loyaltyTiers;

    // ============ State: Emergency ============

    /// @notice Whether the contract is in emergency freeze mode
    bool public override isFrozen;

    /// @notice The frozen markup rate when in emergency mode
    uint256 public override frozenMarkupBps;

    // ============ State: Operational ============

    /// @notice Count of currently active managed L1s
    uint256 public override activeManagedL1s;

    /// @notice Mapping of subnet ID to managed subnet data
    mapping(bytes32 => ManagedSubnet) private _subnets;

    // ============ External Contracts ============

    /// @notice $VAMS ERC-20 token for deposits
    IERC20 public vamsToken;

    /// @notice Reference to VAMS staking contract for loyalty lookups
    IVAMSStaking public stakingContract;

    /// @notice Reference to VAMS fee collector for markup collection
    IVAMSFeeCollector public feeCollector;

    // ============ Constants ============

    /// @notice Basis points denominator
    uint256 public constant BPS_DENOMINATOR = 10000;

    /// @notice Absolute minimum markup (protocol cannot go below this)
    uint256 public constant ABSOLUTE_MIN_BPS = 50; // 0.5%

    /// @notice Absolute maximum markup (protocol cannot go above this)
    uint256 public constant ABSOLUTE_MAX_BPS = 1000; // 10%

    // ============ Constructor ============

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    // ============ Initializer ============

    /**
     * @notice Initialize the validator manager
     * @param _admin Admin address with all roles initially
     * @param _vamsToken Address of $VAMS ERC-20 token
     * @param _stakingContract Address of VAMS staking contract
     * @param _feeCollector Address of VAMS fee collector
     */
    function initialize(address _admin, address _vamsToken, address _stakingContract, address _feeCollector)
        external
        initializer
    {
        if (_admin == address(0)) revert ZeroAddress();
        if (_vamsToken == address(0)) revert ZeroAddress();
        if (_stakingContract == address(0)) revert ZeroAddress();
        if (_feeCollector == address(0)) revert ZeroAddress();

        __AccessControl_init();
        __Pausable_init();

        // AC02: Set DEFAULT_ADMIN_ROLE as the admin for all operational roles
        _setRoleAdmin(UPGRADER_ROLE, DEFAULT_ADMIN_ROLE);
        _setRoleAdmin(GOVERNANCE_ROLE, DEFAULT_ADMIN_ROLE);
        _setRoleAdmin(EMERGENCY_ROLE, DEFAULT_ADMIN_ROLE);

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(GOVERNANCE_ROLE, _admin);
        _grantRole(EMERGENCY_ROLE, _admin);
        _grantRole(UPGRADER_ROLE, _admin);

        vamsToken = IERC20(_vamsToken);
        stakingContract = IVAMSStaking(_stakingContract);
        feeCollector = IVAMSFeeCollector(_feeCollector);

        // Default DAO parameters
        minMarkupBps = 100; // 1%
        maxMarkupBps = 500; // 5%
        baseRateBps = 300; // 3%
        targetCapacity = 100; // 100 L1s

        // Default demand curve: [50%, 80%, 95%] → [-1%, 0%, +1%, +2%]
        _demandThresholds.push(5000); // 50%
        _demandThresholds.push(8000); // 80%
        _demandThresholds.push(9500); // 95%

        _demandModifiers.push(-100); // < 50%: -1%
        _demandModifiers.push(0); // 50-80%: 0%
        _demandModifiers.push(100); // 80-95%: +1%
        _demandModifiers.push(200); // > 95%: +2%

        // Default loyalty tiers
        _loyaltyTiers.push(
            LoyaltyTier({
                minStake: 10_000e18, // 10k VAMS
                minLockDays: 30,
                discountBps: 25 // 0.25%
            })
        );
        _loyaltyTiers.push(
            LoyaltyTier({
                minStake: 50_000e18, // 50k VAMS
                minLockDays: 60,
                discountBps: 50 // 0.5%
            })
        );
        _loyaltyTiers.push(
            LoyaltyTier({
                minStake: 100_000e18, // 100k VAMS
                minLockDays: 90,
                discountBps: 100 // 1%
            })
        );
    }

    // ============ Core Functions ============

    /// @inheritdoc IVAMSValidatorManager
    function calculateMarkup(address enterprise) public view override returns (uint256 markupBps) {
        // Emergency freeze overrides algorithm
        if (isFrozen) {
            return frozenMarkupBps;
        }

        int256 demandMod = getDemandModifier();
        uint256 loyaltyDiscount = getLoyaltyDiscount(enterprise);

        // Calculate: Base + Demand - Loyalty
        // forge-lint: disable-next-line(unsafe-typecast)
        int256 rawMarkup = int256(baseRateBps) + demandMod - int256(loyaltyDiscount);

        // Clamp to DAO-set [min, max]
        // forge-lint: disable-next-line(unsafe-typecast)
        if (rawMarkup < int256(minMarkupBps)) return minMarkupBps;
        // forge-lint: disable-next-line(unsafe-typecast)
        if (rawMarkup > int256(maxMarkupBps)) return maxMarkupBps;
        // forge-lint: disable-next-line(unsafe-typecast)
        return uint256(rawMarkup);
    }

    /// @inheritdoc IVAMSValidatorManager
    function deposit(bytes32 subnetId, uint256 amount) external override nonReentrant whenNotPaused {
        ManagedSubnet storage subnet = _subnets[subnetId];
        if (!subnet.active) revert SubnetNotRegistered();
        if (amount == 0) revert ZeroAmount();

        uint256 markupBps = calculateMarkup(msg.sender);
        uint256 markupAmount = (amount * markupBps) / BPS_DENOMINATOR;
        uint256 netAmount = amount - markupAmount;

        // Effects — update subnet stats first (CEI pattern)
        subnet.totalDeposited += netAmount;

        // Interactions — transfer $VAMS from depositor
        vamsToken.safeTransferFrom(msg.sender, address(this), amount);

        // Route markup to fee collector
        if (markupAmount > 0) {
            vamsToken.safeTransfer(address(feeCollector), markupAmount);
        }

        emit Deposit(msg.sender, subnetId, amount, markupBps, netAmount);
        emit MarkupCollected(msg.sender, markupAmount);
    }

    /// @inheritdoc IVAMSValidatorManager
    function registerSubnet(bytes32 subnetId, uint256 validatorCount) external override onlyRole(GOVERNANCE_ROLE) {
        if (_subnets[subnetId].active) revert SubnetAlreadyExists();

        _subnets[subnetId] = ManagedSubnet({
            owner: msg.sender,
            validatorCount: validatorCount,
            totalDeposited: 0,
            registeredAt: block.timestamp,
            active: true
        });

        activeManagedL1s += 1;
        emit SubnetRegistered(subnetId, msg.sender);
    }

    /// @inheritdoc IVAMSValidatorManager
    function deregisterSubnet(bytes32 subnetId) external override {
        ManagedSubnet storage subnet = _subnets[subnetId];
        if (!subnet.active) revert SubnetNotRegistered();
        if (subnet.owner != msg.sender && !hasRole(GOVERNANCE_ROLE, msg.sender)) {
            revert NotSubnetOwner();
        }

        subnet.active = false;
        activeManagedL1s -= 1;

        emit SubnetDeregistered(subnetId);
    }

    // ============ DAO Governance Functions ============

    /// @inheritdoc IVAMSValidatorManager
    function updateBounds(uint256 _minBps, uint256 _maxBps) external override onlyRole(GOVERNANCE_ROLE) {
        if (_minBps < ABSOLUTE_MIN_BPS || _maxBps > ABSOLUTE_MAX_BPS) revert InvalidBounds();
        if (_minBps >= _maxBps) revert InvalidBounds();

        minMarkupBps = _minBps;
        maxMarkupBps = _maxBps;

        // Ensure base rate is still valid
        if (baseRateBps < _minBps) baseRateBps = _minBps;
        if (baseRateBps > _maxBps) baseRateBps = _maxBps;

        emit BoundsUpdated(_minBps, _maxBps);
    }

    /// @inheritdoc IVAMSValidatorManager
    function updateBaseRate(uint256 _baseRateBps) external override onlyRole(GOVERNANCE_ROLE) {
        if (_baseRateBps < minMarkupBps || _baseRateBps > maxMarkupBps) revert InvalidBaseRate();

        uint256 oldRate = baseRateBps;
        baseRateBps = _baseRateBps;

        emit BaseRateUpdated(oldRate, _baseRateBps);
    }

    /// @inheritdoc IVAMSValidatorManager
    function updateDemandCurve(uint256[] calldata thresholds, int256[] calldata modifiers)
        external
        override
        onlyRole(GOVERNANCE_ROLE)
    {
        if (thresholds.length + 1 != modifiers.length) revert InvalidThresholds();

        // Validate thresholds are ascending
        for (uint256 i = 1; i < thresholds.length; i++) {
            if (thresholds[i] <= thresholds[i - 1]) revert InvalidThresholds();
        }

        delete _demandThresholds;
        delete _demandModifiers;

        for (uint256 i = 0; i < thresholds.length; i++) {
            _demandThresholds.push(thresholds[i]);
        }
        for (uint256 i = 0; i < modifiers.length; i++) {
            _demandModifiers.push(modifiers[i]);
        }

        emit DemandCurveUpdated(thresholds, modifiers);
    }

    /// @inheritdoc IVAMSValidatorManager
    function updateLoyaltyTiers(LoyaltyTier[] calldata tiers) external override onlyRole(GOVERNANCE_ROLE) {
        delete _loyaltyTiers;
        for (uint256 i = 0; i < tiers.length; i++) {
            _loyaltyTiers.push(tiers[i]);
        }

        emit LoyaltyTiersUpdated(tiers.length);
    }

    /// @inheritdoc IVAMSValidatorManager
    function updateTargetCapacity(uint256 _capacity) external override onlyRole(GOVERNANCE_ROLE) {
        uint256 oldCapacity = targetCapacity;
        targetCapacity = _capacity;
        emit TargetCapacityUpdated(oldCapacity, _capacity);
    }

    // ============ Emergency Functions ============

    /// @inheritdoc IVAMSValidatorManager
    function emergencyFreeze(uint256 _fixedRate) external override onlyRole(EMERGENCY_ROLE) {
        if (isFrozen) revert AlreadyFrozen();
        if (_fixedRate < minMarkupBps || _fixedRate > maxMarkupBps) revert InvalidBaseRate();

        isFrozen = true;
        frozenMarkupBps = _fixedRate;

        emit EmergencyFreezeActivated(_fixedRate);
    }

    /// @inheritdoc IVAMSValidatorManager
    function emergencyUnfreeze() external override onlyRole(GOVERNANCE_ROLE) {
        if (!isFrozen) revert NotFrozen();

        isFrozen = false;
        frozenMarkupBps = 0;

        emit EmergencyFreezeDeactivated();
    }

    /**
     * @notice Pause the contract
     */
    function pause() external onlyRole(EMERGENCY_ROLE) {
        _pause();
    }

    /**
     * @notice Unpause the contract
     */
    function unpause() external onlyRole(GOVERNANCE_ROLE) {
        _unpause();
    }

    // ============ View Functions ============

    /// @inheritdoc IVAMSValidatorManager
    function getUtilization() external view override returns (uint256 utilizationBps) {
        if (targetCapacity == 0) return 0;
        return (activeManagedL1s * BPS_DENOMINATOR) / targetCapacity;
    }

    /// @inheritdoc IVAMSValidatorManager
    function getDemandModifier() public view override returns (int256) {
        if (targetCapacity == 0) return 0;

        uint256 utilizationBps = (activeManagedL1s * BPS_DENOMINATOR) / targetCapacity;
        uint256 thresholdCount = _demandThresholds.length;

        // Walk through thresholds to find applicable modifier
        for (uint256 i = 0; i < thresholdCount; i++) {
            if (utilizationBps < _demandThresholds[i]) {
                return _demandModifiers[i];
            }
        }
        // Above all thresholds
        return _demandModifiers[_demandModifiers.length - 1];
    }

    /// @inheritdoc IVAMSValidatorManager
    function getLoyaltyDiscount(address enterprise) public view override returns (uint256) {
        IVAMSStaking.StakeInfo memory stakeInfo = stakingContract.getStakeInfo(enterprise);

        if (stakeInfo.amount == 0 || stakeInfo.stakedAt == 0) return 0;

        uint256 daysLocked = (block.timestamp - stakeInfo.stakedAt) / 1 days;

        // Check tiers from highest to lowest (sorted by minStake desc)
        for (uint256 i = _loyaltyTiers.length; i > 0; i--) {
            LoyaltyTier memory tier = _loyaltyTiers[i - 1];
            if (stakeInfo.amount >= tier.minStake && daysLocked >= tier.minLockDays) {
                return tier.discountBps;
            }
        }
        return 0;
    }

    /// @inheritdoc IVAMSValidatorManager
    function getDemandCurve() external view override returns (uint256[] memory, int256[] memory) {
        return (_demandThresholds, _demandModifiers);
    }

    /// @inheritdoc IVAMSValidatorManager
    function getLoyaltyTiers() external view override returns (LoyaltyTier[] memory) {
        return _loyaltyTiers;
    }

    /// @inheritdoc IVAMSValidatorManager
    function getSubnet(bytes32 subnetId) external view override returns (ManagedSubnet memory) {
        return _subnets[subnetId];
    }

    // ============ Admin Functions ============

    /**
     * @notice Update the $VAMS token reference
     * @param _vamsToken New $VAMS token address
     */
    function setVamsToken(address _vamsToken) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_vamsToken == address(0)) revert ZeroAddress();
        vamsToken = IERC20(_vamsToken);
    }

    /**
     * @notice Update staking contract reference
     * @param _stakingContract New staking contract address
     */
    function setStakingContract(address _stakingContract) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_stakingContract == address(0)) revert ZeroAddress();
        stakingContract = IVAMSStaking(_stakingContract);
    }

    /**
     * @notice Update fee collector reference
     * @param _feeCollector New fee collector address
     */
    function setFeeCollector(address _feeCollector) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_feeCollector == address(0)) revert ZeroAddress();
        feeCollector = IVAMSFeeCollector(_feeCollector);
    }

    // ============ Internal Functions ============

    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}

    // ============ Storage Gap ============

    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
