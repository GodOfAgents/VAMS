// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console} from "forge-std/Test.sol";
import {VAMSTrustAggregator} from "../src/trust/VAMSTrustAggregator.sol";
import {IVAMSTrustAggregator} from "../src/interfaces/IVAMSTrustAggregator.sol";
import {Upgrades} from "openzeppelin-foundry-upgrades/Upgrades.sol";

contract VAMSTrustAggregatorTest is Test {
    VAMSTrustAggregator public aggregator;
    address public agent;

    function setUp() public {
        // Deploy Proxy
        address proxy = Upgrades.deployUUPSProxy(
            "VAMSTrustAggregator.sol",
            abi.encodeCall(VAMSTrustAggregator.initialize, ())
        );
        aggregator = VAMSTrustAggregator(proxy);
        agent = address(0x123);
    }

    function test_InitialState() public {
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint(tier), uint(IVAMSTrustAggregator.TrustTier.UNVERIFIED));
    }

    function test_SubmitIdentityProof_UpdatesTier() public {
        vm.startPrank(agent);

        // 1. Submit ERC-8004 Identity (Weight: 10) -> BRONZE (Score > 0)
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, hex"1234");
        
        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint(tier), uint(IVAMSTrustAggregator.TrustTier.BRONZE));
        
        vm.stopPrank();
    }

    function test_AggregateProofs_ReachesSilver() public {
        vm.startPrank(agent);

        // 1. ERC-8004 (10)
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, hex"11");
        
        // 2. Polygon ID (20) -> Total 30 (Silver Threshold)
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.POLYGON_ID, hex"22");

        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint(tier), uint(IVAMSTrustAggregator.TrustTier.SILVER));

        vm.stopPrank();
    }

    function test_AggregateProofs_ReachesGold() public {
        vm.startPrank(agent);

        // Needs 70 points for Gold
        
        // Identity (30)
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.COINBASE_WALLET, hex"AA"); 
        
        // Verification (20 + 25 = 45) -> Total 75
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.PARALLEL_RESEARCH, hex"BB");
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.PHALA_EXECUTION, hex"CC");

        IVAMSTrustAggregator.TrustTier tier = aggregator.getAgentTier(agent);
        assertEq(uint(tier), uint(IVAMSTrustAggregator.TrustTier.GOLD));

        vm.stopPrank();
    }

    function test_CannotSubmitSameProofTwice() public {
        vm.startPrank(agent);

        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, hex"11");
        uint256 score1 = aggregator.getAgentScore(agent);

        // Submit again - should not increase score
        aggregator.submitProof(IVAMSTrustAggregator.ProofType.ERC8004_IDENTITY, hex"11");
        uint256 score2 = aggregator.getAgentScore(agent);

        assertEq(score1, score2);

        vm.stopPrank();
    }
}
