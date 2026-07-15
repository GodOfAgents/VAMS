// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title RecoveryQueue
 * @author VAMS Protocol
 * @notice Enable prioritized queuing with expiration tracking for L1 halt fallbacks and automated recovery
 */
contract RecoveryQueue is AccessControl {
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");
    bytes32 public constant HALT_MANAGER_ROLE = keccak256("HALT_MANAGER_ROLE");

    enum Priority {
        CRITICAL,
        HIGH,
        MEDIUM,
        LOW
    }

    struct Action {
        uint256 id;
        address target;
        bytes data;
        Priority priority;
        uint256 queuedAt;
        uint256 expiresAt;
        bool executed;
    }

    uint256 public nextActionId = 1;
    bool public isL1Halted;

    mapping(uint256 => Action) public actions;
    // Map of priority => acton IDs for ordering logic off-chain
    // Not iterating on-chain to save gas

    event ActionQueued(uint256 indexed id, address indexed target, Priority priority, uint256 expiresAt);
    event ActionExecuted(uint256 indexed id, address indexed executor, bool success);
    event HaltStatusChanged(bool isHalted, uint256 timestamp);

    constructor(address _admin) {
        require(_admin != address(0), "Zero admin address");
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(EXECUTOR_ROLE, _admin);
        _grantRole(HALT_MANAGER_ROLE, _admin);
    }

    /**
     * @notice Enqueue an action during an L1 halt / emergency
     */
    function enqueueRecoveryAction(address _target, bytes calldata _data, Priority _priority, uint256 _duration)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
        returns (uint256)
    {
        // usually queued by multi-sig or timelock
        uint256 id = nextActionId++;

        uint256 expiresAt = block.timestamp + _duration;

        actions[id] = Action({
            id: id,
            target: _target,
            data: _data,
            priority: _priority,
            queuedAt: block.timestamp,
            expiresAt: expiresAt,
            executed: false
        });

        emit ActionQueued(id, _target, _priority, expiresAt);
        return id;
    }

    /**
     * @notice Set the L1 halt status
     */
    function setL1Halted(bool _halted) external onlyRole(HALT_MANAGER_ROLE) {
        isL1Halted = _halted;
        emit HaltStatusChanged(_halted, block.timestamp);
    }

    /**
     * @notice Execute an enqueued action
     * @param _actionId The ID of the action
     */
    function executeRecoveryAction(uint256 _actionId) external onlyRole(EXECUTOR_ROLE) {
        require(isL1Halted, "Not in halt recovery mode");

        Action storage a = actions[_actionId];
        require(a.id != 0, "Action does not exist");
        require(!a.executed, "Action already executed");
        require(block.timestamp <= a.expiresAt, "Action expired");

        a.executed = true;

        (bool success,) = a.target.call(a.data);

        // Emitting success status - in a real fallback scenario we might allow partial failure tracking
        emit ActionExecuted(_actionId, msg.sender, success);

        require(success, "Recovery action failed");
    }
}
