// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {VAMSTimelockController} from "./VAMSTimelockController.sol";

/// @notice VAMS timelock variant that exposes the exact active operation during target calls.
/// @dev Inactive source prototype. It adds execution context only; it does not add registry
///      authorization, consent verification, governance identities, or deployment configuration.
contract OperationAwareVAMSTimelockControllerV1 is VAMSTimelockController {
    error NestedOperationExecution();

    bool private _operationActive;
    bytes32 private _activeOperationId;
    bool private _activeOperationBatch;

    constructor(
        uint256 minDelay,
        address[] memory proposers,
        address[] memory executors,
        address admin
    ) VAMSTimelockController(minDelay, proposers, executors, admin) {}

    /// @notice Returns the active Timelock operation context, or an all-zero idle tuple.
    function activeOperationContext()
        external view returns (bool active, bytes32 operationId, bool batch)
    {
        return (_operationActive, _activeOperationId, _activeOperationBatch);
    }

    /// @notice Executes a single scheduled operation while exposing its exact hash to targets.
    function execute(
        address target,
        uint256 value,
        bytes calldata payload,
        bytes32 predecessor,
        bytes32 salt
    ) public payable override onlyRoleOrOpenRole(EXECUTOR_ROLE) {
        if (_operationActive) revert NestedOperationExecution();
        bytes32 operationId = hashOperation(target, value, payload, predecessor, salt);
        _operationActive = true;
        _activeOperationId = operationId;
        _activeOperationBatch = false;

        // Base implementation still performs readiness, predecessor, execution and completion checks.
        super.execute(target, value, payload, predecessor, salt);

        _clearOperationContext();
    }

    /// @notice Executes a scheduled batch while exposing its batch hash to each target call.
    function executeBatch(
        address[] calldata targets,
        uint256[] calldata values,
        bytes[] calldata payloads,
        bytes32 predecessor,
        bytes32 salt
    ) public payable override onlyRoleOrOpenRole(EXECUTOR_ROLE) {
        if (_operationActive) revert NestedOperationExecution();
        if (targets.length != values.length || targets.length != payloads.length) {
            revert TimelockInvalidOperationLength(targets.length, payloads.length, values.length);
        }
        bytes32 operationId = hashOperationBatch(targets, values, payloads, predecessor, salt);
        _operationActive = true;
        _activeOperationId = operationId;
        _activeOperationBatch = true;

        // Base implementation retains the inherited batch execution and predecessor semantics.
        super.executeBatch(targets, values, payloads, predecessor, salt);

        _clearOperationContext();
    }

    function _clearOperationContext() private {
        _activeOperationId = bytes32(0);
        _activeOperationBatch = false;
        _operationActive = false;
    }
}
