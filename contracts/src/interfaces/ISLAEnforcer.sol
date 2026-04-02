// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ISLAEnforcer
 * @notice Protocol interface for enforcing Service Level Agreements based on
 *         Sentinel network performance telemetry.
 */
interface ISLAEnforcer {
    struct SLAReport {
        bytes32 nodeId;
        uint256 timestamp;
        uint256 metricsScore;
        string challengeType; // "cpu_simulated", "latency", etc.
        uint64 daHeight;
        string daCommitment;
    }

    // Events
    event SentinelRegistered(address indexed sentinel);
    event SentinelRemoved(address indexed sentinel);
    event SLAViolationReported(bytes32 indexed nodeId, address indexed provider, string challengeType, uint256 score);
    event SLAPenaltyEnforced(bytes32 indexed nodeId, address indexed provider, uint256 slashAmount);

    // Errors
    error UnauthorizedSentinel();
    error InvalidSignature();
    error ReportTooOld();
    error NodeNotRegistered();

    /**
     * @notice Registers an authorized Sentinel node that can submit SLA reports.
     * @param sentinel Address of the Sentinel
     */
    function registerSentinel(address sentinel) external;

    /**
     * @notice Submits an SLA performance report for a specific hardware node.
     * @param report The SLA metrics report
     * @param signature The EIP-712 signature from an authorized Sentinel
     */
    function submitSLAReport(SLAReport calldata report, bytes calldata signature) external;
}
