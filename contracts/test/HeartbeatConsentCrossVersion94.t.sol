// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Vm} from "forge-std/Vm.sol";
import {SeedableHeartbeatRegistryV2, SyntheticAuthoritySourceV2, SyntheticChallengeProviderV2}
    from "./HeartbeatAtomicConsentRegistryV2Integration.t.sol";
import {SeedableRegistry91Sol, SyntheticCustody91Sol, SyntheticChallenge91Sol}
    from "./HeartbeatAtomicConsentRegistryV3Integration.t.sol";
import {OperationAwareVAMSTimelockControllerV2 as TL2} from "../src/governance/OperationAwareVAMSTimelockControllerV2.sol";
import {OperationAwareVAMSTimelockControllerV3 as TL3} from "../src/governance/OperationAwareVAMSTimelockControllerV3.sol";
import {HeartbeatConsentPolicyV2 as Policy2} from "../src/trust/HeartbeatConsentPolicyV2.sol";
import {HeartbeatConsentPolicyV3 as Policy3} from "../src/trust/HeartbeatConsentPolicyV3.sol";
import {HeartbeatAuthoritySourceV3 as Source3} from "../src/trust/HeartbeatAuthoritySourceV3.sol";
import {HeartbeatAtomicConsentRegistryV2 as Registry2} from "../src/trust/HeartbeatAtomicConsentRegistryV2.sol";
import {HeartbeatAtomicConsentRegistryV3 as Registry3} from "../src/trust/HeartbeatAtomicConsentRegistryV3.sol";
import {HeartbeatConsentVerificationRouterV2 as Router} from "../src/trust/HeartbeatConsentVerificationRouterV2.sol";
import {HeartbeatConsentProfileV2 as Types2} from "../src/trust/HeartbeatConsentProfileV2.sol";
import {HeartbeatAuthorityTypesV3 as Types3} from "../src/trust/HeartbeatAuthorityTypesV3.sol";
import {HeartbeatConsentV2 as Consent} from "../src/trust/HeartbeatConsentV2.sol";
import {HeartbeatPrincipalV1 as Principal} from "../src/trust/HeartbeatPrincipalV1.sol";

/// @dev Source-only prepared local tests. Existing fixture classes are imported unchanged.
///      Custody/challenge/V2 authority/migration are synthetic; verifier and both consumers are real.
contract HeartbeatConsentCrossVersion94Tests is Test {
    uint256 private constant OLD_KEY = 11;
    uint256 private constant NEW_KEY = 12;
    uint256 private constant M2_KEY = 13;
    uint256 private constant N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
    string private constant SIG_DOMAIN = "VAMS:GATEWAY:HEARTBEAT-CONSENT-SIGNATURE:v2";
    bytes32 private constant NETWORK = keccak256("synthetic-network-crossversion94");
    bytes32 private constant ROOT2 = keccak256("synthetic-policy-v2-crossversion94");
    bytes32 private constant ROOT3 = keccak256("synthetic-policy-v3-crossversion94");
    bytes32 private constant CONFIG2 = keccak256("synthetic-v2-config-crossversion94");
    bytes32 private constant CHALLENGE = keccak256("synthetic-challenge-crossversion94");
    bytes32 private constant FINALITY = keccak256("synthetic-finality-crossversion94");

    Router private router;
    TL2 private lock2;
    Policy2 private policy2;
    SeedableHeartbeatRegistryV2 private registry2;
    SyntheticAuthoritySourceV2 private authority2;
    SyntheticChallengeProviderV2 private challenge2;
    TL3 private lock3;
    Policy3 private policy3;
    Source3 private source3;
    SeedableRegistry91Sol private registry3;
    SyntheticCustody91Sol private custody3;
    SyntheticChallenge91Sol private challenge3;
    bytes private oldRaw2;
    bytes private oldRaw3;
    bytes32 private principalId;

    struct Target {
        bool v3;
        address registry;
        address timelock;
        bytes oldRaw;
        bytes32 nativeDigest;
        bytes32 configDigest;
        uint64 sequence;
        bytes32 root;
        uint64 version;
        uint64 epoch;
    }
    struct Prepared {
        Target target;
        Consent.BaseIntent base;
        bytes baseRaw;
        bytes proposedRaw;
        bytes witnessRaw;
        bytes oldSignature;
        bytes newSignature;
        bytes evidence;
        bytes32 operationId;
        uint64 eta;
        uint64 operationEpoch;
        Types2.ChallengeFacts facts;
    }

    function setUp() public {
        vm.warp(1_800_000_000);
        router = new Router();
        _setupV2();
        _setupV3();
        // Seed both records only after every governance setup warp and role/configuration update.
        Principal.Record memory old2 = _record(false, OLD_KEY, 1);
        Principal.Record memory old3 = _record(true, OLD_KEY, 1);
        principalId = old2.principalId;
        require(old3.principalId == principalId, "same canonical principal ID");
        oldRaw2 = Principal.canonicalBytes(old2);
        oldRaw3 = Principal.canonicalBytes(old3);
        registry2.seed(principalId, oldRaw2, 0, 1);
        registry3.seedCanonicalForTest(oldRaw3);
    }

    function testV2ActualSnapshotDigestCommitsOnNativeV2Consumer() public {
        Prepared memory p = _prepare(false, false);
        vm.warp(p.eta);
        _assertReadyAndGenuine(p);
        require(p.base.authoritySourceDigest == Types2.authorityDigest(authority2.currentSnapshot()), "actual V2 snapshot digest");
        _relay(p);
        _assertCommitted(p);
    }

    function testV3ActualConsumerDigestCommitsOnNativeV3Consumer() public {
        Prepared memory p = _prepare(true, false);
        vm.warp(p.eta);
        _assertReadyAndGenuine(p);
        require(p.base.authoritySourceDigest == _v3ConsumerDigest(), "actual V3 accepted consumer digest");
        _relay(p);
        _assertCommitted(p);
    }

    function testV3ConsumerRejectsActualV2SnapshotDigestWithNativeTargetProof() public {
        Prepared memory p = _prepare(true, true);
        require(p.base.authoritySourceDigest == Types2.authorityDigest(authority2.currentSnapshot()), "foreign value from actual V2 snapshot");
        vm.warp(p.eta);
        _assertReadyAndGenuine(p);
        bytes32 beforeState = keccak256(_entryResponse(true));
        vm.expectRevert(Registry3.AuthorityUnavailable.selector);
        _relay(p);
        _assertRejectedUnchanged(p, beforeState);
    }

    function testV2ConsumerRejectsActualV3ConsumerDigestWithNativeTargetProof() public {
        Prepared memory p = _prepare(false, true);
        require(p.base.authoritySourceDigest == _v3ConsumerDigest(), "foreign value from actual V3 producer and consumer instance");
        vm.warp(p.eta);
        _assertReadyAndGenuine(p);
        bytes32 beforeState = keccak256(_entryResponse(false));
        vm.expectRevert(Registry2.AuthorityUnavailable.selector);
        _relay(p);
        _assertRejectedUnchanged(p, beforeState);
    }

    function _setupV2() private {
        address[] memory members = new address[](1);
        members[0] = address(this);
        lock2 = new TL2(48 hours, members, members, address(this));
        policy2 = new Policy2(address(lock2));
        registry2 = new SeedableHeartbeatRegistryV2(address(lock2), address(policy2), address(router), bytes32(uint256(1)), bytes32(uint256(2)));
        authority2 = new SyntheticAuthoritySourceV2();
        challenge2 = new SyntheticChallengeProviderV2();
        Types2.AuthoritySnapshot memory a;
        a.sourceSchema = 2; a.scheme = 1; a.registrySchema = 2; a.chainId = block.chainid;
        a.networkContextDigest = NETWORK; a.registry = address(registry2); a.registryRuntimeCodeHash = address(registry2).codehash;
        a.policy = address(policy2); a.policyRuntimeCodeHash = address(policy2).codehash;
        a.timelock = address(lock2); a.timelockRuntimeCodeHash = address(lock2).codehash;
        a.authorityConfigDigest = CONFIG2; a.authorityChangeSequence = 1;
        a.policyRoot = ROOT2; a.policyVersion = 1; a.authorityEpoch = 1;
        authority2.set(a);
        Types2.Profile memory p;
        p.configured = true; p.schema = 2; p.policyRoot = ROOT2; p.policyVersion = 1; p.authorityEpoch = 1;
        p.maxConsentTtl = 1000; p.maxPrincipalLifetime = 30 days;
        p.oldKeyGracePolicy = Types2.GRACE_POLICY_ZERO; p.keyPolicy = Types2.KEY_POLICY_REQUIRE_DISTINCT;
        p.relayerPolicy = Types2.RELAYER_POLICY_PERMISSIONLESS;
        p.withdrawalPolicy = Types2.WITHDRAWAL_POLICY_NO_PERSISTENT_CONSENT_FRAME;
        p.batchPolicy = Types2.BATCH_POLICY_SINGLE_ONLY; p.requeuePolicy = Types2.REQUEUE_POLICY_TIMELOCK_EPOCH;
        p.authoritySource = address(authority2); p.authoritySourceRuntimeCodeHash = address(authority2).codehash;
        p.challengeProvider = address(challenge2); p.challengeProviderRuntimeCodeHash = address(challenge2).codehash;
        p.authorityConfigDigest = CONFIG2; p.networkContextDigest = NETWORK;
        p.challengeProfileDigest = CHALLENGE; p.finalityProfileDigest = FINALITY;
        _govern(address(lock2), address(policy2), abi.encodeCall(policy2.configure, (ROOT2, uint64(1), uint64(1), p)), keccak256("configure-v2-94"));
        _govern(address(lock2), address(lock2), abi.encodeCall(lock2.grantRole, (lock2.EXECUTOR_ROLE(), address(registry2))), keccak256("executor-v2-94"));
    }

    function _setupV3() private {
        address[] memory members = new address[](1);
        members[0] = address(this);
        lock3 = new TL3(48 hours, members, members, address(this));
        custody3 = new SyntheticCustody91Sol();
        challenge3 = new SyntheticChallenge91Sol();
        policy3 = new Policy3(address(lock3), keccak256(type(Source3).runtimeCode));
        source3 = new Source3(address(lock3), address(policy3), address(custody3), address(custody3).codehash, block.chainid, NETWORK);
        _govern(address(lock3), address(policy3), abi.encodeCall(policy3.bindAuthoritySource, (address(source3))), keccak256("bind-v3-94"));
        _configureV3(1);
        registry3 = new SeedableRegistry91Sol(address(lock3), address(policy3), address(router), address(source3), address(custody3),
            address(custody3).codehash, address(challenge3), address(challenge3).codehash, NETWORK, bytes32(uint256(1)), bytes32(uint256(2)));
        _govern(address(lock3), address(lock3), abi.encodeCall(lock3.grantRole, (lock3.EXECUTOR_ROLE(), address(registry3))), keccak256("executor-v3-94"));
        _configureV3(2);
    }

    function _configureV3(uint64 version) private {
        Types3.ProfileConfig memory p;
        p.policyRoot = ROOT3; p.policyVersion = version; p.authorityEpoch = version;
        p.maxConsentTtl = 1000; p.maxPrincipalLifetime = 30 days;
        p.oldKeyGracePolicy = Types3.GRACE_POLICY_ZERO; p.keyPolicy = Types3.KEY_POLICY_REQUIRE_DISTINCT;
        p.relayerPolicy = Types3.RELAYER_POLICY_PERMISSIONLESS;
        p.withdrawalPolicy = Types3.WITHDRAWAL_POLICY_NO_PERSISTENT_FRAME;
        p.batchPolicy = Types3.BATCH_POLICY_SINGLE_ONLY; p.requeuePolicy = Types3.REQUEUE_POLICY_TIMELOCK_EPOCH;
        p.networkContextDigest = NETWORK;
        p.custodyAdapter = address(custody3); p.custodyAdapterRuntimeCodeHash = address(custody3).codehash;
        p.challengeProvider = address(challenge3); p.challengeProviderRuntimeCodeHash = address(challenge3).codehash;
        p.challengeProfileDigest = CHALLENGE; p.finalityProfileDigest = FINALITY;
        _govern(address(lock3), address(policy3), abi.encodeCall(policy3.configure, (p)), keccak256(abi.encode("configure-v3-94", version)));
        require(policy3.consentProfile().authorityConfigDigest == source3.currentState().authorityConfigDigest, "fresh V3 policy");
    }

    function _target(bool v3) private view returns (Target memory t) {
        t.v3 = v3;
        if (v3) {
            Types3.ProducerState memory a = source3.currentState();
            Types3.Profile memory p = policy3.consentProfile();
            require(p.authorityConfigDigest == a.authorityConfigDigest && a.authorityConfigDigest == Types3.authorityConfigDigest(a), "V3 current digest recomputes");
            t.registry = address(registry3); t.timelock = address(lock3); t.oldRaw = oldRaw3;
            t.nativeDigest = _v3ConsumerDigest(); t.configDigest = a.authorityConfigDigest; t.sequence = a.authorityChangeSequence;
            t.root = p.policyRoot; t.version = p.policyVersion; t.epoch = p.authorityEpoch;
        } else {
            Types2.AuthoritySnapshot memory a = authority2.currentSnapshot();
            Types2.Profile memory p = policy2.consentProfile();
            require(a.registry == address(registry2) && a.registryRuntimeCodeHash == address(registry2).codehash &&
                a.timelock == address(lock2) && a.timelockRuntimeCodeHash == address(lock2).codehash &&
                a.policy == address(policy2) && a.policyRuntimeCodeHash == address(policy2).codehash &&
                a.authorityConfigDigest == p.authorityConfigDigest && !a.isProxy, "V2 snapshot describes real local stack");
            t.registry = address(registry2); t.timelock = address(lock2); t.oldRaw = oldRaw2;
            t.nativeDigest = Types2.authorityDigest(a); t.configDigest = a.authorityConfigDigest; t.sequence = a.authorityChangeSequence;
            t.root = p.policyRoot; t.version = p.policyVersion; t.epoch = p.authorityEpoch;
        }
    }

    function _v3ConsumerDigest() private view returns (bytes32) {
        return sha256(abi.encode(bytes32("VAMS:CONSUMER:AUTHORITY:V3"), block.chainid, address(registry3),
            address(registry3).codehash, source3.currentState().authorityConfigDigest));
    }

    function _prepare(bool v3, bool foreign) private returns (Prepared memory p) {
        p.target = _target(v3);
        Principal.Record memory proposed = _record(v3, NEW_KEY, 2);
        proposed.notBefore = uint64(block.timestamp + 48 hours);
        proposed.expiresAt = proposed.notBefore + 50000;
        p.proposedRaw = Principal.canonicalBytes(proposed);
        p.base = _nativeBase(p.target, p.proposedRaw);
        if (foreign) {
            bytes32 nativeBaseHash = keccak256(abi.encode(p.base));
            bytes32 foreignDigest = _target(!v3).nativeDigest;
            require(foreignDigest != p.target.nativeDigest, "distinct actual authority domains");
            p.base.authoritySourceDigest = foreignDigest;
            // Restore the one substituted field to prove every other base member is native.
            p.base.authoritySourceDigest = p.target.nativeDigest;
            require(keccak256(abi.encode(p.base)) == nativeBaseHash, "only authoritySourceDigest substituted");
            p.base.authoritySourceDigest = foreignDigest;
        }
        p.baseRaw = Consent.canonicalBaseBytes(p.base);
        _queue(p);
        _challengeAndSign(p);
    }

    function _nativeBase(Target memory t, bytes memory proposedRaw) private view returns (Consent.BaseIntent memory b) {
        b.mode = Consent.MODE_ROTATE_NORMAL; b.sourceScheme = 1;
        b.authoritySourceDigest = t.nativeDigest; b.timelockAddress = t.timelock; b.timelockCodeHash = t.timelock.codehash;
        b.authorityConfigDigest = t.configDigest; b.authorityChangeSequence = t.sequence;
        b.policyRoot = t.root; b.policyVersion = t.version; b.authorityEpoch = t.epoch;
        b.principalId = principalId; b.expectedRecordDigest = _recordDigest(t.oldRaw);
        b.proposedRecordDigest = _recordDigest(proposedRaw); b.expectedGeneration = 1; b.proposedGeneration = 2; b.consentNonce = 0;
        b.timelockSalt = keccak256(abi.encode("native-target-crossversion94", t.registry));
    }

    function _queue(Prepared memory p) private {
        // TL3 inherits this exact singleton operation ABI. Its actual class/address stay TL3.
        TL2 targetLock = TL2(payable(p.target.timelock));
        bytes memory payload = abi.encodeWithSelector(Registry2.applyConsent.selector, p.baseRaw, p.proposedRaw);
        p.operationId = targetLock.hashOperation(p.target.registry, 0, payload, p.base.timelockPredecessor, p.base.timelockSalt);
        targetLock.schedule(p.target.registry, 0, payload, p.base.timelockPredecessor, p.base.timelockSalt, 48 hours);
        p.eta = uint64(targetLock.getTimestamp(p.operationId));
        p.operationEpoch = targetLock.operationEpoch(p.operationId);
    }

    function _challengeAndSign(Prepared memory p) private {
        p.evidence = abi.encodePacked("synthetic-crossversion94", p.operationId);
        Consent.Witness memory w;
        w.baseIntentDigest = Consent.baseDigest(p.base); w.operationId = p.operationId; w.queuedEta = p.eta;
        w.postEtaChallengeCommitment = sha256(abi.encode("synthetic-challenge94", p.operationId, p.operationEpoch, p.eta, w.baseIntentDigest));
        w.issuedAt = p.eta; w.expiresAt = p.eta + 900; w.mode = Consent.MODE_ROTATE_NORMAL;
        w.requiredRoleMask = Consent.ROLE_MASK_ROTATE_NORMAL;
        p.witnessRaw = Consent.canonicalWitnessBytes(w);
        p.facts.schema = 2; p.facts.networkContextDigest = NETWORK; p.facts.operationId = p.operationId;
        p.facts.operationEpoch = p.operationEpoch; p.facts.queuedEta = p.eta; p.facts.baseIntentDigest = w.baseIntentDigest;
        p.facts.challengeCommitment = w.postEtaChallengeCommitment; p.facts.issuedAt = w.issuedAt; p.facts.expiresAt = w.expiresAt;
        p.facts.challengeProfileDigest = CHALLENGE; p.facts.finalityProfileDigest = FINALITY; p.facts.evidenceDigest = sha256(p.evidence);
        if (p.target.v3) challenge3.set(p.facts); else challenge2.set(p.facts);
        p.oldSignature = _sign(OLD_KEY, _statement(p.witnessRaw, Consent.ROLE_OLD_KEY));
        p.newSignature = _sign(NEW_KEY, _statement(p.witnessRaw, Consent.ROLE_NEW_KEY));
    }

    function _assertReadyAndGenuine(Prepared memory p) private view {
        require(router.verifyNormalPair(p.baseRaw,p.witnessRaw,p.target.oldRaw,p.proposedRaw,p.oldSignature,p.newSignature), "real router accepts exact OLD and NEW signatures");
        Target memory current = _target(p.target.v3);
        require(p.base.timelockAddress == current.timelock && p.base.timelockCodeHash == current.timelock.codehash &&
            p.base.authorityConfigDigest == current.configDigest && p.base.authorityChangeSequence == current.sequence &&
            p.base.policyRoot == current.root && p.base.policyVersion == current.version && p.base.authorityEpoch == current.epoch,
            "native target timelock policy and current config");
        TL2 targetLock = TL2(payable(current.timelock));
        bytes memory payload = abi.encodeWithSelector(Registry2.applyConsent.selector, p.baseRaw, p.proposedRaw);
        require(targetLock.hasRole(targetLock.EXECUTOR_ROLE(), current.registry) && targetLock.isOperationReady(p.operationId) &&
            targetLock.getTimestamp(p.operationId) == p.eta && targetLock.operationEpoch(p.operationId) == p.operationEpoch &&
            targetLock.hashOperation(current.registry,0,payload,p.base.timelockPredecessor,p.base.timelockSalt) == p.operationId &&
            block.timestamp == p.eta, "native singleton operation ready at exact ETA with executor role");
        Types2.ChallengeFacts memory observed = p.target.v3 ? challenge3.resolveChallenge(p.evidence) : challenge2.resolveChallenge(p.evidence);
        require(keccak256(abi.encode(observed)) == keccak256(abi.encode(p.facts)), "exact target queue challenge finality and evidence facts");
        _assertNativeClasses(p.target.v3);
        _assertRecordWindowAndCas(p);
    }

    function _assertRecordWindowAndCas(Prepared memory p) private view {
        (bool ok,Router.PrincipalView memory proposed,) = router.decodePrincipal(p.proposedRaw);
        require(ok && proposed.principalId == principalId && proposed.principalGeneration == 2 &&
            proposed.notBefore <= block.timestamp && proposed.expiresAt > block.timestamp &&
            proposed.expiresAt - proposed.notBefore <= 30 days, "native valid proposed record window");
        require(p.facts.issuedAt == p.eta && p.facts.expiresAt > block.timestamp &&
            p.facts.expiresAt - p.facts.issuedAt <= 1000, "live target witness challenge TTL");
        require(p.base.expectedGeneration == 1 && p.base.proposedGeneration == 2 && p.base.consentNonce == 0 &&
            p.base.expectedRecordDigest == _recordDigest(p.target.oldRaw), "native expected generation nonce and record digest");
        require(keccak256(_entryResponse(p.target.v3)) == keccak256(_expectedEntry(p.target,p.target.oldRaw,1,0)),
            "actual target entry satisfies every CAS and anchor precondition");
    }

    function _assertNativeClasses(bool v3) private view {
        require(address(router).codehash == keccak256(type(Router).runtimeCode), "actual shared RouterV2 class");
        if (v3) {
            require(address(lock3).codehash == keccak256(type(TL3).runtimeCode) &&
                address(policy3).codehash == keccak256(type(Policy3).runtimeCode) &&
                address(source3).codehash == keccak256(type(Source3).runtimeCode), "actual native V3 dependency classes");
        } else {
            require(address(lock2).codehash == keccak256(type(TL2).runtimeCode) &&
                address(policy2).codehash == keccak256(type(Policy2).runtimeCode), "actual native V2 dependency classes");
        }
    }

    function _relay(Prepared memory p) private {
        if (p.target.v3) registry3.relayConsent(p.baseRaw,p.proposedRaw,p.witnessRaw,p.oldSignature,p.newSignature,p.evidence);
        else registry2.relayConsent(p.baseRaw,p.proposedRaw,p.witnessRaw,p.oldSignature,p.newSignature,p.evidence);
    }

    function _entryResponse(bool v3) private view returns (bytes memory response) {
        address target = v3 ? address(registry3) : address(registry2);
        bool ok;
        (ok, response) = target.staticcall(abi.encodeWithSelector(Registry2.principalState.selector, principalId));
        require(ok, "actual consumer principalState response");
    }

    function _assertRejectedUnchanged(Prepared memory p, bytes32 beforeState) private view {
        require(keccak256(_entryResponse(p.target.v3)) == beforeState, "all five V2 or seven V3 entry fields unchanged");
        TL2 targetLock = TL2(payable(p.target.timelock));
        require(targetLock.isOperationReady(p.operationId) && !targetLock.isOperationDone(p.operationId) &&
            targetLock.getTimestamp(p.operationId) == p.eta && targetLock.operationEpoch(p.operationId) == p.operationEpoch,
            "rejected domain leaves queue ETA epoch and status unchanged");
    }

    function _assertCommitted(Prepared memory p) private view {
        require(keccak256(_entryResponse(p.target.v3)) == keccak256(_expectedEntry(p.target,p.proposedRaw,2,1)),
            "exact canonical record generation nonce and authority anchors committed");
        TL2 targetLock = TL2(payable(p.target.timelock));
        require(targetLock.isOperationDone(p.operationId) && !targetLock.isOperationReady(p.operationId), "native positive consumes exact singleton operation");
    }

    function _expectedEntry(Target memory t, bytes memory record, uint64 generation, uint64 nonce) private view returns (bytes memory) {
        bytes32 digest = _recordDigest(record);
        bytes memory expected;
        if (t.v3) {
            Types3.ProducerState memory a = source3.currentState();
            expected = abi.encode(record,digest,generation,nonce,a.authorityChangeSequence,a.custodyChangeSequence,a.custodyConfigurationDigest);
        } else expected = abi.encode(record,digest,generation,nonce,t.sequence);
        return expected;
    }

    function _govern(address lockAddress, address target, bytes memory payload, bytes32 salt) private {
        TL2 targetLock = TL2(payable(lockAddress));
        targetLock.schedule(target,0,payload,bytes32(0),salt,48 hours);
        vm.warp(block.timestamp + 48 hours);
        targetLock.execute(target,0,payload,bytes32(0),salt);
    }

    function _record(bool v3, uint256 scalar, uint64 generation) private returns (Principal.Record memory r) {
        Vm.Wallet memory body = vm.createWallet(scalar);
        Vm.Wallet memory m2 = vm.createWallet(M2_KEY);
        r.nodeIdCommitment = bytes32(uint256(3)); r.hostDomain = bytes32(uint256(1)); r.serviceDomain = bytes32(uint256(2));
        r.principalId = Principal.principalIdFor(r.hostDomain,r.serviceDomain,r.nodeIdCommitment);
        r.m2SignerPublicKey = abi.encodePacked(bytes32(m2.publicKeyX),bytes32(m2.publicKeyY));
        r.m2SignerDid = string(abi.encodePacked("did:key:",_hex(r.m2SignerPublicKey)));
        r.certificateFingerprint = bytes32(uint256(4)); r.bodyPublicKey = abi.encodePacked(bytes32(body.publicKeyX),bytes32(body.publicKeyY));
        r.audience = "gateway.testnet"; r.method = "POST"; r.path = "/heartbeat";
        if (v3) {
            Types3.Profile memory p = policy3.consentProfile();
            r.policyRoot = p.policyRoot; r.policyVersion = p.policyVersion; r.authorityEpoch = p.authorityEpoch;
        } else {
            Types2.Profile memory p = policy2.consentProfile();
            r.policyRoot = p.policyRoot; r.policyVersion = p.policyVersion; r.authorityEpoch = p.authorityEpoch;
        }
        r.principalGeneration = generation; r.notBefore = uint64(block.timestamp); r.expiresAt = uint64(block.timestamp + 10 days);
    }

    function _recordDigest(bytes memory raw) private view returns (bytes32 digest) {
        (bool ok,, bytes32 decodedDigest) = router.decodePrincipal(raw);
        require(ok, "canonical PrincipalV1 bytes");
        return decodedDigest;
    }

    function _statement(bytes memory raw, uint8 role) private pure returns (bytes32) {
        (bool ok,Consent.Witness memory w) = Consent.tryDecodeWitness(raw);
        require(ok, "canonical ConsentV2 witness");
        return sha256(abi.encodePacked(SIG_DOMAIN,hex"00",bytes1(uint8(1)),bytes1(role),Consent.witnessDigest(w)));
    }

    function _sign(uint256 scalar, bytes32 digest) private returns (bytes memory) {
        (,bytes32 r,bytes32 s) = vm.sign(scalar,digest);
        return abi.encodePacked(r,bytes32(uint256(s) > N / 2 ? N - uint256(s) : uint256(s)));
    }

    function _hex(bytes memory raw) private pure returns (bytes memory out) {
        bytes memory alphabet = bytes("0123456789abcdef");
        out = new bytes(raw.length * 2);
        for (uint256 i; i < raw.length; ++i) {
            out[i*2] = alphabet[uint8(raw[i]) >> 4];
            out[i*2+1] = alphabet[uint8(raw[i]) & 15];
        }
    }
}
