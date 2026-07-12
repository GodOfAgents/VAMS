// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVAMSProofPlugin} from "../../interfaces/IVAMSProofPlugin.sol";

interface IWorldIDVerifier {
    function verifyProof(
        uint256 root,
        uint256 groupId,
        uint256 signalHash,
        uint256 nullifierHash,
        uint256 externalNullifierHash,
        uint256[8] calldata proof
    ) external view;
}

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

    /// @notice World ID Orb-verified group identifier
    uint256 public constant WORLD_ID_GROUP = 1;

    /// @notice World ID proof structure
    struct WorldIDProof {
        uint256 root;           // Merkle tree root
        uint256 nullifierHash;  // Unique nullifier (prevents double-use)
        uint256[8] proof;       // ZK proof (Groth16)
        uint256 externalNullifier; // Scoped nullifier
    }

    constructor(address _worldIdVerifier) {
        require(_worldIdVerifier != address(0), "WorldIDPlugin: zero verifier");
        worldIdVerifier = _worldIdVerifier;
    }

    function proofType() external pure override returns (bytes32) {
        return keccak256(abi.encodePacked("WORLD_ID_HUMAN"));
    }

    function verify(
        bytes32 serviceHash,
        bytes32 deliveryHash,
        bytes calldata proofData
    ) external view override returns (bool valid) {
        if (proofData.length != 11 * 32) return false;

        WorldIDProof memory worldProof = abi.decode(proofData, (WorldIDProof));
        if (worldProof.root == 0) return false;
        if (worldProof.nullifierHash == 0) return false;
        if (worldProof.externalNullifier != _hashToField(abi.encodePacked(VAMS_ACTION))) return false;

        uint256 signalHash = _hashToField(abi.encodePacked(serviceHash, deliveryHash));
        try IWorldIDVerifier(worldIdVerifier).verifyProof(
            worldProof.root,
            WORLD_ID_GROUP,
            signalHash,
            worldProof.nullifierHash,
            worldProof.externalNullifier,
            worldProof.proof
        ) {
            return true;
        } catch {
            return false;
        }
    }

    function _hashToField(bytes memory value) internal pure returns (uint256) {
        return uint256(keccak256(value)) >> 8;
    }

    function trustWeight() external pure override returns (uint256) {
        return 4000; // 40% — highest trust (proof of personhood + liability)
    }

    function name() external pure override returns (string memory) {
        return "World ID Proof of Personhood";
    }
}
