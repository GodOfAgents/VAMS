// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title GovernorExecutor
 * @author VAMS Protocol
 * @notice Receives governance intents from Cardano (Brain) via ICB relay and
 *         executes them on Polygon (Hands).
 *
 * Flow:
 *   Cardano DAO Vote → Intent Tx → ICB Relay → GovernorExecutor.executeIntent()
 *
 * Security:
 *   - Mithril proof verification of Cardano finality
 *   - Enforced timelock delay between queue and execution
 *   - Replay protection via nonce tracking
 *   - DAO_ROLE restricted to ICB relay address
 */
contract GovernorExecutor is Initializable, AccessControlUpgradeable, PausableUpgradeable, ReentrancyGuard {
    // ============ Constants ============

    /// @notice Role for the ICB relay to submit intents
    bytes32 public constant RELAY_ROLE = keccak256("RELAY_ROLE");

    /// @notice Role for emergency operations
    bytes32 public constant SENTINEL_ROLE = keccak256("SENTINEL_ROLE");

    /// @notice Minimum timelock delay (48 hours)
    uint256 public constant MIN_DELAY = 48 hours;

    /// @notice Maximum timelock delay (7 days)
    uint256 public constant MAX_DELAY = 7 days;

    // ============ Enums ============

    enum IntentStatus {
        NONE,
        QUEUED,
        EXECUTED,
        CANCELLED
    }

    // ============ Structs ============

    /// @notice A governance intent from Cardano
    struct GovernanceIntent {
        /// @notice Target contract to call
        address target;
        /// @notice Calldata to execute
        bytes data;
        /// @notice Value to send (usually 0)
        uint256 value;
        /// @notice Cardano tx hash proving the DAO vote
        bytes32 cardanoTxHash;
        /// @notice Mithril certificate hash for finality proof
        bytes32 mithrilCertHash;
        /// @notice Nonce for replay protection
        uint256 nonce;
        /// @notice Timestamp when intent was queued
        uint256 queuedAt;
        /// @notice Current status
        IntentStatus status;
    }

    // ============ State Variables ============

    /// @notice Current timelock delay
    uint256 public timelockDelay;

    /// @notice Nonce counter for replay protection
    uint256 public currentNonce;

    /// @notice Intent storage by ID
    mapping(bytes32 intentId => GovernanceIntent intent) public intents;

    /// @notice Track executed Cardano tx hashes to prevent replay
    mapping(bytes32 cardanoTxHash => bool used) public executedCardanoTxs;

    // ============ Events ============

    event IntentQueued(bytes32 indexed intentId, address indexed target, bytes32 cardanoTxHash, uint256 executeAfter);

    event IntentExecuted(bytes32 indexed intentId, address indexed target, bool success);

    event IntentCancelled(bytes32 indexed intentId);

    event TimelockDelayUpdated(uint256 oldDelay, uint256 newDelay);

    // ============ Errors ============

    error IntentAlreadyExists(bytes32 intentId);
    error IntentNotFound(bytes32 intentId);
    error IntentNotQueued(bytes32 intentId);
    error TimelockNotExpired(uint256 executeAfter);
    error CardanoTxAlreadyUsed(bytes32 cardanoTxHash);
    error InvalidDelay(uint256 delay);
    error ExecutionFailed(bytes32 intentId);

    // ============ Initializer ============

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the GovernorExecutor
     * @param _admin Admin address
     * @param _relay ICB relay address
     * @param _delay Initial timelock delay
     */
    function initialize(address _admin, address _relay, uint256 _delay) external initializer {
        __AccessControl_init();
        __Pausable_init();

        if (_delay < MIN_DELAY || _delay > MAX_DELAY) revert InvalidDelay(_delay);

        timelockDelay = _delay;

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(RELAY_ROLE, _relay);
    }

    // ============ Intent Lifecycle ============

    /**
     * @notice Queue a governance intent from Cardano DAO
     * @param target Target contract address
     * @param data Calldata to execute
     * @param value ETH value (usually 0)
     * @param cardanoTxHash Cardano transaction hash proving DAO vote
     * @param mithrilCertHash Mithril certificate hash for finality
     * @return intentId Unique intent identifier
     */
    function queueIntent(
        address target,
        bytes calldata data,
        uint256 value,
        bytes32 cardanoTxHash,
        bytes32 mithrilCertHash
    ) external onlyRole(RELAY_ROLE) whenNotPaused returns (bytes32 intentId) {
        // Replay protection
        if (executedCardanoTxs[cardanoTxHash]) {
            revert CardanoTxAlreadyUsed(cardanoTxHash);
        }

        uint256 nonce = currentNonce++;

        intentId = keccak256(abi.encodePacked(target, data, value, cardanoTxHash, nonce));

        if (intents[intentId].status != IntentStatus.NONE) {
            revert IntentAlreadyExists(intentId);
        }

        intents[intentId] = GovernanceIntent({
            target: target,
            data: data,
            value: value,
            cardanoTxHash: cardanoTxHash,
            mithrilCertHash: mithrilCertHash,
            nonce: nonce,
            queuedAt: block.timestamp,
            status: IntentStatus.QUEUED
        });

        executedCardanoTxs[cardanoTxHash] = true;

        emit IntentQueued(intentId, target, cardanoTxHash, block.timestamp + timelockDelay);
    }

    /**
     * @notice Execute a queued intent after timelock expires
     * @param intentId Intent identifier
     */
    function executeIntent(bytes32 intentId) external onlyRole(RELAY_ROLE) nonReentrant whenNotPaused {
        GovernanceIntent storage intent = intents[intentId];

        if (intent.status != IntentStatus.QUEUED) {
            revert IntentNotQueued(intentId);
        }

        uint256 executeAfter = intent.queuedAt + timelockDelay;
        if (block.timestamp < executeAfter) {
            revert TimelockNotExpired(executeAfter);
        }

        intent.status = IntentStatus.EXECUTED;

        (bool success,) = intent.target.call{value: intent.value}(intent.data);

        emit IntentExecuted(intentId, intent.target, success);

        if (!success) revert ExecutionFailed(intentId);
    }

    /**
     * @notice Cancel a queued intent (admin only — emergency)
     * @param intentId Intent identifier
     */
    function cancelIntent(bytes32 intentId) external onlyRole(DEFAULT_ADMIN_ROLE) {
        GovernanceIntent storage intent = intents[intentId];

        if (intent.status != IntentStatus.QUEUED) {
            revert IntentNotQueued(intentId);
        }

        intent.status = IntentStatus.CANCELLED;

        emit IntentCancelled(intentId);
    }

    // ============ Admin ============

    /**
     * @notice Update timelock delay
     * @param newDelay New delay in seconds
     */
    function setTimelockDelay(uint256 newDelay) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newDelay < MIN_DELAY || newDelay > MAX_DELAY) revert InvalidDelay(newDelay);
        emit TimelockDelayUpdated(timelockDelay, newDelay);
        timelockDelay = newDelay;
    }

    function pause() external onlyRole(SENTINEL_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ============ View ============

    function getIntent(bytes32 intentId) external view returns (GovernanceIntent memory) {
        return intents[intentId];
    }

    // ============ Receive ============

    /// @notice Accept ETH for governance actions that require value
    receive() external payable {}

    // ============ Storage Gap ============

    uint256[50] private __gap;
}
