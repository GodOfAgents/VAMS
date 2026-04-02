// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVAMSProofPlugin} from "./IVAMSProofPlugin.sol";

/**
 * @title IVAMSTrustAggregator
 * @notice Interface for the VAMS Layer 4 Verification Aggregator.
 * @dev Aggregates proofs from pluggable proof plugins to determine Agent Trust Tier.
 *      Supports both the legacy "Decagon" proof types and the new extensible plugin system.
 */
interface IVAMSTrustAggregator {
    
    // ============================================================
    //                    LEGACY PROOF TYPES
    // ============================================================

    /// @notice The 10 Types of Proofs VAMS accepts (The "Decagon") — LEGACY
    /// @dev Kept for backward compatibility. New proof types use the plugin system.
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

    // ============================================================
    //                       TRUST TIERS
    // ============================================================

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
        // Bitmask of verified legacy proofs (1 << ProofType)
        uint256 verifiedProofsMask; 
        uint256 lastVerificationTimestamp;
        // Bitmask-style tracking for plugin proofs
        uint256 pluginProofCount;
    }

    // ============================================================
    //                         EVENTS
    // ============================================================

    /// @notice Emitted when an agent submits a valid proof (legacy)
    event ProofVerified(address indexed agent, ProofType indexed proofType, bytes32 proofHash);

    /// @notice Emitted when an agent's tier changes
    event TierUpdated(address indexed agent, TrustTier newTier);

    /// @notice Emitted when a proof plugin is registered
    event ProofPluginRegistered(bytes32 indexed proofType, address indexed plugin);

    /// @notice Emitted when a proof plugin is deregistered
    event ProofPluginDeregistered(bytes32 indexed proofType, address indexed plugin);

    /// @notice Emitted when a plugin proof is verified
    event PluginProofVerified(
        address indexed agent, 
        bytes32 indexed proofType, 
        bytes32 proofHash, 
        uint256 trustWeight
    );

    // ============================================================
    //                   LEGACY FUNCTIONS
    // ============================================================

    /**
     * @notice Submit a proof from one of the legacy Decagon protocols.
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
     * @notice Check if an agent has a specific legacy proof verified.
     * @param agent The address of the agent.
     * @param proofType The proof type to check.
     */
    function hasProof(address agent, ProofType proofType) external view returns (bool);

    // ============================================================
    //                   PLUGIN FUNCTIONS
    // ============================================================

    /**
     * @notice Register a new proof plugin.
     * @dev Only callable by owner/DAO. Plugin must implement IVAMSProofPlugin.
     * @param plugin The proof plugin contract address.
     */
    function registerProofPlugin(IVAMSProofPlugin plugin) external;

    /**
     * @notice Deregister an existing proof plugin.
     * @dev Only callable by owner/DAO.
     * @param pluginProofType The bytes32 proof type to deregister.
     */
    function deregisterProofPlugin(bytes32 pluginProofType) external;

    /**
     * @notice Submit a proof via the plugin system.
     * @param pluginProofType The bytes32 identifier of the proof plugin.
     * @param serviceHash Hash of the original service request.
     * @param deliveryHash Hash of the service response/output.
     * @param proofData Plugin-specific proof bytes.
     */
    function submitPluginProof(
        bytes32 pluginProofType,
        bytes32 serviceHash,
        bytes32 deliveryHash,
        bytes calldata proofData
    ) external;

    /**
     * @notice Verify a service delivery proof without updating state.
     * @param serviceHash Hash of the original service request.
     * @param deliveryHash Hash of the service response/output.
     * @param pluginProofType The proof plugin type identifier.
     * @param proofData Plugin-specific proof bytes.
     * @return valid Whether the proof is valid.
     * @return trustWeight The trust weight of the proof type.
     */
    function verifyServiceDelivery(
        bytes32 serviceHash,
        bytes32 deliveryHash,
        bytes32 pluginProofType,
        bytes calldata proofData
    ) external view returns (bool valid, uint256 trustWeight);

    /**
     * @notice Get the address of a registered proof plugin.
     * @param pluginProofType The bytes32 proof type identifier.
     * @return plugin The plugin contract address (address(0) if not registered).
     */
    function getProofPlugin(bytes32 pluginProofType) external view returns (IVAMSProofPlugin plugin);
}
