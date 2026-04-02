// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "../interfaces/ISLAEnforcer.sol";
import "../interfaces/IVAMSHardwareRegistry.sol";
import "../slashing/VAMSSlasher.sol";

/**
 * @title SLAEnforcer
 * @notice Protocol implementation for interpreting Sentinel network telemetry 
 *         and enforcing programmable SLA slashing logic.
 */
contract SLAEnforcer is Initializable, AccessControlUpgradeable, ReentrancyGuardUpgradeable, ISLAEnforcer {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");

    IVAMSHardwareRegistry public registry;
    VAMSSlasher public slasher;

    /// @notice Registry of authorized Sentinels
    mapping(address => bool) public isSentinel;
    
    /// @notice Prevents replay of old reports for a given node
    mapping(bytes32 => uint256) public lastReportTimestamp;

    /// @notice Standard minimum benchmark score mapping to percentage out of 10000 (75%)
    uint256 public constant MIN_SLA_SCORE_BPS = 7500; 

    function initialize(
        address _admin,
        address _registry,
        address _slasher
    ) public initializer {
        __AccessControl_init();
        __ReentrancyGuard_init();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(ADMIN_ROLE, _admin);
        _grantRole(REGISTRAR_ROLE, _admin);

        registry = IVAMSHardwareRegistry(_registry);
        slasher = VAMSSlasher(_slasher);
    }

    /// @inheritdoc ISLAEnforcer
    function registerSentinel(address sentinel) external onlyRole(REGISTRAR_ROLE) {
        if (sentinel == address(0)) revert UnauthorizedSentinel();
        isSentinel[sentinel] = true;
        emit SentinelRegistered(sentinel);
    }

    function removeSentinel(address sentinel) external onlyRole(REGISTRAR_ROLE) {
        isSentinel[sentinel] = false;
        emit SentinelRemoved(sentinel);
    }

    /// @inheritdoc ISLAEnforcer
    function submitSLAReport(SLAReport calldata report, bytes calldata signature) external nonReentrant {
        // 1. Reconstruct payload hash and verify signature
        bytes32 structHash = keccak256(
            abi.encode(
                report.nodeId,
                report.timestamp,
                report.metricsScore,
                keccak256(bytes(report.challengeType)),
                report.daHeight,
                keccak256(bytes(report.daCommitment))
            )
        );
        bytes32 digest = structHash.toEthSignedMessageHash();
        address signer = digest.recover(signature);
        
        if (!isSentinel[signer]) revert UnauthorizedSentinel();

        // 2. Freshness Check
        if (report.timestamp <= lastReportTimestamp[report.nodeId]) revert ReportTooOld();
        lastReportTimestamp[report.nodeId] = report.timestamp;

        // 3. Match Hardware Registry
        IVAMSHardwareRegistry.VAMSResourceNode memory node;
        try registry.getNode(report.nodeId) returns (IVAMSHardwareRegistry.VAMSResourceNode memory n) {
            node = n;
        } catch {
            revert NodeNotRegistered();
        }

        if (node.provider == address(0)) revert NodeNotRegistered();

        // 4. Update Registry with the latest Benchmark
        try registry.updateBenchmark(report.nodeId, report.metricsScore, report.timestamp) {} catch {}

        // 5. Enforce SLA Rules (auto-slashing logic)
        if (report.metricsScore < MIN_SLA_SCORE_BPS) {
            uint256 penaltyBps = 0;
            VAMSSlasher.OffenseType oType;
            
            if (report.metricsScore == 0) {
                // Node offline or failure to respond
                oType = VAMSSlasher.OffenseType.SLA_OFFLINE;
            } else if (report.metricsScore < 1000) {
                // Score is less than 10%, implies fraud/manipulation (i.e., spoofing an H100 with a weaker GPU)
                oType = VAMSSlasher.OffenseType.SLA_FRAUD;
            } else {
                // Typical capacity degradation (thermal throttling, noisy neighbors)
                oType = VAMSSlasher.OffenseType.SLA_CAPACITY;
            }

            emit SLAViolationReported(report.nodeId, node.provider, report.challengeType, report.metricsScore);
            
            // Execute programmable slash
            try slasher.slashSLA(node.provider, oType, penaltyBps) returns (VAMSSlasher.SlashResult memory res) {
                emit SLAPenaltyEnforced(report.nodeId, node.provider, res.slashAmount);
            } catch {
                // Continue execution. Real implementation would emit a SlasherReverted event.
            }
        }
    }
}
