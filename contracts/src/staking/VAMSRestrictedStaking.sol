// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {VAMSStaking} from "./VAMSStaking.sol";

/// @notice Faucet-testnet staking with non-activatable emissions.
/// @dev A future reward design requires a separately reviewed deployment.
contract VAMSRestrictedStaking is VAMSStaking {
    bool public constant rewardsEnabled = false;
    error RestrictedRewardsDisabled();

    constructor(address token, address admin) VAMSStaking(token, token, 0, admin) {
        annualEmissionBudget = 0;
    }

    function updateEmissionRate(uint256 newRate) external override onlyRole(EMISSION_ADMIN_ROLE) {
        if (newRate != 0) revert RestrictedRewardsDisabled();
    }

    function updateEmissionBudget(uint256 newBudget) external override onlyRole(EMISSION_ADMIN_ROLE) {
        if (newBudget != 0) revert RestrictedRewardsDisabled();
    }
}
