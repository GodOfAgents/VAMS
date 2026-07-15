// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "forge-std/Test.sol";
import "../../src/routing/RoutingProofVerifier.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

contract RoutingProofVerifierTest is Test {
    using MessageHashUtils for bytes32;

    RoutingProofVerifier public verifier;

    address public admin = address(1);
    address public oracle = address(2);
    uint256 public oraclePrivateKey = 0xA11CE;

    bytes32 public constant RULES_ROOT = keccak256("InitialRules");

    function setUp() public {
        vm.startPrank(admin);

        // Deploy
        verifier = new RoutingProofVerifier();
        verifier.initialize(admin);

        // Setup Roles
        oracle = vm.addr(oraclePrivateKey); // Derive address from private key
        verifier.grantRole(verifier.VERIFIER_ORACLE_ROLE(), oracle);

        // Set Initial Rules
        verifier.updateRoutingRulesRoot(RULES_ROOT);

        vm.stopPrank();
    }

    function test_VerifyValidProof() public {
        bytes32 txHash = keccak256("tx1");
        bytes32 metadataHash = keccak256("meta");
        bytes32 decisionHash = keccak256("decision");

        // Construct message
        bytes32 messageHash = keccak256(abi.encodePacked(txHash, metadataHash, decisionHash, RULES_ROOT));

        // Sign with Oracle Key
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(oraclePrivateKey, messageHash.toEthSignedMessageHash());
        bytes memory signature = abi.encodePacked(r, s, v);

        IRoutingProofVerifier.RoutingProof memory proof = IRoutingProofVerifier.RoutingProof({
            inputMetadataHash: metadataHash,
            routingDecisionHash: decisionHash,
            routingRulesRoot: RULES_ROOT,
            zkProof: signature
        });

        bool isValid = verifier.verifyRoutingDecision(txHash, proof);
        assertTrue(isValid, "Proof should be valid");
    }

    function test_FailInvalidRoot() public {
        bytes32 txHash = keccak256("tx1");
        bytes32 wrongRoot = keccak256("WrongRules");

        IRoutingProofVerifier.RoutingProof memory proof = IRoutingProofVerifier.RoutingProof({
            inputMetadataHash: bytes32(0),
            routingDecisionHash: bytes32(0),
            routingRulesRoot: wrongRoot, // Wrong root
            zkProof: ""
        });

        bool isValid = verifier.verifyRoutingDecision(txHash, proof);
        assertFalse(isValid, "Proof with wrong root should be invalid");
    }

    function test_FailInvalidSignature() public {
        bytes32 txHash = keccak256("tx1");
        bytes32 metadataHash = keccak256("meta");
        bytes32 decisionHash = keccak256("decision");

        // Sign with RANDOM Key (not oracle)
        uint256 randomKey = 0xB0B;
        bytes32 messageHash = keccak256(abi.encodePacked(txHash, metadataHash, decisionHash, RULES_ROOT));

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(randomKey, messageHash.toEthSignedMessageHash());
        bytes memory signature = abi.encodePacked(r, s, v);

        IRoutingProofVerifier.RoutingProof memory proof = IRoutingProofVerifier.RoutingProof({
            inputMetadataHash: metadataHash,
            routingDecisionHash: decisionHash,
            routingRulesRoot: RULES_ROOT,
            zkProof: signature
        });

        bool isValid = verifier.verifyRoutingDecision(txHash, proof);
        assertFalse(isValid, "Proof with invalid signer should be invalid");
    }
}
