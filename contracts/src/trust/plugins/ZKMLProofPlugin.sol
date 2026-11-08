// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVAMSProofPlugin} from "../../interfaces/IVAMSProofPlugin.sol";

/**
 * @title ZKMLProofPlugin
 * @notice Proof plugin for Zero-Knowledge Machine Learning proof verification.
 * @dev Verifies that an ML inference result was correctly computed using a ZK proof.
 *      Integration point for EZKL, Modulus Labs, or other ZKML verifier contracts.
 *      This plugin replaces the legacy SXT_SQL_PROOF + adds ML verification capability.
 */
contract ZKMLProofPlugin is IVAMSProofPlugin {

    /// @notice External ZKML verifier contract (e.g., EZKL verifier)
    address public zkmlVerifier;

    /// @notice Approved model hashes
    mapping(bytes32 => bool) public approvedModels;

    /// @notice Contract admin
    address public immutable admin;

    /// @notice ZKML proof structure (decoded from proofData)
    struct ZKMLProof {
        bytes proof;           // ZK proof bytes
        bytes32 modelHash;     // Hash of the ML model
        bytes32 inputHash;     // Hash of the model input
        bytes32 outputHash;    // Hash of the model output
        bytes publicInputs;    // Public inputs for verifier circuit
    }

    event ModelApproved(bytes32 indexed modelHash);
    event ModelRevoked(bytes32 indexed modelHash);
    event VerifierUpdated(address indexed oldVerifier, address indexed newVerifier);

    modifier onlyAdmin() {
        require(msg.sender == admin, "ZKMLProofPlugin: not admin");
        _;
    }

    constructor(address _admin, address _zkmlVerifier) {
        admin = _admin;
        zkmlVerifier = _zkmlVerifier;
    }

    // ============================================================
    //                  IVAMSProofPlugin
    // ============================================================

    function proofType() external pure override returns (bytes32) {
        return keccak256(abi.encodePacked("ZKML_VERIFICATION"));
    }

    function verify(
        bytes32,
        bytes32,
        bytes calldata
    ) external pure override returns (bool valid) {
        // Disabled until M4 selects and qualifies a real verifier and circuit relation.
        return false;
    }

    function trustWeight() external pure override returns (uint256) {
        return 0; // Disabled until an approved verifier and circuit are integrated.
    }

    function name() external pure override returns (string memory) {
        return "ZKML Inference Proof";
    }

    // ============================================================
    //                  ADMIN FUNCTIONS
    // ============================================================

    function approveModel(bytes32 modelHash) external onlyAdmin {
        approvedModels[modelHash] = true;
        emit ModelApproved(modelHash);
    }

    function revokeModel(bytes32 modelHash) external onlyAdmin {
        approvedModels[modelHash] = false;
        emit ModelRevoked(modelHash);
    }

    function setVerifier(address newVerifier) external onlyAdmin {
        address old = zkmlVerifier;
        zkmlVerifier = newVerifier;
        emit VerifierUpdated(old, newVerifier);
    }
}
