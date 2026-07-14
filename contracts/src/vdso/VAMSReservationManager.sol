// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VDSOCanaryAccess} from "./VDSOCanaryAccess.sol";
import {VDSOTypes} from "./VDSOTypes.sol";
import {IVAMSRecoveryVerifier} from "./interfaces/IVAMSRecoveryVerifier.sol";

/// @title VAMSReservationManager
/// @notice Fail-closed VDSO reservations with monotonic fencing tokens.
/// @dev Expiry makes recovery eligible but never unlocks an object. Abort
///      requires both the recovery role and a configured non-execution verifier.
contract VAMSReservationManager is VDSOCanaryAccess {
    bytes32 public constant KERNEL_ROLE = keccak256("VDSO_RESERVATION_KERNEL_ROLE");
    bytes32 public constant RECOVERY_ROLE = keccak256("VDSO_RECOVERY_ROLE");
    bytes32 public constant RECOVERY_ABORT_PROOF_DOMAIN = keccak256("VAMS:RECOVERY_ABORT_PROOF:v1");

    IVAMSRecoveryVerifier public immutable recoveryVerifier;

    struct Reservation {
        bytes32 objectId;
        bytes32 domainId;
        bytes32 intentId;
        address holder;
        uint64 authorityEpoch;
        uint64 fencingToken;
        uint64 expiresAt;
        VDSOTypes.ReservationStatus status;
        bytes32 transitionHash;
        bytes32 recoveryProofHash;
        VDSOTypes.SettlementMetadata settlement;
    }

    mapping(bytes32 reservationId => Reservation reservation) private _reservations;
    mapping(bytes32 objectId => bytes32 reservationId) public activeReservation;
    mapping(bytes32 objectId => uint64 lastFencingToken) public lastFencingToken;
    mapping(bytes32 reservationId => bool consumed) public reservationIdUsed;

    event Reserved(
        bytes32 indexed reservationId,
        bytes32 indexed objectId,
        bytes32 indexed domainId,
        bytes32 intentId,
        uint64 authorityEpoch,
        uint64 fencingToken,
        uint64 expiresAt,
        address holder
    );
    event RecoveryPending(bytes32 indexed reservationId, uint64 fencingToken);
    event ReservationCommitted(
        bytes32 indexed reservationId, bytes32 indexed transitionHash, bytes32 bridgeProofHash, bytes32 payloadHash
    );
    event RecoveryCommitFinalized(
        bytes32 indexed reservationId,
        bytes32 indexed transitionHash,
        bytes32 indexed recoveryExecutionProofHash,
        bytes32 bridgeProofHash,
        bytes32 payloadHash
    );
    event ReservationAborted(bytes32 indexed reservationId, bytes32 indexed recoveryProofHash);

    error InvalidReservation();
    error ReservationReplay(bytes32 reservationId);
    error ObjectAlreadyReserved(bytes32 objectId, bytes32 reservationId);
    error InvalidExpiry();
    error InvalidReservationStatus(VDSOTypes.ReservationStatus expected, VDSOTypes.ReservationStatus actual);
    error ReservationExpired(uint64 expiresAt);
    error RecoveryNotEligible(uint64 expiresAt);
    error InvalidFencingToken(uint64 expected, uint64 supplied);
    error MissingRecoveryProof();
    error RecoveryAbortDisabled();
    error InvalidRecoveryProof();

    constructor(address admin, address pauser, address recoveryAuthority, address recoveryVerifierAddress)
        VDSOCanaryAccess(admin, pauser)
    {
        if (recoveryAuthority == address(0)) revert InvalidAddress();
        if (recoveryVerifierAddress != address(0) && recoveryVerifierAddress.code.length == 0) revert InvalidAddress();
        recoveryVerifier = IVAMSRecoveryVerifier(recoveryVerifierAddress);
        _grantRole(RECOVERY_ROLE, recoveryAuthority);
    }

    /// @notice Opens an exclusive reservation and allocates the next fencing token.
    function reserve(
        bytes32 reservationId,
        bytes32 objectId,
        bytes32 domainId,
        bytes32 intentId,
        address holder,
        uint64 authorityEpoch,
        uint64 expiresAt
    ) external onlyRole(KERNEL_ROLE) whenNotPaused returns (uint64 fencingToken) {
        if (
            reservationId == bytes32(0) || objectId == bytes32(0) || domainId == bytes32(0) || intentId == bytes32(0)
                || holder == address(0) || authorityEpoch == 0
        ) {
            revert InvalidReservation();
        }
        if (reservationIdUsed[reservationId]) revert ReservationReplay(reservationId);
        if (expiresAt <= block.timestamp) revert InvalidExpiry();

        bytes32 current = activeReservation[objectId];
        if (current != bytes32(0)) revert ObjectAlreadyReserved(objectId, current);

        fencingToken = lastFencingToken[objectId] + 1;
        lastFencingToken[objectId] = fencingToken;
        reservationIdUsed[reservationId] = true;
        activeReservation[objectId] = reservationId;
        _reservations[reservationId] = Reservation({
            objectId: objectId,
            domainId: domainId,
            intentId: intentId,
            holder: holder,
            authorityEpoch: authorityEpoch,
            fencingToken: fencingToken,
            expiresAt: expiresAt,
            status: VDSOTypes.ReservationStatus.RESERVED,
            transitionHash: bytes32(0),
            recoveryProofHash: bytes32(0),
            settlement: VDSOTypes.SettlementMetadata({
                schemaVersion: VDSOTypes.SETTLEMENT_SCHEMA_VERSION,
                sourceHost: VDSOTypes.Host.NONE,
                destinationHost: VDSOTypes.Host.NONE,
                sourceChainId: 0,
                sourceTransactionHash: bytes32(0),
                settledAtHeight: 0,
                bridgeProofHash: bytes32(0),
                payloadHash: bytes32(0)
            })
        });

        emit Reserved(reservationId, objectId, domainId, intentId, authorityEpoch, fencingToken, expiresAt, holder);
    }

    /// @notice Marks an expired reservation as recovery-pending without unlocking it.
    function markRecoveryPending(bytes32 reservationId) external {
        Reservation storage reservation = _reservations[reservationId];
        if (reservation.status != VDSOTypes.ReservationStatus.RESERVED) {
            revert InvalidReservationStatus(VDSOTypes.ReservationStatus.RESERVED, reservation.status);
        }
        if (block.timestamp < reservation.expiresAt) {
            revert RecoveryNotEligible(reservation.expiresAt);
        }

        reservation.status = VDSOTypes.ReservationStatus.RECOVERY_PENDING;
        emit RecoveryPending(reservationId, reservation.fencingToken);
    }

    /// @notice Commits a live reservation. Expired reservations must recover instead.
    function commit(
        bytes32 reservationId,
        uint64 fencingToken,
        bytes32 transitionHash,
        VDSOTypes.SettlementMetadata calldata settlement
    ) external onlyRole(KERNEL_ROLE) {
        Reservation storage reservation = _reservations[reservationId];
        if (reservation.status != VDSOTypes.ReservationStatus.RESERVED) {
            revert InvalidReservationStatus(VDSOTypes.ReservationStatus.RESERVED, reservation.status);
        }
        if (block.timestamp >= reservation.expiresAt) {
            revert ReservationExpired(reservation.expiresAt);
        }
        if (fencingToken != reservation.fencingToken) {
            revert InvalidFencingToken(reservation.fencingToken, fencingToken);
        }
        if (transitionHash == bytes32(0)) revert InvalidReservation();

        reservation.status = VDSOTypes.ReservationStatus.COMMITTED;
        reservation.transitionHash = transitionHash;
        reservation.settlement = settlement;
        activeReservation[reservation.objectId] = bytes32(0);

        emit ReservationCommitted(reservationId, transitionHash, settlement.bridgeProofHash, settlement.payloadHash);
    }

    /// @notice Finalizes a proven late commit without passing through abort.
    /// @dev The kernel may call this only after semantic proof and adapter
    ///      settlement verification. The audit hash is retained on-chain.
    function finalizeRecoveryCommit(
        bytes32 reservationId,
        uint64 fencingToken,
        bytes32 transitionHash,
        bytes32 recoveryExecutionProofHash,
        VDSOTypes.SettlementMetadata calldata settlement
    ) external onlyRole(KERNEL_ROLE) {
        Reservation storage reservation = _reservations[reservationId];
        if (reservation.status != VDSOTypes.ReservationStatus.RECOVERY_PENDING) {
            revert InvalidReservationStatus(VDSOTypes.ReservationStatus.RECOVERY_PENDING, reservation.status);
        }
        if (fencingToken != reservation.fencingToken) {
            revert InvalidFencingToken(reservation.fencingToken, fencingToken);
        }
        if (transitionHash == bytes32(0) || recoveryExecutionProofHash == bytes32(0)) {
            revert MissingRecoveryProof();
        }

        reservation.status = VDSOTypes.ReservationStatus.COMMITTED;
        reservation.transitionHash = transitionHash;
        reservation.recoveryProofHash = recoveryExecutionProofHash;
        reservation.settlement = settlement;
        activeReservation[reservation.objectId] = bytes32(0);

        emit RecoveryCommitFinalized(
            reservationId,
            transitionHash,
            recoveryExecutionProofHash,
            settlement.bridgeProofHash,
            settlement.payloadHash
        );
    }

    /// @notice Releases a recovery-pending object only after verified non-execution.
    /// @dev A zero verifier address permanently disables abort and freezes ambiguity closed.
    function abortRecovery(bytes32 reservationId, bytes calldata recoveryProof) external onlyRole(RECOVERY_ROLE) {
        Reservation storage reservation = _reservations[reservationId];
        if (reservation.status != VDSOTypes.ReservationStatus.RECOVERY_PENDING) {
            revert InvalidReservationStatus(VDSOTypes.ReservationStatus.RECOVERY_PENDING, reservation.status);
        }
        if (address(recoveryVerifier) == address(0)) revert RecoveryAbortDisabled();
        if (recoveryProof.length == 0) revert MissingRecoveryProof();

        bool verified = false;
        try recoveryVerifier.verifyNonExecution(
            reservationId,
            reservation.objectId,
            reservation.domainId,
            reservation.intentId,
            reservation.authorityEpoch,
            reservation.fencingToken,
            recoveryProof
        ) returns (
            bool valid
        ) {
            verified = valid;
        } catch {
            revert InvalidRecoveryProof();
        }
        if (!verified) revert InvalidRecoveryProof();

        bytes32 recoveryProofHash = keccak256(
            abi.encode(
                RECOVERY_ABORT_PROOF_DOMAIN,
                reservationId,
                reservation.objectId,
                reservation.domainId,
                reservation.intentId,
                reservation.authorityEpoch,
                reservation.fencingToken,
                keccak256(recoveryProof)
            )
        );

        reservation.status = VDSOTypes.ReservationStatus.ABORTED;
        reservation.recoveryProofHash = recoveryProofHash;
        activeReservation[reservation.objectId] = bytes32(0);

        emit ReservationAborted(reservationId, recoveryProofHash);
    }

    function getReservation(bytes32 reservationId) external view returns (Reservation memory) {
        return _reservations[reservationId];
    }
}
