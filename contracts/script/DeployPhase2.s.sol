// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/registry/VAMSHardwareRegistry.sol";
import "../src/sentinel/SLAEnforcer.sol";
import "../src/trust/plugins/HardwareVerifiedPlugin.sol";
import "../src/economic/HardwareCommitment.sol";

contract DeployPhase2 is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address admin = vm.addr(deployerPrivateKey);
        
        address providerBondRegistry = vm.envAddress("PROVIDER_BOND_REGISTRY");
        address vamsSlasher = vm.envAddress("VAMS_SLASHER");
        
        vm.startBroadcast(deployerPrivateKey);

        // 1. Deploy Hardware Registry (Phase 2, Sprint 1)
        VAMSHardwareRegistry registry = new VAMSHardwareRegistry();
        registry.initialize(admin);

        // 2. Deploy SLA Enforcer (Phase 2, Sprint 3)
        SLAEnforcer enforcer = new SLAEnforcer();
        enforcer.initialize(admin, address(registry), vamsSlasher);

        // 3. Deploy Trust Plugin for SLA (Phase 2, Sprint 3)
        HardwareVerifiedPlugin plugin = new HardwareVerifiedPlugin(address(enforcer), 1500);

        // 4. Deploy Hardware Commitment Economics (Phase 2, Sprint 4)
        HardwareCommitment commitment = new HardwareCommitment();
        commitment.initialize(admin, address(registry), providerBondRegistry);

        // In a real execution environment with proxies, the roles would be distributed here:
        // registry.grantRole(registry.SENTINEL_ROLE(), address(enforcer));
        // ProviderBondRegistry(providerBondRegistry).grantRole(HARDWARE_COMMITMENT_ROLE, address(commitment));
        // VAMSSlasher(vamsSlasher).grantRole(SLASHER_ROLE, address(enforcer));

        vm.stopBroadcast();
    }
}
