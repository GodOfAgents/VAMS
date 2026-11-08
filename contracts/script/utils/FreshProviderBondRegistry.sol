// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ProviderBondRegistry} from "../../src/economic/ProviderBondRegistry.sol";

/// @notice Create and initialize a fresh registry in one indivisible transaction.
/// @dev No callable factory/admin surface or legacy-state adoption. The helper
///      retains only the immutable resulting address; it receives no registry role.
contract FreshProviderBondRegistry {
    ProviderBondRegistry public immutable registry;

    constructor(address admin, address token, address insuranceRecipient) {
        require(admin != address(0) && admin != address(this), "Invalid bootstrap admin");
        require(token.code.length > 0 && insuranceRecipient.code.length > 0, "Missing dependency code");
        ProviderBondRegistry fresh = new ProviderBondRegistry();
        fresh.initialize(admin, token, insuranceRecipient);
        registry = fresh;
    }
}
