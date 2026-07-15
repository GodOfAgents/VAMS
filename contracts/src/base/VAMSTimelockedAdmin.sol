// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";

/**
 * @title VAMSTimelockedAdmin
 * @author VAMS Protocol
 * @notice Provides 24-hour timelock functionality for critical global setters (AC04)
 * @dev Inherit this contract to protect critical economic setting updates
 */
abstract contract VAMSTimelockedAdmin is AccessControlUpgradeable {
    uint256 public constant ADMIN_DELAY = 24 hours;

    mapping(bytes32 => uint256) public pendingChanges;

    event ChangeProposed(bytes32 indexed changeId, uint256 executionTime);
    event ChangeExecuted(bytes32 indexed changeId);
    event ChangeCancelled(bytes32 indexed changeId);

    error ChangeNotProposed(bytes32 changeId);
    error TimelockNotExpired(uint256 executionTime);

    /**
     * @notice Propose a change to enter the timelock
     * @dev Generates a unique change ID for the parameter
     */
    function _proposeChange(bytes32 changeId) internal {
        uint256 executionTime = block.timestamp + ADMIN_DELAY;
        pendingChanges[changeId] = executionTime;
        emit ChangeProposed(changeId, executionTime);
    }

    /**
     * @notice Pre-check and consume a scheduled change
     * @dev Must be called before executing the state change
     */
    function _enforceTimelock(bytes32 changeId) internal {
        uint256 executionTime = pendingChanges[changeId];
        if (executionTime == 0) revert ChangeNotProposed(changeId);
        if (block.timestamp < executionTime) revert TimelockNotExpired(executionTime);

        pendingChanges[changeId] = 0; // reset
        emit ChangeExecuted(changeId);
    }

    /**
     * @notice Cancel a pending change
     */
    function _cancelChange(bytes32 changeId) internal {
        if (pendingChanges[changeId] != 0) {
            pendingChanges[changeId] = 0;
            emit ChangeCancelled(changeId);
        }
    }
}
