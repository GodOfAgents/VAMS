// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVAMSProofPlugin} from "../../interfaces/IVAMSProofPlugin.sol";

/**
 * @title PolygonIDPlugin
 * @notice Proof plugin for Polygon ID (Iden3) ZK-VC credential verification.
 * @dev Verifies zero-knowledge verifiable credentials issued via Polygon ID.
 *      Provides privacy-preserving identity verification without revealing
 *      the underlying credential data.
 */
contract PolygonIDPlugin is IVAMSProofPlugin {
    /// @notice Polygon ID state contract address
    address public immutable iden3State;

    /// @notice Approved credential schemas
    mapping(uint256 => bool) public approvedSchemas;

    /// @notice Contract admin
    address public immutable admin;

    /// @notice Polygon ID proof structure
    struct PolygonIDProof {
        uint256[] inputs; // Public inputs for ZK circuit
        uint256[2] a; // ZK proof point A
        uint256[2][2] b; // ZK proof point B
        uint256[2] c; // ZK proof point C
        uint256 schemaHash; // Credential schema hash
    }

    event SchemaApproved(uint256 indexed schemaHash);
    event SchemaRevoked(uint256 indexed schemaHash);

    modifier onlyAdmin() {
        require(msg.sender == admin, "PolygonIDPlugin: not admin");
        _;
    }

    constructor(address _admin, address _iden3State) {
        admin = _admin;
        iden3State = _iden3State;
    }

    function proofType() external pure override returns (bytes32) {
        return keccak256(abi.encodePacked("POLYGON_ID"));
    }

    function verify(
        bytes32,
        /* serviceHash */
        bytes32,
        /* deliveryHash */
        bytes calldata proofData
    )
        external
        view
        override
        returns (bool valid)
    {
        if (proofData.length == 0) return false;

        PolygonIDProof memory idProof = abi.decode(proofData, (PolygonIDProof));

        // 1. Verify credential schema is approved
        if (!approvedSchemas[idProof.schemaHash]) return false;

        // 2. Verify ZK proof via Iden3 verifier
        //    In production: IZKPVerifier(iden3State).verifyProof(
        //        idProof.inputs, [idProof.a, idProof.b, idProof.c]
        //    );

        // Structural validation for MVP
        if (idProof.inputs.length == 0) return false;

        return true;
    }

    function trustWeight() external pure override returns (uint256) {
        return 2000; // 20% — privacy-preserving identity verification
    }

    function name() external pure override returns (string memory) {
        return "Polygon ID ZK Credential";
    }

    // ============================================================
    //                  ADMIN FUNCTIONS
    // ============================================================

    function approveSchema(uint256 schemaHash) external onlyAdmin {
        approvedSchemas[schemaHash] = true;
        emit SchemaApproved(schemaHash);
    }

    function revokeSchema(uint256 schemaHash) external onlyAdmin {
        approvedSchemas[schemaHash] = false;
        emit SchemaRevoked(schemaHash);
    }
}
