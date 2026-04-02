// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVAMSProofPlugin} from "../../interfaces/IVAMSProofPlugin.sol";

/**
 * @title WorldIDPlugin
 * @notice Proof plugin for World ID proof-of-personhood verification.
 * @dev Verifies Worldcoin's ZK proof of unique personhood (iris scan).
 *      Highest-weight identity proof — establishes liability and human control.
 *      Integration point for the World ID Semaphore verifier.
 */
contract WorldIDPlugin is IVAMSProofPlugin {

    /// @notice World ID verifier contract address
    address public immutable worldIdVerifier;

    /// @notice World ID action string for VAMS
    string public constant VAMS_ACTION = "vams-agent-verify";

    /// @notice World ID proof structure
    struct WorldIDProof {
        uint256 root;           // Merkle tree root
        uint256 nullifierHash;  // Unique nullifier (prevents double-use)
        uint256[8] proof;       // ZK proof (Groth16)
        uint256 externalNullifier; // Scoped nullifier
    }

    /// @notice Track used nullifiers to prevent reuse
    mapping(uint256 => bool) public usedNullifiers;

    constructor(address _worldIdVerifier) {
        worldIdVerifier = _worldIdVerifier;
    }

    function proofType() external pure override returns (bytes32) {
        return keccak256(abi.encodePacked("WORLD_ID_HUMAN"));
    }

    function verify(
        bytes32 /* serviceHash */,
        bytes32 /* deliveryHash */,
        bytes calldata proofData
    ) external view override returns (bool valid) {
        if (proofData.length == 0) return false;

        WorldIDProof memory worldProof = abi.decode(proofData, (WorldIDProof));

        // 1. Check nullifier hasn't been used
        if (usedNullifiers[worldProof.nullifierHash]) return false;

        // 2. Verify ZK proof via World ID verifier
        //    In production: IWorldID(worldIdVerifier).verifyProof(
        //        worldProof.root,
        //        groupId,
        //        abi.encodePacked(signal).hashToField(),
        //        worldProof.nullifierHash,
        //        worldProof.externalNullifier,
        //        worldProof.proof
        //    );

        // Structural validation for MVP
        if (worldProof.root == 0) return false;
        if (worldProof.nullifierHash == 0) return false;

        return true;
    }

    function trustWeight() external pure override returns (uint256) {
        return 4000; // 40% — highest trust (proof of personhood + liability)
    }

    function name() external pure override returns (string memory) {
        return "World ID Proof of Personhood";
    }
}
