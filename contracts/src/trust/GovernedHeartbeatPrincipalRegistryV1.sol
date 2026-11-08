// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {HeartbeatPrincipalV1} from "./HeartbeatPrincipalV1.sol";
import {RestrictedPolicyRuntimeV1} from "./RestrictedPolicyRuntimeV1.sol";
import {VAMSTimelockController} from "../governance/VAMSTimelockController.sol";

interface IRestrictedHeartbeatPolicyV1 {
    function governance() external view returns (address);
    function hostDomain() external view returns (bytes32);
    function budgetUnit() external view returns (bytes32);
    function policyRoot() external view returns (bytes32);
    function policyVersion() external view returns (uint256);
    function authorityEpoch() external view returns (uint256);
}

interface IHeartbeatSafeIdentityV1 {
    function masterCopy() external view returns (address);
    function getOwners() external view returns (address[] memory);
    function getThreshold() external view returns (uint256);
}

/// @notice Non-upgradeable, timelock-written current-state registry for EVM heartbeat principals.
/// @dev Records are unsigned data. This contract does not verify M2/body-key consent, certificates,
///      native finality, issuer custody, Cardano state, or the authenticity of constructor config.
contract GovernedHeartbeatPrincipalRegistryV1 {
    uint256 public constant MINIMUM_DELAY = 48 hours;

    struct SafeIdentity {
        bytes32 proxyRuntimeCodeHash;
        address singleton;
        bytes32 singletonRuntimeCodeHash;
    }

    struct Entry {
        bytes canonicalRecord;
        bytes32 digest;
        uint64 generation;
        bool tombstone;
    }

    error InvalidConfiguration();
    error PolicyRuntimeMismatch();
    error TimelockIdentityMismatch();
    error PolicyBindingMismatch();
    error InvalidEmergencySafe();
    error Unauthorized();
    error Paused();
    error WrongChain();
    error PolicyUnavailable();
    error StalePolicySnapshot();
    error InvalidRecord();
    error RecordNotCurrentlyValid();
    error CompareAndSetFailed();
    error GenerationOverflow();
    error Tombstoned();

    address public immutable policy;
    address public immutable governance;
    address public immutable emergencySafe;
    bytes32 public immutable hostDomain;
    bytes32 public immutable serviceDomain;
    bytes32 public immutable budgetUnit;
    uint256 public immutable deploymentChainId;
    bool public paused = true;
    mapping(bytes32 principalId => Entry) private _entries;

    event RegistryPaused(address indexed caller);
    event RegistryUnpaused(address indexed caller, bytes32 policyRoot, uint64 policyVersion, uint64 authorityEpoch);
    event PrincipalRegistered(bytes32 indexed principalId, bytes32 indexed digest, uint64 generation);
    event PrincipalReplaced(bytes32 indexed principalId, bytes32 indexed digest, uint64 generation);
    event PrincipalRevoked(bytes32 indexed principalId, bytes32 indexed tombstoneDigest, uint64 generation);

    constructor(
        address policy_,
        address expectedTimelock,
        bytes32 expectedHostDomain,
        bytes32 expectedServiceDomain,
        bytes32 expectedBudgetUnit,
        address emergencySafe_,
        SafeIdentity memory safeIdentity
    ) {
        if (
            policy_ == address(0) || expectedTimelock == address(0) || expectedHostDomain == bytes32(0) ||
            expectedServiceDomain == bytes32(0) || expectedBudgetUnit == bytes32(0) ||
            emergencySafe_ == address(0) || block.chainid == 0
        ) revert InvalidConfiguration();

        // Authenticate exact policy runtime and its supplied immutables before any policy getter call.
        if (!RestrictedPolicyRuntimeV1.matches(
            policy_, expectedTimelock, expectedHostDomain, expectedBudgetUnit
        )) revert PolicyRuntimeMismatch();
        if (
            expectedTimelock.code.length == 0 ||
            expectedTimelock.codehash != keccak256(type(VAMSTimelockController).runtimeCode)
        ) revert TimelockIdentityMismatch();
        if (VAMSTimelockController(payable(expectedTimelock)).getMinDelay() < MINIMUM_DELAY) {
            revert TimelockIdentityMismatch();
        }

        IRestrictedHeartbeatPolicyV1 boundPolicy = IRestrictedHeartbeatPolicyV1(policy_);
        if (
            boundPolicy.governance() != expectedTimelock ||
            boundPolicy.hostDomain() != expectedHostDomain ||
            boundPolicy.budgetUnit() != expectedBudgetUnit
        ) revert PolicyBindingMismatch();

        _validateEmergencySafe(emergencySafe_, safeIdentity);
        policy = policy_;
        governance = expectedTimelock;
        emergencySafe = emergencySafe_;
        hostDomain = expectedHostDomain;
        serviceDomain = expectedServiceDomain;
        budgetUnit = expectedBudgetUnit;
        deploymentChainId = block.chainid;
    }

    /// @notice Emergency authority can only stop registry writes and active results.
    function pause() external {
        if (msg.sender != emergencySafe) revert Unauthorized();
        paused = true;
        emit RegistryPaused(msg.sender);
    }

    /// @notice Only a queued operation executed by the exact VAMS timelock can unpause.
    function unpause(bytes32 expectedRoot, uint64 expectedVersion, uint64 expectedEpoch) external {
        if (msg.sender != governance) revert Unauthorized();
        if (block.chainid != deploymentChainId) revert WrongChain();
        (bytes32 root, uint64 version, uint64 epoch) = _currentPolicySnapshot();
        if (
            root == bytes32(0) || version == 0 || epoch == 0 ||
            root != expectedRoot || version != expectedVersion || epoch != expectedEpoch
        ) revert StalePolicySnapshot();
        paused = false;
        emit RegistryUnpaused(msg.sender, root, version, epoch);
    }

    /// @notice Create the first generation for a scoped principal slot.
    /// @dev The bounded calldata is decoded only after checking its length. Timelock execution is
    ///      the state authority; this function does not claim that consent was cryptographically proven.
    function registerPrincipal(bytes calldata encoded, bytes32 expectedPreviousDigest, uint64 expectedPreviousGeneration)
        external
    {
        _onlyWritableTimelock();
        if (expectedPreviousDigest != bytes32(0) || expectedPreviousGeneration != 0) revert CompareAndSetFailed();
        if (encoded.length > HeartbeatPrincipalV1.MAX_ENCODING_BYTES) revert InvalidRecord();
        (bool ok, HeartbeatPrincipalV1.Record memory record) =
            HeartbeatPrincipalV1.tryDecodeCalldata(encoded);
        if (!ok) revert InvalidRecord();
        bytes32 principalId = record.principalId;
        Entry storage entry = _entries[principalId];
        if (entry.generation != 0 || entry.tombstone || entry.digest != bytes32(0)) revert CompareAndSetFailed();
        if (record.principalGeneration != 1) revert CompareAndSetFailed();
        _requireRecordCurrent(record);
        bytes memory canonical = HeartbeatPrincipalV1.canonicalBytes(record);
        bytes32 digest_ = sha256(canonical);
        entry.canonicalRecord = canonical;
        entry.digest = digest_;
        entry.generation = record.principalGeneration;
        emit PrincipalRegistered(principalId, digest_, record.principalGeneration);
    }

    /// @notice Replace credentials/record fields for the same host/service/node slot.
    function replacePrincipal(
        bytes32 principalId,
        bytes32 expectedPreviousDigest,
        uint64 expectedPreviousGeneration,
        bytes calldata encoded
    ) external {
        _onlyWritableTimelock();
        if (encoded.length > HeartbeatPrincipalV1.MAX_ENCODING_BYTES) revert InvalidRecord();
        Entry storage entry = _entries[principalId];
        if (
            entry.generation != expectedPreviousGeneration || entry.digest != expectedPreviousDigest ||
            entry.generation == 0 || entry.tombstone
        ) revert CompareAndSetFailed();
        if (entry.generation == type(uint64).max) revert GenerationOverflow();
        (bool ok, HeartbeatPrincipalV1.Record memory record) =
            HeartbeatPrincipalV1.tryDecodeCalldata(encoded);
        if (!ok || record.principalId != principalId || record.principalGeneration != entry.generation + 1) {
            revert InvalidRecord();
        }
        _requireRecordCurrent(record);
        bytes memory previous = entry.canonicalRecord;
        (bool previousOk, HeartbeatPrincipalV1.Record memory previousRecord) =
            HeartbeatPrincipalV1.tryDecode(previous);
        if (
            !previousOk || previousRecord.hostDomain != record.hostDomain ||
            previousRecord.serviceDomain != record.serviceDomain ||
            previousRecord.nodeIdCommitment != record.nodeIdCommitment
        ) revert InvalidRecord();
        bytes memory canonical = HeartbeatPrincipalV1.canonicalBytes(record);
        bytes32 digest_ = sha256(canonical);
        entry.canonicalRecord = canonical;
        entry.digest = digest_;
        entry.generation = record.principalGeneration;
        emit PrincipalReplaced(principalId, digest_, record.principalGeneration);
    }

    /// @notice Irreversibly tombstone one exact current slot using CAS and the live policy snapshot.
    function revokePrincipal(
        bytes32 principalId,
        bytes32 expectedPreviousDigest,
        uint64 expectedPreviousGeneration,
        bytes32 expectedPolicyRoot,
        uint64 expectedPolicyVersion,
        uint64 expectedAuthorityEpoch
    ) external {
        _onlyWritableTimelock();
        Entry storage entry = _entries[principalId];
        if (
            entry.generation != expectedPreviousGeneration || entry.digest != expectedPreviousDigest ||
            entry.generation == 0 || entry.tombstone
        ) revert CompareAndSetFailed();
        if (entry.generation == type(uint64).max) revert GenerationOverflow();
        (bytes32 root, uint64 version, uint64 epoch) = _currentPolicySnapshot();
        if (
            root == bytes32(0) || root != expectedPolicyRoot ||
            version != expectedPolicyVersion || epoch != expectedAuthorityEpoch
        ) revert StalePolicySnapshot();
        uint64 nextGeneration = entry.generation + 1;
        bytes32 tombstoneDigest = sha256(abi.encodePacked(
            "VAMS:GATEWAY:HEARTBEAT-TOMBSTONE:v1\x00",
            principalId,
            expectedPreviousDigest,
            bytes8(nextGeneration),
            root,
            bytes8(version),
            bytes8(epoch)
        ));
        entry.digest = tombstoneDigest;
        entry.generation = nextGeneration;
        entry.tombstone = true;
        emit PrincipalRevoked(principalId, tombstoneDigest, nextGeneration);
    }

    /// @notice Return stored data and a conservative local state classification.
    /// @dev This view is an EVM contract result, not a native finalized-state or RPC-authentication proof.
    function principalState(bytes32 principalId)
        external view returns (bytes memory canonicalRecord, bytes32 digest_, uint64 generation, bool tombstone, bool active)
    {
        Entry storage entry = _entries[principalId];
        canonicalRecord = entry.canonicalRecord;
        digest_ = entry.digest;
        generation = entry.generation;
        tombstone = entry.tombstone;
        if (
            paused || block.chainid != deploymentChainId || tombstone || generation == 0 ||
            canonicalRecord.length == 0
        ) return (canonicalRecord, digest_, generation, tombstone, false);
        (bool ok, HeartbeatPrincipalV1.Record memory record) =
            HeartbeatPrincipalV1.tryDecode(canonicalRecord);
        if (!ok || record.principalId != principalId || record.principalGeneration != generation) {
            return (canonicalRecord, digest_, generation, tombstone, false);
        }
        (bytes32 root, uint64 version, uint64 epoch) = _currentPolicySnapshotView();
        active = root != bytes32(0) && root == record.policyRoot &&
            version == record.policyVersion && epoch == record.authorityEpoch &&
            block.timestamp >= record.notBefore && block.timestamp < record.expiresAt;
    }

    function _onlyWritableTimelock() private view {
        if (msg.sender != governance) revert Unauthorized();
        if (paused) revert Paused();
        if (block.chainid != deploymentChainId) revert WrongChain();
    }

    function _requireRecordCurrent(HeartbeatPrincipalV1.Record memory record) private view {
        if (!HeartbeatPrincipalV1.valid(record)) revert InvalidRecord();
        if (record.hostDomain != hostDomain || record.serviceDomain != serviceDomain) revert InvalidRecord();
        if (block.timestamp < record.notBefore || block.timestamp >= record.expiresAt) revert RecordNotCurrentlyValid();
        (bytes32 root, uint64 version, uint64 epoch) = _currentPolicySnapshot();
        if (root == bytes32(0) || record.policyRoot != root || record.policyVersion != version || record.authorityEpoch != epoch) {
            revert StalePolicySnapshot();
        }
    }

    function _currentPolicySnapshot() private view returns (bytes32 root, uint64 version, uint64 epoch) {
        uint256 versionWord = IRestrictedHeartbeatPolicyV1(policy).policyVersion();
        uint256 epochWord = IRestrictedHeartbeatPolicyV1(policy).authorityEpoch();
        if (versionWord > type(uint64).max || epochWord > type(uint64).max) revert PolicyUnavailable();
        root = IRestrictedHeartbeatPolicyV1(policy).policyRoot();
        version = uint64(versionWord);
        epoch = uint64(epochWord);
    }

    function _currentPolicySnapshotView() private view returns (bytes32 root, uint64 version, uint64 epoch) {
        try IRestrictedHeartbeatPolicyV1(policy).policyVersion() returns (uint256 versionWord) {
            if (versionWord > type(uint64).max) return (bytes32(0), 0, 0);
            version = uint64(versionWord);
        } catch { return (bytes32(0), 0, 0); }
        try IRestrictedHeartbeatPolicyV1(policy).authorityEpoch() returns (uint256 epochWord) {
            if (epochWord > type(uint64).max) return (bytes32(0), 0, 0);
            epoch = uint64(epochWord);
        } catch { return (bytes32(0), 0, 0); }
        try IRestrictedHeartbeatPolicyV1(policy).policyRoot() returns (bytes32 rootWord) {
            root = rootWord;
        } catch { return (bytes32(0), 0, 0); }
    }

    function _validateEmergencySafe(address candidate, SafeIdentity memory identity) private view {
        if (
            candidate.code.length == 0 || identity.proxyRuntimeCodeHash == bytes32(0) ||
            candidate.codehash != identity.proxyRuntimeCodeHash || identity.singleton == address(0) ||
            identity.singleton.code.length == 0 || identity.singletonRuntimeCodeHash == bytes32(0) ||
            identity.singleton.codehash != identity.singletonRuntimeCodeHash
        ) revert InvalidEmergencySafe();
        (bool singletonOk, bytes memory singletonData) = _boundedStaticCall(
            candidate, abi.encodeWithSelector(IHeartbeatSafeIdentityV1.masterCopy.selector), 32
        );
        if (!singletonOk || singletonData.length != 32 || _wordAddress(singletonData, 0) != identity.singleton) {
            revert InvalidEmergencySafe();
        }
        (bool ownersOk, bytes memory ownersData) = _boundedStaticCall(
            candidate, abi.encodeWithSelector(IHeartbeatSafeIdentityV1.getOwners.selector), 160
        );
        if (!ownersOk || ownersData.length != 160 || _readWord(ownersData, 0) != 32 || _readWord(ownersData, 32) != 3) {
            revert InvalidEmergencySafe();
        }
        address owner0 = _wordAddress(ownersData, 64);
        address owner1 = _wordAddress(ownersData, 96);
        address owner2 = _wordAddress(ownersData, 128);
        if (
            owner0 == address(0) || owner1 == address(0) || owner2 == address(0) ||
            owner0 == owner1 || owner0 == owner2 || owner1 == owner2
        ) revert InvalidEmergencySafe();
        (bool thresholdOk, bytes memory thresholdData) = _boundedStaticCall(
            candidate, abi.encodeWithSelector(IHeartbeatSafeIdentityV1.getThreshold.selector), 32
        );
        if (!thresholdOk || thresholdData.length != 32 || _readWord(thresholdData, 0) != 2) {
            revert InvalidEmergencySafe();
        }
    }

    function _wordAddress(bytes memory raw, uint256 offset) private pure returns (address result) {
        uint256 word = _readWord(raw, offset);
        if (word >> 160 != 0) return address(0);
        result = address(uint160(word));
    }

    function _readWord(bytes memory raw, uint256 offset) private pure returns (uint256 result) {
        assembly { result := mload(add(add(raw, 0x20), offset)) }
    }

    function _boundedStaticCall(address target, bytes memory input, uint256 expectedReturnLength)
        private view returns (bool success, bytes memory result)
    {
        result = new bytes(expectedReturnLength);
        uint256 actualLength;
        assembly {
            success := staticcall(gas(), target, add(input, 0x20), mload(input), add(result, 0x20), expectedReturnLength)
            actualLength := returndatasize()
        }
        if (!success || actualLength != expectedReturnLength) return (false, result);
    }
}
