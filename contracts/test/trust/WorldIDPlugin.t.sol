// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {IWorldIDVerifier, WorldIDPlugin} from "../../src/trust/plugins/WorldIDPlugin.sol";

contract MockWorldIDVerifier is IWorldIDVerifier {
    bool public shouldRevert;
    uint256 public expectedSignalHash;
    uint256 public expectedExternalNullifier;

    function setShouldRevert(bool value) external {
        shouldRevert = value;
    }

    function setExpectedBinding(uint256 signalHash, uint256 externalNullifier) external {
        expectedSignalHash = signalHash;
        expectedExternalNullifier = externalNullifier;
    }

    function verifyProof(
        uint256,
        uint256 groupId,
        uint256 signalHash,
        uint256,
        uint256 externalNullifier,
        uint256[8] calldata
    ) external view {
        require(!shouldRevert, "invalid proof");
        require(groupId == 1, "wrong group");
        require(signalHash == expectedSignalHash, "wrong signal");
        require(externalNullifier == expectedExternalNullifier, "wrong action");
    }
}

contract WorldIDPluginTest is Test {
    MockWorldIDVerifier internal verifier;
    WorldIDPlugin internal plugin;

    function setUp() public {
        verifier = new MockWorldIDVerifier();
        plugin = new WorldIDPlugin(address(verifier));
        verifier.setExpectedBinding(
            uint256(keccak256(abi.encodePacked(keccak256("service"), keccak256("delivery")))) >> 8,
            uint256(keccak256(abi.encodePacked("vams-agent-verify"))) >> 8
        );
    }

    function test_constructorRejectsZeroVerifier() public {
        vm.expectRevert("WorldIDPlugin: zero verifier");
        new WorldIDPlugin(address(0));
    }

    function test_verifyCallsVerifierWithBoundProof() public view {
        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");
        WorldIDPlugin.WorldIDProof memory proof = _proof();

        assertTrue(plugin.verify(serviceHash, deliveryHash, abi.encode(proof)));
    }

    function test_verifyRejectsWrongExternalNullifier() public view {
        WorldIDPlugin.WorldIDProof memory proof = _proof();
        proof.externalNullifier = 123;

        assertFalse(plugin.verify(bytes32(uint256(1)), bytes32(uint256(2)), abi.encode(proof)));
    }

    function test_verifyRejectsMalformedProofData() public view {
        assertFalse(plugin.verify(bytes32(uint256(1)), bytes32(uint256(2)), hex"1234"));
    }

    function test_verifyFailsClosedWhenVerifierReverts() public {
        verifier.setShouldRevert(true);

        assertFalse(plugin.verify(bytes32(uint256(1)), bytes32(uint256(2)), abi.encode(_proof())));
    }

    function _proof() internal pure returns (WorldIDPlugin.WorldIDProof memory proof) {
        proof.root = 1;
        proof.nullifierHash = 2;
        proof.externalNullifier = uint256(keccak256(abi.encodePacked("vams-agent-verify"))) >> 8;
        proof.proof[0] = 3;
    }
}
