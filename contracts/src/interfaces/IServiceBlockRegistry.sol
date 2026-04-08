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

    event ServiceBlockProvisioned(
        bytes32 indexed blockId,
        address indexed agent,
        uint256 provisionCount
    );

    // ═══════════════════ Functions ═══════════════════

    /// @notice Register a new service block (requires stake)
    function registerServiceBlock(
        string calldata name,
        string calldata category,
        string calldata description,
        bytes32 resourceRequirementsHash,
        string calldata deploymentCID,
        uint256 revenueShareBps,
        uint256 minTrustTier
    ) external returns (bytes32 blockId);

    /// @notice Verify a service block (admin/DAO)
    function verifyServiceBlock(bytes32 blockId) external;

    /// @notice Deactivate a service block
    function deactivateServiceBlock(bytes32 blockId) external;

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
