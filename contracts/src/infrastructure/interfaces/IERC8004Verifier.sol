// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IERC8004Verifier
 * @notice Interface for verifying ERC-8004 Remote Attestation proofs
 * @dev See https://eips.ethereum.org/EIPS/eip-8004
 */
interface IERC8004Verifier {
    struct EnclaveReport {
        bytes32 mrenclave; // Measurement of the enclave code
        bytes32 mrsigner; // Measurement of the signer (if applicable)
        bytes userReportData; // Data committed by the user (e.g., public key)
        uint64 timestamp; // Attestation timestamp
    }

    /**
     * @notice Verify a remote attestation quote
     * @param proof The raw TEE quote/proof
     * @return success True if verification passed
     * @return report The decoded enclave report
     */
    function verifyAttestation(bytes calldata proof) external view returns (bool success, EnclaveReport memory report);
}
