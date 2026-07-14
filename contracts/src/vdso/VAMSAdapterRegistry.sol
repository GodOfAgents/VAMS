// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VDSOCanaryAccess} from "./VDSOCanaryAccess.sol";
import {VDSOTypes} from "./VDSOTypes.sol";
import {IVAMSExecutionAdapter} from "./interfaces/IVAMSExecutionAdapter.sol";

/// @title VAMSAdapterRegistry
/// @notice Timelocked, capability-bound adapter registry for VDSO canaries.
contract VAMSAdapterRegistry is VDSOCanaryAccess {
    bytes32 public constant REGISTRAR_ROLE = keccak256("VDSO_ADAPTER_REGISTRAR_ROLE");
    bytes32 public constant GUARDIAN_ROLE = keccak256("VDSO_ADAPTER_GUARDIAN_ROLE");
    bytes32 public constant LIVE_EVIDENCE_MODE = keccak256("VAMS:LIVE_EVIDENCE:v1");
    uint64 public constant ACTIVATION_DELAY = 48 hours;

    struct AdapterConfig {
        address adapter;
        VDSOTypes.Host host;
        uint256 capabilityMask;
        bytes32 verifierId;
        bytes32 profileRoot;
        bytes32 conformanceRoot;
        bytes32 codeHash;
        bytes32 evidenceMode;
        bytes32 quarantineReasonHash;
        uint64 version;
        uint64 validUntil;
        uint64 activateAfter;
        VDSOTypes.AdapterStatus status;
    }

    mapping(bytes32 adapterId => AdapterConfig config) private _adapters;

    event AdapterProposed(
        bytes32 indexed adapterId, address indexed adapter, VDSOTypes.Host indexed host, uint64 activateAfter
    );
    event AdapterActivated(bytes32 indexed adapterId, uint64 indexed version);
    event AdapterQuarantined(bytes32 indexed adapterId, bytes32 indexed reasonHash);
    event AdapterReactivationScheduled(bytes32 indexed adapterId, uint64 activateAfter);
    event AdapterRetired(bytes32 indexed adapterId);

    error InvalidAdapter();
    error InvalidAdapterStatus(VDSOTypes.AdapterStatus expected, VDSOTypes.AdapterStatus actual);
    error ActivationDelayNotElapsed(uint64 activateAfter);
    error AdapterCodeChanged(bytes32 expectedCodeHash, bytes32 actualCodeHash);
    error AdapterSelfReportMismatch();
    error AdapterExpired(uint64 validUntil);

    constructor(address admin, address pauser, address guardian) VDSOCanaryAccess(admin, pauser) {
        if (guardian == address(0)) revert InvalidAddress();
        _grantRole(REGISTRAR_ROLE, admin);
        _grantRole(GUARDIAN_ROLE, guardian);
    }

    function proposeAdapter(
        bytes32 adapterId,
        address adapter,
        VDSOTypes.Host host,
        uint256 capabilityMask,
        bytes32 verifierId,
        bytes32 profileRoot,
        bytes32 conformanceRoot,
        uint64 version,
        uint64 validUntil
    ) external onlyRole(REGISTRAR_ROLE) whenNotPaused {
        if (
            adapterId == bytes32(0) || adapter.code.length == 0 || host == VDSOTypes.Host.NONE || capabilityMask == 0
                || verifierId == bytes32(0) || profileRoot == bytes32(0) || conformanceRoot == bytes32(0)
                || version == 0
        ) revert InvalidAdapter();
        if (_adapters[adapterId].status != VDSOTypes.AdapterStatus.NONE) {
            revert InvalidAdapterStatus(VDSOTypes.AdapterStatus.NONE, _adapters[adapterId].status);
        }

        uint64 activateAfter = uint64(block.timestamp) + ACTIVATION_DELAY;
        if (validUntil <= activateAfter) revert AdapterExpired(validUntil);
        if (!_selfReportMatches(adapter, host, capabilityMask)) {
            revert AdapterSelfReportMismatch();
        }

        _adapters[adapterId] = AdapterConfig({
            adapter: adapter,
            host: host,
            capabilityMask: capabilityMask,
            verifierId: verifierId,
            profileRoot: profileRoot,
            conformanceRoot: conformanceRoot,
            codeHash: adapter.codehash,
            evidenceMode: LIVE_EVIDENCE_MODE,
            quarantineReasonHash: bytes32(0),
            version: version,
            validUntil: validUntil,
            activateAfter: activateAfter,
            status: VDSOTypes.AdapterStatus.PENDING
        });

        emit AdapterProposed(adapterId, adapter, host, activateAfter);
    }

    function activateAdapter(bytes32 adapterId) external onlyRole(REGISTRAR_ROLE) whenNotPaused {
        AdapterConfig storage config = _adapters[adapterId];
        if (config.status != VDSOTypes.AdapterStatus.PENDING) {
            revert InvalidAdapterStatus(VDSOTypes.AdapterStatus.PENDING, config.status);
        }
        if (block.timestamp < config.activateAfter) {
            revert ActivationDelayNotElapsed(config.activateAfter);
        }
        if (block.timestamp >= config.validUntil) revert AdapterExpired(config.validUntil);

        bytes32 actualCodeHash = config.adapter.codehash;
        if (actualCodeHash != config.codeHash) {
            revert AdapterCodeChanged(config.codeHash, actualCodeHash);
        }
        if (!_selfReportMatches(config.adapter, config.host, config.capabilityMask)) {
            revert AdapterSelfReportMismatch();
        }

        config.status = VDSOTypes.AdapterStatus.ACTIVE;
        config.quarantineReasonHash = bytes32(0);
        emit AdapterActivated(adapterId, config.version);
    }

    /// @notice Emergency fail-closed action; no delay is applied to quarantine.
    function quarantineAdapter(bytes32 adapterId, bytes32 reasonHash) external onlyRole(GUARDIAN_ROLE) {
        AdapterConfig storage config = _adapters[adapterId];
        if (config.status != VDSOTypes.AdapterStatus.ACTIVE) {
            revert InvalidAdapterStatus(VDSOTypes.AdapterStatus.ACTIVE, config.status);
        }
        if (reasonHash == bytes32(0)) revert InvalidAdapter();

        config.status = VDSOTypes.AdapterStatus.QUARANTINED;
        config.quarantineReasonHash = reasonHash;
        emit AdapterQuarantined(adapterId, reasonHash);
    }

    /// @notice Quarantined adapters must pass the full delay again before use.
    function scheduleReactivation(bytes32 adapterId, uint64 newValidUntil)
        external
        onlyRole(REGISTRAR_ROLE)
        whenNotPaused
    {
        AdapterConfig storage config = _adapters[adapterId];
        if (config.status != VDSOTypes.AdapterStatus.QUARANTINED) {
            revert InvalidAdapterStatus(VDSOTypes.AdapterStatus.QUARANTINED, config.status);
        }
        uint64 activateAfter = uint64(block.timestamp) + ACTIVATION_DELAY;
        if (newValidUntil <= activateAfter) revert AdapterExpired(newValidUntil);

        config.status = VDSOTypes.AdapterStatus.PENDING;
        config.validUntil = newValidUntil;
        config.activateAfter = activateAfter;
        emit AdapterReactivationScheduled(adapterId, activateAfter);
    }

    function retireAdapter(bytes32 adapterId) external onlyRole(REGISTRAR_ROLE) {
        AdapterConfig storage config = _adapters[adapterId];
        if (config.status == VDSOTypes.AdapterStatus.NONE) revert InvalidAdapter();
        config.status = VDSOTypes.AdapterStatus.RETIRED;
        emit AdapterRetired(adapterId);
    }

    function isActiveAndCapable(
        bytes32 adapterId,
        uint256 requiredCapabilities,
        VDSOTypes.Host requiredHost,
        bytes32 verifierId
    ) public view returns (bool) {
        AdapterConfig memory config = _adapters[adapterId];
        if (paused() || config.status != VDSOTypes.AdapterStatus.ACTIVE) return false;
        if (block.timestamp >= config.validUntil) return false;
        if (config.host != requiredHost || config.verifierId != verifierId) return false;
        if ((config.capabilityMask & requiredCapabilities) != requiredCapabilities) return false;
        if (config.adapter.codehash != config.codeHash) return false;
        return _selfReportMatches(config.adapter, config.host, config.capabilityMask);
    }

    function getAdapter(bytes32 adapterId) external view returns (AdapterConfig memory) {
        return _adapters[adapterId];
    }

    function _selfReportMatches(address adapter, VDSOTypes.Host expectedHost, uint256 expectedCapabilities)
        private
        view
        returns (bool)
    {
        try IVAMSExecutionAdapter(adapter).host() returns (VDSOTypes.Host reportedHost) {
            if (reportedHost != expectedHost) return false;
        } catch {
            return false;
        }
        try IVAMSExecutionAdapter(adapter).capabilityMask() returns (uint256 reportedCapabilities) {
            if (reportedCapabilities != expectedCapabilities) return false;
        } catch {
            return false;
        }
        try IVAMSExecutionAdapter(adapter).evidenceMode() returns (bytes32 reportedEvidenceMode) {
            return reportedEvidenceMode == LIVE_EVIDENCE_MODE;
        } catch {
            return false;
        }
    }
}
