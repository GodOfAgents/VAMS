// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";

import {IX402NonceRegistry} from "./IX402NonceRegistry.sol";

/**
 * @title X402NonceRegistry
 * @author VAMS Protocol
 * @notice Prevents double-spending in x402 micropayments by tracking used nonces
 * @dev Implements the x402 nonce registry per ARCHITECTURE_v0-3-0.md §20.2.1
 * 
 * Security Model:
 * - Each agent has independent nonce space
 * - Nonces can only be consumed by authorized settlement contracts
 * - Both nonce AND receipt hash must be unused (belt-and-suspenders)
 * - Supports batch operations for gas efficiency
 * 
 * Gas Optimization:
 * - Uses mapping for O(1) lookups
 * - Minimal storage per nonce (32 bytes packed)
 * - Batch operations amortize fixed costs
 */
contract X402NonceRegistry is 
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    IX402NonceRegistry 
{
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;
    
    // ============ Constants ============
    
    /// @notice Role for settlement contracts that can consume nonces
    bytes32 public constant SETTLER_ROLE = keccak256("SETTLER_ROLE");
    
    /// @notice Role for protocol administrators
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    /// @notice Role for pausing in emergencies
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    
    // ============ Storage ============
    
    /// @notice Mapping: agent => nonce => NonceInfo
    mapping(address => mapping(uint256 => NonceInfo)) private _nonces;
    
    /// @notice Mapping: receiptHash => claimed
    mapping(bytes32 => bool) private _claimedReceipts;
    
    /// @notice Mapping: agent => highest used nonce
    mapping(address => uint256) private _highestNonce;
    
    /// @notice Reference to escrow manager for balance checks
    address public escrowManager;
    
    /// @notice Total nonces consumed (for analytics)
    uint256 public totalNoncesConsumed;
    
    // ============ Initializer ============
    
    /**
     * @notice Initialize the nonce registry
     * @param admin Protocol admin address
     * @param _escrowManager Escrow manager for balance checks
     */
    function initialize(
        address admin,
        address _escrowManager
    ) external initializer {
        if (admin == address(0)) revert ZeroAddress();
        
        __AccessControl_init();
        __Pausable_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        
        escrowManager = _escrowManager;
    }
    
    // ============ View Functions ============
    
    /// @inheritdoc IX402NonceRegistry
    function isNonceValid(address agent, uint256 nonce) 
        external 
        view 
        override 
        returns (bool) 
    {
        return !_nonces[agent][nonce].used;
    }
    
    /// @inheritdoc IX402NonceRegistry
    function isReceiptClaimed(bytes32 receiptHash) 
        external 
        view 
        override 
        returns (bool) 
    {
        return _claimedReceipts[receiptHash];
    }
    
    /// @inheritdoc IX402NonceRegistry
    function verifyReceipt(
        address agent,
        uint256 nonce,
        uint256 amount,
        bytes calldata signature
    ) external view override returns (bool valid, string memory reason) {
        // 1. Check nonce is unused
        if (_nonces[agent][nonce].used) {
            return (false, "Nonce already used - potential double-spend");
        }
        
        // 2. Compute and check receipt hash
        bytes32 receiptHash = _computeReceiptHash(agent, nonce, amount);
        if (_claimedReceipts[receiptHash]) {
            return (false, "Receipt already claimed");
        }
        
        // 3. Verify signature
        bytes32 messageHash = receiptHash.toEthSignedMessageHash();
        address signer = messageHash.recover(signature);
        
        if (signer != agent) {
            return (false, "Invalid signature - signer does not match agent");
        }
        
        // 4. Optionally check escrow balance (if escrow manager is set)
        if (escrowManager != address(0)) {
            // Note: This would require interface to escrow manager
            // For now, we skip this check and let escrow manager handle it
        }
        
        return (true, "Receipt valid");
    }
    
    /// @inheritdoc IX402NonceRegistry
    function getNextNonce(address agent) 
        external 
        view 
        override 
        returns (uint256) 
    {
        // Start from highest known + 1 for efficiency
        uint256 start = _highestNonce[agent];
        
        // Search for first unused nonce
        for (uint256 i = start; i <= start + 1000; i++) {
            if (!_nonces[agent][i].used) {
                return i;
            }
        }
        
        // Fallback: search from 0 (shouldn't happen normally)
        for (uint256 i = 0; i < start; i++) {
            if (!_nonces[agent][i].used) {
                return i;
            }
        }
        
        // If all searched nonces are used, return next sequential
        return start + 1001;
    }
    
    /// @inheritdoc IX402NonceRegistry
    function getHighestUsedNonce(address agent) 
        external 
        view 
        override 
        returns (uint256) 
    {
        return _highestNonce[agent];
    }
    
    /// @inheritdoc IX402NonceRegistry
    function getNonceInfo(address agent, uint256 nonce) 
        external 
        view 
        override 
        returns (NonceInfo memory) 
    {
        return _nonces[agent][nonce];
    }
    
    /// @inheritdoc IX402NonceRegistry
    function isAuthorizedSettler(address settler) 
        external 
        view 
        override 
        returns (bool) 
    {
        return hasRole(SETTLER_ROLE, settler);
    }
    
    // ============ State-Changing Functions ============
    
    /// @inheritdoc IX402NonceRegistry
    function consumeNonce(
        address agent,
        uint256 nonce,
        bytes32 receiptHash,
        bytes32 escrowId
    ) external override onlyRole(SETTLER_ROLE) whenNotPaused {
        _consumeNonce(agent, nonce, receiptHash, escrowId);
    }
    
    /// @inheritdoc IX402NonceRegistry
    function batchConsumeNonces(
        address[] calldata agents,
        uint256[] calldata nonces,
        bytes32[] calldata receiptHashes,
        bytes32[] calldata escrowIds
    ) external override onlyRole(SETTLER_ROLE) whenNotPaused {
        uint256 length = agents.length;
        require(
            length == nonces.length && 
            length == receiptHashes.length && 
            length == escrowIds.length,
            "Array length mismatch"
        );
        
        for (uint256 i = 0; i < length; i++) {
            _consumeNonce(agents[i], nonces[i], receiptHashes[i], escrowIds[i]);
        }
    }
    
    // ============ Admin Functions ============
    
    /// @inheritdoc IX402NonceRegistry
    function authorizeSettler(address settler) 
        external 
        override 
        onlyRole(ADMIN_ROLE) 
    {
        if (settler == address(0)) revert ZeroAddress();
        
        _grantRole(SETTLER_ROLE, settler);
        emit SettlerAuthorized(settler);
    }
    
    /// @inheritdoc IX402NonceRegistry
    function deauthorizeSettler(address settler) 
        external 
        override 
        onlyRole(ADMIN_ROLE) 
    {
        _revokeRole(SETTLER_ROLE, settler);
        emit SettlerDeauthorized(settler);
    }
    
    /**
     * @notice Update the escrow manager reference
     * @param _escrowManager New escrow manager address
     */
    function setEscrowManager(address _escrowManager) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        escrowManager = _escrowManager;
    }
    
    /**
     * @notice Pause the registry in case of emergency
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }
    
    /**
     * @notice Unpause the registry
     */
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }
    
    // ============ Internal Functions ============
    
    /**
     * @dev Internal function to consume a nonce
     * @param agent Agent address
     * @param nonce Nonce value
     * @param receiptHash Receipt hash
     * @param escrowId Associated escrow ID
     */
    function _consumeNonce(
        address agent,
        uint256 nonce,
        bytes32 receiptHash,
        bytes32 escrowId
    ) internal {
        // Check nonce is unused
        if (_nonces[agent][nonce].used) {
            revert NonceAlreadyUsed(agent, nonce);
        }
        
        // Check receipt is unclaimed
        if (_claimedReceipts[receiptHash]) {
            revert ReceiptAlreadyClaimed(receiptHash);
        }
        
        // Mark nonce as used
        _nonces[agent][nonce] = NonceInfo({
            used: true,
            receiptHash: receiptHash,
            consumedAt: block.timestamp,
            escrowId: escrowId
        });
        
        // Mark receipt as claimed
        _claimedReceipts[receiptHash] = true;
        
        // Update highest nonce if needed
        if (nonce > _highestNonce[agent]) {
            _highestNonce[agent] = nonce;
        }
        
        // Increment counter
        unchecked {
            totalNoncesConsumed++;
        }
        
        emit NonceConsumed(agent, nonce, receiptHash, escrowId);
    }
    
    /**
     * @dev Compute receipt hash for verification
     * @param agent Agent address
     * @param nonce Nonce value
     * @param amount Payment amount
     * @return Receipt hash
     */
    function _computeReceiptHash(
        address agent,
        uint256 nonce,
        uint256 amount
    ) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(agent, nonce, amount));
    }
    
}
