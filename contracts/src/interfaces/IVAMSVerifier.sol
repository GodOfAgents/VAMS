// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSVerifier (Border Control)
 * @dev The gatekeeper that verifies "Proof of Travel" logs and manages Agent Risk States.
 *      "Your Medals determine your Access."
 */
interface IVAMSVerifier {
    enum RiskState {
        VERIFIED, // 🟢 Full Access
        ROAMING, // 🟡 Suspended (Away)
        UNTRUSTED, // 🔴 Restricted (Bad Log / Gap)
        PROBATION // 🟠 Limited (Rebuilding Trust)
    }

    struct RoamingLog {
        uint256 timestampOut;
        uint256 timestampIn;
        uint256 chainId; // Where did they go?
        bytes32 activityHash; // Hash of the off-chain log
        bytes signature; // TEE/Bridge Signature
    }

    // =============================================================
    //                           EVENTS
    // =============================================================

    event AgentDeparted(address indexed agent, uint256 destinationChainId, uint256 timestamp);
    event AgentReturned(address indexed agent, RiskState newStatus, uint256 timestamp);
    event AccessDenied(address indexed agent, string reason);

    // =============================================================
    //                       CORE FUNCTIONS
    // =============================================================

    /**
     * @notice Registers departure. Freezes credit line.
     * @param destinationChainId The Chain ID the agent is moving to.
     */
    function declareExit(uint256 destinationChainId) external;

    /**
     * @notice The "Re-Entry Interview". Verifies off-chain activity.
     * @param activities Structured log of performed actions.
     * @param signature Cryptographic proof (TEE/Bridge) of the log.
     * @return newState The calculated RiskState based on the proof.
     */
    function submitReEntryLog(bytes calldata activities, bytes calldata signature) external returns (RiskState newState);

    /**
     * @notice Checks if an agent has the required "Medal" for a specific action.
     * @param agent The agent address.
     * @param requiredBadgeHash The hash of the badge (e.g. keccak256("CREDIT_SCORE_700")).
     * @return authorized True if the agent has the badge AND is in VERIFIED state.
     */
    function checkAccess(address agent, bytes32 requiredBadgeHash) external view returns (bool authorized);
}
