// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "../base/VAMSUpgradeableBase.sol";

/**
 * @title VAMSRouter
 * @author VAMS Protocol
 * @notice Conditional L1 Router (CLR) with Manual Override for Development
 * @dev 
 * Routing Modes:
 * - AUTOMATIC: CLR rules apply (production default)
 * - MANUAL: Developer can force any route (dev/testing)
 * - HYBRID: Automatic with manual override capability
 * 
 * Manual routing is disabled in Phase 3+ (DAO governance)
 */
contract VAMSRouter is VAMSUpgradeableBase {
    
    // ============ Enums ============
    
    enum RoutingMode {
        AUTOMATIC,   // CLR rules apply
        MANUAL,      // Full manual control
        HYBRID       // Automatic with override
    }
    
    enum ChainId {
        VAMS_L3_POLYGON,    // Primary: Polygon CDK Validium
        CARDANO_MAINNET,    // Secondary: Formal Verification (Ouroboros)
        CARDANO_HYDRA,      // Secondary: High Velocity non-EVM
        MIDNIGHT_ZKSD,      // Compliance Privacy
        ETHEREUM,           // High-value settlement
        SOLANA,             // Low-latency non-EVM
        SEI,                // Fast EVM
        PHALA_TEE           // Privacy Compute
    }
    
    // ============ Structs ============
    
    struct TransactionMetadata {
        uint256 valueUSD;
        uint256 maxLatencyMs;
        bool requiresPrivacy;
        bool requiresCompliance;
        bool requiresFormalVerification;
        bool requiresEVM;
        bool isInstitutional;
    }
    
    struct RoutingDecision {
        ChainId targetChain;
        bool isManualOverride;
        address decidedBy;
        uint256 timestamp;
    }
    
    struct ManualRoute {
        ChainId targetChain;
        uint256 expiresAt;
        string reason;
    }
    
    // ============ Constants ============
    
    bytes32 public constant ROUTER_OPERATOR_ROLE = keccak256("ROUTER_OPERATOR_ROLE");
    bytes32 public constant MANUAL_ROUTER_ROLE = keccak256("MANUAL_ROUTER_ROLE");
    
    uint256 public constant SECURITY_THRESHOLD_USD = 10_000;
    uint256 public constant VELOCITY_THRESHOLD_MS = 1_000;
    uint256 public constant MAX_MANUAL_ROUTE_DURATION = 7 days;
    
    // ============ State ============
    
    /// @notice Current routing mode
    RoutingMode public routingMode;
    
    /// @notice Manual routes by transaction hash
    mapping(bytes32 => ManualRoute) public manualRoutes;
    
    /// @notice Global manual override (forces all txs to specific chain)
    ManualRoute public globalManualOverride;
    
    /// @notice Whether global override is active
    bool public globalOverrideActive;
    
    /// @notice Routing history (last 1000 decisions)
    mapping(uint256 => RoutingDecision) public routingHistory;
    uint256 public routingHistoryIndex;
    
    // ============ Events ============
    
    event RoutingModeChanged(RoutingMode indexed oldMode, RoutingMode indexed newMode, address changedBy);
    event TransactionRouted(bytes32 indexed txHash, ChainId indexed targetChain, bool manualOverride);
    event ManualRouteSet(bytes32 indexed txHash, ChainId targetChain, uint256 expiresAt, string reason);
    event GlobalOverrideActivated(ChainId targetChain, uint256 expiresAt, string reason);
    event GlobalOverrideDeactivated(address deactivatedBy);
    event ManualRoutingDisabled(string reason);
    
    // ============ Errors ============
    
    error ManualRoutingDisabledInDAO();
    error RouteExpired();
    error InvalidDuration();
    error ManualRoutingNotAllowed();
    
    // ============ Initializer ============
    
    function initialize(
        address _admin,
        address[] memory /* _guardians */
    ) public initializer {
        __VAMSUpgradeableBase_init(_admin);
        
        _grantRole(ROUTER_OPERATOR_ROLE, _admin);
        _grantRole(MANUAL_ROUTER_ROLE, _admin);
        
        // Start in HYBRID mode (automatic with manual override)
        routingMode = RoutingMode.HYBRID;
    }
    
    // ============ Routing Functions ============
    
    /**
     * @notice Route a transaction to appropriate chain
     * @param _txHash Transaction hash
     * @param _metadata Transaction metadata for routing decision
     * @return decision The routing decision
     */
    function routeTransaction(
        bytes32 _txHash,
        TransactionMetadata calldata _metadata
    ) external onlyRole(ROUTER_OPERATOR_ROLE) returns (RoutingDecision memory decision) {
        
        // Check global override first
        if (globalOverrideActive && block.timestamp < globalManualOverride.expiresAt) {
            decision = RoutingDecision({
                targetChain: globalManualOverride.targetChain,
                isManualOverride: true,
                decidedBy: address(this),
                timestamp: block.timestamp
            });
            emit TransactionRouted(_txHash, decision.targetChain, true);
            return decision;
        }
        
        // Check specific manual route
        ManualRoute storage manualRoute = manualRoutes[_txHash];
        if (manualRoute.expiresAt > 0 && block.timestamp < manualRoute.expiresAt) {
            decision = RoutingDecision({
                targetChain: manualRoute.targetChain,
                isManualOverride: true,
                decidedBy: address(this),
                timestamp: block.timestamp
            });
            emit TransactionRouted(_txHash, decision.targetChain, true);
            return decision;
        }
        
        // Automatic routing (CLR rules)
        if (routingMode == RoutingMode.MANUAL) {
            revert ManualRoutingNotAllowed();
        }
        
        ChainId target = _applyRoutingRules(_metadata);
        
        decision = RoutingDecision({
            targetChain: target,
            isManualOverride: false,
            decidedBy: msg.sender,
            timestamp: block.timestamp
        });
        
        // Store in history
        routingHistory[routingHistoryIndex % 1000] = decision;
        routingHistoryIndex++;
        
        emit TransactionRouted(_txHash, target, false);
    }
    
    // ============ Manual Routing ============
    
    /**
     * @notice Set a manual route for a specific transaction
     * @param _txHash Transaction hash
     * @param _targetChain Target chain
     * @param _duration How long the override lasts
     * @param _reason Reason for manual routing
     */
    function setManualRoute(
        bytes32 _txHash,
        ChainId _targetChain,
        uint256 _duration,
        string calldata _reason
    ) external onlyRole(MANUAL_ROUTER_ROLE) {
        _checkManualRoutingAllowed();
        
        if (_duration > MAX_MANUAL_ROUTE_DURATION) revert InvalidDuration();
        
        manualRoutes[_txHash] = ManualRoute({
            targetChain: _targetChain,
            expiresAt: block.timestamp + _duration,
            reason: _reason
        });
        
        emit ManualRouteSet(_txHash, _targetChain, block.timestamp + _duration, _reason);
    }
    
    /**
     * @notice Activate global manual override (routes ALL transactions)
     * @param _targetChain Target chain for all transactions
     * @param _duration How long the override lasts
     * @param _reason Reason for override
     */
    function activateGlobalOverride(
        ChainId _targetChain,
        uint256 _duration,
        string calldata _reason
    ) external onlyRole(MANUAL_ROUTER_ROLE) {
        _checkManualRoutingAllowed();
        
        if (_duration > MAX_MANUAL_ROUTE_DURATION) revert InvalidDuration();
        
        globalManualOverride = ManualRoute({
            targetChain: _targetChain,
            expiresAt: block.timestamp + _duration,
            reason: _reason
        });
        globalOverrideActive = true;
        
        emit GlobalOverrideActivated(_targetChain, block.timestamp + _duration, _reason);
    }
    
    /**
     * @notice Deactivate global manual override
     */
    function deactivateGlobalOverride() external onlyRole(MANUAL_ROUTER_ROLE) {
        globalOverrideActive = false;
        emit GlobalOverrideDeactivated(msg.sender);
    }
    
    /**
     * @notice Change routing mode
     * @param _mode New routing mode
     */
    function setRoutingMode(RoutingMode _mode) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_mode == RoutingMode.MANUAL) {
            _checkManualRoutingAllowed();
        }
        
        RoutingMode oldMode = routingMode;
        routingMode = _mode;
        
        emit RoutingModeChanged(oldMode, _mode, msg.sender);
    }
    
    // ============ Internal: Routing Rules ============
    
    /**
     * @notice Apply CLR routing rules
     * @param _meta Transaction metadata
     * @return ChainId Target chain
     */
    function _applyRoutingRules(TransactionMetadata calldata _meta) internal pure returns (ChainId) {
        // Priority 1: Compliance Privacy → Midnight ZK-SD
        if (_meta.requiresCompliance && _meta.requiresPrivacy) {
            return ChainId.MIDNIGHT_ZKSD;
        }

        // Priority 2: Privacy/Compute → Phala TEE
        if (_meta.requiresPrivacy) {
            return ChainId.PHALA_TEE;
        }
        
        // Priority 3: High-value → Ethereum
        if (_meta.valueUSD > SECURITY_THRESHOLD_USD) {
            return ChainId.ETHEREUM;
        }
        
        // Priority 4: Institutional Compliance → Polygon CDK KYC Layer
        if (_meta.isInstitutional) {
            // Polygon CDK has the institutional KYC layer configuration
            return ChainId.VAMS_L3_POLYGON;
        }

        // Priority 5: Formal Verification → Cardano Ouroboros
        if (_meta.requiresFormalVerification) {
            return ChainId.CARDANO_MAINNET;
        }
        
        // Priority 6: Low latency → Fast chains
        if (_meta.maxLatencyMs < VELOCITY_THRESHOLD_MS) {
            if (_meta.requiresEVM) {
                return ChainId.SEI;
            } else {
                return ChainId.CARDANO_HYDRA;
            }
        }
        
        // Default: Polygon CDK Validium
        return ChainId.VAMS_L3_POLYGON;
    }
    
    /**
     * @notice Check if manual routing is allowed
     * @dev Manual routing is disabled in Phase 3+ (DAO governance)
     */
    function _checkManualRoutingAllowed() internal view {
        if (governancePhase >= 3) {
            revert ManualRoutingDisabledInDAO();
        }
    }
    
    // ============ View Functions ============
    
    /**
     * @notice Preview routing decision without executing
     */
    function previewRoute(TransactionMetadata calldata _meta) external pure returns (ChainId) {
        return _applyRoutingRules(_meta);
    }
    
    /**
     * @notice Check if manual routing is currently allowed
     */
    function isManualRoutingAllowed() external view returns (bool) {
        return governancePhase < 3;
    }
    
    /**
     * @notice Get routing mode as string
     */
    function getRoutingModeString() external view returns (string memory) {
        if (routingMode == RoutingMode.AUTOMATIC) return "AUTOMATIC";
        if (routingMode == RoutingMode.MANUAL) return "MANUAL";
        return "HYBRID";
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
