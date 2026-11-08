// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console} from "forge-std/Test.sol";
import {VAMSTrustAggregator} from "../src/trust/VAMSTrustAggregator.sol";
import {IVAMSTrustAggregator} from "../src/interfaces/IVAMSTrustAggregator.sol";
import {IVAMSProofPlugin} from "../src/interfaces/IVAMSProofPlugin.sol";
import {IComposedSettlement} from "../src/economic/IComposedSettlement.sol";
import {TEEProofPlugin} from "../src/trust/plugins/TEEProofPlugin.sol";
import {OutputHashProofPlugin} from "../src/trust/plugins/OutputHashProofPlugin.sol";
import {ERC8004IdentityPlugin} from "../src/trust/plugins/ERC8004IdentityPlugin.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract MockLegacyPlugin is IVAMSProofPlugin {
    bytes32 private _type;
    constructor(bytes32 t) { _type = t; }
    function proofType() external view override returns (bytes32) { return _type; }
    function verify(bytes32, bytes32, bytes calldata proofData) external pure override returns (bool) {
        return proofData.length >= 64;
    }
    function trustWeight() external pure override returns (uint256) { return 1000; }
    function name() external pure override returns (string memory) { return "Mock Legacy"; }
}

// Test-only fixture for aggregator arithmetic, with no attestation claim.
contract MockScoringPlugin is IVAMSProofPlugin {
    function proofType() external pure returns (bytes32) { return keccak256("TEST_ONLY_SCORING"); }
    function verify(bytes32, bytes32, bytes calldata proof) external pure returns (bool) { return proof.length >= 64; }
    function trustWeight() external pure returns (uint256) { return 2500; }
    function name() external pure returns (string memory) { return "Test-only scoring"; }
    function allowEnclave(bytes32) external pure {} // No hardware semantics.
}

// Trusted-source boundary fixture only; not authentic service or ledger evidence.
contract SettledEvidenceFixture {
    address public root;
    bool public claimed = true;
    constructor(address provider) { root = provider; }
    function unsettle() external { claimed = false; }
    function getProviderAlloc(bytes32, uint256) external view returns (IComposedSettlement.ProviderAlloc memory) {
        return IComposedSettlement.ProviderAlloc(root, 100, claimed, 1);
    }
    function verifiedProviderProofs(bytes32, uint256) external pure returns (bool) { return true; }
    function deliveredOutputHash(bytes32, uint256) external pure returns (bytes32) { return keccak256("output"); }
    function getDeliveryContext(bytes32, uint256) external pure returns (bytes32) { return keccak256("context"); }
}

contract VAMSTrustAggregatorTest is Test {
    VAMSTrustAggregator public aggregator;
    TEEProofPlugin public teePlugin;
    MockScoringPlugin public scoringPlugin;
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
        bytes memory initData = abi.encodeWithSelector(
            VAMSTrustAggregator.initialize.selector
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), initData);
        aggregator = VAMSTrustAggregator(address(proxy));

        // Deploy plugins
        teePlugin = new TEEProofPlugin(owner);
        scoringPlugin = new MockScoringPlugin();
        outputHashPlugin = new OutputHashProofPlugin(owner);
        identityPlugin = new ERC8004IdentityPlugin(address(0x789));

        aggregator.registerProofPlugin(new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY))));
        aggregator.registerProofPlugin(new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.POLYGON_ID))));
        aggregator.registerProofPlugin(new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.COINBASE_WALLET))));
        aggregator.registerProofPlugin(new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.PARALLEL_RESEARCH))));
        aggregator.registerProofPlugin(new MockLegacyPlugin(bytes32(uint256(IVAMSTrustAggregator.ProofType.PHALA_EXECUTION))));
    }

    // ============================================================
    //              LEGACY TESTS (Backward Compatibility)
    // ============================================================

    function test_InitialState() public view {
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint(tier), uint(IVAMSTrustAggregator.TrustTier.UNVERIFIED));
    }

    function test_SubmitIdentityProof_UpdatesTier() public {
        vm.startPrank(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint(tier), uint(IVAMSTrustAggregator.TrustTier.BRONZE));
        vm.stopPrank();
    }

    function test_AggregateProofs_ReachesSilver() public {
        vm.startPrank(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.POLYGON_ID, new bytes(64));
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint(tier), uint(IVAMSTrustAggregator.TrustTier.SILVER));
        vm.stopPrank();
    }

    function test_AggregateProofs_ReachesGold() public {
        vm.startPrank(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.COINBASE_WALLET, new bytes(64)); 
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.PARALLEL_RESEARCH, new bytes(64));
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.PHALA_EXECUTION, new bytes(64));
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint(tier), uint(IVAMSTrustAggregator.TrustTier.GOLD));
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
        aggregator.registerProofPlugin(scoringPlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        scoringPlugin.allowEnclave(testEnclave);

        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");

        // Synthetic payload for scoring arithmetic only
        bytes memory sgxQuote = abi.encodePacked(serviceHash, deliveryHash);
        bytes memory proofData = abi.encode(
            sgxQuote,
            testEnclave,
            bytes32(0),
            agent
        );

        // Cache proofType before prank to avoid prank being consumed by proofType() call
        bytes32 pType = scoringPlugin.proofType();
        vm.prank(agent);
        aggregator.submitPluginProof(
            pType,
            serviceHash,
            deliveryHash,
            proofData
        );

        // Test fixture weight = 2500 bps -> 25 score points
        uint256 score = aggregator.getAgentScore(agent);
        assertEq(score, 25);
    }

    function test_SubmitPluginProof_DuplicateNoScoreIncrease() public {
        aggregator.registerProofPlugin(scoringPlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        scoringPlugin.allowEnclave(testEnclave);

        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");

        bytes memory proofData = abi.encode(
            abi.encodePacked(serviceHash, deliveryHash),
            testEnclave,
            bytes32(0),
            agent
        );

        vm.startPrank(agent);
        aggregator.submitPluginProof(scoringPlugin.proofType(), serviceHash, deliveryHash, proofData);
        uint256 score1 = aggregator.getAgentScore(agent);
        
        aggregator.submitPluginProof(scoringPlugin.proofType(), serviceHash, deliveryHash, proofData);
        uint256 score2 = aggregator.getAgentScore(agent);
        
        assertEq(score1, score2, "Score should not increase on duplicate");
        vm.stopPrank();
    }

    function test_UnknownProofTypeReverts() public {
        bytes32 fakeType = keccak256("UNKNOWN");
        vm.prank(agent);
        vm.expectRevert("Unknown proof type");
        aggregator.submitPluginProof(
            fakeType,
            bytes32(0),
            bytes32(0),
            new bytes(64)
        );
    }

    function test_PluginWeightContributesToTier() public {
        // Register multiple plugins
        aggregator.registerProofPlugin(scoringPlugin);
        aggregator.registerProofPlugin(outputHashPlugin);

        // Allow enclave and register provider
        bytes32 testEnclave = keccak256("test-enclave");
        scoringPlugin.allowEnclave(testEnclave);
        outputHashPlugin.registerProvider(agent);

        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");

        // Submit test-only scoring fixture (25 points)
        bytes memory teeProofData = abi.encode(
            abi.encodePacked(serviceHash, deliveryHash),
            testEnclave,
            bytes32(0),
            agent
        );

        vm.startPrank(agent);
        aggregator.submitPluginProof(scoringPlugin.proofType(), serviceHash, deliveryHash, teeProofData);

        // Agent should be Bronze (25 > 0)
        assertEq(uint(aggregator.getAgentTier(agent)), uint(IVAMSTrustAggregator.TrustTier.BRONZE));
        
        vm.stopPrank();
    }

    // ============================================================
    //              VERIFY SERVICE DELIVERY (VIEW)
    // ============================================================

    function test_VerifyServiceDelivery_ReturnsWeightAndValidity() public {
        aggregator.registerProofPlugin(scoringPlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        scoringPlugin.allowEnclave(testEnclave);

        bytes32 serviceHash = keccak256("service");
        bytes32 deliveryHash = keccak256("delivery");

        bytes memory proofData = abi.encode(
            abi.encodePacked(serviceHash, deliveryHash),
            testEnclave,
            bytes32(0),
            agent
        );

        (bool valid, uint256 weight) = aggregator.verifyServiceDelivery(
            serviceHash, deliveryHash, scoringPlugin.proofType(), proofData
        );

        assertTrue(valid);
        assertEq(weight, 2500);
    }

    // ============================================================
    //              MIXED LEGACY + PLUGIN TESTS
    // ============================================================

    function test_LegacyAndPluginProofsAccumulate() public {
        aggregator.registerProofPlugin(scoringPlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        scoringPlugin.allowEnclave(testEnclave);

        vm.startPrank(agent);

        // Submit legacy proof (ERC8004 = 10 points)
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        uint256 score1 = aggregator.getAgentScore(agent);
        assertEq(score1, 10);

        // Submit test-only scoring fixture (25 points)
        bytes memory proofData = abi.encode(
            abi.encodePacked(keccak256("svc"), keccak256("dlv")),
            testEnclave,
            bytes32(0),
            agent
        );
        aggregator.submitPluginProof(
            scoringPlugin.proofType(),
            keccak256("svc"),
            keccak256("dlv"),
            proofData
        );
        uint256 score2 = aggregator.getAgentScore(agent);
        assertEq(score2, 35); // 10 + 25

        // Should be Silver (35 >= 30)
        assertEq(uint(aggregator.getAgentTier(agent)), uint(IVAMSTrustAggregator.TrustTier.SILVER));

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
        aggregator.registerProofPlugin(scoringPlugin);
        bytes32 testEnclave = keccak256("test-enclave");
        scoringPlugin.allowEnclave(testEnclave);

        bytes32 pType = scoringPlugin.proofType();
        assertFalse(aggregator.hasPluginProof(agent, pType));

        bytes memory proofData = abi.encode(abi.encodePacked(keccak256("s"), keccak256("d")), testEnclave, bytes32(0), agent);
        vm.prank(agent);
        aggregator.submitPluginProof(pType, keccak256("s"), keccak256("d"), proofData);

        assertTrue(aggregator.hasPluginProof(agent, pType));
    }
    function test_RetiredTEERejectsConcatenationForgeryForRootAndRelay() public {
        aggregator.registerProofPlugin(teePlugin);
        bytes32 enclave=keccak256("test-enclave");
        teePlugin.allowEnclave(enclave);
        bytes32 service=keccak256("service"); bytes32 output=keccak256("output");
        bytes memory forgery=abi.encode(abi.encodePacked(service,output),enclave,bytes32(0),agent);
        bytes32 kind=teePlugin.proofType();
        vm.prank(agent);
        vm.expectRevert("Plugin proof verification failed");
        aggregator.submitPluginProof(kind,service,output,forgery);
        vm.prank(nonOwner);
        vm.expectRevert("Plugin proof verification failed");
        aggregator.submitPluginProof(kind,service,output,forgery);
        assertEq(aggregator.getAgentScore(agent),0);
        assertEq(aggregator.getAgentScore(nonOwner),0);
        assertEq(teePlugin.trustWeight(),0);
    }

    function test_RelayCannotAttributeSettledEvidenceToItself() public {
        SettledEvidenceFixture source = new SettledEvidenceFixture(agent);
        aggregator.setSettlementEvidenceSource(address(source),address(source).codehash);
        vm.prank(nonOwner);
        bytes32 key=aggregator.submitSettledDeliveryProof(address(source),keccak256("allocation"),0);
        assertEq(aggregator.settledDeliveryRoots(key),agent);
        assertEq(aggregator.getAgentScore(nonOwner),0);
        assertEq(aggregator.getAgentScore(agent),0); // Evidence records do not invent trust weights.
        vm.expectRevert("Delivery evidence already recorded");
        aggregator.submitSettledDeliveryProof(address(source),keccak256("allocation"),0);
    }

    function test_UnapprovedOrUnsettledEvidenceCannotBeAttributed() public {
        SettledEvidenceFixture source = new SettledEvidenceFixture(agent);
        vm.expectRevert("Unapproved evidence source");
        aggregator.submitSettledDeliveryProof(address(source),keccak256("allocation"),0);
        aggregator.setSettlementEvidenceSource(address(source),address(source).codehash);
        source.unsettle();
        vm.expectRevert("Unsettled delivery");
        aggregator.submitSettledDeliveryProof(address(source),keccak256("allocation"),0);
    }

    function test_NewEvidenceSourcesRequireGovernanceAndExactCode() public {
        SettledEvidenceFixture source = new SettledEvidenceFixture(agent);
        vm.prank(nonOwner);
        vm.expectRevert();
        aggregator.setSettlementEvidenceSource(address(source),address(source).codehash);
        vm.expectRevert("Evidence source identity mismatch");
        aggregator.setSettlementEvidenceSource(address(source),bytes32(uint256(1)));
    }

    function test_ImplementationAndProxyCannotBeReinitialized() public {
        VAMSTrustAggregator implementation = new VAMSTrustAggregator();
        bytes4 invalidInitialization = bytes4(keccak256("InvalidInitialization()"));
        vm.expectRevert(invalidInitialization);
        implementation.initialize();
        vm.expectRevert(invalidInitialization);
        aggregator.initialize();
        assertTrue(aggregator.hasRole(aggregator.DEFAULT_ADMIN_ROLE(), owner));
    }

    function test_UnauthorizedProxyUpgradeRejects() public {
        VAMSTrustAggregator replacement = new VAMSTrustAggregator();
        bytes32 upgrader = aggregator.UPGRADER_ROLE();
        vm.prank(nonOwner);
        vm.expectRevert(abi.encodeWithSignature(
            "AccessControlUnauthorizedAccount(address,bytes32)", nonOwner, upgrader
        ));
        aggregator.upgradeToAndCall(address(replacement), bytes(""));
        assertTrue(aggregator.hasRole(upgrader, owner));
        assertFalse(aggregator.hasRole(upgrader, nonOwner));
    }

    /// @dev Current implementation -> current implementation only. The separate
    /// compiled layout comparison covers the preserved pre-change storage shape;
    /// neither check qualifies an unknown deployed implementation or live custody.
    function test_AuthorizedProxyUpgradePreservesProfileAndSettledEvidence() public {
        // Explicit synthetic scoring collaborator, not an authentic identity proof.
        vm.prank(agent);
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, new bytes(64));
        uint256 score = aggregator.getAgentScore(agent);
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        SettledEvidenceFixture source = new SettledEvidenceFixture(agent);
        bytes32 sourceCodeHash = address(source).codehash;
        aggregator.setSettlementEvidenceSource(address(source), sourceCodeHash);
        bytes32 allocation = keccak256("LOCAL-UPGRADE-STATE-FIXTURE");
        bytes32 evidenceKey = aggregator.submitSettledDeliveryProof(address(source), allocation, 0);

        VAMSTrustAggregator replacement = new VAMSTrustAggregator();
        aggregator.upgradeToAndCall(address(replacement), bytes(""));

        assertEq(aggregator.getAgentScore(agent), score);
        assertEq(uint256(aggregator.getAgentTier(agent)), uint256(tier));
        assertEq(aggregator.governancePhase(), 1);
        assertTrue(aggregator.hasRole(aggregator.DEFAULT_ADMIN_ROLE(), owner));
        assertTrue(aggregator.hasRole(aggregator.UPGRADER_ROLE(), owner));
        assertEq(aggregator.settlementEvidenceSources(address(source)), sourceCodeHash);
        assertEq(aggregator.settledDeliveryRoots(evidenceKey), agent);
        vm.expectRevert("Delivery evidence already recorded");
        aggregator.submitSettledDeliveryProof(address(source), allocation, 0);
    }

}
