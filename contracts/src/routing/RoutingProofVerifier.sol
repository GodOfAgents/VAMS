// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "../interfaces/IRoutingProofVerifier.sol";

/**
 * @title RoutingProofVerifier
 * @author VAMS Protocol
 * @notice The On-Chain Observer implementing the "Bit from Bit" theory.
 * @dev 
 * This contract collapses probabilistic routing states into deterministic facts.
 * In Phase 1 (Guarded), it verifies signatures from trusted CLR operators.
 * In Phase 2 (ZK), it will verify ZK-SNARKs.
 */
contract RoutingProofVerifier is 
    Initializable, 
    AccessControlUpgradeable, 
    IRoutingProofVerifier 
{
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    // ============ Constants ============
    
    bytes32 public constant RULES_UPDATER_ROLE = keccak256("RULES_UPDATER_ROLE");
    bytes32 public constant VERIFIER_ORACLE_ROLE = keccak256("VERIFIER_ORACLE_ROLE");

    // ============ State ============
    
    /// @notice The current Merkle root of valid routing rules
    bytes32 public routingRulesRoot;

    // ============ Initializer ============

    function initialize(address _admin) public initializer {
        __AccessControl_init();
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(RULES_UPDATER_ROLE, _admin);
        _grantRole(VERIFIER_ORACLE_ROLE, _admin);
    }

    // ============ Observer Logic ============

    /**
     * @notice Verify a routing decision.
     * @dev In v1, we check if the proof (signature) was signed by a VERIFIER_ORACLE.
     */
    function verifyRoutingDecision(
        bytes32 _txHash,
        RoutingProof calldata _proof
    ) public view override returns (bool) {
        // 1. Verify that the proof references the current rules
        if (_proof.routingRulesRoot != routingRulesRoot) {
            return false;
        }

        // 2. Reconstruct the signed message
        // Message = H(txHash, inputMetadataHash, routingDecisionHash, routingRulesRoot)
        bytes32 messageHash = keccak256(
            abi.encodePacked(
                _txHash,
                _proof.inputMetadataHash,
                _proof.routingDecisionHash,
                _proof.routingRulesRoot
            )
        );
        
        // 3. Recover signer from signature (v1 mock for ZK)
        address signer = messageHash.toEthSignedMessageHash().recover(_proof.zkProof);
        
        // 4. Check if signer is authorized
        return hasRole(VERIFIER_ORACLE_ROLE, signer);
    }

    /**
     * @notice Submit a proof to be verified and logged.
     * @dev Helper for off-chain agents to "collapse" the state on-chain.
     */
    function submitProof(
        bytes32 _txHash,
        RoutingProof calldata _proof
    ) external {
        bool isValid = verifyRoutingDecision(_txHash, _proof);
        require(isValid, "Invalid Proof");
        
        emit ProofVerified(_txHash, true);
    }

    // ============ Admin Functions ============

    function updateRoutingRulesRoot(bytes32 _newRoot) external onlyRole(RULES_UPDATER_ROLE) {
        routingRulesRoot = _newRoot;
        emit RulesUpdated(_newRoot, msg.sender);
    }
}
