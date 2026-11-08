// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {VAMSUpgradeableBase} from "../base/VAMSUpgradeableBase.sol";
import {IVAMSTrustAggregator} from "../interfaces/IVAMSTrustAggregator.sol";
import {IVAMSProofPlugin} from "../interfaces/IVAMSProofPlugin.sol";
import {IComposedSettlement} from "../economic/IComposedSettlement.sol";

interface ISettledDeliveryEvidenceV1 {
    function getProviderAlloc(bytes32 allocationId, uint256 index)
        external view returns (IComposedSettlement.ProviderAlloc memory);
    function getDeliveryContext(bytes32 allocationId, uint256 index) external view returns (bytes32);
    function verifiedProviderProofs(bytes32 allocationId, uint256 index) external view returns (bool);
    function deliveredOutputHash(bytes32 allocationId, uint256 index) external view returns (bytes32);
}

/**
 * @title VAMSTrustAggregator
 * @notice Implementation of VAMS Layer 4 — Pluggable Proof Architecture.
 * @dev Aggregates proofs from pluggable proof plugins to assign Trust Scores.
 *      Maintains backward compatibility with the legacy "Decagon" proof system
 *      while enabling extensible, permissionless proof plugin registration.
 *
 *      UPGRADE NOTES:
 *      - This contract is UUPS-upgradeable. Storage layout is preserved.
 *      - Legacy state (lines 21-29 of original) is kept in the same slots.
 *      - New plugin state is appended AFTER existing storage.
 */
contract VAMSTrustAggregator is 
    VAMSUpgradeableBase, 
    IVAMSTrustAggregator 
{
    // ============================================================
    //              LEGACY STATE — DO NOT REORDER
    // ============================================================

    /// @dev Slot 0: Agent profiles (legacy, preserved from v1)
    mapping(address => AgentProfile) private _profiles;

    /// @dev Constants (not in storage)
    uint256 public constant SCORE_THRESHOLD_SILVER = 30;
    uint256 public constant SCORE_THRESHOLD_GOLD = 70;
    uint256 public constant SCORE_THRESHOLD_PLATINUM = 90;

    /// @dev Slot 1: Legacy proof weights (preserved from v1)
    mapping(ProofType => uint256) public proofWeights;

    // ============================================================
    //              PLUGIN STATE — APPENDED (v2)
    // ============================================================

    /// @dev Slot 2: Registered proof plugins keyed by proof type identifier
    mapping(bytes32 => IVAMSProofPlugin) private _proofPlugins;

    /// @dev Slot 3: Track which plugin proof types an agent has verified
    ///      agent => (pluginProofType => verified)
    mapping(address => mapping(bytes32 => bool)) private _agentPluginProofs;

    /// @dev Slot 4: Array of all registered plugin proof types (for enumeration)
    bytes32[] private _registeredPluginTypes;

    /// @dev Slot 5: Quick lookup for plugin type index in _registeredPluginTypes
    /// @dev Quick lookup for plugin type index in _registeredPluginTypes
    mapping(bytes32 => uint256) private _pluginTypeIndex;

    /// @dev Governance flag to enable/disable legacy decagon proofs
    bool public legacyProofsEnabled;

    /// @dev Storage gap for future upgrades
    mapping(address => bytes32) public settlementEvidenceSources;
    mapping(bytes32 => address) public settledDeliveryRoots;
    uint256[41] private __gap;

    event SettlementEvidenceSourceConfigured(address indexed source, bytes32 runtimeHash);
    event RootDeliveryEvidenceAccepted(address indexed root, address indexed settlement,
        bytes32 indexed allocationId, uint256 providerIndex, bytes32 context, bytes32 outputHash);

    // ============================================================
    //                      CONSTRUCTOR
    // ============================================================

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize() public initializer {
        __VAMSUpgradeableBase_init(msg.sender);

        legacyProofsEnabled = true;

        // Initialize Default Legacy Weights
        
        // A. Identity (Baseline)
        proofWeights[ProofType.ERC8004_IDENTITY] = 10;
        proofWeights[ProofType.COINBASE_WALLET] = 30;
        proofWeights[ProofType.POLYGON_ID] = 20;

        // B. Verification (Capability)
        proofWeights[ProofType.PARALLEL_RESEARCH] = 20;
        proofWeights[ProofType.PHALA_EXECUTION] = 25;
        proofWeights[ProofType.SXT_SQL_PROOF] = 15;
        proofWeights[ProofType.MCP_CONNECTION] = 10;

        // C. Reputation (Trust)
        proofWeights[ProofType.SPECTRAL_CREDIT] = 20;
        proofWeights[ProofType.AUTONOLAS_CONSENSUS] = 25;
        proofWeights[ProofType.WORLD_ID_HUMAN] = 40;
    }

    // ============================================================
    //                  LEGACY PROOF SUBMISSION
    // ============================================================

    /**
     * @notice Submit a proof from the legacy Decagon system.
     * @dev Preserved for backward compatibility. Routes through legacy verification.
     */
    function submitProof(ProofType proofType, bytes calldata proofData) external override {
        require(legacyProofsEnabled, "Legacy proofs disabled");
        bool valid = _verifyLegacyProof(proofType, proofData, msg.sender);
        require(valid, "Invalid Proof");

        AgentProfile storage profile = _profiles[msg.sender];
        
        uint256 proofBit = uint256(1) << uint256(proofType);
        
        // Only add score if not already verified
        if ((profile.verifiedProofsMask & proofBit) == 0) {
            profile.verifiedProofsMask |= proofBit;
            profile.trustScore += proofWeights[proofType];
            profile.lastVerificationTimestamp = block.timestamp;
            
            emit ProofVerified(msg.sender, proofType, keccak256(proofData));
            
            _updateTier(msg.sender);
        }
    }

    // ============================================================
    //                  PLUGIN PROOF SUBMISSION
    // ============================================================

    /**
     * @notice Submit a proof via the plugin system.
     * @dev Routes verification to the registered plugin contract.
     */
    function submitPluginProof(
        bytes32 pluginProofType,
        bytes32 serviceHash,
        bytes32 deliveryHash,
        bytes calldata proofData
    ) external override {
        IVAMSProofPlugin plugin = _proofPlugins[pluginProofType];
        require(address(plugin) != address(0), "Unknown proof type");

        // Verify via plugin (staticcall — no state mutation)
        bool valid = plugin.verify(serviceHash, deliveryHash, proofData);
        require(valid, "Plugin proof verification failed");

        AgentProfile storage profile = _profiles[msg.sender];

        // Only add score if not already verified for this plugin type
        if (!_agentPluginProofs[msg.sender][pluginProofType]) {
            _agentPluginProofs[msg.sender][pluginProofType] = true;
            
            // Convert basis points (0-10000) to score points (0-100)
            uint256 weight = plugin.trustWeight();
            uint256 scoreContribution = weight / 100; // 2500 bps -> 25 points
            profile.trustScore += scoreContribution;
            profile.pluginProofCount += 1;
            profile.lastVerificationTimestamp = block.timestamp;

            emit PluginProofVerified(
                msg.sender, 
                pluginProofType, 
                keccak256(proofData), 
                weight
            );

            _updateTier(msg.sender);
        }
    }

    /**
     * @notice Verify a service delivery proof without updating state.
     * @dev Can be called externally by other contracts for composability.
     */
    function verifyServiceDelivery(
        bytes32 serviceHash,
        bytes32 deliveryHash,
        bytes32 pluginProofType,
        bytes calldata proofData
    ) external view override returns (bool valid, uint256 trustWeight) {
        IVAMSProofPlugin plugin = _proofPlugins[pluginProofType];
        require(address(plugin) != address(0), "Unknown proof type");
        
        valid = plugin.verify(serviceHash, deliveryHash, proofData);
        trustWeight = plugin.trustWeight();
    }

    // ============================================================
    //                  PLUGIN MANAGEMENT
    // ============================================================

    /**
     * @notice Register a new proof plugin.
     * @dev Only owner/DAO. Reverts if a plugin for this proof type is already registered.
     */
    function registerProofPlugin(IVAMSProofPlugin plugin) external override onlyRole(UPGRADER_ROLE) {
        bytes32 pType = plugin.proofType();
        require(address(_proofPlugins[pType]) == address(0), "Plugin type already registered");
        require(address(plugin) != address(0), "Invalid plugin address");

        _proofPlugins[pType] = plugin;
        _pluginTypeIndex[pType] = _registeredPluginTypes.length;
        _registeredPluginTypes.push(pType);

        emit ProofPluginRegistered(pType, address(plugin));
    }

    /**
     * @notice Deregister an existing proof plugin.
     * @dev Only owner/DAO. Existing proofs from this plugin remain valid (scores kept).
     */
    function deregisterProofPlugin(bytes32 pluginProofType) external override onlyRole(UPGRADER_ROLE) {
        address pluginAddr = address(_proofPlugins[pluginProofType]);
        require(pluginAddr != address(0), "Plugin not registered");

        // Remove from array (swap-and-pop)
        uint256 idx = _pluginTypeIndex[pluginProofType];
        uint256 lastIdx = _registeredPluginTypes.length - 1;
        if (idx != lastIdx) {
            bytes32 lastType = _registeredPluginTypes[lastIdx];
            _registeredPluginTypes[idx] = lastType;
            _pluginTypeIndex[lastType] = idx;
        }
        _registeredPluginTypes.pop();
        delete _pluginTypeIndex[pluginProofType];
        delete _proofPlugins[pluginProofType];

        emit ProofPluginDeregistered(pluginProofType, pluginAddr);
    }

    // ============================================================
    //                      VIEW FUNCTIONS
    // ============================================================

    function getAgentTier(address agent) external view override returns (TrustTier) {
        return _profiles[agent].currentTier;
    }

    function hasProof(address agent, ProofType proofType) external view override returns (bool) {
        return (_profiles[agent].verifiedProofsMask & (uint256(1) << uint256(proofType))) != 0;
    }

    function getAgentScore(address agent) external view returns (uint256) {
        return _profiles[agent].trustScore;
    }

    function getProofPlugin(bytes32 pluginProofType) external view override returns (IVAMSProofPlugin) {
        return _proofPlugins[pluginProofType];
    }

    /// @notice Check if an agent has a specific plugin proof verified
    function hasPluginProof(address agent, bytes32 pluginProofType) external view returns (bool) {
        return _agentPluginProofs[agent][pluginProofType];
    }

    /// @notice Get the count of registered plugin types
    function getRegisteredPluginCount() external view returns (uint256) {
        return _registeredPluginTypes.length;
    }

    /// @notice Get a registered plugin type by index
    function getRegisteredPluginType(uint256 index) external view returns (bytes32) {
        require(index < _registeredPluginTypes.length, "Index out of bounds");
        return _registeredPluginTypes[index];
    }

    // ============================================================
    //                    INTERNAL LOGIC
    // ============================================================

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
     * @dev Legacy verification logic for Decagon proof types.
     *      In Phase 2, these will migrate to individual plugins.
     */
    function _verifyLegacyProof(
        ProofType proofType, 
        bytes calldata proofData, 
        address /* agent */
    ) internal view returns (bool) {
        if (proofData.length < 64) return false;

        bytes32 pTypeBytes = bytes32(uint256(proofType));
        IVAMSProofPlugin plugin = _proofPlugins[pTypeBytes];
        
        if (address(plugin) == address(0)) {
            return false;
        }

        return plugin.verify(bytes32(0), bytes32(0), proofData);
    }

    // --- Admin ---

    /// @notice Register exact reviewed settlement code as an evidence source.
    /// @dev Source/dependency qualification is separate from code-hash equality.
    function setSettlementEvidenceSource(address source, bytes32 runtimeHash) external onlyRole(UPGRADER_ROLE) {
        require(source != address(0), "Missing evidence source");
        if (runtimeHash != 0) require(source.code.length > 0 && source.codehash == runtimeHash, "Evidence source identity mismatch");
        settlementEvidenceSources[source] = runtimeHash;
        emit SettlementEvidenceSourceConfigured(source, runtimeHash);
    }

    /// @notice A relay records an authenticated settled delivery for its provider root.
    /// @dev This records evidence only; it does not award an unqualified score or
    /// authorize any effect. Caller identity never determines the credited root.
    function submitSettledDeliveryProof(address source, bytes32 allocationId, uint256 providerIndex)
        external returns (bytes32 key) {
        bytes32 runtime = settlementEvidenceSources[source];
        require(runtime != 0 && source.codehash == runtime, "Unapproved evidence source");
        ISettledDeliveryEvidenceV1 evidence = ISettledDeliveryEvidenceV1(source);
        IComposedSettlement.ProviderAlloc memory p = evidence.getProviderAlloc(allocationId, providerIndex);
        require(p.provider != address(0) && p.claimed && evidence.verifiedProviderProofs(allocationId, providerIndex), "Unsettled delivery");
        bytes32 output = evidence.deliveredOutputHash(allocationId, providerIndex);
        bytes32 context = evidence.getDeliveryContext(allocationId, providerIndex);
        require(output != 0 && context != 0, "Missing delivery evidence");
        key = keccak256(abi.encode(block.chainid, source, allocationId, providerIndex));
        require(settledDeliveryRoots[key] == address(0), "Delivery evidence already recorded");
        settledDeliveryRoots[key] = p.provider;
        emit RootDeliveryEvidenceAccepted(p.provider, source, allocationId, providerIndex, context, output);
    }
    
    function setProofWeight(ProofType proofType, uint256 weight) external onlyRole(UPGRADER_ROLE) {
        proofWeights[proofType] = weight;
    }

    function setLegacyProofsEnabled(bool enabled) external onlyRole(UPGRADER_ROLE) {
        legacyProofsEnabled = enabled;
    }

    // _authorizeUpgrade is implemented in VAMSUpgradeableBase
}
