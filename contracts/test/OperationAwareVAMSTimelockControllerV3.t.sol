// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";
import {OperationAwareVAMSTimelockControllerV2} from "../src/governance/OperationAwareVAMSTimelockControllerV2.sol";
import {OperationAwareVAMSTimelockControllerV3} from "../src/governance/OperationAwareVAMSTimelockControllerV3.sol";

/// @dev Test-only access to internal mutation/overflow paths not exposed by production APIs.
contract OperationAwareVAMSTimelockControllerV3Harness is OperationAwareVAMSTimelockControllerV3 {
    constructor(uint256 delay, address[] memory proposers, address[] memory executors, address admin)
        OperationAwareVAMSTimelockControllerV3(delay, proposers, executors, admin) {}

    function setRoleAdminForTest(bytes32 role, bytes32 adminRole) external {
        _setRoleAdmin(role, adminRole);
    }

    function forceSequenceForTest(uint64 sequence) external {
        authorityChangeSequence = sequence;
    }
}

contract OperationAwareVAMSTimelockControllerV3Tests is Test {
    uint256 private constant DELAY = 48 hours;
    bytes32 private constant TEST_ROLE = keccak256("V3_TEST_ROLE");
    bytes32 private constant OTHER_ADMIN_ROLE = keccak256("V3_OTHER_ADMIN_ROLE");

    OperationAwareVAMSTimelockControllerV3 private timelock;
    uint256 private saltCounter;

    function setUp() public {
        vm.warp(1_700_000_001);
        timelock = _newTimelock(address(0));
    }

    function testConstructorDigestCanonicalizesOrderAndDuplicates() public {
        address[] memory proposersA = new address[](3);
        proposersA[0] = address(0xCAFE);
        proposersA[1] = address(this);
        proposersA[2] = address(0xCAFE);
        address[] memory executorsA = new address[](3);
        executorsA[0] = address(0);
        executorsA[1] = address(0xBEEF);
        executorsA[2] = address(0);

        address[] memory proposersB = new address[](2);
        proposersB[0] = address(this);
        proposersB[1] = address(0xCAFE);
        address[] memory executorsB = new address[](2);
        executorsB[0] = address(0xBEEF);
        executorsB[1] = address(0);

        OperationAwareVAMSTimelockControllerV3 first =
            new OperationAwareVAMSTimelockControllerV3(DELAY, proposersA, executorsA, address(this));
        OperationAwareVAMSTimelockControllerV3 second =
            new OperationAwareVAMSTimelockControllerV3(DELAY, proposersB, executorsB, address(this));

        assertTrue(first.hasRole(first.DEFAULT_ADMIN_ROLE(), address(first)));
        assertTrue(second.hasRole(second.DEFAULT_ADMIN_ROLE(), address(second)));
        assertTrue(first.hasRole(first.DEFAULT_ADMIN_ROLE(), address(this)));
        assertTrue(second.hasRole(second.DEFAULT_ADMIN_ROLE(), address(this)));
        assertTrue(first.hasRole(first.PROPOSER_ROLE(), address(0xCAFE)));
        assertTrue(first.hasRole(first.CANCELLER_ROLE(), address(0xCAFE)));
        assertTrue(first.hasRole(first.EXECUTOR_ROLE(), address(0)));
        assertTrue(second.hasRole(second.PROPOSER_ROLE(), address(0xCAFE)));
        assertTrue(second.hasRole(second.CANCELLER_ROLE(), address(0xCAFE)));
        assertTrue(second.hasRole(second.EXECUTOR_ROLE(), address(0)));
        assertTrue(first.authorityConfigCommitment() != bytes32(0));
        assertTrue(first.initialRoleConfigurationDigest() != bytes32(0));
        assertEq(first.initialRoleConfigurationDigest(), _expectedInitialDigest(first));
        assertEq(second.initialRoleConfigurationDigest(), _expectedInitialDigest(second));
        assertTrue(first.initialRoleConfigurationDigest() != second.initialRoleConfigurationDigest());
        assertEq(first.authorityChangeSequence(), 0);
        assertEq(second.authorityChangeSequence(), 0);
    }

    function testEffectiveGrantAndRevokeAdvanceExactlyOnce() public {
        OperationAwareVAMSTimelockControllerV3Harness adminLock = _newAdminHarness();
        address member = address(0xBEEF);
        uint64 initialSequence = adminLock.authorityChangeSequence();
        bytes32 initialCommitment = adminLock.authorityConfigCommitment();

        adminLock.grantRole(TEST_ROLE, member);
        assertEq(adminLock.authorityChangeSequence(), initialSequence + 1);
        assertTrue(adminLock.authorityConfigCommitment() != initialCommitment);
        assertTrue(adminLock.hasRole(TEST_ROLE, member));

        uint64 grantedSequence = adminLock.authorityChangeSequence();
        bytes32 grantedCommitment = adminLock.authorityConfigCommitment();
        adminLock.revokeRole(TEST_ROLE, member);
        assertEq(adminLock.authorityChangeSequence(), grantedSequence + 1);
        assertTrue(adminLock.authorityConfigCommitment() != grantedCommitment);
        assertFalse(adminLock.hasRole(TEST_ROLE, member));
    }

    function testGrantExistingAndRevokeAbsentAreNoops() public {
        OperationAwareVAMSTimelockControllerV3Harness adminLock = _newAdminHarness();
        address member = address(0xBEEF);
        adminLock.grantRole(TEST_ROLE, member);
        uint64 sequence = adminLock.authorityChangeSequence();
        bytes32 commitment = adminLock.authorityConfigCommitment();

        adminLock.grantRole(TEST_ROLE, member);
        adminLock.revokeRole(TEST_ROLE, address(0xDEAD));

        assertEq(adminLock.authorityChangeSequence(), sequence);
        assertEq(adminLock.authorityConfigCommitment(), commitment);
    }

    function testSelfRenounceAdvancesEffectiveRoleMutationOnce() public {
        uint64 sequence = timelock.authorityChangeSequence();
        bytes32 commitment = timelock.authorityConfigCommitment();
        assertTrue(timelock.hasRole(timelock.CANCELLER_ROLE(), address(this)));

        timelock.renounceRole(timelock.CANCELLER_ROLE(), address(this));

        assertEq(timelock.authorityChangeSequence(), sequence + 1);
        assertTrue(timelock.authorityConfigCommitment() != commitment);
        assertFalse(timelock.hasRole(timelock.CANCELLER_ROLE(), address(this)));
    }

    function testUnscheduledNonAdminRoleMutationFailsWithoutChangingCommitment() public {
        bytes32 commitment = timelock.authorityConfigCommitment();
        vm.expectRevert();
        timelock.grantRole(TEST_ROLE, address(0xBEEF));
        assertEq(timelock.authorityChangeSequence(), 0);
        assertEq(timelock.authorityConfigCommitment(), commitment);
        assertFalse(timelock.hasRole(TEST_ROLE, address(0xBEEF)));
    }

    function testQueuedSelfCallGrantAdvancesOnlyWhenAuthorityMutationExecutes() public {
        address member = address(0xBEEF);
        bytes32 initialCommitment = timelock.authorityConfigCommitment();
        bytes memory grant = abi.encodeCall(timelock.grantRole, (TEST_ROLE, member));
        bytes32 salt = _nextSalt();
        bytes32 operationId = _scheduleSingle(address(timelock), grant, salt, DELAY);

        assertEq(timelock.authorityChangeSequence(), 0);
        assertTrue(timelock.authorityConfigCommitment() == initialCommitment);
        vm.warp(block.timestamp + DELAY);
        timelock.execute(address(timelock), 0, grant, bytes32(0), salt);

        assertTrue(timelock.isOperationDone(operationId));
        assertTrue(timelock.hasRole(TEST_ROLE, member));
        assertEq(timelock.authorityChangeSequence(), 1);
        assertTrue(timelock.authorityConfigCommitment() != initialCommitment);
    }

    function testRoleMembershipABAHasNewGenerationAndCommitment() public {
        OperationAwareVAMSTimelockControllerV3Harness adminLock = _newAdminHarness();
        address member = address(0xBEEF);
        adminLock.grantRole(TEST_ROLE, member);
        uint64 sequenceAtA = adminLock.authorityChangeSequence();
        bytes32 commitmentAtA = adminLock.authorityConfigCommitment();

        adminLock.revokeRole(TEST_ROLE, member);
        adminLock.grantRole(TEST_ROLE, member);

        assertTrue(adminLock.hasRole(TEST_ROLE, member));
        assertEq(adminLock.authorityChangeSequence(), sequenceAtA + 2);
        assertTrue(adminLock.authorityConfigCommitment() != commitmentAtA);
    }

    function testEffectiveRoleAdminChangeAdvancesAndNoopDoesNot() public {
        OperationAwareVAMSTimelockControllerV3Harness harness = _newAdminHarness();
        uint64 initialSequence = harness.authorityChangeSequence();
        bytes32 initialCommitment = harness.authorityConfigCommitment();

        harness.setRoleAdminForTest(TEST_ROLE, OTHER_ADMIN_ROLE);
        assertEq(harness.authorityChangeSequence(), initialSequence + 1);
        assertTrue(harness.authorityConfigCommitment() != initialCommitment);

        uint64 changedSequence = harness.authorityChangeSequence();
        bytes32 changedCommitment = harness.authorityConfigCommitment();
        harness.setRoleAdminForTest(TEST_ROLE, OTHER_ADMIN_ROLE);
        assertEq(harness.authorityChangeSequence(), changedSequence);
        assertEq(harness.authorityConfigCommitment(), changedCommitment);

        harness.setRoleAdminForTest(TEST_ROLE, harness.DEFAULT_ADMIN_ROLE());
        assertEq(harness.authorityChangeSequence(), changedSequence + 1);
        assertTrue(harness.authorityConfigCommitment() != changedCommitment);
    }

    function testEffectiveDelayIncreaseAdvancesOnceAndPreservesFloor() public {
        uint64 initialSequence = timelock.authorityChangeSequence();
        bytes32 initialCommitment = timelock.authorityConfigCommitment();
        bytes memory update = abi.encodeCall(timelock.updateDelay, (72 hours));
        bytes32 salt = _nextSalt();
        _scheduleSingle(address(timelock), update, salt, DELAY);
        assertEq(timelock.authorityChangeSequence(), initialSequence);
        vm.warp(block.timestamp + DELAY);
        timelock.execute(address(timelock), 0, update, bytes32(0), salt);

        assertEq(timelock.getMinDelay(), 72 hours);
        assertEq(timelock.authorityChangeSequence(), initialSequence + 1);
        assertTrue(timelock.authorityConfigCommitment() != initialCommitment);
    }

    function testQueuedNoopDelayUpdatePreservesGenerationAndCommitment() public {
        uint64 initialSequence = timelock.authorityChangeSequence();
        bytes32 initialCommitment = timelock.authorityConfigCommitment();
        bytes memory update = abi.encodeCall(timelock.updateDelay, (DELAY));
        bytes32 salt = _nextSalt();
        bytes32 operationId = _scheduleSingle(address(timelock), update, salt, DELAY);

        vm.warp(block.timestamp + DELAY);
        timelock.execute(address(timelock), 0, update, bytes32(0), salt);

        assertTrue(timelock.isOperationDone(operationId));
        assertEq(timelock.getMinDelay(), DELAY);
        assertEq(timelock.authorityChangeSequence(), initialSequence);
        assertEq(timelock.authorityConfigCommitment(), initialCommitment);
    }

    function testQueuedDelayOverflowRevertsAtomicallyAndLeavesOperationReady() public {
        OperationAwareVAMSTimelockControllerV3Harness harness = _newAdminHarness();
        bytes32 initialCommitment = harness.authorityConfigCommitment();
        harness.forceSequenceForTest(type(uint64).max);

        bytes memory update = abi.encodeCall(harness.updateDelay, (72 hours));
        bytes32 salt = _nextSalt();
        bytes32 operationId = harness.hashOperation(address(harness), 0, update, bytes32(0), salt);
        harness.schedule(address(harness), 0, update, bytes32(0), salt, DELAY);
        vm.warp(block.timestamp + DELAY);

        vm.expectRevert(OperationAwareVAMSTimelockControllerV3.AuthorityChangeSequenceOverflow.selector);
        harness.execute(address(harness), 0, update, bytes32(0), salt);

        assertEq(harness.getMinDelay(), DELAY);
        assertEq(harness.authorityChangeSequence(), type(uint64).max);
        assertEq(harness.authorityConfigCommitment(), initialCommitment);
        assertTrue(harness.isOperationReady(operationId));
        assertFalse(harness.isOperationDone(operationId));
    }

    function testDelayBelowFloorRevertsWithoutAdvancingGeneration() public {
        uint64 initialSequence = timelock.authorityChangeSequence();
        bytes32 initialCommitment = timelock.authorityConfigCommitment();
        bytes memory update = abi.encodeCall(timelock.updateDelay, (47 hours));
        bytes32 salt = _nextSalt();
        _scheduleSingle(address(timelock), update, salt, DELAY);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(abi.encodeWithSelector(VAMSTimelockController.DelayTooShort.selector, 47 hours, DELAY));
        timelock.execute(address(timelock), 0, update, bytes32(0), salt);

        assertEq(timelock.authorityChangeSequence(), initialSequence);
        assertEq(timelock.authorityConfigCommitment(), initialCommitment);
        assertEq(timelock.getMinDelay(), DELAY);
    }

    function testOperationScheduleCancelRequeueAndExecuteDoNotChangeGlobalGeneration() public {
        uint64 sequence = timelock.authorityChangeSequence();
        bytes32 commitment = timelock.authorityConfigCommitment();
        bytes32 salt = _nextSalt();
        bytes32 id = timelock.hashOperation(address(0xBEEF), 0, bytes(""), bytes32(0), salt);

        timelock.schedule(address(0xBEEF), 0, bytes(""), bytes32(0), salt, DELAY);
        assertEq(timelock.operationEpoch(id), 1);
        timelock.cancel(id);
        assertEq(timelock.operationEpoch(id), 2);
        timelock.schedule(address(0xBEEF), 0, bytes(""), bytes32(0), salt, DELAY);
        assertEq(timelock.operationEpoch(id), 3);
        vm.warp(block.timestamp + DELAY);
        timelock.execute(address(0xBEEF), 0, bytes(""), bytes32(0), salt);

        assertTrue(timelock.isOperationDone(id));
        assertEq(timelock.operationEpoch(id), 3);
        assertEq(timelock.authorityChangeSequence(), sequence);
        assertEq(timelock.authorityConfigCommitment(), commitment);
    }

    function testSequenceOverflowRevertsRoleMutationAtomically() public {
        OperationAwareVAMSTimelockControllerV3Harness harness = _newAdminHarness();
        address member = address(0xBEEF);
        bytes32 commitment = harness.authorityConfigCommitment();
        harness.forceSequenceForTest(type(uint64).max);

        vm.expectRevert(OperationAwareVAMSTimelockControllerV3.AuthorityChangeSequenceOverflow.selector);
        harness.grantRole(TEST_ROLE, member);

        assertFalse(harness.hasRole(TEST_ROLE, member));
        assertEq(harness.authorityChangeSequence(), type(uint64).max);
        assertEq(harness.authorityConfigCommitment(), commitment);
    }

    function testV3HasDistinctRuntimeAndV2HasNoAuthorityGenerationSurface() public {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(0);
        OperationAwareVAMSTimelockControllerV2 oldVersion =
            new OperationAwareVAMSTimelockControllerV2(DELAY, proposers, executors, address(0));

        assertTrue(address(oldVersion).codehash != address(timelock).codehash);
        assertEq(oldVersion.operationEpoch(bytes32(0)), 0);
        assertEq(timelock.authorityChangeSequence(), 0);
        assertTrue(timelock.authorityConfigCommitment() != bytes32(0));
    }

    function testBatchDelayABAAdvancesBeforeFollowingTarget() public {
        uint64 initialSequence = timelock.authorityChangeSequence();
        bytes32 initialCommitment = timelock.authorityConfigCommitment();
        AuthoritySequenceObserver83 observer = new AuthoritySequenceObserver83(timelock);
        address[] memory targets = new address[](3);
        uint256[] memory values = new uint256[](3);
        bytes[] memory payloads = new bytes[](3);
        targets[0] = address(timelock);
        targets[1] = address(observer);
        targets[2] = address(timelock);
        payloads[0] = abi.encodeCall(timelock.updateDelay, (72 hours));
        payloads[1] = abi.encodeCall(observer.observe, ());
        payloads[2] = abi.encodeCall(timelock.updateDelay, (DELAY));
        bytes32 salt = _nextSalt();
        bytes32 id = timelock.hashOperationBatch(targets, values, payloads, bytes32(0), salt);
        timelock.scheduleBatch(targets, values, payloads, bytes32(0), salt, DELAY);
        vm.warp(block.timestamp + DELAY);

        timelock.executeBatch(targets, values, payloads, bytes32(0), salt);

        assertEq(observer.observedSequence(), initialSequence + 1);
        assertEq(observer.observedDelay(), 72 hours);
        assertEq(timelock.getMinDelay(), DELAY);
        assertEq(timelock.authorityChangeSequence(), initialSequence + 2);
        assertTrue(timelock.authorityConfigCommitment() != initialCommitment);
        assertTrue(timelock.isOperationDone(id));
    }

    function testRevertingDelayBatchRestoresGenerationAndDelay() public {
        uint64 initialSequence = timelock.authorityChangeSequence();
        bytes32 initialCommitment = timelock.authorityConfigCommitment();
        address[] memory targets = new address[](2);
        uint256[] memory values = new uint256[](2);
        bytes[] memory payloads = new bytes[](2);
        targets[0] = address(timelock);
        targets[1] = address(timelock);
        payloads[0] = abi.encodeCall(timelock.updateDelay, (72 hours));
        payloads[1] = abi.encodeCall(timelock.updateDelay, (47 hours));
        bytes32 salt = _nextSalt();
        bytes32 id = timelock.hashOperationBatch(targets, values, payloads, bytes32(0), salt);
        timelock.scheduleBatch(targets, values, payloads, bytes32(0), salt, DELAY);
        vm.warp(block.timestamp + DELAY);

        vm.expectRevert(abi.encodeWithSelector(VAMSTimelockController.DelayTooShort.selector, 47 hours, DELAY));
        timelock.executeBatch(targets, values, payloads, bytes32(0), salt);

        assertEq(timelock.getMinDelay(), DELAY);
        assertEq(timelock.authorityChangeSequence(), initialSequence);
        assertEq(timelock.authorityConfigCommitment(), initialCommitment);
        assertTrue(timelock.isOperationReady(id));
        assertFalse(timelock.isOperationDone(id));
    }

    function _newTimelock(address admin) private returns (OperationAwareVAMSTimelockControllerV3 created) {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(0);
        created = new OperationAwareVAMSTimelockControllerV3(DELAY, proposers, executors, admin);
    }

    function _newAdminHarness() private returns (OperationAwareVAMSTimelockControllerV3Harness created) {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(0);
        created = new OperationAwareVAMSTimelockControllerV3Harness(DELAY, proposers, executors, address(this));
    }

    function _scheduleSingle(address target, bytes memory payload, bytes32 salt, uint256 delay)
        private returns (bytes32 operationId)
    {
        operationId = timelock.hashOperation(target, 0, payload, bytes32(0), salt);
        timelock.schedule(target, 0, payload, bytes32(0), salt, delay);
    }

    function _nextSalt() private returns (bytes32) { return bytes32(++saltCounter); }

    function _expectedInitialDigest(OperationAwareVAMSTimelockControllerV3 controller)
        private view returns (bytes32)
    {
        address[] memory admins = _sortedPair(address(controller), address(this));
        address[] memory proposers = _sortedPair(address(this), address(0xCAFE));
        address[] memory executors = _sortedPair(address(0), address(0xBEEF));
        bytes32 adminSet = keccak256(abi.encode(
            controller.DEFAULT_ADMIN_ROLE(), controller.getRoleAdmin(controller.DEFAULT_ADMIN_ROLE()), admins
        ));
        bytes32 proposerSet = keccak256(abi.encode(
            controller.PROPOSER_ROLE(), controller.getRoleAdmin(controller.PROPOSER_ROLE()), proposers
        ));
        bytes32 cancellerSet = keccak256(abi.encode(
            controller.CANCELLER_ROLE(), controller.getRoleAdmin(controller.CANCELLER_ROLE()), proposers
        ));
        bytes32 executorSet = keccak256(abi.encode(
            controller.EXECUTOR_ROLE(), controller.getRoleAdmin(controller.EXECUTOR_ROLE()), executors
        ));
        return keccak256(abi.encode(
            controller.INITIAL_ROLE_CONFIG_V3_DOMAIN(), controller.getMinDelay(),
            adminSet, proposerSet, cancellerSet, executorSet
        ));
    }

    function _sortedPair(address a, address b) private pure returns (address[] memory values) {
        values = new address[](2);
        if (uint160(a) <= uint160(b)) {
            values[0] = a;
            values[1] = b;
        } else {
            values[0] = b;
            values[1] = a;
        }
    }
}

/// @dev Test-only target that observes the generation after a previous batch target returns.
contract AuthoritySequenceObserver83 {
    OperationAwareVAMSTimelockControllerV3 private immutable _controller;
    uint64 public observedSequence;
    uint256 public observedDelay;
    constructor(OperationAwareVAMSTimelockControllerV3 controller) { _controller = controller; }
    function observe() external {
        require(msg.sender == address(_controller), "controller only");
        observedSequence = _controller.authorityChangeSequence();
        observedDelay = _controller.getMinDelay();
    }
}