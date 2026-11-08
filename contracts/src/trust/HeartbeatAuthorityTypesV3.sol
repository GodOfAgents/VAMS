// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

library HeartbeatAuthorityTypesV3 {
    uint16 internal constant PROFILE_SCHEMA = 3;
    uint16 internal constant SOURCE_SCHEMA = 3;
    uint16 internal constant CUSTODY_SCHEMA = 1;
    uint8 internal constant EVM_SCHEME = 1;

    uint8 internal constant KEY_POLICY_ALLOW_SAME = 1;
    uint8 internal constant KEY_POLICY_REQUIRE_DISTINCT = 2;
    uint8 internal constant RELAYER_POLICY_PERMISSIONLESS = 1;
    uint8 internal constant RELAYER_POLICY_ADDRESS = 2;
    uint8 internal constant GRACE_POLICY_ZERO = 1;
    uint8 internal constant WITHDRAWAL_POLICY_NO_PERSISTENT_FRAME = 1;
    uint8 internal constant BATCH_POLICY_SINGLE_ONLY = 1;
    uint8 internal constant REQUEUE_POLICY_TIMELOCK_EPOCH = 1;

    bytes32 internal constant PROFILE_PROJECTION_DOMAIN = bytes32("VAMS:CONSENT-PROFILE:V3");
    bytes32 internal constant AUTHORITY_CONFIG_DOMAIN = bytes32("VAMS:AUTHORITY:CONFIG:V3");
    bytes32 internal constant AUTHORITY_SNAPSHOT_DOMAIN = bytes32("VAMS:AUTHORITY:SNAPSHOT:V3");

    struct ProfileConfig {
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
        bytes32 networkContextDigest;
        address custodyAdapter;
        bytes32 custodyAdapterRuntimeCodeHash;
        address challengeProvider;
        bytes32 challengeProviderRuntimeCodeHash;
        bytes32 challengeProfileDigest;
        bytes32 finalityProfileDigest;
    }

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
        bytes32 networkContextDigest;
        address custodyAdapter;
        bytes32 custodyAdapterRuntimeCodeHash;
        address challengeProvider;
        bytes32 challengeProviderRuntimeCodeHash;
        bytes32 challengeProfileDigest;
        bytes32 finalityProfileDigest;
        bytes32 authorityConfigDigest;
    }

    struct CustodyState {
        uint16 schema;
        uint64 changeSequence;
        bytes32 configurationDigest;
    }

    /// @dev This producer state deliberately has no registry address/code-hash fields.
    ///      The V3 consumer must bind its own identity after reading this state.
    struct ProducerState {
        uint16 sourceSchema;
        uint8 scheme;
        uint256 chainId;
        bytes32 networkContextDigest;
        address source;
        bytes32 sourceRuntimeCodeHash;
        address timelock;
        bytes32 timelockRuntimeCodeHash;
        uint64 authorityChangeSequence;
        bytes32 authorityConfigCommitment;
        uint256 minDelay;
        address policy;
        bytes32 policyRuntimeCodeHash;
        bytes32 policyRoot;
        uint64 policyVersion;
        uint64 authorityEpoch;
        bytes32 policyProjectionDigest;
        address custodyAdapter;
        bytes32 custodyAdapterRuntimeCodeHash;
        uint64 custodyChangeSequence;
        bytes32 custodyConfigurationDigest;
        bytes32 authorityConfigDigest;
    }

    /// @dev Static tuple with the same field order as the prior flat authorityConfigDigest ABI.
    struct AuthorityConfigProjection {
        uint16 sourceSchema;
        uint8 scheme;
        uint256 chainId;
        bytes32 networkContextDigest;
        address source;
        bytes32 sourceRuntimeCodeHash;
        address timelock;
        bytes32 timelockRuntimeCodeHash;
        uint64 authorityChangeSequence;
        bytes32 authorityConfigCommitment;
        uint256 minDelay;
        address policy;
        bytes32 policyRuntimeCodeHash;
        bytes32 policyProjectionDigest;
        address custodyAdapter;
        bytes32 custodyAdapterRuntimeCodeHash;
        uint64 custodyChangeSequence;
        bytes32 custodyConfigurationDigest;
    }

    /// @dev Static tuple with the same field order as the prior flat profile projection ABI.
    struct ProfileProjection {
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
        bytes32 networkContextDigest;
        address custodyAdapter;
        bytes32 custodyAdapterRuntimeCodeHash;
        address challengeProvider;
        bytes32 challengeProviderRuntimeCodeHash;
        bytes32 challengeProfileDigest;
        bytes32 finalityProfileDigest;
    }

    function validConfig(ProfileConfig memory p) internal pure returns (bool) {
        return p.policyRoot != bytes32(0) && p.policyVersion != 0 && p.authorityEpoch != 0 &&
            p.maxConsentTtl != 0 && p.maxPrincipalLifetime != 0 &&
            p.oldKeyGracePolicy == GRACE_POLICY_ZERO && p.oldKeyGraceSeconds == 0 &&
            (p.keyPolicy == KEY_POLICY_ALLOW_SAME || p.keyPolicy == KEY_POLICY_REQUIRE_DISTINCT) &&
            (p.relayerPolicy == RELAYER_POLICY_PERMISSIONLESS || p.relayerPolicy == RELAYER_POLICY_ADDRESS) &&
            (p.relayerPolicy != RELAYER_POLICY_ADDRESS || p.allowedRelayer != address(0)) &&
            (p.relayerPolicy != RELAYER_POLICY_PERMISSIONLESS || p.allowedRelayer == address(0)) &&
            p.withdrawalPolicy == WITHDRAWAL_POLICY_NO_PERSISTENT_FRAME &&
            p.batchPolicy == BATCH_POLICY_SINGLE_ONLY &&
            p.requeuePolicy == REQUEUE_POLICY_TIMELOCK_EPOCH &&
            p.networkContextDigest != bytes32(0) &&
            p.custodyAdapter != address(0) && p.custodyAdapterRuntimeCodeHash != bytes32(0) &&
            p.challengeProvider != address(0) && p.challengeProviderRuntimeCodeHash != bytes32(0) &&
            p.challengeProfileDigest != bytes32(0) && p.finalityProfileDigest != bytes32(0);
    }

    /// @dev Explicit field projection; authorityConfigDigest is intentionally excluded.
    function profileProjectionDigest(Profile memory p) internal pure returns (bytes32) {
        ProfileProjection memory projection;
        projection.configured = p.configured;
        projection.schema = p.schema;
        projection.policyRoot = p.policyRoot;
        projection.policyVersion = p.policyVersion;
        projection.authorityEpoch = p.authorityEpoch;
        projection.maxConsentTtl = p.maxConsentTtl;
        projection.maxPrincipalLifetime = p.maxPrincipalLifetime;
        projection.oldKeyGraceSeconds = p.oldKeyGraceSeconds;
        projection.oldKeyGracePolicy = p.oldKeyGracePolicy;
        projection.keyPolicy = p.keyPolicy;
        projection.relayerPolicy = p.relayerPolicy;
        projection.allowedRelayer = p.allowedRelayer;
        projection.withdrawalPolicy = p.withdrawalPolicy;
        projection.batchPolicy = p.batchPolicy;
        projection.requeuePolicy = p.requeuePolicy;
        projection.authoritySource = p.authoritySource;
        projection.authoritySourceRuntimeCodeHash = p.authoritySourceRuntimeCodeHash;
        projection.networkContextDigest = p.networkContextDigest;
        projection.custodyAdapter = p.custodyAdapter;
        projection.custodyAdapterRuntimeCodeHash = p.custodyAdapterRuntimeCodeHash;
        projection.challengeProvider = p.challengeProvider;
        projection.challengeProviderRuntimeCodeHash = p.challengeProviderRuntimeCodeHash;
        projection.challengeProfileDigest = p.challengeProfileDigest;
        projection.finalityProfileDigest = p.finalityProfileDigest;
        return sha256(abi.encode(PROFILE_PROJECTION_DOMAIN, projection));
    }

    /// @dev Static tuple with byte-for-byte field order matching the R2 flat abi.encode inputs.
    function authorityConfigDigest(ProducerState memory s) internal pure returns (bytes32) {
        AuthorityConfigProjection memory projection;
        projection.sourceSchema = s.sourceSchema;
        projection.scheme = s.scheme;
        projection.chainId = s.chainId;
        projection.networkContextDigest = s.networkContextDigest;
        projection.source = s.source;
        projection.sourceRuntimeCodeHash = s.sourceRuntimeCodeHash;
        projection.timelock = s.timelock;
        projection.timelockRuntimeCodeHash = s.timelockRuntimeCodeHash;
        projection.authorityChangeSequence = s.authorityChangeSequence;
        projection.authorityConfigCommitment = s.authorityConfigCommitment;
        projection.minDelay = s.minDelay;
        projection.policy = s.policy;
        projection.policyRuntimeCodeHash = s.policyRuntimeCodeHash;
        projection.policyProjectionDigest = s.policyProjectionDigest;
        projection.custodyAdapter = s.custodyAdapter;
        projection.custodyAdapterRuntimeCodeHash = s.custodyAdapterRuntimeCodeHash;
        projection.custodyChangeSequence = s.custodyChangeSequence;
        projection.custodyConfigurationDigest = s.custodyConfigurationDigest;
        return sha256(abi.encode(AUTHORITY_CONFIG_DOMAIN, projection));
    }

    function authoritySnapshotDigest(ProducerState memory s) internal pure returns (bytes32) {
        return sha256(abi.encode(AUTHORITY_SNAPSHOT_DOMAIN, s));
    }
}

interface IHeartbeatCustodyAuthorityAdapterV1 {
    function currentCustodyState()
        external view returns (HeartbeatAuthorityTypesV3.CustodyState memory state);
}

interface IHeartbeatAuthoritySourceV3 {
    function policy() external view returns (address);
    function timelock() external view returns (address);
    function computeAuthorityConfigDigest() external view returns (bytes32);
    function currentState() external view returns (HeartbeatAuthorityTypesV3.ProducerState memory);
}

