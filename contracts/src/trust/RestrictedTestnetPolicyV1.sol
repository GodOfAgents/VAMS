// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ActionContextV1} from "./ActionContextV1.sol";
import {VAMSTimelockController} from "../governance/VAMSTimelockController.sol";
import {GovernedObjectGrantV1} from "./GovernedObjectGrantV1.sol";

/// @notice Bounded current-state policy, governed by the exact VAMS timelock.
/// @dev Not an ethical classifier. No initial policy or effect is authorized.
contract RestrictedTestnetPolicyV1 {
    address public immutable governance;
    bytes32 public immutable hostDomain;
    bytes32 public immutable budgetUnit;
    bytes32 public policyRoot;
    uint256 public policyVersion;
    uint256 public authorityEpoch;
    uint256 public capabilityMask;
    uint256 public maxActionBudget;
    uint256 public maxLifetime;
    mapping(bytes32 => bool) public eligibleRoutes;
    mapping(address => bool) public eligibleInitiators;
    mapping(bytes32 => bool) public revokedObjectGrants;
    event PolicyAdvanced(bytes32 indexed root, uint256 version, uint256 epoch);
    event ObjectGrantRevoked(bytes32 indexed grantDigest, bytes32 indexed actorRoot);

    modifier onlyGovernance() {
        require(msg.sender == governance, "Governance only");
        _;
    }

    constructor(address timelock, bytes32 domain, bytes32 unit) {
        require(timelock.codehash == keccak256(type(VAMSTimelockController).runtimeCode), "Unknown timelock runtime");
        require(VAMSTimelockController(payable(timelock)).getMinDelay() >= 48 hours, "Timelock below 48 hours");
        require(domain != 0 && unit != 0, "Missing domain/unit");
        governance = timelock;
        hostDomain = domain;
        budgetUnit = unit;
    }

    function configure(bytes32 root, uint256 version, uint256 epoch,
        uint256 capabilities, uint256 maxBudget, uint256 lifetime) external onlyGovernance {
        require(root != 0 && version > policyVersion && epoch > authorityEpoch, "Policy must advance");
        require(capabilities != 0 && (capabilities & ~uint256(7)) == 0, "Unsupported capability");
        require(maxBudget > 0 && lifetime > 0 && lifetime <= 24 hours, "Invalid policy bounds");
        policyRoot = root;
        policyVersion = version;
        authorityEpoch = epoch;
        capabilityMask = capabilities;
        maxActionBudget = maxBudget;
        maxLifetime = lifetime;
        emit PolicyAdvanced(root, version, epoch);
    }

    /// @dev Every eligibility edit invalidates all pending approval generations.
    function setEligibility(bytes32 workload, bytes32 provider, bytes32 target, bool enabled) external onlyGovernance {
        require(workload != 0 && provider != 0 && target != 0, "Missing identity");
        eligibleRoutes[sha256(abi.encode(workload, provider, target))] = enabled;
        ++policyVersion;
        ++authorityEpoch;
        emit PolicyAdvanced(policyRoot, policyVersion, authorityEpoch);
    }

    function setInitiator(address actor, bool enabled) external onlyGovernance {
        require(actor != address(0), "Missing actor");
        eligibleInitiators[actor] = enabled;
        ++policyVersion;
        ++authorityEpoch;
        emit PolicyAdvanced(policyRoot, policyVersion, authorityEpoch);
    }

    function authorizesEscrow(address actor, address[] calldata providers, bytes32[] calldata workloads,
        uint256 total, uint256 validity, bytes32 target) external view returns (bool) {
        if (policyRoot == 0 || !eligibleInitiators[actor] || (capabilityMask & uint256(4)) == 0 ||
            total == 0 || total > maxActionBudget || validity > maxLifetime ||
            providers.length == 0 || providers.length != workloads.length) return false;
        for (uint256 i; i < providers.length; ++i) {
            bytes32 provider = bytes32(uint256(uint160(providers[i])));
            if (!eligibleRoutes[sha256(abi.encode(workloads[i], provider, target))]) return false;
        }
        return true;
    }

    function authorizesChallenge(address provider, bytes32 workload, uint256 amount, bytes32 target)
        external view returns (bool) {
        return policyRoot != 0 && (capabilityMask & uint256(4)) != 0 && amount > 0 && amount <= maxActionBudget &&
            eligibleRoutes[sha256(abi.encode(workload, bytes32(uint256(uint160(provider))), target))];
    }

    function authorizes(ActionContextV1.Context memory c) external view returns (bool) {
        // Runtime effects need the typed grant path; signing is not qualified.
        return c.capabilities == 4 && _authorizesContext(c);
    }

    function _authorizesContext(ActionContextV1.Context memory c) private view returns (bool) {
        if (!ActionContextV1.valid(c) || policyRoot == 0 || c.rootScheme != 1 ||
            c.policyRoot != policyRoot || c.policyVersion != policyVersion || c.authorityEpoch != authorityEpoch ||
            c.hostDomain != hostDomain || c.budgetUnit != budgetUnit || c.chainId != block.chainid ||
            c.issuedAt > block.timestamp || c.expiresAt <= block.timestamp ||
            c.expiresAt - c.issuedAt > maxLifetime || (c.capabilities & ~capabilityMask) != 0 ||
            c.budget > maxActionBudget) return false;
        return eligibleRoutes[sha256(abi.encode(ActionContextV1.workloadHash(c), c.providerId, c.target))];
    }

    /// @notice Digest the exact actor consent; the result itself grants no rights.
    function objectGrantDigestV1(GovernedObjectGrantV1.Grant memory grant) external view returns (bytes32) {
        return GovernedObjectGrantV1.digest(grant,address(this),block.chainid,hostDomain,budgetUnit);
    }

    /// @notice Permanently revoke only the caller's own exact grant, including a
    ///         future grant. This cannot widen policy or invalidate other actors.
    function revokeObjectGrantV1(GovernedObjectGrantV1.Grant memory grant) external {
        require(msg.sender != address(0) && grant.actorRoot == bytes32(uint256(uint160(msg.sender))), "Actor only");
        bytes32 digest = GovernedObjectGrantV1.digest(grant,address(this),block.chainid,hostDomain,budgetUnit);
        if (revokedObjectGrants[digest]) return;
        revokedObjectGrants[digest] = true;
        emit ObjectGrantRevoked(digest,grant.actorRoot);
    }

    function _objectGrantAllowed(ActionContextV1.Context memory c, GovernedObjectGrantV1.Witness memory witness,
        bytes32 authorityIssuer, bytes32 providerIssuer) private view returns (bool) {
        if (!GovernedObjectGrantV1.valid(witness.grant) || !_authorizesContext(c) ||
            block.chainid > uint256(uint64(type(int64).max)) || witness.grant.budgetLimit > maxActionBudget ||
            !GovernedObjectGrantV1.matches(witness.grant,c,authorityIssuer,providerIssuer)) return false;
        bytes32 digest = GovernedObjectGrantV1.digest(witness.grant,address(this),block.chainid,hostDomain,budgetUnit);
        return !revokedObjectGrants[digest] && GovernedObjectGrantV1.member(digest,policyRoot,witness.siblings,witness.index) &&
            GovernedObjectGrantV1.consented(witness.grant,digest,witness.consent);
    }

    /// @dev Issuer IDs must be supplied from the actual configured runtime identity.
    ///      This view does not consume an operation, reserve budget or prove an effect.
    function authorizesObjectV1(GovernedObjectGrantV1.Proposal memory p, GovernedObjectGrantV1.Witness memory witness,
        bytes32 authorityIssuer, bytes32 providerIssuer) external view returns (bool) {
        return _objectGrantAllowed(p.context,witness,authorityIssuer,providerIssuer) &&
            p.resourceId != 0 && GovernedObjectGrantV1.includes(witness.grant.resources,p.resourceId) &&
            p.costUnits <= witness.grant.maxActionCost && p.costUnits <= p.context.budget &&
            p.fencingToken > 0 && p.fencingToken <= uint256(uint64(type(int64).max)) &&
            p.context.actionHash == GovernedObjectGrantV1.actionHash(p);
    }

    function authorizesObjectScopeV1(GovernedObjectGrantV1.Scope memory s, GovernedObjectGrantV1.Witness memory witness,
        bytes32 authorityIssuer, bytes32 providerIssuer) external view returns (bool) {
        if (!_objectGrantAllowed(s.context,witness,authorityIssuer,providerIssuer) ||
            !GovernedObjectGrantV1.sortedResources(s.resources) ||
            s.budgetLimit == 0 || s.budgetLimit > s.context.budget || s.maxActionCost > s.budgetLimit ||
            s.maxActionCost > witness.grant.maxActionCost || s.fencingToken == 0 ||
            s.fencingToken > uint256(uint64(type(int64).max))) return false;
        for (uint256 i; i < s.resources.length; ++i) {
            if (!GovernedObjectGrantV1.includes(witness.grant.resources,s.resources[i])) return false;
        }
        return true;
    }
}
