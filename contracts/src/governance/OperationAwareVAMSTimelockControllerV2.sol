// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {OperationAwareVAMSTimelockControllerV1} from "./OperationAwareVAMSTimelockControllerV1.sol";
import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

/// @notice 48-hour VAMS Timelock context with a monotonically increasing schedule epoch per ID.
/// @dev V1 remains unchanged. Epochs invalidate a proof if an identical operation is cancelled
///      and re-scheduled, including within one block timestamp.
contract OperationAwareVAMSTimelockControllerV2 is OperationAwareVAMSTimelockControllerV1 {
    error OperationEpochOverflow(bytes32 operationId);

    mapping(bytes32 operationId => uint64 epoch) private _operationEpochs;
    mapping(bytes32 operationId => uint256 delaySeconds) private _scheduledDelays;

    constructor(uint256 minDelay, address[] memory proposers, address[] memory executors, address admin)
        OperationAwareVAMSTimelockControllerV1(minDelay, proposers, executors, admin) {}

    function operationEpoch(bytes32 operationId) external view returns (uint64) {
        return _operationEpochs[operationId];
    }

    function scheduledDelay(bytes32 operationId) external view returns (uint256) {
        return _scheduledDelays[operationId];
    }

    function schedule(
        address target,
        uint256 value,
        bytes calldata data,
        bytes32 predecessor,
        bytes32 salt,
        uint256 delay
    ) public override onlyRole(PROPOSER_ROLE) {
        bytes32 operationId = hashOperation(target, value, data, predecessor, salt);
        _advanceEpoch(operationId);
        _scheduledDelays[operationId] = delay;
        super.schedule(target, value, data, predecessor, salt, delay);
    }

    function scheduleBatch(
        address[] calldata targets,
        uint256[] calldata values,
        bytes[] calldata payloads,
        bytes32 predecessor,
        bytes32 salt,
        uint256 delay
    ) public override onlyRole(PROPOSER_ROLE) {
        bytes32 operationId = hashOperationBatch(targets, values, payloads, predecessor, salt);
        _advanceEpoch(operationId);
        _scheduledDelays[operationId] = delay;
        super.scheduleBatch(targets, values, payloads, predecessor, salt, delay);
    }

    function cancel(bytes32 operationId) public override onlyRole(CANCELLER_ROLE) {
        super.cancel(operationId);
        delete _scheduledDelays[operationId];
        _advanceEpoch(operationId);
    }

    function _advanceEpoch(bytes32 operationId) private {
        uint64 epoch = _operationEpochs[operationId];
        if (epoch == type(uint64).max) revert OperationEpochOverflow(operationId);
        _operationEpochs[operationId] = epoch + 1;
    }
}

