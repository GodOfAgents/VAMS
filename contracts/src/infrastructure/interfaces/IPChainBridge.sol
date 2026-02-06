// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IPChainBridge
 * @author VAMS Protocol
 * @notice Interface for routing funds to Avalanche P-Chain via AWM/Teleporter
 * @dev This interface defines the cross-chain messaging pattern for ACP-77 validator deposits
 *
 * Integration Flow:
 * 1. VAMSValidatorManager calculates markup and deducts fees
 * 2. Net amount is sent to this bridge contract
 * 3. Bridge uses AWM to send message to P-Chain
 * 4. P-Chain native contract registers validator stake
 *
 * References:
 * - AWM: https://build.avax.network/docs/cross-chain/avalanche-warp-messaging
 * - Teleporter: https://build.avax.network/docs/cross-chain/avalanche-warp-messaging/deep-dive
 * - ACP-77: https://github.com/avalanche-foundation/ACPs/tree/main/ACPs/77-reinventing-subnets
 */
interface IPChainBridge {
    // ============ Structs ============
    
    /**
     * @notice Configuration for a validator registration
     * @param subnetId The L1 subnet ID to register validator for
     * @param nodeId The node ID of the validator (BLS public key)
     * @param blsPublicKey BLS proof of possession key for consensus
     * @param weight Validator weight (stake amount in nAVAX)
     * @param delegationFeeBps Fee percentage for delegations (basis points)
     */
    struct ValidatorRegistration {
        bytes32 subnetId;
        bytes nodeId;           // 20 bytes node ID
        bytes blsPublicKey;     // 48 bytes BLS public key
        uint64 weight;          // Stake weight in nAVAX
        uint16 delegationFeeBps;
    }
    
    /**
     * @notice Result of a P-Chain operation
     * @param success Whether the operation succeeded
     * @param validationId Unique ID of the validation (if successful)
     * @param timestamp When the result was received
     */
    struct BridgeResult {
        bool success;
        bytes32 validationId;
        uint256 timestamp;
    }
    
    // ============ Events ============
    
    /**
     * @notice Emitted when a cross-chain message is sent to P-Chain
     * @param messageId Unique identifier for the AWM message
     * @param subnetId Target subnet ID
     * @param amount AVAX amount being bridged
     * @param sender Address initiating the bridge
     */
    event PChainMessageSent(
        bytes32 indexed messageId,
        bytes32 indexed subnetId,
        uint256 amount,
        address indexed sender
    );
    
    /**
     * @notice Emitted when a P-Chain response is received
     * @param messageId Original message ID
     * @param success Whether the registration succeeded
     * @param validationId The P-Chain validation ID (if successful)
     */
    event PChainResponseReceived(
        bytes32 indexed messageId,
        bool success,
        bytes32 validationId
    );
    
    /**
     * @notice Emitted when validator stake is increased
     * @param subnetId Subnet ID
     * @param validationId Existing validation ID
     * @param additionalAmount Additional stake amount
     */
    event ValidatorStakeIncreased(
        bytes32 indexed subnetId,
        bytes32 indexed validationId,
        uint256 additionalAmount
    );
    
    /**
     * @notice Emitted when validator begins exit process
     * @param subnetId Subnet ID
     * @param validationId Validation being exited
     */
    event ValidatorExitInitiated(
        bytes32 indexed subnetId,
        bytes32 indexed validationId
    );
    
    // ============ Errors ============
    
    /// @notice Thrown when the amount is below minimum stake
    error InsufficientStakeAmount(uint256 provided, uint256 minimum);
    
    /// @notice Thrown when the subnet is not supported
    error UnsupportedSubnet(bytes32 subnetId);
    
    /// @notice Thrown when AWM message send fails
    error AWMMessageFailed(bytes reason);
    
    /// @notice Thrown when the caller is not authorized
    error UnauthorizedCaller(address caller);
    
    /// @notice Thrown when the validation ID is invalid
    error InvalidValidationId(bytes32 validationId);
    
    /// @notice Thrown when the node ID format is invalid
    error InvalidNodeId(bytes nodeId);
    
    // ============ Core Functions ============
    
    /**
     * @notice Route AVAX to P-Chain for validator registration
     * @dev This is the primary entry point for the ValidatorManager
     * @param registration Validator registration details
     * @return messageId Unique identifier for tracking the cross-chain message
     *
     * Requirements:
     * - msg.value must be >= minimum stake amount (25,000 AVAX for mainnet)
     * - subnetId must be a registered managed L1
     * - nodeId must be valid and not already registered
     * - blsPublicKey must be valid BLS key format
     *
     * Flow:
     * 1. Validate inputs
     * 2. Construct Warp message for P-Chain
     * 3. Send via Teleporter/AWM
     * 4. Store pending registration for callback
     */
    function routeToPChain(
        ValidatorRegistration calldata registration
    ) external payable returns (bytes32 messageId);
    
    /**
     * @notice Increase stake for an existing validator
     * @param subnetId Subnet containing the validator
     * @param validationId Existing validation ID from initial registration
     * @return messageId Unique identifier for the stake increase message
     *
     * Requirements:
     * - validationId must exist and be active
     * - msg.value must be > 0
     */
    function increaseStake(
        bytes32 subnetId,
        bytes32 validationId
    ) external payable returns (bytes32 messageId);
    
    /**
     * @notice Initiate validator exit/unstaking process
     * @dev This begins the P-Chain unbonding period
     * @param subnetId Subnet containing the validator
     * @param validationId Validation to exit
     * @return messageId Unique identifier for the exit message
     *
     * Requirements:
     * - validationId must exist and be active
     * - Caller must be the original depositor or authorized
     */
    function initiateValidatorExit(
        bytes32 subnetId,
        bytes32 validationId
    ) external returns (bytes32 messageId);
    
    // ============ Callback Functions ============
    
    /**
     * @notice Process response from P-Chain via AWM
     * @dev Called by the Teleporter/AWM receiver
     * @param messageId Original message ID
     * @param result Result of the P-Chain operation
     *
     * Requirements:
     * - Only callable by authorized Teleporter contract
     * - messageId must correspond to a pending operation
     */
    function receivePChainResponse(
        bytes32 messageId,
        BridgeResult calldata result
    ) external;
    
    // ============ View Functions ============
    
    /**
     * @notice Check if a subnet is supported for bridging
     * @param subnetId Subnet ID to check
     * @return supported True if the subnet is configured for P-Chain routing
     */
    function isSupportedSubnet(bytes32 subnetId) external view returns (bool supported);
    
    /**
     * @notice Get the minimum stake amount for a subnet
     * @param subnetId Subnet ID to query
     * @return minStake Minimum stake in wei
     */
    function getMinimumStake(bytes32 subnetId) external view returns (uint256 minStake);
    
    /**
     * @notice Get pending message status
     * @param messageId Message ID to query
     * @return pending True if the message is awaiting P-Chain response
     * @return timestamp When the message was sent
     */
    function getMessageStatus(bytes32 messageId) external view returns (
        bool pending,
        uint256 timestamp
    );
    
    /**
     * @notice Get the AWM/Teleporter messenger address
     * @return messenger Address of the Teleporter messenger contract
     */
    function getTeleporterMessenger() external view returns (address messenger);
}
