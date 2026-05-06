// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/staking/VAMSStaking.sol";
import "../../src/registry/VAMSAgentRegistry.sol";

/**
 * @title AgentLifecycleIntegration
 * @notice Integration tests for agent registration with staking requirements
 * @dev Tests cross-contract interactions:
 *      Agent → Staking → AgentRegistry → Challenge/Finalize
 */
contract AgentLifecycleIntegration is BaseTest {
    VAMSStaking public staking;
    VAMSAgentRegistry public agentRegistry;
    
    // Constants from AgentRegistry
    uint256 constant MIN_REGISTRATION_STAKE = 1000 ether;
    uint256 constant MIN_CHALLENGER_STAKE = 100 ether;
    uint256 constant CHALLENGE_WINDOW = 7 days;
    
    // Staking constants
    uint256 constant EMISSION_RATE = 5e14; // ~0.0005 VAMS/sec, below MAX_EMISSION_RATE
    uint256 constant MIN_STAKE = 50_000 ether;
    
    function setUp() public override {
        super.setUp();
        
        // Deploy staking contract
        vm.prank(admin);
        staking = new VAMSStaking(
            address(token),
            address(token),
            EMISSION_RATE,
            admin
        );
        _mintTo(address(staking), 10_000_000 ether);
        
        // Deploy agent registry
        agentRegistry = new VAMSAgentRegistry();
        agentRegistry.initialize(admin, address(token), slasher);
    }
    
    // ============ Helper Functions ============
    
    function _registerAgent(
        address agentOwner,
        bytes32 publicKeyHash,
        string memory metadata,
        uint256 stake
    ) internal returns (bytes32 agentId) {
        _fundAndApprove(agentOwner, address(agentRegistry), stake);
        
        vm.prank(agentOwner);
        agentId = agentRegistry.registerAgent(publicKeyHash, stake, metadata, address(0));
    }
    
    // ============ Agent Lifecycle Tests ============
    
    function test_FullAgentLifecycle() public {
        // 1. Register agent with stake
        bytes32 publicKeyHash = keccak256("TestAgent-PubKey");
        bytes32 agentId = _registerAgent(
            agent1,
            publicKeyHash,
            "ipfs://agent-metadata",
            MIN_REGISTRATION_STAKE
        );
        
        // Verify registration
        (
            address owner,
            bytes32 pkHash,
            uint256 stake,
            VAMSAgentRegistry.AgentStatus status,
            uint256 registeredAt,
            uint256 finalizedAt,
            bytes32 latestMerkleRoot
        ) = agentRegistry.getAgent(agentId);
        
        assertEq(owner, agent1);
        assertEq(pkHash, publicKeyHash);
        assertEq(stake, MIN_REGISTRATION_STAKE);
        assertEq(uint(status), uint(VAMSAgentRegistry.AgentStatus.PENDING));
        
        // 2. Wait for challenge window
        _advanceTime(CHALLENGE_WINDOW + 1);
        
        // 3. Finalize agent
        vm.prank(agent1);
        agentRegistry.finalizeAgent(agentId);
        
        // Verify finalization
        (, , , status, , ,) = agentRegistry.getAgent(agentId);
        assertEq(uint(status), uint(VAMSAgentRegistry.AgentStatus.ACTIVE));
        
        // 4. Submit Merkle root (owner only)
        bytes32 merkleRoot = keccak256("merkle root");
        
        vm.prank(agent1);
        agentRegistry.submitMerkleRoot(agentId, merkleRoot);
        
        (, , , , , , latestMerkleRoot) = agentRegistry.getAgent(agentId);
        assertEq(latestMerkleRoot, merkleRoot);
        
        // 5. Deregister agent
        uint256 agent1BalanceBefore = token.balanceOf(agent1);
        
        vm.prank(agent1);
        agentRegistry.deregisterAgent(agentId);
        
        // Verify deregistration and stake return
        (, , stake, status, , ,) = agentRegistry.getAgent(agentId);
        assertEq(uint(status), uint(VAMSAgentRegistry.AgentStatus.DEREGISTERED));
        assertEq(token.balanceOf(agent1), agent1BalanceBefore + MIN_REGISTRATION_STAKE);
    }
    
    function test_AgentChallenge_FraudProven() public {
        // 1. Register agent
        bytes32 agentId = _registerAgent(
            agent1,
            keccak256("SuspiciousAgent-PubKey"),
            "ipfs://suspicious",
            MIN_REGISTRATION_STAKE
        );
        
        // 2. Challenger submits challenge
        _fundAndApprove(user1, address(agentRegistry), MIN_CHALLENGER_STAKE);
        
        bytes32 fraudProofHash = keccak256("fraud proof data");
        
        vm.prank(user1);
        bytes32 challengeId = agentRegistry.submitChallenge(
            agentId,
            fraudProofHash,
            MIN_CHALLENGER_STAKE,
            "ipfs://evidence"
        );
        
        // Verify challenge state
        (, , , VAMSAgentRegistry.AgentStatus status, , ,) = agentRegistry.getAgent(agentId);
        assertEq(uint(status), uint(VAMSAgentRegistry.AgentStatus.CHALLENGED));
        
        // 3. Guardian resolves challenge - fraud proven
        uint256 challengerBefore = token.balanceOf(user1);
        
        vm.prank(admin); // Admin has GUARDIAN_ROLE
        agentRegistry.resolveChallenge(challengeId, true, "");
        
        // Verify challenger gets stake back + reward (50% of agent stake)
        uint256 reward = (MIN_REGISTRATION_STAKE * 5000) / 10000; // 50% of agent stake
        assertEq(
            token.balanceOf(user1), 
            challengerBefore + MIN_CHALLENGER_STAKE + reward
        );
        
        // Verify agent is slashed
        (, , , status, , ,) = agentRegistry.getAgent(agentId);
        assertEq(uint(status), uint(VAMSAgentRegistry.AgentStatus.SLASHED));
    }
    
    function test_AgentChallenge_Rejected() public {
        // 1. Register agent
        bytes32 agentId = _registerAgent(
            agent1,
            keccak256("HonestAgent-PubKey"),
            "ipfs://honest",
            MIN_REGISTRATION_STAKE
        );
        
        // 2. False challenge submitted
        _fundAndApprove(user1, address(agentRegistry), MIN_CHALLENGER_STAKE);
        
        vm.prank(user1);
        bytes32 challengeId = agentRegistry.submitChallenge(
            agentId,
            keccak256("false fraud proof"),
            MIN_CHALLENGER_STAKE,
            "ipfs://false-evidence"
        );
        
        // 3. Challenge rejected - agent vindicated
        uint256 challengerBefore = token.balanceOf(user1);
        
        vm.prank(admin); // Admin has GUARDIAN_ROLE
        agentRegistry.resolveChallenge(challengeId, false, "");
        
        // Verify challenger loses stake (no refund)
        assertEq(token.balanceOf(user1), challengerBefore);
        
        // Verify agent returns to active status
        (, , , VAMSAgentRegistry.AgentStatus status, , ,) = agentRegistry.getAgent(agentId);
        assertEq(uint(status), uint(VAMSAgentRegistry.AgentStatus.ACTIVE));
    }
    
    function test_MultipleAgents_SameOwner() public {
        // Register multiple agents from same owner
        bytes32 agentId1 = _registerAgent(agent1, keccak256("Agent1-PubKey"), "ipfs://1", MIN_REGISTRATION_STAKE);
        bytes32 agentId2 = _registerAgent(agent1, keccak256("Agent2-PubKey"), "ipfs://2", MIN_REGISTRATION_STAKE);
        bytes32 agentId3 = _registerAgent(agent1, keccak256("Agent3-PubKey"), "ipfs://3", MIN_REGISTRATION_STAKE);
        
        // Verify all registered
        bytes32[] memory ownedAgents = agentRegistry.getAgentsByOwner(agent1);
        assertEq(ownedAgents.length, 3);
        
        // Finalize all after window
        _advanceTime(CHALLENGE_WINDOW + 1);
        
        vm.startPrank(agent1);
        agentRegistry.finalizeAgent(agentId1);
        agentRegistry.finalizeAgent(agentId2);
        agentRegistry.finalizeAgent(agentId3);
        vm.stopPrank();
        
        // All should be active
        (, , , VAMSAgentRegistry.AgentStatus status1, , ,) = agentRegistry.getAgent(agentId1);
        (, , , VAMSAgentRegistry.AgentStatus status2, , ,) = agentRegistry.getAgent(agentId2);
        (, , , VAMSAgentRegistry.AgentStatus status3, , ,) = agentRegistry.getAgent(agentId3);
        
        assertEq(uint(status1), uint(VAMSAgentRegistry.AgentStatus.ACTIVE));
        assertEq(uint(status2), uint(VAMSAgentRegistry.AgentStatus.ACTIVE));
        assertEq(uint(status3), uint(VAMSAgentRegistry.AgentStatus.ACTIVE));
    }
    
    function test_StakedUser_CanRegisterAgent() public {
        // First stake tokens in staking contract
        _fundAndApprove(user1, address(staking), MIN_STAKE);
        
        vm.prank(user1);
        staking.stake(MIN_STAKE, IVAMSStaking.LockPeriod.SevenDays);
        
        // Now register agent (separate transaction)
        bytes32 agentId = _registerAgent(
            user1,
            keccak256("StakedUserAgent-PubKey"),
            "ipfs://staked-user",
            MIN_REGISTRATION_STAKE
        );
        
        // Verify registration
        (address owner, , , , , ,) = agentRegistry.getAgent(agentId);
        assertEq(owner, user1);
        
        // Verify user still has staking position
        IVAMSStaking.StakeInfo memory stakeInfo = staking.getStakeInfo(user1);
        assertEq(stakeInfo.amount, MIN_STAKE);
    }
    
    function test_TEEAttestation_Update() public {
        // Register agent
        bytes32 agentId = _registerAgent(
            agent1,
            keccak256("TEEAgent-PubKey"),
            "ipfs://tee-agent",
            MIN_REGISTRATION_STAKE
        );
        
        // Wait and finalize
        _advanceTime(CHALLENGE_WINDOW + 1);
        vm.prank(agent1);
        agentRegistry.finalizeAgent(agentId);
        
        // Update TEE attestation
        bytes32 newAttestation = keccak256("new attestation");
        
        vm.prank(agent1);
        agentRegistry.updateTEEAttestation(agentId, newAttestation);
        
        // Verify update via agents mapping (direct access to teeAttestation)
        (address owner, bytes32 publicKeyHash, bytes32 teeAttestation,,,,,,,,) = agentRegistry.agents(agentId);
        assertEq(teeAttestation, newAttestation);
    }
    
    function test_MerkleHistory_Tracked() public {
        // Register and finalize agent
        bytes32 agentId = _registerAgent(
            agent1,
            keccak256("MerkleAgent-PubKey"),
            "ipfs://merkle",
            MIN_REGISTRATION_STAKE
        );
        _advanceTime(CHALLENGE_WINDOW + 1);
        vm.prank(agent1);
        agentRegistry.finalizeAgent(agentId);
        
        // Submit multiple Merkle roots
        bytes32[] memory roots = new bytes32[](3);
        
        vm.startPrank(agent1);
        for (uint256 i = 0; i < 3; i++) {
            roots[i] = keccak256(abi.encodePacked("root", i));
            agentRegistry.submitMerkleRoot(agentId, roots[i]);
        }
        vm.stopPrank();
        
        // Verify history
        VAMSAgentRegistry.MerkleSubmission[] memory history = agentRegistry.getMerkleHistory(agentId);
        assertEq(history.length, 3);
        assertEq(history[2].merkleRoot, roots[2]); // Latest
    }
    
    // ============ Edge Case Tests ============
    
    function test_CannotFinalize_BeforeWindow() public {
        bytes32 agentId = _registerAgent(
            agent1,
            keccak256("Test-PubKey"),
            "ipfs://test",
            MIN_REGISTRATION_STAKE
        );
        
        // Try to finalize before window expires
        _advanceTime(CHALLENGE_WINDOW - 1 hours);
        
        vm.prank(agent1);
        vm.expectRevert();
        agentRegistry.finalizeAgent(agentId);
    }
    
    function test_CannotDeregister_NotOwner() public {
        bytes32 agentId = _registerAgent(
            agent1,
            keccak256("Test-PubKey"),
            "ipfs://test",
            MIN_REGISTRATION_STAKE
        );
        
        _advanceTime(CHALLENGE_WINDOW + 1);
        vm.prank(agent1);
        agentRegistry.finalizeAgent(agentId);
        
        // Try to deregister as non-owner
        vm.prank(user1);
        vm.expectRevert();
        agentRegistry.deregisterAgent(agentId);
    }
    
    function test_ChallengeMustMeetMinStake() public {
        bytes32 agentId = _registerAgent(
            agent1,
            keccak256("Test-PubKey"),
            "ipfs://test",
            MIN_REGISTRATION_STAKE
        );
        
        // Try to challenge with insufficient stake
        _fundAndApprove(user1, address(agentRegistry), MIN_CHALLENGER_STAKE - 1);
        
        vm.prank(user1);
        vm.expectRevert();
        agentRegistry.submitChallenge(
            agentId,
            keccak256("fraud"),
            MIN_CHALLENGER_STAKE - 1,
            "ipfs://evidence"
        );
    }
    
    // ============ Fuzz Tests ============
    
    function testFuzz_AgentStakeAmount(uint256 stakeAmount) public {
        stakeAmount = bound(stakeAmount, MIN_REGISTRATION_STAKE, 1_000_000 ether);
        
        bytes32 agentId = _registerAgent(
            agent1,
            keccak256(abi.encodePacked("Fuzz-PubKey", stakeAmount)),
            "ipfs://fuzz",
            stakeAmount
        );
        
        (, , uint256 stake, , , ,) = agentRegistry.getAgent(agentId);
        assertEq(stake, stakeAmount);
        
        // Finalize and deregister to get stake back
        _advanceTime(CHALLENGE_WINDOW + 1);
        
        uint256 balanceBefore = token.balanceOf(agent1);
        
        vm.startPrank(agent1);
        agentRegistry.finalizeAgent(agentId);
        agentRegistry.deregisterAgent(agentId);
        vm.stopPrank();
        
        assertEq(token.balanceOf(agent1), balanceBefore + stakeAmount);
    }
}
