// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Script.sol";
import "../src/economic/X402EscrowManager.sol";
import "../src/economic/ProviderBondRegistry.sol";

contract SetupX402Roles is Script {
    address ESCROW_MANAGER;
    address BOND_REGISTRY;

    function run() external {
        ESCROW_MANAGER = vm.envAddress("X402_ESCROW");
        BOND_REGISTRY = vm.envAddress("PROVIDER_BOND");
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(deployerPrivateKey);

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
