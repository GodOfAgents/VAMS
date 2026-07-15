// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IRoutingProofVerifier
 * @notice The "Observer" interface for the Bit from Bit architecture.
 * @dev Verifies that routing decisions made by the CLR align with committed rules.
 */
interface IRoutingProofVerifier {
    struct RoutingProof {
        bytes32 inputMetadataHash; // H(valueUSD, latency, privacy, etc.)
        bytes32 routingDecisionHash; // H(selectedChain, selectedProvider)
        bytes32 routingRulesRoot; // Merkle root of active routing rules
        bytes zkProof; // SNARK proof (or signature in v1)
    }

    event ProofVerified(bytes32 indexed txHash, bool valid);
    event RulesUpdated(bytes32 indexed newRoot, address indexed updatedBy);

    /**
     * @notice Verify a routing decision against the committed rules.
     * @param _txHash The transaction hash being verified.
     * @param _proof The proof data.
     * @return bool True if valid, false otherwise.
     */
    function verifyRoutingDecision(bytes32 _txHash, RoutingProof calldata _proof) external view returns (bool);

    /**
     * @notice Update the Merkle root of the active routing rules.
     * @param _newRoot The new Merkle root.
     */
    function updateRoutingRulesRoot(bytes32 _newRoot) external;
}
