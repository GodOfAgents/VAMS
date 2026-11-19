// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {ITwoPhaseCommitManager} from "../../src/economic/ITwoPhaseCommitManager.sol";
import {TwoPhaseCommitManager} from "../../src/economic/TwoPhaseCommitManager.sol";

/// @dev Synthetic local escrow boundary for callback tests. It is not a live
/// escrow implementation and does not custody tokens or attest service work.
contract TwoPhaseCallbackEscrowFixture {
    error SyntheticLockFailure(uint256 index);
    error SyntheticRefundBeforeExpiry(bytes32 escrowId, uint256 expiresAt);

    struct Observation {
        uint256 callbackIndex;
        uint256 visibleEscrowCount;
        uint256 visiblePreparedCount;
        uint256 visibleServiceCount;
        uint256 visibleWorkflowState;
        uint256 visibleAgentWorkflowCount;
        uint256 visibleTotalWorkflows;
        bool currentServiceRegistered;
        bool visiblePrefixMatches;
        bool nestedInitiateSucceeded;
        bytes4 nestedInitiateError;
        bool currentPrepareSucceeded;
        bytes4 currentPrepareError;
        bool priorPrepareSucceeded;
        bytes4 priorPrepareError;
        bool abortSucceeded;
        bytes4 abortError;
        bool commitSucceeded;
        bytes4 commitError;
        uint256 preparedCountAfterCallbacks;
    }

    ITwoPhaseCommitManager public manager;
    bytes32 public workflowId;
    bytes32 public secretHash;
    uint256 public failAtIndex = type(uint256).max;
    uint256 public calls;
    uint256 public refundCalls;
    bool public abortProbeEnabled;

    bytes32[] private _escrowIds;
    Observation[] private _observations;
    mapping(bytes32 => uint256) public expiryOf;

    function configure(
        ITwoPhaseCommitManager manager_,
        bytes32 workflowId_,
        bytes32 secretHash_,
        uint256 failAtIndex_
    ) external {
        manager = manager_;
        workflowId = workflowId_;
        secretHash = secretHash_;
        failAtIndex = failAtIndex_;
        abortProbeEnabled = true;
    }

    function setAbortProbeEnabled(bool enabled) external {
        abortProbeEnabled = enabled;
    }

    function initiateAsAgent(
        bytes32 workflowId_,
        ITwoPhaseCommitManager.ServiceRequest[] calldata services,
        bytes32 commitSecretHash,
        uint256 prepareWindow
    ) external returns (bytes32[] memory) {
        return manager.initiateWorkflow(workflowId_, services, commitSecretHash, prepareWindow);
    }

    function abortAsAgent(bytes32 workflowId_) external {
        manager.abortWorkflow(workflowId_, "synthetic agent abort");
    }

    function refundAsAgent(bytes32 workflowId_, bytes32 escrowId) external {
        manager.claimRefund(workflowId_, escrowId);
    }

    function observationCount() external view returns (uint256) {
        return _observations.length;
    }

    function lockEscrow(
        address provider,
        uint256 amount,
        uint256 nonce,
        uint256 validForSeconds,
        bytes32,
        bytes32
    ) external returns (bytes32 escrowId) {
        uint256 index = calls++;
        if (index == failAtIndex) revert SyntheticLockFailure(index);

        escrowId = keccak256(abi.encode(block.chainid, address(this), msg.sender, provider, amount, nonce));
        _escrowIds.push(escrowId);
        expiryOf[escrowId] = block.timestamp + validForSeconds;
        _probeDuringLock(index, escrowId);
    }

    function refundExpiredEscrow(bytes32 escrowId) external {
        uint256 expiry = expiryOf[escrowId];
        if (expiry == 0 || block.timestamp <= expiry) {
            revert SyntheticRefundBeforeExpiry(escrowId, expiry);
        }
        ++refundCalls;
    }

    function escrowIdAt(uint256 index) external view returns (bytes32) {
        return _escrowIds[index];
    }

    function recordedEscrowCount() external view returns (uint256) {
        return _escrowIds.length;
    }

    function observation(uint256 index) external view returns (Observation memory) {
        return _observations[index];
    }

    function _probeDuringLock(uint256 index, bytes32 currentEscrowId) private {
        Observation memory o;
        o.callbackIndex = index;

        {
        ITwoPhaseCommitManager.Workflow memory wf = manager.getWorkflow(workflowId);
        bytes32[] memory visibleEscrows = manager.getWorkflowEscrows(workflowId);
        o.visibleEscrowCount = visibleEscrows.length;
        o.visiblePreparedCount = wf.preparedCount;
        o.visibleServiceCount = wf.serviceCount;
        o.visibleWorkflowState = uint256(wf.state);
        TwoPhaseCommitManager concreteManager = TwoPhaseCommitManager(address(manager));
        o.visibleAgentWorkflowCount = concreteManager.getAgentWorkflows(wf.agent).length;
        o.visibleTotalWorkflows = concreteManager.totalWorkflows();
        o.currentServiceRegistered = manager.getService(workflowId, currentEscrowId).escrowId != bytes32(0);
        o.visiblePrefixMatches = visibleEscrows.length == index;
        for (uint256 i = 0; i < visibleEscrows.length && o.visiblePrefixMatches; ++i) {
            o.visiblePrefixMatches = visibleEscrows[i] == _escrowIds[i];
        }
        }

        {
        ITwoPhaseCommitManager.ServiceRequest[] memory nestedServices =
            new ITwoPhaseCommitManager.ServiceRequest[](1);
        nestedServices[0] = ITwoPhaseCommitManager.ServiceRequest({
            provider: address(0xCAFE), amount: 1, serviceType: bytes32(uint256(0xCAFE)), timeout: 0
        });
        (bool nestedOk, bytes memory nestedResult) = address(manager).call(
            abi.encodeWithSelector(
                ITwoPhaseCommitManager.initiateWorkflow.selector,
                workflowId,
                nestedServices,
                secretHash,
                uint256(0)
            )
        );
        o.nestedInitiateSucceeded = nestedOk;
        o.nestedInitiateError = _selector(nestedResult);
        }

        {
        (bool currentOk, bytes memory currentResult) = address(manager).call(
            abi.encodeWithSelector(
                ITwoPhaseCommitManager.markServicePrepared.selector, workflowId, currentEscrowId
            )
        );
        o.currentPrepareSucceeded = currentOk;
        o.currentPrepareError = _selector(currentResult);
        }

        if (index > 0) {
            (bool priorOk, bytes memory priorResult) = address(manager).call(
                abi.encodeWithSelector(
                    ITwoPhaseCommitManager.markServicePrepared.selector, workflowId, _escrowIds[index - 1]
                )
            );
            o.priorPrepareSucceeded = priorOk;
            o.priorPrepareError = _selector(priorResult);
        }

        if (abortProbeEnabled) {
            (bool abortOk, bytes memory abortResult) = address(manager).call(
                abi.encodeWithSelector(ITwoPhaseCommitManager.abortWorkflow.selector, workflowId, "synthetic callback")
            );
            o.abortSucceeded = abortOk;
            o.abortError = _selector(abortResult);
        }

        {
        (bool commitOk, bytes memory commitResult) = address(manager).call(
            abi.encodeWithSelector(
                ITwoPhaseCommitManager.commitWorkflow.selector, workflowId, bytes32(uint256(0x5151))
            )
        );
        o.commitSucceeded = commitOk;
        o.commitError = _selector(commitResult);
        }
        o.preparedCountAfterCallbacks = manager.getWorkflow(workflowId).preparedCount;
        _observations.push(o);
    }

    function _selector(bytes memory result) private pure returns (bytes4 selector) {
        if (result.length >= 4) {
            assembly ("memory-safe") {
                selector := mload(add(result, 32))
            }
        }
    }
}

/// @notice Adversarial callback and lifecycle tests for the production manager.
/// The proxy, escrow manager, token address, providers, and all workflow data
/// are local synthetic fixtures; this suite grants no live role or activation.
contract TwoPhaseCommitCallbackRegressionTest is Test {
    bytes32 private constant SECRET = keccak256("local two phase callback test secret");
    bytes32 private constant WORKFLOW = keccak256("callback-observation-workflow");
    bytes32 private constant RETRY_WORKFLOW = keccak256("callback-failure-retry-workflow");
    bytes32 private constant EXPIRY_WORKFLOW = keccak256("callback-expiry-workflow");
    bytes32 private constant CALLBACK_ABORT_WORKFLOW = keccak256("callback-authorized-abort-workflow");
    bytes32 private constant IMMEDIATE_ABORT_WORKFLOW = keccak256("immediate-authorized-abort-workflow");
    bytes32 private constant SERVICE_A = keccak256("service-a");
    bytes32 private constant SERVICE_B = keccak256("service-b");
    bytes32 private constant SERVICE_C = keccak256("service-c");
    address private constant PROVIDER_A = address(0xA0A);
    address private constant PROVIDER_B = address(0xB0B);
    address private constant PROVIDER_C = address(0xC0C);

    bytes4 private constant REENTRANCY_ERROR = bytes4(keccak256("ReentrancyGuardReentrantCall()"));
    bytes4 private constant SERVICE_NOT_FOUND_ERROR = bytes4(keccak256("ServiceNotFound(bytes32,bytes32)"));
    bytes4 private constant UNAUTHORIZED_ERROR = bytes4(keccak256("UnauthorizedCaller()"));
    bytes4 private constant INVALID_WORKFLOW_STATE_ERROR = bytes4(keccak256("InvalidWorkflowState(bytes32,uint8,uint8)"));

    ITwoPhaseCommitManager private manager;
    TwoPhaseCallbackEscrowFixture private escrow;

    function setUp() public {
        vm.warp(1_000_000);
        escrow = new TwoPhaseCallbackEscrowFixture();
        TwoPhaseCommitManager implementation = new TwoPhaseCommitManager();
        ERC1967Proxy proxy = new ERC1967Proxy(
            address(implementation),
            abi.encodeCall(TwoPhaseCommitManager.initialize, (address(this), address(this), address(escrow)))
        );
        manager = ITwoPhaseCommitManager(address(proxy));
    }

    function test_callbacksSeePartialLedgerButOnlyRegisteredAuthorizedProviderCanPrepare() public {
        escrow.configure(manager, WORKFLOW, keccak256(abi.encodePacked(SECRET)), type(uint256).max);
        ITwoPhaseCommitManager.ServiceRequest[] memory requests = _threeServices(address(escrow));

        bytes32[] memory ids = manager.initiateWorkflow(WORKFLOW, requests, keccak256(abi.encodePacked(SECRET)), 0);

        assertEq(ids.length, 3);
        assertEq(escrow.calls(), 3);
        assertEq(manager.getWorkflowEscrows(WORKFLOW).length, 3);
        assertEq(TwoPhaseCommitManager(address(manager)).getAgentWorkflows(address(this)).length, 1);
        assertEq(TwoPhaseCommitManager(address(manager)).totalWorkflows(), 1);

        for (uint256 i = 0; i < 3; ++i) {
            TwoPhaseCallbackEscrowFixture.Observation memory o = escrow.observation(i);
            assertEq(o.callbackIndex, i);
            assertEq(o.visibleEscrowCount, i);
            assertEq(o.visibleServiceCount, 3);
            assertEq(o.visibleWorkflowState, uint256(ITwoPhaseCommitManager.WorkflowState.PENDING));
            assertEq(o.visibleAgentWorkflowCount, 0);
            assertEq(o.visibleTotalWorkflows, 0);
            assertFalse(o.currentServiceRegistered);
            assertTrue(o.visiblePrefixMatches);
            assertFalse(o.nestedInitiateSucceeded);
            assertEq(o.nestedInitiateError, REENTRANCY_ERROR);
            assertFalse(o.currentPrepareSucceeded);
            assertEq(o.currentPrepareError, SERVICE_NOT_FOUND_ERROR);
            assertFalse(o.abortSucceeded);
            assertEq(o.abortError, UNAUTHORIZED_ERROR);
            assertFalse(o.commitSucceeded);
            assertEq(o.commitError, UNAUTHORIZED_ERROR);
        }

        TwoPhaseCallbackEscrowFixture.Observation memory second = escrow.observation(1);
        assertEq(second.visiblePreparedCount, 0);
        assertTrue(second.priorPrepareSucceeded);
        assertEq(second.priorPrepareError, bytes4(0));
        assertEq(second.preparedCountAfterCallbacks, 1);

        TwoPhaseCallbackEscrowFixture.Observation memory third = escrow.observation(2);
        assertEq(third.visiblePreparedCount, 1);
        assertFalse(third.priorPrepareSucceeded);
        assertEq(third.priorPrepareError, UNAUTHORIZED_ERROR);
        assertEq(third.preparedCountAfterCallbacks, 1);

        ITwoPhaseCommitManager.Workflow memory wf = manager.getWorkflow(WORKFLOW);
        assertEq(uint256(wf.state), uint256(ITwoPhaseCommitManager.WorkflowState.PENDING));
        assertEq(wf.preparedCount, 1);

        vm.prank(PROVIDER_B);
        manager.markServicePrepared(WORKFLOW, ids[1]);
        vm.prank(PROVIDER_C);
        manager.markServicePrepared(WORKFLOW, ids[2]);
        wf = manager.getWorkflow(WORKFLOW);
        assertEq(uint256(wf.state), uint256(ITwoPhaseCommitManager.WorkflowState.PREPARED));
        assertEq(wf.preparedCount, 3);

        manager.commitWorkflow(WORKFLOW, SECRET);
        wf = manager.getWorkflow(WORKFLOW);
        assertEq(uint256(wf.state), uint256(ITwoPhaseCommitManager.WorkflowState.COMMITTED));
        assertEq(TwoPhaseCommitManager(address(manager)).getRevealedSecret(WORKFLOW), SECRET);
    }

    function test_escrowRevertRollsBackPartialWorkflowAndAllowsLaterInitiation() public {
        escrow.configure(manager, RETRY_WORKFLOW, keccak256(abi.encodePacked(SECRET)), 2);
        ITwoPhaseCommitManager.ServiceRequest[] memory requests = _threeServices(address(escrow));
        uint256 firstNonce = uint256(keccak256(abi.encodePacked(RETRY_WORKFLOW, uint256(0))));
        bytes32 firstEscrowId = keccak256(
            abi.encode(block.chainid, address(escrow), address(manager), address(escrow), uint256(11), firstNonce)
        );
        vm.expectCall(
            address(manager),
            abi.encodeWithSelector(ITwoPhaseCommitManager.markServicePrepared.selector, RETRY_WORKFLOW, firstEscrowId)
        );
        vm.expectRevert(abi.encodeWithSelector(TwoPhaseCallbackEscrowFixture.SyntheticLockFailure.selector, 2));
        manager.initiateWorkflow(RETRY_WORKFLOW, requests, keccak256(abi.encodePacked(SECRET)), 0);

        ITwoPhaseCommitManager.Workflow memory revertedWorkflow = manager.getWorkflow(RETRY_WORKFLOW);
        assertEq(revertedWorkflow.createdAt, 0);
        assertEq(manager.getWorkflowEscrows(RETRY_WORKFLOW).length, 0);
        assertEq(TwoPhaseCommitManager(address(manager)).getAgentWorkflows(address(this)).length, 0);
        assertEq(TwoPhaseCommitManager(address(manager)).totalWorkflows(), 0);
        assertEq(escrow.calls(), 0);
        assertEq(escrow.recordedEscrowCount(), 0);
        assertEq(escrow.observationCount(), 0);
        assertEq(escrow.expiryOf(firstEscrowId), 0);

        escrow.configure(manager, RETRY_WORKFLOW, keccak256(abi.encodePacked(SECRET)), type(uint256).max);
        bytes32[] memory ids = manager.initiateWorkflow(RETRY_WORKFLOW, requests, keccak256(abi.encodePacked(SECRET)), 0);
        assertEq(ids.length, 3);
        assertEq(ids[0], firstEscrowId);
        assertEq(manager.getWorkflowEscrows(RETRY_WORKFLOW).length, 3);
        assertEq(TwoPhaseCommitManager(address(manager)).totalWorkflows(), 1);
        TwoPhaseCallbackEscrowFixture.Observation memory second = escrow.observation(1);
        assertTrue(second.priorPrepareSucceeded);
        assertEq(second.preparedCountAfterCallbacks, 1);
    }

    function test_authorizedAgentAbortDuringCallbackMatchesImmediateAbortAndRefundsOnce() public {
        bytes32 secretHash = keccak256(abi.encodePacked(SECRET));
        ITwoPhaseCommitManager.ServiceRequest[] memory requests = _threeServices(PROVIDER_A);

        escrow.configure(manager, CALLBACK_ABORT_WORKFLOW, secretHash, type(uint256).max);
        bytes32[] memory callbackIds = escrow.initiateAsAgent(
            CALLBACK_ABORT_WORKFLOW, requests, secretHash, 60
        );
        assertEq(callbackIds.length, 3);
        ITwoPhaseCommitManager.Workflow memory callbackWorkflow = manager.getWorkflow(CALLBACK_ABORT_WORKFLOW);
        assertEq(callbackWorkflow.agent, address(escrow));
        assertEq(uint256(callbackWorkflow.state), uint256(ITwoPhaseCommitManager.WorkflowState.ABORTED));
        assertEq(callbackWorkflow.preparedCount, 0);
        assertEq(TwoPhaseCommitManager(address(manager)).getAgentWorkflows(address(escrow)).length, 1);
        assertEq(TwoPhaseCommitManager(address(manager)).getRevealedSecret(CALLBACK_ABORT_WORKFLOW), bytes32(0));
        _assertPendingEscrowRows(CALLBACK_ABORT_WORKFLOW, callbackIds, requests);

        TwoPhaseCallbackEscrowFixture.Observation memory firstCallback = escrow.observation(0);
        assertTrue(firstCallback.abortSucceeded);
        assertEq(firstCallback.abortError, bytes4(0));
        assertEq(firstCallback.commitError, INVALID_WORKFLOW_STATE_ERROR);
        TwoPhaseCallbackEscrowFixture.Observation memory laterCallback = escrow.observation(1);
        assertFalse(laterCallback.abortSucceeded);
        assertEq(laterCallback.abortError, INVALID_WORKFLOW_STATE_ERROR);

        uint256 lastExpiry;
        for (uint256 i = 0; i < callbackIds.length; ++i) {
            uint256 expiry = escrow.expiryOf(callbackIds[i]);
            if (expiry > lastExpiry) lastExpiry = expiry;
        }
        vm.warp(lastExpiry + 1);
        for (uint256 i = 0; i < callbackIds.length; ++i) {
            escrow.refundAsAgent(CALLBACK_ABORT_WORKFLOW, callbackIds[i]);
        }
        assertEq(escrow.refundCalls(), 3);
        vm.expectRevert(
            abi.encodeWithSelector(ITwoPhaseCommitManager.ServiceAlreadyPrepared.selector, callbackIds[0])
        );
        escrow.refundAsAgent(CALLBACK_ABORT_WORKFLOW, callbackIds[0]);
        assertEq(escrow.refundCalls(), 3);

        TwoPhaseCallbackEscrowFixture immediateEscrow = new TwoPhaseCallbackEscrowFixture();
        TwoPhaseCommitManager(address(manager)).setEscrowManager(address(immediateEscrow));
        immediateEscrow.configure(manager, IMMEDIATE_ABORT_WORKFLOW, secretHash, type(uint256).max);
        immediateEscrow.setAbortProbeEnabled(false);
        bytes32[] memory immediateIds = immediateEscrow.initiateAsAgent(
            IMMEDIATE_ABORT_WORKFLOW, requests, secretHash, 60
        );
        ITwoPhaseCommitManager.Workflow memory beforeAbort = manager.getWorkflow(IMMEDIATE_ABORT_WORKFLOW);
        assertEq(uint256(beforeAbort.state), uint256(ITwoPhaseCommitManager.WorkflowState.PENDING));
        assertEq(beforeAbort.preparedCount, 0);
        immediateEscrow.abortAsAgent(IMMEDIATE_ABORT_WORKFLOW);
        ITwoPhaseCommitManager.Workflow memory immediateWorkflow = manager.getWorkflow(IMMEDIATE_ABORT_WORKFLOW);
        assertEq(immediateWorkflow.agent, address(immediateEscrow));
        assertEq(uint256(immediateWorkflow.state), uint256(ITwoPhaseCommitManager.WorkflowState.ABORTED));
        assertEq(immediateWorkflow.preparedCount, callbackWorkflow.preparedCount);
        assertEq(TwoPhaseCommitManager(address(manager)).getRevealedSecret(IMMEDIATE_ABORT_WORKFLOW), bytes32(0));
        _assertPendingEscrowRows(IMMEDIATE_ABORT_WORKFLOW, immediateIds, requests);
    }

    function test_expiredWorkflowRefundWaitsForEscrowExpiryAndThenRecovers() public {
        escrow.configure(manager, EXPIRY_WORKFLOW, keccak256(abi.encodePacked(SECRET)), type(uint256).max);
        ITwoPhaseCommitManager.ServiceRequest[] memory requests = _twoServices(PROVIDER_B, PROVIDER_C);
        bytes32[] memory ids = manager.initiateWorkflow(
            EXPIRY_WORKFLOW, requests, keccak256(abi.encodePacked(SECRET)), 60
        );

        ITwoPhaseCommitManager.Workflow memory wf = manager.getWorkflow(EXPIRY_WORKFLOW);
        vm.warp(wf.prepareDeadline + 1);
        manager.processExpiredWorkflow(EXPIRY_WORKFLOW);
        wf = manager.getWorkflow(EXPIRY_WORKFLOW);
        assertEq(uint256(wf.state), uint256(ITwoPhaseCommitManager.WorkflowState.EXPIRED));

        uint256 escrowExpiry = escrow.expiryOf(ids[0]);
        vm.expectRevert(
            abi.encodeWithSelector(TwoPhaseCallbackEscrowFixture.SyntheticRefundBeforeExpiry.selector, ids[0], escrowExpiry)
        );
        manager.claimRefund(EXPIRY_WORKFLOW, ids[0]);
        ITwoPhaseCommitManager.ServiceEntry memory stillPending = manager.getService(EXPIRY_WORKFLOW, ids[0]);
        assertEq(uint256(stillPending.state), uint256(ITwoPhaseCommitManager.ServiceState.PENDING));

        vm.warp(escrowExpiry + 1);
        manager.claimRefund(EXPIRY_WORKFLOW, ids[0]);
        manager.claimRefund(EXPIRY_WORKFLOW, ids[1]);
        assertEq(escrow.refundCalls(), 2);
        assertEq(
            uint256(manager.getService(EXPIRY_WORKFLOW, ids[0]).state),
            uint256(ITwoPhaseCommitManager.ServiceState.REFUNDED)
        );
        assertEq(
            uint256(manager.getService(EXPIRY_WORKFLOW, ids[1]).state),
            uint256(ITwoPhaseCommitManager.ServiceState.REFUNDED)
        );
    }

    function _threeServices(address firstProvider)
        private
        pure
        returns (ITwoPhaseCommitManager.ServiceRequest[] memory requests)
    {
        requests = new ITwoPhaseCommitManager.ServiceRequest[](3);
        requests[0] = ITwoPhaseCommitManager.ServiceRequest(firstProvider, 11, SERVICE_A, 0);
        requests[1] = ITwoPhaseCommitManager.ServiceRequest(PROVIDER_B, 13, SERVICE_B, 0);
        requests[2] = ITwoPhaseCommitManager.ServiceRequest(PROVIDER_C, 17, SERVICE_C, 0);
    }

    function _twoServices(address providerA, address providerB)
        private
        pure
        returns (ITwoPhaseCommitManager.ServiceRequest[] memory requests)
    {
        requests = new ITwoPhaseCommitManager.ServiceRequest[](2);
        requests[0] = ITwoPhaseCommitManager.ServiceRequest(providerA, 11, SERVICE_A, 0);
        requests[1] = ITwoPhaseCommitManager.ServiceRequest(providerB, 13, SERVICE_B, 0);
    }

    function _assertPendingEscrowRows(
        bytes32 workflowId,
        bytes32[] memory ids,
        ITwoPhaseCommitManager.ServiceRequest[] memory requests
    ) private view {
        bytes32[] memory registeredIds = manager.getWorkflowEscrows(workflowId);
        assertEq(registeredIds.length, ids.length);
        for (uint256 i = 0; i < ids.length; ++i) {
            assertEq(registeredIds[i], ids[i]);
            ITwoPhaseCommitManager.ServiceEntry memory service = manager.getService(workflowId, ids[i]);
            assertEq(service.escrowId, ids[i]);
            assertEq(service.provider, requests[i].provider);
            assertEq(service.amount, requests[i].amount);
            assertEq(uint256(service.state), uint256(ITwoPhaseCommitManager.ServiceState.PENDING));
        }
    }
}
