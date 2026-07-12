// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import "../interfaces/IHardwareCommitment.sol";
import "./IProviderBondRegistry.sol";
import "../interfaces/IVAMSHardwareRegistry.sol";
import "../interfaces/ISLAEnforcer.sol";

/**
 * @title HardwareCommitment
 * @notice Enforces time-locked hardware commitments.
 */
contract HardwareCommitment is 
    Initializable, 
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard,
    IHardwareCommitment 
{
    bytes32 public constant SLA_ENFORCER_ROLE = keccak256("SLA_ENFORCER_ROLE");
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    IVAMSHardwareRegistry public registry;
    IProviderBondRegistry public bondRegistry;

    mapping(bytes32 => HardwareCommitment) private _commitments;
    mapping(address => bytes32[]) private _providerCommitments;
    // Track which commitment ID a nodeId is tied to right now
    mapping(bytes32 => bytes32) private _activeNodeCommitments;

    uint256 public constant MIN_COMMITMENT_DURATION = 30 days;
    
    // Slashing constants
    uint256 public constant EARLY_EXIT_SLASH_BPS = 2500; // 25% slash to leave early

    event RegistryUpdated(address newRegistry);
    event BondRegistryUpdated(address newBondRegistry);

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(
        address admin,
        address _registry,
        address _bondRegistry
    ) external initializer {
        if (admin == address(0) || _registry == address(0) || _bondRegistry == address(0)) revert("Zero Address");
        
        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);

        registry = IVAMSHardwareRegistry(_registry);
        bondRegistry = IProviderBondRegistry(_bondRegistry);
    }

    // ============ Core Actions ============

    function createCommitment(
        bytes32[] calldata nodeIds, 
        uint256 durationSeconds, 
        uint256 minUptimeBps
    ) external nonReentrant whenNotPaused returns (bytes32 commitmentId) {
        if (nodeIds.length == 0) revert ZeroNodeCommitment();
        if (durationSeconds < MIN_COMMITMENT_DURATION) revert("Duration too short");

        uint256 baseCollateral = 0;
        
        for (uint i = 0; i < nodeIds.length; i++) {
            bytes32 nid = nodeIds[i];
            IVAMSHardwareRegistry.VAMSResourceNode memory node = registry.getNode(nid);
            
            if (node.provider != msg.sender) revert NodeNotOwnedByProvider(nid, msg.sender);
            
            // Check if already committed
            if (_activeNodeCommitments[nid] != bytes32(0)) {
                revert("Node already committed");
            }
            
            baseCollateral += node.collateralStaked;
        }

        uint256 _requiredCollateral = calculateDiscountedCollateral(baseCollateral, durationSeconds);

        commitmentId = keccak256(abi.encodePacked(msg.sender, block.timestamp, nodeIds[0]));

        HardwareCommitment storage c = _commitments[commitmentId];
        c.provider = msg.sender;
        c.nodeIds = nodeIds;
        c.collateral = _requiredCollateral;
        c.commitmentStart = block.timestamp;
        c.commitmentEnd = block.timestamp + durationSeconds;
        c.minUptimeBps = minUptimeBps;
        c.isActive = true;

        for (uint i = 0; i < nodeIds.length; i++) {
            _activeNodeCommitments[nodeIds[i]] = commitmentId;
        }

        _providerCommitments[msg.sender].push(commitmentId);

        // Interact only after the commitment is fully visible to callbacks.
        bondRegistry.lockHardwareCollateral(msg.sender, _requiredCollateral);

        emit CommitmentCreated(commitmentId, msg.sender, durationSeconds, c.collateral);
        return commitmentId;
    }

    function extendCommitment(bytes32 commitmentId, uint256 additionalSeconds) external nonReentrant whenNotPaused {
        HardwareCommitment storage c = _commitments[commitmentId];
        if (!c.isActive) revert CommitmentInactive(commitmentId);
        if (c.provider != msg.sender) revert UnauthorizedProvider(msg.sender, c.provider);

        c.commitmentEnd += additionalSeconds;

        emit CommitmentExtended(commitmentId, c.commitmentEnd, 0); // Collateral calculation omits internal additions here for simplicity
    }

    function endCommitment(bytes32 commitmentId) external nonReentrant {
        HardwareCommitment storage c = _commitments[commitmentId];
        if (!c.isActive) revert CommitmentInactive(commitmentId);
        if (c.provider != msg.sender) revert UnauthorizedProvider(msg.sender, c.provider);

        if (block.timestamp < c.commitmentEnd) {
            revert CommitmentNotExpired(commitmentId, block.timestamp, c.commitmentEnd);
        }

        c.isActive = false;

        for (uint i = 0; i < c.nodeIds.length; i++) {
            delete _activeNodeCommitments[c.nodeIds[i]];
        }

        bondRegistry.unlockHardwareCollateral(msg.sender, c.collateral);

        emit CommitmentEnded(commitmentId, msg.sender, c.collateral);
    }

    function slashCommitment(bytes32 commitmentId, uint256 penaltyBps) external onlyRole(SLA_ENFORCER_ROLE) nonReentrant {
        HardwareCommitment storage c = _commitments[commitmentId];
        if (!c.isActive) revert CommitmentInactive(commitmentId);

        uint256 slashAmount = (c.collateral * penaltyBps) / 10000;
        c.totalSlashed += slashAmount;

        // In a real execution, we trigger ProviderBondRegistry or VAMSSlasher.
        
        emit CommitmentSlashed(commitmentId, slashAmount, "SLA Violation");
    }

    // ============ Internal Math ============
    
    function calculateDiscountedCollateral(uint256 baseCollateral, uint256 durationSeconds) public pure returns (uint256) {
        if (durationSeconds >= 180 days) {
            return (baseCollateral * 60) / 100; // 0.6x
        } else if (durationSeconds >= 90 days) {
            return (baseCollateral * 80) / 100; // 0.8x
        } else {
            return baseCollateral; // 1.0x
        }
    }

    // ============ Views ============

    function getCommitment(bytes32 commitmentId) external view returns (HardwareCommitment memory) {
        return _commitments[commitmentId];
    }

    function getProviderCommitments(address provider) external view returns (bytes32[] memory) {
        return _providerCommitments[provider];
    }
    
    function isNodeCommitted(bytes32 nodeId) external view returns (bool, bytes32) {
        bytes32 cid = _activeNodeCommitments[nodeId];
        if (cid == bytes32(0)) return (false, bytes32(0));
        HardwareCommitment memory c = _commitments[cid];
        if (c.isActive && block.timestamp < c.commitmentEnd) {
            return (true, cid);
        }
        return (false, bytes32(0));
    }
}
