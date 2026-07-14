// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @notice Common access and emergency-stop controls for VDSO canary modules.
/// @dev The caller supplies governance and pause-council addresses; this base
///      embeds no deployer, operator, or private-key assumptions.
abstract contract VDSOCanaryAccess is AccessControl, Pausable {
    bytes32 public constant PAUSER_ROLE = keccak256("VDSO_PAUSER_ROLE");

    error InvalidAddress();

    constructor(address admin, address pauser) {
        if (admin == address(0) || pauser == address(0)) revert InvalidAddress();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, pauser);
    }

    /// @notice Emergency council may stop new canary work.
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /// @notice Governance, expected to be a timelock in deployments, resumes work.
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }
}
