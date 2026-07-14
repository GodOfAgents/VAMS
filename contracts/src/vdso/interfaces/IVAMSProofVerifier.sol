// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Backend-neutral proof-verifier interface used by the canary router.
interface IVAMSProofVerifier {
    function verify(bytes32 programId, bytes32 transitionHash, bytes calldata proof) external view returns (bool);
}
