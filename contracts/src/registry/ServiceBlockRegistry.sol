// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IServiceBlockRegistry} from "../interfaces/IServiceBlockRegistry.sol";

/**
 * @title ServiceBlockRegistry
 * @author VAMS Protocol
 * @notice Permissionless marketplace for composable infrastructure services.
 * @dev Builders register Service Blocks backed by $VAMS stake.
 *      Agents provision blocks through the Resource Composer, and builders
 *      earn revenue share on usage fees.
 *
 *      Deployment metadata is stored via existing DA integrations
 *      (Celestia DA, Arweave, Iagon) — not IPFS.
 *
 *      Architecture Reference: Phase 3 (Intelligence Layer), Sprint 8
 */
contract ServiceBlockRegistry is IServiceBlockRegistry, AccessControl {
    // ═══════════════════ Constants ═══════════════════

    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant COMPOSER_ROLE = keccak256("COMPOSER_ROLE");

    /// @notice Minimum $VAMS stake to register a service block
    uint256 public constant MINIMUM_STAKE = 1_000 * 1e18; // 1000 $VAMS

    /// @notice Maximum revenue share for builders (50%)
    uint256 public constant MAX_REVENUE_SHARE_BPS = 5_000;

    /// @notice Stake lock period after block deactivation (90 days)
    uint256 public constant STAKE_LOCK_PERIOD = 90 days;

    // ═══════════════════ Storage ═══════════════════

    /// @notice The $VAMS token contract
    IERC20 public immutable vamsToken;

    /// @notice Service blocks indexed by blockId
    mapping(bytes32 => ServiceBlock) private _blocks;

    /// @notice All registered block IDs (for enumeration)
    bytes32[] private _blockIds;

    /// @notice Tracks whether a blockId exists
    mapping(bytes32 => bool) private _blockExists;

    /// @notice Deactivation timestamps for stake unlock calculation
    mapping(bytes32 => uint256) private _deactivatedAt;

    // ═══════════════════ Constructor ═══════════════════

    /// @notice Initialize the ServiceBlockRegistry
    /// @param admin Address with DEFAULT_ADMIN_ROLE and VERIFIER_ROLE
    /// @param _vamsToken Address of the ERC-20 $VAMS token
    constructor(address admin, address _vamsToken) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(VERIFIER_ROLE, admin);
        vamsToken = IERC20(_vamsToken);
    }

    // ═══════════════════ Builder Functions ═══════════════════

    /// @inheritdoc IServiceBlockRegistry
    function registerServiceBlock(
        string calldata name,
        string calldata category,
        string calldata description,
        bytes32 resourceRequirementsHash,
        string calldata deploymentCID,
        uint256 revenueShareBps,
        uint256 minTrustTier
    ) external returns (bytes32 blockId) {
        require(bytes(name).length > 0, "Name required");
        require(bytes(category).length > 0, "Category required");
        require(revenueShareBps <= MAX_REVENUE_SHARE_BPS, "Revenue share too high");
        require(minTrustTier <= 4, "Invalid trust tier");

        // Generate deterministic block ID
        blockId = keccak256(abi.encodePacked(name, msg.sender));
        require(!_blockExists[blockId], "Block already registered");

        // Transfer stake from builder
        require(
            vamsToken.transferFrom(msg.sender, address(this), MINIMUM_STAKE),
            "Stake transfer failed"
        );

        // Register block
        _blocks[blockId] = ServiceBlock({
            blockId: blockId,
            builder: msg.sender,
            name: name,
            category: category,
            description: description,
            resourceRequirementsHash: resourceRequirementsHash,
            deploymentCID: deploymentCID,
            revenueShareBps: revenueShareBps,
            minTrustTier: minTrustTier,
            stakedAmount: MINIMUM_STAKE,
            isVerified: false,
            isActive: true,
            registeredAt: block.timestamp,
            totalProvisions: 0
        });

        _blockIds.push(blockId);
        _blockExists[blockId] = true;

        emit ServiceBlockRegistered(blockId, msg.sender, name, category, revenueShareBps);
        return blockId;
    }

    // ═══════════════════ Verifier Functions ═══════════════════

    /// @inheritdoc IServiceBlockRegistry
    function verifyServiceBlock(bytes32 blockId) external onlyRole(VERIFIER_ROLE) {
        require(_blockExists[blockId], "Block not found");
        require(!_blocks[blockId].isVerified, "Already verified");

        _blocks[blockId].isVerified = true;
        emit ServiceBlockVerified(blockId, msg.sender);
    }

    // ═══════════════════ Lifecycle ═══════════════════

    /// @inheritdoc IServiceBlockRegistry
    function deactivateServiceBlock(bytes32 blockId) external {
        require(_blockExists[blockId], "Block not found");
        ServiceBlock storage blk = _blocks[blockId];
        require(
            blk.builder == msg.sender || hasRole(VERIFIER_ROLE, msg.sender),
            "Not authorized"
        );
        require(blk.isActive, "Already inactive");

        blk.isActive = false;
        _deactivatedAt[blockId] = block.timestamp;
        emit ServiceBlockDeactivated(blockId);
    }

    /// @notice Builder reclaims stake after lock period
    /// @param blockId The 32-byte identifier of the service block
    function withdrawStake(bytes32 blockId) external {
        require(_blockExists[blockId], "Block not found");
        ServiceBlock storage blk = _blocks[blockId];
        require(blk.builder == msg.sender, "Not the builder");
        require(!blk.isActive, "Must deactivate first");
        require(
            block.timestamp >= _deactivatedAt[blockId] + STAKE_LOCK_PERIOD,
            "Stake still locked"
        );
        require(blk.stakedAmount > 0, "Already withdrawn");

        uint256 amount = blk.stakedAmount;
        blk.stakedAmount = 0;
        require(vamsToken.transfer(msg.sender, amount), "Transfer failed");
    }

    // ═══════════════════ Composer Integration ═══════════════════

    /// @inheritdoc IServiceBlockRegistry
    function recordProvision(bytes32 blockId, address agent)
        external
        onlyRole(COMPOSER_ROLE)
    {
        require(_blockExists[blockId], "Block not found");
        require(_blocks[blockId].isActive, "Block not active");

        _blocks[blockId].totalProvisions += 1;
        emit ServiceBlockProvisioned(blockId, agent, _blocks[blockId].totalProvisions);
    }

    // ═══════════════════ View Functions ═══════════════════

    /// @inheritdoc IServiceBlockRegistry
    function getServiceBlock(bytes32 blockId)
        external view returns (ServiceBlock memory)
    {
        require(_blockExists[blockId], "Block not found");
        return _blocks[blockId];
    }

    /// @inheritdoc IServiceBlockRegistry
    function calculateBuilderRevenue(bytes32 blockId, uint256 usageFees)
        external view returns (uint256 builderShare)
    {
        require(_blockExists[blockId], "Block not found");
        return (usageFees * _blocks[blockId].revenueShareBps) / 10_000;
    }

    /// @inheritdoc IServiceBlockRegistry
    function minimumStake() external pure returns (uint256) {
        return MINIMUM_STAKE;
    }

    /// @inheritdoc IServiceBlockRegistry
    function totalBlocks() external view returns (uint256) {
        return _blockIds.length;
    }

    /// @notice Get block ID at index (for enumeration)
    /// @param index The index to lookup
    /// @return The bytes32 identifier of the block
    function blockIdAt(uint256 index) external view returns (bytes32) {
        require(index < _blockIds.length, "Index out of bounds");
        return _blockIds[index];
    }
}
