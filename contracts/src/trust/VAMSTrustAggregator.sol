// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {OwnableUpgradeable} from "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {IVAMSTrustAggregator} from "../interfaces/IVAMSTrustAggregator.sol";

/**
 * @title VAMSTrustAggregator
 * @notice Implementation of VAMS Layer 4.
 * @dev Aggregates proofs from the "Decagon" of protocols to assign Trust Scores.
 */
contract VAMSTrustAggregator is 
    Initializable, 
    OwnableUpgradeable, 
    UUPSUpgradeable, 
    IVAMSTrustAggregator 
{
    // --- State ---
    mapping(address => AgentProfile) private _profiles;

    // --- Constants ---
    uint256 public constant SCORE_THRESHOLD_SILVER = 30; // Needs ~2-3 proofs
    uint256 public constant SCORE_THRESHOLD_GOLD = 70;   // Needs ~5-6 proofs
    uint256 public constant SCORE_THRESHOLD_PLATINUM = 90; // Needs specific high-value proofs

    // Weighting for each protocol (0-100)
    mapping(ProofType => uint256) public proofWeights;

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize() public initializer {
        __Ownable_init(msg.sender);
        __UUPSUpgradeable_init();

        // Initialize Default Weights
        
        // A. Identity (Baseline)
        proofWeights[ProofType.ERC8004_IDENTITY] = 10;
        proofWeights[ProofType.COINBASE_WALLET] = 30; // High trust (KYC)
        proofWeights[ProofType.POLYGON_ID] = 20;

        // B. Verification (Capability)
        proofWeights[ProofType.PARALLEL_RESEARCH] = 20; // Provenance is key
        proofWeights[ProofType.PHALA_EXECUTION] = 25;   // Execution integrity is critical
        proofWeights[ProofType.SXT_SQL_PROOF] = 15;
        proofWeights[ProofType.MCP_CONNECTION] = 10;

        // C. Reputation (Trust)
        proofWeights[ProofType.SPECTRAL_CREDIT] = 20;
        proofWeights[ProofType.AUTONOLAS_CONSENSUS] = 25;
        proofWeights[ProofType.WORLD_ID_HUMAN] = 40; // High trust (Liability)
    }

    /**
     * @notice Submit a proof to upgrade the agent's score.
     * @dev In a production version, this would call out to specific Verifier adapters.
     *      For this MVP, we verify signatures/mock inputs to simulate the aggregation.
     */
    function submitProof(ProofType proofType, bytes calldata proofData) external override {
        // 1. Verify the specific proof type
        bool valid = _verifyProtocolProof(proofType, proofData, msg.sender);
        require(valid, "Invalid Proof");

        // 2. Update Agent State
        AgentProfile storage profile = _profiles[msg.sender];
        
        uint256 proofBit = 1 << uint256(proofType);
        
        // Only add score if not already verified
        if ((profile.verifiedProofsMask & proofBit) == 0) {
            profile.verifiedProofsMask |= proofBit;
            profile.trustScore += proofWeights[proofType];
            
            emit ProofVerified(msg.sender, proofType, keccak256(proofData));
            
            // 3. Recalculate Tier
            _updateTier(msg.sender);
        }
    }

    function getAgentTier(address agent) external view override returns (TrustTier) {
        return _profiles[agent].currentTier;
    }

    function hasProof(address agent, ProofType proofType) external view override returns (bool) {
        return (_profiles[agent].verifiedProofsMask & (1 << uint256(proofType))) != 0;
    }

    function getAgentScore(address agent) external view returns (uint256) {
        return _profiles[agent].trustScore;
    }

    // --- Internal Logic ---

    function _updateTier(address agent) internal {
        AgentProfile storage profile = _profiles[agent];
        uint256 score = profile.trustScore;
        TrustTier oldTier = profile.currentTier;
        TrustTier newTier = TrustTier.UNVERIFIED;

        if (score >= SCORE_THRESHOLD_PLATINUM) {
            newTier = TrustTier.PLATINUM;
        } else if (score >= SCORE_THRESHOLD_GOLD) {
            newTier = TrustTier.GOLD;
        } else if (score >= SCORE_THRESHOLD_SILVER) {
            newTier = TrustTier.SILVER;
        } else if (score > 0) {
            newTier = TrustTier.BRONZE;
        }

        if (newTier != oldTier) {
            profile.currentTier = newTier;
            emit TierUpdated(agent, newTier);
        }
    }

    /**
     * @dev Mock verification logic for the MVP. 
     *      In Phase 2, these will call external Verifier Contracts.
     */
    function _verifyProtocolProof(ProofType proofType, bytes calldata proofData, address agent) internal view returns (bool) {
        // Check for empty proof
        if (proofData.length == 0) return false;

        // --- A. IDENTITY ---
        if (proofType == ProofType.ERC8004_IDENTITY) {
            // Check if proofData is valid ERC721 ownership proof (mock)
            return true;
        }
        if (proofType == ProofType.COINBASE_WALLET) {
            // Verify Coinbase Attestation Signature
            return true;
        }
        if (proofType == ProofType.POLYGON_ID) {
            // Verify ZK Proof via Iden3
            return true;
        }

        // --- B. VERIFICATION ---
        if (proofType == ProofType.PARALLEL_RESEARCH) {
            // Verify Parallel Protocol Signature on the Source Log
            return true;
        }
        if (proofType == ProofType.PHALA_EXECUTION) {
            // Check Intel SGX Quote (Mock check)
            // In reality: Automata.verify(proofData)
            return true;
        }

        // ... Logic for others ...
        
        return true;
    }

    // --- Admin ---
    
    function setProofWeight(ProofType proofType, uint256 weight) external onlyOwner {
        proofWeights[proofType] = weight;
    }

    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}
}
