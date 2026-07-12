// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/governance/TimelockController.sol";

/**
 * @title VAMSTimelockController
 * @author VAMS Protocol
 * @notice Timelock controller for VAMS Governance
 * @dev 
 * - Enforces minimum delay for standard operations
 * - Emergency response uses pause-only authority and cannot bypass this delay.
 */
contract VAMSTimelockController is TimelockController {
    /// @notice Minimum permissible governance delay (48 hours)
    uint256 public constant ABSOLUTE_MIN_DELAY = 48 hours;
    
    // ============ Errors ============
    
    error DelayTooShort(uint256 provided, uint256 minimum);
    
    /**
     * @notice Deploy VAMS Timelock Controller
     * @param minDelay Initial minimum delay in seconds
     * @param proposers Addresses that can propose operations
     * @param executors Addresses that can execute operations
     * @param admin Initial admin (should be renounced after setup)
     */
    constructor(
        uint256 minDelay,
        address[] memory proposers,
        address[] memory executors,
        address admin
    ) TimelockController(minDelay, proposers, executors, admin) {
        if (minDelay < ABSOLUTE_MIN_DELAY) {
            revert DelayTooShort(minDelay, ABSOLUTE_MIN_DELAY);
        }
    }
    
    /**
     * @notice Override minimum delay updates to enforce safety floor
     * @dev Prevents setting delay below ABSOLUTE_MIN_DELAY (48 hours)
     */
    function updateDelay(uint256 newDelay) public override {
        if (newDelay < ABSOLUTE_MIN_DELAY) {
            revert DelayTooShort(newDelay, ABSOLUTE_MIN_DELAY);
        }
        // Call parent (requires TIMELOCK_ADMIN_ROLE via self-call)
        super.updateDelay(newDelay);
    }
}
