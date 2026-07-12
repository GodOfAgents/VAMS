// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IRegionAwareDEC} from "./IRegionAwareDEC.sol";
import {IRegionalIncentives} from "./IRegionalIncentives.sol";
import {IDynamicEmissionController} from "../governance/IDynamicEmissionController.sol";

/**
 * @title RegionAwareDEC
 * @author VAMS Protocol
 * @notice Region-weighted Dynamic Emission Controller.
 * @dev Reads live multipliers from RegionalIncentives and the global emission
 *      rate from DynamicEmissionController, then allocates epoch emission budgets
 *      proportionally across geographic regions.
 *
 *      Allocation formula per region:
 *        weightedCap   = currentCapacity × multiplierBps
 *        allocationBps = (weightedCap × 10000) / totalWeightedCap
 *        regionEmission = (epochBudget × allocationBps) / 10000
 *
 *      A per-region cap (default 30%) prevents any single region from
 *      dominating the emission budget regardless of multiplier.
 *
 *      Architecture Reference: Phase 4 (Economic Layer), Sprint 9
 */
contract RegionAwareDEC is IRegionAwareDEC, AccessControl {
    using SafeERC20 for IERC20;

    // ═══════════════════ Constants ═══════════════════

    bytes32 public constant KEEPER_ROLE = keccak256("KEEPER_ROLE");
    bytes32 public constant CONFIG_ROLE = keccak256("CONFIG_ROLE");

    /// @notice BPS denominator
    uint256 public constant BPS_DENOMINATOR = 10_000;

    /// @notice Default epoch duration: 7 days
    uint256 public constant DEFAULT_EPOCH_DURATION = 7 days;

    /// @notice Default per-region cap: 30%
    uint256 public constant DEFAULT_REGION_CAP_BPS = 3_000;

    /// @notice Absolute per-region ceiling: 30% (INV-1)
    uint256 public constant MAX_REGION_CAP_BPS = 3_000;

    /// @notice Minimum per-region cap: 5%
    uint256 public constant MIN_REGION_CAP_BPS = 500;

    // ═══════════════════ Storage ═══════════════════

    /// @notice RegionalIncentives contract
    IRegionalIncentives public regionalIncentives;

    /// @notice VAMS token for emission distribution
    IERC20 public immutable vamsToken;

    /// @notice Address of the RewardDistributor that receives emissions
    address public rewardDistributor;

    /// @notice Address of the DynamicEmissionController for global rate
    address public emissionController;

    /// @notice Current epoch ID (monotonically increasing)
    uint256 public override currentEpoch;

    /// @notice Epoch duration in seconds
    uint256 public override epochDuration;

    /// @notice Per-region allocation cap in BPS
    uint256 public override regionCapBps;

    /// @notice Timestamp of last epoch distribution
    uint256 public lastEpochDistribution;

    /// @notice Total supply snapshot for emission calculation (set at deploy)
    uint256 public totalSupplyForEmission;

    /// @notice Cached region allocations for the current epoch
    mapping(bytes32 => RegionEmissionAlloc) private _currentAllocations;

    /// @notice Epoch summaries
    mapping(uint256 => EpochSummary) private _epochSummaries;

    // ═══════════════════ Constructor ═══════════════════

    /// @notice Initialize the RegionAwareDEC contract
    /// @param admin Admin address
    /// @param _vamsToken VAMS Token address
    /// @param _regionalIncentives Regional incentives contract address
    /// @param _emissionController Global dynamic emission controller address
    /// @param _totalSupplyForEmission Initial total supply parameter for baseline calculations
    constructor(
        address admin,
        address _vamsToken,
        address _regionalIncentives,
        address _emissionController,
        uint256 _totalSupplyForEmission
    ) {
        require(admin != address(0), "Zero admin");
        require(_vamsToken != address(0), "Zero token");
        require(_regionalIncentives != address(0), "Zero regional incentives");

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(KEEPER_ROLE, admin);
        _grantRole(CONFIG_ROLE, admin);

        vamsToken = IERC20(_vamsToken);
        regionalIncentives = IRegionalIncentives(_regionalIncentives);
        emissionController = _emissionController;
        totalSupplyForEmission = _totalSupplyForEmission;

        epochDuration = DEFAULT_EPOCH_DURATION;
        regionCapBps = DEFAULT_REGION_CAP_BPS;
        lastEpochDistribution = block.timestamp;
        currentEpoch = 0;
    }

    // ═══════════════════ Config ═══════════════════

    /// @inheritdoc IRegionAwareDEC
    function setRegionalIncentives(address _regionalIncentives)
        external
        onlyRole(CONFIG_ROLE)
    {
        require(_regionalIncentives != address(0), "Zero address");
        regionalIncentives = IRegionalIncentives(_regionalIncentives);
    }

    /// @inheritdoc IRegionAwareDEC
    function setEmissionController(address _dec) external onlyRole(CONFIG_ROLE) {
        emissionController = _dec;
    }

    /// @inheritdoc IRegionAwareDEC
    function setRewardDistributor(address _rewardDistributor)
        external
        onlyRole(CONFIG_ROLE)
    {
        address old = rewardDistributor;
        rewardDistributor = _rewardDistributor;
        emit RewardDistributorUpdated(old, _rewardDistributor);
    }

    /// @inheritdoc IRegionAwareDEC
    function setRegionCap(uint256 capBps) external onlyRole(CONFIG_ROLE) {
        if (capBps < MIN_REGION_CAP_BPS || capBps > MAX_REGION_CAP_BPS) {
            revert InvalidRegionCap(capBps);
        }
        uint256 old = regionCapBps;
        regionCapBps = capBps;
        emit RegionCapUpdated(old, capBps);
    }

    /// @notice Update epoch duration
    /// @param _epochDuration The new duration in seconds (between 1 and 30 days)
    function setEpochDuration(uint256 _epochDuration) external onlyRole(CONFIG_ROLE) {
        require(_epochDuration >= 1 days && _epochDuration <= 30 days, "Invalid duration");
        epochDuration = _epochDuration;
    }

    /// @notice Update total supply snapshot for emission calculation
    /// @param _supply The new total supply for emission calculation formulas
    function setTotalSupplyForEmission(uint256 _supply) external onlyRole(CONFIG_ROLE) {
        require(_supply > 0, "Zero supply");
        totalSupplyForEmission = _supply;
    }

    // ═══════════════════ Core Logic ═══════════════════

    /// @inheritdoc IRegionAwareDEC
    function getEpochEmissionBudget() public view override returns (uint256) {
        // Read global emission rate from DEC (in BPS of annual)
        // If no DEC configured, use 200 bps (2%) as baseline
        uint256 annualRateBps = 200; // default baseline
        if (emissionController != address(0)) {
            // DynamicEmissionController stores rate in BPS (e.g. 200 = 2%)
            try IDynamicEmissionController(emissionController).currentEmissionRate()
                returns (uint256 rate)
            {
                annualRateBps = rate;
            } catch {
                // Fallback to baseline
            }
        }

        // annualEmission = totalSupply × annualRateBps / BPS_DENOMINATOR
        // epochBudget = annualEmission × epochDuration / 365.25 days
        // FIX M15: Multiply before divide to prevent truncation to zero
        uint256 epochBudget = (totalSupplyForEmission * annualRateBps * epochDuration) / (BPS_DENOMINATOR * 365.25 days);

        return epochBudget;
    }

    /// @inheritdoc IRegionAwareDEC
    function calculateRegionAllocations()
        public
        view
        override
        returns (RegionEmissionAlloc[] memory allocations)
    {
        // Enumerate all regions from RegionalIncentives
        uint256 regionCount = _getTotalRegions();
        if (regionCount == 0) {
            return new RegionEmissionAlloc[](0);
        }

        // Phase 1: collect raw weighted capacities
        RegionEmissionAlloc[] memory raw = new RegionEmissionAlloc[](regionCount);
        uint256 totalWeightedCap = 0;
        uint256 activeCount = 0;

        for (uint256 i = 0; i < regionCount; i++) {
            bytes32 regionId = _getRegionIdAt(i);

            if (!regionalIncentives.isRegionActive(regionId)) {
                continue;
            }

            IRegionalIncentives.RegionConfig memory config =
                regionalIncentives.getRegionConfig(regionId);
            uint256 multiplier = regionalIncentives.getRewardMultiplier(regionId);

            // weightedCapacity = currentCapacity × multiplierBps
            // If capacity is 0 but region is active, give a minimum weight of 1
            // to ensure bootstrapping regions get a minimal allocation
            uint256 effectiveCapacity = config.currentCapacity > 0
                ? config.currentCapacity
                : 1;
            uint256 weightedCap = effectiveCapacity * multiplier;

            raw[activeCount] = RegionEmissionAlloc({
                regionId: regionId,
                weightedCapacity: weightedCap,
                allocationBps: 0, // calculated in phase 2
                emittedThisEpoch: 0
            });

            totalWeightedCap += weightedCap;
            activeCount++;
        }

        if (activeCount == 0 || totalWeightedCap == 0) {
            return new RegionEmissionAlloc[](0);
        }

        // Phase 2: calculate proportional BPS allocations with cap enforcement
        allocations = new RegionEmissionAlloc[](activeCount);
        uint256 cappedTotal = 0;
        uint256 uncappedCount = 0;

        // First pass: identify capped regions
        for (uint256 i = 0; i < activeCount; i++) {
            uint256 rawBps = (raw[i].weightedCapacity * BPS_DENOMINATOR) / totalWeightedCap;

            if (rawBps > regionCapBps) {
                allocations[i] = RegionEmissionAlloc({
                    regionId: raw[i].regionId,
                    weightedCapacity: raw[i].weightedCapacity,
                    allocationBps: regionCapBps,
                    emittedThisEpoch: 0
                });
                cappedTotal += regionCapBps;
            } else {
                allocations[i] = RegionEmissionAlloc({
                    regionId: raw[i].regionId,
                    weightedCapacity: raw[i].weightedCapacity,
                    allocationBps: rawBps, // preliminary
                    emittedThisEpoch: 0
                });
                uncappedCount++;
            }
        }

        // Second pass: redistribute capped surplus proportionally to uncapped regions
        if (cappedTotal > 0 && uncappedCount > 0) {
            uint256 remainingBps = BPS_DENOMINATOR - cappedTotal;
            uint256 uncappedWeightedTotal = 0;

            for (uint256 i = 0; i < activeCount; i++) {
                if (allocations[i].allocationBps < regionCapBps) {
                    uncappedWeightedTotal += allocations[i].weightedCapacity;
                }
            }

            if (uncappedWeightedTotal > 0) {
                uint256 distributedBps = 0;
                uint256 lastUncappedIndex = activeCount;
                
                for (uint256 i = 0; i < activeCount; i++) {
                    if (allocations[i].allocationBps < regionCapBps) {
                        uint256 redistributedBps =
                            (allocations[i].weightedCapacity * remainingBps) / uncappedWeightedTotal;
                        allocations[i].allocationBps = redistributedBps > regionCapBps ? regionCapBps : redistributedBps;
                        distributedBps += allocations[i].allocationBps;
                        lastUncappedIndex = i;
                    }
                }
                
                // ECON07: Distribute remaining precision remainder to the last uncapped region
                if (lastUncappedIndex < activeCount && distributedBps < remainingBps) {
                    uint256 remainder = remainingBps - distributedBps;
                    if (allocations[lastUncappedIndex].allocationBps + remainder <= regionCapBps) {
                        allocations[lastUncappedIndex].allocationBps += remainder;
                    }
                }
            }
        }

        return allocations;
    }

    /// @inheritdoc IRegionAwareDEC
    function getRegionAllocation(bytes32 regionId)
        external
        view
        override
        returns (RegionEmissionAlloc memory)
    {
        return _currentAllocations[regionId];
    }

    /// @inheritdoc IRegionAwareDEC
    function distributeEpochEmissions()
        external
        override
        onlyRole(KEEPER_ROLE)
        returns (uint256 totalEmitted)
    {
        // Enforce epoch boundary
        if (block.timestamp < lastEpochDistribution + epochDuration) {
            revert EpochNotElapsed(block.timestamp, lastEpochDistribution + epochDuration);
        }

        // Calculate allocations
        RegionEmissionAlloc[] memory allocations = calculateRegionAllocations();
        if (allocations.length == 0) {
            revert NoActiveRegions();
        }

        uint256 epochBudget = getEpochEmissionBudget();

        // Distribute to reward distributor
        require(rewardDistributor != address(0), "RewardDistributor not set");

        totalEmitted = 0;

        for (uint256 i = 0; i < allocations.length; i++) {
            uint256 regionEmission = (epochBudget * allocations[i].allocationBps) / BPS_DENOMINATOR;

            allocations[i].emittedThisEpoch = regionEmission;
            totalEmitted += regionEmission;

            // Cache allocation for queries
            _currentAllocations[allocations[i].regionId] = allocations[i];
        }

        // Transfer total emission to reward distributor
        // The contract must hold sufficient VAMS tokens (pre-funded by treasury/minter)
        if (totalEmitted > 0) {
            uint256 balance = vamsToken.balanceOf(address(this));
            require(balance >= totalEmitted, "Insufficient emission balance");
            vamsToken.safeTransfer(rewardDistributor, totalEmitted);
        }

        // Record epoch
        currentEpoch++;
        _epochSummaries[currentEpoch] = EpochSummary({
            epochId: currentEpoch,
            startTime: lastEpochDistribution,
            endTime: block.timestamp,
            totalEmitted: totalEmitted,
            regionCount: allocations.length
        });

        lastEpochDistribution = block.timestamp;

        emit EpochEmissionsDistributed(currentEpoch, totalEmitted, rewardDistributor);
        emit RegionAllocationsUpdated(currentEpoch, _sumWeightedCapacity(allocations), allocations.length);

        return totalEmitted;
    }

    // ═══════════════════ View Helpers ═══════════════════

    /// @notice Get a completed epoch's summary
    /// @param epochId The ID of the epoch
    /// @return The epoch summary struct
    function getEpochSummary(uint256 epochId) external view returns (EpochSummary memory) {
        return _epochSummaries[epochId];
    }

    /// @notice Get time until next epoch distribution is allowed
    /// @return Time in seconds until the next epoch
    function timeUntilNextEpoch() external view returns (uint256) {
        uint256 nextEpochAt = lastEpochDistribution + epochDuration;
        if (block.timestamp >= nextEpochAt) return 0;
        return nextEpochAt - block.timestamp;
    }

    // ═══════════════════ Internal ═══════════════════

    function _getTotalRegions() internal view returns (uint256) {
        // RegionalIncentives exposes totalRegions()
        // We use a low-level call since the interface doesn't include it
        (bool success, bytes memory data) = address(regionalIncentives).staticcall(
            abi.encodeWithSignature("totalRegions()")
        );
        if (!success) return 0;
        return abi.decode(data, (uint256));
    }

    function _getRegionIdAt(uint256 index) internal view returns (bytes32) {
        (bool success, bytes memory data) = address(regionalIncentives).staticcall(
            abi.encodeWithSignature("regionIdAt(uint256)", index)
        );
        require(success, "regionIdAt failed");
        return abi.decode(data, (bytes32));
    }

    function _sumWeightedCapacity(RegionEmissionAlloc[] memory allocations)
        internal
        pure
        returns (uint256 total)
    {
        for (uint256 i = 0; i < allocations.length; i++) {
            total += allocations[i].weightedCapacity;
        }
    }

    /// @notice Receive function stub added for flexibility if needed later
    /// @dev Currently DEC should only receive VAMS via explicit transfer
    /// @notice Expose current emission rate (baseline or queried from the dynamic controller)
    /// @return The current annual emission rate in base points
    function currentEmissionRate() external view returns (uint256) {
        if (emissionController != address(0)) {
            try IDynamicEmissionController(emissionController).currentEmissionRate()
                returns (uint256 rate)
            {
                return rate;
            } catch {}
        }
        return 200; // baseline
    }
}
