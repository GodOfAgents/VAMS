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
 * @notice Retired compatibility adapter; generic attestation acceptance is disabled.
 * @dev This legacy interface has no qualified root/action/agent binding or freshness
 *      profile. A verifier's success flag alone must not establish agent trust.
 *      Qualified action-bound DCAP evidence uses its separate versioned verifier.
 */
contract VAMSERC8004Adapter is AccessControl {
    
    // ============ State ============

    IVAMSAgentRegistry public immutable registry;
    IERC8004Verifier public verifier;
    
    // Agent ID => Verified MRENCLAVE
    mapping(bytes32 => bytes32) public verifiedEnclaves;
    
    // ============ Events ============

    event AgentVerified(bytes32 indexed agentId, bytes32 indexed mrenclave, uint64 timestamp);
    
    // ============ Errors ============

    error InvalidProof();
    error NotAgentOwner();
    error RegistryNotSet();
    error LegacyAttestationDisabled();
    
    // ============ Constructor ============

    constructor(address _registry, address _verifier) {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        registry = IVAMSAgentRegistry(_registry);
        verifier = IERC8004Verifier(_verifier);
    }
    
    // ============ Main Functions ============

    /**
     * @notice Reject the unqualified legacy attestation path before external calls.
     * @dev Retains the selector for compatibility. Changing the configured verifier
     *      cannot enable acceptance; a future binding scheme requires a reviewed
     *      versioned implementation. No registry or verifier result is consumed.
     */
    function verifyAndRegister(bytes32, bytes calldata) external pure {
        revert LegacyAttestationDisabled();
    }
    
    // ============ Admin ============

    function setVerifier(address _verifier) external onlyRole(DEFAULT_ADMIN_ROLE) {
        verifier = IERC8004Verifier(_verifier);
    }
}
