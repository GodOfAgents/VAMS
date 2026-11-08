// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {OperationAwareVAMSTimelockControllerV2} from "../src/governance/OperationAwareVAMSTimelockControllerV2.sol";
import {HeartbeatConsentPolicyV2} from "../src/trust/HeartbeatConsentPolicyV2.sol";
import {HeartbeatConsentVerificationRouterV2} from "../src/trust/HeartbeatConsentVerificationRouterV2.sol";
import {HeartbeatAtomicConsentRegistryV2} from "../src/trust/HeartbeatAtomicConsentRegistryV2.sol";
import {HeartbeatConsentProfileV2 as Types} from "../src/trust/HeartbeatConsentProfileV2.sol";

/// @dev Counterfeit interface fixture: its unrestricted setter demonstrates why a governance getter is not a code identity.
contract CounterfeitHeartbeatConsentPolicyV2 {
    address public immutable governance;
    Types.Profile private _profile;
    constructor(address governance_) { governance = governance_; }
    function consentProfile() external view returns (Types.Profile memory) { return _profile; }
    function setProfile(Types.Profile calldata value) external { _profile = value; }
}

/// @dev Local constructor/context regression fixtures only; no authentic policy/source is modeled.
contract HeartbeatAtomicConsentRegistryV2Tests is Test {
    OperationAwareVAMSTimelockControllerV2 private timelock;
    HeartbeatConsentPolicyV2 private policy;
    HeartbeatConsentVerificationRouterV2 private verifier;
    HeartbeatAtomicConsentRegistryV2 private registry;

    function setUp() public {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        timelock = new OperationAwareVAMSTimelockControllerV2(48 hours, proposers, executors, address(this));
        policy = new HeartbeatConsentPolicyV2(address(timelock));
        verifier = new HeartbeatConsentVerificationRouterV2();
        registry = new HeartbeatAtomicConsentRegistryV2(
            address(timelock), address(policy), address(verifier), bytes32(uint256(1)), bytes32(uint256(2))
        );
    }

    function testProfileStartsUnconfiguredAndConsumerCannotAssumePolicy() public view {
        require(policy.policyRoot() == bytes32(0), "prototype policy must start closed");
        require(registry.deploymentChainId() == block.chainid, "local chain binding");
    }

    function testConstructorRejectsCounterfeitGovernanceGetterPolicy() public {
        CounterfeitHeartbeatConsentPolicyV2 counterfeit = new CounterfeitHeartbeatConsentPolicyV2(address(timelock));
        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.InvalidConfiguration.selector);
        new HeartbeatAtomicConsentRegistryV2(
            address(timelock), address(counterfeit), address(verifier), bytes32(uint256(1)), bytes32(uint256(2))
        );
    }

    function testDirectCallbackRejectsWithoutTransactionScopedProofFrame() public {
        vm.expectRevert(HeartbeatAtomicConsentRegistryV2.WrongOperationContext.selector);
        registry.applyConsent(bytes(""), bytes(""));
    }

    function testTimelockCallbackRejectsWithoutRelayFrameAndRollsBackOperation() public {
        bytes memory payload = abi.encodeCall(registry.applyConsent, (bytes(""), bytes("")));
        bytes32 salt = keccak256("synthetic-direct-call");
        bytes32 operationId = timelock.hashOperation(address(registry), 0, payload, bytes32(0), salt);
        timelock.schedule(address(registry), 0, payload, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        vm.expectRevert();
        timelock.execute(address(registry), 0, payload, bytes32(0), salt);
        require(timelock.isOperationReady(operationId), "failed callback must roll back Timelock completion");
        (, bytes32 digest, uint64 generation, uint64 nonce,) = registry.principalState(bytes32(uint256(7)));
        require(digest == bytes32(0) && generation == 0 && nonce == 0, "failed call must not mutate state");
    }

    function testBatchContextCannotReachMutationWithoutFrame() public {
        address[] memory targets = new address[](1);
        uint256[] memory values = new uint256[](1);
        bytes[] memory payloads = new bytes[](1);
        targets[0] = address(registry);
        payloads[0] = abi.encodeCall(registry.applyConsent, (bytes(""), bytes("")));
        bytes32 salt = keccak256("synthetic-batch");
        timelock.scheduleBatch(targets, values, payloads, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        vm.expectRevert();
        timelock.executeBatch(targets, values, payloads, bytes32(0), salt);
    }

    function testCancelAndIdenticalRequeueAdvanceOperationEpoch() public {
        bytes memory payload = abi.encodeCall(registry.applyConsent, (bytes(""), bytes("")));
        bytes32 salt = keccak256("synthetic-requeue");
        bytes32 id = timelock.hashOperation(address(registry), 0, payload, bytes32(0), salt);
        timelock.schedule(address(registry), 0, payload, bytes32(0), salt, 48 hours);
        uint64 firstEpoch = timelock.operationEpoch(id);
        require(firstEpoch == 1 && timelock.scheduledDelay(id) == 48 hours, "initial schedule facts");
        timelock.cancel(id);
        require(timelock.operationEpoch(id) == firstEpoch + 1 && timelock.scheduledDelay(id) == 0, "cancel invalidates frame epoch");
        timelock.schedule(address(registry), 0, payload, bytes32(0), salt, 48 hours);
        require(timelock.operationEpoch(id) == firstEpoch + 2, "identical requeue gets fresh epoch");
    }

    /// @dev Independent static-word vectors; synthetic encoding check only, not valid authority fixtures.
    function testAuthorityDigestMatchesIndependentStaticAbiGoldens() public pure {
        Types.AuthoritySnapshot memory small = _smallAuthoritySnapshot();
        require(
            Types.authorityDigest(small) == bytes32(0xb36979521037091d2695283b9aea0c338f035a2f7ce2d20560cae74eadb63dfd),
            "small authority ABI golden"
        );
        Types.AuthoritySnapshot memory maximumWidths = _maximumWidthAuthoritySnapshot();
        require(
            Types.authorityDigest(maximumWidths) == bytes32(0x2b704348054482ba04f55cb3bf82122fb6b1f91ee82ccb9f09fe7f40fad248e1),
            "maximum-width authority ABI golden"
        );
    }

    function _smallAuthoritySnapshot() private pure returns (Types.AuthoritySnapshot memory s) {
        s.sourceSchema = 2;
        s.scheme = 1;
        s.registrySchema = 2;
        s.chainId = 0x13882;
        s.networkContextDigest = bytes32(uint256(0x11));
        s.registry = address(0x1234);
        s.registryRuntimeCodeHash = bytes32(uint256(0x21));
        s.policy = address(0x5678);
        s.policyRuntimeCodeHash = bytes32(uint256(0x22));
        s.timelock = address(0x9abc);
        s.timelockRuntimeCodeHash = bytes32(uint256(0x23));
        s.authorityConfigDigest = bytes32(uint256(0x24));
        s.authorityChangeSequence = 9;
        s.policyRoot = bytes32(uint256(0x25));
        s.policyVersion = 2;
        s.authorityEpoch = 3;
        s.isProxy = false;
    }

    function _maximumWidthAuthoritySnapshot() private pure returns (Types.AuthoritySnapshot memory s) {
        s.sourceSchema = type(uint16).max;
        s.scheme = type(uint8).max;
        s.registrySchema = type(uint16).max;
        s.chainId = type(uint256).max;
        s.networkContextDigest = bytes32(type(uint256).max);
        s.registry = address(type(uint160).max);
        s.registryRuntimeCodeHash = bytes32(type(uint256).max);
        s.policy = address(type(uint160).max);
        s.policyRuntimeCodeHash = bytes32(type(uint256).max);
        s.timelock = address(type(uint160).max);
        s.timelockRuntimeCodeHash = bytes32(type(uint256).max);
        s.authorityConfigDigest = bytes32(type(uint256).max);
        s.authorityChangeSequence = type(uint64).max;
        s.policyRoot = bytes32(type(uint256).max);
        s.policyVersion = type(uint64).max;
        s.authorityEpoch = type(uint64).max;
        s.isProxy = true;
    }
}
