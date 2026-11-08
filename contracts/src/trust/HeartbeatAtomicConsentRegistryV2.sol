// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {OperationAwareVAMSTimelockControllerV2} from "../governance/OperationAwareVAMSTimelockControllerV2.sol";
import {HeartbeatConsentV2 as Consent} from "./HeartbeatConsentV2.sol";
import {HeartbeatConsentProfileV2 as ProfileTypes} from "./HeartbeatConsentProfileV2.sol";
import {IHeartbeatConsentProfileV2, IHeartbeatAuthoritySourceV2, IHeartbeatChallengeProviderV2} from "./HeartbeatConsentProfileV2.sol";
import {HeartbeatConsentVerificationRouterV2} from "./HeartbeatConsentVerificationRouterV2.sol";
import {HeartbeatConsentPolicyV2} from "./HeartbeatConsentPolicyV2.sol";

/// @notice Inactive schema-2 atomic consumer prototype for consented EVM principal rotation.
/// @dev No enrollment, withdrawal, approval store, Cardano reader, or live activation.
contract HeartbeatAtomicConsentRegistryV2 {
    uint256 public constant RECOVERY_DELAY = 48 hours;
    uint256 private constant MAX_RAW = 1024;

    struct Entry {
        bytes canonicalRecord;
        bytes32 digest;
        uint64 generation;
        uint64 consentNonce;
        uint64 authoritySequence;
    }
    struct ProofFrame {
        bool active;
        bool consumed;
        bytes32 operationId;
        uint64 operationEpoch;
        bytes32 callDigest;
        bytes32 authorityDigest;
        uint64 authoritySequence;
        bytes32 profileDigest;
        bytes baseRaw;
        bytes witnessRaw;
        bytes oldSignature;
        bytes newSignature;
        bytes challengeEvidence;
    }
    struct RelayRequest {
        bytes baseRaw;
        bytes proposedRaw;
        bytes witnessRaw;
        bytes oldSignature;
        bytes newSignature;
        bytes challengeEvidence;
    }
    struct RelayContext {
        Consent.BaseIntent base;
        HeartbeatConsentVerificationRouterV2.PrincipalView proposed;
        Consent.Witness witness;
        bytes32 proposedDigest;
        ProfileTypes.Profile profile;
        bytes oldRecordRaw;
        bytes callData;
        bytes32 operationId;
        uint64 operationEpoch;
        uint64 eta;
        bytes32 authorityDigest;
        uint64 authoritySequence;
    }
    struct CallbackContext {
        Consent.BaseIntent base;
        HeartbeatConsentVerificationRouterV2.PrincipalView proposed;
        Consent.Witness witness;
        bytes32 proposedDigest;
        ProfileTypes.Profile profile;
        ProfileTypes.AuthoritySnapshot authority;
    }

    error InvalidConfiguration();
    error PolicyUnavailable();
    error AuthorityUnavailable();
    error ChallengeUnavailable();
    error InvalidConsent();
    error StaleState();
    error WrongOperationContext();
    error UnauthorizedExecutor();
    error ReentrantCall();

    address public immutable timelock;
    bytes32 public immutable timelockRuntimeCodeHash;
    address public immutable policy;
    bytes32 public immutable policyRuntimeCodeHash;
    address public immutable verifier;
    bytes32 public immutable verifierRuntimeCodeHash;
    bytes32 public immutable hostDomain;
    bytes32 public immutable serviceDomain;
    uint256 public immutable deploymentChainId;

    mapping(bytes32 principalId => Entry) internal _entries;
    ProofFrame private _frame;
    bool private _relayEntered;

    event PrincipalConsentApplied(bytes32 indexed principalId, bytes32 digest, uint64 generation, uint64 nonce);

    constructor(address timelock_, address policy_, address verifier_, bytes32 hostDomain_, bytes32 serviceDomain_) {
        if (
            timelock_ == address(0) || policy_ == address(0) || verifier_ == address(0) ||
            hostDomain_ == bytes32(0) || serviceDomain_ == bytes32(0) || block.chainid == 0 ||
            timelock_.code.length == 0 || policy_.code.length == 0 || verifier_.code.length == 0 ||
            timelock_.codehash != keccak256(type(OperationAwareVAMSTimelockControllerV2).runtimeCode) ||
            policy_.codehash != keccak256(type(HeartbeatConsentPolicyV2).runtimeCode) ||
            verifier_.codehash != keccak256(type(HeartbeatConsentVerificationRouterV2).runtimeCode) ||
            OperationAwareVAMSTimelockControllerV2(payable(timelock_)).getMinDelay() < RECOVERY_DELAY ||
            IHeartbeatConsentProfileV2(policy_).governance() != timelock_
        ) revert InvalidConfiguration();
        timelock = timelock_;
        timelockRuntimeCodeHash = timelock_.codehash;
        policy = policy_;
        policyRuntimeCodeHash = policy_.codehash;
        verifier = verifier_;
        verifierRuntimeCodeHash = verifier_.codehash;
        hostDomain = hostDomain_;
        serviceDomain = serviceDomain_;
        deploymentChainId = block.chainid;
    }

    /// @notice Relay a post-ETA proof frame through the Timelock's exact singleton operation.
    /// @dev Queued calldata contains only base and proposed record, so no operation-hash cycle exists.
    function relayConsent(
        bytes calldata baseRaw, bytes calldata proposedRaw, bytes calldata witnessRaw,
        bytes calldata oldSignature, bytes calldata newSignature, bytes calldata challengeEvidence
    ) external {
        if (_relayEntered || _frame.active) revert ReentrantCall();
        _relayEntered = true;
        if (baseRaw.length > MAX_RAW || proposedRaw.length > MAX_RAW || witnessRaw.length > MAX_RAW ||
            oldSignature.length > 64 || newSignature.length > 64 || challengeEvidence.length > MAX_RAW) {
            revert InvalidConsent();
        }
        RelayRequest memory request;
        request.baseRaw = baseRaw;
        request.proposedRaw = proposedRaw;
        request.witnessRaw = witnessRaw;
        request.oldSignature = oldSignature;
        request.newSignature = newSignature;
        request.challengeEvidence = challengeEvidence;
        _relayRequest(request);
        delete _frame;
        _relayEntered = false;
    }

    function _relayRequest(RelayRequest memory request) private {
        RelayContext memory context = _decodeRelayRequest(request);
        _checkRelayState(request, context);
        _checkRelayOperation(context);
        _checkRelayDependencies(request, context);
        _frame.active = true;
        _frame.operationId = context.operationId;
        _frame.operationEpoch = context.operationEpoch;
        _frame.callDigest = keccak256(context.callData);
        _frame.authorityDigest = context.authorityDigest;
        _frame.authoritySequence = context.authoritySequence;
        _frame.profileDigest = keccak256(abi.encode(context.profile));
        _frame.baseRaw = request.baseRaw;
        _frame.witnessRaw = request.witnessRaw;
        _frame.oldSignature = request.oldSignature;
        _frame.newSignature = request.newSignature;
        _frame.challengeEvidence = request.challengeEvidence;
        OperationAwareVAMSTimelockControllerV2 lock = OperationAwareVAMSTimelockControllerV2(payable(timelock));
        lock.execute(address(this), 0, context.callData, context.base.timelockPredecessor, context.base.timelockSalt);
        if (!_frame.consumed) revert WrongOperationContext();
    }

    function _decodeRelayRequest(RelayRequest memory request) private view returns (RelayContext memory c) {
        (bool consentOk, Consent.BaseIntent memory base, Consent.Witness memory witness) =
            HeartbeatConsentVerificationRouterV2(verifier).decodeConsent(request.baseRaw, request.witnessRaw);
        (bool proposedOk, HeartbeatConsentVerificationRouterV2.PrincipalView memory proposed, bytes32 proposedDigest) =
            HeartbeatConsentVerificationRouterV2(verifier).decodePrincipal(request.proposedRaw);
        if (!consentOk || !proposedOk) revert InvalidConsent();
        if (base.mode != Consent.MODE_ROTATE_NORMAL && base.mode != Consent.MODE_RECOVER_LOST_KEY) revert InvalidConsent();
        if (base.mode == Consent.MODE_ROTATE_NORMAL && (request.oldSignature.length != 64 || request.newSignature.length != 64)) revert InvalidConsent();
        if (base.mode == Consent.MODE_RECOVER_LOST_KEY && (request.oldSignature.length != 0 || request.newSignature.length != 64)) revert InvalidConsent();
        if (base.timelockAddress != timelock || base.timelockCodeHash != timelockRuntimeCodeHash ||
            base.principalId != proposed.principalId || proposed.hostDomain != hostDomain ||
            proposed.serviceDomain != serviceDomain || proposedDigest != base.proposedRecordDigest ||
            proposed.principalGeneration != base.proposedGeneration) revert InvalidConsent();
        c.base = base;
        c.proposed = proposed;
        c.witness = witness;
        c.proposedDigest = proposedDigest;
    }

    function _checkRelayState(RelayRequest memory request, RelayContext memory c) private view {
        Entry storage entry = _entries[c.base.principalId];
        if (entry.generation == 0 || entry.digest != c.base.expectedRecordDigest ||
            entry.generation != c.base.expectedGeneration || entry.consentNonce != c.base.consentNonce ||
            entry.generation == type(uint64).max || c.base.proposedGeneration != entry.generation + 1 ||
            c.proposed.policyRoot != c.base.policyRoot || c.proposed.policyVersion != c.base.policyVersion ||
            c.proposed.authorityEpoch != c.base.authorityEpoch) revert StaleState();
        c.oldRecordRaw = entry.canonicalRecord;
        c.profile = _loadProfile();
        _checkProposalProfile(c.profile, c.base, c.oldRecordRaw, c.proposed);
        if (c.profile.relayerPolicy == ProfileTypes.RELAYER_POLICY_ADDRESS && msg.sender != c.profile.allowedRelayer) revert InvalidConsent();
        if (c.profile.keyPolicy == ProfileTypes.KEY_POLICY_REQUIRE_DISTINCT &&
            keccak256(_bodyKey(c.oldRecordRaw)) == keccak256(c.proposed.bodyPublicKey)) revert InvalidConsent();
        c.callData = abi.encodeCall(this.applyConsent, (request.baseRaw, request.proposedRaw));
    }

    function _checkRelayOperation(RelayContext memory c) private view {
        OperationAwareVAMSTimelockControllerV2 lock = OperationAwareVAMSTimelockControllerV2(payable(timelock));
        c.operationId = lock.hashOperation(address(this), 0, c.callData, c.base.timelockPredecessor, c.base.timelockSalt);
        uint256 eta = lock.getTimestamp(c.operationId);
        if (eta <= 1 || eta > type(uint64).max || uint64(eta) != c.witness.queuedEta || c.operationId != c.witness.operationId ||
            !lock.isOperationReady(c.operationId) || c.witness.issuedAt < c.witness.queuedEta || c.witness.issuedAt > block.timestamp ||
            c.witness.expiresAt <= block.timestamp || c.witness.expiresAt - c.witness.issuedAt > c.profile.maxConsentTtl) revert InvalidConsent();
        if (c.base.mode == Consent.MODE_RECOVER_LOST_KEY && lock.scheduledDelay(c.operationId) < RECOVERY_DELAY) revert InvalidConsent();
        if (!lock.hasRole(lock.EXECUTOR_ROLE(), address(this)) && !lock.hasRole(lock.EXECUTOR_ROLE(), address(0))) revert UnauthorizedExecutor();
        c.eta = uint64(eta);
        c.operationEpoch = lock.operationEpoch(c.operationId);
    }

    function _checkRelayDependencies(RelayRequest memory request, RelayContext memory c) private view {
        ProfileTypes.AuthoritySnapshot memory authority = _readAuthority(c.profile);
        c.authorityDigest = ProfileTypes.authorityDigest(authority);
        if (c.authorityDigest != c.base.authoritySourceDigest || authority.authorityConfigDigest != c.base.authorityConfigDigest ||
            authority.authorityChangeSequence != c.base.authorityChangeSequence ||
            authority.authorityChangeSequence < _entries[c.base.principalId].authoritySequence) revert AuthorityUnavailable();
        ProfileTypes.ChallengeFacts memory challenge = _readChallenge(c.profile, request.challengeEvidence);
        _checkChallenge(c.profile, challenge, c.witness, c.base, request.challengeEvidence,
            c.operationId, c.operationEpoch, c.eta);
        if (!_verify(c.base.mode, request.baseRaw, request.witnessRaw, c.oldRecordRaw,
            request.proposedRaw, request.oldSignature, request.newSignature)) revert InvalidConsent();
        c.authoritySequence = authority.authorityChangeSequence;
    }

    /// @notice Timelock-only mutation callback; direct and batch calls reject.
    function applyConsent(bytes calldata baseRaw, bytes calldata proposedRaw) external {
        ProofFrame storage f = _frame;
        bytes32 operationId = _checkCallbackOperation(f);
        CallbackContext memory context = _decodeCallback(baseRaw, proposedRaw, f);
        _checkCallbackCurrentState(context, f);
        _checkCallbackAuthority(context, f);
        _checkCallbackChallenge(context, f, operationId);
        _checkCallbackSignatures(context, f, proposedRaw);
        _commitCallback(context, f, proposedRaw);
    }

    function _checkCallbackOperation(ProofFrame storage f) private view returns (bytes32 operationId) {
        if (!f.active || f.consumed || msg.sender != timelock) revert WrongOperationContext();
        OperationAwareVAMSTimelockControllerV2 lock = OperationAwareVAMSTimelockControllerV2(payable(timelock));
        (bool active, bytes32 op, bool batch) = lock.activeOperationContext();
        if (!active || batch || op != f.operationId || keccak256(msg.data) != f.callDigest || lock.operationEpoch(op) != f.operationEpoch) {
            revert WrongOperationContext();
        }
        return op;
    }

    function _decodeCallback(bytes calldata baseRaw, bytes calldata proposedRaw, ProofFrame storage f)
        private view returns (CallbackContext memory c)
    {
        (bool consentOk, Consent.BaseIntent memory base, Consent.Witness memory witness) =
            HeartbeatConsentVerificationRouterV2(verifier).decodeConsent(baseRaw, f.witnessRaw);
        (bool proposedOk, HeartbeatConsentVerificationRouterV2.PrincipalView memory proposed, bytes32 proposedDigest) =
            HeartbeatConsentVerificationRouterV2(verifier).decodePrincipal(proposedRaw);
        if (!consentOk || !proposedOk || base.principalId != proposed.principalId) revert InvalidConsent();
        c.base = base;
        c.proposed = proposed;
        c.witness = witness;
        c.proposedDigest = proposedDigest;
    }

    function _checkCallbackCurrentState(CallbackContext memory c, ProofFrame storage f) private view {
        Entry storage entry = _entries[c.base.principalId];
        if (entry.digest != c.base.expectedRecordDigest || entry.generation != c.base.expectedGeneration ||
            entry.consentNonce != c.base.consentNonce || entry.generation == type(uint64).max ||
            c.proposed.principalGeneration != entry.generation + 1 ||
            c.proposedDigest != c.base.proposedRecordDigest) revert StaleState();
        c.profile = _loadProfile();
        _checkProposalProfile(c.profile, c.base, entry.canonicalRecord, c.proposed);
        if (keccak256(abi.encode(c.profile)) != f.profileDigest) revert PolicyUnavailable();
    }

    function _checkCallbackAuthority(CallbackContext memory c, ProofFrame storage f) private view {
        c.authority = _readAuthority(c.profile);
        Entry storage entry = _entries[c.base.principalId];
        if (ProfileTypes.authorityDigest(c.authority) != f.authorityDigest ||
            c.authority.authorityChangeSequence != f.authoritySequence ||
            c.authority.authorityChangeSequence != c.base.authorityChangeSequence ||
            c.authority.authorityChangeSequence < entry.authoritySequence) revert AuthorityUnavailable();
    }

    function _checkCallbackChallenge(CallbackContext memory c, ProofFrame storage f, bytes32 operationId) private view {
        if (c.witness.operationId != operationId) revert InvalidConsent();
        ProfileTypes.ChallengeFacts memory facts = _readChallenge(c.profile, f.challengeEvidence);
        _checkChallenge(c.profile, facts, c.witness, c.base, f.challengeEvidence,
            operationId, f.operationEpoch, c.witness.queuedEta);
    }

    function _checkCallbackSignatures(CallbackContext memory c, ProofFrame storage f, bytes calldata proposedRaw) private view {
        Entry storage entry = _entries[c.base.principalId];
        if (!_verify(c.base.mode, f.baseRaw, f.witnessRaw, entry.canonicalRecord,
            proposedRaw, f.oldSignature, f.newSignature)) revert InvalidConsent();
    }

    function _commitCallback(CallbackContext memory c, ProofFrame storage f, bytes calldata proposedRaw) private {
        Entry storage entry = _entries[c.base.principalId];
        if (entry.consentNonce == type(uint64).max) revert StaleState();
        entry.canonicalRecord = proposedRaw;
        entry.digest = c.proposedDigest;
        entry.generation = c.proposed.principalGeneration;
        ++entry.consentNonce;
        entry.authoritySequence = c.authority.authorityChangeSequence;
        f.consumed = true;
        emit PrincipalConsentApplied(c.base.principalId, entry.digest, entry.generation, entry.consentNonce);
    }

    function principalState(bytes32 principalId) external view returns (bytes memory, bytes32, uint64, uint64, uint64) {
        Entry storage e = _entries[principalId];
        return (e.canonicalRecord, e.digest, e.generation, e.consentNonce, e.authoritySequence);
    }

    function _loadProfile() private view returns (ProfileTypes.Profile memory p) {
        if (policy.codehash != policyRuntimeCodeHash || verifier.codehash != verifierRuntimeCodeHash ||
            timelock.codehash != timelockRuntimeCodeHash || block.chainid != deploymentChainId) revert PolicyUnavailable();
        try IHeartbeatConsentProfileV2(policy).consentProfile() returns (ProfileTypes.Profile memory v) { p = v; }
        catch { revert PolicyUnavailable(); }
        if (!ProfileTypes.validProfile(p)) revert PolicyUnavailable();
    }

    function _readAuthority(ProfileTypes.Profile memory p) private view returns (ProfileTypes.AuthoritySnapshot memory a) {
        if (p.authoritySource.codehash != p.authoritySourceRuntimeCodeHash) revert AuthorityUnavailable();
        try IHeartbeatAuthoritySourceV2(p.authoritySource).currentSnapshot() returns (ProfileTypes.AuthoritySnapshot memory v) { a = v; }
        catch { revert AuthorityUnavailable(); }
        if (a.sourceSchema != ProfileTypes.AUTHORITY_SOURCE_SCHEMA || a.scheme != ProfileTypes.EVM_SCHEME ||
            a.registrySchema != ProfileTypes.REGISTRY_SCHEMA || a.chainId != deploymentChainId ||
            a.networkContextDigest != p.networkContextDigest || a.registry != address(this) ||
            a.registryRuntimeCodeHash != address(this).codehash || a.policy != policy || a.policyRuntimeCodeHash != policyRuntimeCodeHash ||
            a.timelock != timelock || a.timelockRuntimeCodeHash != timelockRuntimeCodeHash ||
            a.authorityConfigDigest != p.authorityConfigDigest || a.isProxy || a.policyRoot != p.policyRoot ||
            a.policyVersion != p.policyVersion || a.authorityEpoch != p.authorityEpoch) revert AuthorityUnavailable();
    }

    function _readChallenge(ProfileTypes.Profile memory p, bytes memory evidence) private view returns (ProfileTypes.ChallengeFacts memory c) {
        if (p.challengeProvider.codehash != p.challengeProviderRuntimeCodeHash) revert ChallengeUnavailable();
        try IHeartbeatChallengeProviderV2(p.challengeProvider).resolveChallenge(evidence) returns (ProfileTypes.ChallengeFacts memory v) { c = v; }
        catch { revert ChallengeUnavailable(); }
        if (c.schema != ProfileTypes.CHALLENGE_SCHEMA) revert ChallengeUnavailable();
    }

    function _checkChallenge(ProfileTypes.Profile memory p, ProfileTypes.ChallengeFacts memory c,
        Consent.Witness memory w, Consent.BaseIntent memory b, bytes memory evidence,
        bytes32 op, uint64 epoch, uint64 eta) private view {
        OperationAwareVAMSTimelockControllerV2 lock = OperationAwareVAMSTimelockControllerV2(payable(timelock));
        if (c.operationId != op || c.operationEpoch != epoch || c.queuedEta != eta || c.baseIntentDigest != w.baseIntentDigest ||
            c.challengeCommitment != w.postEtaChallengeCommitment || c.issuedAt != w.issuedAt || c.expiresAt != w.expiresAt ||
            c.issuedAt < eta || c.issuedAt > block.timestamp || c.expiresAt <= block.timestamp ||
            c.expiresAt - c.issuedAt > p.maxConsentTtl || c.revoked || c.networkContextDigest != p.networkContextDigest ||
            c.evidenceDigest != sha256(evidence) ||
            c.challengeProfileDigest != p.challengeProfileDigest || c.finalityProfileDigest != p.finalityProfileDigest ||
            lock.getTimestamp(op) != eta || !lock.isOperationReady(op) || lock.operationEpoch(op) != epoch ||
            (b.mode == Consent.MODE_RECOVER_LOST_KEY && lock.scheduledDelay(op) < RECOVERY_DELAY)) revert ChallengeUnavailable();
    }

    function _checkProposalProfile(ProfileTypes.Profile memory p, Consent.BaseIntent memory b, bytes memory oldRaw,
        HeartbeatConsentVerificationRouterV2.PrincipalView memory proposed) private view {
        if (!p.configured || p.policyRoot != b.policyRoot || p.policyVersion != b.policyVersion || p.authorityEpoch != b.authorityEpoch ||
            p.oldKeyGracePolicy != ProfileTypes.GRACE_POLICY_ZERO || p.oldKeyGraceSeconds != 0 ||
            proposed.policyRoot != p.policyRoot || proposed.policyVersion != p.policyVersion || proposed.authorityEpoch != p.authorityEpoch ||
            proposed.notBefore > block.timestamp || proposed.expiresAt <= block.timestamp ||
            proposed.expiresAt - proposed.notBefore > p.maxPrincipalLifetime) revert PolicyUnavailable();
        if (p.keyPolicy == ProfileTypes.KEY_POLICY_REQUIRE_DISTINCT && keccak256(_bodyKey(oldRaw)) == keccak256(proposed.bodyPublicKey)) revert InvalidConsent();
    }

    function _verify(uint8 mode, bytes memory b, bytes memory w, bytes memory oldRaw, bytes memory proposed,
        bytes memory oldSig, bytes memory newSig) private view returns (bool) {
        if (verifier.codehash != verifierRuntimeCodeHash) return false;
        if (mode == Consent.MODE_ROTATE_NORMAL) {
            try HeartbeatConsentVerificationRouterV2(verifier).verifyNormalPair(b, w, oldRaw, proposed, oldSig, newSig) returns (bool ok) { return ok; }
            catch { return false; }
        }
        if (mode == Consent.MODE_RECOVER_LOST_KEY) {
            if (oldSig.length != 0) return false;
            try HeartbeatConsentVerificationRouterV2(verifier).verifyRecoveryNew(b, w, proposed, newSig) returns (bool ok) { return ok; }
            catch { return false; }
        }
        return false;
    }

    function _bodyKey(bytes memory raw) private view returns (bytes memory) {
        (bool ok, HeartbeatConsentVerificationRouterV2.PrincipalView memory record,) =
            HeartbeatConsentVerificationRouterV2(verifier).decodePrincipal(raw);
        if (!ok) return bytes("");
        return record.bodyPublicKey;
    }
}
