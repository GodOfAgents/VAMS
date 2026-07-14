// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {VDSOCanaryAccess} from "./VDSOCanaryAccess.sol";
import {VDSOTypes} from "./VDSOTypes.sol";
import {VAMSObjectStore} from "./VAMSObjectStore.sol";
import {VAMSReservationManager} from "./VAMSReservationManager.sol";
import {VAMSAdapterRegistry} from "./VAMSAdapterRegistry.sol";
import {VAMSProgramRegistry} from "./VAMSProgramRegistry.sol";
import {VAMSProofRouter} from "./VAMSProofRouter.sol";
import {VAMSCapabilityRouter} from "./VAMSCapabilityRouter.sol";
import {IVAMSExecutionAdapter} from "./interfaces/IVAMSExecutionAdapter.sol";

/// @title VAMSExecutionKernel
/// @notice Coordinates the side-by-side VDSO canary without replacing legacy routing.
contract VAMSExecutionKernel is VDSOCanaryAccess, ReentrancyGuard {
    bytes32 public constant EXECUTOR_ROLE = keccak256("VDSO_EXECUTOR_ROLE");
    bytes32 public constant SEMANTIC_TRANSITION_DOMAIN = keccak256("VAMS:SEMANTIC_TRANSITION:v1");
    bytes32 public constant RECOVERY_EXECUTION_PROOF_DOMAIN = keccak256("VAMS:RECOVERY_EXECUTION_PROOF:v1");

    VAMSObjectStore public immutable objectStore;
    VAMSReservationManager public immutable reservationManager;
    VAMSAdapterRegistry public immutable adapterRegistry;
    VAMSProgramRegistry public immutable programRegistry;
    VAMSProofRouter public immutable proofRouter;
    VAMSCapabilityRouter public immutable capabilityRouter;

    mapping(bytes32 executionId => bool consumed) public executionUsed;
    mapping(bytes32 executionId => bytes32 adapterId) public executionAdapter;

    event ReservationOpened(
        bytes32 indexed reservationId,
        bytes32 indexed objectId,
        bytes32 indexed domainId,
        uint64 authorityEpoch,
        uint64 fencingToken
    );
    event TransitionExecuted(
        bytes32 indexed executionId,
        bytes32 indexed intentId,
        bytes32 indexed objectId,
        bytes32 adapterId,
        uint64 objectVersion,
        bytes32 bridgeProofHash,
        bytes32 payloadHash
    );

    error InvalidKernelConfiguration();
    error InvalidTransition();
    error ExecutionReplay(bytes32 executionId);
    error ProgramUnavailable(bytes32 programId, bytes32 verifierId);
    error DomainAuthorityMismatch(bytes32 domainId, VDSOTypes.Host requiredHost);
    error ReservationMismatch(bytes32 reservationId);
    error ObjectLocked(bytes32 objectId, bytes32 reservationId);
    error PausedTransitionRequiresReservation();
    error TransitionHashMismatch(bytes32 expectedHash, bytes32 suppliedHash);
    error StaleObjectVersion(uint64 expectedVersion, uint64 currentVersion);
    error ExistingObjectDomainMismatch(bytes32 objectDomain, bytes32 requestedDomain);
    error AdapterSettlementRejected(bytes32 adapterId);
    error InvalidCrossHostSettlement();
    error MissingRecoveryExecutionProof();
    error RecoveryExecutionProofHashMismatch(bytes32 expected, bytes32 supplied);
    error UnsupportedCanaryHostAccessMode(VDSOTypes.Host host, VDSOTypes.AccessMode accessMode);
    error UnauthorizedReservationHolder(address expected, address caller);
    error ProofNotRecorded();

    constructor(
        address admin,
        address pauser,
        address objectStoreAddress,
        address reservationManagerAddress,
        address adapterRegistryAddress,
        address programRegistryAddress,
        address proofRouterAddress,
        address capabilityRouterAddress
    ) VDSOCanaryAccess(admin, pauser) {
        if (
            objectStoreAddress.code.length == 0 || reservationManagerAddress.code.length == 0
                || adapterRegistryAddress.code.length == 0 || programRegistryAddress.code.length == 0
                || proofRouterAddress.code.length == 0 || capabilityRouterAddress.code.length == 0
        ) revert InvalidKernelConfiguration();

        objectStore = VAMSObjectStore(objectStoreAddress);
        reservationManager = VAMSReservationManager(reservationManagerAddress);
        adapterRegistry = VAMSAdapterRegistry(adapterRegistryAddress);
        programRegistry = VAMSProgramRegistry(programRegistryAddress);
        proofRouter = VAMSProofRouter(proofRouterAddress);
        capabilityRouter = VAMSCapabilityRouter(capabilityRouterAddress);
        _grantRole(EXECUTOR_ROLE, admin);
    }

    /// @notice Opens a reservation only for this kernel's authoritative host/domain.
    function beginReservation(
        bytes32 reservationId,
        bytes32 objectId,
        bytes32 domainId,
        bytes32 intentId,
        address holder,
        uint64 expiresAt,
        VDSOTypes.Host requiredHost,
        uint64 authorityEpoch
    ) external onlyRole(EXECUTOR_ROLE) whenNotPaused nonReentrant returns (uint64 fencingToken) {
        _validateCanaryHostAccessMode(requiredHost, VDSOTypes.AccessMode.RESERVE);
        _requireDomainAuthority(domainId, requiredHost, authorityEpoch);
        VAMSObjectStore.ObjectHeader memory currentObject = objectStore.getObject(objectId);
        if (currentObject.version != 0 && currentObject.domainId != domainId) {
            revert ExistingObjectDomainMismatch(currentObject.domainId, domainId);
        }
        fencingToken =
            reservationManager.reserve(reservationId, objectId, domainId, intentId, holder, authorityEpoch, expiresAt);
        emit ReservationOpened(reservationId, objectId, domainId, authorityEpoch, fencingToken);
    }

    /// @notice Verifies and records one deterministic state transition.
    /// @dev While kernel-paused, only an already-open RESERVE transition may
    ///      finish; no new non-reserved transition can enter.
    function executeTransition(
        VDSOTypes.TransitionRequest calldata request,
        bytes32[] calldata candidateAdapterIds,
        bytes calldata primaryProof,
        bytes calldata secondaryProof,
        bytes calldata adapterSettlementProof
    ) external onlyRole(EXECUTOR_ROLE) nonReentrant returns (uint64 objectVersion) {
        _validateTransition(request);
        VDSOTypes.ReservationStatus reservationStatus = _validateReservation(request);
        _validateRecoveryExecutionProof(request, reservationStatus, primaryProof);
        bytes32 selectedAdapterId = _selectAndVerifyAdapter(request, candidateAdapterIds, adapterSettlementProof);

        executionUsed[request.executionId] = true;
        executionAdapter[request.executionId] = selectedAdapterId;
        _recordProof(request, primaryProof, secondaryProof);
        _finalizeReservation(request, reservationStatus);
        objectVersion = _writeObject(request);

        _emitTransitionExecuted(request, selectedAdapterId, objectVersion);
    }

    function _validateTransition(VDSOTypes.TransitionRequest calldata request) private view {
        if (
            request.executionId == bytes32(0) || request.intentId == bytes32(0) || request.programId == bytes32(0)
                || request.objectId == bytes32(0) || request.domainId == bytes32(0)
                || request.transitionHash == bytes32(0) || request.newStateRoot == bytes32(0)
                || request.verifierId == bytes32(0)
        ) revert InvalidTransition();
        if (executionUsed[request.executionId]) revert ExecutionReplay(request.executionId);
        if (paused() && request.accessMode != VDSOTypes.AccessMode.RESERVE) {
            revert PausedTransitionRequiresReservation();
        }
        if (request.accessMode == VDSOTypes.AccessMode.READ) revert InvalidTransition();
        if (
            (request.accessMode == VDSOTypes.AccessMode.RESERVE && request.reservationHolder == address(0))
                || (request.accessMode != VDSOTypes.AccessMode.RESERVE && request.reservationHolder != address(0))
        ) revert InvalidTransition();
        _validateCanaryHostAccessMode(request.requiredHost, request.accessMode);

        _requireDomainAuthority(request.domainId, request.requiredHost, request.authorityEpoch);
        if (!programRegistry.isProgramActive(request.programId, request.verifierId)) {
            revert ProgramUnavailable(request.programId, request.verifierId);
        }

        VAMSObjectStore.ObjectHeader memory currentObject = objectStore.getObject(request.objectId);
        bytes32 expectedTransitionHash = _computeSemanticTransitionHash(request, currentObject.stateRoot);
        if (request.transitionHash != expectedTransitionHash) {
            revert TransitionHashMismatch(expectedTransitionHash, request.transitionHash);
        }
        if (request.expectedObjectVersion != currentObject.version) {
            revert StaleObjectVersion(request.expectedObjectVersion, currentObject.version);
        }
        if (currentObject.version != 0 && currentObject.domainId != request.domainId) {
            revert ExistingObjectDomainMismatch(currentObject.domainId, request.domainId);
        }
    }

    function _selectAndVerifyAdapter(
        VDSOTypes.TransitionRequest calldata request,
        bytes32[] calldata candidateAdapterIds,
        bytes calldata adapterSettlementProof
    ) private view returns (bytes32 selectedAdapterId) {
        selectedAdapterId = capabilityRouter.selectAdapter(
            candidateAdapterIds, request.requiredCapabilities, request.requiredHost, request.verifierId
        );
        _validateCrossHostSettlement(request.settlement, request.requiredHost);
        _verifyAdapterSettlement(selectedAdapterId, request, adapterSettlementProof);
    }

    function _recordProof(
        VDSOTypes.TransitionRequest calldata request,
        bytes calldata primaryProof,
        bytes calldata secondaryProof
    ) private {
        bool recorded = proofRouter.verifyAndRecord(
            request.executionId,
            request.verifierId,
            request.programId,
            request.transitionHash,
            primaryProof,
            secondaryProof
        );
        if (!recorded) revert ProofNotRecorded();
    }

    function _finalizeReservation(
        VDSOTypes.TransitionRequest calldata request,
        VDSOTypes.ReservationStatus reservationStatus
    ) private {
        if (request.accessMode != VDSOTypes.AccessMode.RESERVE) return;
        if (reservationStatus == VDSOTypes.ReservationStatus.RECOVERY_PENDING) {
            reservationManager.finalizeRecoveryCommit(
                request.reservationId,
                request.fencingToken,
                request.transitionHash,
                request.recoveryExecutionProofHash,
                request.settlement
            );
        } else {
            reservationManager.commit(
                request.reservationId, request.fencingToken, request.transitionHash, request.settlement
            );
        }
    }

    function _writeObject(VDSOTypes.TransitionRequest calldata request) private returns (uint64) {
        return objectStore.writeObject(
            request.objectId,
            request.domainId,
            request.expectedObjectVersion,
            request.newStateRoot,
            request.evidenceRoot
        );
    }

    function _requireDomainAuthority(bytes32 domainId, VDSOTypes.Host requiredHost, uint64 authorityEpoch)
        private
        view
    {
        VAMSObjectStore.DomainAuthority memory authority = objectStore.getDomainAuthority(domainId);
        if (
            !authority.enabled || authority.writer != address(this) || authority.host != requiredHost
                || requiredHost == VDSOTypes.Host.NONE || authority.epoch != authorityEpoch
        ) revert DomainAuthorityMismatch(domainId, requiredHost);
    }

    /// @notice Computes the settlement-independent semantic transition hash.
    function computeSemanticTransitionHash(VDSOTypes.TransitionRequest calldata request, bytes32 currentPreStateRoot)
        external
        pure
        returns (bytes32)
    {
        return _computeSemanticTransitionHash(request, currentPreStateRoot);
    }

    /// @notice Binds a verified late-execution proof to its semantic transition.
    function computeRecoveryExecutionProofHash(bytes32 transitionHash, bytes calldata executionProof)
        external
        pure
        returns (bytes32)
    {
        return _computeRecoveryExecutionProofHash(transitionHash, executionProof);
    }

    function _validateReservation(VDSOTypes.TransitionRequest calldata request)
        private
        view
        returns (VDSOTypes.ReservationStatus reservationStatus)
    {
        bytes32 activeId = reservationManager.activeReservation(request.objectId);
        if (request.accessMode == VDSOTypes.AccessMode.RESERVE) {
            if (request.reservationId == bytes32(0) || activeId != request.reservationId) {
                revert ReservationMismatch(request.reservationId);
            }
            VAMSReservationManager.Reservation memory reservation =
                reservationManager.getReservation(request.reservationId);
            if (
                reservation.objectId != request.objectId || reservation.intentId != request.intentId
                    || reservation.domainId != request.domainId || reservation.authorityEpoch != request.authorityEpoch
                    || reservation.fencingToken != request.fencingToken
                    || reservation.holder != request.reservationHolder
            ) revert ReservationMismatch(request.reservationId);
            if (reservation.holder != msg.sender) {
                revert UnauthorizedReservationHolder(reservation.holder, msg.sender);
            }
            reservationStatus = reservation.status;
            if (
                reservationStatus != VDSOTypes.ReservationStatus.RESERVED
                    && reservationStatus != VDSOTypes.ReservationStatus.RECOVERY_PENDING
            ) revert ReservationMismatch(request.reservationId);
            if (
                reservationStatus == VDSOTypes.ReservationStatus.RECOVERY_PENDING
                    && request.recoveryExecutionProofHash == bytes32(0)
            ) revert MissingRecoveryExecutionProof();
            if (
                reservationStatus == VDSOTypes.ReservationStatus.RESERVED
                    && request.recoveryExecutionProofHash != bytes32(0)
            ) revert ReservationMismatch(request.reservationId);
        } else {
            if (request.reservationId != bytes32(0)) {
                revert ReservationMismatch(request.reservationId);
            }
            if (activeId != bytes32(0)) revert ObjectLocked(request.objectId, activeId);
            if (request.recoveryExecutionProofHash != bytes32(0)) revert MissingRecoveryExecutionProof();
            reservationStatus = VDSOTypes.ReservationStatus.NONE;
        }
    }

    function _validateRecoveryExecutionProof(
        VDSOTypes.TransitionRequest calldata request,
        VDSOTypes.ReservationStatus reservationStatus,
        bytes calldata primaryProof
    ) private pure {
        if (reservationStatus != VDSOTypes.ReservationStatus.RECOVERY_PENDING) return;
        if (primaryProof.length == 0 || request.recoveryExecutionProofHash == bytes32(0)) {
            revert MissingRecoveryExecutionProof();
        }
        bytes32 expected = _computeRecoveryExecutionProofHash(request.transitionHash, primaryProof);
        if (request.recoveryExecutionProofHash != expected) {
            revert RecoveryExecutionProofHashMismatch(expected, request.recoveryExecutionProofHash);
        }
    }

    function _computeRecoveryExecutionProofHash(bytes32 transitionHash, bytes calldata executionProof)
        private
        pure
        returns (bytes32)
    {
        return keccak256(abi.encode(RECOVERY_EXECUTION_PROOF_DOMAIN, transitionHash, keccak256(executionProof)));
    }

    function _computeSemanticTransitionHash(VDSOTypes.TransitionRequest calldata request, bytes32 currentPreStateRoot)
        private
        pure
        returns (bytes32)
    {
        // All fields are static ABI words, so concatenating the two encoded
        // segments is byte-identical to one abi.encode call and avoids a
        // compiler stack-depth failure without changing consensus bytes.
        bytes memory identity = abi.encode(
            SEMANTIC_TRANSITION_DOMAIN,
            request.intentId,
            request.programId,
            request.objectId,
            request.domainId,
            request.authorityEpoch,
            request.reservationHolder
        );
        bytes memory effect = abi.encode(
            currentPreStateRoot,
            request.newStateRoot,
            request.evidenceRoot,
            request.expectedObjectVersion,
            request.fencingToken,
            request.accessMode,
            _wireHost(request.requiredHost),
            request.requiredCapabilities
        );
        return keccak256(bytes.concat(identity, effect));
    }

    function _wireHost(VDSOTypes.Host host) private pure returns (uint8) {
        if (host == VDSOTypes.Host.POLYGON) return 0;
        if (host == VDSOTypes.Host.CARDANO) return 1;
        revert InvalidTransition();
    }

    function _validateCrossHostSettlement(VDSOTypes.SettlementMetadata calldata settlement, VDSOTypes.Host requiredHost)
        private
        pure
    {
        if (
            settlement.schemaVersion != VDSOTypes.SETTLEMENT_SCHEMA_VERSION
                || settlement.sourceHost == VDSOTypes.Host.NONE || settlement.destinationHost == VDSOTypes.Host.NONE
                || settlement.destinationHost != requiredHost
        ) revert InvalidCrossHostSettlement();

        if (settlement.sourceHost == settlement.destinationHost) {
            if (
                settlement.sourceChainId != 0 || settlement.sourceTransactionHash != bytes32(0)
                    || settlement.settledAtHeight != 0 || settlement.bridgeProofHash != bytes32(0)
                    || settlement.payloadHash != bytes32(0)
            ) revert InvalidCrossHostSettlement();
            return;
        }
        if (
            settlement.sourceChainId == 0 || settlement.sourceTransactionHash == bytes32(0)
                || settlement.settledAtHeight == 0 || settlement.bridgeProofHash == bytes32(0)
                || settlement.payloadHash == bytes32(0) || settlement.bridgeProofHash == settlement.payloadHash
        ) revert InvalidCrossHostSettlement();
    }

    function _validateCanaryHostAccessMode(VDSOTypes.Host host, VDSOTypes.AccessMode accessMode) private pure {
        // This EVM kernel may verify Cardano evidence, but it must never write
        // a Cardano-authoritative domain. Native READ/ACCUMULATE remain on the
        // Aiken host during the initial canary.
        if (host == VDSOTypes.Host.CARDANO) revert UnsupportedCanaryHostAccessMode(host, accessMode);
    }

    function _verifyAdapterSettlement(
        bytes32 selectedAdapterId,
        VDSOTypes.TransitionRequest calldata request,
        bytes calldata adapterSettlementProof
    ) private view {
        VAMSAdapterRegistry.AdapterConfig memory config = adapterRegistry.getAdapter(selectedAdapterId);
        try IVAMSExecutionAdapter(config.adapter)
            .verifySettlement(request.transitionHash, request.settlement, adapterSettlementProof) returns (
            bool valid
        ) {
            if (!valid) revert AdapterSettlementRejected(selectedAdapterId);
        } catch {
            revert AdapterSettlementRejected(selectedAdapterId);
        }
    }

    function _emitTransitionExecuted(
        VDSOTypes.TransitionRequest calldata request,
        bytes32 selectedAdapterId,
        uint64 objectVersion
    ) private {
        emit TransitionExecuted(
            request.executionId,
            request.intentId,
            request.objectId,
            selectedAdapterId,
            objectVersion,
            request.settlement.bridgeProofHash,
            request.settlement.payloadHash
        );
    }
}
