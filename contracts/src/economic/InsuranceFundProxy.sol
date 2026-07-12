// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title InsuranceFundProxy
 * @author VAMS Protocol
 * @notice Polygon-side proxy that accumulates insurance fund contributions
 *         and batches them to Cardano via the ICB-SDK bridge.
 *
 * Sources:
 *   - 10% of protocol fees from VAMSFeeCollector
 *   - 100% of slashed validator/keeper stakes
 *
 * The accumulated funds are bridged weekly to the Cardano VAMSInsuranceFund
 * (Plutus V3) which custodies the capital and allows DAO-voted claims.
 */
contract InsuranceFundProxy is 
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard
{
    using SafeERC20 for IERC20;

    // ============ Constants ============

    /// @notice Role for depositing fees/slashes
    bytes32 public constant DEPOSITOR_ROLE = keccak256("DEPOSITOR_ROLE");

    /// @notice Role for triggering bridge batches
    bytes32 public constant BRIDGE_OPERATOR_ROLE = keccak256("BRIDGE_OPERATOR_ROLE");

    /// @notice Role for emergency operations
    bytes32 public constant SENTINEL_ROLE = keccak256("SENTINEL_ROLE");

    // ============ State Variables ============

    /// @notice The $VAMS token
    IERC20 public vamsToken;

    /// @notice ICB bridge endpoint address
    address public bridgeEndpoint;

    /// @notice Total accumulated from fees
    uint256 public accumulatedFees;

    /// @notice Total accumulated from slashing
    uint256 public accumulatedSlashes;

    /// @notice Total bridged to Cardano historically
    uint256 public totalBridged;

    /// @notice Minimum batch size to bridge (prevents dust transactions)
    uint256 public minBatchSize;

    /// @notice Last bridge timestamp
    uint256 public lastBridgeTime;

    /// @notice Minimum interval between bridges (1 day default)
    uint256 public bridgeInterval;

    // ============ Events ============

    event FeeDeposited(address indexed from, uint256 amount);
    event SlashDeposited(address indexed from, uint256 amount);
    event BatchBridged(uint256 totalAmount, uint256 feesPortion, uint256 slashesPortion, uint256 timestamp);
    event BridgeEndpointUpdated(address oldEndpoint, address newEndpoint);
    event MinBatchSizeUpdated(uint256 oldSize, uint256 newSize);

    // ============ Errors ============

    error ZeroAddress();
    error ZeroAmount();
    error BatchTooSmall(uint256 available, uint256 minimum);
    error BridgeIntervalNotMet(uint256 nextBridgeTime);
    error BridgeEndpointNotSet();

    // ============ Initializer ============

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the InsuranceFundProxy
     * @param _admin Admin address
     * @param _vamsToken $VAMS token address
     * @param _bridgeEndpoint ICB bridge endpoint
     * @param _minBatchSize Minimum batch size to bridge
     */
    function initialize(
        address _admin,
        address _vamsToken,
        address _bridgeEndpoint,
        uint256 _minBatchSize
    ) external initializer {
        if (_admin == address(0) || _vamsToken == address(0)) revert ZeroAddress();

        __AccessControl_init();
        __Pausable_init();

        vamsToken = IERC20(_vamsToken);
        bridgeEndpoint = _bridgeEndpoint;
        minBatchSize = _minBatchSize;
        bridgeInterval = 1 days;

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(DEPOSITOR_ROLE, _admin);
        _grantRole(BRIDGE_OPERATOR_ROLE, _admin);
    }

    // ============ Deposit Functions ============

    /**
     * @notice Deposit protocol fees into the insurance fund proxy
     * @param amount Amount of $VAMS to deposit
     */
    function depositFees(uint256 amount) external onlyRole(DEPOSITOR_ROLE) whenNotPaused {
        if (amount == 0) revert ZeroAmount();

        vamsToken.safeTransferFrom(msg.sender, address(this), amount);
        accumulatedFees += amount;

        emit FeeDeposited(msg.sender, amount);
    }

    /**
     * @notice Deposit slashed stakes into the insurance fund proxy
     * @param amount Amount of $VAMS from slashing
     */
    function depositSlash(uint256 amount) external onlyRole(DEPOSITOR_ROLE) whenNotPaused {
        if (amount == 0) revert ZeroAmount();

        vamsToken.safeTransferFrom(msg.sender, address(this), amount);
        accumulatedSlashes += amount;

        emit SlashDeposited(msg.sender, amount);
    }

    // ============ Bridge Functions ============

    /**
     * @notice Bridge accumulated funds to Cardano InsuranceFund
     * @dev Called by bridge operator (keeper/bot) on weekly schedule
     */
    function bridgeBatch() external onlyRole(BRIDGE_OPERATOR_ROLE) nonReentrant whenNotPaused {
        if (bridgeEndpoint == address(0)) revert BridgeEndpointNotSet();

        uint256 nextBridgeTime = lastBridgeTime + bridgeInterval;
        if (block.timestamp < nextBridgeTime) {
            revert BridgeIntervalNotMet(nextBridgeTime);
        }

        uint256 totalAvailable = accumulatedFees + accumulatedSlashes;
        if (totalAvailable < minBatchSize) {
            revert BatchTooSmall(totalAvailable, minBatchSize);
        }

        uint256 feesPortion = accumulatedFees;
        uint256 slashesPortion = accumulatedSlashes;

        // Reset accumulators
        accumulatedFees = 0;
        accumulatedSlashes = 0;
        totalBridged += totalAvailable;
        lastBridgeTime = block.timestamp;

        // Transfer to ICB bridge endpoint for Cardano relay
        vamsToken.safeTransfer(bridgeEndpoint, totalAvailable);

        emit BatchBridged(totalAvailable, feesPortion, slashesPortion, block.timestamp);
    }

    // ============ Admin Functions ============

    function setBridgeEndpoint(address _bridgeEndpoint) external onlyRole(DEFAULT_ADMIN_ROLE) {
        emit BridgeEndpointUpdated(bridgeEndpoint, _bridgeEndpoint);
        bridgeEndpoint = _bridgeEndpoint;
    }

    function setMinBatchSize(uint256 _minBatchSize) external onlyRole(DEFAULT_ADMIN_ROLE) {
        emit MinBatchSizeUpdated(minBatchSize, _minBatchSize);
        minBatchSize = _minBatchSize;
    }

    function setBridgeInterval(uint256 _interval) external onlyRole(DEFAULT_ADMIN_ROLE) {
        bridgeInterval = _interval;
    }

    function pause() external onlyRole(SENTINEL_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ============ View Functions ============

    function totalAccumulated() external view returns (uint256) {
        return accumulatedFees + accumulatedSlashes;
    }

    // ============ Storage Gap ============

    uint256[50] private __gap;
}
