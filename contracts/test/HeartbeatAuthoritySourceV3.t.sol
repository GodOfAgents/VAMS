// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {OperationAwareVAMSTimelockControllerV3} from "../src/governance/OperationAwareVAMSTimelockControllerV3.sol";
import {OperationAwareVAMSTimelockControllerV2} from "../src/governance/OperationAwareVAMSTimelockControllerV2.sol";
import {HeartbeatConsentPolicyV3} from "../src/trust/HeartbeatConsentPolicyV3.sol";
import {HeartbeatAuthoritySourceV3} from "../src/trust/HeartbeatAuthoritySourceV3.sol";
import {
    HeartbeatAuthorityTypesV3 as Types,
    IHeartbeatCustodyAuthorityAdapterV1
} from "../src/trust/HeartbeatAuthorityTypesV3.sol";

/// @dev Synthetic test fixture only. It is not a custody/Safe adapter or production evidence.
contract SyntheticCustodyAdapterV1 is IHeartbeatCustodyAuthorityAdapterV1 {
    Types.CustodyState private _state = Types.CustodyState({
        schema: Types.CUSTODY_SCHEMA,
        changeSequence: 1,
        configurationDigest: keccak256("test-only custody state")
    });
    bool public shouldRevert;

    function setState(uint16 schema, uint64 sequence, bytes32 digest) external {
        _state = Types.CustodyState(schema, sequence, digest);
    }

    function setRevert(bool value) external { shouldRevert = value; }

    function currentCustodyState() external view returns (Types.CustodyState memory) {
        require(!shouldRevert, "test adapter unavailable");
        return _state;
    }
}

/// @dev Wrong-interface-class fixture; bytecode identity must be rejected by SourceV3.
contract FakePolicyV3 {
    function governance() external pure returns (address) { return address(1); }
}

contract FakeAuthoritySourceV3 {
    function computeAuthorityConfigDigest() external pure returns (bytes32) { return bytes32(uint256(1)); }
}

/// @dev Runtime has the expected selector but deliberately returns malformed custody bytes.
contract MalformedCustodyAdapterV1 {
    fallback() external {
        assembly { return(0, 0) }
    }
}

/// @dev Returns a valid static custody tuple followed by one extra word.
contract TrailingCustodyAdapterV1 {
    fallback() external {
        assembly {
            mstore(0x00, 1)
            mstore(0x20, 1)
            mstore(0x40, 1)
            mstore(0x60, 0xdeadbeef)
            return(0x00, 0x80)
        }
    }
}

/// @dev Synthetic bounded-response fixture only; no real custody authority.
contract MutableCustodyResponseAdapterR5 {
    uint8 private _mode;
    bytes private _payload;

    constructor(bytes memory initialPayload) { _payload = initialPayload; }

    function setPayload(bytes calldata payload) external {
        _payload = payload;
        _mode = 0;
    }

    function setHugeResponse() external { _mode = 1; }
    function setGasBurn() external { _mode = 2; }
    function setRevert() external { _mode = 3; }

    fallback() external {
        uint8 mode = _mode;
        if (mode == 1) {
            assembly {
                mstore(0x00, 1)
                mstore(0x20, 1)
                mstore(0x40, 1)
                return(0x00, 0x1000)
            }
        }
        if (mode == 2) {
            // Burns only the caller-provided staticcall stipend; the test invocation
            // below also caps its own outer gas to bound the regression itself.
            assembly { for { } 1 { } { } }
        }
        if (mode == 3) assembly { revert(0, 0) }
        bytes memory payload = _payload;
        assembly { return(add(payload, 0x20), mload(payload)) }
    }
}

contract HeartbeatAuthoritySourceV3Tests is Test {
    uint160 private constant TEST_ACTOR = 0xCAFE;
    bytes32 private constant NETWORK = keccak256("synthetic test network context");

    OperationAwareVAMSTimelockControllerV3 private lock;
    HeartbeatConsentPolicyV3 private policy;
    HeartbeatAuthoritySourceV3 private source;
    SyntheticCustodyAdapterV1 private custody;
    uint64 private _operationCounter;

    function setUp() public {
        vm.warp(1_800_000_000);
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        lock = new OperationAwareVAMSTimelockControllerV3(48 hours, proposers, executors, address(this));
        custody = new SyntheticCustodyAdapterV1();
        bytes32 sourceHash = keccak256(type(HeartbeatAuthoritySourceV3).runtimeCode);
        policy = new HeartbeatConsentPolicyV3(address(lock), sourceHash);
        source = new HeartbeatAuthoritySourceV3(
            address(lock), address(policy), address(custody), address(custody).codehash, block.chainid, NETWORK
        );
        _executeGovernance(
            address(policy), abi.encodeCall(policy.bindAuthoritySource, (address(source)))
        );
    }

    function testUnconfiguredPolicyCannotProduceAuthority() public {
        vm.expectRevert(HeartbeatAuthoritySourceV3.ProfileUnavailable.selector);
        source.currentState();
        vm.expectRevert(HeartbeatAuthoritySourceV3.ProfileUnavailable.selector);
        source.computeAuthorityConfigDigest();
    }

    function testTimelockPolicyBindingAndDigestProjectionAreRealReads() public {
        _configure(1, 1, keccak256("policy-root-A"));
        Types.Profile memory p = policy.consentProfile();
        Types.ProducerState memory state = source.currentState();
        require(p.authorityConfigDigest != bytes32(0), "policy digest set by source");
        require(state.authorityConfigDigest == p.authorityConfigDigest, "stored and current digest agree");
        require(state.timelock == address(lock) && state.policy == address(policy), "direct identities");
        require(state.authorityChangeSequence == lock.authorityChangeSequence(), "direct TL sequence");
        require(state.authorityConfigCommitment == lock.authorityConfigCommitment(), "direct TL commitment");
        require(state.custodyChangeSequence == 1, "direct test adapter sequence");

        bytes32 projectionBefore = Types.profileProjectionDigest(p);
        p.authorityConfigDigest = bytes32(uint256(0x1234));
        require(Types.profileProjectionDigest(p) == projectionBefore, "self digest excluded from projection");
    }

    function testRoleGrantRevokeAtoBtoAChangesGlobalGenerationAndStalesProfile() public {
        _configure(1, 1, keccak256("policy-root-A"));
        Types.ProducerState memory beforeState = source.currentState();

        _executeGovernance(address(lock), abi.encodeCall(lock.grantRole, (lock.CANCELLER_ROLE(), address(TEST_ACTOR))));
        Types.ProducerState memory middleState = source.currentState();
        require(middleState.authorityChangeSequence == beforeState.authorityChangeSequence + 1, "grant increments once");
        require(middleState.authorityConfigCommitment != beforeState.authorityConfigCommitment, "grant commitment changes");

        _executeGovernance(address(lock), abi.encodeCall(lock.revokeRole, (lock.CANCELLER_ROLE(), address(TEST_ACTOR))));
        Types.ProducerState memory afterState = source.currentState();
        require(!lock.hasRole(lock.CANCELLER_ROLE(), address(TEST_ACTOR)), "effective role restored");
        require(afterState.authorityChangeSequence == beforeState.authorityChangeSequence + 2, "A-B-A sequence retained");
        require(afterState.authorityConfigCommitment != beforeState.authorityConfigCommitment, "A-B-A commitment retained");
        require(afterState.authorityConfigDigest != policy.consentProfile().authorityConfigDigest, "old policy digest is stale");
    }

    function testRoleNoopDoesNotAdvanceGlobalGeneration() public {
        _configure(1, 1, keccak256("policy-root-A"));
        uint64 beforeSequence = lock.authorityChangeSequence();
        bytes32 beforeCommitment = lock.authorityConfigCommitment();
        _executeGovernance(address(lock), abi.encodeCall(lock.grantRole, (lock.EXECUTOR_ROLE(), address(this))));
        require(lock.authorityChangeSequence() == beforeSequence, "no-op grant does not increment");
        require(lock.authorityConfigCommitment() == beforeCommitment, "no-op grant leaves commitment");
    }

    function testDelayAtoBtoAIsMonotonicAndSubFloorUpdateRollsBack() public {
        _configure(1, 1, keccak256("policy-root-A"));
        Types.ProducerState memory beforeState = source.currentState();
        _executeGovernance(address(lock), abi.encodeCall(lock.updateDelay, (48 hours + 1)));
        Types.ProducerState memory changedState = source.currentState();
        require(changedState.minDelay == 48 hours + 1, "delay observed directly");
        require(changedState.authorityChangeSequence == beforeState.authorityChangeSequence + 1, "delay increments once");
        _executeGovernance(address(lock), abi.encodeCall(lock.updateDelay, (48 hours)));
        Types.ProducerState memory restoredState = source.currentState();
        require(restoredState.minDelay == beforeState.minDelay, "delay restored");
        require(restoredState.authorityChangeSequence == beforeState.authorityChangeSequence + 2, "delay A-B-A sequence retained");
        require(restoredState.authorityConfigCommitment != beforeState.authorityConfigCommitment, "delay A-B-A commitment retained");

        uint64 sequenceBeforeRejectedCall = lock.authorityChangeSequence();
        bytes memory invalidCall = abi.encodeCall(lock.updateDelay, (47 hours));
        bytes32 salt = _salt(address(lock), invalidCall);
        uint256 delay = lock.getMinDelay();
        lock.schedule(address(lock), 0, invalidCall, bytes32(0), salt, delay);
        vm.warp(block.timestamp + delay);
        vm.expectRevert();
        lock.execute(address(lock), 0, invalidCall, bytes32(0), salt);
        require(lock.authorityChangeSequence() == sequenceBeforeRejectedCall, "failed delay update rolls back generation");
        require(lock.getMinDelay() == 48 hours, "48-hour floor retained");
    }

    function testScheduleAndCancelOnlyUseOperationEpochs() public {
        _configure(1, 1, keccak256("policy-root-A"));
        uint64 sequenceBefore = lock.authorityChangeSequence();
        bytes32 salt = _salt(address(lock), abi.encodeCall(lock.grantRole, (lock.CANCELLER_ROLE(), address(TEST_ACTOR))));
        bytes memory callData = abi.encodeCall(lock.grantRole, (lock.CANCELLER_ROLE(), address(TEST_ACTOR)));
        bytes32 operationId = lock.hashOperation(address(lock), 0, callData, bytes32(0), salt);
        lock.schedule(address(lock), 0, callData, bytes32(0), salt, lock.getMinDelay());
        uint64 epochAfterSchedule = lock.operationEpoch(operationId);
        lock.cancel(operationId);
        require(lock.operationEpoch(operationId) == epochAfterSchedule + 1, "cancel advances operation epoch");
        require(lock.authorityChangeSequence() == sequenceBefore, "lifecycle does not change global generation");
    }

    function testPolicyVersionEpochChangeRecomputesDigest() public {
        _configure(1, 1, keccak256("policy-root-A"));
        bytes32 oldDigest = policy.consentProfile().authorityConfigDigest;
        _configure(2, 2, keccak256("policy-root-B"));
        Types.Profile memory p = policy.consentProfile();
        require(p.policyVersion == 2 && p.authorityEpoch == 2, "monotonic policy state");
        require(p.authorityConfigDigest != oldDigest, "policy change changes digest");
        require(source.currentState().authorityConfigDigest == p.authorityConfigDigest, "new digest matches live state");
    }

    function testAdapterAtoBtoASequenceMakesStoredDigestStale() public {
        _configure(1, 1, keccak256("policy-root-A"));
        bytes32 stored = policy.consentProfile().authorityConfigDigest;
        custody.setState(Types.CUSTODY_SCHEMA, 2, keccak256("temporary custody B"));
        custody.setState(Types.CUSTODY_SCHEMA, 3, keccak256("restored custody A"));
        Types.ProducerState memory current = source.currentState();
        require(current.custodyConfigurationDigest != bytes32(0), "adapter state read");
        require(current.authorityConfigDigest != stored, "custody generation prevents A-B-A restoration");
        _configure(2, 2, keccak256("policy-root-B"));
        require(source.currentState().authorityConfigDigest == policy.consentProfile().authorityConfigDigest, "governance refreshes digest");
    }

    function testPolicyConfigurationRollsBackIfAdapterBecomesUnavailable() public {
        _configure(1, 1, keccak256("policy-root-A"));
        custody.setRevert(true);
        Types.ProfileConfig memory next = _config(2, 2, keccak256("policy-root-B"));
        bytes memory callData = abi.encodeCall(policy.configure, (next));
        bytes32 salt = _salt(address(policy), callData);
        uint256 delay = lock.getMinDelay();
        lock.schedule(address(policy), 0, callData, bytes32(0), salt, delay);
        vm.warp(block.timestamp + delay);
        vm.expectRevert(HeartbeatConsentPolicyV3.AuthorityConfigurationUnavailable.selector);
        lock.execute(address(policy), 0, callData, bytes32(0), salt);
        require(policy.policyVersion() == 1 && policy.authorityEpoch() == 1, "failed config rolls back counters");
        require(policy.policyRoot() == keccak256("policy-root-A"), "failed config rolls back root");
    }

    function testWrongPolicyRuntimeAndWrongAdapterHashReject() public {
        FakePolicyV3 fakePolicy = new FakePolicyV3();
        vm.expectRevert(HeartbeatAuthoritySourceV3.InvalidConfiguration.selector);
        new HeartbeatAuthoritySourceV3(
            address(lock), address(fakePolicy), address(custody), address(custody).codehash, block.chainid, NETWORK
        );

        vm.expectRevert(HeartbeatAuthoritySourceV3.InvalidConfiguration.selector);
        new HeartbeatAuthoritySourceV3(
            address(lock), address(policy), address(custody), bytes32(uint256(0x1234)), block.chainid, NETWORK
        );

        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        OperationAwareVAMSTimelockControllerV2 oldLock =
            new OperationAwareVAMSTimelockControllerV2(48 hours, proposers, executors, address(this));
        vm.expectRevert(HeartbeatAuthoritySourceV3.InvalidConfiguration.selector);
        new HeartbeatAuthoritySourceV3(
            address(oldLock), address(policy), address(custody), address(custody).codehash, block.chainid, NETWORK
        );
    }

    function testPolicyRejectsUnpinnedSourceClass() public {
        FakeAuthoritySourceV3 fakeSource = new FakeAuthoritySourceV3();
        HeartbeatConsentPolicyV3 wrongSourcePolicy = new HeartbeatConsentPolicyV3(
            address(lock), keccak256(type(HeartbeatAuthoritySourceV3).runtimeCode)
        );
        _expectOnLockFailure(
            lock,
            address(wrongSourcePolicy),
            abi.encodeCall(wrongSourcePolicy.bindAuthoritySource, (address(fakeSource))),
            HeartbeatConsentPolicyV3.AuthoritySourceIdentityMismatch.selector
        );
    }

    function testMissingCustodyAdapterRejectsAtConstruction() public {
        vm.expectRevert(HeartbeatAuthoritySourceV3.InvalidConfiguration.selector);
        new HeartbeatAuthoritySourceV3(address(lock), address(policy), address(0), bytes32(0), block.chainid, NETWORK);
    }

    function testMalformedAndUnsupportedCustodyStatesFailClosed() public {
        MalformedCustodyAdapterV1 malformed = new MalformedCustodyAdapterV1();
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        OperationAwareVAMSTimelockControllerV3 lock2 =
            new OperationAwareVAMSTimelockControllerV3(48 hours, proposers, executors, address(this));
        HeartbeatConsentPolicyV3 policy2 = new HeartbeatConsentPolicyV3(
            address(lock2), keccak256(type(HeartbeatAuthoritySourceV3).runtimeCode)
        );
        HeartbeatAuthoritySourceV3 source2 = new HeartbeatAuthoritySourceV3(
            address(lock2), address(policy2), address(malformed), address(malformed).codehash, block.chainid, NETWORK
        );
        _executeOnLock(lock2, address(policy2), abi.encodeCall(policy2.bindAuthoritySource, (address(source2))));
        Types.ProfileConfig memory malformedProfile = _config(1, 1, keccak256("malformed-adapter-profile"));
        malformedProfile.custodyAdapter = address(malformed);
        malformedProfile.custodyAdapterRuntimeCodeHash = address(malformed).codehash;
        bytes memory malformedConfigure = abi.encodeCall(policy2.configure, (malformedProfile));
        _expectOnLockFailure(
            lock2,
            address(policy2),
            malformedConfigure,
            HeartbeatConsentPolicyV3.AuthorityConfigurationUnavailable.selector
        );
        require(policy2.policyVersion() == 0, "malformed adapter leaves policy unconfigured");

        _configure(1, 1, keccak256("policy-root-A"));
        custody.setState(2, 1, keccak256("wrong schema"));
        Types.ProfileConfig memory unsupported = _config(2, 2, keccak256("policy-root-B"));
        bytes memory unsupportedConfigure = abi.encodeCall(policy.configure, (unsupported));
        _expectOnLockFailure(
            lock,
            address(policy),
            unsupportedConfigure,
            HeartbeatConsentPolicyV3.AuthorityConfigurationUnavailable.selector
        );
    }

    function testBeforeChainSwitchAwayFromDeploymentChainMustReject() public {
        _configure(1, 1, keccak256("policy-root-A"));
        vm.chainId(block.chainid + 1);
        vm.expectRevert(bytes4(keccak256("ChainIdentityMismatch()")));
        source.currentState();
    }

    function testBeforeTrailingCustodyReturnDataMustRejectAndRollbackConfigure() public {
        TrailingCustodyAdapterV1 trailing = new TrailingCustodyAdapterV1();
        (OperationAwareVAMSTimelockControllerV3 lock2, HeartbeatConsentPolicyV3 policy2,) =
            _deployStackWithAdapter(address(trailing));
        Types.ProfileConfig memory config = _config(1, 1, keccak256("trailing-adapter-profile"));
        config.custodyAdapter = address(trailing);
        config.custodyAdapterRuntimeCodeHash = address(trailing).codehash;
        bytes memory callData = abi.encodeCall(policy2.configure, (config));
        _expectOnLockFailure(
            lock2,
            address(policy2),
            callData,
            HeartbeatConsentPolicyV3.AuthorityConfigurationUnavailable.selector
        );
        require(policy2.policyVersion() == 0 && policy2.authorityEpoch() == 0, "trailing data rolls back policy");
        require(policy2.policyRoot() == bytes32(0), "trailing data rolls back root");
    }

    function testBeforePolicyCannotBindSourceConfiguredForAnotherPolicy() public {
        HeartbeatConsentPolicyV3 otherPolicy = new HeartbeatConsentPolicyV3(
            address(lock), keccak256(type(HeartbeatAuthoritySourceV3).runtimeCode)
        );
        _expectOnLockFailure(
            lock,
            address(otherPolicy),
            abi.encodeCall(otherPolicy.bindAuthoritySource, (address(source))),
            HeartbeatConsentPolicyV3.AuthoritySourceIdentityMismatch.selector
        );
        require(otherPolicy.authoritySource() == address(0), "wrong-policy source remains unbound");
    }

    // Append inside HeartbeatAuthoritySourceV3Tests. The file already imports
    // HeartbeatAuthorityTypesV3 as Types. Constants are from the independent
    // stdlib manual-word vectors, not from Solidity-generated expected values.
    function testGolden87IndependentStaticAbiDigests() public pure {
        Types.Profile memory profile = _golden87Profile();
        bytes32 profileDigest = Types.profileProjectionDigest(profile);
        require(profileDigest == 0x7e6538f01d76eb9c7d5f441010cec9987060fc743eb5f9b1f49680c49d66b937, "profile golden");
    
        // The final stored digest is intentionally omitted from the projection.
        profile.authorityConfigDigest = bytes32(0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee);
        require(Types.profileProjectionDigest(profile) == profileDigest, "profile digest field excluded");
    
        Types.ProducerState memory state = _golden87State(profileDigest);
        bytes32 configDigest = Types.authorityConfigDigest(state);
        require(configDigest == 0xa520b3e09e90b9ece035aeef2c707ad813c2b8539bc18947d25dc50713c0ff19, "config golden");
        state.authorityConfigDigest = bytes32(0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee);
        require(Types.authorityConfigDigest(state) == configDigest, "config final digest excluded");
        state.authorityConfigDigest = configDigest;
        require(Types.authoritySnapshotDigest(state) == 0x969d2c65cd11dc139e7bb533af3d78f3d5292e69075aa456d6cf2d2d966ccef8, "snapshot golden");
    
        // policyRoot is absent from the final config projection as a direct field,
        // but is committed through the explicit profileProjectionDigest.
        profile.policyRoot = 0x1212121212121212121212121212121212121212121212121212121212121212;
        bytes32 changedProfileDigest = Types.profileProjectionDigest(profile);
        require(changedProfileDigest == 0x5db3243469c957c922c69d9b4a793df0a6b6d05867fc120db92e5be3a985e4fb, "root profile binding");
        state.policyProjectionDigest = changedProfileDigest;
        require(Types.authorityConfigDigest(state) == 0xe8782332a6d0a7f3d32142b4b664057efc85173fbbf19d6809f4e61b938d1c2b, "root reaches authority config");
    }
    
    function _golden87Profile() private pure returns (Types.Profile memory p) {
        p = Types.Profile({
            configured: true,
            schema: 3,
            policyRoot: 0x1111111111111111111111111111111111111111111111111111111111111111,
            policyVersion: 0x0102030405060708,
            authorityEpoch: 0x1112131415161718,
            maxConsentTtl: 86400,
            maxPrincipalLifetime: 2592000,
            oldKeyGraceSeconds: 0,
            oldKeyGracePolicy: 1,
            keyPolicy: 2,
            relayerPolicy: 2,
            allowedRelayer: address(uint160(0xa001)),
            withdrawalPolicy: 1,
            batchPolicy: 1,
            requeuePolicy: 1,
            authoritySource: address(uint160(0xa002)),
            authoritySourceRuntimeCodeHash: 0x2222222222222222222222222222222222222222222222222222222222222222,
            networkContextDigest: 0x3333333333333333333333333333333333333333333333333333333333333333,
            custodyAdapter: address(uint160(0xa003)),
            custodyAdapterRuntimeCodeHash: 0x4444444444444444444444444444444444444444444444444444444444444444,
            challengeProvider: address(uint160(0xa004)),
            challengeProviderRuntimeCodeHash: 0x5555555555555555555555555555555555555555555555555555555555555555,
            challengeProfileDigest: 0x6666666666666666666666666666666666666666666666666666666666666666,
            finalityProfileDigest: 0x7777777777777777777777777777777777777777777777777777777777777777,
            authorityConfigDigest: bytes32(0)
        });
    }
    
    function _golden87State(bytes32 profileDigest) private pure returns (Types.ProducerState memory s) {
        s = Types.ProducerState({
            sourceSchema: 3,
            scheme: 1,
            chainId: 31337,
            networkContextDigest: 0x3333333333333333333333333333333333333333333333333333333333333333,
            source: address(uint160(0xb001)),
            sourceRuntimeCodeHash: 0x8888888888888888888888888888888888888888888888888888888888888888,
            timelock: address(uint160(0xb002)),
            timelockRuntimeCodeHash: 0x9999999999999999999999999999999999999999999999999999999999999999,
            authorityChangeSequence: 0x2122232425262728,
            authorityConfigCommitment: 0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,
            minDelay: 172800,
            policy: address(uint160(0xb003)),
            policyRuntimeCodeHash: 0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,
            policyRoot: 0x1111111111111111111111111111111111111111111111111111111111111111,
            policyVersion: 0x0102030405060708,
            authorityEpoch: 0x1112131415161718,
            policyProjectionDigest: profileDigest,
            custodyAdapter: address(uint160(0xa003)),
            custodyAdapterRuntimeCodeHash: 0x4444444444444444444444444444444444444444444444444444444444444444,
            custodyChangeSequence: 0x3132333435363738,
            custodyConfigurationDigest: 0xcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc,
            authorityConfigDigest: bytes32(0)
        });
    }
    

    function testAfterConstructorRejectsZeroAndWrongExpectedChainId() public {
        vm.expectRevert(HeartbeatAuthoritySourceV3.ChainIdentityMismatch.selector);
        new HeartbeatAuthoritySourceV3(
            address(lock), address(policy), address(custody), address(custody).codehash, 0, NETWORK
        );
        vm.expectRevert(HeartbeatAuthoritySourceV3.ChainIdentityMismatch.selector);
        new HeartbeatAuthoritySourceV3(
            address(lock), address(policy), address(custody), address(custody).codehash, block.chainid + 1, NETWORK
        );
    }
    
    function testAfterReadRejectsZeroChainId() public {
        _configure(1, 1, keccak256("policy-root-chain-zero"));
        vm.chainId(0);
        vm.expectRevert(HeartbeatAuthoritySourceV3.ChainIdentityMismatch.selector);
        source.currentState();
    }
    
    function testAfterAcceptsCanonical96ByteCustodyTuple() public {
        bytes memory valid = abi.encode(uint16(1), uint64(1), bytes32(uint256(1)));
        MutableCustodyResponseAdapterR5 adapter = new MutableCustodyResponseAdapterR5(valid);
        (OperationAwareVAMSTimelockControllerV3 lock2, HeartbeatConsentPolicyV3 policy2,) =
            _deployAfterStackWithAdapter(address(adapter));
        Types.ProfileConfig memory config = _config(1, 1, keccak256("canonical-96-byte-adapter"));
        config.custodyAdapter = address(adapter);
        config.custodyAdapterRuntimeCodeHash = address(adapter).codehash;
        _executeOnLock(lock2, address(policy2), abi.encodeCall(policy2.configure, (config)));
        Types.Profile memory p = policy2.consentProfile();
        require(p.authorityConfigDigest != bytes32(0), "exact 96-byte tuple configures");
    }
    
    function testAfterRejectsShortAndNoncanonicalCustodyTuplesWithRollback() public {
        bytes memory valid = abi.encode(uint16(1), uint64(1), bytes32(uint256(1)));
        MutableCustodyResponseAdapterR5 adapter = new MutableCustodyResponseAdapterR5(valid);
        (OperationAwareVAMSTimelockControllerV3 lock2, HeartbeatConsentPolicyV3 policy2,) =
            _deployAfterStackWithAdapter(address(adapter));
    
        bytes memory shortTuple = abi.encode(uint16(1), uint64(1), bytes32(uint256(1)));
        assembly { mstore(shortTuple, 95) }
        bytes[] memory bad = new bytes[](6);
        bad[0] = shortTuple;
        bad[1] = abi.encode(uint256(1), (uint256(1) << 64) | 1, bytes32(uint256(1)));
        bad[2] = abi.encode(uint256(2), uint256(1), bytes32(uint256(1)));
        bad[3] = abi.encode(uint256(1), uint256(0), bytes32(uint256(1)));
        bad[4] = abi.encode(uint256(1), uint256(1), bytes32(0));
        bad[5] = abi.encode((uint256(1) << 16) | 1, uint256(1), bytes32(uint256(1)));
    
        for (uint256 i; i < bad.length; ++i) {
            adapter.setPayload(bad[i]);
            Types.ProfileConfig memory config = _config(
                1, 1, keccak256(abi.encode("invalid-custody-payload", i))
            );
            config.custodyAdapter = address(adapter);
            config.custodyAdapterRuntimeCodeHash = address(adapter).codehash;
            _expectOnLockFailure(
                lock2,
                address(policy2),
                abi.encodeCall(policy2.configure, (config)),
                HeartbeatConsentPolicyV3.AuthorityConfigurationUnavailable.selector
            );
            require(policy2.policyVersion() == 0 && policy2.authorityEpoch() == 0, "bad tuple update rolls back");
            require(policy2.policyRoot() == bytes32(0), "bad tuple root remains unset");
        }
    }
    
    function testAfterHugeCustodyReturnAndGasBurnFailWithinBoundedOuterCall() public {
        bytes memory valid = abi.encode(uint16(1), uint64(1), bytes32(uint256(1)));
        MutableCustodyResponseAdapterR5 adapter = new MutableCustodyResponseAdapterR5(valid);
        (OperationAwareVAMSTimelockControllerV3 lock2, HeartbeatConsentPolicyV3 policy2,
            HeartbeatAuthoritySourceV3 source2) = _deployAfterStackWithAdapter(address(adapter));
        Types.ProfileConfig memory config = _config(1, 1, keccak256("bounded-adapter-response"));
        config.custodyAdapter = address(adapter);
        config.custodyAdapterRuntimeCodeHash = address(adapter).codehash;
        _executeOnLock(lock2, address(policy2), abi.encodeCall(policy2.configure, (config)));
    
        adapter.setHugeResponse();
        vm.expectRevert(HeartbeatAuthoritySourceV3.CustodyUnavailable.selector);
        source2.currentState{gas: 300_000}();
    
        adapter.setGasBurn();
        vm.expectRevert(HeartbeatAuthoritySourceV3.CustodyUnavailable.selector);
        source2.currentState{gas: 300_000}();
    
        adapter.setRevert();
        vm.expectRevert(HeartbeatAuthoritySourceV3.CustodyUnavailable.selector);
        source2.currentState{gas: 300_000}();
    }
    
    function testAfterRoleRenounceAdvancesAuthorityGenerationAndStalesDigest() public {
        _configure(1, 1, keccak256("policy-root-renounce"));
        Types.ProducerState memory beforeState = source.currentState();
        address actor = address(TEST_ACTOR);
        _executeGovernance(address(lock), abi.encodeCall(lock.grantRole, (lock.CANCELLER_ROLE(), actor)));
        uint64 afterGrant = lock.authorityChangeSequence();
        bytes32 role = lock.CANCELLER_ROLE();
        vm.prank(actor);
        lock.renounceRole(role, actor);
        Types.ProducerState memory afterRenounce = source.currentState();
        require(afterRenounce.authorityChangeSequence == afterGrant + 1, "renounce increments once");
        require(afterRenounce.authorityChangeSequence == beforeState.authorityChangeSequence + 2, "grant and renounce recorded");
        require(afterRenounce.authorityConfigCommitment != beforeState.authorityConfigCommitment, "renounce retains history");
        require(afterRenounce.authorityConfigDigest != policy.consentProfile().authorityConfigDigest, "old digest is stale");
    }
    
    function testAfterNoOpDelayAndUnsupportedRoleAdminRouteDoNotAdvanceSequence() public {
        _configure(1, 1, keccak256("policy-root-no-op-delay"));
        uint64 beforeSequence = lock.authorityChangeSequence();
        bytes32 beforeCommitment = lock.authorityConfigCommitment();
        _executeGovernance(address(lock), abi.encodeCall(lock.updateDelay, (lock.getMinDelay())));
        require(lock.authorityChangeSequence() == beforeSequence, "no-op delay does not advance sequence");
        require(lock.authorityConfigCommitment() == beforeCommitment, "no-op delay keeps commitment");
    
        (bool ok,) = address(lock).call(
            abi.encodeWithSignature("setRoleAdmin(bytes32,bytes32)", lock.CANCELLER_ROLE(), lock.PROPOSER_ROLE())
        );
        require(!ok, "no unsupported external role-admin mutation route");
        require(lock.authorityChangeSequence() == beforeSequence, "unsupported route leaves generation unchanged");
    }
    
    function _deployAfterStackWithAdapter(address adapter)
        private returns (
            OperationAwareVAMSTimelockControllerV3 lock2,
            HeartbeatConsentPolicyV3 policy2,
            HeartbeatAuthoritySourceV3 source2
        )
    {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        lock2 = new OperationAwareVAMSTimelockControllerV3(48 hours, proposers, executors, address(this));
        bytes32 sourceHash = keccak256(type(HeartbeatAuthoritySourceV3).runtimeCode);
        policy2 = new HeartbeatConsentPolicyV3(address(lock2), sourceHash);
        source2 = new HeartbeatAuthoritySourceV3(
            address(lock2), address(policy2), adapter, adapter.codehash, block.chainid, NETWORK
        );
        _executeOnLock(lock2, address(policy2), abi.encodeCall(policy2.bindAuthoritySource, (address(source2))));
    }

    function _configure(uint64 version, uint64 epoch, bytes32 root) private {
        Types.ProfileConfig memory config = _config(version, epoch, root);
        _executeGovernance(address(policy), abi.encodeCall(policy.configure, (config)));
    }

    function _config(uint64 version, uint64 epoch, bytes32 root)
        private view returns (Types.ProfileConfig memory config)
    {
        config = Types.ProfileConfig({
            policyRoot: root,
            policyVersion: version,
            authorityEpoch: epoch,
            maxConsentTtl: 1 hours,
            maxPrincipalLifetime: 30 days,
            oldKeyGraceSeconds: 0,
            oldKeyGracePolicy: Types.GRACE_POLICY_ZERO,
            keyPolicy: Types.KEY_POLICY_REQUIRE_DISTINCT,
            relayerPolicy: Types.RELAYER_POLICY_PERMISSIONLESS,
            allowedRelayer: address(0),
            withdrawalPolicy: Types.WITHDRAWAL_POLICY_NO_PERSISTENT_FRAME,
            batchPolicy: Types.BATCH_POLICY_SINGLE_ONLY,
            requeuePolicy: Types.REQUEUE_POLICY_TIMELOCK_EPOCH,
            networkContextDigest: NETWORK,
            custodyAdapter: address(custody),
            custodyAdapterRuntimeCodeHash: address(custody).codehash,
            challengeProvider: address(this),
            challengeProviderRuntimeCodeHash: address(this).codehash,
            challengeProfileDigest: keccak256("synthetic challenge profile"),
            finalityProfileDigest: keccak256("synthetic finality profile")
        });
    }

    function _executeGovernance(address target, bytes memory data) private {
        _executeOnLock(lock, target, data);
    }

    function _executeOnLock(OperationAwareVAMSTimelockControllerV3 targetLock, address target, bytes memory data) private {
        bytes32 salt = _salt(target, data);
        uint256 delay = targetLock.getMinDelay();
        targetLock.schedule(target, 0, data, bytes32(0), salt, delay);
        vm.warp(block.timestamp + delay);
        targetLock.execute(target, 0, data, bytes32(0), salt);
    }

    function _expectOnLockFailure(
        OperationAwareVAMSTimelockControllerV3 targetLock,
        address target,
        bytes memory data,
        bytes4 expectedSelector
    ) private {
        bytes32 salt = _salt(target, data);
        uint256 delay = targetLock.getMinDelay();
        targetLock.schedule(target, 0, data, bytes32(0), salt, delay);
        vm.warp(block.timestamp + delay);
        vm.expectRevert(expectedSelector);
        targetLock.execute(target, 0, data, bytes32(0), salt);
    }

    function _deployStackWithAdapter(address adapter)
        private returns (
            OperationAwareVAMSTimelockControllerV3 lock2,
            HeartbeatConsentPolicyV3 policy2,
            HeartbeatAuthoritySourceV3 source2
        )
    {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        lock2 = new OperationAwareVAMSTimelockControllerV3(48 hours, proposers, executors, address(this));
        policy2 = new HeartbeatConsentPolicyV3(
            address(lock2), keccak256(type(HeartbeatAuthoritySourceV3).runtimeCode)
        );
        source2 = new HeartbeatAuthoritySourceV3(
            address(lock2), address(policy2), adapter, adapter.codehash, block.chainid, NETWORK
        );
        _executeOnLock(lock2, address(policy2), abi.encodeCall(policy2.bindAuthoritySource, (address(source2))));
    }

    function _salt(address target, bytes memory data) private returns (bytes32) {
        ++_operationCounter;
        return keccak256(abi.encode(address(this), target, _operationCounter, keccak256(data)));
    }
}

