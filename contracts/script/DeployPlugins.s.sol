// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {VAMSTrustAggregator} from "../src/trust/VAMSTrustAggregator.sol";
import {IVAMSProofPlugin} from "../src/interfaces/IVAMSProofPlugin.sol";
import {TEEProofPlugin} from "../src/trust/plugins/TEEProofPlugin.sol";
import {ZKMLProofPlugin} from "../src/trust/plugins/ZKMLProofPlugin.sol";
import {OutputHashProofPlugin} from "../src/trust/plugins/OutputHashProofPlugin.sol";
import {ERC8004IdentityPlugin} from "../src/trust/plugins/ERC8004IdentityPlugin.sol";
import {WorldIDPlugin} from "../src/trust/plugins/WorldIDPlugin.sol";
import {PolygonIDPlugin} from "../src/trust/plugins/PolygonIDPlugin.sol";

/**
 * @title DeployPlugins
 * @notice Deployment script for VAMS proof plugins and registration with the aggregator.
 * @dev Usage:
 *      forge script script/DeployPlugins.s.sol:DeployPlugins \
 *          --rpc-url $RPC_URL \
 *          --broadcast \
 *          --verify
 */
contract DeployPlugins is Script {
    /// @notice Address of the deployed VAMSTrustAggregator proxy
    /// @dev Set this to the actual deployed proxy address before running
    address constant AGGREGATOR_PROXY = address(0); // TODO: Set before deployment

    /// @notice Address of the VAMS Agent NFT contract (for ERC8004 plugin)
    address constant AGENT_NFT = address(0); // TODO: Set before deployment

    /// @notice Address of the World ID verifier contract
    address constant WORLD_ID_VERIFIER = address(0); // TODO: Set before deployment

    /// @notice Address of the Polygon ID / Iden3 state contract
    address constant IDEN3_STATE = address(0); // TODO: Set before deployment

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("Deployer:", deployer);
        console.log("Aggregator:", AGGREGATOR_PROXY);

        vm.startBroadcast(deployerPrivateKey);

        // --- 1. Deploy Plugins ---

        console.log("\n=== Deploying Proof Plugins ===\n");

        TEEProofPlugin teePlugin = new TEEProofPlugin(deployer);
        console.log("TEEProofPlugin:", address(teePlugin));

        ZKMLProofPlugin zkmlPlugin = new ZKMLProofPlugin(deployer, address(0));
        console.log("ZKMLProofPlugin:", address(zkmlPlugin));

        OutputHashProofPlugin outputHashPlugin = new OutputHashProofPlugin(deployer);
        console.log("OutputHashProofPlugin:", address(outputHashPlugin));

        ERC8004IdentityPlugin identityPlugin = new ERC8004IdentityPlugin(AGENT_NFT);
        console.log("ERC8004IdentityPlugin:", address(identityPlugin));

        WorldIDPlugin worldIdPlugin = new WorldIDPlugin(WORLD_ID_VERIFIER);
        console.log("WorldIDPlugin:", address(worldIdPlugin));

        PolygonIDPlugin polygonIdPlugin = new PolygonIDPlugin(deployer, IDEN3_STATE);
        console.log("PolygonIDPlugin:", address(polygonIdPlugin));

        // --- 2. Register Plugins with Aggregator ---

        if (AGGREGATOR_PROXY != address(0)) {
            console.log("\n=== Registering Plugins ===\n");

            VAMSTrustAggregator aggregator = VAMSTrustAggregator(AGGREGATOR_PROXY);

            aggregator.registerProofPlugin(teePlugin);
            console.log("Registered: TEE");

            aggregator.registerProofPlugin(zkmlPlugin);
            console.log("Registered: ZKML");

            aggregator.registerProofPlugin(outputHashPlugin);
            console.log("Registered: OutputHash");

            aggregator.registerProofPlugin(identityPlugin);
            console.log("Registered: ERC8004 Identity");

            aggregator.registerProofPlugin(worldIdPlugin);
            console.log("Registered: World ID");

            aggregator.registerProofPlugin(polygonIdPlugin);
            console.log("Registered: Polygon ID");

            // --- 3. Verify Registration ---

            console.log("\n=== Verifying Registration ===\n");

            uint256 count = aggregator.getRegisteredPluginCount();
            console.log("Total registered plugins:", count);

            for (uint256 i = 0; i < count; i++) {
                bytes32 pType = aggregator.getRegisteredPluginType(i);
                IVAMSProofPlugin plugin = aggregator.getProofPlugin(pType);
                console.log("Plugin", i, ":", plugin.name());
            }
        } else {
            console.log("\nAGGREGATOR_PROXY not set -- skipping registration.");
            console.log("Update the constant and re-run to register plugins.");
        }

        vm.stopBroadcast();

        console.log("\n=== Deployment Complete ===");
    }
}
