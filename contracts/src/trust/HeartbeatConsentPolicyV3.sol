// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {OperationAwareVAMSTimelockControllerV3} from "../governance/OperationAwareVAMSTimelockControllerV3.sol";
import {
    HeartbeatAuthorityTypesV3 as Types,
    IHeartbeatAuthoritySourceV3
} from "./HeartbeatAuthorityTypesV3.sol";

/// @notice Inactive V3 consent policy whose authority digest is computed from live producer reads.
/// @dev Expected source hash is deployment input here; the future V3 consumer must independently
///      pin the reviewed SourceV3 runtime hash and must not trust this value by itself.
contract HeartbeatConsentPolicyV3 {
    error Unauthorized();
    error TimelockIdentityMismatch();
    error InvalidPolicyConfiguration();
    error AuthoritySourceAlreadyBound();
    error AuthoritySourceIdentityMismatch();
    error AuthorityConfigurationUnavailable();

    uint256 public constant RECOVERY_DELAY = 48 hours;

    address public governance;
    bytes32 public timelockRuntimeCodeHash;
    bytes32 public expectedAuthoritySourceRuntimeCodeHash;
    address public authoritySource;
    bytes32 public policyRoot;
    uint64 public policyVersion;
    uint64 public authorityEpoch;

    Types.Profile private _profile;

    event AuthoritySourceBound(address indexed source, bytes32 runtimeCodeHash);
    event ConsentPolicyAdvanced(bytes32 indexed root, uint64 version, uint64 epoch, bytes32 authorityConfigDigest);

    constructor(address timelock_, bytes32 expectedSourceRuntimeCodeHash_) {
        bytes32 expectedTimelockHash = keccak256(type(OperationAwareVAMSTimelockControllerV3).runtimeCode);
        if (
            timelock_ == address(0) || timelock_.code.length == 0 ||
            timelock_.codehash != expectedTimelockHash ||
            OperationAwareVAMSTimelockControllerV3(payable(timelock_)).getMinDelay() < RECOVERY_DELAY ||
            expectedSourceRuntimeCodeHash_ == bytes32(0)
        ) revert TimelockIdentityMismatch();
        governance = timelock_;
        timelockRuntimeCodeHash = expectedTimelockHash;
        expectedAuthoritySourceRuntimeCodeHash = expectedSourceRuntimeCodeHash_;
    }

    function consentProfile() external view returns (Types.Profile memory) {
        return _profile;
    }

    /// @notice One-time Timelock binding to the exact source artifact hash supplied at deployment.
    /// @dev The V3 consumer independently pins the source implementation class.
    function bindAuthoritySource(address source_) external {
        if (msg.sender != governance) revert Unauthorized();
        if (authoritySource != address(0)) revert AuthoritySourceAlreadyBound();
        if (
            source_ == address(0) || source_.code.length == 0 ||
            source_.codehash != expectedAuthoritySourceRuntimeCodeHash
        ) revert AuthoritySourceIdentityMismatch();
        // A matching implementation can have been constructed for another instance.
        IHeartbeatAuthoritySourceV3 source = IHeartbeatAuthoritySourceV3(source_);
        if (source.policy() != address(this) || source.timelock() != governance) {
            revert AuthoritySourceIdentityMismatch();
        }
        authoritySource = source_;
        emit AuthoritySourceBound(source_, source_.codehash);
    }

    /// @notice Stage a complete explicit profile, then compute its digest from current on-chain state.
    /// @dev The input has no digest field. Failure in the source/adaptor reverts the whole update.
    function configure(Types.ProfileConfig calldata next) external {
        if (msg.sender != governance) revert Unauthorized();
        if (
            authoritySource == address(0) ||
            authoritySource.codehash != expectedAuthoritySourceRuntimeCodeHash ||
            !Types.validConfig(next) ||
            next.custodyAdapter.code.length == 0 ||
            next.custodyAdapter.codehash != next.custodyAdapterRuntimeCodeHash ||
            next.challengeProvider.code.length == 0 ||
            next.challengeProvider.codehash != next.challengeProviderRuntimeCodeHash ||
            next.policyVersion <= policyVersion || next.authorityEpoch <= authorityEpoch ||
            next.policyRoot == bytes32(0)
        ) revert InvalidPolicyConfiguration();

        Types.Profile memory staged = Types.Profile({
            configured: true,
            schema: Types.PROFILE_SCHEMA,
            policyRoot: next.policyRoot,
            policyVersion: next.policyVersion,
            authorityEpoch: next.authorityEpoch,
            maxConsentTtl: next.maxConsentTtl,
            maxPrincipalLifetime: next.maxPrincipalLifetime,
            oldKeyGraceSeconds: next.oldKeyGraceSeconds,
            oldKeyGracePolicy: next.oldKeyGracePolicy,
            keyPolicy: next.keyPolicy,
            relayerPolicy: next.relayerPolicy,
            allowedRelayer: next.allowedRelayer,
            withdrawalPolicy: next.withdrawalPolicy,
            batchPolicy: next.batchPolicy,
            requeuePolicy: next.requeuePolicy,
            authoritySource: authoritySource,
            authoritySourceRuntimeCodeHash: expectedAuthoritySourceRuntimeCodeHash,
            networkContextDigest: next.networkContextDigest,
            custodyAdapter: next.custodyAdapter,
            custodyAdapterRuntimeCodeHash: next.custodyAdapterRuntimeCodeHash,
            challengeProvider: next.challengeProvider,
            challengeProviderRuntimeCodeHash: next.challengeProviderRuntimeCodeHash,
            challengeProfileDigest: next.challengeProfileDigest,
            finalityProfileDigest: next.finalityProfileDigest,
            authorityConfigDigest: bytes32(0)
        });

        policyRoot = next.policyRoot;
        policyVersion = next.policyVersion;
        authorityEpoch = next.authorityEpoch;
        _profile = staged;

        bytes32 computed;
        try IHeartbeatAuthoritySourceV3(authoritySource).computeAuthorityConfigDigest() returns (bytes32 digest) {
            computed = digest;
        } catch {
            revert AuthorityConfigurationUnavailable();
        }
        if (computed == bytes32(0)) revert AuthorityConfigurationUnavailable();
        _profile.authorityConfigDigest = computed;
        emit ConsentPolicyAdvanced(next.policyRoot, next.policyVersion, next.authorityEpoch, computed);
    }
}

