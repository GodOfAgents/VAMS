// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IServiceBlockRegistry
 * @author VAMS Protocol
 * @notice Interface for the permissionless Service Block marketplace.
 * @dev Service Blocks are composable infrastructure packages that third-party
 *      builders register and agents can provision. Each block defines resource
 *      requirements and a revenue share for its builder.
 *
 *      Deployment metadata is stored via the VAMS DA Router (Celestia, Arweave, etc.)
 *
 *      Architecture Reference: Phase 3 (Intelligence Layer), Sprint 8
 */
interface IServiceBlockRegistry {
    // ═══════════════════ Structs ═══════════════════

    /// @notice A registered service block in the marketplace
    struct ServiceBlock {
        bytes32 blockId;                // keccak256(name + builder)
        address builder;                // Creator/maintainer address
        string name;                    // Human-readable name
        string category;                // "AI", "STORAGE", "DEFI", "NETWORK"
        string description;             // Block description
        bytes32 resourceRequirementsHash; // Hash of off-chain blueprint spec
        string deploymentCID;           // DA reference (Celestia namespace, Arweave TX, etc.)
        uint256 revenueShareBps;        // Builder's revenue share (0-5000, max 50%)
        uint256 minTrustTier;           // Required agent trust tier (0-4)
        uint256 stakedAmount;           // Builder's $VAMS stake
        bool isVerified;                // Verified by admin/DAO
        bool isActive;                  // Currently available
        uint256 registeredAt;
        uint256 totalProvisions;        // Usage counter
        bytes32 manifestHash;           // Hash of signed SkillOps manifest
        bytes32 capabilityRoot;         // Merkle root of declared capabilities
        uint256 permissionsBitmap;      // Declared capability permissions
        address manifestSigner;         // Signer that authorized the manifest
        uint256 manifestVersion;        // Monotonic manifest schema/version
        bool isQuarantined;             // Blocked from provisioning
        bytes32 quarantineReasonHash;   // Hash of quarantine evidence/reason
    }

    /// @notice SkillOps manifest metadata signed by the builder.
    struct ServiceBlockManifest {
        bytes32 manifestHash;
        bytes32 capabilityRoot;
        uint256 permissionsBitmap;
        address manifestSigner;
        uint256 manifestVersion;
    }

    /// @notice Registration payload for a Service Block listing.
    struct ServiceBlockRegistration {
        string name;
        string category;
        string description;
        bytes32 resourceRequirementsHash;
        string deploymentCID;
        uint256 revenueShareBps;
        uint256 minTrustTier;
        ServiceBlockManifest manifest;
    }

    // ═══════════════════ Events ═══════════════════

    event ServiceBlockRegistered(
        bytes32 indexed blockId,
        address indexed builder,
        string name,
        string category,
        uint256 revenueShareBps
    );

    event ServiceBlockVerified(bytes32 indexed blockId, address verifiedBy);
    event ServiceBlockDeactivated(bytes32 indexed blockId);
    event ServiceBlockActivated(bytes32 indexed blockId);
    event ServiceBlockQuarantined(bytes32 indexed blockId, bytes32 reasonHash, address indexed quarantinedBy);
    event ServiceBlockQuarantineCleared(bytes32 indexed blockId, address indexed clearedBy);

    event ServiceBlockProvisioned(
        bytes32 indexed blockId,
        address indexed agent,
        uint256 provisionCount
    );

    // ═══════════════════ Functions ═══════════════════

    /// @notice Register a new service block (requires stake)
    function registerServiceBlock(
        ServiceBlockRegistration calldata registration,
        bytes calldata manifestSignature
    ) external returns (bytes32 blockId);

    /// @notice Verify a service block (admin/DAO)
    function verifyServiceBlock(bytes32 blockId) external;

    /// @notice Deactivate a service block
    function deactivateServiceBlock(bytes32 blockId) external;

    /// @notice Quarantine a service block after SkillOps/security evidence
    function quarantineServiceBlock(bytes32 blockId, bytes32 reasonHash) external;

    /// @notice Clear a service block quarantine
    function clearServiceBlockQuarantine(bytes32 blockId) external;

    /// @notice Record a provision event (called by Composer)
    function recordProvision(bytes32 blockId, address agent) external;

    /// @notice Get a service block by ID
    function getServiceBlock(bytes32 blockId) external view returns (ServiceBlock memory);

    /// @notice Calculate builder revenue from usage fees
    function calculateBuilderRevenue(bytes32 blockId, uint256 usageFees)
        external view returns (uint256 builderShare);

    /// @notice Get the minimum stake required to register a block
    function minimumStake() external view returns (uint256);

    /// @notice Get total registered service blocks
    function totalBlocks() external view returns (uint256);
}
