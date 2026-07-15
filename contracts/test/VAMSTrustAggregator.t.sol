// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console} from "forge-std/Test.sol";
import {VAMSTrustAggregator} from "../src/trust/VAMSTrustAggregator.sol";
import {IVAMSTrustAggregator} from "../src/interfaces/IVAMSTrustAggregator.sol";
import {IVAMSProofPlugin} from "../src/interfaces/IVAMSProofPlugin.sol";
import {TEEProofPlugin} from "../src/trust/plugins/TEEProofPlugin.sol";
import {OutputHashProofPlugin} from "../src/trust/plugins/OutputHashProofPlugin.sol";
import {ERC8004IdentityPlugin} from "../src/trust/plugins/ERC8004IdentityPlugin.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract MockLegacyPlugin is IVAMSProofPlugin {
    bytes32 private _type;

    constructor(bytes32 t) {
        _type = t;
    }

    function proofType() external view override returns (bytes32) {
        return _type;
    }

    function verify(bytes32, bytes32, bytes calldata proofData) external pure override returns (bool) {
        return proofData.length >= 64;
    }

    function trustWeight() external pure override returns (uint256) {
        return 1000;
    }

    function name() external pure override returns (string memory) {
        return "Mock Legacy";
    }
}

contract VAMSTrustAggregatorTest is Test {
    VAMSTrustAggregator public aggregator;
    TEEProofPlugin public teePlugin;
    OutputHashProofPlugin public outputHashPlugin;
    ERC8004IdentityPlugin public identityPlugin;

    address public owner;
    address public agent;
    address public nonOwner;

    function setUp() public {
        owner = address(this);
        agent = address(0x123);
        nonOwner = address(0x456);

        // Deploy aggregator via UUPS proxy
        VAMSTrustAggregator impl = new VAMSTrustAggregator();
        bytes memory initData = abi.encodeWithSelector(VAMSTrustAggregator.initialize.selector);
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), initData);
        aggregator = VAMSTrustAggregator(address(proxy));

        // Deploy plugins
        teePlugin = new TEEProofPlugin(owner);
        outputHashPlugin = new OutputHashProofPlugin(owner);
        identityPlugin = new ERC8004IdentityPlugin(address(0x789));

        aggregator.registerProofPlugin(
            new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY)))
        );
        aggregator.registerProofPlugin(
            new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.POLYGON_ID)))
        );
        aggregator.registerProofPlugin(
            new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.COINBASE_WALLET)))
        );
        aggregator.registerProofPlugin(
            new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.PARALLEL_RESEARCH)))
        );
        aggregator.registerProofPlugin(
            new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.PHALA_EXECUTION)))
        );
    }

    // ============================================================
    //              LEGACY TESTS (Backward Compatibility)
    // ============================================================

    function test_InitialState() public view {
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint256(tier), uint256(IVAMSTrustAggregator.TrustTier.UNVERIFIED));
    }

    function test_SubmitIdentityProof_UpdatesTier() public {
        vm.startPrank(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint256(tier), uint256(IVAMSTrustAggregator.TrustTier.BRONZE));
        vm.stopPrank();
    }

    function test_AggregateProofs_ReachesSilver() public {
        vm.startPrank(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.POLYGON_ID, new bytes(64));
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint256(tier), uint256(IVAMSTrustAggregator.TrustTier.SILVER));
        vm.stopPrank();
    }

    function test_AggregateProofs_ReachesGold() public {
        vm.startPrank(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.COINBASE_WALLET, new bytes(64));
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.PARALLEL_RESEARCH, new bytes(64));
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.PHALA_EXECUTION, new bytes(64));
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint256(tier), uint256(IVAMSTrustAggregator.TrustTier.GOLD));
        vm.stopPrank();
    }

    function test_CannotSubmitSameProofTwice() public {
        vm.startPrank(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        uint256 score1 = aggregator.getAgentScore(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        uint256 score2 = aggregator.getAgentScore(agent);
        assertEq(score1, score2);
        vm.stopPrank();
    }

    // ============================================================
    //              PLUGIN REGISTRATION TESTS
    // ============================================================

    function test_RegisterPlugin_OnlyOwner() public {
        vm.prank(nonOwner);
        vm.expectRevert();
        aggregator.registerProofPlugin(teePlugin);
    }

    function test_RegisterPlugin_EmitsEvent() public {
        bytes32 pType = teePlugin.proofType();
        vm.expectEmit(true, true, false, false);
        emit IVAMSTrustAggregator.ProofPluginRegistered(pType, address(teePlugin));
        aggregator.registerProofPlugin(teePlugin);
    }

    function test_RegisterPlugin_StoresCorrectly() public {
        aggregator.registerProofPlugin(teePlugin);
        bytes32 pType = teePlugin.proofType();
        IVAMSProofPlugin stored = aggregator.getProofPlugin(pType);
        assertEq(address(stored), address(teePlugin));
    }

    function test_DuplicatePluginTypeReverts() public {
        aggregator.registerProofPlugin(teePlugin);

        // Create another plugin with the same proof type
        TEEProofPlugin teePlugin2 = new TEEProofPlugin(owner);
        vm.expectRevert("Plugin type already registered");
        aggregator.registerProofPlugin(teePlugin2);
    }

    function test_DeregisterPlugin() public {
        aggregator.registerProofPlugin(teePlugin);
        bytes32 pType = teePlugin.proofType();

        aggregator.deregisterProofPlugin(pType);

        IVAMSProofPlugin stored = aggregator.getProofPlugin(pType);
        assertEq(address(stored), address(0));
    }

    function test_DeregisterPlugin_NonexistentReverts() public {
        bytes32 fakeType = keccak256("FAKE_TYPE");
        vm.expectRevert("Plugin not registered");
        aggregator.deregisterProofPlugin(fakeType);
    }

    // ============================================================
    //              PLUGIN PROOF SUBMISSION TESTS
    // ============================================================

    function test_SubmitPluginProof_UpdatesScore() public {
        // Register plugin & allow enclave
        aggregator.registerProofPlugin(teePlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        teePlugin.allowEnclave(testEnclave);

        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");

        // Create valid attestation proof data
        bytes memory sgxQuote = abi.encodePacked(serviceHash, deliveryHash);
        bytes memory proofData = abi.encode(sgxQuote, testEnclave, bytes32(0), agent);

        // Cache proofType before prank to avoid prank being consumed by proofType() call
        bytes32 pType = teePlugin.proofType();
        vm.prank(agent);
        aggregator.submitPluginProof(pType, serviceHash, deliveryHash, proofData);

        // TEE weight = 2500 bps -> 25 score points
        uint256 score = aggregator.getAgentScore(agent);
        assertEq(score, 25);
    }

    function test_SubmitPluginProof_DuplicateNoScoreIncrease() public {
        aggregator.registerProofPlugin(teePlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        teePlugin.allowEnclave(testEnclave);

        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");

        bytes memory proofData = abi.encode(abi.encodePacked(serviceHash, deliveryHash), testEnclave, bytes32(0), agent);

        vm.startPrank(agent);
        aggregator.submitPluginProof(teePlugin.proofType(), serviceHash, deliveryHash, proofData);
        uint256 score1 = aggregator.getAgentScore(agent);

        aggregator.submitPluginProof(teePlugin.proofType(), serviceHash, deliveryHash, proofData);
        uint256 score2 = aggregator.getAgentScore(agent);

        assertEq(score1, score2, "Score should not increase on duplicate");
        vm.stopPrank();
    }

    function test_UnknownProofTypeReverts() public {
        bytes32 fakeType = keccak256("UNKNOWN");
        vm.prank(agent);
        vm.expectRevert("Unknown proof type");
        aggregator.submitPluginProof(fakeType, bytes32(0), bytes32(0), new bytes(64));
    }

    function test_PluginWeightContributesToTier() public {
        // Register multiple plugins
        aggregator.registerProofPlugin(teePlugin);
        aggregator.registerProofPlugin(outputHashPlugin);

        // Allow enclave and register provider
        bytes32 testEnclave = keccak256("test-enclave");
        teePlugin.allowEnclave(testEnclave);
        outputHashPlugin.registerProvider(agent);

        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");

        // Submit TEE proof (25 points)
        bytes memory teeProofData =
            abi.encode(abi.encodePacked(serviceHash, deliveryHash), testEnclave, bytes32(0), agent);

        vm.startPrank(agent);
        aggregator.submitPluginProof(teePlugin.proofType(), serviceHash, deliveryHash, teeProofData);

        // Agent should be Bronze (25 > 0)
        assertEq(uint256(aggregator.getAgentTier(agent)), uint256(IVAMSTrustAggregator.TrustTier.BRONZE));

        vm.stopPrank();
    }

    // ============================================================
    //              VERIFY SERVICE DELIVERY (VIEW)
    // ============================================================

    function test_VerifyServiceDelivery_ReturnsWeightAndValidity() public {
        aggregator.registerProofPlugin(teePlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        teePlugin.allowEnclave(testEnclave);

        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");

        bytes memory proofData = abi.encode(abi.encodePacked(serviceHash, deliveryHash), testEnclave, bytes32(0), agent);

        (bool valid, uint256 weight) =
            aggregator.verifyServiceDelivery(serviceHash, deliveryHash, teePlugin.proofType(), proofData);

        assertTrue(valid);
        assertEq(weight, 2500);
    }

    // ============================================================
    //              MIXED LEGACY + PLUGIN TESTS
    // ============================================================

    function test_LegacyAndPluginProofsAccumulate() public {
        aggregator.registerProofPlugin(teePlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        teePlugin.allowEnclave(testEnclave);

        vm.startPrank(agent);

        // Submit legacy proof (ERC8004 = 10 points)
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        uint256 score1 = aggregator.getAgentScore(agent);
        assertEq(score1, 10);

        // Submit plugin proof (TEE = 25 points)
        bytes memory proofData =
            abi.encode(abi.encodePacked(keccak256("svc"), keccak256("dlv")), testEnclave, bytes32(0), agent);
        aggregator.submitPluginProof(teePlugin.proofType(), keccak256("svc"), keccak256("dlv"), proofData);
        uint256 score2 = aggregator.getAgentScore(agent);
        assertEq(score2, 35); // 10 + 25

        // Should be Silver (35 >= 30)
        assertEq(uint256(aggregator.getAgentTier(agent)), uint256(IVAMSTrustAggregator.TrustTier.SILVER));

        vm.stopPrank();
    }

    // ============================================================
    //              ENUMERATION TESTS
    // ============================================================

    function test_GetRegisteredPluginCount() public {
        assertEq(aggregator.getRegisteredPluginCount(), 5);

        aggregator.registerProofPlugin(teePlugin);
        assertEq(aggregator.getRegisteredPluginCount(), 6);

        aggregator.registerProofPlugin(outputHashPlugin);
        assertEq(aggregator.getRegisteredPluginCount(), 7);

        aggregator.deregisterProofPlugin(teePlugin.proofType());
        assertEq(aggregator.getRegisteredPluginCount(), 6);
    }

    function test_HasPluginProof() public {
        aggregator.registerProofPlugin(teePlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        teePlugin.allowEnclave(testEnclave);

        bytes32 pType = teePlugin.proofType();
        assertFalse(aggregator.hasPluginProof(agent, pType));

        bytes memory proofData =
            abi.encode(abi.encodePacked(keccak256("s"), keccak256("d")), testEnclave, bytes32(0), agent);
        vm.prank(agent);
        aggregator.submitPluginProof(pType, keccak256("s"), keccak256("d"), proofData);

        assertTrue(aggregator.hasPluginProof(agent, pType));
    }
}
