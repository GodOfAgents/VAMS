// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Script.sol";
import "../src/economic/X402EscrowManager.sol";
import "../src/economic/X402NonceRegistry.sol";
import "../src/economic/ProviderBondRegistry.sol";
import "../src/token/VAMSToken.sol";
import "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

contract DeployX402 is Script {
    address constant TOKEN_ADDRESS = 0x62a705eD1cAbBBafFCd99e9b2497024031329fd4;
    address constant REGISTRY_ADDRESS = 0x7e290350448cDC8A22e4cF4Ad377B1E595CDd347;

    function run() external {
        vm.startBroadcast();

        address deployer = msg.sender;
        console.log("Deploying X402 Stack from:", deployer);

        // 1. Deploy Nonce Registry
        X402NonceRegistry nonceRegistry = new X402NonceRegistry();
        console.log("X402NonceRegistry deployed:", address(nonceRegistry));

        // 2. Deploy Provider Bond Registry
        ProviderBondRegistry bondRegistry = new ProviderBondRegistry();
        // Initialize Bond Registry (needs token & agent registry)
        // Note: Bond Registry also needs initialization if it's upgradeable or constructor args
        // Checking constructor... it's Initializable.
        // Assuming implementation is upgradeable pattern for now, but deploying direct for simplicity if needed.
        // Let's use Transparent Proxy for Bond Registry too to be consistent.
        
        ProxyAdmin proxyAdmin = new ProxyAdmin(deployer);
        
        // Encode initializer for Bond Registry
        bytes memory bondData = abi.encodeWithSelector(
            ProviderBondRegistry.initialize.selector,
            deployer,
            TOKEN_ADDRESS,
            REGISTRY_ADDRESS
        );
        
        TransparentUpgradeableProxy bondProxy = new TransparentUpgradeableProxy(
            address(bondRegistry),
            address(proxyAdmin),
            bondData
        );
        console.log("ProviderBondRegistry Proxy deployed:", address(bondProxy));

        // 3. Deploy X402 Escrow Manager
        X402EscrowManager escrowManager = new X402EscrowManager();
        
        // Encode initializer for Escrow Manager
        bytes memory escrowData = abi.encodeWithSelector(
            X402EscrowManager.initialize.selector,
            deployer,       // Admin
            TOKEN_ADDRESS,  // VAMS Token
            address(nonceRegistry),
            address(bondProxy),
            deployer        // Treasury (for now)
        );

        TransparentUpgradeableProxy escrowProxy = new TransparentUpgradeableProxy(
            address(escrowManager),
            address(proxyAdmin),
            escrowData
        );
        console.log("X402EscrowManager Proxy deployed:", address(escrowProxy));

        vm.stopBroadcast();
    }
}
