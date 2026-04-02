// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SlashingParameters
 * @author VAMS Protocol
 * @notice Constants for slashing penalty calculations
 * @dev All penalties in basis points (1 bps = 0.01%)
 */
library SlashingParameters {
    // ============ LIVENESS SLASHING ============
    
    /// @notice Missed heartbeats threshold for minor offense
    uint256 internal constant SLASH_LIVENESS_THRESHOLD_LOW = 50;
    
    /// @notice Missed heartbeats threshold for medium offense
    uint256 internal constant SLASH_LIVENESS_THRESHOLD_MED = 500;
    
    /// @notice Penalty for minor liveness failure (0.5%)
    uint256 internal constant SLASH_LIVENESS_PENALTY_LOW_BPS = 50;
    
    /// @notice Penalty for medium liveness failure (2.0%)
    uint256 internal constant SLASH_LIVENESS_PENALTY_MED_BPS = 200;
    
    /// @notice Jail duration for minor offense (1 hour)
    uint256 internal constant SLASH_LIVENESS_JAIL_LOW = 1 hours;
    
    /// @notice Jail duration for medium offense (24 hours)
    uint256 internal constant SLASH_LIVENESS_JAIL_MED = 24 hours;
    
    // ============ EQUIVOCATION SLASHING ============
    
    /// @notice Penalty per equivocation offense (5.0%)
    uint256 internal constant SLASH_EQUIVOCATION_PENALTY_BPS = 500;
    
    /// @notice Jail duration for equivocation (7 days)
    uint256 internal constant SLASH_EQUIVOCATION_JAIL = 7 days;
    
    /// @notice Number of offenses before permanent tombstone
    uint256 internal constant SLASH_EQUIVOCATION_TOMBSTONE_COUNT = 3;
    
    // ============ MALICIOUS INPUT SLASHING ============
    
    /// @notice Penalty for malicious behavior (10.0%)
    uint256 internal constant SLASH_MALICIOUS_PENALTY_BPS = 1000;
    
    /// @notice Share of slash going to victim (50%)
    uint256 internal constant SLASH_MALICIOUS_VICTIM_SHARE_BPS = 5000;
    
    // ============ SLA ENFORCEMENT ============
    
    /// @notice Penalty for capacity breach (5.0%)
    uint256 internal constant SLA_CAPACITY_PENALTY_BPS = 500;
    
    /// @notice Penalty for offline status (1.0%)
    uint256 internal constant SLA_OFFLINE_PENALTY_BPS = 100;
    
    /// @notice Penalty for fraud (50.0%)
    uint256 internal constant SLA_FRAUD_PENALTY_BPS = 5000;
    
    // ============ ESCALATION MULTIPLIERS ============
    
    /// @notice Multiplier per repeat offense (1.5x)
    uint256 internal constant SLASH_REPEAT_MULTIPLIER_BPS = 15000;
    
    /// @notice Maximum escalation multiplier (5.0x)
    uint256 internal constant SLASH_MAX_MULTIPLIER_BPS = 50000;
    
    // ============ MINIMUM STAKES ============
    
    /// @notice Minimum stake for CLR operators (100,000 $VAMS)
    uint256 internal constant MIN_OPERATOR_STAKE = 100_000 * 1e18;
    
    /// @notice Minimum bond for providers (10,000 $VAMS)
    uint256 internal constant MIN_PROVIDER_BOND = 10_000 * 1e18;
    
    // ============ BASIS POINTS ============
    
    /// @notice Basis points denominator (100%)
    uint256 internal constant BPS_DENOMINATOR = 10000;
}
