// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Vm} from "forge-std/Vm.sol";
import {OperationAwareVAMSTimelockControllerV3} from "../src/governance/OperationAwareVAMSTimelockControllerV3.sol";
import {HeartbeatConsentPolicyV3} from "../src/trust/HeartbeatConsentPolicyV3.sol";
import {HeartbeatAuthoritySourceV3} from "../src/trust/HeartbeatAuthoritySourceV3.sol";
import {HeartbeatAuthorityTypesV3 as Types} from "../src/trust/HeartbeatAuthorityTypesV3.sol";
import {HeartbeatConsentProfileV2 as ChallengeTypes} from "../src/trust/HeartbeatConsentProfileV2.sol";
import {HeartbeatConsentVerificationRouterV2} from "../src/trust/HeartbeatConsentVerificationRouterV2.sol";
import {HeartbeatAtomicConsentRegistryV3} from "../src/trust/HeartbeatAtomicConsentRegistryV3.sol";
import {HeartbeatConsentV2 as Consent} from "../src/trust/HeartbeatConsentV2.sol";
import {HeartbeatPrincipalV1 as Principal} from "../src/trust/HeartbeatPrincipalV1.sol";

/// @dev Synthetic local custody observation; supplies no authentic signer/custody authority.
contract SyntheticCustody91Sol {
    uint64 public sequence = 2;
    bytes32 public digest = keccak256("synthetic-custody-91sol");

    function set(uint64 nextSequence, bytes32 nextDigest) external {
        sequence = nextSequence;
        digest = nextDigest;
    }

    function currentCustodyState() external view returns (Types.CustodyState memory) {
        return Types.CustodyState(1, sequence, digest);
    }
}

/// @dev Challenge mutation is confined to this fixture. All consumer/producer code is real.
contract SyntheticChallenge91Sol {
    ChallengeTypes.ChallengeFacts private _facts;
    OperationAwareVAMSTimelockControllerV3 private _lock;
    bool private _mismatchDuringCallback;
    address private _reentryTarget;
    bytes private _reentryCall;
    bool private _reentryOnlyDuringActiveOperation;
    bool private _bubbleReentryFailure;

    error NestedRelayWasNotRejected();

    function set(ChallengeTypes.ChallengeFacts calldata facts) external {
        _facts = facts;
    }

    function setCallbackMismatch(address lock_, bool enabled) external {
        _lock = OperationAwareVAMSTimelockControllerV3(payable(lock_));
        _mismatchDuringCallback = enabled;
    }

    function setStaticReentryProbe(
        address lock_, address target, bytes calldata relayCall, bool onlyDuringActiveOperation, bool bubbleFailure
    ) external {
        _lock = OperationAwareVAMSTimelockControllerV3(payable(lock_));
        _reentryTarget = target;
        _reentryCall = relayCall;
        _reentryOnlyDuringActiveOperation = onlyDuringActiveOperation;
        _bubbleReentryFailure = bubbleFailure;
    }

    function resolveChallenge(bytes calldata) external view returns (ChallengeTypes.ChallengeFacts memory facts) {
        facts = _facts;
        if (_reentryTarget != address(0)) {
            bool probe = true;
            if (_reentryOnlyDuringActiveOperation) {
                (probe,,) = _lock.activeOperationContext();
            }
            if (probe) {
                (bool ok, bytes memory result) = _reentryTarget.staticcall(_reentryCall);
                bytes4 selector;
                if (result.length >= 4) assembly { selector := mload(add(result, 0x20)) }
                if (_bubbleReentryFailure) {
                    // Test oracle: only the exact guard denial causes the outer
                    // ChallengeUnavailable rollback. A different/empty failure
                    // returns valid facts, making the expected outer revert fail.
                    if (ok || selector != HeartbeatAtomicConsentRegistryV3.ReentrantCall.selector) return facts;
                    assembly ("memory-safe") {
                        revert(add(result, 0x20), mload(result))
                    }
                }
                if (ok || selector != HeartbeatAtomicConsentRegistryV3.ReentrantCall.selector) {
                    revert NestedRelayWasNotRejected();
                }
            }
        }
        if (_mismatchDuringCallback) {
            (bool active,,) = _lock.activeOperationContext();
            if (active) ++facts.operationEpoch;
        }
    }
}

/// @dev Local migration fixture only. There is no production enrollment or verifier override.
contract SeedableRegistry91Sol is HeartbeatAtomicConsentRegistryV3 {
    constructor(
        address t,
        address p,
        address v,
        address s,
        address c,
        bytes32 ch,
        address q,
        bytes32 qh,
        bytes32 n,
        bytes32 h,
        bytes32 x
    ) HeartbeatAtomicConsentRegistryV3(t, p, v, s, c, ch, q, qh, n, h, x) {}

    function seedCanonicalForTest(bytes calldata raw) external {
        (bool ok, HeartbeatConsentVerificationRouterV2.PrincipalView memory p, bytes32 digest) =
            HeartbeatConsentVerificationRouterV2(verifier).decodePrincipal(raw);
        require(ok && p.hostDomain == hostDomain && p.serviceDomain == serviceDomain, "canonical seed domains");
        Types.Profile memory profile = _loadProfile();
        Types.ProducerState memory authority = _readAuthority(profile);
        require(
            p.policyRoot == profile.policyRoot && p.policyVersion == profile.policyVersion
                && p.authorityEpoch == profile.authorityEpoch && p.notBefore <= block.timestamp
                && p.expiresAt > block.timestamp && p.expiresAt - p.notBefore <= profile.maxPrincipalLifetime,
            "canonical seed current profile"
        );
        require(_entries[p.principalId].generation == 0, "seed once");
        _entries[p.principalId] = Entry(
            raw,
            digest,
            p.principalGeneration,
            0,
            authority.authorityChangeSequence,
            authority.custodyChangeSequence,
            authority.custodyConfigurationDigest
        );
    }
}

/// @dev Public fixed VM scalars 11/12/13 are test fixtures, never real deployment keys.
///      All TTLs, roles and provider facts below are synthetic local choices, not approved profiles.
contract HeartbeatAtomicConsentRegistryV3IntegrationTests is Test {
    uint256 private constant OLD_KEY = 11;
    uint256 private constant NEW_KEY = 12;
    uint256 private constant M2_KEY = 13;
    uint256 private constant N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
    string private constant SIG_DOMAIN = "VAMS:GATEWAY:HEARTBEAT-CONSENT-SIGNATURE:v2";
    bytes32 private constant ROOT = keccak256("synthetic-governed-root-91sol");
    bytes32 private constant NETWORK = keccak256("synthetic-evm-network-91sol");
    bytes32 private constant CHALLENGE_PROFILE = keccak256("synthetic-challenge-profile-91sol");
    bytes32 private constant FINALITY_PROFILE = keccak256("synthetic-finality-profile-91sol");

    OperationAwareVAMSTimelockControllerV3 private lock;
    HeartbeatConsentPolicyV3 private policy;
    HeartbeatAuthoritySourceV3 private source;
    HeartbeatConsentVerificationRouterV2 private verifier;
    SyntheticCustody91Sol private custody;
    SyntheticChallenge91Sol private challenges;
    SeedableRegistry91Sol private registry;
    Principal.Record private oldRecord;
    bytes private oldRaw;

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

    function setUp() public {
        vm.warp(1_800_000_000);
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        lock = new OperationAwareVAMSTimelockControllerV3(48 hours, proposers, executors, address(this));
        custody = new SyntheticCustody91Sol();
        challenges = new SyntheticChallenge91Sol();
        verifier = new HeartbeatConsentVerificationRouterV2();
        policy = new HeartbeatConsentPolicyV3(address(lock), keccak256(type(HeartbeatAuthoritySourceV3).runtimeCode));
        source = new HeartbeatAuthoritySourceV3(
            address(lock), address(policy), address(custody), address(custody).codehash, block.chainid, NETWORK
        );
        _govern(address(policy), abi.encodeCall(policy.bindAuthoritySource, (address(source))), keccak256("bind-91sol"));
        _configure(1);
        registry = _newRegistry();
        _govern(
            address(lock),
            abi.encodeCall(lock.grantRole, (lock.EXECUTOR_ROLE(), address(registry))),
            keccak256("grant-registry-91sol")
        );
        // EXECUTOR grant changes the actual producer digest. Refresh before any signed frame/seed.
        _configure(2);
        oldRecord = _record(OLD_KEY, 1);
        oldRaw = Principal.canonicalBytes(oldRecord);
        registry.seedCanonicalForTest(oldRaw);
    }

    function testSignedNormalOldAndNewCommitThroughRealV3Callback() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        require(p.oldSignature.length == 64 && p.newSignature.length == 64, "both role signatures");
        require(
            verifier.verifyNormalPair(p.baseRaw, p.witnessRaw, oldRaw, p.proposedRaw, p.oldSignature, p.newSignature),
            "real router validates normal pair"
        );
        vm.warp(p.eta);
        _relay(registry, p);
        _assertCommitted(registry, p);
    }

    function testSignedRecoveryNewOnlyCommitsAfterObservedFortyEightHours() public {
        uint256 scheduledAt = block.timestamp;
        Prepared memory p = _prepare(registry, registry, Consent.MODE_RECOVER_LOST_KEY, 0);
        require(p.oldSignature.length == 0 && p.newSignature.length == 64, "NEW only");
        require(
            lock.scheduledDelay(p.operationId) >= 48 hours && p.eta >= scheduledAt + 48 hours,
            "actual recorded schedule delay"
        );
        require(
            verifier.verifyRecoveryNew(p.baseRaw, p.witnessRaw, p.proposedRaw, p.newSignature),
            "real router validates recovery NEW"
        );
        vm.warp(p.eta);
        _relay(registry, p);
        _assertCommitted(registry, p);
    }

    function testStaticChallengeCallbackCannotReenterSignedNormalRelayDuringTimelockExecution() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        bytes memory nestedRelay = abi.encodeCall(
            registry.relayConsent,
            (p.baseRaw, p.proposedRaw, p.witnessRaw, bytes(""), p.newSignature, p.evidence)
        );
        challenges.setStaticReentryProbe(address(lock), address(registry), nestedRelay, true, false);
        vm.expectCall(address(registry), nestedRelay);
        vm.warp(p.eta);

        _assertGenuineNormalPair(p);
        _relay(registry, p);
        _assertCommitted(registry, p);
    }

    function testUncaughtStaticCallbackNestedRecoveryRelayRollsBackThenRetriesOnce() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_RECOVER_LOST_KEY, 0);
        bytes memory nestedRelay = abi.encodeCall(
            registry.relayConsent,
            (p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, bytes(""), p.evidence)
        );
        challenges.setStaticReentryProbe(address(lock), address(registry), nestedRelay, true, true);
        vm.expectCall(address(registry), nestedRelay);
        vm.warp(p.eta);

        require(
            verifier.verifyRecoveryNew(p.baseRaw, p.witnessRaw, p.proposedRaw, p.newSignature),
            "real router validates recovery NEW"
        );
        bytes32 beforeState = _stateHash(registry);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.ChallengeUnavailable.selector);
        _relay(registry, p);
        _assertUnchangedReady(registry, p, beforeState);

        challenges.setStaticReentryProbe(address(lock), address(0), bytes(""), true, true);
        _relay(registry, p);
        _assertCommitted(registry, p);
    }

    function testRecoveryBeforeEtaRejectsWithoutMutationOrConsumption() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_RECOVER_LOST_KEY, 0);
        vm.warp(p.eta - 1);
        bytes32 beforeState = _stateHash(registry);
        vm.expectRevert();
        _relay(registry, p);
        require(_stateHash(registry) == beforeState && !lock.isOperationDone(p.operationId), "early recovery unchanged");
        require(lock.getTimestamp(p.operationId) == p.eta, "ETA retained");
        vm.warp(p.eta);
        _relay(registry, p);
        _assertCommitted(registry, p);
    }

    function testNormalMissingOldRejectsThenSameSignedOperationSucceeds() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        bytes memory oldSignature = p.oldSignature;
        p.oldSignature = bytes("");
        vm.warp(p.eta);
        bytes32 beforeState = _stateHash(registry);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.InvalidConsent.selector);
        _relay(registry, p);
        _assertUnchangedReady(registry, p, beforeState);
        p.oldSignature = oldSignature;
        _relay(registry, p);
        _assertCommitted(registry, p);
    }

    function testNormalWrongNewSignerRejectsThenCorrectPairSucceeds() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        bytes memory correctNew = p.newSignature;
        p.newSignature = _sign(OLD_KEY, _statement(p.witnessRaw, Consent.ROLE_NEW_KEY));
        require(
            !verifier.verifyNormalPair(p.baseRaw, p.witnessRaw, oldRaw, p.proposedRaw, p.oldSignature, p.newSignature),
            "real verifier rejects wrong NEW key"
        );
        vm.warp(p.eta);
        bytes32 beforeState = _stateHash(registry);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.InvalidConsent.selector);
        _relay(registry, p);
        _assertUnchangedReady(registry, p, beforeState);
        p.newSignature = correctNew;
        _relay(registry, p);
        _assertCommitted(registry, p);
    }

    function testSignedReplayCannotAdvanceGenerationOrNonceTwice() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        vm.warp(p.eta);
        _relay(registry, p);
        _assertCommitted(registry, p);
        bytes32 afterState = _stateHash(registry);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.StaleState.selector);
        _relay(registry, p);
        require(_stateHash(registry) == afterState && lock.isOperationDone(p.operationId), "replay unchanged");
    }

    function testSignedWrongNonceRejectsBeforeOperationConsumption() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 1);
        require(
            verifier.verifyNormalPair(p.baseRaw, p.witnessRaw, oldRaw, p.proposedRaw, p.oldSignature, p.newSignature),
            "wrong nonce still has genuine possession signatures"
        );
        vm.warp(p.eta);
        bytes32 beforeState = _stateHash(registry);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.StaleState.selector);
        _relay(registry, p);
        _assertUnchangedReady(registry, p, beforeState);
    }

    function testCallbackChallengeMismatchRollsBackEveryFieldAndSameProofRetries() public {
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        challenges.setCallbackMismatch(address(lock), true);
        vm.warp(p.eta);
        bytes32 beforeState = _stateHash(registry);
        uint64 epoch = lock.operationEpoch(p.operationId);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.ChallengeUnavailable.selector);
        _relay(registry, p);
        _assertUnchangedReady(registry, p, beforeState);
        require(lock.operationEpoch(p.operationId) == epoch, "epoch rolled back");
        challenges.setCallbackMismatch(address(lock), false);
        _relay(registry, p);
        _assertCommitted(registry, p);
    }

    function testOtherRegistryCannotUseSignedForeignConsumerAuthorityDigest() public {
        SeedableRegistry91Sol second = _newRegistry();
        _govern(
            address(lock),
            abi.encodeCall(lock.grantRole, (lock.EXECUTOR_ROLE(), address(second))),
            keccak256("grant-second-91sol")
        );
        _configure(3);
        // Fresh synthetic migration under the refreshed profile; expected record remains oldRaw.
        // This independent registry gets the same canonical generation-one identity with current policy.
        oldRecord = _record(OLD_KEY, 1);
        oldRaw = Principal.canonicalBytes(oldRecord);
        second.seedCanonicalForTest(oldRaw);
        Prepared memory p = _prepare(second, registry, Consent.MODE_ROTATE_NORMAL, 0);
        require(
            verifier.verifyNormalPair(p.baseRaw, p.witnessRaw, oldRaw, p.proposedRaw, p.oldSignature, p.newSignature),
            "foreign digest has genuine possession signatures for exact second queue"
        );
        vm.warp(p.eta);
        bytes32 beforeState = _stateHash(second);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.AuthorityUnavailable.selector);
        _relay(second, p);
        _assertUnchangedReady(second, p, beforeState);
    }

    function testFreshPolicyCannotHideCustodySequenceRollbackFromTwoToOne() public {
        _assertSeededCustody(2, custody.digest());
        bytes32 seededState = _stateHash(registry);
        custody.set(1, keccak256("synthetic-custody-rollback-91solr2"));
        _configure(3);
        _assertFreshCurrentPolicyAndPriorOldRecord();
        require(source.currentState().custodyChangeSequence == 1, "current producer observes rollback");
        require(_stateHash(registry) == seededState, "policy refresh did not reseed principal");
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        _assertGenuineNormalPair(p);
        vm.warp(p.eta);
        uint64 epoch = lock.operationEpoch(p.operationId);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.AuthorityUnavailable.selector);
        _relay(registry, p);
        _assertUnchangedReady(registry, p, seededState);
        require(lock.operationEpoch(p.operationId) == epoch, "rollback rejection preserves operation epoch");
    }

    function testFreshPolicyCannotHideDigestDriftAtSameCustodySequenceTwo() public {
        bytes32 seededDigest = custody.digest();
        _assertSeededCustody(2, seededDigest);
        bytes32 seededState = _stateHash(registry);
        bytes32 changedDigest = keccak256("synthetic-custody-same-sequence-drift-91solr2");
        require(changedDigest != seededDigest, "different custody configuration");
        custody.set(2, changedDigest);
        _configure(3);
        _assertFreshCurrentPolicyAndPriorOldRecord();
        require(
            source.currentState().custodyChangeSequence == 2
                && source.currentState().custodyConfigurationDigest == changedDigest,
            "current producer observes same-sequence drift"
        );
        require(_stateHash(registry) == seededState, "policy refresh did not reseed principal");
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        _assertGenuineNormalPair(p);
        vm.warp(p.eta);
        uint64 epoch = lock.operationEpoch(p.operationId);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.AuthorityUnavailable.selector);
        _relay(registry, p);
        _assertUnchangedReady(registry, p, seededState);
        require(lock.operationEpoch(p.operationId) == epoch, "drift rejection preserves operation epoch");
    }

    function testFreshPolicyAndIncreasingCustodySequenceCommitsNewAnchor() public {
        _assertSeededCustody(2, custody.digest());
        bytes32 seededState = _stateHash(registry);
        bytes32 nextDigest = keccak256("synthetic-custody-next-configuration-91solr2");
        require(nextDigest != custody.digest(), "different next custody configuration");
        custody.set(3, nextDigest);
        _configure(3);
        _assertFreshCurrentPolicyAndPriorOldRecord();
        require(_stateHash(registry) == seededState, "policy refresh did not reseed principal");
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        _assertGenuineNormalPair(p);
        vm.warp(p.eta);
        _relay(registry, p);
        _assertCommitted(registry, p);
        _assertSeededCustody(3, nextDigest);
    }

    function testCancelAndSameIdSameEtaRequeueRejectsOldSignedChallengeEpoch() public {
        // No warp between original scheduling, cancellation and requeue: ETA, base,
        // operation ID and TTL stay identical; only the actual queue epoch changes.
        Prepared memory p = _prepare(registry, registry, Consent.MODE_ROTATE_NORMAL, 0);
        _assertGenuineNormalPair(p);
        (bool ok, Consent.BaseIntent memory b) = Consent.tryDecodeBase(p.baseRaw);
        require(ok, "canonical queued base");
        bytes memory payload = abi.encodeCall(registry.applyConsent, (p.baseRaw, p.proposedRaw));
        uint64 oldEpoch = lock.operationEpoch(p.operationId);
        bytes32 authorityBefore = source.currentState().authorityConfigDigest;
        lock.cancel(p.operationId);
        lock.schedule(address(registry), 0, payload, b.timelockPredecessor, b.timelockSalt, 48 hours);
        require(
            lock.hashOperation(address(registry), 0, payload, b.timelockPredecessor, b.timelockSalt) == p.operationId
                && lock.getTimestamp(p.operationId) == p.eta,
            "identical operation ID and ETA"
        );
        require(lock.operationEpoch(p.operationId) == oldEpoch + 2, "cancel and requeue advance epoch");
        require(
            source.currentState().authorityConfigDigest == authorityBefore
                && policy.consentProfile().authorityConfigDigest == authorityBefore,
            "ordinary queue lifecycle does not stale authority policy"
        );
        vm.warp(p.eta);
        bytes32 beforeState = _stateHash(registry);
        _assertGenuineNormalPair(p);
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.ChallengeUnavailable.selector);
        _relay(registry, p);
        _assertUnchangedReady(registry, p, beforeState);
        require(lock.operationEpoch(p.operationId) == oldEpoch + 2, "old approvals cannot consume requeued epoch");
    }

    function _assertSeededCustody(uint64 expectedSequence, bytes32 expectedDigest) private view {
        (,,,,, uint64 observedSequence, bytes32 observedDigest) = registry.principalState(oldRecord.principalId);
        require(
            observedSequence == expectedSequence && observedDigest == expectedDigest,
            "retained principal custody anchor"
        );
    }

    function _assertFreshCurrentPolicyAndPriorOldRecord() private view {
        Types.Profile memory p = policy.consentProfile();
        Types.ProducerState memory a = source.currentState();
        require(
            p.policyVersion == 3 && p.authorityEpoch == 3 && p.authorityConfigDigest == a.authorityConfigDigest
                && a.authorityConfigDigest == Types.authorityConfigDigest(a),
            "fresh policy equals recomputed current producer digest"
        );
        require(
            oldRecord.policyVersion == 2 && oldRecord.authorityEpoch == 2,
            "OLD record retains prior profile while NEW consent uses current profile"
        );
    }

    function _assertGenuineNormalPair(Prepared memory p) private view {
        require(
            verifier.verifyNormalPair(p.baseRaw, p.witnessRaw, oldRaw, p.proposedRaw, p.oldSignature, p.newSignature),
            "actual router validates OLD plus NEW signatures before consumer guard"
        );
    }

    function _prepare(SeedableRegistry91Sol target, SeedableRegistry91Sol digestTarget, uint8 mode, uint64 nonce)
        private
        returns (Prepared memory p)
    {
        Principal.Record memory proposed = _record(NEW_KEY, 2);
        proposed.notBefore = uint64(block.timestamp + 48 hours);
        proposed.expiresAt = proposed.notBefore + 50000;
        p.proposedRaw = Principal.canonicalBytes(proposed);
        Types.ProducerState memory a = source.currentState();
        Types.Profile memory profile = policy.consentProfile();
        Consent.BaseIntent memory b;
        b.mode = mode;
        b.sourceScheme = Types.EVM_SCHEME;
        b.authoritySourceDigest = sha256(
            abi.encode(
                bytes32("VAMS:CONSUMER:AUTHORITY:V3"),
                block.chainid,
                address(digestTarget),
                address(digestTarget).codehash,
                a.authorityConfigDigest
            )
        );
        b.timelockAddress = address(lock);
        b.timelockCodeHash = address(lock).codehash;
        b.authorityConfigDigest = a.authorityConfigDigest;
        b.authorityChangeSequence = a.authorityChangeSequence;
        b.policyRoot = profile.policyRoot;
        b.policyVersion = profile.policyVersion;
        b.authorityEpoch = profile.authorityEpoch;
        b.principalId = oldRecord.principalId;
        b.proposedRecordDigest = Principal.digest(proposed);
        b.expectedRecordDigest = Principal.digest(oldRecord);
        b.expectedGeneration = 1;
        b.proposedGeneration = 2;
        b.consentNonce = nonce;
        b.timelockSalt = keccak256(abi.encode("synthetic-signed-91sol", address(target), mode, nonce));
        p.baseRaw = Consent.canonicalBaseBytes(b);
        bytes memory payload = abi.encodeCall(target.applyConsent, (p.baseRaw, p.proposedRaw));
        p.operationId = lock.hashOperation(address(target), 0, payload, b.timelockPredecessor, b.timelockSalt);
        lock.schedule(address(target), 0, payload, b.timelockPredecessor, b.timelockSalt, 48 hours);
        p.eta = uint64(lock.getTimestamp(p.operationId));
        _challengeAndSign(p, b);
    }

    function _challengeAndSign(Prepared memory p, Consent.BaseIntent memory b) private {
        uint64 epoch = lock.operationEpoch(p.operationId);
        p.evidence = bytes("synthetic-challenge-evidence-91sol");
        bytes32 commitment = sha256(
            abi.encodePacked(
                "synthetic-challenge-91sol", p.operationId, bytes8(epoch), bytes8(p.eta), Consent.baseDigest(b)
            )
        );
        Consent.Witness memory w;
        w.baseIntentDigest = Consent.baseDigest(b);
        w.operationId = p.operationId;
        w.queuedEta = p.eta;
        w.postEtaChallengeCommitment = commitment;
        w.issuedAt = p.eta;
        w.expiresAt = p.eta + 900;
        w.mode = b.mode;
        w.requiredRoleMask =
            b.mode == Consent.MODE_ROTATE_NORMAL ? Consent.ROLE_MASK_ROTATE_NORMAL : Consent.ROLE_MASK_RECOVER_LOST_KEY;
        p.witnessRaw = Consent.canonicalWitnessBytes(w);
        ChallengeTypes.ChallengeFacts memory c;
        c.schema = 2;
        c.networkContextDigest = NETWORK;
        c.operationId = p.operationId;
        c.operationEpoch = epoch;
        c.queuedEta = p.eta;
        c.baseIntentDigest = w.baseIntentDigest;
        c.challengeCommitment = commitment;
        c.issuedAt = w.issuedAt;
        c.expiresAt = w.expiresAt;
        c.challengeProfileDigest = CHALLENGE_PROFILE;
        c.finalityProfileDigest = FINALITY_PROFILE;
        c.evidenceDigest = sha256(p.evidence);
        challenges.set(c);
        if (b.mode == Consent.MODE_ROTATE_NORMAL) {
            p.oldSignature = _sign(OLD_KEY, _statement(p.witnessRaw, Consent.ROLE_OLD_KEY));
        } else {
            p.oldSignature = bytes("");
        }
        p.newSignature = _sign(NEW_KEY, _statement(p.witnessRaw, Consent.ROLE_NEW_KEY));
    }

    function _configure(uint64 version) private {
        Types.ProfileConfig memory p;
        p.policyRoot = ROOT;
        p.policyVersion = version;
        p.authorityEpoch = version;
        p.maxConsentTtl = 1000;
        p.maxPrincipalLifetime = 30 days;
        p.oldKeyGracePolicy = Types.GRACE_POLICY_ZERO;
        p.keyPolicy = Types.KEY_POLICY_REQUIRE_DISTINCT;
        p.relayerPolicy = Types.RELAYER_POLICY_PERMISSIONLESS;
        p.withdrawalPolicy = Types.WITHDRAWAL_POLICY_NO_PERSISTENT_FRAME;
        p.batchPolicy = Types.BATCH_POLICY_SINGLE_ONLY;
        p.requeuePolicy = Types.REQUEUE_POLICY_TIMELOCK_EPOCH;
        p.networkContextDigest = NETWORK;
        p.custodyAdapter = address(custody);
        p.custodyAdapterRuntimeCodeHash = address(custody).codehash;
        p.challengeProvider = address(challenges);
        p.challengeProviderRuntimeCodeHash = address(challenges).codehash;
        p.challengeProfileDigest = CHALLENGE_PROFILE;
        p.finalityProfileDigest = FINALITY_PROFILE;
        _govern(
            address(policy), abi.encodeCall(policy.configure, (p)), keccak256(abi.encode("configure-91sol", version))
        );
        require(
            policy.consentProfile().authorityConfigDigest == source.currentState().authorityConfigDigest,
            "stored policy digest matches real current producer"
        );
    }

    function _newRegistry() private returns (SeedableRegistry91Sol) {
        return new SeedableRegistry91Sol(
            address(lock),
            address(policy),
            address(verifier),
            address(source),
            address(custody),
            address(custody).codehash,
            address(challenges),
            address(challenges).codehash,
            NETWORK,
            bytes32(uint256(1)),
            bytes32(uint256(2))
        );
    }

    function _govern(address target, bytes memory data, bytes32 salt) private {
        lock.schedule(target, 0, data, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        lock.execute(target, 0, data, bytes32(0), salt);
    }

    function _relay(SeedableRegistry91Sol target, Prepared memory p) private {
        target.relayConsent(p.baseRaw, p.proposedRaw, p.witnessRaw, p.oldSignature, p.newSignature, p.evidence);
    }

    function _stateHash(SeedableRegistry91Sol target) private view returns (bytes32) {
        (
            bytes memory raw,
            bytes32 digest,
            uint64 generation,
            uint64 nonce,
            uint64 sequence,
            uint64 custodySequence,
            bytes32 custodyDigest
        ) = target.principalState(oldRecord.principalId);
        return keccak256(abi.encode(raw, digest, generation, nonce, sequence, custodySequence, custodyDigest));
    }

    function _assertUnchangedReady(SeedableRegistry91Sol target, Prepared memory p, bytes32 beforeState) private view {
        require(_stateHash(target) == beforeState, "all principal fields unchanged");
        require(
            lock.isOperationReady(p.operationId) && !lock.isOperationDone(p.operationId)
                && lock.getTimestamp(p.operationId) == p.eta,
            "queued operation remains ready"
        );
    }

    function _assertCommitted(SeedableRegistry91Sol target, Prepared memory p) private view {
        (
            bytes memory raw,
            bytes32 digest,
            uint64 generation,
            uint64 nonce,
            uint64 sequence,
            uint64 custodySequence,
            bytes32 custodyDigest
        ) = target.principalState(oldRecord.principalId);
        (bool ok, Principal.Record memory proposed) = Principal.tryDecode(p.proposedRaw);
        require(
            ok && keccak256(raw) == keccak256(p.proposedRaw) && digest == Principal.digest(proposed),
            "exact record/digest committed"
        );
        Types.ProducerState memory a = source.currentState();
        require(
            generation == 2 && nonce == 1 && sequence == a.authorityChangeSequence
                && custodySequence == a.custodyChangeSequence && custodyDigest == a.custodyConfigurationDigest,
            "atomic generation nonce and authority/custody anchors"
        );
        require(
            lock.isOperationDone(p.operationId) && !lock.isOperationReady(p.operationId), "singleton operation consumed"
        );
    }

    function _record(uint256 bodyScalar, uint64 generation) private returns (Principal.Record memory r) {
        Vm.Wallet memory body = vm.createWallet(bodyScalar);
        Vm.Wallet memory m2 = vm.createWallet(M2_KEY);
        r.nodeIdCommitment = bytes32(uint256(3));
        r.hostDomain = bytes32(uint256(1));
        r.serviceDomain = bytes32(uint256(2));
        r.principalId = Principal.principalIdFor(r.hostDomain, r.serviceDomain, r.nodeIdCommitment);
        r.m2SignerPublicKey = abi.encodePacked(bytes32(m2.publicKeyX), bytes32(m2.publicKeyY));
        r.m2SignerDid = string(abi.encodePacked("did:key:", _hex(r.m2SignerPublicKey)));
        r.certificateFingerprint = bytes32(uint256(4));
        r.bodyPublicKey = abi.encodePacked(bytes32(body.publicKeyX), bytes32(body.publicKeyY));
        r.audience = "gateway.testnet";
        r.method = "POST";
        r.path = "/heartbeat";
        Types.Profile memory p = policy.consentProfile();
        r.policyRoot = p.policyRoot;
        r.policyVersion = p.policyVersion;
        r.authorityEpoch = p.authorityEpoch;
        r.principalGeneration = generation;
        r.notBefore = uint64(block.timestamp);
        r.expiresAt = uint64(block.timestamp + 10 days);
    }

    function _statement(bytes memory raw, uint8 role) private pure returns (bytes32) {
        (bool ok, Consent.Witness memory w) = Consent.tryDecodeWitness(raw);
        require(ok, "canonical witness");
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
}
