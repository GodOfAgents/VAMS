// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
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
contract ServiceBlockRegistry is IServiceBlockRegistry, AccessControl, EIP712 {
    // ═══════════════════ Constants ═══════════════════

    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant COMPOSER_ROLE = keccak256("COMPOSER_ROLE");

    /// @notice Minimum $VAMS stake to register a service block
    uint256 public constant MINIMUM_STAKE = 1_000 * 1e18; // 1000 $VAMS

    /// @notice Maximum revenue share for builders (50%)
    uint256 public constant MAX_REVENUE_SHARE_BPS = 5_000;

    /// @notice Stake lock period after block deactivation (90 days)
    uint256 public constant STAKE_LOCK_PERIOD = 90 days;

    /// @notice Permission bitmap mask for known SkillOps scopes
    uint256 public constant PERMISSION_EXTERNAL_READ = 1 << 0;
    uint256 public constant PERMISSION_SESSION_WRITE = 1 << 1;
    uint256 public constant PERMISSION_PERSISTENT_MUTATION = 1 << 2;
    uint256 public constant PERMISSION_WALLET_ACCESS = 1 << 3;
    uint256 public constant PERMISSION_NETWORK_EGRESS = 1 << 4;
    uint256 public constant PERMISSION_TEE_REQUIRED = 1 << 5;
    uint256 public constant VALID_PERMISSION_MASK =
        PERMISSION_EXTERNAL_READ |
        PERMISSION_SESSION_WRITE |
        PERMISSION_PERSISTENT_MUTATION |
        PERMISSION_WALLET_ACCESS |
        PERMISSION_NETWORK_EGRESS |
        PERMISSION_TEE_REQUIRED;

    bytes32 public constant SERVICE_BLOCK_MANIFEST_TYPEHASH = keccak256(
        "ServiceBlockManifest(uint256 chainId,address registry,address builder,string name,string deploymentCID,bytes32 resourceRequirementsHash,bytes32 manifestHash,bytes32 capabilityRoot,uint256 permissionsBitmap,uint256 manifestVersion)"
    );

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
    constructor(address admin, address _vamsToken) EIP712("VAMSServiceBlockRegistry", "1") {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(VERIFIER_ROLE, admin);
        vamsToken = IERC20(_vamsToken);
    }

    // ═══════════════════ Builder Functions ═══════════════════

    /// @inheritdoc IServiceBlockRegistry
    function registerServiceBlock(
        ServiceBlockRegistration calldata registration,
        bytes calldata manifestSignature
    ) external returns (bytes32 blockId) {
        require(bytes(registration.name).length > 0, "Name required");
        require(bytes(registration.category).length > 0, "Category required");
        require(registration.revenueShareBps <= MAX_REVENUE_SHARE_BPS, "Revenue share too high");
        require(registration.minTrustTier <= 4, "Invalid trust tier");
        _verifyManifest(
            msg.sender,
            registration.name,
            registration.deploymentCID,
            registration.resourceRequirementsHash,
            registration.manifest,
            manifestSignature
        );

        // Generate deterministic block ID
        blockId = keccak256(abi.encodePacked(registration.name, msg.sender));
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
            name: registration.name,
            category: registration.category,
            description: registration.description,
            resourceRequirementsHash: registration.resourceRequirementsHash,
            deploymentCID: registration.deploymentCID,
            revenueShareBps: registration.revenueShareBps,
            minTrustTier: registration.minTrustTier,
            stakedAmount: MINIMUM_STAKE,
            isVerified: false,
            isActive: true,
            registeredAt: block.timestamp,
            totalProvisions: 0,
            manifestHash: registration.manifest.manifestHash,
            capabilityRoot: registration.manifest.capabilityRoot,
            permissionsBitmap: registration.manifest.permissionsBitmap,
            manifestSigner: registration.manifest.manifestSigner,
            manifestVersion: registration.manifest.manifestVersion,
            isQuarantined: false,
            quarantineReasonHash: bytes32(0)
        });

        _blockIds.push(blockId);
        _blockExists[blockId] = true;

        emit ServiceBlockRegistered(
            blockId,
            msg.sender,
            registration.name,
            registration.category,
            registration.revenueShareBps
        );
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

    /// @inheritdoc IServiceBlockRegistry
    function quarantineServiceBlock(bytes32 blockId, bytes32 reasonHash)
        external
        onlyRole(VERIFIER_ROLE)
    {
        require(_blockExists[blockId], "Block not found");
        require(reasonHash != bytes32(0), "Reason required");
        ServiceBlock storage blk = _blocks[blockId];
        require(!blk.isQuarantined, "Already quarantined");

        blk.isQuarantined = true;
        blk.quarantineReasonHash = reasonHash;
        emit ServiceBlockQuarantined(blockId, reasonHash, msg.sender);
    }

    /// @inheritdoc IServiceBlockRegistry
    function clearServiceBlockQuarantine(bytes32 blockId)
        external
        onlyRole(VERIFIER_ROLE)
    {
        require(_blockExists[blockId], "Block not found");
        ServiceBlock storage blk = _blocks[blockId];
        require(blk.isQuarantined, "Not quarantined");

        blk.isQuarantined = false;
        blk.quarantineReasonHash = bytes32(0);
        emit ServiceBlockQuarantineCleared(blockId, msg.sender);
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
        require(!_blocks[blockId].isQuarantined, "Block quarantined");

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

    /// @notice Return the EIP-712 digest a builder signs for a Service Block manifest.
    function hashServiceBlockManifest(
        address builder,
        string calldata name,
        string calldata deploymentCID,
        bytes32 resourceRequirementsHash,
        ServiceBlockManifest calldata manifest
    ) external view returns (bytes32) {
        return _hashServiceBlockManifest(
            builder,
            name,
            deploymentCID,
            resourceRequirementsHash,
            manifest
        );
    }

    function _verifyManifest(
        address builder,
        string calldata name,
        string calldata deploymentCID,
        bytes32 resourceRequirementsHash,
        ServiceBlockManifest calldata manifest,
        bytes calldata manifestSignature
    ) internal view {
        require(manifest.manifestHash != bytes32(0), "Manifest hash required");
        require(manifest.capabilityRoot != bytes32(0), "Capability root required");
        require(manifest.manifestSigner == builder, "Manifest signer mismatch");
        require(manifest.manifestVersion > 0, "Manifest version required");
        require(manifest.permissionsBitmap != 0, "Permissions required");
        require(
            manifest.permissionsBitmap & ~VALID_PERMISSION_MASK == 0,
            "Unknown permission"
        );

        bytes32 digest = _hashServiceBlockManifest(
            builder,
            name,
            deploymentCID,
            resourceRequirementsHash,
            manifest
        );
        require(ECDSA.recover(digest, manifestSignature) == builder, "Invalid manifest signature");
    }

    function _hashServiceBlockManifest(
        address builder,
        string calldata name,
        string calldata deploymentCID,
        bytes32 resourceRequirementsHash,
        ServiceBlockManifest calldata manifest
    ) internal view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(
                SERVICE_BLOCK_MANIFEST_TYPEHASH,
                block.chainid,
                address(this),
                builder,
                keccak256(bytes(name)),
                keccak256(bytes(deploymentCID)),
                resourceRequirementsHash,
                manifest.manifestHash,
                manifest.capabilityRoot,
                manifest.permissionsBitmap,
                manifest.manifestVersion
            )
        );
        return _hashTypedDataV4(structHash);
    }
}
