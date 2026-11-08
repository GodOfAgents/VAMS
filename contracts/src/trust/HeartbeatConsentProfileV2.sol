// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Typed, versioned dependencies for the isolated consent-gated registry prototype.
/// @dev A configured value is still an input, not proof of deployment trust or custody.
library HeartbeatConsentProfileV2 {
    uint16 internal constant PROFILE_SCHEMA = 2;
    uint16 internal constant AUTHORITY_SOURCE_SCHEMA = 2;
    uint16 internal constant REGISTRY_SCHEMA = 2;
    uint16 internal constant CHALLENGE_SCHEMA = 2;
    uint8 internal constant EVM_SCHEME = 1;

    uint8 internal constant KEY_POLICY_UNSET = 0;
    uint8 internal constant KEY_POLICY_ALLOW_SAME = 1;
    uint8 internal constant KEY_POLICY_REQUIRE_DISTINCT = 2;

    uint8 internal constant RELAYER_POLICY_UNSET = 0;
    uint8 internal constant RELAYER_POLICY_PERMISSIONLESS = 1;
    uint8 internal constant RELAYER_POLICY_ADDRESS = 2;

    uint8 internal constant GRACE_POLICY_UNSET = 0;
    uint8 internal constant GRACE_POLICY_ZERO = 1;
    uint8 internal constant GRACE_POLICY_BOUNDED = 2;

    uint8 internal constant WITHDRAWAL_POLICY_UNSET = 0;
    uint8 internal constant WITHDRAWAL_POLICY_NO_PERSISTENT_CONSENT_FRAME = 1;

    uint8 internal constant BATCH_POLICY_UNSET = 0;
    uint8 internal constant BATCH_POLICY_SINGLE_ONLY = 1;

    uint8 internal constant REQUEUE_POLICY_UNSET = 0;
    uint8 internal constant REQUEUE_POLICY_TIMELOCK_EPOCH = 1;

    struct Profile {
        bool configured;
        uint16 schema;
        bytes32 policyRoot;
        uint64 policyVersion;
        uint64 authorityEpoch;
        uint64 maxConsentTtl;
        uint64 maxPrincipalLifetime;
        uint64 oldKeyGraceSeconds;
        uint8 oldKeyGracePolicy;
        uint8 keyPolicy;
        uint8 relayerPolicy;
        address allowedRelayer;
        uint8 withdrawalPolicy;
        uint8 batchPolicy;
        uint8 requeuePolicy;
        address authoritySource;
        bytes32 authoritySourceRuntimeCodeHash;
        address challengeProvider;
        bytes32 challengeProviderRuntimeCodeHash;
        bytes32 authorityConfigDigest;
        bytes32 networkContextDigest;
        bytes32 challengeProfileDigest;
        bytes32 finalityProfileDigest;
    }

    struct AuthoritySnapshot {
        uint16 sourceSchema;
        uint8 scheme;
        uint16 registrySchema;
        uint256 chainId;
        bytes32 networkContextDigest;
        address registry;
        bytes32 registryRuntimeCodeHash;
        address policy;
        bytes32 policyRuntimeCodeHash;
        address timelock;
        bytes32 timelockRuntimeCodeHash;
        bytes32 authorityConfigDigest;
        uint64 authorityChangeSequence;
        bytes32 policyRoot;
        uint64 policyVersion;
        uint64 authorityEpoch;
        bool isProxy;
    }

    struct ChallengeFacts {
        uint16 schema;
        bytes32 networkContextDigest;
        bytes32 operationId;
        uint64 operationEpoch;
        uint64 queuedEta;
        bytes32 baseIntentDigest;
        bytes32 challengeCommitment;
        uint64 issuedAt;
        uint64 expiresAt;
        bytes32 challengeProfileDigest;
        bytes32 finalityProfileDigest;
        bytes32 evidenceDigest;
        bool revoked;
    }

    function validProfile(Profile memory p) internal view returns (bool) {
        if (!p.configured || p.schema != PROFILE_SCHEMA || p.policyRoot == bytes32(0) ||
            p.policyVersion == 0 || p.authorityEpoch == 0 || p.maxConsentTtl == 0 ||
            p.maxPrincipalLifetime == 0 ||
            p.oldKeyGracePolicy != GRACE_POLICY_ZERO || p.oldKeyGraceSeconds != 0 ||
            (p.keyPolicy != KEY_POLICY_ALLOW_SAME && p.keyPolicy != KEY_POLICY_REQUIRE_DISTINCT) ||
            (p.relayerPolicy != RELAYER_POLICY_PERMISSIONLESS && p.relayerPolicy != RELAYER_POLICY_ADDRESS) ||
            (p.relayerPolicy == RELAYER_POLICY_ADDRESS && p.allowedRelayer == address(0)) ||
            (p.relayerPolicy == RELAYER_POLICY_PERMISSIONLESS && p.allowedRelayer != address(0)) ||
            p.withdrawalPolicy != WITHDRAWAL_POLICY_NO_PERSISTENT_CONSENT_FRAME ||
            p.batchPolicy != BATCH_POLICY_SINGLE_ONLY || p.requeuePolicy != REQUEUE_POLICY_TIMELOCK_EPOCH ||
            p.authoritySource == address(0) || p.authoritySourceRuntimeCodeHash == bytes32(0) ||
            p.authoritySource.code.length == 0 || p.authoritySource.codehash != p.authoritySourceRuntimeCodeHash ||
            p.challengeProvider == address(0) || p.challengeProviderRuntimeCodeHash == bytes32(0) ||
            p.challengeProvider.code.length == 0 || p.challengeProvider.codehash != p.challengeProviderRuntimeCodeHash ||
            p.authorityConfigDigest == bytes32(0) || p.networkContextDigest == bytes32(0) ||
            p.challengeProfileDigest == bytes32(0) || p.finalityProfileDigest == bytes32(0)) return false;
        return true;
    }

    function authorityDigest(AuthoritySnapshot memory s) internal pure returns (bytes32) {
        return sha256(abi.encodePacked(
            "VAMS:GATEWAY:AUTHORITY-SOURCE:v2\x00",
            abi.encode(s)
        ));
    }
}

interface IHeartbeatConsentProfileV2 {
    function governance() external view returns (address);
    function consentProfile() external view returns (HeartbeatConsentProfileV2.Profile memory);
}

interface IHeartbeatAuthoritySourceV2 {
    function currentSnapshot() external view returns (HeartbeatConsentProfileV2.AuthoritySnapshot memory);
}

interface IHeartbeatChallengeProviderV2 {
    function resolveChallenge(bytes calldata evidence)
        external view returns (HeartbeatConsentProfileV2.ChallengeFacts memory);
}

