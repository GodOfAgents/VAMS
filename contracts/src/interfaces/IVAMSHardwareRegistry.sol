// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSHardwareRegistry
 * @author VAMS Protocol
 * @notice Interface for the on-chain hardware resource catalogue.
 * @dev Inspired by ICN ScalerNode registration. Hardware classes use bytes32
 *      identifiers (keccak256 hashes) for extensibility -- new classes are
 *      added via governance without contract upgrades.
 *
 *      Architecture Reference: Phase 2 of VAMS-ICN improvement roadmap.
 */
interface IVAMSHardwareRegistry {
    // ═══════════════════ Structs ═══════════════════

    /// @notice On-chain metadata for a registered hardware class
    struct HardwareClassInfo {
        bytes32 classId; // keccak256("GPU_H100"), etc.
        string name; // Human-readable name
        string category; // "GPU", "CPU", "STORAGE", "NETWORK", "TEE"
        uint256 minCollateral; // Minimum $VAMS collateral per node
        uint256 minBenchmarkScore; // Minimum benchmark score (bps, 0-10000)
        bool isActive; // Accepting new node registrations?
    }

    /// @notice A registered hardware resource node
    struct VAMSResourceNode {
        bytes32 nodeId;
        address provider;
        bytes32 hwClass; // References HardwareClassInfo.classId
        string region; // ISO 3166 region code (e.g. "us-east-1")
        uint256 capacityUnits; // Standardized capacity per class
        uint256 reservationPrice; // $VAMS per hour (18 decimals)
        uint256 maxBookingDuration; // Maximum reservation window (seconds)
        uint256 collateralStaked; // $VAMS bonded for this node
        bool isActive;
        uint256 registeredAt;
        uint256 lastBenchmarkAt; // Last Sentinel benchmark timestamp
        uint256 benchmarkScore; // Latest benchmark score (0-10000 bps)
    }

    // ═══════════════════ Events ═══════════════════

    event HardwareClassRegistered(
        bytes32 indexed classId, string name, string category, uint256 minCollateral, uint256 minBenchmarkScore
    );

    event HardwareClassDeactivated(bytes32 indexed classId);

    event HardwareClassCollateralUpdated(bytes32 indexed classId, uint256 oldMinCollateral, uint256 newMinCollateral);

    event NodeRegistered(
        bytes32 indexed nodeId, address indexed provider, bytes32 indexed hwClass, string region, uint256 collateral
    );

    event NodeDeregistered(bytes32 indexed nodeId, address indexed provider);

    event NodeCapacityUpdated(bytes32 indexed nodeId, uint256 oldCapacity, uint256 newCapacity);

    event NodePriceUpdated(bytes32 indexed nodeId, uint256 oldPrice, uint256 newPrice);

    event BenchmarkUpdated(bytes32 indexed nodeId, uint256 score, uint256 timestamp);

    event DeregistrationRequested(bytes32 indexed nodeId, uint256 cooldownEndsAt);

    // ═══════════════════ Errors ═══════════════════

    error ClassAlreadyRegistered(bytes32 classId);
    error ClassNotFound(bytes32 classId);
    error ClassNotActive(bytes32 classId);
    error NodeNotFound(bytes32 nodeId);
    error NodeNotActive(bytes32 nodeId);
    error NotNodeOwner(bytes32 nodeId, address caller);
    error InsufficientCollateral(uint256 provided, uint256 required);
    error CooldownNotExpired(uint256 expiresAt);
    error InvalidRegion();
    error NodeAlreadyExists(bytes32 nodeId);
    error DeregistrationNotRequested(bytes32 nodeId);
    error ZeroAddress();
    error ZeroValue();

    // ═══════════════════ Hardware Class Management ═══════════════════

    /// @notice Register a new hardware class (admin/governance only)
    function registerHardwareClass(
        bytes32 classId,
        string calldata name,
        string calldata category,
        uint256 minCollateral,
        uint256 minBenchmarkScore
    ) external;

    /// @notice Deactivate a hardware class (stop new registrations)
    function deactivateHardwareClass(bytes32 classId) external;

    /// @notice Update minimum collateral for a hardware class
    function updateClassCollateral(bytes32 classId, uint256 newMinCollateral) external;

    /// @notice Get hardware class info
    function getHardwareClass(bytes32 classId) external view returns (HardwareClassInfo memory);

    /// @notice Get total number of registered hardware classes
    function getRegisteredClassCount() external view returns (uint256);

    /// @notice Get class ID at index (for enumeration)
    function getRegisteredClassId(uint256 index) external view returns (bytes32);

    // ═══════════════════ Node Management ═══════════════════

    /// @notice Register a new hardware node
    function registerNode(
        bytes32 hwClass,
        string calldata region,
        uint256 capacityUnits,
        uint256 reservationPrice,
        uint256 maxBookingDuration
    ) external returns (bytes32 nodeId);

    /// @notice Request node deregistration (starts cooldown)
    function requestDeregistration(bytes32 nodeId) external;

    /// @notice Execute node deregistration after cooldown
    function executeDeregistration(bytes32 nodeId) external;

    /// @notice Update node capacity
    function updateCapacity(bytes32 nodeId, uint256 newCapacity) external;

    /// @notice Update node hourly price
    function updatePrice(bytes32 nodeId, uint256 newPrice) external;

    /// @notice Update node benchmark score (Sentinel-only)
    function updateBenchmark(bytes32 nodeId, uint256 score, uint256 timestamp) external;

    // ═══════════════════ Query Functions ═══════════════════

    /// @notice Get node details
    function getNode(bytes32 nodeId) external view returns (VAMSResourceNode memory);

    /// @notice Get all node IDs for a provider
    function getNodesByProvider(address provider) external view returns (bytes32[] memory);

    /// @notice Get total registered node count
    function getTotalNodeCount() external view returns (uint256);

    /// @notice Check if a node is active and meeting SLA
    function isNodeHealthy(bytes32 nodeId) external view returns (bool);
}
