// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {OperationAwareVAMSTimelockControllerV3} from "../governance/OperationAwareVAMSTimelockControllerV3.sol";
import {HeartbeatConsentV2 as Consent} from "./HeartbeatConsentV2.sol";
import {HeartbeatPrincipalV1 as Principal} from "./HeartbeatPrincipalV1.sol";
import {HeartbeatConsentVerificationRouterV2} from "./HeartbeatConsentVerificationRouterV2.sol";
import {HeartbeatConsentPolicyV3} from "./HeartbeatConsentPolicyV3.sol";
import {HeartbeatAuthoritySourceV3} from "./HeartbeatAuthoritySourceV3.sol";
import {HeartbeatAuthorityTypesV3 as Types} from "./HeartbeatAuthorityTypesV3.sol";
import {
    HeartbeatConsentProfileV2 as ChallengeTypes,
    IHeartbeatChallengeProviderV2
} from "./HeartbeatConsentProfileV2.sol";

/// @notice Inactive V3 consumer prototype using unchanged V2 consent and V1 principal bytes.
/// @dev Constructor pins class identities and dependency instances. This is not an activation
///      manifest: custody, challenge, enrollment and deployment trust remain unqualified.
contract HeartbeatAtomicConsentRegistryV3 {
    uint256 public constant RECOVERY_DELAY = 48 hours;
    uint256 private constant MAX_RAW = 1024;
    bytes32 private constant TIMELOCK_V3_CLASS = 0xd1d9aa58a6416881356db67b5cdc4a3317f7e46f1666a864a7cacc86985a88b6;
    bytes32 private constant POLICY_V3_CLASS = 0x2527d74539e8973eb3e9642ff337181b0e077bdc7800943c6054e5392f70c31d;
    bytes32 private constant SOURCE_V3_CLASS = 0x4612a5ae010aea63d7aaa81b91461e82713c1c87310c82cca199d1c0dfdeaebd;
    bytes32 private constant ROUTER_V2_CLASS = 0x32525d82e5aec455c7ec5000d2fb003f75570e46d757fb78b9e01378cf81369f;
    bytes32 private constant CONSUMER_DOMAIN = bytes32("VAMS:CONSUMER:AUTHORITY:V3");
    uint8 private constant MODE_ROTATE_NORMAL = Consent.MODE_ROTATE_NORMAL;
    uint8 private constant MODE_RECOVER_LOST_KEY = Consent.MODE_RECOVER_LOST_KEY;
    uint8 private constant KEY_POLICY_REQUIRE_DISTINCT = 2;
    uint8 private constant RELAYER_POLICY_ADDRESS = 2;
    uint8 private constant GRACE_POLICY_ZERO = 1;

    struct Entry {
        bytes record;
        bytes32 digest;
        uint64 generation;
        uint64 nonce;
        uint64 timelockSequence;
        uint64 custodySequence;
        bytes32 custodyDigest;
    }

    struct Frame {
        bool active;
        bool consumed;
        bytes32 operationId;
        uint64 operationEpoch;
        bytes32 callHash;
        bytes32 authorityDigest;
        uint64 timelockSequence;
        bytes32 profileDigest;
        bytes32 baseRawHash;
        bytes32 witnessRawHash;
        bytes32 oldSigHash;
        bytes32 newSigHash;
        bytes32 challengeHash;
        bytes baseRaw;
        bytes witnessRaw;
        bytes oldSignature;
        bytes newSignature;
        bytes challengeEvidence;
    }

    struct ViewPrincipal {
        bytes32 principalId;
        bytes bodyPublicKey;
        bytes32 hostDomain;
        bytes32 serviceDomain;
        bytes32 policyRoot;
        uint64 policyVersion;
        uint64 authorityEpoch;
        uint64 generation;
        uint64 notBefore;
        uint64 expiresAt;
    }

    struct Request {
        bytes baseRaw;
        bytes proposedRaw;
        bytes witnessRaw;
        bytes oldSig;
        bytes newSig;
        bytes challengeEvidence;
    }

    struct Context {
        Consent.BaseIntent base;
        Consent.Witness witness;
        ViewPrincipal proposed;
        bytes32 proposedDigest;
        Types.Profile profile;
        Types.ProducerState authority;
        bytes oldRecord;
        bytes callData;
        bytes32 operationId;
        uint64 operationEpoch;
        uint64 eta;
        bytes32 consumerDigest;
    }

    error InvalidConfiguration();
    error InvalidConsent();
    error PolicyUnavailable();
    error AuthorityUnavailable();
    error ChallengeUnavailable();
    error StaleState();
    error WrongOperationContext();
    error UnauthorizedExecutor();
    error ReentrantCall();

    // Constructor-set storage keeps this runtime independent of constructor inputs; no setter is exposed.
    address public timelock;
    address public policy;
    address public verifier;
    address public authoritySource;
    address public custodyAdapter;
    address public challengeProvider;
    bytes32 public custodyAdapterRuntimeCodeHash;
    bytes32 public challengeProviderRuntimeCodeHash;
    bytes32 public networkContextDigest;
    bytes32 public hostDomain;
    bytes32 public serviceDomain;
    uint256 public deploymentChainId;
    mapping(bytes32 => Entry) internal _entries;
    Frame private _frame;
    bool private _entered;

    event PrincipalConsentApplied(bytes32 indexed principalId, bytes32 digest, uint64 generation, uint64 nonce);

    constructor(
        address timelock_,
        address policy_,
        address verifier_,
        address source_,
        address custody_,
        bytes32 custodyHash_,
        address challenge_,
        bytes32 challengeHash_,
        bytes32 networkDigest_,
        bytes32 hostDomain_,
        bytes32 serviceDomain_
    ) {
        if (
            block.chainid == 0 || timelock_ == address(0) || policy_ == address(0) || verifier_ == address(0)
                || source_ == address(0) || custody_ == address(0) || challenge_ == address(0)
                || networkDigest_ == bytes32(0) || hostDomain_ == bytes32(0) || serviceDomain_ == bytes32(0)
                || custodyHash_ == bytes32(0) || challengeHash_ == bytes32(0)
        ) revert InvalidConfiguration();
        if (
            timelock_.codehash != TIMELOCK_V3_CLASS || policy_.codehash != POLICY_V3_CLASS
                || verifier_.codehash != ROUTER_V2_CLASS || source_.codehash != SOURCE_V3_CLASS
                || custody_.codehash != custodyHash_ || challenge_.codehash != challengeHash_
        ) revert InvalidConfiguration();
        OperationAwareVAMSTimelockControllerV3 lock = OperationAwareVAMSTimelockControllerV3(payable(timelock_));
        HeartbeatConsentPolicyV3 policyContract = HeartbeatConsentPolicyV3(policy_);
        HeartbeatAuthoritySourceV3 source = HeartbeatAuthoritySourceV3(source_);
        if (
            lock.getMinDelay() < RECOVERY_DELAY || policyContract.governance() != timelock_
                || policyContract.authoritySource() != source_ || source.timelock() != timelock_
                || source.policy() != policy_ || source.custodyAdapter() != custody_
                || source.expectedCustodyAdapterRuntimeCodeHash() != custodyHash_
        ) revert InvalidConfiguration();
        Types.ProducerState memory s = source.currentState();
        Types.Profile memory configuredProfile = policyContract.consentProfile();
        if (
            s.chainId != block.chainid || s.networkContextDigest != networkDigest_ || s.source != source_
                || s.custodyAdapter != custody_ || s.custodyAdapterRuntimeCodeHash != custodyHash_
                || s.policy != policy_ || s.timelock != timelock_ || !configuredProfile.configured
                || configuredProfile.authoritySource != source_
                || configuredProfile.authoritySourceRuntimeCodeHash != SOURCE_V3_CLASS
                || configuredProfile.custodyAdapter != custody_
                || configuredProfile.custodyAdapterRuntimeCodeHash != custodyHash_
                || configuredProfile.challengeProvider != challenge_
                || configuredProfile.challengeProviderRuntimeCodeHash != challengeHash_
                || configuredProfile.authorityConfigDigest != s.authorityConfigDigest
                || Types.profileProjectionDigest(configuredProfile) != s.policyProjectionDigest
        ) revert InvalidConfiguration();
        timelock = timelock_;
        policy = policy_;
        verifier = verifier_;
        authoritySource = source_;
        custodyAdapter = custody_;
        custodyAdapterRuntimeCodeHash = custodyHash_;
        challengeProvider = challenge_;
        challengeProviderRuntimeCodeHash = challengeHash_;
        networkContextDigest = networkDigest_;
        hostDomain = hostDomain_;
        serviceDomain = serviceDomain_;
        deploymentChainId = block.chainid;
    }

    function relayConsent(
        bytes calldata baseRaw,
        bytes calldata proposedRaw,
        bytes calldata witnessRaw,
        bytes calldata oldSignature,
        bytes calldata newSignature,
        bytes calldata challengeEvidence
    ) external {
        if (_entered || _frame.active) revert ReentrantCall();
        _entered = true;
        if (
            baseRaw.length > MAX_RAW || proposedRaw.length > MAX_RAW || witnessRaw.length > MAX_RAW
                || challengeEvidence.length > MAX_RAW || oldSignature.length > 64 || newSignature.length > 64
        ) revert InvalidConsent();
        Request memory r = Request(baseRaw, proposedRaw, witnessRaw, oldSignature, newSignature, challengeEvidence);
        Context memory c = _prepare(r);
        _installFrame(r, c);
        OperationAwareVAMSTimelockControllerV3(payable(timelock))
            .execute(address(this), 0, c.callData, c.base.timelockPredecessor, c.base.timelockSalt);
        if (!_frame.consumed) revert WrongOperationContext();
        delete _frame;
        _entered = false;
    }

    function _prepare(Request memory r) private view returns (Context memory c) {
        (bool ok, Consent.BaseIntent memory b, Consent.Witness memory w) =
            HeartbeatConsentVerificationRouterV2(verifier).decodeConsent(r.baseRaw, r.witnessRaw);
        (bool principalOk, HeartbeatConsentVerificationRouterV2.PrincipalView memory p, bytes32 digest) =
            HeartbeatConsentVerificationRouterV2(verifier).decodePrincipal(r.proposedRaw);
        if (!ok || !principalOk || (b.mode != MODE_ROTATE_NORMAL && b.mode != MODE_RECOVER_LOST_KEY)) {
            revert InvalidConsent();
        }
        if (
            (b.mode == MODE_ROTATE_NORMAL && (r.oldSig.length != 64 || r.newSig.length != 64))
                || (b.mode == MODE_RECOVER_LOST_KEY && (r.oldSig.length != 0 || r.newSig.length != 64))
        ) revert InvalidConsent();
        ViewPrincipal memory proposed = _principal(p);
        if (
            b.timelockAddress != timelock || b.timelockCodeHash != timelock.codehash
                || b.principalId != proposed.principalId || proposed.hostDomain != hostDomain
                || proposed.serviceDomain != serviceDomain || digest != b.proposedRecordDigest
                || proposed.generation != b.proposedGeneration
        ) revert InvalidConsent();
        Entry storage e = _entries[b.principalId];
        if (
            e.generation == 0 || e.digest != b.expectedRecordDigest || e.generation != b.expectedGeneration
                || e.nonce != b.consentNonce || e.generation == type(uint64).max
                || b.proposedGeneration != e.generation + 1
        ) revert StaleState();
        c.base = b;
        c.witness = w;
        c.proposed = proposed;
        c.proposedDigest = digest;
        c.oldRecord = e.record;
        c.profile = _loadProfile();
        _checkProfile(c.profile, b, c.oldRecord, proposed);
        if (c.profile.relayerPolicy == RELAYER_POLICY_ADDRESS && msg.sender != c.profile.allowedRelayer) {
            revert InvalidConsent();
        }
        if (
            c.profile.keyPolicy == KEY_POLICY_REQUIRE_DISTINCT
                && keccak256(_bodyKey(c.oldRecord)) == keccak256(proposed.bodyPublicKey)
        ) revert InvalidConsent();
        c.callData = abi.encodeCall(this.applyConsent, (r.baseRaw, r.proposedRaw));
        OperationAwareVAMSTimelockControllerV3 lock = OperationAwareVAMSTimelockControllerV3(payable(timelock));
        c.operationId = lock.hashOperation(address(this), 0, c.callData, b.timelockPredecessor, b.timelockSalt);
        uint256 eta = lock.getTimestamp(c.operationId);
        if (
            eta <= 1 || eta > type(uint64).max || uint64(eta) != w.queuedEta || c.operationId != w.operationId
                || !lock.isOperationReady(c.operationId) || w.issuedAt < w.queuedEta || w.issuedAt > block.timestamp
                || w.expiresAt <= block.timestamp || w.expiresAt - w.issuedAt > c.profile.maxConsentTtl
        ) revert InvalidConsent();
        if (b.mode == MODE_RECOVER_LOST_KEY && lock.scheduledDelay(c.operationId) < RECOVERY_DELAY) {
            revert InvalidConsent();
        }
        if (!lock.hasRole(lock.EXECUTOR_ROLE(), address(this)) && !lock.hasRole(lock.EXECUTOR_ROLE(), address(0))) {
            revert UnauthorizedExecutor();
        }
        c.operationEpoch = lock.operationEpoch(c.operationId);
        c.eta = uint64(eta);
        c.authority = _readAuthority(c.profile);
        c.consumerDigest = _consumerDigest(c.authority.authorityConfigDigest);
        if (
            c.consumerDigest != b.authoritySourceDigest || c.authority.authorityConfigDigest != b.authorityConfigDigest
                || c.authority.authorityChangeSequence != b.authorityChangeSequence
                || c.authority.authorityChangeSequence < e.timelockSequence
                || c.authority.custodyChangeSequence < e.custodySequence
                || (c.authority.custodyChangeSequence == e.custodySequence
                    && e.custodyDigest != bytes32(0)
                    && c.authority.custodyConfigurationDigest != e.custodyDigest)
        ) revert AuthorityUnavailable();
        _checkPreparedEvidence(r, c);
    }

    function _checkPreparedEvidence(Request memory r, Context memory c) private view {
        ChallengeTypes.ChallengeFacts memory facts = _challenge(r.challengeEvidence);
        _checkChallenge(
            c.profile, facts, c.witness, c.base, r.challengeEvidence, c.operationId, c.operationEpoch, c.eta
        );
        if (!_verify(c.base.mode, r.baseRaw, r.witnessRaw, c.oldRecord, r.proposedRaw, r.oldSig, r.newSig)) {
            revert InvalidConsent();
        }
    }

    function applyConsent(bytes calldata baseRaw, bytes calldata proposedRaw) external {
        Frame storage f = _frame;
        if (!f.active || f.consumed || msg.sender != timelock) revert WrongOperationContext();
        bytes32 op = _checkActiveOperation(f);
        Context memory c = _decodeCallback(baseRaw, proposedRaw, f);
        Entry storage e = _entries[c.base.principalId];
        if (
            e.digest != c.base.expectedRecordDigest || e.generation != c.base.expectedGeneration
                || e.nonce != c.base.consentNonce || e.generation == type(uint64).max
                || c.proposed.generation != e.generation + 1
        ) revert StaleState();
        c.profile = _loadProfile();
        _checkProfile(c.profile, c.base, e.record, c.proposed);
        if (keccak256(abi.encode(c.profile)) != f.profileDigest) revert PolicyUnavailable();
        c.authority = _readAuthority(c.profile);
        c.consumerDigest = _consumerDigest(c.authority.authorityConfigDigest);
        _checkCallbackAuthority(c, f, e);
        _checkCallbackEvidence(c, f, e.record, proposedRaw, op);
        if (e.nonce == type(uint64).max) revert StaleState();
        e.record = proposedRaw;
        e.digest = c.proposedDigest;
        e.generation = c.proposed.generation;
        ++e.nonce;
        e.timelockSequence = c.authority.authorityChangeSequence;
        e.custodySequence = c.authority.custodyChangeSequence;
        e.custodyDigest = c.authority.custodyConfigurationDigest;
        f.consumed = true;
        emit PrincipalConsentApplied(c.base.principalId, c.proposedDigest, e.generation, e.nonce);
    }

    function _checkActiveOperation(Frame storage f) private view returns (bytes32 op) {
        OperationAwareVAMSTimelockControllerV3 lock = OperationAwareVAMSTimelockControllerV3(payable(timelock));
        bool active;
        bool batch;
        (active, op, batch) = lock.activeOperationContext();
        if (
            !active || batch || op != f.operationId || keccak256(msg.data) != f.callHash
                || lock.operationEpoch(op) != f.operationEpoch
        ) revert WrongOperationContext();
    }

    function _decodeCallback(bytes calldata baseRaw, bytes calldata proposedRaw, Frame storage f)
        private
        view
        returns (Context memory c)
    {
        (bool ok, Consent.BaseIntent memory b, Consent.Witness memory w) =
            HeartbeatConsentVerificationRouterV2(verifier).decodeConsent(baseRaw, f.witnessRaw);
        (bool pOk, HeartbeatConsentVerificationRouterV2.PrincipalView memory p, bytes32 digest) =
            HeartbeatConsentVerificationRouterV2(verifier).decodePrincipal(proposedRaw);
        if (
            !ok || !pOk || b.principalId != p.principalId || digest != b.proposedRecordDigest
                || keccak256(baseRaw) != f.baseRawHash || keccak256(f.witnessRaw) != f.witnessRawHash
                || keccak256(f.oldSignature) != f.oldSigHash || keccak256(f.newSignature) != f.newSigHash
                || keccak256(f.challengeEvidence) != f.challengeHash
        ) revert InvalidConsent();
        c.base = b;
        c.witness = w;
        c.proposed = _principal(p);
        c.proposedDigest = digest;
    }

    function _checkCallbackAuthority(Context memory c, Frame storage f, Entry storage e) private view {
        if (
            c.consumerDigest != f.authorityDigest || c.consumerDigest != c.base.authoritySourceDigest
                || c.authority.authorityConfigDigest != c.base.authorityConfigDigest
                || c.authority.authorityChangeSequence != f.timelockSequence
                || c.authority.authorityChangeSequence != c.base.authorityChangeSequence
                || c.authority.authorityChangeSequence < e.timelockSequence
                || c.authority.custodyChangeSequence < e.custodySequence
                || (c.authority.custodyChangeSequence == e.custodySequence
                    && e.custodyDigest != bytes32(0)
                    && c.authority.custodyConfigurationDigest != e.custodyDigest)
        ) revert AuthorityUnavailable();
    }

    function _checkCallbackEvidence(
        Context memory c,
        Frame storage f,
        bytes memory oldRecord,
        bytes calldata proposedRaw,
        bytes32 op
    ) private view {
        ChallengeTypes.ChallengeFacts memory facts = _challenge(f.challengeEvidence);
        _checkChallenge(
            c.profile, facts, c.witness, c.base, f.challengeEvidence, op, f.operationEpoch, c.witness.queuedEta
        );
        if (!_verify(c.base.mode, f.baseRaw, f.witnessRaw, oldRecord, proposedRaw, f.oldSignature, f.newSignature)) {
            revert InvalidConsent();
        }
    }

    function _installFrame(Request memory r, Context memory c) private {
        Frame storage f = _frame;
        f.active = true;
        f.operationId = c.operationId;
        f.operationEpoch = c.operationEpoch;
        f.callHash = keccak256(c.callData);
        f.authorityDigest = c.consumerDigest;
        f.timelockSequence = c.authority.authorityChangeSequence;
        f.profileDigest = keccak256(abi.encode(c.profile));
        f.baseRawHash = keccak256(r.baseRaw);
        f.witnessRawHash = keccak256(r.witnessRaw);
        f.oldSigHash = keccak256(r.oldSig);
        f.newSigHash = keccak256(r.newSig);
        f.challengeHash = keccak256(r.challengeEvidence);
        f.baseRaw = r.baseRaw;
        f.witnessRaw = r.witnessRaw;
        f.oldSignature = r.oldSig;
        f.newSignature = r.newSig;
        f.challengeEvidence = r.challengeEvidence;
    }

    function _principal(HeartbeatConsentVerificationRouterV2.PrincipalView memory p)
        private
        pure
        returns (ViewPrincipal memory v)
    {
        return ViewPrincipal(
            p.principalId,
            p.bodyPublicKey,
            p.hostDomain,
            p.serviceDomain,
            p.policyRoot,
            p.policyVersion,
            p.authorityEpoch,
            p.principalGeneration,
            p.notBefore,
            p.expiresAt
        );
    }

    function _loadProfile() internal view returns (Types.Profile memory p) {
        if (
            block.chainid != deploymentChainId || timelock.codehash != TIMELOCK_V3_CLASS
                || policy.codehash != POLICY_V3_CLASS || verifier.codehash != ROUTER_V2_CLASS
                || authoritySource.codehash != SOURCE_V3_CLASS
                || custodyAdapter.codehash != custodyAdapterRuntimeCodeHash
                || challengeProvider.codehash != challengeProviderRuntimeCodeHash
        ) revert PolicyUnavailable();
        try HeartbeatConsentPolicyV3(policy).consentProfile() returns (Types.Profile memory x) {
            p = x;
        } catch {
            revert PolicyUnavailable();
        }
        if (
            !p.configured || p.schema != 3 || p.policyRoot == bytes32(0) || p.policyVersion == 0
                || p.authorityEpoch == 0 || p.maxConsentTtl == 0 || p.maxPrincipalLifetime == 0
                || p.authoritySource != authoritySource || p.authoritySourceRuntimeCodeHash != SOURCE_V3_CLASS
                || p.networkContextDigest != networkContextDigest || p.custodyAdapter != custodyAdapter
                || p.custodyAdapterRuntimeCodeHash != custodyAdapterRuntimeCodeHash
                || p.challengeProvider != challengeProvider
                || p.challengeProviderRuntimeCodeHash != challengeProviderRuntimeCodeHash
                || p.oldKeyGracePolicy != GRACE_POLICY_ZERO || p.oldKeyGraceSeconds != 0
                || (p.keyPolicy != 1 && p.keyPolicy != KEY_POLICY_REQUIRE_DISTINCT)
                || (p.relayerPolicy != 1 && p.relayerPolicy != RELAYER_POLICY_ADDRESS)
                || (p.relayerPolicy == RELAYER_POLICY_ADDRESS && p.allowedRelayer == address(0))
                || (p.relayerPolicy == 1 && p.allowedRelayer != address(0)) || p.withdrawalPolicy != 1
                || p.batchPolicy != 1 || p.requeuePolicy != 1 || p.challengeProfileDigest == bytes32(0)
                || p.finalityProfileDigest == bytes32(0)
        ) revert PolicyUnavailable();
    }

    function _readAuthority(Types.Profile memory p) internal view returns (Types.ProducerState memory s) {
        try HeartbeatAuthoritySourceV3(authoritySource).currentState() returns (Types.ProducerState memory x) {
            s = x;
        } catch {
            revert AuthorityUnavailable();
        }
        if (
            s.sourceSchema != 3 || s.scheme != Types.EVM_SCHEME || s.chainId != deploymentChainId
                || s.source != authoritySource || s.sourceRuntimeCodeHash != SOURCE_V3_CLASS || s.timelock != timelock
                || s.timelockRuntimeCodeHash != TIMELOCK_V3_CLASS || s.policy != policy
                || s.policyRuntimeCodeHash != POLICY_V3_CLASS || s.custodyAdapter != custodyAdapter
                || s.custodyAdapterRuntimeCodeHash != custodyAdapterRuntimeCodeHash
                || s.networkContextDigest != networkContextDigest || s.policyRoot != p.policyRoot
                || s.policyVersion != p.policyVersion || s.authorityEpoch != p.authorityEpoch
                || s.policyProjectionDigest != Types.profileProjectionDigest(p)
                || p.authorityConfigDigest != s.authorityConfigDigest || s.authorityConfigDigest == bytes32(0)
                || s.authorityConfigDigest != Types.authorityConfigDigest(s)
                || HeartbeatConsentPolicyV3(policy).expectedAuthoritySourceRuntimeCodeHash() != SOURCE_V3_CLASS
                || HeartbeatConsentPolicyV3(policy).authoritySource() != authoritySource
        ) revert AuthorityUnavailable();
        OperationAwareVAMSTimelockControllerV3 lock = OperationAwareVAMSTimelockControllerV3(payable(timelock));
        if (
            s.authorityChangeSequence != lock.authorityChangeSequence()
                || s.authorityConfigCommitment != lock.authorityConfigCommitment() || s.minDelay != lock.getMinDelay()
                || s.minDelay < RECOVERY_DELAY
        ) revert AuthorityUnavailable();
    }

    function _consumerDigest(bytes32 sourceDigest) internal view returns (bytes32) {
        return sha256(abi.encode(CONSUMER_DOMAIN, block.chainid, address(this), address(this).codehash, sourceDigest));
    }

    function _challenge(bytes memory evidence) private view returns (ChallengeTypes.ChallengeFacts memory c) {
        if (challengeProvider.codehash != challengeProviderRuntimeCodeHash) revert ChallengeUnavailable();
        try IHeartbeatChallengeProviderV2(challengeProvider).resolveChallenge(evidence) returns (
            ChallengeTypes.ChallengeFacts memory x
        ) {
            c = x;
        } catch {
            revert ChallengeUnavailable();
        }
        if (c.schema != 2) revert ChallengeUnavailable();
    }

    function _checkChallenge(
        Types.Profile memory p,
        ChallengeTypes.ChallengeFacts memory c,
        Consent.Witness memory w,
        Consent.BaseIntent memory b,
        bytes memory evidence,
        bytes32 op,
        uint64 epoch,
        uint64 eta
    ) private view {
        OperationAwareVAMSTimelockControllerV3 lock = OperationAwareVAMSTimelockControllerV3(payable(timelock));
        if (
            c.operationId != op || c.operationEpoch != epoch || c.queuedEta != eta
                || c.baseIntentDigest != w.baseIntentDigest || c.challengeCommitment != w.postEtaChallengeCommitment
                || c.issuedAt != w.issuedAt || c.expiresAt != w.expiresAt || c.issuedAt < eta
                || c.issuedAt > block.timestamp || c.expiresAt <= block.timestamp
                || c.expiresAt - c.issuedAt > p.maxConsentTtl || c.revoked
                || c.networkContextDigest != p.networkContextDigest || c.evidenceDigest != sha256(evidence)
                || c.challengeProfileDigest != p.challengeProfileDigest
                || c.finalityProfileDigest != p.finalityProfileDigest || lock.getTimestamp(op) != eta
                || !lock.isOperationReady(op) || lock.operationEpoch(op) != epoch
                || (b.mode == MODE_RECOVER_LOST_KEY && lock.scheduledDelay(op) < RECOVERY_DELAY)
        ) revert ChallengeUnavailable();
    }

    function _checkProfile(
        Types.Profile memory p,
        Consent.BaseIntent memory b,
        bytes memory oldRaw,
        ViewPrincipal memory proposed
    ) private view {
        if (
            !p.configured || p.policyRoot != b.policyRoot || p.policyVersion != b.policyVersion
                || p.authorityEpoch != b.authorityEpoch || proposed.policyRoot != p.policyRoot
                || proposed.policyVersion != p.policyVersion || proposed.authorityEpoch != p.authorityEpoch
                || proposed.notBefore > block.timestamp || proposed.expiresAt <= block.timestamp
                || proposed.expiresAt - proposed.notBefore > p.maxPrincipalLifetime
        ) revert PolicyUnavailable();
        if (
            p.keyPolicy == KEY_POLICY_REQUIRE_DISTINCT
                && keccak256(_bodyKey(oldRaw)) == keccak256(proposed.bodyPublicKey)
        ) {
            revert InvalidConsent();
        }
    }

    function _verify(
        uint8 mode,
        bytes memory b,
        bytes memory w,
        bytes memory oldRaw,
        bytes memory proposed,
        bytes memory oldSig,
        bytes memory newSig
    ) private view returns (bool) {
        if (verifier.codehash != ROUTER_V2_CLASS) return false;
        if (mode == MODE_ROTATE_NORMAL) {
            try HeartbeatConsentVerificationRouterV2(verifier)
                .verifyNormalPair(b, w, oldRaw, proposed, oldSig, newSig) returns (
                bool ok
            ) {
                return ok;
            } catch {
                return false;
            }
        }
        if (mode == MODE_RECOVER_LOST_KEY) {
            if (oldSig.length != 0) return false;
            try HeartbeatConsentVerificationRouterV2(verifier).verifyRecoveryNew(b, w, proposed, newSig) returns (
                bool ok
            ) {
                return ok;
            } catch {
                return false;
            }
        }
        return false;
    }

    function _bodyKey(bytes memory raw) private view returns (bytes memory) {
        (bool ok, HeartbeatConsentVerificationRouterV2.PrincipalView memory p,) =
            HeartbeatConsentVerificationRouterV2(verifier).decodePrincipal(raw);
        if (!ok) return bytes("");
        return p.bodyPublicKey;
    }

    function principalState(bytes32 id)
        external
        view
        returns (bytes memory, bytes32, uint64, uint64, uint64, uint64, bytes32)
    {
        Entry storage e = _entries[id];
        return (e.record, e.digest, e.generation, e.nonce, e.timelockSequence, e.custodySequence, e.custodyDigest);
    }
}
