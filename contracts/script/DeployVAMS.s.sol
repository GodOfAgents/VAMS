// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Script.sol";
import "../src/token/VAMSToken.sol";
import "../src/staking/VAMSStaking.sol";
import "../src/vesting/VAMSVesting.sol";
import "../src/governance/VAMSTimelockController.sol";
import "../src/registry/VAMSAgentRegistry.sol";
import "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

contract DeployVAMS is Script {
    function run() external {
        // Use PRIVATE_KEY passed via command line --private-key if env var fails
        // Or handle the hex string properly
        
        // Setup Deployer
        // Note: When using --private-key flag in forge script, msg.sender is automatically set.
        // vm.startBroadcast() without arguments uses that key.
        
        vm.startBroadcast();

        address deployer = msg.sender;
        console.log("Deploying from:", deployer);

        // 1. Deploy VAMSToken (admin, treasury)
        VAMSToken token = new VAMSToken(deployer, deployer);
        console.log("VAMSToken deployed to:", address(token));

        // 2. Deploy Timelock (Governance)
        address[] memory proposers = new address[](1);
        proposers[0] = deployer;
        address[] memory executors = new address[](1);
        executors[0] = address(0); // Anyone can execute
        
        VAMSTimelockController timelock = new VAMSTimelockController(
            86400, // 24h delay
            proposers,
            executors,
            deployer
        );
        console.log("VAMSTimelock deployed to:", address(timelock));

        // 3. Deploy Staking
        VAMSStaking staking = new VAMSStaking(
            address(token),
            address(token), // Using VAMS as reward token
            1e18,           // Initial reward rate
            address(timelock)
        );
        console.log("VAMSStaking deployed to:", address(staking));

        // 4. Deploy Vesting
        VAMSVesting vesting = new VAMSVesting(
            address(token),
            address(timelock)
        );
        console.log("VAMSVesting deployed to:", address(vesting));

        // 5. Deploy Registry (Upgradeable)
        VAMSAgentRegistry implementation = new VAMSAgentRegistry();
        
        ProxyAdmin proxyAdmin = new ProxyAdmin(deployer);

        bytes memory data = abi.encodeWithSelector(
            VAMSAgentRegistry.initialize.selector,
            deployer,       // Admin
            address(token), // VAMS Token
            address(0)      // Slasher (set later)
        );

        TransparentUpgradeableProxy proxy = new TransparentUpgradeableProxy(
            address(implementation),
            address(proxyAdmin),
            data
        );
        console.log("VAMSAgentRegistry Proxy deployed to:", address(proxy));

        vm.stopBroadcast();
    }
}
