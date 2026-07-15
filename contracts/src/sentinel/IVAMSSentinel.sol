// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSSentinel
 * @author VAMS Protocol
 * @notice Interface for the autonomous anomaly detector that replaces
 *         human multi-sig as the primary emergency guardian.
 * @dev Three detection layers:
 *   L1 — On-chain invariants (same-block, permissionless)
 *   L2 — Keeper consensus (sub-second, staked AI agents)
 *   L3 — Price circuit breaker (hourly oracle check)
 */
interface IVAMSSentinel {
    // ═══════════════════ Enums ═══════════════════

    /// @notice Classification of detected anomalies
    enum AnomalyType {
        TVL_DRAIN, // TVL drops > threshold in 1 block
        WHALE_EXIT, // Single withdrawal > % of pool
        BRIDGE_FLOOD, // Bridged amount > 3σ of daily avg
        PRICE_CRASH, // $VAMS price drops > threshold in window
        KEEPER_CONSENSUS // Staked keepers flag anomaly score > 80
    }

    /// @notice Protocol operational mode
    enum ProtocolMode {
        NORMAL, // All operations enabled
        RESTRICTED, // High-value operations throttled
        PAUSED // All operations paused
    }

    // ═══════════════════ Structs ═══════════════════

    /// @notice Record of a detected anomaly
    struct AnomalyReport {
        AnomalyType anomalyType;
        uint256 detectedAt;
        uint8 severity; // 1-10
        bytes32 evidenceHash;
        bool pauseTriggered;
        address reporter; // address(0) for on-chain detection
    }

    /// @notice Detection thresholds (DAO-configurable)
    struct Thresholds {
        uint16 tvlDrainBps; // TVL drop in bps per block (default 1500 = 15%)
        uint16 whaleExitBps; // Single withdrawal as % of pool (default 500 = 5%)
        uint16 bridgeFloodSigma; // Standard deviations above daily avg (default 3)
        uint16 priceCrashBps; // Price drop in bps per window (default 5000 = 50%)
        uint8 keeperConsensusMin; // Min keepers flagging (default 3)
        uint256 cooldownPeriod; // Seconds between allowed pauses (default 4 hours)
    }

    /// @notice Keeper report submitted off-chain
    struct KeeperReport {
        address keeper;
        uint8 anomalyScore; // 0-100
        bytes32 evidenceHash;
        uint256 timestamp;
    }

    // ═══════════════════ Events ═══════════════════

    event AnomalyDetected(uint256 indexed anomalyId, AnomalyType anomalyType, uint8 severity, bytes32 evidenceHash);
    event ProtocolPaused(uint256 indexed anomalyId, ProtocolMode mode);
    event ProtocolResumed(address indexed authority, uint256 indexed anomalyId);
    event KeeperReportSubmitted(address indexed keeper, uint8 score, bytes32 evidenceHash);
    event KeeperRegistered(address indexed keeper, uint256 bondAmount);
    event KeeperSlashed(address indexed keeper, uint256 slashAmount, string reason);
    event ThresholdsUpdated(Thresholds newThresholds);
    event PausableTargetAdded(address indexed target);
    event PausableTargetRemoved(address indexed target);

    // ═══════════════════ Errors ═══════════════════

    error CooldownActive(uint256 nextAllowedAt);
    error InsufficientKeeperBond(uint256 provided, uint256 required);
    error KeeperAlreadyRegistered(address keeper);
    error KeeperNotRegistered(address keeper);
    error ProtocolNotPaused();
    error ProtocolAlreadyPaused();
    error InvalidAnomalyScore(uint8 score);
    error NoPausableTargets();
    error StaleReport(uint256 reportAge, uint256 maxAge);

    // ═══════════════════ L1: On-Chain Invariants ═══════════════════

    /// @notice Permissionless check of on-chain invariants; pauses if breached
    /// @return pauseTriggered Whether the check triggered a pause
    function checkInvariantsAndPause() external returns (bool pauseTriggered);

    // ═══════════════════ L2: Keeper Consensus ═══════════════════

    /// @notice Register as a keeper by bonding $VAMS
    /// @param bondAmount Amount of $VAMS to bond (must >= MIN_KEEPER_BOND)
    function registerKeeper(uint256 bondAmount) external;

    /// @notice Submit an anomaly report (keeper only, staked)
    /// @param anomalyScore Score from 0-100 (80+ triggers consensus check)
    /// @param evidenceHash IPFS/Arweave hash of off-chain evidence
    function submitKeeperReport(uint8 anomalyScore, bytes32 evidenceHash) external;

    // ═══════════════════ L3: Price Circuit Breaker ═══════════════════

    /// @notice Update the hourly price anchor from oracle
    function updatePriceAnchor() external;

    // ═══════════════════ DAO Functions ═══════════════════

    /// @notice Resume protocol after anomaly investigation (DAO only)
    /// @param anomalyId The anomaly that triggered the pause
    function resumeProtocol(uint256 anomalyId) external;

    /// @notice Update detection thresholds (DAO only)
    /// @param newThresholds New threshold configuration
    function updateThresholds(Thresholds calldata newThresholds) external;

    // ═══════════════════ View Functions ═══════════════════

    /// @notice Get current protocol operational mode
    function getProtocolMode() external view returns (ProtocolMode);

    /// @notice Get an anomaly report by ID
    function getAnomalyReport(uint256 anomalyId) external view returns (AnomalyReport memory);

    /// @notice Get total number of recorded anomalies
    function getAnomalyCount() external view returns (uint256);

    /// @notice Get current detection thresholds
    function getThresholds() external view returns (Thresholds memory);

    /// @notice Check if an address is a registered keeper
    function isKeeper(address account) external view returns (bool);
}
