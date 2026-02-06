// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSValidatorManager
 * @notice Interface for the VAMS Validator Manager with Bounded DAO governance
 * @dev Manages deposits for Avalanche L1 validators with dynamic markup
 */
interface IVAMSValidatorManager {
    // ============ Structs ============
    
    struct LoyaltyTier {
        uint256 minStake;      // Minimum $VAMS staked
        uint256 minLockDays;   // Minimum days locked
        uint256 discountBps;   // Discount in basis points
    }
    
    struct ManagedSubnet {
        address owner;
        uint256 validatorCount;
        uint256 totalDeposited;
        uint256 registeredAt;
        bool active;
    }
    
    // ============ Events ============
    
    event Deposit(
        address indexed enterprise, 
        bytes32 indexed subnetId, 
        uint256 amount, 
        uint256 markupBps, 
        uint256 netAmount
    );
    event MarkupCollected(address indexed enterprise, uint256 markupAmount);
    event BoundsUpdated(uint256 minBps, uint256 maxBps);
    event BaseRateUpdated(uint256 oldRate, uint256 newRate);
    event DemandCurveUpdated(uint256[] thresholds, int256[] modifiers);
    event LoyaltyTiersUpdated(uint256 tierCount);
    event EmergencyFreezeActivated(uint256 frozenRate);
    event EmergencyFreezeDeactivated();
    event SubnetRegistered(bytes32 indexed subnetId, address indexed owner);
    event SubnetDeregistered(bytes32 indexed subnetId);
    event TargetCapacityUpdated(uint256 oldCapacity, uint256 newCapacity);
    
    // ============ Errors ============
    
    error InvalidBounds();
    error InvalidBaseRate();
    error InvalidThresholds();
    error AmountMismatch();
    error SubnetNotRegistered();
    error SubnetAlreadyExists();
    error NotSubnetOwner();
    error AlreadyFrozen();
    error NotFrozen();
    error ZeroAmount();
    error ZeroAddress();
    
    // ============ Core Functions ============
    
    /**
     * @notice Calculate effective markup for an enterprise
     * @param enterprise Address to calculate markup for
     * @return markupBps The markup in basis points
     */
    function calculateMarkup(address enterprise) external view returns (uint256 markupBps);
    
    /**
     * @notice Deposit funds for a managed L1 validator
     * @param subnetId The subnet identifier
     */
    function deposit(bytes32 subnetId) external payable;
    
    /**
     * @notice Register a new managed subnet
     * @param subnetId Unique identifier for the subnet
     * @param validatorCount Number of validators for this subnet
     */
    function registerSubnet(bytes32 subnetId, uint256 validatorCount) external;
    
    /**
     * @notice Deregister a managed subnet
     * @param subnetId The subnet to deregister
     */
    function deregisterSubnet(bytes32 subnetId) external;
    
    // ============ DAO Governance Functions ============
    
    /**
     * @notice Update markup bounds
     * @param minBps New minimum markup in basis points
     * @param maxBps New maximum markup in basis points
     */
    function updateBounds(uint256 minBps, uint256 maxBps) external;
    
    /**
     * @notice Update base rate
     * @param baseRateBps New base rate in basis points
     */
    function updateBaseRate(uint256 baseRateBps) external;
    
    /**
     * @notice Update demand curve
     * @param thresholds Utilization breakpoints in basis points
     * @param modifiers Corresponding bps modifiers
     */
    function updateDemandCurve(uint256[] calldata thresholds, int256[] calldata modifiers) external;
    
    /**
     * @notice Update loyalty tiers
     * @param tiers Array of loyalty tier configurations
     */
    function updateLoyaltyTiers(LoyaltyTier[] calldata tiers) external;
    
    /**
     * @notice Update target capacity
     * @param capacity New target capacity
     */
    function updateTargetCapacity(uint256 capacity) external;
    
    // ============ Emergency Functions ============
    
    /**
     * @notice Freeze to a fixed rate
     * @param fixedRate The rate to freeze to in basis points
     */
    function emergencyFreeze(uint256 fixedRate) external;
    
    /**
     * @notice Unfreeze and resume algorithmic pricing
     */
    function emergencyUnfreeze() external;
    
    // ============ View Functions ============
    
    function minMarkupBps() external view returns (uint256);
    function maxMarkupBps() external view returns (uint256);
    function baseRateBps() external view returns (uint256);
    function targetCapacity() external view returns (uint256);
    function activeManagedL1s() external view returns (uint256);
    function isFrozen() external view returns (bool);
    function frozenMarkupBps() external view returns (uint256);
    
    function getUtilization() external view returns (uint256 utilizationBps);
    function getDemandCurve() external view returns (uint256[] memory thresholds, int256[] memory modifiers);
    function getLoyaltyTiers() external view returns (LoyaltyTier[] memory);
    function getSubnet(bytes32 subnetId) external view returns (ManagedSubnet memory);
    function getDemandModifier() external view returns (int256);
    function getLoyaltyDiscount(address enterprise) external view returns (uint256);
}
