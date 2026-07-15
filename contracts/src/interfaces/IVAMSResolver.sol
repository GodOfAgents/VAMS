// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSResolver
 * @dev Standard interface for verifying agent attributes from external sources.
 *      "The API for the Medal Board."
 */
interface IVAMSResolver {
    struct Badge {
        string provider; // e.g., "Phala Network"
        string badgeName; // e.g., "TEE Secured"
        string badgeId; // e.g., "SGX_V2"
        uint256 issuedAt; // Timestamp
        uint256 expiresAt; // Timestamp (0 = indefinite)
        string metadataURI; // IPFS URI for detailed JSON (audit reports, etc.)
        bytes signature; // Provider's signature (if applicable)
    }

    /**
     * @notice Verifies if an agent possesses a specific attribute/badge.
     * @param agent The address of the agent (VAMS ID owner).
     * @param badgeType The type of badge being queried (e.g., keccak256("TEE_SECURED")).
     * @return isValid True if the agent has the valid badge.
     * @return badgeData The structured badge data.
     */
    function verifyBadge(address agent, bytes32 badgeType) external view returns (bool isValid, Badge memory badgeData);

    /**
     * @notice Returns a dynamic score (e.g., Credit Score, Reputation).
     * @dev This may call an oracle or read recent on-chain state.
     * @param agent The address of the agent.
     * @return score The numeric score (normalization handled by frontend).
     * @return lastUpdated Timestamp of the last update.
     */
    function getScore(address agent) external view returns (uint256 score, uint256 lastUpdated);
}
