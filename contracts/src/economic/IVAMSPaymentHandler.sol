// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSPaymentHandler
 * @author VAMS Protocol
 * @notice Interface for x402 payment channel management
 * @dev Handles $VAMS-only payment channels with nonce-based state
 */
interface IVAMSPaymentHandler {
    // ============ Enums ============

    enum ChannelStatus {
        OPEN, // Active channel
        CLOSING, // Dispute period active
        CLOSED // Channel settled
    }

    // ============ Structs ============

    struct Channel {
        address partyA; // Channel opener
        address partyB; // Counterparty
        uint256 depositA; // Party A's deposit
        uint256 depositB; // Party B's deposit
        uint256 nonce; // Latest state nonce
        uint256 balanceA; // Party A's current balance
        uint256 balanceB; // Party B's current balance
        uint256 openedAt; // Channel open timestamp
        uint256 closingAt; // When dispute period ends (0 if not closing)
        ChannelStatus status; // Current status
    }

    struct ChannelState {
        bytes32 channelId; // Channel identifier
        uint256 nonce; // State nonce (must be higher than previous)
        uint256 balanceA; // Party A balance
        uint256 balanceB; // Party B balance
    }

    // ============ Events ============

    event ChannelOpened(bytes32 indexed channelId, address indexed partyA, address indexed partyB, uint256 depositA);
    event ChannelDeposited(bytes32 indexed channelId, address indexed party, uint256 amount);
    event ChannelClosingInitiated(bytes32 indexed channelId, address indexed initiator, uint256 closingAt);
    event ChannelDisputed(bytes32 indexed channelId, address indexed disputer, uint256 newNonce);
    event ChannelSettled(bytes32 indexed channelId, uint256 finalBalanceA, uint256 finalBalanceB);
    event ChannelCooperativelyClosed(bytes32 indexed channelId);

    // ============ Errors ============

    error ChannelNotFound(bytes32 channelId);
    error ChannelAlreadyClosed(bytes32 channelId);
    error ChannelNotClosing(bytes32 channelId);
    error ChannelStillDisputable(bytes32 channelId, uint256 closingAt);
    error NotChannelParticipant(address caller);
    error InvalidSignature();
    error InvalidNonce(uint256 provided, uint256 required);
    error InvalidBalances(uint256 totalBalances, uint256 totalDeposits);
    error DisputeWindowExpired(bytes32 channelId);
    error ZeroAmount();
    error ZeroAddress();

    // ============ External Functions ============

    /**
     * @notice Open a new payment channel
     * @param counterparty The other party in the channel
     * @param deposit Initial deposit amount
     * @return channelId Unique channel identifier
     */
    function openChannel(address counterparty, uint256 deposit) external returns (bytes32 channelId);

    /**
     * @notice Add funds to an existing channel
     * @param channelId Channel to deposit into
     * @param amount Amount to deposit
     */
    function depositToChannel(bytes32 channelId, uint256 amount) external;

    /**
     * @notice Cooperatively close a channel with mutual signatures
     * @param channelId Channel to close
     * @param finalState Final agreed state
     * @param signatureA Party A's signature
     * @param signatureB Party B's signature
     */
    function cooperativeClose(
        bytes32 channelId,
        ChannelState calldata finalState,
        bytes calldata signatureA,
        bytes calldata signatureB
    ) external;

    /**
     * @notice Initiate unilateral close (starts dispute period)
     * @param channelId Channel to close
     * @param state Latest known state
     * @param signature Other party's signature on state
     */
    function initiateClose(bytes32 channelId, ChannelState calldata state, bytes calldata signature) external;

    /**
     * @notice Dispute a closing with a higher nonce state
     * @param channelId Channel being closed
     * @param state Higher nonce state
     * @param signature Other party's signature
     */
    function dispute(bytes32 channelId, ChannelState calldata state, bytes calldata signature) external;

    /**
     * @notice Finalize settlement after dispute window
     * @param channelId Channel to settle
     */
    function settle(bytes32 channelId) external;

    // ============ View Functions ============

    /**
     * @notice Get channel details
     * @param channelId Channel identifier
     * @return Channel struct
     */
    function getChannel(bytes32 channelId) external view returns (Channel memory);

    /**
     * @notice Get channels for an address
     * @param party Address to query
     * @return Array of channel IDs
     */
    function getChannelsFor(address party) external view returns (bytes32[] memory);

    /**
     * @notice Check if dispute window is active
     * @param channelId Channel to check
     * @return True if in dispute window
     */
    function isDisputable(bytes32 channelId) external view returns (bool);

    /**
     * @notice Get settlement fee rate (basis points)
     * @return Fee in basis points
     */
    function settlementFeeBps() external view returns (uint256);
}
