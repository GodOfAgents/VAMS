// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSProofPlugin
 * @notice Plugin interface for extensible proof verification in VAMS Layer 4.
 * @dev Any new proof type (TEE attestation, ZKML, FHE, RISC Zero, etc.) can be
 *      added to the trust framework by deploying a contract implementing this interface
 *      and registering it with the VAMSTrustAggregator.
 *
 *      Plugins are stateless verifiers — they MUST NOT mutate state.
 *      All functions are `view` to enforce this constraint.
 */
interface IVAMSProofPlugin {
    /// @notice Returns the unique type identifier for this proof plugin.
    /// @dev Should return keccak256(abi.encodePacked("PROOF_TYPE_NAME")).
    ///      Example: keccak256("PHALA_EXECUTION") for TEE attestation proofs.
    /// @return The bytes32 proof type identifier.
    function proofType() external view returns (bytes32);

    /// @notice Verify a proof of service delivery.
    /// @dev Implementation is plugin-specific. Examples:
    ///      - TEE plugin: decode SGX quote, verify mrenclave, check attestation
    ///      - ZKML plugin: verify ZK proof against model/input/output hashes
    ///      - Output Hash plugin: verify hash commitment + provider signature
    ///
    /// @param serviceHash Hash of the original service request
    /// @param deliveryHash Hash of the service response/output
    /// @param proofData Plugin-specific proof bytes (ABI-encoded)
    /// @return valid Whether the proof is valid
    function verify(bytes32 serviceHash, bytes32 deliveryHash, bytes calldata proofData)
        external
        view
        returns (bool valid);

    /// @notice Returns the trust weight of this proof type in basis points (0–10000).
    /// @dev Used by VAMSTrustAggregator to compute weighted composite trust scores.
    ///      Examples: TEE attestation = 2500 (25%), World ID = 4000 (40%)
    /// @return weight Trust weight in basis points
    function trustWeight() external view returns (uint256 weight);

    /// @notice Returns a human-readable name for the proof type.
    /// @return name The proof type name (e.g., "Phala TEE Attestation")
    function name() external view returns (string memory);
}
