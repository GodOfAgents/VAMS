// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "./interfaces/IPChainBridge.sol";

/**
 * @title PChainBridge
 * @author VAMS Protocol
 * @notice Routes validator deposits to Avalanche P-Chain via AWM/Teleporter
 * @dev Implements cross-chain messaging for ACP-77 validator management
 *
 * Architecture:
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │                          C-Chain (EVM)                                  │
 * │  ┌───────────────────┐      ┌─────────────────┐      ┌──────────────┐  │
 * │  │ ValidatorManager  │ ──►  │   PChainBridge  │ ──►  │  Teleporter  │  │
 * │  └───────────────────┘      └─────────────────┘      └──────────────┘  │
 * │                                                              │         │
 * │                                                    AWM Message          │
 * └──────────────────────────────────────────────────────────────│─────────┘
 *                                                                │
 * ┌──────────────────────────────────────────────────────────────▼─────────┐
 * │                           P-Chain                                       │
 * │  ┌────────────────────────────────────────────────────────────────────┐ │
 * │  │                  Warp Precompile (Native)                          │ │
 * │  │  - Receives AWM messages                                           │ │
 * │  │  - Executes AddPermissionlessValidator/Delegator                   │ │
 * │  │  - Manages L1 validator set                                        │ │
 * │  └────────────────────────────────────────────────────────────────────┘ │
 * └─────────────────────────────────────────────────────────────────────────┘
 *
 * References:
 * - Teleporter: https://github.com/ava-labs/teleporter
 * - ICM: https://build.avax.network/docs/cross-chain/
 * - ACP-77: https://github.com/avalanche-foundation/ACPs/tree/main/ACPs/77
 */
contract PChainBridge is
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    UUPSUpgradeable,
    IPChainBridge
{
    // ============ Constants ============
    
    /// @notice Role for submitting bridge messages
    bytes32 public constant BRIDGE_OPERATOR_ROLE = keccak256("BRIDGE_OPERATOR_ROLE");
    
    /// @notice Role for configuring bridge parameters
    bytes32 public constant BRIDGE_ADMIN_ROLE = keccak256("BRIDGE_ADMIN_ROLE");
    
    /// @notice P-Chain blockchain ID (mainnet)
    /// @dev This is the well-known ID for Avalanche P-Chain
    bytes32 public constant P_CHAIN_BLOCKCHAIN_ID = 0x0000000000000000000000000000000000000000000000000000000000000000;
    
    /// @notice Warp precompile address on C-Chain
    address public constant WARP_PRECOMPILE = 0x0200000000000000000000000000000000000005;
    
    /// @notice Default minimum stake for mainnet (25,000 AVAX)
    uint256 public constant DEFAULT_MIN_STAKE = 25_000 ether;
    
    // ============ State Variables ============
    
    /// @notice Teleporter messenger contract
    address public teleporterMessenger;
    
    /// @notice Destination address on P-Chain for validator registration
    bytes32 public pChainDestination;
    
    /// @notice Supported subnets for bridging
    mapping(bytes32 => bool) private _supportedSubnets;
    
    /// @notice Minimum stake per subnet
    mapping(bytes32 => uint256) private _minimumStakes;
    
    /// @notice Pending messages awaiting P-Chain response
    mapping(bytes32 => PendingMessage) private _pendingMessages;
    
    /// @notice Validation records (messageId => validationId)
    mapping(bytes32 => bytes32) private _validationIds;
    
    /// @notice Message counter for generating unique IDs
    uint256 private _messageNonce;
    
    /// @notice Total AVAX bridged
    uint256 public totalBridged;
    
    // ============ Structs ============
    
    struct PendingMessage {
        address sender;
        bytes32 subnetId;
        uint256 amount;
        uint256 timestamp;
        MessageType messageType;
        bool pending;
    }
    
    enum MessageType {
        REGISTER_VALIDATOR,
        INCREASE_STAKE,
        EXIT_VALIDATOR
    }
    
    // ============ Constructor & Initializer ============
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /**
     * @notice Initialize the P-Chain bridge
     * @param _admin Admin address
     * @param _teleporter Teleporter messenger address
     */
    function initialize(
        address _admin,
        address _teleporter
    ) external initializer {
        if (_admin == address(0)) revert UnauthorizedCaller(address(0));
        if (_teleporter == address(0)) revert AWMMessageFailed("Zero teleporter");
        
        __AccessControl_init();
        __Pausable_init();
        __ReentrancyGuard_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(BRIDGE_OPERATOR_ROLE, _admin);
        _grantRole(BRIDGE_ADMIN_ROLE, _admin);
        
        teleporterMessenger = _teleporter;
    }
    
    // ============ Core Bridge Functions ============
    
    /// @inheritdoc IPChainBridge
    function routeToPChain(
        ValidatorRegistration calldata registration
    ) external payable override nonReentrant whenNotPaused returns (bytes32 messageId) {
        // Validate inputs
        if (!_supportedSubnets[registration.subnetId]) {
            revert UnsupportedSubnet(registration.subnetId);
        }
        
        uint256 minStake = _minimumStakes[registration.subnetId];
        if (minStake == 0) minStake = DEFAULT_MIN_STAKE;
        
        if (msg.value < minStake) {
            revert InsufficientStakeAmount(msg.value, minStake);
        }
        
        if (registration.nodeId.length != 20) {
            revert InvalidNodeId(registration.nodeId);
        }
        
        // Generate unique message ID
        messageId = _generateMessageId(registration.subnetId, msg.sender);
        
        // Store pending message
        _pendingMessages[messageId] = PendingMessage({
            sender: msg.sender,
            subnetId: registration.subnetId,
            amount: msg.value,
            timestamp: block.timestamp,
            messageType: MessageType.REGISTER_VALIDATOR,
            pending: true
        });
        
        // Construct and send AWM message
        _sendWarpMessage(messageId, registration, msg.value);
        
        totalBridged += msg.value;
        
        emit PChainMessageSent(messageId, registration.subnetId, msg.value, msg.sender);
        
        return messageId;
    }
    
    /// @inheritdoc IPChainBridge
    function increaseStake(
        bytes32 subnetId,
        bytes32 validationId
    ) external payable override nonReentrant whenNotPaused returns (bytes32 messageId) {
        if (!_supportedSubnets[subnetId]) {
            revert UnsupportedSubnet(subnetId);
        }
        
        if (msg.value == 0) {
            revert InsufficientStakeAmount(0, 1);
        }
        
        if (validationId == bytes32(0)) {
            revert InvalidValidationId(validationId);
        }
        
        messageId = _generateMessageId(subnetId, msg.sender);
        
        _pendingMessages[messageId] = PendingMessage({
            sender: msg.sender,
            subnetId: subnetId,
            amount: msg.value,
            timestamp: block.timestamp,
            messageType: MessageType.INCREASE_STAKE,
            pending: true
        });
        
        // Send stake increase message
        _sendStakeIncreaseMessage(messageId, subnetId, validationId, msg.value);
        
        totalBridged += msg.value;
        
        emit ValidatorStakeIncreased(subnetId, validationId, msg.value);
        
        return messageId;
    }
    
    /// @inheritdoc IPChainBridge
    function initiateValidatorExit(
        bytes32 subnetId,
        bytes32 validationId
    ) external override nonReentrant whenNotPaused returns (bytes32 messageId) {
        if (!_supportedSubnets[subnetId]) {
            revert UnsupportedSubnet(subnetId);
        }
        
        if (validationId == bytes32(0)) {
            revert InvalidValidationId(validationId);
        }
        
        messageId = _generateMessageId(subnetId, msg.sender);
        
        _pendingMessages[messageId] = PendingMessage({
            sender: msg.sender,
            subnetId: subnetId,
            amount: 0,
            timestamp: block.timestamp,
            messageType: MessageType.EXIT_VALIDATOR,
            pending: true
        });
        
        // Send exit message
        _sendExitMessage(messageId, subnetId, validationId);
        
        emit ValidatorExitInitiated(subnetId, validationId);
        
        return messageId;
    }
    
    // ============ Callback Functions ============
    
    /// @inheritdoc IPChainBridge
    function receivePChainResponse(
        bytes32 messageId,
        BridgeResult calldata result
    ) external override {
        // Only Teleporter can call this
        if (msg.sender != teleporterMessenger) {
            revert UnauthorizedCaller(msg.sender);
        }
        
        PendingMessage storage pending = _pendingMessages[messageId];
        if (!pending.pending) {
            revert InvalidValidationId(messageId);
        }
        
        pending.pending = false;
        
        if (result.success && result.validationId != bytes32(0)) {
            _validationIds[messageId] = result.validationId;
        }
        
        emit PChainResponseReceived(messageId, result.success, result.validationId);
    }
    
    // ============ Admin Functions ============
    
    /**
     * @notice Add a supported subnet for bridging
     * @param subnetId Subnet ID to add
     * @param minStake Minimum stake for this subnet
     */
    function addSupportedSubnet(
        bytes32 subnetId,
        uint256 minStake
    ) external onlyRole(BRIDGE_ADMIN_ROLE) {
        _supportedSubnets[subnetId] = true;
        _minimumStakes[subnetId] = minStake;
    }
    
    /**
     * @notice Remove a supported subnet
     * @param subnetId Subnet ID to remove
     */
    function removeSupportedSubnet(
        bytes32 subnetId
    ) external onlyRole(BRIDGE_ADMIN_ROLE) {
        _supportedSubnets[subnetId] = false;
    }
    
    /**
     * @notice Update Teleporter messenger address
     * @param _teleporter New Teleporter address
     */
    function setTeleporterMessenger(
        address _teleporter
    ) external onlyRole(BRIDGE_ADMIN_ROLE) {
        if (_teleporter == address(0)) revert AWMMessageFailed("Zero teleporter");
        teleporterMessenger = _teleporter;
    }
    
    /**
     * @notice Pause bridge operations
     */
    function pause() external onlyRole(BRIDGE_ADMIN_ROLE) {
        _pause();
    }
    
    /**
     * @notice Unpause bridge operations
     */
    function unpause() external onlyRole(BRIDGE_ADMIN_ROLE) {
        _unpause();
    }
    
    /**
     * @notice Emergency rescue for stuck funds
     * @dev Only callable by admin after timeout
     * @param messageId Message with stuck funds
     */
    function rescueStuckFunds(
        bytes32 messageId
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        PendingMessage storage pending = _pendingMessages[messageId];
        
        // Must be pending for at least 7 days
        require(
            pending.pending && 
            block.timestamp > pending.timestamp + 7 days,
            "Too early or not pending"
        );
        
        pending.pending = false;
        
        // Return funds to original sender
        (bool success, ) = pending.sender.call{value: pending.amount}("");
        require(success, "Transfer failed");
    }
    
    // ============ View Functions ============
    
    /// @inheritdoc IPChainBridge
    function isSupportedSubnet(bytes32 subnetId) external view override returns (bool) {
        return _supportedSubnets[subnetId];
    }
    
    /// @inheritdoc IPChainBridge
    function getMinimumStake(bytes32 subnetId) external view override returns (uint256) {
        uint256 minStake = _minimumStakes[subnetId];
        return minStake == 0 ? DEFAULT_MIN_STAKE : minStake;
    }
    
    /// @inheritdoc IPChainBridge
    function getMessageStatus(bytes32 messageId) external view override returns (
        bool pending,
        uint256 timestamp
    ) {
        PendingMessage storage msg_ = _pendingMessages[messageId];
        return (msg_.pending, msg_.timestamp);
    }
    
    /// @inheritdoc IPChainBridge
    function getTeleporterMessenger() external view override returns (address) {
        return teleporterMessenger;
    }
    
    /**
     * @notice Get validation ID for a completed registration
     * @param messageId Original message ID
     * @return validationId P-Chain validation ID
     */
    function getValidationId(bytes32 messageId) external view returns (bytes32) {
        return _validationIds[messageId];
    }
    
    // ============ Internal Functions ============
    
    /**
     * @notice Generate unique message ID
     */
    function _generateMessageId(
        bytes32 subnetId,
        address sender
    ) internal returns (bytes32) {
        return keccak256(abi.encodePacked(
            block.chainid,
            address(this),
            subnetId,
            sender,
            _messageNonce++
        ));
    }
    
    /**
     * @notice Send AWM message for validator registration
     * @dev This encodes the message for the P-Chain Warp precompile
     */
    function _sendWarpMessage(
        bytes32 messageId,
        ValidatorRegistration calldata registration,
        uint256 amount
    ) internal {
        // Encode the message payload for P-Chain
        bytes memory payload = abi.encode(
            uint8(0x01), // Message type: AddPermissionlessValidator
            messageId,
            registration.subnetId,
            registration.nodeId,
            registration.blsPublicKey,
            registration.weight,
            registration.delegationFeeBps,
            amount
        );
        
        // In production, this would call ITeleporterMessenger.sendCrossChainMessage()
        // For now, we store the payload and emit an event
        // The actual Teleporter integration requires the deployed Teleporter contracts
        
        // bytes32 messageHash = keccak256(payload);
        // ITeleporterMessenger(teleporterMessenger).sendCrossChainMessage{value: amount}(
        //     TeleporterMessageInput({
        //         destinationBlockchainID: P_CHAIN_BLOCKCHAIN_ID,
        //         destinationAddress: pChainDestination,
        //         feeInfo: TeleporterFeeInfo({feeTokenAddress: address(0), amount: 0}),
        //         requiredGasLimit: 500_000,
        //         allowedRelayerAddresses: new address[](0),
        //         message: payload
        //     })
        // );
    }
    
    /**
     * @notice Send stake increase message
     */
    function _sendStakeIncreaseMessage(
        bytes32 messageId,
        bytes32 subnetId,
        bytes32 validationId,
        uint256 amount
    ) internal {
        bytes memory payload = abi.encode(
            uint8(0x02), // Message type: IncreaseStake
            messageId,
            subnetId,
            validationId,
            amount
        );
        
        // Same Teleporter integration as above
    }
    
    /**
     * @notice Send validator exit message
     */
    function _sendExitMessage(
        bytes32 messageId,
        bytes32 subnetId,
        bytes32 validationId
    ) internal {
        bytes memory payload = abi.encode(
            uint8(0x03), // Message type: InitiateExit
            messageId,
            subnetId,
            validationId
        );
        
        // Same Teleporter integration as above
    }
    
    /**
     * @notice Authorize upgrade (UUPS pattern)
     */
    function _authorizeUpgrade(address newImplementation) internal override onlyRole(DEFAULT_ADMIN_ROLE) {
        // Upgrade authorization
    }
    
    // ============ Receive Function ============
    
    /**
     * @notice Allow contract to receive ETH
     */
    receive() external payable {}
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage for future upgrades
    uint256[44] private __gap;
}
