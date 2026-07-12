// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "./IVAMSPaymentHandler.sol";

/**
 * @title VAMSPaymentHandler
 * @author VAMS Protocol
 * @notice x402 payment channel management for micropayments
 * @dev 
 * - $VAMS-only payment channels
 * - Nonce-based state prevents double-spending
 * - 24-hour dispute window for contested closures
 * - 0.05% settlement fee to protocol treasury
 */
contract VAMSPaymentHandler is 
    Initializable, 
    AccessControlUpgradeable,
    ReentrancyGuard,
    PausableUpgradeable,
    IVAMSPaymentHandler 
{
    using SafeERC20 for IERC20;
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;
    
    // ============ Constants ============
    
    /// @notice Operator role for emergency functions
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    /// @notice INTG01: Role for VAMSSentinel autonomous emergency pause
    bytes32 public constant SENTINEL_ROLE = keccak256("SENTINEL_ROLE");
    
    /// @notice Dispute window duration (24 hours)
    uint256 public constant DISPUTE_WINDOW = 24 hours;
    
    /// @notice Settlement fee (0.05% = 5 bps)
    uint256 public constant SETTLEMENT_FEE_BPS = 5;
    
    /// @notice Basis points denominator
    uint256 public constant BPS_DENOMINATOR = 10000;
    
    // ============ State ============
    
    /// @notice VAMS token
    IERC20 public vamsToken;
    
    /// @notice Protocol treasury for fees
    address public treasury;
    
    /// @notice Total channels created
    uint256 public totalChannels;
    
    /// @notice Total volume settled
    uint256 public totalVolumeSettled;
    
    /// @notice Channels mapping
    mapping(bytes32 channelId => Channel channel) private _channels;
    
    /// @notice Channels by participant
    mapping(address party => bytes32[] channelIds) private _partyChannels;
    
    // ============ Initializer ============
    
    /**
     * @notice Initialize the payment handler
     * @param _admin Admin address
     * @param _vamsToken VAMS token address
     * @param _treasury Treasury for fees
     */
    function initialize(
        address _admin,
        address _vamsToken,
        address _treasury
    ) public initializer {
        if (_admin == address(0) || _vamsToken == address(0) || _treasury == address(0)) {
            revert ZeroAddress();
        }
        
        __AccessControl_init();
        __Pausable_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);
        
        vamsToken = IERC20(_vamsToken);
        treasury = _treasury;
    }
    
    // ============ Channel Lifecycle ============
    
    /// @inheritdoc IVAMSPaymentHandler
    function openChannel(
        address counterparty,
        uint256 deposit
    ) external override nonReentrant whenNotPaused returns (bytes32 channelId) {
        if (counterparty == address(0)) revert ZeroAddress();
        if (counterparty == msg.sender) revert ZeroAddress(); // Can't open channel with self
        if (deposit == 0) revert ZeroAmount();
        
        // Generate unique channel ID
        channelId = keccak256(abi.encodePacked(
            msg.sender,
            counterparty,
            block.timestamp,
            totalChannels
        ));
        
        // Transfer deposit
        vamsToken.safeTransferFrom(msg.sender, address(this), deposit);
        
        // Create channel
        _channels[channelId] = Channel({
            partyA: msg.sender,
            partyB: counterparty,
            depositA: deposit,
            depositB: 0,
            nonce: 0,
            balanceA: deposit,
            balanceB: 0,
            openedAt: block.timestamp,
            closingAt: 0,
            status: ChannelStatus.OPEN
        });
        
        _partyChannels[msg.sender].push(channelId);
        _partyChannels[counterparty].push(channelId);
        totalChannels++;
        
        emit ChannelOpened(channelId, msg.sender, counterparty, deposit);
    }
    
    /// @inheritdoc IVAMSPaymentHandler
    function depositToChannel(bytes32 channelId, uint256 amount) external override nonReentrant {
        Channel storage channel = _channels[channelId];
        
        if (channel.partyA == address(0)) revert ChannelNotFound(channelId);
        if (channel.status != ChannelStatus.OPEN) revert ChannelAlreadyClosed(channelId);
        if (amount == 0) revert ZeroAmount();
        
        bool isPartyA = msg.sender == channel.partyA;
        bool isPartyB = msg.sender == channel.partyB;
        if (!isPartyA && !isPartyB) revert NotChannelParticipant(msg.sender);
        
        vamsToken.safeTransferFrom(msg.sender, address(this), amount);
        
        if (isPartyA) {
            channel.depositA += amount;
            channel.balanceA += amount;
        } else {
            channel.depositB += amount;
            channel.balanceB += amount;
        }
        
        emit ChannelDeposited(channelId, msg.sender, amount);
    }
    
    /// @inheritdoc IVAMSPaymentHandler
    function cooperativeClose(
        bytes32 channelId,
        ChannelState calldata finalState,
        bytes calldata signatureA,
        bytes calldata signatureB
    ) external override nonReentrant {
        Channel storage channel = _channels[channelId];
        
        if (channel.partyA == address(0)) revert ChannelNotFound(channelId);
        if (channel.status == ChannelStatus.CLOSED) revert ChannelAlreadyClosed(channelId);
        
        // Verify state matches channel
        if (finalState.channelId != channelId) revert ChannelNotFound(channelId);
        
        // Verify balances sum to deposits
        uint256 totalDeposits = channel.depositA + channel.depositB;
        if (finalState.balanceA + finalState.balanceB != totalDeposits) {
            revert InvalidBalances(finalState.balanceA + finalState.balanceB, totalDeposits);
        }
        
        // Verify both signatures
        bytes32 stateHash = _hashState(finalState);
        _verifySignature(stateHash, signatureA, channel.partyA);
        _verifySignature(stateHash, signatureB, channel.partyB);
        
        // Execute settlement
        _executeSettlement(channelId, finalState.balanceA, finalState.balanceB);
        
        emit ChannelCooperativelyClosed(channelId);
    }
    
    /// @inheritdoc IVAMSPaymentHandler
    function initiateClose(
        bytes32 channelId,
        ChannelState calldata state,
        bytes calldata signature
    ) external override nonReentrant {
        Channel storage channel = _channels[channelId];
        
        if (channel.partyA == address(0)) revert ChannelNotFound(channelId);
        if (channel.status != ChannelStatus.OPEN) revert ChannelAlreadyClosed(channelId);
        
        bool isPartyA = msg.sender == channel.partyA;
        bool isPartyB = msg.sender == channel.partyB;
        if (!isPartyA && !isPartyB) revert NotChannelParticipant(msg.sender);
        
        // Verify state
        if (state.channelId != channelId) revert ChannelNotFound(channelId);
        if (state.nonce <= channel.nonce) revert InvalidNonce(state.nonce, channel.nonce + 1);
        
        // Verify signature from OTHER party
        bytes32 stateHash = _hashState(state);
        address otherParty = isPartyA ? channel.partyB : channel.partyA;
        _verifySignature(stateHash, signature, otherParty);
        
        // Update channel state
        channel.nonce = state.nonce;
        channel.balanceA = state.balanceA;
        channel.balanceB = state.balanceB;
        channel.status = ChannelStatus.CLOSING;
        channel.closingAt = block.timestamp + DISPUTE_WINDOW;
        
        emit ChannelClosingInitiated(channelId, msg.sender, channel.closingAt);
    }
    
    /// @inheritdoc IVAMSPaymentHandler
    function dispute(
        bytes32 channelId,
        ChannelState calldata state,
        bytes calldata signature
    ) external override nonReentrant {
        Channel storage channel = _channels[channelId];
        
        if (channel.partyA == address(0)) revert ChannelNotFound(channelId);
        if (channel.status != ChannelStatus.CLOSING) revert ChannelNotClosing(channelId);
        if (block.timestamp >= channel.closingAt) revert DisputeWindowExpired(channelId);
        
        bool isPartyA = msg.sender == channel.partyA;
        bool isPartyB = msg.sender == channel.partyB;
        if (!isPartyA && !isPartyB) revert NotChannelParticipant(msg.sender);
        
        // Must have higher nonce
        if (state.nonce <= channel.nonce) revert InvalidNonce(state.nonce, channel.nonce + 1);
        
        // Verify signature from OTHER party
        bytes32 stateHash = _hashState(state);
        address otherParty = isPartyA ? channel.partyB : channel.partyA;
        _verifySignature(stateHash, signature, otherParty);
        
        // Update to newer state and reset dispute window
        channel.nonce = state.nonce;
        channel.balanceA = state.balanceA;
        channel.balanceB = state.balanceB;
        channel.closingAt = block.timestamp + DISPUTE_WINDOW;
        
        emit ChannelDisputed(channelId, msg.sender, state.nonce);
    }
    
    /// @inheritdoc IVAMSPaymentHandler
    function settle(bytes32 channelId) external override nonReentrant {
        Channel storage channel = _channels[channelId];
        
        if (channel.partyA == address(0)) revert ChannelNotFound(channelId);
        if (channel.status != ChannelStatus.CLOSING) revert ChannelNotClosing(channelId);
        if (block.timestamp < channel.closingAt) {
            revert ChannelStillDisputable(channelId, channel.closingAt);
        }
        
        _executeSettlement(channelId, channel.balanceA, channel.balanceB);
    }
    
    // ============ Internal Functions ============
    
    /**
     * @notice Execute final settlement with fee deduction
     */
    function _executeSettlement(
        bytes32 channelId,
        uint256 balanceA,
        uint256 balanceB
    ) internal {
        Channel storage channel = _channels[channelId];
        
        // Calculate fees
        uint256 totalSettlement = balanceA + balanceB;
        uint256 feeA = (balanceA * SETTLEMENT_FEE_BPS) / BPS_DENOMINATOR;
        uint256 feeB = (balanceB * SETTLEMENT_FEE_BPS) / BPS_DENOMINATOR;
        uint256 fee = feeA + feeB;
        
        uint256 payoutA = balanceA - feeA;
        uint256 payoutB = balanceB - feeB;
        
        // Update state
        channel.status = ChannelStatus.CLOSED;
        totalVolumeSettled += totalSettlement;
        
        // Transfer funds
        if (payoutA > 0) {
            vamsToken.safeTransfer(channel.partyA, payoutA);
        }
        if (payoutB > 0) {
            vamsToken.safeTransfer(channel.partyB, payoutB);
        }
        if (fee > 0) {
            vamsToken.safeTransfer(treasury, fee);
        }
        
        emit ChannelSettled(channelId, payoutA, payoutB);
    }
    
    /**
     * @notice Hash channel state for signing
     */
    function _hashState(ChannelState calldata state) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(
            state.channelId,
            state.nonce,
            state.balanceA,
            state.balanceB
        ));
    }
    
    /**
     * @notice Verify signature matches expected signer
     */
    function _verifySignature(
        bytes32 hash,
        bytes calldata signature,
        address expectedSigner
    ) internal pure {
        bytes32 ethSignedHash = hash.toEthSignedMessageHash();
        address recovered = ethSignedHash.recover(signature);
        if (recovered != expectedSigner) revert InvalidSignature();
    }
    
    // ============ Admin Functions ============
    
    /**
     * @notice Update treasury address
     */
    function setTreasury(address _treasury) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_treasury == address(0)) revert ZeroAddress();
        treasury = _treasury;
    }
    
    /**
     * @notice INTG01: Sentinel-callable emergency pause (implements IPausableTarget)
     * @param reason Human-readable reason for the pause
     */
    function emergencyPause(string calldata reason) external onlyRole(SENTINEL_ROLE) {
        emit EmergencyPauseActivated(msg.sender, reason);
        _pause();
    }

    /// @dev Emitted when Sentinel triggers an emergency pause
    event EmergencyPauseActivated(address indexed sentinel, string reason);

    /**
     * @notice Pause channel operations
     */
    function pause() external onlyRole(OPERATOR_ROLE) {
        _pause();
    }

    /**
     * @notice Unpause channel operations
     */
    function unpause() external {
        require(
            hasRole(OPERATOR_ROLE, msg.sender) || hasRole(SENTINEL_ROLE, msg.sender),
            "VAMSPaymentHandler: not authorized"
        );
        _unpause();
    }
    
    // ============ View Functions ============
    
    /// @inheritdoc IVAMSPaymentHandler
    function getChannel(bytes32 channelId) external view override returns (Channel memory) {
        return _channels[channelId];
    }
    
    /// @inheritdoc IVAMSPaymentHandler
    function getChannelsFor(address party) external view override returns (bytes32[] memory) {
        return _partyChannels[party];
    }
    
    /// @inheritdoc IVAMSPaymentHandler
    function isDisputable(bytes32 channelId) external view override returns (bool) {
        Channel storage channel = _channels[channelId];
        return channel.status == ChannelStatus.CLOSING && 
               block.timestamp < channel.closingAt;
    }
    
    /// @inheritdoc IVAMSPaymentHandler
    function settlementFeeBps() external pure override returns (uint256) {
        return SETTLEMENT_FEE_BPS;
    }
    
    /**
     * @notice Get total deposits in a channel
     */
    function getChannelTotal(bytes32 channelId) external view returns (uint256) {
        Channel storage channel = _channels[channelId];
        return channel.depositA + channel.depositB;
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
