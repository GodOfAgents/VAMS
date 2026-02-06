// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "./interfaces/IERC8004Verifier.sol";

interface IVAMSAgentRegistry {
    function updateTEEAttestation(bytes32 agentId, bytes32 attestation) external;
    function getAgent(bytes32 agentId) external view returns (address owner, bytes32, uint256, uint8, uint256, uint256, bytes32);
}

/**
 * @title VAMSERC8004Adapter
 * @notice Bridges ERC-8004 Remote Attestations to VAMS Identity
 * @dev Verifies TEE proofs and updates the AgentRegistry with the verified MRENCLAVE
 */
contract VAMSERC8004Adapter is AccessControl {
    
    // ============ State ============

    IVAMSAgentRegistry public registry;
    IERC8004Verifier public verifier;
    
    // Agent ID => Verified MRENCLAVE
    mapping(bytes32 => bytes32) public verifiedEnclaves;
    
    // ============ Events ============

    event AgentVerified(bytes32 indexed agentId, bytes32 indexed mrenclave, uint64 timestamp);
    
    // ============ Errors ============

    error InvalidProof();
    error NotAgentOwner();
    error RegistryNotSet();
    
    // ============ Constructor ============

    constructor(address _registry, address _verifier) {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        registry = IVAMSAgentRegistry(_registry);
        verifier = IERC8004Verifier(_verifier);
    }
    
    // ============ Main Functions ============

    /**
     * @notice Submit an ERC-8004 Proof to verify an agent
     * @param agentId The VAMS Agent ID
     * @param proof The raw TEE Remote Attestation quote
     */
    function verifyAndRegister(bytes32 agentId, bytes calldata proof) external {
        // 1. Check ownership
        (address owner,,,,,,) = registry.getAgent(agentId);
        if (owner != msg.sender) revert NotAgentOwner();
        
        // 2. Verify Proof via Automata/Phala verifier
        (bool success, IERC8004Verifier.EnclaveReport memory report) = verifier.verifyAttestation(proof);
        if (!success) revert InvalidProof();
        
        // 3. Store Verification locally
        verifiedEnclaves[agentId] = report.mrenclave;
        
        // 4. Update Registry (Optional: if Registry allows external updaters)
        // For now, we trust this Adapter as the source of truth for "Verified MRENCLAVE"
        // registry.updateTEEAttestation(agentId, report.mrenclave); 
        
        emit AgentVerified(agentId, report.mrenclave, report.timestamp);
    }
    
    // ============ Admin ============

    function setVerifier(address _verifier) external onlyRole(DEFAULT_ADMIN_ROLE) {
        verifier = IERC8004Verifier(_verifier);
    }
}
