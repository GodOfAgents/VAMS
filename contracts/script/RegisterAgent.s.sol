// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Script.sol";
import "../src/registry/VAMSAgentRegistry.sol";
import "../src/token/VAMSToken.sol";

contract RegisterAgent is Script {
    // Addresses from CONTRACTS.md
    address TOKEN_ADDRESS;
    address REGISTRY_ADDRESS;

    // Agent Details
    // Using the VAMS Node ID from IDENTITY.md as the seed for the Public Key Hash
    string constant NODE_ID = "vams_e7d2d15275054b27a379deb0b8c0a673fb8d959e";
    string constant METADATA_URI = "ipfs://bafkreic7x7t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6"; // Placeholder

    function run() external {
        TOKEN_ADDRESS = vm.envAddress("VAMS_TOKEN");
        REGISTRY_ADDRESS = vm.envAddress("AGENT_REGISTRY");
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        // We will pass the key directly as a hex string with 0x prefix or use the broadcast feature
        // Since we are running with --private-key on command line, we can just use vm.startBroadcast()
        // and it will use the deployer account automatically.
        
        vm.startBroadcast(deployerPrivateKey);

        address deployer = msg.sender;
        console.log("Deploying from:", deployer);

        VAMSToken token = VAMSToken(TOKEN_ADDRESS);
        VAMSAgentRegistry registry = VAMSAgentRegistry(REGISTRY_ADDRESS);

        // 1. Approve Registry to spend VAMS
        uint256 stakeAmount = 1000 ether; // 1000 VAMS
        console.log("Approving VAMS token...");
        token.approve(REGISTRY_ADDRESS, stakeAmount);

        // 2. Register Agent
        bytes32 publicKeyHash = keccak256(abi.encodePacked(NODE_ID));
        console.log("Registering Agent with PK Hash:");
        console.logBytes32(publicKeyHash);

        try registry.registerAgent(publicKeyHash, stakeAmount, METADATA_URI) {
            console.log("Agent Registered Successfully!");
        } catch Error(string memory reason) {
            console.log("Registration Failed:", reason);
        } catch {
            console.log("Registration Failed (Unknown Error)");
        }

        vm.stopBroadcast();
    }
}
