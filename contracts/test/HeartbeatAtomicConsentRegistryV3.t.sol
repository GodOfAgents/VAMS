// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {OperationAwareVAMSTimelockControllerV3} from "../src/governance/OperationAwareVAMSTimelockControllerV3.sol";
import {OperationAwareVAMSTimelockControllerV2} from "../src/governance/OperationAwareVAMSTimelockControllerV2.sol";
import {HeartbeatConsentPolicyV3} from "../src/trust/HeartbeatConsentPolicyV3.sol";
import {HeartbeatAuthoritySourceV3} from "../src/trust/HeartbeatAuthoritySourceV3.sol";
import {HeartbeatAuthorityTypesV3 as Types} from "../src/trust/HeartbeatAuthorityTypesV3.sol";
import {HeartbeatConsentProfileV2 as ChallengeTypes} from "../src/trust/HeartbeatConsentProfileV2.sol";
import {HeartbeatConsentVerificationRouterV2} from "../src/trust/HeartbeatConsentVerificationRouterV2.sol";
import {HeartbeatAtomicConsentRegistryV3} from "../src/trust/HeartbeatAtomicConsentRegistryV3.sol";

/// @dev Synthetic custody/challenge adapters are local test fixtures only.
contract MutableCustodyAdapter91 {
    uint64 public sequence = 1;
    bytes32 public digest = bytes32(uint256(0x91));

    function currentCustodyState() external view returns (Types.CustodyState memory) {
        return Types.CustodyState(1, sequence, digest);
    }

    function set(uint64 nextSequence, bytes32 nextDigest) external {
        sequence = nextSequence;
        digest = nextDigest;
    }
}

contract SyntheticChallenge91 {
    function resolveChallenge(bytes calldata) external pure returns (ChallengeTypes.ChallengeFacts memory f) {
        f.schema = 2;
    }
}

contract SeededRegistry91 is HeartbeatAtomicConsentRegistryV3 {
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

    function seedForTest(bytes32 id, bytes calldata record, bytes32 digest, uint64 generation) external {
        Entry storage e = _entries[id];
        e.record = record;
        e.digest = digest;
        e.generation = generation;
    }

    function consumerDigestForTest() external view returns (bytes32) {
        Types.Profile memory p = _loadProfile();
        Types.ProducerState memory a = _readAuthority(p);
        return _consumerDigest(a.authorityConfigDigest);
    }
}

/// @dev Local getter/callback-denial wiring fixture for concrete classes; custody and challenge are synthetic.
contract HeartbeatAtomicConsentRegistryV3Tests is Test {
    OperationAwareVAMSTimelockControllerV3 private lock;
    HeartbeatConsentPolicyV3 private policy;
    HeartbeatAuthoritySourceV3 private source;
    HeartbeatConsentVerificationRouterV2 private router;
    MutableCustodyAdapter91 private custody;
    SyntheticChallenge91 private challenge;
    SeededRegistry91 private registry;
    bytes32 private constant NETWORK = bytes32(uint256(0x9101));

    function setUp() public {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        lock = new OperationAwareVAMSTimelockControllerV3(48 hours, proposers, executors, address(this));
        custody = new MutableCustodyAdapter91();
        challenge = new SyntheticChallenge91();
        router = new HeartbeatConsentVerificationRouterV2();
        policy = new HeartbeatConsentPolicyV3(address(lock), keccak256(type(HeartbeatAuthoritySourceV3).runtimeCode));
        source = new HeartbeatAuthoritySourceV3(
            address(lock), address(policy), address(custody), address(custody).codehash, block.chainid, NETWORK
        );
        _govern(address(policy), abi.encodeCall(policy.bindAuthoritySource, (address(source))), keccak256("bind"));
        Types.ProfileConfig memory p;
        p.policyRoot = bytes32(uint256(0x9102));
        p.policyVersion = 1;
        p.authorityEpoch = 1;
        p.maxConsentTtl = 7 days;
        p.maxPrincipalLifetime = 365 days;
        p.oldKeyGracePolicy = Types.GRACE_POLICY_ZERO;
        p.keyPolicy = Types.KEY_POLICY_ALLOW_SAME;
        p.relayerPolicy = Types.RELAYER_POLICY_PERMISSIONLESS;
        p.withdrawalPolicy = Types.WITHDRAWAL_POLICY_NO_PERSISTENT_FRAME;
        p.batchPolicy = Types.BATCH_POLICY_SINGLE_ONLY;
        p.requeuePolicy = Types.REQUEUE_POLICY_TIMELOCK_EPOCH;
        p.networkContextDigest = NETWORK;
        p.custodyAdapter = address(custody);
        p.custodyAdapterRuntimeCodeHash = address(custody).codehash;
        p.challengeProvider = address(challenge);
        p.challengeProviderRuntimeCodeHash = address(challenge).codehash;
        p.challengeProfileDigest = bytes32(uint256(0x9103));
        p.finalityProfileDigest = bytes32(uint256(0x9104));
        _govern(address(policy), abi.encodeCall(policy.configure, (p)), keccak256("configure"));
        registry = new SeededRegistry91(
            address(lock),
            address(policy),
            address(router),
            address(source),
            address(custody),
            address(custody).codehash,
            address(challenge),
            address(challenge).codehash,
            NETWORK,
            bytes32(uint256(1)),
            bytes32(uint256(2))
        );
    }

    function testPinnedV3ClassesFeedConsumerGetterFixture() public view {
        Types.ProducerState memory state = source.currentState();
        require(
            state.source == address(source) && state.policy == address(policy) && state.timelock == address(lock),
            "producer links"
        );
        require(
            registry.authoritySource() == address(source) && registry.verifier() == address(router), "consumer pins"
        );
        require(registry.deploymentChainId() == block.chainid, "chain bound");
    }

    function testProducerDigestChangesWhenCustodySequenceAndConfigChange() public {
        Types.ProducerState memory beforeState = source.currentState();
        custody.set(2, bytes32(uint256(0x92)));
        Types.ProducerState memory afterState = source.currentState();
        require(
            afterState.custodyChangeSequence == 2
                && afterState.custodyConfigurationDigest != beforeState.custodyConfigurationDigest,
            "custody drift observed"
        );
        require(
            afterState.authorityConfigDigest != beforeState.authorityConfigDigest, "authority digest tracks custody"
        );
    }

    function testDirectCallbackRejectsWithoutFrame() public {
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.WrongOperationContext.selector);
        registry.applyConsent(bytes(""), bytes(""));
    }

    function testTimelockCallbackWithoutRelayFrameRevertsAndKeepsOperationQueued() public {
        bytes memory payload = abi.encodeCall(registry.applyConsent, (bytes(""), bytes("")));
        bytes32 salt = keccak256("V3-no-frame");
        bytes32 id = lock.hashOperation(address(registry), 0, payload, bytes32(0), salt);
        lock.schedule(address(registry), 0, payload, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        vm.expectRevert();
        lock.execute(address(registry), 0, payload, bytes32(0), salt);
        require(lock.isOperationReady(id), "revert must rollback execution");
        (, bytes32 digest, uint64 generation, uint64 nonce,,,) = registry.principalState(bytes32(uint256(0x91)));
        require(digest == bytes32(0) && generation == 0 && nonce == 0, "no mutation");
    }

    function testV2TimelockCannotInstantiateV3Consumer() public {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        OperationAwareVAMSTimelockControllerV2 oldLock =
            new OperationAwareVAMSTimelockControllerV2(48 hours, proposers, executors, address(this));
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.InvalidConfiguration.selector);
        new SeededRegistry91(
            address(oldLock),
            address(policy),
            address(router),
            address(source),
            address(custody),
            address(custody).codehash,
            address(challenge),
            address(challenge).codehash,
            NETWORK,
            bytes32(uint256(1)),
            bytes32(uint256(2))
        );
    }

    function testCurrentProfileDigestRejectsCustodyDrift() public {
        custody.set(2, bytes32(uint256(0x92)));
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.AuthorityUnavailable.selector);
        registry.consumerDigestForTest();
    }

    function testConsumerDigestIncludesExactRegistryInstance() public {
        SeededRegistry91 second = new SeededRegistry91(
            address(lock),
            address(policy),
            address(router),
            address(source),
            address(custody),
            address(custody).codehash,
            address(challenge),
            address(challenge).codehash,
            NETWORK,
            bytes32(uint256(1)),
            bytes32(uint256(2))
        );
        require(registry.consumerDigestForTest() != second.consumerDigestForTest(), "digest binds registry identity");
    }

    function testBatchCallbackCannotEnterMutation() public {
        address[] memory targets = new address[](1);
        uint256[] memory values = new uint256[](1);
        bytes[] memory calls = new bytes[](1);
        targets[0] = address(registry);
        calls[0] = abi.encodeCall(registry.applyConsent, (bytes(""), bytes("")));
        bytes32 salt = keccak256("V3-batch-no-frame");
        lock.scheduleBatch(targets, values, calls, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        vm.expectRevert();
        lock.executeBatch(targets, values, calls, bytes32(0), salt);
    }

    function testWrongSourceClassCannotInstantiateV3Consumer() public {
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.InvalidConfiguration.selector);
        new SeededRegistry91(
            address(lock),
            address(policy),
            address(router),
            address(policy),
            address(custody),
            address(custody).codehash,
            address(challenge),
            address(challenge).codehash,
            NETWORK,
            bytes32(uint256(1)),
            bytes32(uint256(2))
        );
    }

    function testTimelockAuthorityABARestoresMembershipButInvalidatesOldProfile() public {
        uint64 initial = lock.authorityChangeSequence();
        bytes32 initialCommitment = lock.authorityConfigCommitment();
        address member = address(0x91BEEF);
        lock.grantRole(lock.PROPOSER_ROLE(), member);
        require(
            lock.hasRole(lock.PROPOSER_ROLE(), member) && lock.authorityChangeSequence() == initial + 1, "grant tracked"
        );
        lock.revokeRole(lock.PROPOSER_ROLE(), member);
        require(
            !lock.hasRole(lock.PROPOSER_ROLE(), member) && lock.authorityChangeSequence() == initial + 2
                && lock.authorityConfigCommitment() != initialCommitment,
            "A-B-A remains distinguishable"
        );
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.AuthorityUnavailable.selector);
        registry.consumerDigestForTest();
    }

    function testConstructorRejectsChallengeThatDiffersFromConfiguredProfile() public {
        vm.expectRevert(HeartbeatAtomicConsentRegistryV3.InvalidConfiguration.selector);
        new SeededRegistry91(
            address(lock),
            address(policy),
            address(router),
            address(source),
            address(custody),
            address(custody).codehash,
            address(custody),
            address(custody).codehash,
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
}
