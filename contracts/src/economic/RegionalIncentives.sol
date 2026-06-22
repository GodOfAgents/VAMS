// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {IRegionalIncentives} from "./IRegionalIncentives.sol";

/**
 * @title RegionalIncentives
 * @author VAMS Protocol
 * @notice On-chain regional reward multiplier system.
 * @dev Incentivizes providers to deploy in underserved geographic regions
 *      by amplifying rewards via bootstrap multipliers that decay as
 *      regional capacity targets are met.
 *
 *      Multiplier Decay:
 *        - 0 — 50% of target:    full bootstrap multiplier
 *        - 50% — 100% of target: linear decay → 1.0× (10000 BPS)
 *        - ≥ 100% of target:     1.0× (standard rate)
 *
 *      Architecture Reference: Phase 3 (Intelligence Layer), Sprint 7
 *
 *      Admin-controlled initially, with a migration path to DAO governance.
 */
contract RegionalIncentives is IRegionalIncentives, AccessControl {
    // ═══════════════════ Constants ═══════════════════

    bytes32 public constant REGION_ADMIN_ROLE = keccak256("REGION_ADMIN_ROLE");
    bytes32 public constant CAPACITY_UPDATER_ROLE = keccak256("CAPACITY_UPDATER_ROLE");

    /// @notice 1.0× multiplier in basis points
    uint256 public constant BASE_MULTIPLIER_BPS = 10_000;

    /// @notice Maximum allowed bootstrap multiplier (5.0×)
    uint256 public constant MAX_MULTIPLIER_BPS = 50_000;

    /// @notice Decay threshold — below this fill ratio, full multiplier applies
    /// @dev Stored as BPS of target capacity (5000 = 50%)
    uint256 public constant DECAY_THRESHOLD_BPS = 5_000;

    // ═══════════════════ Storage ═══════════════════

    /// @notice Region configurations indexed by regionId
    mapping(bytes32 => RegionConfig) private _regions;

    /// @notice List of all configured region IDs (for enumeration)
    bytes32[] private _regionIds;

    /// @notice Tracks whether a regionId has been added to the list
    mapping(bytes32 => bool) private _regionExists;

    /// @notice Hardware cost baseline index by regionId (in BPS or token units)
    mapping(bytes32 => uint256) private _regionPHardware;

    /// @notice Active unique provider count by regionId
    mapping(bytes32 => uint256) private _regionProviderCount;

    event EconomicParamsUpdated(bytes32 indexed regionId, uint256 pHardware, uint256 providerCount);

    // ═══════════════════ Constructor ═══════════════════

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REGION_ADMIN_ROLE, admin);
        _grantRole(CAPACITY_UPDATER_ROLE, admin);
    }

    // ═══════════════════ Admin Functions ═══════════════════

    /// @inheritdoc IRegionalIncentives
    function setRegionConfig(
        bytes32 regionId,
        string calldata displayName,
        uint256 targetCapacity,
        uint256 bootstrapMultiplierBps
    ) external onlyRole(REGION_ADMIN_ROLE) {
        require(targetCapacity > 0, "Target capacity must be > 0");
        require(
            bootstrapMultiplierBps >= BASE_MULTIPLIER_BPS &&
            bootstrapMultiplierBps <= MAX_MULTIPLIER_BPS,
            "Multiplier must be between 1.0x and 5.0x"
        );

        RegionConfig storage region = _regions[regionId];
        region.regionId = regionId;
        region.displayName = displayName;
        region.targetCapacity = targetCapacity;
        region.bootstrapMultiplierBps = bootstrapMultiplierBps;
        region.isActive = true;

        // Track new regions
        if (!_regionExists[regionId]) {
            _regionIds.push(regionId);
            _regionExists[regionId] = true;
        }

        emit RegionConfigured(regionId, displayName, targetCapacity, bootstrapMultiplierBps);
    }

    /// @inheritdoc IRegionalIncentives
    function updateCapacity(bytes32 regionId, uint256 newCapacity)
        external
        onlyRole(CAPACITY_UPDATER_ROLE)
    {
        require(_regionExists[regionId], "Region not configured");
        uint256 oldCapacity = _regions[regionId].currentCapacity;
        _regions[regionId].currentCapacity = newCapacity;

        emit RegionCapacityUpdated(
            regionId,
            oldCapacity,
            newCapacity,
            getRewardMultiplier(regionId)
        );
    }

    /// @inheritdoc IRegionalIncentives
    function batchUpdateCapacity(
        bytes32[] calldata regionIds,
        uint256[] calldata capacities
    ) external onlyRole(CAPACITY_UPDATER_ROLE) {
        require(regionIds.length == capacities.length, "Array length mismatch");

        for (uint256 i = 0; i < regionIds.length; i++) {
            if (_regionExists[regionIds[i]]) {
                uint256 oldCap = _regions[regionIds[i]].currentCapacity;
                _regions[regionIds[i]].currentCapacity = capacities[i];

                emit RegionCapacityUpdated(
                    regionIds[i],
                    oldCap,
                    capacities[i],
                    getRewardMultiplier(regionIds[i])
                );
            }
        }
    }

    /// @inheritdoc IRegionalIncentives
    function deactivateRegion(bytes32 regionId)
        external
        onlyRole(REGION_ADMIN_ROLE)
    {
        require(_regionExists[regionId], "Region not configured");
        _regions[regionId].isActive = false;
        emit RegionDeactivated(regionId);
    }

    /// @inheritdoc IRegionalIncentives
    function activateRegion(bytes32 regionId)
        external
        onlyRole(REGION_ADMIN_ROLE)
    {
        require(_regionExists[regionId], "Region not configured");
        _regions[regionId].isActive = true;
        emit RegionActivated(regionId);
    }

    // ═══════════════════ View Functions ═══════════════════

    /// @inheritdoc IRegionalIncentives
    function getRewardMultiplier(bytes32 regionId)
        public
        view
        returns (uint256 multiplierBps)
    {
        RegionConfig storage region = _regions[regionId];

        // Unknown or inactive region → standard rate
        if (!_regionExists[regionId] || !region.isActive) {
            return BASE_MULTIPLIER_BPS;
        }

        if (region.targetCapacity == 0) {
            return BASE_MULTIPLIER_BPS;
        }

        // Calculate fill ratio in BPS (0 — 10000+)
        uint256 fillRatioBps = (region.currentCapacity * 10_000) / region.targetCapacity;

        if (fillRatioBps >= 10_000) {
            // At or above target → 1.0× standard rate
            return BASE_MULTIPLIER_BPS;
        } else if (fillRatioBps <= DECAY_THRESHOLD_BPS) {
            // Below 50% → full bootstrap multiplier
            return region.bootstrapMultiplierBps;
        } else {
            // 50% — 100%: linear decay from bootstrap → 1.0×
            // decayProgress = (fillRatioBps - 5000) / 5000, range 0 → 1
            uint256 decayNumerator = fillRatioBps - DECAY_THRESHOLD_BPS;
            uint256 decayDenominator = 10_000 - DECAY_THRESHOLD_BPS; // 5000

            uint256 multiplierRange = region.bootstrapMultiplierBps - BASE_MULTIPLIER_BPS;
            uint256 reduction = (multiplierRange * decayNumerator) / decayDenominator;

            return region.bootstrapMultiplierBps - reduction;
        }
    }

    /// @inheritdoc IRegionalIncentives
    function getRegionConfig(bytes32 regionId)
        external
        view
        returns (RegionConfig memory)
    {
        require(_regionExists[regionId], "Region not configured");
        return _regions[regionId];
    }

    /// @inheritdoc IRegionalIncentives
    function isRegionActive(bytes32 regionId) external view returns (bool) {
        return _regionExists[regionId] && _regions[regionId].isActive;
    }

    /// @notice Get total number of configured regions
    function totalRegions() external view returns (uint256) {
        return _regionIds.length;
    }

    /// @notice Get region ID at index (for enumeration)
    function regionIdAt(uint256 index) external view returns (bytes32) {
        require(index < _regionIds.length, "Index out of bounds");
        return _regionIds[index];
    }

    /// @notice Set hardware baseline and provider count for a region
    function setEconomicParams(
        bytes32 regionId,
        uint256 pHardware,
        uint256 providerCount
    ) external onlyRole(REGION_ADMIN_ROLE) {
        require(_regionExists[regionId], "Region not configured");
        _regionPHardware[regionId] = pHardware;
        _regionProviderCount[regionId] = providerCount;
        emit EconomicParamsUpdated(regionId, pHardware, providerCount);
    }

    /// @notice Get the economic parameters configured for a region
    function getEconomicParams(bytes32 regionId) external view returns (uint256 pHardware, uint256 providerCount) {
        return (_regionPHardware[regionId], _regionProviderCount[regionId]);
    }

    /// @notice Get the hybrid price floor for a region
    /// @param regionId The geographic region ID
    /// @param bidMin The lowest cleared bid in the region
    /// @return priceFloor The hybrid price floor calculation
    function getPriceFloor(bytes32 regionId, uint256 bidMin) public view returns (uint256) {
        if (!_regionExists[regionId]) {
            return bidMin;
        }

        uint256 n = _regionProviderCount[regionId];
        uint256 pHardware = _regionPHardware[regionId];

        // alpha = min(10000, n * 1000) BPS
        uint256 alphaBps = n * 1000;
        if (alphaBps > 10_000) {
            alphaBps = 10_000;
        }

        // P_floor = (alpha * bidMin + (10000 - alpha) * pHardware) / 10000
        uint256 priceFloor = (alphaBps * bidMin + (10_000 - alphaBps) * pHardware) / 10_000;
        return priceFloor;
    }
}
