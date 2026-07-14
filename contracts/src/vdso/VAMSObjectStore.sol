// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VDSOCanaryAccess} from "./VDSOCanaryAccess.sol";
import {VDSOTypes} from "./VDSOTypes.sol";

/// @title VAMSObjectStore
/// @notice Versioned VDSO object commitments with one authoritative writer per domain.
/// @dev Polygon and Cardano remain peer hosts. Authority is assigned per state
///      domain, so no contract-wide canonical-host assumption is introduced.
contract VAMSObjectStore is VDSOCanaryAccess {
    bytes32 public constant AUTHORITY_ADMIN_ROLE = keccak256("VDSO_AUTHORITY_ADMIN_ROLE");
    bytes32 public constant KERNEL_ROLE = keccak256("VDSO_OBJECT_KERNEL_ROLE");

    struct DomainAuthority {
        VDSOTypes.Host host;
        address writer;
        uint64 epoch;
        bool enabled;
    }

    struct ObjectHeader {
        bytes32 domainId;
        bytes32 stateRoot;
        bytes32 evidenceRoot;
        uint64 version;
        uint64 updatedAt;
    }

    mapping(bytes32 domainId => DomainAuthority authority) private _domainAuthorities;
    mapping(bytes32 objectId => ObjectHeader header) private _objects;

    event DomainAuthorityAssigned(
        bytes32 indexed domainId, VDSOTypes.Host indexed host, address indexed writer, uint64 epoch
    );
    event DomainAuthorityDisabled(bytes32 indexed domainId, uint64 indexed epoch);
    event ObjectWritten(
        bytes32 indexed objectId, bytes32 indexed domainId, uint64 version, bytes32 stateRoot, bytes32 evidenceRoot
    );

    error InvalidDomain();
    error InvalidHost();
    error UnauthorizedDomainWriter(bytes32 domainId, address caller);
    error DomainAuthorityUnavailable(bytes32 domainId);
    error ObjectDomainMismatch(bytes32 expectedDomain, bytes32 suppliedDomain);
    error VersionMismatch(uint64 expectedVersion, uint64 actualVersion);
    error EmptyCommitment();

    constructor(address admin, address pauser) VDSOCanaryAccess(admin, pauser) {
        _grantRole(AUTHORITY_ADMIN_ROLE, admin);
    }

    /// @notice Atomically replaces the sole writer for a state domain.
    /// @dev Deployment governance should hold this role behind its external timelock.
    function assignDomainAuthority(bytes32 domainId, VDSOTypes.Host host, address writer)
        external
        onlyRole(AUTHORITY_ADMIN_ROLE)
    {
        if (domainId == bytes32(0)) revert InvalidDomain();
        if (host == VDSOTypes.Host.NONE) revert InvalidHost();
        if (writer == address(0)) revert InvalidAddress();

        DomainAuthority storage authority = _domainAuthorities[domainId];
        uint64 newEpoch = authority.epoch + 1;
        authority.host = host;
        authority.writer = writer;
        authority.epoch = newEpoch;
        authority.enabled = true;

        emit DomainAuthorityAssigned(domainId, host, writer, newEpoch);
    }

    /// @notice Removes all write authority from a domain without deleting state.
    function disableDomainAuthority(bytes32 domainId) external onlyRole(AUTHORITY_ADMIN_ROLE) {
        DomainAuthority storage authority = _domainAuthorities[domainId];
        if (!authority.enabled) revert DomainAuthorityUnavailable(domainId);
        authority.enabled = false;
        authority.writer = address(0);
        authority.epoch += 1;
        emit DomainAuthorityDisabled(domainId, authority.epoch);
    }

    /// @notice Writes a new object version using compare-and-swap semantics.
    function writeObject(
        bytes32 objectId,
        bytes32 domainId,
        uint64 expectedVersion,
        bytes32 newStateRoot,
        bytes32 evidenceRoot
    ) external onlyRole(KERNEL_ROLE) whenNotPaused returns (uint64 newVersion) {
        if (objectId == bytes32(0) || domainId == bytes32(0)) revert InvalidDomain();
        if (newStateRoot == bytes32(0)) revert EmptyCommitment();

        DomainAuthority memory authority = _domainAuthorities[domainId];
        if (!authority.enabled) revert DomainAuthorityUnavailable(domainId);
        if (msg.sender != authority.writer) {
            revert UnauthorizedDomainWriter(domainId, msg.sender);
        }

        ObjectHeader storage header = _objects[objectId];
        if (header.version != expectedVersion) {
            revert VersionMismatch(expectedVersion, header.version);
        }
        if (header.version != 0 && header.domainId != domainId) {
            revert ObjectDomainMismatch(header.domainId, domainId);
        }

        newVersion = expectedVersion + 1;
        header.domainId = domainId;
        header.stateRoot = newStateRoot;
        header.evidenceRoot = evidenceRoot;
        header.version = newVersion;
        header.updatedAt = uint64(block.timestamp);

        emit ObjectWritten(objectId, domainId, newVersion, newStateRoot, evidenceRoot);
    }

    function getDomainAuthority(bytes32 domainId) external view returns (DomainAuthority memory) {
        return _domainAuthorities[domainId];
    }

    function getObject(bytes32 objectId) external view returns (ObjectHeader memory) {
        return _objects[objectId];
    }
}
