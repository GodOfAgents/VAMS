// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Script.sol";
import "../src/economic/X402EscrowManager.sol";
import "../src/economic/ProviderBondRegistry.sol";

contract SetupX402Roles is Script {
    address constant ESCROW_MANAGER = 0xfC58658fA08102612c78166374854fE31cCFBb58;
    address constant BOND_REGISTRY = 0xC00d6C3CA385D1fAcbB23b9B2d6dceE6A120cd0c;

    function run() external {
        vm.startBroadcast();

        address deployer = msg.sender;
        console.log("Setting up X402 Roles from:", deployer);

        X402EscrowManager escrow = X402EscrowManager(ESCROW_MANAGER);
        ProviderBondRegistry bond = ProviderBondRegistry(BOND_REGISTRY);

        // Grant ESCROW_ROLE to EscrowManager on BondRegistry
        // ESCROW_ROLE: 0x2fdac322ee704ce09f0773f7f3f92eb98d5e7c836ee9c056cccd5f61041e5e3f
        bytes32 ESCROW_ROLE = keccak256("ESCROW_ROLE");
        
        console.log("Granting ESCROW_ROLE to EscrowManager...");
        bond.grantRole(ESCROW_ROLE, ESCROW_MANAGER);
        
        console.log("Roles Configured.");

        vm.stopBroadcast();
    }
}
