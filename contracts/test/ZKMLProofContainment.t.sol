// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {VAMSTrustAggregator} from "../src/trust/VAMSTrustAggregator.sol";
import {ZKMLProofPlugin} from "../src/trust/plugins/ZKMLProofPlugin.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract ZKMLProofContainmentTest is Test {
    VAMSTrustAggregator private aggregator;
    address private agent = address(0x1234);

    function setUp() public {
        VAMSTrustAggregator implementation = new VAMSTrustAggregator();
        bytes memory initData = abi.encodeWithSelector(VAMSTrustAggregator.initialize.selector);
        aggregator = VAMSTrustAggregator(
            address(new ERC1967Proxy(address(implementation), initData))
        );
    }

    function testPlaceholderCannotEnterAggregatorOrDeliveryAdmission() public {
        bytes32 modelHash = keccak256("model");
        bytes32 inputHash = keccak256("input");
        bytes32 outputHash = keccak256("output");
        bytes32 serviceHash = keccak256(abi.encodePacked(modelHash, inputHash));
        bytes memory structurallyValidPlaceholder = abi.encode(
            hex"0101010101010101010101010101010101010101010101010101010101010101",
            modelHash,
            inputHash,
            outputHash,
            abi.encodePacked(modelHash, inputHash, outputHash)
        );

        // Exercise both absent and configured verifier addresses: no backend
        // is selected until an independently reviewed verifier interface exists.
        for (uint256 i = 0; i < 2; i++) {
            address verifier = i == 0 ? address(0) : address(0xBEEF);
            ZKMLProofPlugin plugin = new ZKMLProofPlugin(address(this), verifier);
            plugin.approveModel(modelHash);
            aggregator.registerProofPlugin(plugin);

            bytes32 proofType = plugin.proofType();
            assertFalse(plugin.verify(serviceHash, outputHash, structurallyValidPlaceholder));
            assertFalse(plugin.verify(serviceHash, outputHash, hex"010203"));

            (bool valid, uint256 weight) = aggregator.verifyServiceDelivery(
                serviceHash, outputHash, proofType, structurallyValidPlaceholder
            );
            assertFalse(valid);
            assertEq(weight, 0);

            vm.expectRevert("Plugin proof verification failed");
            vm.prank(agent);
            aggregator.submitPluginProof(
                proofType, serviceHash, outputHash, structurallyValidPlaceholder
            );
            assertEq(aggregator.getAgentScore(agent), 0);
            assertFalse(aggregator.hasPluginProof(agent, proofType));
            aggregator.deregisterProofPlugin(proofType);
        }
    }
}
