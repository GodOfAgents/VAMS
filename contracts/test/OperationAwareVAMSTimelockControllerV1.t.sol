// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";
import {OperationAwareVAMSTimelockControllerV1 as OperationAwareTimelock} from "../src/governance/OperationAwareVAMSTimelockControllerV1.sol";

contract OperationContextObserver {
    error ContextMissing();
    error WrongContext();
    error BatchNotAllowed();

    OperationAwareTimelock public immutable timelock;
    bytes32 public expectedOperationId;
    bool public expectedBatch;
    bool public enforceExpectedContext;
    bool public rejectBatch;
    uint256 public calls;
    bool public lastActive;
    bytes32 public lastOperationId;
    bool public lastBatch;

    constructor(OperationAwareTimelock timelock_) { timelock = timelock_; }

    function configure(bytes32 id, bool batch, bool enforce, bool rejectBatch_) external {
        expectedOperationId = id;
        expectedBatch = batch;
        enforceExpectedContext = enforce;
        rejectBatch = rejectBatch_;
    }

    function observe() external {
        (bool active, bytes32 operationId, bool batch) = timelock.activeOperationContext();
        if (!active) revert ContextMissing();
        if (enforceExpectedContext && (operationId != expectedOperationId || batch != expectedBatch)) {
            revert WrongContext();
        }
        if (rejectBatch && batch) revert BatchNotAllowed();
        ++calls;
        lastActive = active;
        lastOperationId = operationId;
        lastBatch = batch;
    }
}

contract OperationContextReentryTarget {
    OperationAwareTimelock public immutable timelock;
    bool public lastNestedSucceeded;
    bytes4 public lastNestedError;

    constructor(OperationAwareTimelock timelock_) { timelock = timelock_; }

    function reenterSingle(bool catchFailure) external { _attemptNested(false, catchFailure); }
    function reenterBatch(bool catchFailure) external { _attemptNested(true, catchFailure); }

    function _attemptNested(bool batch, bool catchFailure) private {
        bytes memory callData;
        if (batch) {
            address[] memory targets = new address[](0);
            uint256[] memory values = new uint256[](0);
            bytes[] memory payloads = new bytes[](0);
            callData = abi.encodeWithSignature(
                "executeBatch(address[],uint256[],bytes[],bytes32,bytes32)",
                targets, values, payloads, bytes32(0), bytes32(0)
            );
        } else {
            callData = abi.encodeWithSignature(
                "execute(address,uint256,bytes,bytes32,bytes32)",
                address(0xBEEF), uint256(0), bytes(""), bytes32(0), bytes32(0)
            );
        }
        (bool success, bytes memory returndata) = address(timelock).call(callData);
        lastNestedSucceeded = success;
        if (returndata.length >= 4) {
            bytes4 selector;
            assembly ("memory-safe") { selector := mload(add(returndata, 0x20)) }
            lastNestedError = selector;
        } else {
            lastNestedError = bytes4(0);
        }
        if (!catchFailure && !success) {
            assembly ("memory-safe") { revert(add(returndata, 0x20), mload(returndata)) }
        }
    }
}

/// @dev Intentionally models the old, insufficient readiness-only check; this is a synthetic
///      design-regression fixture and is not evidence of a deployed/live V1 exploit.
contract ReadinessOnlySyntheticConsumer {
    error WatchedOperationNotReady();
    error UnauthorizedTimelockCaller();

    VAMSTimelockController public immutable timelock;
    bytes32 public watchedOperationId;
    uint256 public acceptedCalls;

    constructor(VAMSTimelockController timelock_) { timelock = timelock_; }
    function watch(bytes32 operationId) external { watchedOperationId = operationId; }
    function consume() external {
        if (msg.sender != address(timelock)) revert UnauthorizedTimelockCaller();
        if (!timelock.isOperationReady(watchedOperationId)) revert WatchedOperationNotReady();
        ++acceptedCalls;
    }
}

contract OperationAwareConsentConsumerFixture {
    error WrongActiveOperation();
    error UnauthorizedTimelockCaller();

    OperationAwareTimelock public immutable timelock;
    bytes32 public expectedOperationId;
    uint256 public acceptedCalls;

    constructor(OperationAwareTimelock timelock_) { timelock = timelock_; }
    function expectOperation(bytes32 operationId) external { expectedOperationId = operationId; }
    function consume() external {
        if (msg.sender != address(timelock)) revert UnauthorizedTimelockCaller();
        (bool active, bytes32 operationId, bool batch) = timelock.activeOperationContext();
        if (!active || batch || operationId != expectedOperationId) revert WrongActiveOperation();
        ++acceptedCalls;
    }
}

contract OperationContextRelay {
    OperationAwareConsentConsumerFixture public immutable consumer;
    bool public observedActive;
    bytes32 public observedOperationId;
    bool public observedBatch;
    bool public lastSucceeded;
    bytes4 public lastError;

    constructor(OperationAwareConsentConsumerFixture consumer_) { consumer = consumer_; }

    function relayConsume() external {
        (observedActive, observedOperationId, observedBatch) = consumer.timelock().activeOperationContext();
        (bool success, bytes memory returndata) = address(consumer).call(
            abi.encodeCall(consumer.consume, ())
        );
        lastSucceeded = success;
        if (returndata.length >= 4) {
            bytes4 selector;
            assembly ("memory-safe") { selector := mload(add(returndata, 0x20)) }
            lastError = selector;
        } else {
            lastError = bytes4(0);
        }
    }
}

contract OperationAwareVAMSTimelockControllerV1Tests is Test {
    uint256 private constant DELAY = 48 hours;
    address private constant OTHER_EXECUTOR = address(0xCAFE);

    OperationAwareTimelock private timelock;
    uint256 private saltCounter;

    function setUp() public {
        vm.warp(1_700_000_001);
        timelock = _newTimelock(true);
    }

    function testIdleSingleOperationContextMatchesInheritedHashAndClears() public {
        OperationContextObserver observer = new OperationContextObserver(timelock);
        bytes memory payload = abi.encodeCall(observer.observe, ());
        bytes32 salt = _nextSalt();
        bytes32 operationId = timelock.hashOperation(address(observer), 0, payload, bytes32(0), salt);
        observer.configure(operationId, false, true, false);
        _scheduleSingle(timelock, address(observer), payload, bytes32(0), salt, DELAY);
        _assertIdle(timelock);

        vm.warp(block.timestamp + DELAY);
        timelock.execute(address(observer), 0, payload, bytes32(0), salt);

        assertEq(observer.calls(), 1);
        assertTrue(observer.lastActive());
        assertEq(observer.lastOperationId(), operationId);
        assertFalse(observer.lastBatch());
        _assertIdle(timelock);
    }

    function testBatchPublishesExactBatchHashToEachTargetAndClears() public {
        OperationContextObserver observer = new OperationContextObserver(timelock);
        address[] memory targets = new address[](2);
        uint256[] memory values = new uint256[](2);
        bytes[] memory payloads = new bytes[](2);
        targets[0] = address(observer);
        targets[1] = address(observer);
        payloads[0] = abi.encodeCall(observer.observe, ());
        payloads[1] = abi.encodeCall(observer.observe, ());
        bytes32 salt = _nextSalt();
        bytes32 operationId = timelock.hashOperationBatch(targets, values, payloads, bytes32(0), salt);
        observer.configure(operationId, true, true, false);
        timelock.scheduleBatch(targets, values, payloads, bytes32(0), salt, DELAY);
        _assertIdle(timelock);

        vm.warp(block.timestamp + DELAY);
        timelock.executeBatch(targets, values, payloads, bytes32(0), salt);

        assertEq(observer.calls(), 2);
        assertTrue(observer.lastActive());
        assertEq(observer.lastOperationId(), operationId);
        assertTrue(observer.lastBatch());
        _assertIdle(timelock);
    }

    function testConstructorAndScheduleKeepFortyEightHourFloor() public {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(0);
        vm.expectRevert(abi.encodeWithSelector(VAMSTimelockController.DelayTooShort.selector, 47 hours, 48 hours));
        new OperationAwareTimelock(47 hours, proposers, executors, address(0));

        OperationContextObserver observer = new OperationContextObserver(timelock);
        bytes memory payload = abi.encodeCall(observer.observe, ());
        bytes32 salt = _nextSalt();
        vm.expectRevert(abi.encodeWithSelector(TimelockController.TimelockInsufficientDelay.selector, 47 hours, DELAY));
        timelock.schedule(address(observer), 0, payload, bytes32(0), salt, 47 hours);
        _assertIdle(timelock);
    }

    function testGovernanceUpdateDelayKeepsFloorAndAllowsIncrease() public {
        bytes memory belowFloor = abi.encodeCall(timelock.updateDelay, (47 hours));
        bytes32 belowSalt = _nextSalt();
        bytes32 belowId = _scheduleSingle(timelock, address(timelock), belowFloor, bytes32(0), belowSalt, DELAY);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(abi.encodeWithSelector(VAMSTimelockController.DelayTooShort.selector, 47 hours, DELAY));
        timelock.execute(address(timelock), 0, belowFloor, bytes32(0), belowSalt);
        assertTrue(timelock.isOperationReady(belowId));
        _assertIdle(timelock);

        bytes memory raiseDelay = abi.encodeCall(timelock.updateDelay, (72 hours));
        bytes32 raiseSalt = _nextSalt();
        bytes32 raiseId = _scheduleSingle(timelock, address(timelock), raiseDelay, bytes32(0), raiseSalt, DELAY);
        vm.warp(block.timestamp + DELAY);
        timelock.execute(address(timelock), 0, raiseDelay, bytes32(0), raiseSalt);
        assertEq(timelock.getMinDelay(), 72 hours);
        assertTrue(timelock.isOperationDone(raiseId));
        _assertIdle(timelock);
    }

    function testEarlyExecutionAndUnfinishedPredecessorDoNotExposeOrRetainContext() public {
        OperationContextObserver observer = new OperationContextObserver(timelock);
        bytes memory payload = abi.encodeCall(observer.observe, ());
        bytes32 earlySalt = _nextSalt();
        bytes32 earlyId = _scheduleSingle(timelock, address(observer), payload, bytes32(0), earlySalt, DELAY);
        vm.expectRevert(abi.encodeWithSelector(TimelockController.TimelockUnexpectedOperationState.selector, earlyId, bytes32(uint256(4))));
        timelock.execute(address(observer), 0, payload, bytes32(0), earlySalt);
        _assertIdle(timelock);
        assertTrue(timelock.isOperationPending(earlyId));

        vm.warp(block.timestamp + DELAY);
        timelock.execute(address(observer), 0, payload, bytes32(0), earlySalt);
        _assertIdle(timelock);

        bytes32 predecessor = bytes32(uint256(0xABCDEF));
        bytes32 predSalt = _nextSalt();
        bytes32 predId = _scheduleSingle(timelock, address(observer), payload, predecessor, predSalt, DELAY);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(abi.encodeWithSelector(TimelockController.TimelockUnexecutedPredecessor.selector, predecessor));
        timelock.execute(address(observer), 0, payload, predecessor, predSalt);
        _assertIdle(timelock);
        assertTrue(timelock.isOperationReady(predId));
    }

    function testCanceledOperationCannotExposeContext() public {
        OperationContextObserver observer = new OperationContextObserver(timelock);
        bytes memory payload = abi.encodeCall(observer.observe, ());
        bytes32 salt = _nextSalt();
        bytes32 operationId = _scheduleSingle(timelock, address(observer), payload, bytes32(0), salt, DELAY);
        timelock.cancel(operationId);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(abi.encodeWithSelector(TimelockController.TimelockUnexpectedOperationState.selector, operationId, bytes32(uint256(4))));
        timelock.execute(address(observer), 0, payload, bytes32(0), salt);
        _assertIdle(timelock);
        assertEq(observer.calls(), 0);
    }

    function testRevertedTargetRollsBackContextAndLeavesOperationReady() public {
        RevertingOperationTarget target = new RevertingOperationTarget();
        bytes memory payload = abi.encodeCall(target.fail, ());
        bytes32 salt = _nextSalt();
        bytes32 operationId = _scheduleSingle(timelock, address(target), payload, bytes32(0), salt, DELAY);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(RevertingOperationTarget.TargetFailure.selector);
        timelock.execute(address(target), 0, payload, bytes32(0), salt);
        _assertIdle(timelock);
        assertTrue(timelock.isOperationReady(operationId));
    }

    function testRestrictedExecutorAndOpenExecutorRolesRemainInherited() public {
        OperationAwareTimelock closed = _newTimelock(false);
        OperationContextObserver closedObserver = new OperationContextObserver(closed);
        bytes memory closedPayload = abi.encodeCall(closedObserver.observe, ());
        bytes32 closedSalt = _nextSalt();
        bytes32 closedId = _scheduleSingle(closed, address(closedObserver), closedPayload, bytes32(0), closedSalt, DELAY);
        closedObserver.configure(closedId, false, true, false);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert();
        vm.prank(OTHER_EXECUTOR);
        closed.execute(address(closedObserver), 0, closedPayload, bytes32(0), closedSalt);
        _assertIdle(closed);
        assertTrue(closed.isOperationReady(closedId));
        closed.execute(address(closedObserver), 0, closedPayload, bytes32(0), closedSalt);
        _assertIdle(closed);
        assertEq(closedObserver.calls(), 1);

        OperationContextObserver openObserver = new OperationContextObserver(timelock);
        bytes memory openPayload = abi.encodeCall(openObserver.observe, ());
        bytes32 openSalt = _nextSalt();
        bytes32 openId = _scheduleSingle(timelock, address(openObserver), openPayload, bytes32(0), openSalt, DELAY);
        openObserver.configure(openId, false, true, false);
        vm.warp(block.timestamp + DELAY);
        vm.prank(OTHER_EXECUTOR);
        timelock.execute(address(openObserver), 0, openPayload, bytes32(0), openSalt);
        assertEq(openObserver.calls(), 1);
        _assertIdle(timelock);
    }

    function testAllCaughtSingleAndBatchNestedExecutionCombinationsAreRejected() public {
        OperationContextReentryTarget target = new OperationContextReentryTarget(timelock);
        for (uint256 outerBatch; outerBatch < 2; ++outerBatch) {
            for (uint256 innerBatch; innerBatch < 2; ++innerBatch) {
                bytes memory payload = innerBatch == 0
                    ? abi.encodeCall(target.reenterSingle, (true))
                    : abi.encodeCall(target.reenterBatch, (true));
                bytes32 salt = _nextSalt();
                if (outerBatch == 0) {
                    _scheduleSingle(timelock, address(target), payload, bytes32(0), salt, DELAY);
                    vm.warp(block.timestamp + DELAY);
                    timelock.execute(address(target), 0, payload, bytes32(0), salt);
                } else {
                    address[] memory targets = new address[](1);
                    uint256[] memory values = new uint256[](1);
                    bytes[] memory payloads = new bytes[](1);
                    targets[0] = address(target);
                    payloads[0] = payload;
                    timelock.scheduleBatch(targets, values, payloads, bytes32(0), salt, DELAY);
                    vm.warp(block.timestamp + DELAY);
                    timelock.executeBatch(targets, values, payloads, bytes32(0), salt);
                }
                assertFalse(target.lastNestedSucceeded());
        assertEq(target.lastNestedError(), OperationAwareTimelock.NestedOperationExecution.selector);
                _assertIdle(timelock);
            }
        }
    }

    function testUncaughtNestedExecutionRevertsOuterAndRollsBackContext() public {
        OperationContextReentryTarget target = new OperationContextReentryTarget(timelock);
        bytes memory payload = abi.encodeCall(target.reenterBatch, (false));
        bytes32 salt = _nextSalt();
        bytes32 operationId = _scheduleSingle(timelock, address(target), payload, bytes32(0), salt, DELAY);
        vm.warp(block.timestamp + DELAY);
        vm.expectRevert(OperationAwareTimelock.NestedOperationExecution.selector);
        timelock.execute(address(target), 0, payload, bytes32(0), salt);
        _assertIdle(timelock);
        assertTrue(timelock.isOperationReady(operationId));
    }

    function testReadinessOnlySyntheticConsumerShowsSingletonBatchAmbiguity() public {
        ReadinessOnlySyntheticConsumer consumer = new ReadinessOnlySyntheticConsumer(timelock);
        bytes memory payload = abi.encodeCall(consumer.consume, ());
        bytes32 singleSalt = _nextSalt();
        bytes32 singleId = timelock.hashOperation(address(consumer), 0, payload, bytes32(0), singleSalt);
        consumer.watch(singleId);
        vm.expectRevert(ReadinessOnlySyntheticConsumer.UnauthorizedTimelockCaller.selector);
        consumer.consume();
        _scheduleSingle(timelock, address(consumer), payload, bytes32(0), singleSalt, DELAY);

        address[] memory targets = new address[](1);
        uint256[] memory values = new uint256[](1);
        bytes[] memory payloads = new bytes[](1);
        targets[0] = address(consumer);
        payloads[0] = payload;
        bytes32 batchSalt = _nextSalt();
        bytes32 batchId = timelock.hashOperationBatch(targets, values, payloads, bytes32(0), batchSalt);
        timelock.scheduleBatch(targets, values, payloads, bytes32(0), batchSalt, DELAY);
        assertTrue(batchId != singleId);
        vm.warp(block.timestamp + DELAY);

        // Synthetic old consumer checks only that the separately queued singleton is ready.
        timelock.executeBatch(targets, values, payloads, bytes32(0), batchSalt);
        assertEq(consumer.acceptedCalls(), 1);
        assertTrue(timelock.isOperationReady(singleId));
        _assertIdle(timelock);
    }

    function testContextBoundSyntheticConsumerRejectsBatchDespiteReadySingleton() public {
        OperationAwareConsentConsumerFixture consumer = new OperationAwareConsentConsumerFixture(timelock);
        bytes memory payload = abi.encodeCall(consumer.consume, ());
        bytes32 singleSalt = _nextSalt();
        bytes32 singleId = timelock.hashOperation(address(consumer), 0, payload, bytes32(0), singleSalt);
        consumer.expectOperation(singleId);
        _scheduleSingle(timelock, address(consumer), payload, bytes32(0), singleSalt, DELAY);

        address[] memory targets = new address[](1);
        uint256[] memory values = new uint256[](1);
        bytes[] memory payloads = new bytes[](1);
        targets[0] = address(consumer);
        payloads[0] = payload;
        bytes32 batchSalt = _nextSalt();
        bytes32 batchId = timelock.hashOperationBatch(targets, values, payloads, bytes32(0), batchSalt);
        timelock.scheduleBatch(targets, values, payloads, bytes32(0), batchSalt, DELAY);
        assertTrue(batchId != singleId);
        vm.warp(block.timestamp + DELAY);

        vm.expectRevert(OperationAwareConsentConsumerFixture.WrongActiveOperation.selector);
        timelock.executeBatch(targets, values, payloads, bytes32(0), batchSalt);
        _assertIdle(timelock);
        assertTrue(timelock.isOperationReady(singleId));
        assertTrue(timelock.isOperationReady(batchId));
        assertEq(consumer.acceptedCalls(), 0);

        timelock.execute(address(consumer), 0, payload, bytes32(0), singleSalt);
        assertEq(consumer.acceptedCalls(), 1);
        _assertIdle(timelock);
    }

    function testContextConsumerRejectsDirectCaller() public {
        OperationAwareConsentConsumerFixture consumer = new OperationAwareConsentConsumerFixture(timelock);
        consumer.expectOperation(bytes32(uint256(123)));
        vm.expectRevert(OperationAwareConsentConsumerFixture.UnauthorizedTimelockCaller.selector);
        consumer.consume();
        assertEq(consumer.acceptedCalls(), 0);
        _assertIdle(timelock);
    }

    function testContextConsumerRejectsRelayWhileAnOperationIsActive() public {
        OperationAwareConsentConsumerFixture consumer = new OperationAwareConsentConsumerFixture(timelock);
        OperationContextRelay relay = new OperationContextRelay(consumer);
        bytes memory payload = abi.encodeCall(relay.relayConsume, ());
        bytes32 salt = _nextSalt();
        bytes32 operationId = _scheduleSingle(timelock, address(relay), payload, bytes32(0), salt, DELAY);
        consumer.expectOperation(operationId);

        vm.warp(block.timestamp + DELAY);
        timelock.execute(address(relay), 0, payload, bytes32(0), salt);

        assertTrue(relay.observedActive());
        assertEq(relay.observedOperationId(), operationId);
        assertFalse(relay.observedBatch());
        assertFalse(relay.lastSucceeded());
        assertEq(relay.lastError(), OperationAwareConsentConsumerFixture.UnauthorizedTimelockCaller.selector);
        assertEq(consumer.acceptedCalls(), 0);
        _assertIdle(timelock);
    }

    function _newTimelock(bool openExecutor) private returns (OperationAwareTimelock created) {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = openExecutor ? address(0) : address(this);
        created = new OperationAwareTimelock(DELAY, proposers, executors, address(0));
    }

    function _scheduleSingle(
        OperationAwareTimelock targetTimelock,
        address target,
        bytes memory payload,
        bytes32 predecessor,
        bytes32 salt,
        uint256 delay
    ) private returns (bytes32 operationId) {
        operationId = targetTimelock.hashOperation(target, 0, payload, predecessor, salt);
        targetTimelock.schedule(target, 0, payload, predecessor, salt, delay);
    }

    function _nextSalt() private returns (bytes32) { return bytes32(++saltCounter); }

    function _assertIdle(OperationAwareTimelock targetTimelock) private view {
        (bool active, bytes32 operationId, bool batch) = targetTimelock.activeOperationContext();
        assertFalse(active);
        assertEq(operationId, bytes32(0));
        assertFalse(batch);
    }
}

contract RevertingOperationTarget {
    error TargetFailure();
    function fail() external pure { revert TargetFailure(); }
}
