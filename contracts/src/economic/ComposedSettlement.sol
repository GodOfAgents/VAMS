// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IComposedSettlement} from "./IComposedSettlement.sol";
import {IProviderBondRegistry} from "./IProviderBondRegistry.sol";

/**
 * @title ComposedSettlement
 * @author VAMS Protocol
 * @notice Multi-provider payment settlement for composed blueprints.
 * @dev Implements a hybrid escrow model:
 *      - Single lock from the agent for the total amount
 *      - Per-provider independent claims (no dependency between providers)
 *      - Builder revenue share deducted from each provider's claim
 *      - Protocol fee (5 bps) deducted on claim
 *      - Unclaimed portions refundable after expiry
 *
 *      Architecture Reference: Phase 4 (Economic Layer), Sprint 10
 *
 *      // TODO [v1.1]: Refactor to UUPS upgradeable pattern (L-02 accepted risk)
 */
contract ComposedSettlement is
    IComposedSettlement,
    AccessControl,
    ReentrancyGuard,
    Pausable
{
    using SafeERC20 for IERC20;

    // ═══════════════════ Constants ═══════════════════

    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");

    /// @notice Settlement fee: 0.05% (5 basis points)
    uint256 public constant SETTLEMENT_FEE_BPS = 5;

    /// @notice BPS denominator
    uint256 public constant BPS_DENOMINATOR = 10_000;

    /// @notice Minimum validity: 5 minutes
    uint256 public constant MIN_VALIDITY = 5 minutes;

    /// @notice Maximum validity: 48 hours (slightly more than X402 for composed)
    uint256 public constant MAX_VALIDITY = 48 hours;

    /// @notice Maximum providers per composed allocation
    uint256 public constant MAX_PROVIDERS = 20;

    // ═══════════════════ Storage ═══════════════════

    /// @notice VAMS token
    IERC20 public immutable vamsToken;

    /// @notice Provider bond registry for validation
    IProviderBondRegistry public bondRegistry;

    /// @notice Fee treasury
    address public treasury;

    /// @notice Allocation counter
    uint256 public allocationCount;

    /// @notice Total escrowed value
    uint256 public totalEscrowed;

    /// @notice Total fees collected
    uint256 public totalFeesCollected;

    /// @notice Total builder revenue distributed
    uint256 public totalBuilderRevenue;

    /// @notice Allocations by ID
    mapping(bytes32 => ComposedAllocation) private _allocations;

    /// @notice Provider allocations within a composed allocation
    /// allocationId => providerIndex => ProviderAlloc
    mapping(bytes32 => mapping(uint256 => ProviderAlloc)) private _providerAllocs;

    /// @notice Agent's allocation IDs
    mapping(address => bytes32[]) private _agentAllocations;

    /// @notice Verified ZK proofs for provider claims (allocationId => providerIndex => isVerified)
    mapping(bytes32 => mapping(uint256 => bool)) public verifiedProviderProofs;

    // ═══════════════════ Constructor ═══════════════════

    /// @notice Initialize the ComposedSettlement contract
    /// @param admin Admin address
    /// @param _vamsToken VAMS ERC-20 token address
    /// @param _bondRegistry Provider bond registry address
    /// @param _treasury Protocol treasury address
    constructor(
        address admin,
        address _vamsToken,
        address _bondRegistry,
        address _treasury
    ) {
        require(admin != address(0), "Zero admin");
        require(_vamsToken != address(0), "Zero token");
        require(_bondRegistry != address(0), "Zero bondRegistry");
        require(_treasury != address(0), "Zero treasury");

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);

        vamsToken = IERC20(_vamsToken);
        bondRegistry = IProviderBondRegistry(_bondRegistry);
        treasury = _treasury;
    }

    // ═══════════════════ Core Functions ═══════════════════

    /// @inheritdoc IComposedSettlement
    function createComposedEscrow(
        address[] calldata providers,
        uint256[] calldata amounts,
        uint256 validForSeconds,
        bytes32 blueprintHash,
        bytes32 serviceBlockId,
        uint256 builderRevShareBps,
        address builderAddress
    ) external override nonReentrant whenNotPaused returns (bytes32 allocationId) {
        // Validations
        if (providers.length == 0) revert ZeroProviders();
        if (providers.length != amounts.length) revert ArrayLengthMismatch();
        if (providers.length > MAX_PROVIDERS) revert InvalidProviderIndex(providers.length, MAX_PROVIDERS);
        require(validForSeconds >= MIN_VALIDITY && validForSeconds <= MAX_VALIDITY, "Invalid validity");

        // Calculate total
        uint256 totalAmount = 0;
        for (uint256 i = 0; i < amounts.length; i++) {
            require(amounts[i] > 0, "Zero amount for provider");
            totalAmount += amounts[i];
        }

        // Validate all providers are bonded
        for (uint256 i = 0; i < providers.length; i++) {
            require(providers[i] != address(0), "Zero provider address");
            (bool canAccept, string memory reason) = bondRegistry.canAcceptRequest(providers[i], amounts[i]);
            require(canAccept, reason);
        }

        // Generate allocation ID
        allocationId = keccak256(abi.encodePacked(
            msg.sender,
            block.timestamp,
            allocationCount,
            blueprintHash
        ));

        // Transfer total from agent
        vamsToken.safeTransferFrom(msg.sender, address(this), totalAmount);

        // Create allocation
        uint256 expiresAt = block.timestamp + validForSeconds;

        _allocations[allocationId] = ComposedAllocation({
            allocationId: allocationId,
            agent: msg.sender,
            totalAmount: totalAmount,
            providerCount: providers.length,
            claimedCount: 0,
            blueprintHash: blueprintHash,
            serviceBlockId: serviceBlockId,
            createdAt: block.timestamp,
            expiresAt: expiresAt,
            status: AllocationStatus.LOCKED,
            builderRevShareBps: builderRevShareBps,
            builderAddress: builderAddress
        });

        // Create per-provider allocations
        for (uint256 i = 0; i < providers.length; i++) {
            _providerAllocs[allocationId][i] = ProviderAlloc({
                provider: providers[i],
                amount: amounts[i],
                claimed: false,
                claimedAt: 0
            });
        }

        // Track
        _agentAllocations[msg.sender].push(allocationId);
        allocationCount++;
        totalEscrowed += totalAmount;

        emit ComposedEscrowCreated(allocationId, msg.sender, totalAmount, providers.length, expiresAt);

        return allocationId;
    }

    /// @inheritdoc IComposedSettlement
    function claimProviderShare(
        bytes32 allocationId,
        uint256 providerIndex
    ) external override nonReentrant whenNotPaused {
        ComposedAllocation storage alloc = _allocations[allocationId];
        if (alloc.agent == address(0)) revert AllocationNotFound(allocationId);

        // Must be in claimable state
        if (alloc.status == AllocationStatus.EXPIRED || alloc.status == AllocationStatus.DISPUTED) {
            revert AllocationNotClaimable(allocationId);
        }

        // Check expiry
        require(block.timestamp <= alloc.expiresAt, "Allocation expired");

        // Validate index
        if (providerIndex >= alloc.providerCount) {
            revert InvalidProviderIndex(providerIndex, alloc.providerCount);
        }

        ProviderAlloc storage pAlloc = _providerAllocs[allocationId][providerIndex];

        // Check not already claimed
        if (pAlloc.claimed) revert ProviderAlreadyClaimed(allocationId, providerIndex);

        // Require ZK proof verification before claiming
        require(verifiedProviderProofs[allocationId][providerIndex], "Proof not verified");

        // Must be the correct provider
        if (msg.sender != pAlloc.provider) {
            revert ProviderMismatch(pAlloc.provider, msg.sender);
        }

        // Calculate fees
        uint256 protocolFee = (pAlloc.amount * SETTLEMENT_FEE_BPS) / BPS_DENOMINATOR;
        uint256 builderShare = 0;

        if (alloc.builderRevShareBps > 0 && alloc.builderAddress != address(0)) {
            builderShare = (pAlloc.amount * alloc.builderRevShareBps) / BPS_DENOMINATOR;
        }

        uint256 providerPayout = pAlloc.amount - protocolFee - builderShare;

        // Update state
        pAlloc.claimed = true;
        pAlloc.claimedAt = block.timestamp;
        alloc.claimedCount++;

        totalEscrowed -= pAlloc.amount;
        totalFeesCollected += protocolFee;
        totalBuilderRevenue += builderShare;

        // Update allocation status
        if (alloc.claimedCount == alloc.providerCount) {
            alloc.status = AllocationStatus.FULLY_CLAIMED;
        } else {
            alloc.status = AllocationStatus.PARTIALLY_CLAIMED;
        }

        // Transfer: protocol fee → treasury
        if (protocolFee > 0 && treasury != address(0)) {
            vamsToken.safeTransfer(treasury, protocolFee);
        }

        // Transfer: builder share → builder
        if (builderShare > 0) {
            vamsToken.safeTransfer(alloc.builderAddress, builderShare);
        }

        // Transfer: payout → provider
        vamsToken.safeTransfer(pAlloc.provider, providerPayout);

        emit ProviderShareClaimed(allocationId, pAlloc.provider, providerPayout, protocolFee, builderShare);
    }

    /// @inheritdoc IComposedSettlement
    function refundExpiredComposed(bytes32 allocationId) external override nonReentrant {
        ComposedAllocation storage alloc = _allocations[allocationId];
        if (alloc.agent == address(0)) revert AllocationNotFound(allocationId);

        // Must be expired
        if (block.timestamp <= alloc.expiresAt) {
            revert AllocationNotExpired(allocationId);
        }

        // Only agent can request refund
        require(msg.sender == alloc.agent, "Not the agent");

        // Must not be fully claimed or already expired-refunded
        require(
            alloc.status == AllocationStatus.LOCKED ||
            alloc.status == AllocationStatus.PARTIALLY_CLAIMED,
            "Cannot refund in current status"
        );

        // Calculate unclaimed amount
        uint256 refundAmount = 0;
        for (uint256 i = 0; i < alloc.providerCount; i++) {
            if (!_providerAllocs[allocationId][i].claimed) {
                refundAmount += _providerAllocs[allocationId][i].amount;
            }
        }

        // Update state
        alloc.status = AllocationStatus.EXPIRED;
        totalEscrowed -= refundAmount;

        // Refund agent
        if (refundAmount > 0) {
            vamsToken.safeTransfer(alloc.agent, refundAmount);
        }

        emit ComposedEscrowRefunded(allocationId, alloc.agent, refundAmount);
    }

    // ═══════════════════ View Functions ═══════════════════

    /// @inheritdoc IComposedSettlement
    function getComposedAllocation(bytes32 allocationId)
        external
        view
        override
        returns (ComposedAllocation memory)
    {
        return _allocations[allocationId];
    }

    /// @inheritdoc IComposedSettlement
    function getProviderAlloc(bytes32 allocationId, uint256 providerIndex)
        external
        view
        override
        returns (ProviderAlloc memory)
    {
        require(providerIndex < _allocations[allocationId].providerCount, "Index OOB");
        return _providerAllocs[allocationId][providerIndex];
    }

    /// @inheritdoc IComposedSettlement
    function isFullyClaimed(bytes32 allocationId) external view override returns (bool) {
        ComposedAllocation storage alloc = _allocations[allocationId];
        return alloc.claimedCount == alloc.providerCount;
    }

    /// @notice Get all allocation IDs for an agent
    /// @param agent The agent address
    /// @return Array of allocation IDs
    function getAgentAllocations(address agent) external view returns (bytes32[] memory) {
        return _agentAllocations[agent];
    }

    // ═══════════════════ Admin ═══════════════════

    /// @notice Update the protocol treasury
    /// @param _treasury New treasury address
    function setTreasury(address _treasury) external onlyRole(ADMIN_ROLE) {
        treasury = _treasury;
    }

    /// @notice Update the bond registry reference
    /// @param _bondRegistry New bond registry address
    function setBondRegistry(address _bondRegistry) external onlyRole(ADMIN_ROLE) {
        bondRegistry = IProviderBondRegistry(_bondRegistry);
    }

    /// @notice Pause all composed escrows
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /// @notice Unpause composed escrows
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    /// @notice Verify a provider's ZK proof (called by off-chain verification nodes)
    /// @param allocationId The composed allocation ID
    /// @param providerIndex The index of the provider
    function verifyProviderProof(bytes32 allocationId, uint256 providerIndex) external onlyRole(VERIFIER_ROLE) {
        ComposedAllocation storage alloc = _allocations[allocationId];
        require(alloc.agent != address(0), "AllocationNotFound");
        require(providerIndex < alloc.providerCount, "InvalidProviderIndex");
        verifiedProviderProofs[allocationId][providerIndex] = true;
    }
}
