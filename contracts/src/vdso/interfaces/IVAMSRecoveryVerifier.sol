// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Verifies a destination-bound proof that an expired reservation did not execute.
interface IVAMSRecoveryVerifier {
    function verifyNonExecution(
        bytes32 reservationId,
        bytes32 objectId,
        bytes32 domainId,
        bytes32 intentId,
        uint64 authorityEpoch,
        uint64 fencingToken,
        bytes calldata proof
    ) external view returns (bool);
}
