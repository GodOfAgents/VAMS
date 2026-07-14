// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Shared wire-level types for the VDSO canary contracts.
/// @dev These types are additive and do not replace the legacy Polygon/Cardano
///      dual-host routing architecture.
library VDSOTypes {
    enum Host {
        NONE,
        POLYGON,
        CARDANO
    }

    enum AccessMode {
        READ,
        CONSUME,
        RESERVE,
        ACCUMULATE
    }

    enum ReservationStatus {
        NONE,
        RESERVED,
        RECOVERY_PENDING,
        COMMITTED,
        ABORTED
    }

    enum AdapterStatus {
        NONE,
        PENDING,
        ACTIVE,
        QUARANTINED,
        RETIRED
    }

    /// @dev Bridge proof and payload commitment remain structurally separate
    ///      to preserve the cross-chain proof separation invariant (INV-10).
    struct SettlementMetadata {
        uint64 sourceChainId;
        bytes32 sourceTransactionHash;
        bytes32 bridgeProofHash;
        bytes32 payloadHash;
    }

    struct TransitionRequest {
        bytes32 executionId;
        bytes32 intentId;
        bytes32 programId;
        bytes32 objectId;
        bytes32 domainId;
        bytes32 reservationId;
        bytes32 transitionHash;
        bytes32 newStateRoot;
        bytes32 evidenceRoot;
        bytes32 verifierId;
        bytes32 recoveryExecutionProofHash;
        address reservationHolder;
        uint64 expectedObjectVersion;
        uint64 authorityEpoch;
        uint64 fencingToken;
        uint256 requiredCapabilities;
        Host requiredHost;
        AccessMode accessMode;
        SettlementMetadata settlement;
    }
}
