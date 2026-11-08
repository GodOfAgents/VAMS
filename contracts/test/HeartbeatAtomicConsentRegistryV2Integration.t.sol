// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Vm} from "forge-std/Vm.sol";
import {OperationAwareVAMSTimelockControllerV2} from "../src/governance/OperationAwareVAMSTimelockControllerV2.sol";
import {HeartbeatConsentPolicyV2} from "../src/trust/HeartbeatConsentPolicyV2.sol";
import {HeartbeatConsentVerificationRouterV2} from "../src/trust/HeartbeatConsentVerificationRouterV2.sol";
import {HeartbeatAtomicConsentRegistryV2} from "../src/trust/HeartbeatAtomicConsentRegistryV2.sol";
import {HeartbeatConsentV2 as Consent} from "../src/trust/HeartbeatConsentV2.sol";
import {HeartbeatPrincipalV1 as Principal} from "../src/trust/HeartbeatPrincipalV1.sol";
import {HeartbeatConsentProfileV2 as Types} from "../src/trust/HeartbeatConsentProfileV2.sol";

contract SyntheticAuthoritySourceV2 {
    Types.AuthoritySnapshot private _snapshot;
    function set(Types.AuthoritySnapshot calldata value) external { _snapshot = value; }
    function currentSnapshot() external view returns (Types.AuthoritySnapshot memory) { return _snapshot; }
}

contract SyntheticChallengeProviderV2 {
    Types.ChallengeFacts private _facts;
    OperationAwareVAMSTimelockControllerV2 private _lock;
    bool private _changeEpochOnlyDuringCallback;
    address private _reentryTarget;
    bytes private _reentryCall;

    error NestedRelayWasNotRejected();

    function set(Types.ChallengeFacts calldata value) external { _facts = value; }

    function setCallbackEpochMismatch(address lock_, bool enabled) external {
        _lock = OperationAwareVAMSTimelockControllerV2(payable(lock_));
        _changeEpochOnlyDuringCallback = enabled;
    }

    function setStaticReentryProbe(address target, bytes calldata relayCall) external {
        _reentryTarget = target;
        _reentryCall = relayCall;
    }

    function resolveChallenge(bytes calldata) external view returns (Types.ChallengeFacts memory facts) {
        facts = _facts;
        if (_reentryTarget != address(0)) {
            (bool ok, bytes memory result) = _reentryTarget.staticcall(_reentryCall);
            bytes4 selector;
            if (result.length >= 4) assembly { selector := mload(add(result, 32)) }
            if (ok || selector != bytes4(keccak256("ReentrantCall()"))) revert NestedRelayWasNotRejected();
        }
        if (_changeEpochOnlyDuringCallback) {
            (bool active,,) = _lock.activeOperationContext();
            if (active) ++facts.operationEpoch;
        }
    }
}

/// @dev Test-only seed surface represents a separately governed existing principal migration.
contract SeedableHeartbeatRegistryV2 is HeartbeatAtomicConsentRegistryV2 {
    constructor(address t, address p, address v, bytes32 h, bytes32 s) HeartbeatAtomicConsentRegistryV2(t,p,v,h,s) {}
    function seed(bytes32 id, bytes calldata record, uint64 nonce, uint64 authoritySequence) external {
        (bool ok, HeartbeatConsentVerificationRouterV2.PrincipalView memory decoded, bytes32 digest) =
            HeartbeatConsentVerificationRouterV2(verifier).decodePrincipal(record);
        require(ok && decoded.principalId == id, "valid synthetic seed only");
        _entries[id] = Entry(record, digest, decoded.principalGeneration, nonce, authoritySequence);
    }
}

contract HeartbeatAtomicConsentRegistryV2IntegrationTests is Test {
    uint256 private constant OLD_KEY = 11;
    uint256 private constant NEW_KEY = 12;
    uint256 private constant M2_KEY = 13;
    uint256 private constant N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
    string private constant SIG_DOMAIN = "VAMS:GATEWAY:HEARTBEAT-CONSENT-SIGNATURE:v2";
    bytes32 private constant ROOT = keccak256("synthetic-governed-root");
    bytes32 private constant AUTH_CONFIG = keccak256("synthetic-authority-config");
    bytes32 private constant NETWORK = keccak256("synthetic-evm-network");
    bytes32 private constant CHALLENGE_PROFILE = keccak256("synthetic-challenge-profile");
    bytes32 private constant FINALITY_PROFILE = keccak256("synthetic-finality-profile");

    OperationAwareVAMSTimelockControllerV2 private lock;
    HeartbeatConsentPolicyV2 private policy;
    HeartbeatConsentVerificationRouterV2 private verifier;
    SeedableHeartbeatRegistryV2 private registry;
    SyntheticAuthoritySourceV2 private authority;
    SyntheticChallengeProviderV2 private challenges;
    Principal.Record private oldRecord;
    bytes private oldRaw;

    function setUp() public {
        vm.warp(1_800_000_000);
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        lock = new OperationAwareVAMSTimelockControllerV2(48 hours, proposers, executors, address(this));
        policy = new HeartbeatConsentPolicyV2(address(lock));
        verifier = new HeartbeatConsentVerificationRouterV2();
        registry = new SeedableHeartbeatRegistryV2(address(lock), address(policy), address(verifier), bytes32(uint256(1)), bytes32(uint256(2)));
        authority = new SyntheticAuthoritySourceV2();
        challenges = new SyntheticChallengeProviderV2();
        _installSyntheticPolicy();
        _executeGovernance(address(lock), abi.encodeCall(lock.grantRole, (lock.EXECUTOR_ROLE(), address(registry))), keccak256("grant-registry-executor"));
        oldRecord = _record(OLD_KEY, 1);
        oldRaw = Principal.canonicalBytes(oldRecord);
        registry.seed(oldRecord.principalId, oldRaw, 0, 1);
    }

    function testNormalRotationAtomicallyUpdatesRecordAndNonceOnce() public {
        _submit(Consent.MODE_ROTATE_NORMAL, false);
        (, bytes32 digest, uint64 generation, uint64 nonce, uint64 sequence) = registry.principalState(oldRecord.principalId);
        require(generation == 2 && nonce == 1 && sequence == 1, "single atomic state advance");
        require(digest != Principal.digest(oldRecord), "proposed record installed");
    }

    function testRecoveryUsesNewKeyOnlyAndObservedFortyEightHourSchedule() public {
        _submit(Consent.MODE_RECOVER_LOST_KEY, false);
        (, , uint64 generation, uint64 nonce,) = registry.principalState(oldRecord.principalId);
        require(generation == 2 && nonce == 1, "recovery consumes one nonce");
    }

    function testNormalRotationRejectsMissingOldRoleBeforeMutation() public {
        Prepared memory p = _prepare(Consent.MODE_ROTATE_NORMAL, true);
        vm.warp(p.eta);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.InvalidConsent.selector);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
        (, bytes32 digest, uint64 generation, uint64 nonce,) = registry.principalState(oldRecord.principalId);
        require(digest == Principal.digest(oldRecord) && generation == 1 && nonce == 0, "missing role leaves state unchanged");
    }

    function testAuthorityAtoBtoASequenceChangeInvalidatesProof() public {
        Prepared memory p = _prepare(Consent.MODE_ROTATE_NORMAL, false);
        Types.AuthoritySnapshot memory original = authority.currentSnapshot();
        Types.AuthoritySnapshot memory changed = original;
        changed.policyRoot = keccak256("temporary-root-B");
        changed.authorityChangeSequence = 2;
        authority.set(changed);
        authority.set(original);
        original.authorityChangeSequence = 3;
        authority.set(original);
        vm.warp(p.eta);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.AuthorityUnavailable.selector);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
        (, bytes32 digest, uint64 generation, uint64 nonce,) = registry.principalState(oldRecord.principalId);
        require(digest == Principal.digest(oldRecord) && generation == 1 && nonce == 0, "authority change leaves state unchanged");
    }

    function testCancelAndIdenticalRequeueInvalidatesBoundChallengeEpoch() public {
        Prepared memory p = _prepare(Consent.MODE_ROTATE_NORMAL, false);
        bytes memory queuedCall = abi.encodeCall(registry.applyConsent, (p.baseRaw, p.proposedRaw));
        (bool ok, Consent.BaseIntent memory b) = Consent.tryDecodeBase(p.baseRaw);
        require(ok, "synthetic base");
        uint64 oldEpoch = lock.operationEpoch(p.operationId);
        lock.cancel(p.operationId);
        lock.schedule(address(registry), 0, queuedCall, b.timelockPredecessor, b.timelockSalt, 48 hours);
        require(lock.operationEpoch(p.operationId) == oldEpoch + 2, "requeue receives new epoch");
        vm.warp(p.eta);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.ChallengeUnavailable.selector);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
    }

    function testMissingTimelockExecutorGrantRejectsBeforeMutation() public {
        _executeGovernance(address(lock), abi.encodeCall(lock.revokeRole, (lock.EXECUTOR_ROLE(), address(registry))), keccak256("revoke-registry-executor"));
        Prepared memory p = _prepare(Consent.MODE_ROTATE_NORMAL, false);
        vm.warp(p.eta);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.UnauthorizedExecutor.selector);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
        (, bytes32 digest, uint64 generation, uint64 nonce,) = registry.principalState(oldRecord.principalId);
        require(digest == Principal.digest(oldRecord) && generation == 1 && nonce == 0, "no executor grant means no mutation");
    }

    function testChangedPolicyProfileRejectsPreviouslySignedConsent() public {
        Prepared memory p = _prepare(Consent.MODE_ROTATE_NORMAL, false);
        Types.Profile memory next = policy.consentProfile();
        bytes32 nextRoot = keccak256("synthetic-next-policy-root");
        next.policyRoot = nextRoot;
        next.policyVersion = 2;
        next.authorityEpoch = 2;
        Types.AuthoritySnapshot memory a = authority.currentSnapshot();
        a.policyRoot = nextRoot;
        a.policyVersion = 2;
        a.authorityEpoch = 2;
        a.authorityChangeSequence = 2;
        authority.set(a);
        _executeGovernance(address(policy), abi.encodeCall(policy.configure, (nextRoot, uint64(2), uint64(2), next)), keccak256("advance-synthetic-policy"));
        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.PolicyUnavailable.selector);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
    }

    function testBackdatedOverlongRecordWindowRejectsAndPreservesCurrentState() public {
        Principal.Record memory backdated = _record(NEW_KEY, 2);
        backdated.notBefore = uint64(block.timestamp - 50000);
        backdated.expiresAt = uint64(block.timestamp + 48 hours + 50000);
        Prepared memory p = _prepareWithRecord(Consent.MODE_ROTATE_NORMAL, false, backdated);
        vm.warp(p.eta);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.PolicyUnavailable.selector);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
        (, bytes32 digest, uint64 generation, uint64 nonce,) = registry.principalState(oldRecord.principalId);
        require(digest == Principal.digest(oldRecord) && generation == 1 && nonce == 0, "overlong signed window cannot mutate");
    }

    function testUnsupportedBoundedGraceProfileIsRejectedInsteadOfAssumingZeroGrace() public {
        Types.Profile memory next = policy.consentProfile();
        bytes32 nextRoot = keccak256("synthetic-bounded-grace-root");
        next.policyRoot = nextRoot;
        next.policyVersion = 2;
        next.authorityEpoch = 2;
        next.oldKeyGracePolicy = Types.GRACE_POLICY_BOUNDED;
        next.oldKeyGraceSeconds = 60;
        bytes memory callData = abi.encodeCall(policy.configure, (nextRoot, uint64(2), uint64(2), next));
        bytes32 salt = keccak256("bounded-grace-profile");
        lock.schedule(address(policy), 0, callData, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        vm.expectRevert(HeartbeatConsentPolicyV2.InvalidPolicyUpdate.selector);
        lock.execute(address(policy), 0, callData, bytes32(0), salt);
        require(policy.policyRoot() == ROOT && policy.policyVersion() == 1, "unsupported grace config must not replace policy");
        (, bytes32 digest, uint64 generation, uint64 nonce,) = registry.principalState(oldRecord.principalId);
        require(digest == Principal.digest(oldRecord) && generation == 1 && nonce == 0, "unsupported grace cannot mutate");
    }

    struct Prepared {
        bytes baseRaw;
        bytes proposedRaw;
        bytes witnessRaw;
        bytes oldSignature;
        bytes newSignature;
        bytes evidence;
        bytes32 operationId;
        uint64 eta;
    }

    struct PrincipalSnapshot {
        bytes canonicalRecord;
        bytes32 digest;
        uint64 generation;
        uint64 nonce;
        uint64 authoritySequence;
    }

    function _submit(uint8 mode, bool omitOld) private {
        Prepared memory p = _prepare(mode, omitOld);
        vm.warp(p.eta);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
        // A consumed operation cannot be replayed; state remains at one generation advance.
        vm.expectRevert();
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
    }

    function _prepare(uint8 mode, bool omitOld) private returns (Prepared memory p) {
        Principal.Record memory proposed = _record(NEW_KEY, 2);
        proposed.notBefore = uint64(block.timestamp + 48 hours);
        proposed.expiresAt = proposed.notBefore + 50000;
        return _prepareWithRecord(mode, omitOld, proposed);
    }

    function _prepareWithRecord(uint8 mode, bool omitOld, Principal.Record memory proposed)
        private returns (Prepared memory p)
    {
        p.proposedRaw = Principal.canonicalBytes(proposed);
        bytes32 authorityDigest = Types.authorityDigest(authority.currentSnapshot());
        Types.Profile memory currentProfile = policy.consentProfile();
        Types.AuthoritySnapshot memory currentAuthority = authority.currentSnapshot();
        Consent.BaseIntent memory b;
        b.mode = mode;
        b.sourceScheme = Types.EVM_SCHEME;
        b.authoritySourceDigest = authorityDigest;
        b.timelockAddress = address(lock);
        b.timelockCodeHash = address(lock).codehash;
        b.authorityConfigDigest = AUTH_CONFIG;
        b.authorityChangeSequence = currentAuthority.authorityChangeSequence;
        b.policyRoot = currentProfile.policyRoot;
        b.policyVersion = currentProfile.policyVersion;
        b.authorityEpoch = currentProfile.authorityEpoch;
        b.principalId = oldRecord.principalId;
        b.proposedRecordDigest = Principal.digest(proposed);
        b.expectedRecordDigest = Principal.digest(oldRecord);
        b.expectedGeneration = 1;
        b.proposedGeneration = 2;
        b.consentNonce = 0;
        b.timelockPredecessor = bytes32(0);
        b.timelockSalt = keccak256(abi.encode(mode, "synthetic-consent"));
        p.baseRaw = Consent.canonicalBaseBytes(b);
        bytes memory queuedCall = abi.encodeCall(registry.applyConsent, (p.baseRaw, p.proposedRaw));
        bytes32 operationId = lock.hashOperation(address(registry), 0, queuedCall, b.timelockPredecessor, b.timelockSalt);
        p.operationId = operationId;
        lock.schedule(address(registry), 0, queuedCall, b.timelockPredecessor, b.timelockSalt, 48 hours);
        p.eta = uint64(lock.getTimestamp(operationId));
        uint64 operationEpoch = lock.operationEpoch(operationId);
        p.evidence = bytes("synthetic-challenge-evidence");
        bytes32 commitment = sha256(abi.encodePacked("synthetic-challenge", operationId, bytes8(operationEpoch), bytes8(p.eta), Consent.baseDigest(b)));
        Consent.Witness memory w;
        w.baseIntentDigest = Consent.baseDigest(b);
        w.operationId = operationId;
        w.queuedEta = p.eta;
        w.postEtaChallengeCommitment = commitment;
        w.issuedAt = p.eta;
        w.expiresAt = p.eta + 900;
        w.mode = mode;
        w.requiredRoleMask = mode == Consent.MODE_ROTATE_NORMAL ? Consent.ROLE_MASK_ROTATE_NORMAL : Consent.ROLE_MASK_RECOVER_LOST_KEY;
        p.witnessRaw = Consent.canonicalWitnessBytes(w);
        Types.ChallengeFacts memory c;
        c.schema = Types.CHALLENGE_SCHEMA;
        c.networkContextDigest = NETWORK;
        c.operationId = operationId;
        c.operationEpoch = operationEpoch;
        c.queuedEta = p.eta;
        c.baseIntentDigest = Consent.baseDigest(b);
        c.challengeCommitment = commitment;
        c.issuedAt = p.eta;
        c.expiresAt = p.eta + 900;
        c.challengeProfileDigest = CHALLENGE_PROFILE;
        c.finalityProfileDigest = FINALITY_PROFILE;
        c.evidenceDigest = sha256(p.evidence);
        challenges.set(c);
        p.oldSignature = (omitOld || mode == Consent.MODE_RECOVER_LOST_KEY)
            ? bytes("") : _sign(OLD_KEY, _statement(p.witnessRaw, Consent.ROLE_OLD_KEY));
        p.newSignature = _sign(NEW_KEY, _statement(p.witnessRaw, Consent.ROLE_NEW_KEY));
    }

    function _installSyntheticPolicy() private {
        Types.AuthoritySnapshot memory a;
        a.sourceSchema = Types.AUTHORITY_SOURCE_SCHEMA;
        a.scheme = Types.EVM_SCHEME;
        a.registrySchema = Types.REGISTRY_SCHEMA;
        a.chainId = block.chainid;
        a.networkContextDigest = NETWORK;
        a.registry = address(registry);
        a.registryRuntimeCodeHash = address(registry).codehash;
        a.policy = address(policy);
        a.policyRuntimeCodeHash = address(policy).codehash;
        a.timelock = address(lock);
        a.timelockRuntimeCodeHash = address(lock).codehash;
        a.authorityConfigDigest = AUTH_CONFIG;
        a.authorityChangeSequence = 1;
        a.policyRoot = ROOT;
        a.policyVersion = 1;
        a.authorityEpoch = 1;
        authority.set(a);
        Types.Profile memory p;
        p.configured = true;
        p.schema = Types.PROFILE_SCHEMA;
        p.policyRoot = ROOT;
        p.policyVersion = 1;
        p.authorityEpoch = 1;
        p.maxConsentTtl = 1000;
        p.maxPrincipalLifetime = 100000;
        p.oldKeyGracePolicy = Types.GRACE_POLICY_ZERO;
        p.keyPolicy = Types.KEY_POLICY_ALLOW_SAME;
        p.relayerPolicy = Types.RELAYER_POLICY_PERMISSIONLESS;
        p.withdrawalPolicy = Types.WITHDRAWAL_POLICY_NO_PERSISTENT_CONSENT_FRAME;
        p.batchPolicy = Types.BATCH_POLICY_SINGLE_ONLY;
        p.requeuePolicy = Types.REQUEUE_POLICY_TIMELOCK_EPOCH;
        p.authoritySource = address(authority);
        p.authoritySourceRuntimeCodeHash = address(authority).codehash;
        p.challengeProvider = address(challenges);
        p.challengeProviderRuntimeCodeHash = address(challenges).codehash;
        p.authorityConfigDigest = AUTH_CONFIG;
        p.networkContextDigest = NETWORK;
        p.challengeProfileDigest = CHALLENGE_PROFILE;
        p.finalityProfileDigest = FINALITY_PROFILE;
        _executeGovernance(address(policy), abi.encodeCall(policy.configure, (ROOT, uint64(1), uint64(1), p)), keccak256("synthetic-policy-configuration"));
    }

    function _executeGovernance(address target, bytes memory callData, bytes32 salt) private {
        lock.schedule(target, 0, callData, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        lock.execute(target, 0, callData, bytes32(0), salt);
    }

    function _record(uint256 bodyScalar, uint64 generation) private returns (Principal.Record memory r) {
        Vm.Wallet memory body = vm.createWallet(bodyScalar);
        Vm.Wallet memory m2 = vm.createWallet(M2_KEY);
        bytes memory bodyKey = abi.encodePacked(bytes32(body.publicKeyX), bytes32(body.publicKeyY));
        bytes memory m2Key = abi.encodePacked(bytes32(m2.publicKeyX), bytes32(m2.publicKeyY));
        r.nodeIdCommitment = bytes32(uint256(3));
        r.hostDomain = bytes32(uint256(1));
        r.serviceDomain = bytes32(uint256(2));
        r.principalId = Principal.principalIdFor(r.hostDomain, r.serviceDomain, r.nodeIdCommitment);
        r.m2SignerDid = string(abi.encodePacked("did:key:", _hex(m2Key)));
        r.m2SignerPublicKey = m2Key;
        r.certificateFingerprint = bytes32(uint256(4));
        r.bodyPublicKey = bodyKey;
        r.audience = "gateway.testnet";
        r.method = "POST";
        r.path = "/heartbeat";
        Types.Profile memory currentProfile = policy.consentProfile();
        r.policyRoot = currentProfile.policyRoot;
        r.policyVersion = currentProfile.policyVersion;
        r.authorityEpoch = currentProfile.authorityEpoch;
        r.principalGeneration = generation;
        r.notBefore = uint64(block.timestamp);
        r.expiresAt = uint64(block.timestamp + 50000);
    }

    function _statement(bytes memory witnessRaw, uint8 role) private pure returns (bytes32) {
        (bool ok, Consent.Witness memory w) = Consent.tryDecodeWitness(witnessRaw);
        require(ok, "synthetic witness");
        return sha256(abi.encodePacked(SIG_DOMAIN, hex"00", bytes1(uint8(1)), bytes1(role), Consent.witnessDigest(w)));
    }

    function _sign(uint256 scalar, bytes32 digest) private returns (bytes memory) {
        (, bytes32 r, bytes32 s) = vm.sign(scalar, digest);
        uint256 lowS = uint256(s) > N / 2 ? N - uint256(s) : uint256(s);
        return abi.encodePacked(r, bytes32(lowS));
    }

    function _hex(bytes memory raw) private pure returns (bytes memory out) {
        bytes memory alphabet = bytes("0123456789abcdef");
        out = new bytes(raw.length * 2);
        for (uint256 i; i < raw.length; ++i) {
            out[i * 2] = alphabet[uint8(raw[i]) >> 4];
            out[i * 2 + 1] = alphabet[uint8(raw[i]) & 15];
        }
    }

    function testRouterPureCodecHelpersMatchCanonicalLibraryDecoding() public {
        Prepared memory prepared = _prepare(Consent.MODE_ROTATE_NORMAL, false);
        _assertConsentCodecParity(prepared.baseRaw, prepared.witnessRaw);
        _assertPrincipalCodecParity(prepared.proposedRaw);
    }

    function testRouterPureCodecHelpersRejectMalformedAndSplitBytes() public {
        Prepared memory prepared = _prepare(Consent.MODE_ROTATE_NORMAL, false);
        bytes memory malformedBase = bytes.concat(prepared.baseRaw, hex"00");
        (bool malformedConsentOk,,) = verifier.decodeConsent(malformedBase, prepared.witnessRaw);
        (bool malformedBaseOk,) = Consent.tryDecodeBase(malformedBase);
        require(!malformedConsentOk && !malformedBaseOk, "trailing base byte rejected");
        bytes memory malformedWitness = bytes.concat(prepared.witnessRaw, hex"00");
        (bool malformedWitnessConsentOk,,) = verifier.decodeConsent(prepared.baseRaw, malformedWitness);
        (bool malformedWitnessOk,) = Consent.tryDecodeWitness(malformedWitness);
        require(!malformedWitnessConsentOk && !malformedWitnessOk, "trailing witness byte rejected");
        _assertMalformedPrincipal(prepared.proposedRaw);
        _assertSplitWitnessRejected(prepared.baseRaw, prepared.witnessRaw);
        _assertOversizedPrincipalRejected();
    }

    function testCallbackChallengeMismatchRollsBackAndSameProofRetries() public {
        Prepared memory p = _prepare(Consent.MODE_ROTATE_NORMAL, false);
        challenges.setCallbackEpochMismatch(address(lock), true);
        vm.warp(p.eta);

        PrincipalSnapshot memory beforeState = _snapshot(oldRecord.principalId);
        uint64 operationEpoch = lock.operationEpoch(p.operationId);
        require(lock.isOperationReady(p.operationId) && !lock.isOperationDone(p.operationId), "queued operation ready before callback");
        require(lock.getTimestamp(p.operationId) == p.eta, "queued ETA retained before callback");

        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.ChallengeUnavailable.selector);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);

        PrincipalSnapshot memory afterFailedState = _snapshot(oldRecord.principalId);
        require(keccak256(afterFailedState.canonicalRecord) == keccak256(beforeState.canonicalRecord) &&
            afterFailedState.digest == beforeState.digest && afterFailedState.generation == beforeState.generation &&
            afterFailedState.nonce == beforeState.nonce && afterFailedState.authoritySequence == beforeState.authoritySequence,
            "late callback failure rolls back all principal fields");
        require(lock.isOperationReady(p.operationId) && !lock.isOperationDone(p.operationId) &&
            lock.getTimestamp(p.operationId) == p.eta && lock.operationEpoch(p.operationId) == operationEpoch,
            "late callback failure leaves the scheduled operation ready");

        challenges.setCallbackEpochMismatch(address(lock), false);
        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
        PrincipalSnapshot memory afterRetryState = _snapshot(oldRecord.principalId);
        require(afterRetryState.digest == _proposedDigest(p.proposedRaw) && afterRetryState.generation == 2 &&
            afterRetryState.nonce == 1 && afterRetryState.authoritySequence == beforeState.authoritySequence,
            "same proof succeeds exactly once after repair");
        require(lock.isOperationDone(p.operationId) && !lock.isOperationReady(p.operationId),
            "successful retry consumes queued operation");
    }

    function testStaticChallengeCallbackCannotReenterRelay() public {
        Prepared memory p = _prepare(Consent.MODE_ROTATE_NORMAL, false);
        bytes memory nestedRelay = abi.encodeCall(registry.relayConsent,
            (p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence));
        challenges.setStaticReentryProbe(address(registry), nestedRelay);
        vm.warp(p.eta);

        registry.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
        PrincipalSnapshot memory state = _snapshot(oldRecord.principalId);
        require(state.digest == _proposedDigest(p.proposedRaw) && state.generation == 2 && state.nonce == 1 && state.authoritySequence == 1,
            "static nested relay attempts are rejected and outer relay commits once");
    }

    function _snapshot(bytes32 principalId) private view returns (PrincipalSnapshot memory state) {
        (state.canonicalRecord, state.digest, state.generation, state.nonce, state.authoritySequence) =
            registry.principalState(principalId);
    }

    function _proposedDigest(bytes memory raw) private pure returns (bytes32) {
        (bool ok, Principal.Record memory proposed) = Principal.tryDecode(raw);
        require(ok, "synthetic proposed record decodes");
        return Principal.digest(proposed);
    }

    function _assertConsentCodecParity(bytes memory baseRaw, bytes memory witnessRaw) private view {
        (bool helperConsentOk, Consent.BaseIntent memory helperBase, Consent.Witness memory helperWitness) =
            verifier.decodeConsent(baseRaw, witnessRaw);
        (bool libraryBaseOk, Consent.BaseIntent memory libraryBase) = Consent.tryDecodeBase(baseRaw);
        (bool libraryWitnessOk, Consent.Witness memory libraryWitness) = Consent.tryDecodeWitness(witnessRaw);
        require(helperConsentOk && libraryBaseOk && libraryWitnessOk, "valid consent bytes decode");
        require(keccak256(abi.encode(helperBase)) == keccak256(abi.encode(libraryBase)), "base decode parity");
        require(keccak256(abi.encode(helperWitness)) == keccak256(abi.encode(libraryWitness)), "witness decode parity");
    }

    function _assertPrincipalCodecParity(bytes memory raw) private view {
        (bool helperOk, HeartbeatConsentVerificationRouterV2.PrincipalView memory viewRecord, bytes32 digest) =
            verifier.decodePrincipal(raw);
        (bool libraryOk, Principal.Record memory fullRecord) = Principal.tryDecode(raw);
        require(helperOk && libraryOk, "valid principal bytes decode");
        require(viewRecord.principalId == fullRecord.principalId, "principal id parity");
        require(keccak256(viewRecord.bodyPublicKey) == keccak256(fullRecord.bodyPublicKey), "body key parity");
        require(viewRecord.hostDomain == fullRecord.hostDomain && viewRecord.serviceDomain == fullRecord.serviceDomain, "domain parity");
        require(viewRecord.policyRoot == fullRecord.policyRoot && viewRecord.policyVersion == fullRecord.policyVersion &&
            viewRecord.authorityEpoch == fullRecord.authorityEpoch, "policy parity");
        require(viewRecord.principalGeneration == fullRecord.principalGeneration &&
            viewRecord.notBefore == fullRecord.notBefore && viewRecord.expiresAt == fullRecord.expiresAt, "lifetime parity");
        require(digest == Principal.digest(fullRecord), "principal digest parity");
    }

    function _assertMalformedPrincipal(bytes memory raw) private view {
        bytes memory malformed = bytes.concat(raw, hex"00");
        (bool helperOk,, bytes32 digest) = verifier.decodePrincipal(malformed);
        (bool libraryOk,) = Principal.tryDecode(malformed);
        require(!helperOk && !libraryOk && digest == bytes32(0), "trailing principal byte rejected");
    }

    function _assertSplitWitnessRejected(bytes memory baseRaw, bytes memory witnessRaw) private view {
        (bool witnessOk, Consent.Witness memory splitWitness) = Consent.tryDecodeWitness(witnessRaw);
        require(witnessOk, "fixture witness decodes");
        splitWitness.baseIntentDigest = bytes32(uint256(splitWitness.baseIntentDigest) ^ 1);
        bytes memory splitRaw = Consent.canonicalWitnessBytes(splitWitness);
        (bool consentOk,,) = verifier.decodeConsent(baseRaw, splitRaw);
        require(!consentOk, "split base and witness rejected");
    }

    function _assertOversizedPrincipalRejected() private view {
        bytes memory oversized = new bytes(1025);
        (bool helperOk,, bytes32 digest) = verifier.decodePrincipal(oversized);
        (bool libraryOk,) = Principal.tryDecode(oversized);
        require(!helperOk && !libraryOk && digest == bytes32(0), "oversized principal rejected");
    }
}
