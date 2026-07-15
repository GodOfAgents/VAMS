// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSFeeCollector
 * @author VAMS Protocol
 * @notice Interface for the VAMS fee collection and distribution system
 */
interface IVAMSFeeCollector {
    // ============ Enums ============

    /// @notice Distribution phases per tokenomics
    enum DistributionPhase {
        PHASE_1, // 100% burn
        PHASE_2, // 40% burn, 30% staking, 20% treasury, 10% insurance
        CUSTOM // Custom allocation
    }

    // ============ Structs ============

    /// @notice Fee distribution allocation
    struct Distribution {
        uint256 burnBps; // Buyback and burn %
        uint256 stakingBps; // Staking rewards %
        uint256 treasuryBps; // Treasury %
        uint256 insuranceBps; // Insurance fund %
    }

    // ============ Events ============

    /// @notice Emitted when fees are collected
    event FeesCollected(address indexed from, address indexed token, uint256 amount);

    /// @notice Emitted when fees are distributed
    event FeesDistributed(
        address indexed token, uint256 burned, uint256 toStaking, uint256 toTreasury, uint256 toInsurance
    );

    /// @notice Emitted when distribution is updated
    event DistributionUpdated(
        DistributionPhase phase, uint256 burnBps, uint256 stakingBps, uint256 treasuryBps, uint256 insuranceBps
    );

    /// @notice Emitted when auto-distribute threshold is updated
    event AutoDistributeThresholdUpdated(uint256 oldThreshold, uint256 newThreshold);

    /// @notice Emitted when a supported token is added/removed
    event TokenSupportUpdated(address indexed token, bool supported);

    // ============ Errors ============

    /// @notice Thrown when distribution doesn't sum to 100%
    error InvalidDistribution(uint256 total);

    /// @notice Thrown when no fees to distribute
    error NoFeesToDistribute();

    /// @notice Thrown when token is not supported
    error TokenNotSupported(address token);

    /// @notice Thrown when amount is zero
    error ZeroAmount();

    /// @notice Thrown when address is zero
    error ZeroAddress();

    // ============ Fee Collection ============

    /// @notice Collect VAMS token fees
    /// @param amount Amount to collect
    function collectFees(uint256 amount) external;

    /// @notice Collect fees from a specific token
    /// @param token Token address
    /// @param amount Amount to collect
    function collectTokenFees(address token, uint256 amount) external;

    // ============ Fee Distribution ============

    /// @notice Distribute accumulated VAMS fees
    function distributeFees() external;

    /// @notice Distribute accumulated fees for a specific token
    /// @param token Token address
    function distributeTokenFees(address token) external;

    /// @notice Distribute all accumulated fees for all supported tokens
    function distributeAllFees() external;

    // ============ Configuration ============

    /// @notice Update distribution percentages
    /// @param _burnBps Burn percentage in basis points
    /// @param _stakingBps Staking percentage in basis points
    /// @param _treasuryBps Treasury percentage in basis points
    /// @param _insuranceBps Insurance percentage in basis points
    function updateDistribution(uint256 _burnBps, uint256 _stakingBps, uint256 _treasuryBps, uint256 _insuranceBps)
        external;

    /// @notice Transition to predefined phase
    /// @param phase Target phase
    function transitionToPhase(DistributionPhase phase) external;

    /// @notice Update auto-distribute threshold
    /// @param threshold New threshold
    function setAutoDistributeThreshold(uint256 threshold) external;

    /// @notice Add/remove token support
    /// @param token Token address
    /// @param supported Whether token should be supported
    function setTokenSupport(address token, bool supported) external;

    // ============ View Functions ============

    /// @notice Get accumulated fees for VAMS token
    /// @return amount Accumulated fees
    function accumulatedFees() external view returns (uint256 amount);

    /// @notice Get accumulated fees for a specific token
    /// @param token Token address
    /// @return amount Accumulated fees
    function getAccumulatedFees(address token) external view returns (uint256 amount);

    /// @notice Get current distribution
    /// @return distribution Current distribution settings
    function getDistribution() external view returns (Distribution memory distribution);

    /// @notice Get current phase
    /// @return phase Current distribution phase
    function getCurrentPhase() external view returns (DistributionPhase phase);

    /// @notice Check if token is supported
    /// @param token Token address
    /// @return supported Whether token is supported
    function isTokenSupported(address token) external view returns (bool supported);

    /// @notice Get auto-distribute threshold
    /// @return threshold Current threshold
    function getAutoDistributeThreshold() external view returns (uint256 threshold);
}
