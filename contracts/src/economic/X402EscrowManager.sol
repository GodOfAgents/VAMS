// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";

import {IX402EscrowManager} from "./IX402EscrowManager.sol";
import {IX402NonceRegistry} from "./IX402NonceRegistry.sol";
import {IProviderBondRegistry} from "./IProviderBondRegistry.sol";

/**
 * @title X402EscrowManager
 * @author VAMS Protocol
 * @notice HTLC-based atomic escrow for x402 micropayment settlements
 * @dev Implements escrow per ARCHITECTURE_v0-3-0.md §20.2.2
 * 
 * Integration Points:
 * - IX402NonceRegistry: Consumes nonces on successful claim
 * - IProviderBondRegistry: Tracks active requests against provider bonds
 * - Fee collection: 0.05% settlement fee to treasury
 * 
 * Security Features:
 * - HTLC for cross-service atomicity
 * - Service proof verification (TEE attestation)
 * - Reentrancy protection on all fund transfers
 * - Guardian dispute resolution with 72h window
 */
contract X402EscrowManager is 
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    IX402EscrowManager 
{
    using SafeERC20 for IERC20;
    
    // ============ Constants ============
    
    /// @notice Minimum escrow validity: 5 minutes
    uint256 public constant MIN_VALIDITY = 5 minutes;
    
    /// @notice Maximum escrow validity: 24 hours
    uint256 public constant MAX_VALIDITY = 24 hours;
    
    /// @notice Dispute window: 72 hours
    uint256 public constant DISPUTE_WINDOW = 72 hours;
    
    /// @notice Settlement fee: 0.05% (5 basis points)
    uint256 public constant SETTLEMENT_FEE_BPS = 5;
    
    /// @notice Basis points denominator
    uint256 private constant BPS_DENOMINATOR = 10000;
    
    /// @notice Role for dispute resolution
    bytes32 public constant RESOLVER_ROLE = keccak256("RESOLVER_ROLE");
    
    /// @notice Role for protocol administration
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    /// @notice Role for emergency pause
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    
    /// @notice Role for TEE attestation verification
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    
    // ============ Storage ============
    
    /// @notice VAMS token contract
    IERC20 public vamsToken;
    
    /// @notice Nonce registry for double-spend prevention
    IX402NonceRegistry public nonceRegistry;
    
    /// @notice Provider bond registry
    IProviderBondRegistry public bondRegistry;
    
    /// @notice Treasury address for fees
    address public treasury;
    
    /// @notice Escrows by ID
    mapping(bytes32 => Escrow) private _escrows;
    
    /// @notice Disputes by escrow ID
    mapping(bytes32 => Dispute) private _disputes;
    
    /// @notice Agent's escrow IDs
    mapping(address => bytes32[]) private _agentEscrows;
    
    /// @notice Provider's escrow IDs
    mapping(address => bytes32[]) private _providerEscrows;
    
    /// @notice Claim timestamps (for dispute window)
    mapping(bytes32 => uint256) private _claimTimestamps;
    
    /// @notice Service proofs approved by VERIFIER_ROLE
    mapping(bytes32 => bool) public verifiedProofs;
    
    /// @notice Total escrowed value
    uint256 public totalEscrowed;
    
    /// @notice Total fees collected
    uint256 public totalFeesCollected;
    
    /// @notice Total escrows created
    uint256 public escrowCount;
    
    // ============ Initializer ============
    
    /**
     * @notice Initialize the escrow manager
     * @param admin Protocol admin
     * @param _vamsToken VAMS token contract
     * @param _nonceRegistry Nonce registry contract
     * @param _bondRegistry Provider bond registry
     * @param _treasury Treasury address for fees
     */
    function initialize(
        address admin,
        address _vamsToken,
        address _nonceRegistry,
        address _bondRegistry,
        address _treasury
    ) external initializer {
        if (admin == address(0) || _vamsToken == address(0)) revert ZeroAddress();
        
        __AccessControl_init();
        __Pausable_init();
        __ReentrancyGuard_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(RESOLVER_ROLE, admin);
        
        vamsToken = IERC20(_vamsToken);
        nonceRegistry = IX402NonceRegistry(_nonceRegistry);
        bondRegistry = IProviderBondRegistry(_bondRegistry);
        treasury = _treasury;
    }
    
    // ============ View Functions ============
    
    /// @inheritdoc IX402EscrowManager
    function getEscrow(bytes32 escrowId) 
        external 
        view 
        override 
        returns (Escrow memory) 
    {
        return _escrows[escrowId];
    }
    
    /// @inheritdoc IX402EscrowManager
    function getDispute(bytes32 escrowId) 
        external 
        view 
        override 
        returns (Dispute memory) 
    {
        return _disputes[escrowId];
    }
    
    /// @inheritdoc IX402EscrowManager
    function getAgentEscrows(address agent) 
        external 
        view 
        override 
        returns (bytes32[] memory) 
    {
        return _agentEscrows[agent];
    }
    
    /// @inheritdoc IX402EscrowManager
    function getProviderEscrows(address provider) 
        external 
        view 
        override 
        returns (bytes32[] memory) 
    {
        return _providerEscrows[provider];
    }
    
    /// @inheritdoc IX402EscrowManager
    function isClaimable(bytes32 escrowId) external view override returns (bool) {
        Escrow storage escrow = _escrows[escrowId];
        return escrow.status == EscrowStatus.LOCKED && 
               block.timestamp <= escrow.expiresAt;
    }
    
    /// @inheritdoc IX402EscrowManager
    function isRefundable(bytes32 escrowId) external view override returns (bool) {
        Escrow storage escrow = _escrows[escrowId];
        return escrow.status == EscrowStatus.LOCKED && 
               block.timestamp > escrow.expiresAt;
    }
    
    /// @inheritdoc IX402EscrowManager
    function computeEscrowId(
        address agent,
        address provider,
        uint256 nonce,
        uint256 timestamp
    ) external pure override returns (bytes32) {
        return _computeEscrowId(agent, provider, nonce, timestamp);
    }
    
    // ============ Agent Functions ============
    
    /// @inheritdoc IX402EscrowManager
    function lockEscrow(
        address provider,
        uint256 amount,
        uint256 nonce,
        uint256 validForSeconds,
        bytes32 hashlock,
        bytes32 serviceType
    ) external override nonReentrant whenNotPaused returns (bytes32 escrowId) {
        // Validate inputs
        if (provider == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (validForSeconds < MIN_VALIDITY || validForSeconds > MAX_VALIDITY) {
            revert InvalidValidityPeriod(validForSeconds, MIN_VALIDITY, MAX_VALIDITY);
        }
        
        // Check provider is registered and can accept
        (bool canAccept, string memory reason) = bondRegistry.canAcceptRequest(provider, amount);
        if (!canAccept) {
            revert ProviderNotRegistered(provider);
        }
        
        // Check nonce is unused
        if (!nonceRegistry.isNonceValid(msg.sender, nonce)) {
            // Nonce already used - would be caught by NonceRegistry, but check here for better UX
            revert IX402NonceRegistry.NonceAlreadyUsed(msg.sender, nonce);
        }
        
        // Compute escrow ID
        escrowId = _computeEscrowId(msg.sender, provider, nonce, block.timestamp);
        
        // Transfer funds from agent
        vamsToken.safeTransferFrom(msg.sender, address(this), amount);
        
        // Create escrow
        uint256 expiresAt = block.timestamp + validForSeconds;
        
        _escrows[escrowId] = Escrow({
            agent: msg.sender,
            provider: provider,
            amount: amount,
            nonce: nonce,
            createdAt: block.timestamp,
            expiresAt: expiresAt,
            hashlock: hashlock,
            status: EscrowStatus.LOCKED,
            serviceType: serviceType
        });
        
        // Track in arrays
        _agentEscrows[msg.sender].push(escrowId);
        _providerEscrows[provider].push(escrowId);
        
        // Notify bond registry
        bondRegistry.acceptRequest(provider, escrowId, amount);
        
        // Update counters
        totalEscrowed += amount;
        escrowCount++;
        
        emit EscrowLocked(escrowId, msg.sender, provider, amount, expiresAt, serviceType);
        
        return escrowId;
    }
    
    /// @inheritdoc IX402EscrowManager
    function refundExpiredEscrow(bytes32 escrowId) 
        external 
        override 
        nonReentrant 
    {
        Escrow storage escrow = _escrows[escrowId];
        
        // Validate
        if (escrow.agent == address(0)) revert EscrowNotFound(escrowId);
        if (escrow.status != EscrowStatus.LOCKED) {
            revert EscrowNotRefundable(escrowId);
        }
        if (block.timestamp <= escrow.expiresAt) {
            revert EscrowNotExpired(escrowId, escrow.expiresAt);
        }
        if (msg.sender != escrow.agent) {
            revert NotEscrowParty(msg.sender);
        }
        
        // Update state
        escrow.status = EscrowStatus.REFUNDED;
        totalEscrowed -= escrow.amount;
        
        // Notify bond registry (request failed/cancelled)
        bondRegistry.completeRequest(escrow.provider, escrowId);
        
        // Refund agent
        vamsToken.safeTransfer(escrow.agent, escrow.amount);
        
        emit EscrowRefunded(escrowId, escrow.agent, escrow.amount);
    }
    
    /// @inheritdoc IX402EscrowManager
    function extendEscrow(bytes32 escrowId, uint256 additionalSeconds) 
        external 
        override
        nonReentrant
    {
        Escrow storage escrow = _escrows[escrowId];
        
        if (escrow.agent == address(0)) revert EscrowNotFound(escrowId);
        if (msg.sender != escrow.agent) revert NotEscrowParty(msg.sender);
        if (escrow.status != EscrowStatus.LOCKED) {
            revert EscrowNotClaimable(escrowId, escrow.status);
        }
        if (block.timestamp > escrow.expiresAt) {
            revert EscrowExpired(escrowId);
        }
        
        uint256 oldExpiry = escrow.expiresAt;
        uint256 newExpiry = escrow.expiresAt + additionalSeconds;
        
        // Cap at MAX_VALIDITY from now
        uint256 maxExpiry = block.timestamp + MAX_VALIDITY;
        if (newExpiry > maxExpiry) {
            newExpiry = maxExpiry;
        }
        
        escrow.expiresAt = newExpiry;
        
        emit EscrowExtended(escrowId, oldExpiry, newExpiry);
    }
    
    // ============ Provider Functions ============
    
    /// @inheritdoc IX402EscrowManager
    function claimEscrow(
        bytes32 escrowId,
        ServiceProof calldata serviceProof,
        bytes32 preimage
    ) external override nonReentrant whenNotPaused {
        Escrow storage escrow = _escrows[escrowId];
        
        // Validate escrow
        if (escrow.agent == address(0)) revert EscrowNotFound(escrowId);
        if (escrow.status != EscrowStatus.LOCKED) {
            revert EscrowNotClaimable(escrowId, escrow.status);
        }
        if (block.timestamp > escrow.expiresAt) {
            revert EscrowExpired(escrowId);
        }
        if (msg.sender != escrow.provider) {
            revert NotEscrowParty(msg.sender);
        }
        
        // Verify HTLC preimage if hashlock was set
        if (escrow.hashlock != bytes32(0)) {
            if (keccak256(abi.encodePacked(preimage)) != escrow.hashlock) {
                revert InvalidHashlock(
                    keccak256(abi.encodePacked(preimage)), 
                    escrow.hashlock
                );
            }
        }
        
        // Verify service proof was approved by a trusted verifier
        if (!verifiedProofs[escrowId]) {
            revert InvalidServiceProof();
        }
        
        // Compute receipt hash and consume nonce
        bytes32 receiptHash = keccak256(abi.encodePacked(
            escrow.agent,
            escrow.nonce,
            escrow.amount,
            escrow.provider,
            block.timestamp
        ));
        
        nonceRegistry.consumeNonce(
            escrow.agent,
            escrow.nonce,
            receiptHash,
            escrowId
        );
        
        // Calculate fee
        uint256 fee = (escrow.amount * SETTLEMENT_FEE_BPS) / BPS_DENOMINATOR;
        uint256 providerPayout = escrow.amount - fee;
        
        // Update state
        escrow.status = EscrowStatus.CLAIMED;
        _claimTimestamps[escrowId] = block.timestamp;
        totalEscrowed -= escrow.amount;
        totalFeesCollected += fee;
        
        // Complete request in bond registry
        bondRegistry.completeRequest(escrow.provider, escrowId);
        
        // Transfer fee to treasury
        if (fee > 0 && treasury != address(0)) {
            vamsToken.safeTransfer(treasury, fee);
        }
        
        // Transfer payout to provider
        vamsToken.safeTransfer(escrow.provider, providerPayout);
        
        emit EscrowClaimed(escrowId, escrow.provider, providerPayout, serviceProof.proofType);
    }
    
    // ============ Dispute Functions ============
    
    /// @inheritdoc IX402EscrowManager
    function disputeEscrow(bytes32 escrowId, bytes calldata evidence) 
        external 
        override 
    {
        Escrow storage escrow = _escrows[escrowId];
        
        if (escrow.agent == address(0)) revert EscrowNotFound(escrowId);
        if (msg.sender != escrow.agent && msg.sender != escrow.provider) {
            revert NotEscrowParty(msg.sender);
        }
        
        // Check dispute is allowed
        // Can dispute LOCKED escrows OR recently CLAIMED escrows (within dispute window)
        if (escrow.status == EscrowStatus.CLAIMED) {
            uint256 claimTime = _claimTimestamps[escrowId];
            if (block.timestamp > claimTime + DISPUTE_WINDOW) {
                revert DisputeWindowExpired(escrowId);
            }
        } else if (escrow.status != EscrowStatus.LOCKED) {
            revert EscrowNotDisputable(escrowId);
        }
        
        // Check no existing dispute
        if (_disputes[escrowId].escrowId != bytes32(0)) {
            revert DisputeAlreadyExists(escrowId);
        }
        
        // Create dispute
        _disputes[escrowId] = Dispute({
            escrowId: escrowId,
            disputer: msg.sender,
            evidence: evidence,
            filedAt: block.timestamp,
            resolved: false
        });
        
        escrow.status = EscrowStatus.DISPUTED;
        
        emit EscrowDisputed(escrowId, msg.sender, evidence);
    }
    
    /// @inheritdoc IX402EscrowManager
    function resolveDispute(
        bytes32 escrowId,
        address winner,
        uint256 agentRefund,
        uint256 providerPayout
    ) external override onlyRole(RESOLVER_ROLE) nonReentrant {
        Escrow storage escrow = _escrows[escrowId];
        Dispute storage dispute = _disputes[escrowId];
        
        if (escrow.agent == address(0)) revert EscrowNotFound(escrowId);
        if (escrow.status != EscrowStatus.DISPUTED) {
            revert EscrowNotDisputable(escrowId);
        }
        if (dispute.resolved) {
            // Already resolved
            revert EscrowNotDisputable(escrowId);
        }
        
        // Validate split
        require(
            agentRefund + providerPayout == escrow.amount,
            "Split must equal escrow amount"
        );
        require(
            winner == escrow.agent || winner == escrow.provider,
            "Winner must be party to escrow"
        );
        
        // Mark resolved
        dispute.resolved = true;
        escrow.status = EscrowStatus.RESOLVED;
        totalEscrowed -= escrow.amount;
        
        // Complete request (even if disputed)
        bondRegistry.completeRequest(escrow.provider, escrowId);
        
        // Distribute funds
        if (agentRefund > 0) {
            vamsToken.safeTransfer(escrow.agent, agentRefund);
        }
        if (providerPayout > 0) {
            vamsToken.safeTransfer(escrow.provider, providerPayout);
        }
        
        emit DisputeResolved(escrowId, winner, agentRefund, providerPayout);
    }
    
    // ============ Internal Functions ============
    
    /**
     * @dev Compute escrow ID from parameters
     */
    function _computeEscrowId(
        address agent,
        address provider,
        uint256 nonce,
        uint256 timestamp
    ) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(agent, provider, nonce, timestamp));
    }
    
    /**
     * @notice Approve a service proof for a given escrow (off-chain verification)
     * @dev Called by trusted verifier nodes after validating TEE/ZK/deterministic proofs off-chain.
     *      The verifier is responsible for actual proof validation (enclave signatures,
     *      ZK proof checks, output hash matching). This function records the approval on-chain.
     * @param escrowId The escrow ID whose service proof has been verified
     */
    function approveServiceProof(
        bytes32 escrowId
    ) external onlyRole(VERIFIER_ROLE) {
        Escrow storage escrow = _escrows[escrowId];
        if (escrow.agent == address(0)) revert EscrowNotFound(escrowId);
        if (escrow.status != EscrowStatus.LOCKED) {
            revert EscrowNotClaimable(escrowId, escrow.status);
        }
        verifiedProofs[escrowId] = true;
        emit ServiceProofApproved(escrowId, msg.sender);
    }
    
    // ============ Admin Functions ============
    
    /**
     * @notice Update treasury address
     * @param _treasury New treasury address
     */
    function setTreasury(address _treasury) external onlyRole(ADMIN_ROLE) {
        treasury = _treasury;
    }
    
    /**
     * @notice Update nonce registry
     * @param _nonceRegistry New nonce registry
     */
    function setNonceRegistry(address _nonceRegistry) external onlyRole(ADMIN_ROLE) {
        nonceRegistry = IX402NonceRegistry(_nonceRegistry);
    }
    
    /**
     * @notice Update bond registry
     * @param _bondRegistry New bond registry
     */
    function setBondRegistry(address _bondRegistry) external onlyRole(ADMIN_ROLE) {
        bondRegistry = IProviderBondRegistry(_bondRegistry);
    }
    
    /**
     * @notice Pause the contract
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }
    
    /**
     * @notice Unpause the contract
     */
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
