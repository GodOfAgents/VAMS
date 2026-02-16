// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSTrustAggregator
 * @notice Interface for the VAMS Layer 4 Verification Aggregator.
 * @dev Aggregates proofs from 10 different protocols to determine Agent Trust Tier.
 */
interface IVAMSTrustAggregator {
    
    /// @notice The 10 Types of Proofs VAMS accepts (The "Decagon")
    enum ProofType {
        // --- A. IDENTITY ---
        ERC8004_IDENTITY,       // 0: On-chain Registry (Base)
        COINBASE_WALLET,        // 1: Compliance / KYC (Corporate)
        POLYGON_ID,             // 2: ZK-VC (Private)

        // --- B. VERIFICATION ---
        PARALLEL_RESEARCH,      // 3: Proof of Research (Provenance)
        PHALA_EXECUTION,        // 4: Proof of Execution (TEE)
        SXT_SQL_PROOF,          // 5: Proof of SQL (Database)
        MCP_CONNECTION,         // 6: Proof of Connection (Tooling)

        // --- C. REPUTATION ---
        SPECTRAL_CREDIT,        // 7: On-chain Credit Score
        AUTONOLAS_CONSENSUS,    // 8: DAO/Fleet Consensus
        WORLD_ID_HUMAN          // 9: Proof of Personhood (Liability)
    }

    /// @notice Trust Tiers assigned to Agents
    enum TrustTier {
        UNVERIFIED, // 0: No proofs
        BRONZE,     // 1: Basic Identity (Sandboxed)
        SILVER,     // 2: Verified Execution (Standard DeFi)
        GOLD,       // 3: Full Sovereignty (High Leverage)
        PLATINUM    // 4: Corporate/Gov Compliant (KYC + Liability)
    }

    struct AgentProfile {
        TrustTier currentTier;
        uint256 trustScore;
        // Bitmask of verified proofs (1 << ProofType)
        uint256 verifiedProofsMask; 
        uint256 lastVerificationTimestamp;
    }

    /// @notice Emitted when an agent submits a valid proof
    event ProofVerified(address indexed agent, ProofType indexed proofType, bytes32 proofHash);

    /// @notice Emitted when an agent's tier changes
    event TierUpdated(address indexed agent, TrustTier newTier);

    /**
     * @notice Submit a proof from one of the supported protocols.
     * @param proofType The type of proof being submitted.
     * @param proofData The raw proof data (signature, ZK-proof, etc.).
     */
    function submitProof(ProofType proofType, bytes calldata proofData) external;

    /**
     * @notice Get the current Trust Tier of an agent.
     * @param agent The address of the agent.
     */
    function getAgentTier(address agent) external view returns (TrustTier);

    /**
     * @notice Check if an agent has a specific proof verified.
     * @param agent The address of the agent.
     * @param proofType The proof type to check.
     */
    function hasProof(address agent, ProofType proofType) external view returns (bool);
}
