// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./ISecurityBudgetEnforcer.sol";

// Interfaces for external protocol components
interface IPriceOracle {
    function getVAMSPrice() external view returns (uint256);
    /// @notice Returns price and last update timestamp
    function getVAMSPriceWithTimestamp() external view returns (uint256 price, uint256 updatedAt);
}

interface ITransactionLimit {
    function setMaxTxValue(uint256 maxValue) external;
}

interface ISettlement {
    function pauseHighValueSettlements() external;
    function pauseAllSettlements() external;
}

interface IValidatorRegistry {
    function increaseStakeRequirement(uint256 percentage) external;
}

interface IMetricProvider {
    function getMetrics() external view returns (ISecurityBudgetEnforcer.ProtocolMetrics memory);
}

/**
 * @title SecurityBudgetEnforcer
 * @author VAMS Protocol
 * @notice Enforces minimum economic security relative to TVL and active operations.
 */
contract SecurityBudgetEnforcer is AccessControl, ReentrancyGuard, ISecurityBudgetEnforcer {
    bytes32 public constant KEEPER_ROLE = keccak256("KEEPER_ROLE");
    bytes32 public constant EMERGENCY_ROLE = keccak256("EMERGENCY_ROLE");

    uint256 public constant MIN_SECURITY_BUDGET_USD = 1_000_000e18;  // $1M floor
    uint256 public constant TVL_SECURITY_RATIO = 10;                 // 10% of TVL
    uint256 public constant MEV_DAYS_COVERAGE = 30;                  // 30 days of MEV
    
    /// @notice AUDIT FIX ECON06: Maximum oracle staleness (1 hour)
    uint256 public constant MAX_ORACLE_STALENESS = 1 hours;
    
    /// @notice Emitted when oracle price is stale
    event OraclePriceStale(uint256 lastUpdated, uint256 maxStaleness);

    IPriceOracle public priceOracle;
    IMetricProvider public metricProvider;
    ITransactionLimit public immutable txLimiter;
    ISettlement public immutable settlement;
    IValidatorRegistry public immutable validators;

    SecurityLevel public currentLevel = SecurityLevel.GREEN;
    uint256 public currentSecurityBudgetUSD;
    uint256 public requiredSecurityBudgetUSD;

    constructor(
        address _admin,
        address _priceOracle,
        address _metricProvider,
        address _txLimiter,
        address _settlement,
        address _validators
    ) {
        require(_admin != address(0), "Zero admin address");
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(EMERGENCY_ROLE, _admin);

        priceOracle = IPriceOracle(_priceOracle);
        metricProvider = IMetricProvider(_metricProvider);
        txLimiter = ITransactionLimit(_txLimiter);
        settlement = ISettlement(_settlement);
        validators = IValidatorRegistry(_validators);
    }

    /**
     * @notice Called periodically by keepers to assess protocol safety
     */
    function updateSecurityStatus() external override nonReentrant onlyRole(KEEPER_ROLE) {
        ProtocolMetrics memory metrics = metricProvider.getMetrics();
        
        // AUDIT FIX ECON06: Check oracle staleness before using price data.
        // Stale prices could lead to incorrect security level assessments.
        uint256 tokenPrice = 0;
        try priceOracle.getVAMSPriceWithTimestamp() returns (uint256 price, uint256 updatedAt) {
            if (block.timestamp - updatedAt > MAX_ORACLE_STALENESS) {
                emit OraclePriceStale(updatedAt, MAX_ORACLE_STALENESS);
                // Force CRITICAL level when price is stale — conservative default
                if (currentLevel != SecurityLevel.CRITICAL) {
                    SecurityLevel oldLevel = currentLevel;
                    currentLevel = SecurityLevel.CRITICAL;
                    _handleLevelTransition(oldLevel, SecurityLevel.CRITICAL);
                }
                return;
            }
            tokenPrice = price;
        } catch {
            // Fallback to basic getter if timestamped interface not available
            tokenPrice = priceOracle.getVAMSPrice();
        }

        // 1. Calculate Required Security Budget
        uint256 tvlRequirement = metrics.totalValueLocked / TVL_SECURITY_RATIO;
        uint256 mevRequirement = (metrics.dailyVolume7DayAvg * MEV_DAYS_COVERAGE) / 100;
        requiredSecurityBudgetUSD = _max3(tvlRequirement, mevRequirement, MIN_SECURITY_BUDGET_USD);

        // 2. Calculate Current Security Budget (Attack Cost)
        // BFT assumption: 1/3 + 1 validators needed to corrupt
        uint256 validatorsToCorrupt = (metrics.activeValidators / 3) + 1;
        
        uint256 avgStakePerValidator = 0;
        if (metrics.activeValidators > 0) {
            avgStakePerValidator = metrics.totalValidatorStake / metrics.activeValidators;
        }
        
        currentSecurityBudgetUSD = (validatorsToCorrupt * avgStakePerValidator * tokenPrice) / 1e18;

        // 3. Determine Security Level
        SecurityLevel newLevel = _calculateLevel(currentSecurityBudgetUSD, requiredSecurityBudgetUSD);

        emit SecurityBudgetUpdated(currentSecurityBudgetUSD, requiredSecurityBudgetUSD, newLevel);

        // 4. Trigger protective measures if condition deteriorates
        if (newLevel != currentLevel) {
            SecurityLevel oldLevel = currentLevel;
            currentLevel = newLevel;
            _handleLevelTransition(oldLevel, newLevel);
        }
    }

    function _calculateLevel(uint256 current, uint256 required) internal pure returns (SecurityLevel) {
        if (required == 0) return SecurityLevel.GREEN;

        uint256 ratio = (current * 100) / required;

        if (ratio >= 150) {
            return SecurityLevel.GREEN;
        } else if (ratio >= 100) {
            return SecurityLevel.YELLOW;
        } else if (ratio >= 75) {
            return SecurityLevel.ORANGE;
        } else if (ratio >= 50) {
            return SecurityLevel.RED;
        } else {
            return SecurityLevel.CRITICAL;
        }
    }

    function _handleLevelTransition(SecurityLevel oldLevel, SecurityLevel newLevel) internal {
        if (newLevel == SecurityLevel.ORANGE) {
            // Limit max transaction size to reduce value-at-risk
            if (address(txLimiter) != address(0)) {
                txLimiter.setMaxTxValue(1000e18); // $1000 equivalent max
            }
        } else if (newLevel == SecurityLevel.RED) {
            // Pause high value settlements and increase stake requirement (+50%)
            if (address(settlement) != address(0)) {
                settlement.pauseHighValueSettlements();
            }
            if (address(validators) != address(0)) {
                validators.increaseStakeRequirement(150); 
            }
        } else if (newLevel == SecurityLevel.CRITICAL) {
            // Full emergency pause
            if (address(settlement) != address(0)) {
                settlement.pauseAllSettlements();
            }
            if (address(validators) != address(0)) {
                validators.increaseStakeRequirement(200); 
            }
        }

        emit SecurityModeActivated(newLevel, block.timestamp);
    }

    function getCurrentSecurityLevel() external view override returns (SecurityLevel) {
        return currentLevel;
    }

    function _max3(uint256 a, uint256 b, uint256 c) internal pure returns (uint256) {
        uint256 max = a > b ? a : b;
        return max > c ? max : c;
    }

    // ============ Config Updates ============

    function setPriceOracle(address _oracle) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(_oracle != address(0), "Zero address");
        emit OracleUpdated(address(priceOracle), _oracle);
        priceOracle = IPriceOracle(_oracle);
    }

    function setMetricProvider(address _provider) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(_provider != address(0), "Zero address");
        emit MetricProviderUpdated(address(metricProvider), _provider);
        metricProvider = IMetricProvider(_provider);
    }
}
