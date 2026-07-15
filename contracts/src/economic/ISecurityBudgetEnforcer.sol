// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ISecurityBudgetEnforcer
 * @author VAMS Protocol
 * @notice Interface for enforcing economic security budgets
 */
interface ISecurityBudgetEnforcer {
    // ============ Enums ============

    enum SecurityLevel {
        GREEN, // >= 150% Required
        YELLOW, // 100-150% Required
        ORANGE, // 75-100% Required
        RED, // < 75% Required
        CRITICAL // < 50% Required
    }

    // ============ Structs ============

    struct ProtocolMetrics {
        uint256 totalValueLocked;
        uint256 dailyVolume7DayAvg;
        uint256 pendingSettlements;
        uint256 totalValidatorStake;
        uint256 activeValidators;
    }

    // ============ Events ============

    event SecurityBudgetUpdated(uint256 currentSecurityUSD, uint256 requiredSecurityUSD, SecurityLevel level);
    event SecurityModeActivated(SecurityLevel level, uint256 timestamp);
    event OracleUpdated(address oldOracle, address newOracle);
    event MetricProviderUpdated(address oldProvider, address newProvider);

    // ============ Functions ============

    /**
     * @notice Called periodically to update the protocol's security status
     */
    function updateSecurityStatus() external;

    /**
     * @notice Get current security level
     */
    function getCurrentSecurityLevel() external view returns (SecurityLevel);
}
