// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

import {IVAMSHardwareRegistry} from "../interfaces/IVAMSHardwareRegistry.sol";
import {HardwareClasses} from "./HardwareClasses.sol";

/**
 * @title VAMSHardwareRegistry
 * @author VAMS Protocol
 * @notice On-chain catalogue of DePIN hardware resources with extensible class system.
 * @dev Inspired by ICN ScalerNode registration. Providers register nodes with
 *      standardized metadata (class, region, capacity, price). Sentinel nodes
 *      update benchmark scores via the SENTINEL_ROLE.
 *
 *      Key design decisions:
 *      - bytes32 class IDs (not enum) for permissionless extensibility
 *      - 7-day deregistration cooldown (aligns with ProviderBondRegistry)
 *      - UUPS upgradeable with storage gap
 *      - Pre-seeds 11 hardware classes during initialize()
 */
contract VAMSHardwareRegistry is
    Initializable,
    AccessControlUpgradeable,
    UUPSUpgradeable,
    ReentrancyGuard,
    PausableUpgradeable,
    IVAMSHardwareRegistry
{
    using SafeERC20 for IERC20;

    // ═══════════════════ Constants ═══════════════════

    /// @notice Deregistration cooldown period
    uint256 public constant DEREGISTRATION_COOLDOWN = 7 days;

    /// @notice Maximum region string length
    uint256 public constant MAX_REGION_LENGTH = 32;

    // ═══════════════════ Roles ═══════════════════

    bytes32 public constant SENTINEL_ROLE = keccak256("SENTINEL_ROLE");
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");

    // ═══════════════════ Storage ═══════════════════

    /// @notice VAMS token for collateral
    IERC20 public vamsToken;

    /// @notice Hardware class registry
    mapping(bytes32 => HardwareClassInfo) private _classes;

    /// @notice Ordered list of class IDs (for enumeration)
    bytes32[] private _classIds;

    /// @notice Node registry
    mapping(bytes32 => VAMSResourceNode) private _nodes;

    /// @notice Provider => list of node IDs
    mapping(address => bytes32[]) private _providerNodes;

    /// @notice Total registered nodes
    uint256 public totalNodes;

    /// @notice Total collateral locked
    uint256 public totalCollateral;

    /// @notice Node ID => deregistration cooldown end timestamp (0 = not requested)
    mapping(bytes32 => uint256) private _deregistrationCooldowns;

    // ═══════════════════ Initializer ═══════════════════

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the registry with pre-seeded hardware classes
     * @param admin Admin address (gets DEFAULT_ADMIN_ROLE + GOVERNANCE_ROLE)
     * @param _vamsToken VAMS token address for collateral
     */
    function initialize(address admin, address _vamsToken) public initializer {
        if (admin == address(0) || _vamsToken == address(0)) revert ZeroAddress();

        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(GOVERNANCE_ROLE, admin);

        vamsToken = IERC20(_vamsToken);

        // Pre-seed the 11 initial hardware classes
        _seedClass(HardwareClasses.GPU_H100,     "GPU_H100",     "GPU",     50_000e18, 8000);
        _seedClass(HardwareClasses.GPU_A100,     "GPU_A100",     "GPU",     25_000e18, 7500);
        _seedClass(HardwareClasses.GPU_L40S,     "GPU_L40S",     "GPU",     20_000e18, 7000);
        _seedClass(HardwareClasses.GPU_RTX_4090, "GPU_RTX_4090", "GPU",     10_000e18, 6000);
        _seedClass(HardwareClasses.CPU_EPYC,     "CPU_EPYC",     "CPU",     10_000e18, 7000);
        _seedClass(HardwareClasses.CPU_XEON,     "CPU_XEON",     "CPU",     10_000e18, 7000);
        _seedClass(HardwareClasses.STORAGE_NVME, "STORAGE_NVME", "STORAGE", 15_000e18, 8000);
        _seedClass(HardwareClasses.STORAGE_HDD,  "STORAGE_HDD",  "STORAGE",  5_000e18, 5000);
        _seedClass(HardwareClasses.NETWORK_10G,  "NETWORK_10G",  "NETWORK",  8_000e18, 7500);
        _seedClass(HardwareClasses.TEE_SGX,      "TEE_SGX",      "TEE",     30_000e18, 9000);
        _seedClass(HardwareClasses.TEE_NITRO,    "TEE_NITRO",    "TEE",     30_000e18, 9000);
    }

    // ═══════════════════ Hardware Class Management ═══════════════════

    /// @inheritdoc IVAMSHardwareRegistry
    function registerHardwareClass(
        bytes32 classId,
        string calldata name,
        string calldata category,
        uint256 minCollateral,
        uint256 minBenchmarkScore
    ) external override onlyRole(GOVERNANCE_ROLE) {
        if (_classes[classId].classId != bytes32(0)) {
            revert ClassAlreadyRegistered(classId);
        }
        if (minCollateral == 0) revert ZeroValue();

        _classes[classId] = HardwareClassInfo({
            classId: classId,
            name: name,
            category: category,
            minCollateral: minCollateral,
            minBenchmarkScore: minBenchmarkScore,
            isActive: true
        });
        _classIds.push(classId);

        emit HardwareClassRegistered(classId, name, category, minCollateral, minBenchmarkScore);
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function deactivateHardwareClass(bytes32 classId) external override onlyRole(GOVERNANCE_ROLE) {
        HardwareClassInfo storage cls = _classes[classId];
        if (cls.classId == bytes32(0)) revert ClassNotFound(classId);

        cls.isActive = false;
        emit HardwareClassDeactivated(classId);
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function updateClassCollateral(
        bytes32 classId,
        uint256 newMinCollateral
    ) external override onlyRole(GOVERNANCE_ROLE) {
        HardwareClassInfo storage cls = _classes[classId];
        if (cls.classId == bytes32(0)) revert ClassNotFound(classId);
        if (newMinCollateral == 0) revert ZeroValue();

        uint256 oldMin = cls.minCollateral;
        cls.minCollateral = newMinCollateral;
        emit HardwareClassCollateralUpdated(classId, oldMin, newMinCollateral);
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function getHardwareClass(bytes32 classId) external view override returns (HardwareClassInfo memory) {
        if (_classes[classId].classId == bytes32(0)) revert ClassNotFound(classId);
        return _classes[classId];
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function getRegisteredClassCount() external view override returns (uint256) {
        return _classIds.length;
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function getRegisteredClassId(uint256 index) external view override returns (bytes32) {
        return _classIds[index];
    }

    // ═══════════════════ Node Management ═══════════════════

    /// @inheritdoc IVAMSHardwareRegistry
    function registerNode(
        bytes32 hwClass,
        string calldata region,
        uint256 capacityUnits,
        uint256 reservationPrice,
        uint256 maxBookingDuration
    ) external override nonReentrant whenNotPaused returns (bytes32 nodeId) {
        // Validate hardware class
        HardwareClassInfo storage cls = _classes[hwClass];
        if (cls.classId == bytes32(0)) revert ClassNotFound(hwClass);
        if (!cls.isActive) revert ClassNotActive(hwClass);

        // Validate region
        bytes memory regionBytes = bytes(region);
        if (regionBytes.length == 0 || regionBytes.length > MAX_REGION_LENGTH) {
            revert InvalidRegion();
        }

        // Validate basic params
        if (capacityUnits == 0 || reservationPrice == 0) revert ZeroValue();

        // Generate deterministic node ID
        nodeId = keccak256(abi.encodePacked(msg.sender, hwClass, region, block.timestamp, totalNodes));
        if (_nodes[nodeId].registeredAt != 0) revert NodeAlreadyExists(nodeId);

        // Transfer collateral
        uint256 collateral = cls.minCollateral;
        vamsToken.safeTransferFrom(msg.sender, address(this), collateral);

        // Create node
        _nodes[nodeId] = VAMSResourceNode({
            nodeId: nodeId,
            provider: msg.sender,
            hwClass: hwClass,
            region: region,
            capacityUnits: capacityUnits,
            reservationPrice: reservationPrice,
            maxBookingDuration: maxBookingDuration,
            collateralStaked: collateral,
            isActive: true,
            registeredAt: block.timestamp,
            lastBenchmarkAt: 0,
            benchmarkScore: 0
        });

        _providerNodes[msg.sender].push(nodeId);
        totalNodes++;
        totalCollateral += collateral;

        emit NodeRegistered(nodeId, msg.sender, hwClass, region, collateral);
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function requestDeregistration(bytes32 nodeId) external override {
        VAMSResourceNode storage node = _nodes[nodeId];
        if (node.registeredAt == 0) revert NodeNotFound(nodeId);
        if (node.provider != msg.sender) revert NotNodeOwner(nodeId, msg.sender);

        uint256 cooldownEnd = block.timestamp + DEREGISTRATION_COOLDOWN;
        _deregistrationCooldowns[nodeId] = cooldownEnd;

        emit DeregistrationRequested(nodeId, cooldownEnd);
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function executeDeregistration(bytes32 nodeId) external override nonReentrant {
        VAMSResourceNode storage node = _nodes[nodeId];
        if (node.registeredAt == 0) revert NodeNotFound(nodeId);
        if (node.provider != msg.sender) revert NotNodeOwner(nodeId, msg.sender);

        uint256 cooldownEnd = _deregistrationCooldowns[nodeId];
        if (cooldownEnd == 0) revert DeregistrationNotRequested(nodeId);
        if (block.timestamp < cooldownEnd) revert CooldownNotExpired(cooldownEnd);

        // Return collateral
        uint256 collateral = node.collateralStaked;
        node.isActive = false;
        node.collateralStaked = 0;
        _deregistrationCooldowns[nodeId] = 0;

        totalCollateral -= collateral;

        if (collateral > 0) {
            vamsToken.safeTransfer(msg.sender, collateral);
        }

        emit NodeDeregistered(nodeId, msg.sender);
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function updateCapacity(bytes32 nodeId, uint256 newCapacity) external override {
        VAMSResourceNode storage node = _nodes[nodeId];
        if (node.registeredAt == 0) revert NodeNotFound(nodeId);
        if (node.provider != msg.sender) revert NotNodeOwner(nodeId, msg.sender);
        if (!node.isActive) revert NodeNotActive(nodeId);
        if (newCapacity == 0) revert ZeroValue();

        uint256 oldCapacity = node.capacityUnits;
        node.capacityUnits = newCapacity;

        emit NodeCapacityUpdated(nodeId, oldCapacity, newCapacity);
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function updatePrice(bytes32 nodeId, uint256 newPrice) external override {
        VAMSResourceNode storage node = _nodes[nodeId];
        if (node.registeredAt == 0) revert NodeNotFound(nodeId);
        if (node.provider != msg.sender) revert NotNodeOwner(nodeId, msg.sender);
        if (!node.isActive) revert NodeNotActive(nodeId);
        if (newPrice == 0) revert ZeroValue();

        uint256 oldPrice = node.reservationPrice;
        node.reservationPrice = newPrice;

        emit NodePriceUpdated(nodeId, oldPrice, newPrice);
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function updateBenchmark(
        bytes32 nodeId,
        uint256 score,
        uint256 timestamp
    ) external override onlyRole(SENTINEL_ROLE) {
        VAMSResourceNode storage node = _nodes[nodeId];
        if (node.registeredAt == 0) revert NodeNotFound(nodeId);

        node.benchmarkScore = score;
        node.lastBenchmarkAt = timestamp;

        emit BenchmarkUpdated(nodeId, score, timestamp);
    }

    // ═══════════════════ Query Functions ═══════════════════

    /// @inheritdoc IVAMSHardwareRegistry
    function getNode(bytes32 nodeId) external view override returns (VAMSResourceNode memory) {
        if (_nodes[nodeId].registeredAt == 0) revert NodeNotFound(nodeId);
        return _nodes[nodeId];
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function getNodesByProvider(address provider) external view override returns (bytes32[] memory) {
        return _providerNodes[provider];
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function getTotalNodeCount() external view override returns (uint256) {
        return totalNodes;
    }

    /// @inheritdoc IVAMSHardwareRegistry
    function isNodeHealthy(bytes32 nodeId) external view override returns (bool) {
        VAMSResourceNode storage node = _nodes[nodeId];
        if (!node.isActive || node.registeredAt == 0) return false;

        HardwareClassInfo storage cls = _classes[node.hwClass];
        // Healthy = active + benchmark score meets class minimum (if benchmarked)
        if (node.lastBenchmarkAt == 0) return true; // Not yet benchmarked, assume healthy
        return node.benchmarkScore >= cls.minBenchmarkScore;
    }

    // ═══════════════════ Internal ═══════════════════

    /**
     * @dev Seed a hardware class during initialization (no event, no role check)
     */
    function _seedClass(
        bytes32 classId,
        string memory name,
        string memory category,
        uint256 minCollateral,
        uint256 minBenchmarkScore
    ) internal {
        _classes[classId] = HardwareClassInfo({
            classId: classId,
            name: name,
            category: category,
            minCollateral: minCollateral,
            minBenchmarkScore: minBenchmarkScore,
            isActive: true
        });
        _classIds.push(classId);
    }

    /// @dev Required by UUPS
    function _authorizeUpgrade(address) internal override onlyRole(DEFAULT_ADMIN_ROLE) {}

    // ═══════════════════ Admin ═══════════════════

    /// @notice Emergency pause
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /// @notice Unpause
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ═══════════════════ Storage Gap ═══════════════════

    uint256[40] private __gap;
}
