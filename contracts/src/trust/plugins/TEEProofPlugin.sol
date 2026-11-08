// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVAMSProofPlugin} from "../../interfaces/IVAMSProofPlugin.sol";

/**
 * @title TEEProofPlugin
 * @notice Proof plugin for TEE (Trusted Execution Environment) attestation verification.
 * @dev Retired, rejecting compatibility plugin. No hardware scheme is verified
 *      by this format. Use the separately qualified action-bound DCAP path.
 */
contract TEEProofPlugin is IVAMSProofPlugin {

    /// @notice Allowed enclave measurement hashes (mrenclave)
    mapping(bytes32 => bool) public allowedEnclaves;

    /// @notice Contract owner for enclave management
    address public immutable admin;

    /// @notice TEE attestation proof structure (decoded from proofData)
    struct TEEAttestation {
        bytes sgxQuote;         // Raw SGX quote bytes
        bytes32 mrenclave;      // Enclave measurement hash
        bytes32 mrsigner;       // Signer measurement hash
        address attestedAgent;  // Agent address embedded in quote
    }

    event EnclaveAllowed(bytes32 indexed mrenclave);
    event EnclaveRevoked(bytes32 indexed mrenclave);

    modifier onlyAdmin() {
        require(msg.sender == admin, "TEEProofPlugin: not admin");
        _;
    }

    constructor(address _admin) {
        admin = _admin;
    }

    // ============================================================
    //                  IVAMSProofPlugin
    // ============================================================

    function proofType() external pure override returns (bytes32) {
        return keccak256(abi.encodePacked("PHALA_EXECUTION"));
    }

    function verify(bytes32, bytes32, bytes calldata) external pure override returns (bool) {
        // Historical hash concatenation is not hardware attestation. Qualified
        // action-bound evidence uses the separate versioned verifier path.
        return false;
    }

    function trustWeight() external pure override returns (uint256) {
        return 0; // No qualification or trust credit for the retired proof format.
    }

    function name() external pure override returns (string memory) {
        return "Phala TEE Attestation";
    }

    // ============================================================
    //                  ADMIN FUNCTIONS
    // ============================================================

    /// @notice Allow a new enclave measurement
    function allowEnclave(bytes32 mrenclave) external onlyAdmin {
        allowedEnclaves[mrenclave] = true;
        emit EnclaveAllowed(mrenclave);
    }

    /// @notice Revoke an enclave measurement
    function revokeEnclave(bytes32 mrenclave) external onlyAdmin {
        allowedEnclaves[mrenclave] = false;
        emit EnclaveRevoked(mrenclave);
    }
}
