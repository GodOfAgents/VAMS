// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/registry/VAMSAgentRegistry.sol";

contract MockERC20 {
    string public name = "VAMS Token";
    string public symbol = "VAMS";
    uint8 public decimals = 18;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
        totalSupply += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(allowance[from][msg.sender] >= amount, "Insufficient allowance");
        require(balanceOf[from] >= amount, "Insufficient balance");

        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

/**
 * @title VAMSAgentRegistryTest
 * @notice Comprehensive tests for VAMSAgentRegistry contract
 */
contract VAMSAgentRegistryTest is Test {
    VAMSAgentRegistry public registry;
    MockERC20 public token;

    address public admin = address(1);
    address public agentOwner = address(2);
    address public challenger = address(3);
    address public guardian = address(4);
    address public slasher = address(6);

    bytes32 public constant TEST_PUBLIC_KEY_HASH = keccak256("test_agent_public_key");
    string public constant TEST_METADATA = "ipfs://QmTest123";

    // ============ Setup ============

    function setUp() public {
        registry = new VAMSAgentRegistry();
        token = new MockERC20();

        registry.initialize(admin, address(token), slasher);

        // Grant roles
        vm.startPrank(admin);
        registry.grantRole(registry.GUARDIAN_ROLE(), guardian);
        registry.grantRole(registry.CHALLENGER_ROLE(), challenger);
        vm.stopPrank();

        // Mint tokens
        token.mint(agentOwner, 1_000_000 ether);
        token.mint(challenger, 1_000_000 ether);
    }

    // ============ Initialization Tests ============

    function test_Initialize() public view {
        assertEq(registry.vamsToken(), address(token));
        assertEq(registry.slasher(), slasher);
        assertTrue(registry.hasRole(registry.DEFAULT_ADMIN_ROLE(), admin));
    }

    function test_Initialize_RevertOnZeroAddress() public {
        VAMSAgentRegistry newRegistry = new VAMSAgentRegistry();

        vm.expectRevert(VAMSAgentRegistry.ZeroAddress.selector);
        newRegistry.initialize(address(0), address(token), slasher);
    }

    function test_Constants() public view {
        assertEq(registry.CHALLENGE_WINDOW(), 7 days);
        assertEq(registry.MIN_REGISTRATION_STAKE(), 1000 ether);
        assertEq(registry.MIN_CHALLENGER_STAKE(), 100 ether);
        assertEq(registry.CHALLENGER_REWARD_BPS(), 5000);
    }

    // ============ Agent Registration Tests ============

    function test_RegisterAgent() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);

        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));

        vm.stopPrank();

        (
            address owner,
            bytes32 publicKeyHash,
            uint256 stake,
            VAMSAgentRegistry.AgentStatus status,
            uint256 registeredAt,
            uint256 finalizedAt,
            bytes32 latestMerkleRoot
        ) = registry.getAgent(agentId);

        assertEq(owner, agentOwner);
        assertEq(publicKeyHash, TEST_PUBLIC_KEY_HASH);
        assertEq(stake, 1000 ether);
        assertEq(uint256(status), uint256(VAMSAgentRegistry.AgentStatus.PENDING));
        assertEq(finalizedAt, registeredAt + 7 days);
        assertEq(latestMerkleRoot, bytes32(0));

        // Check token balance
        assertEq(token.balanceOf(address(registry)), 1000 ether);
    }

    function test_RegisterAgent_IncrementsTotalAgents() public {
        assertEq(registry.totalAgents(), 0);

        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        assertEq(registry.totalAgents(), 1);
    }

    function test_RegisterAgent_RevertOnInsufficientStake() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 500 ether);

        vm.expectRevert(abi.encodeWithSelector(VAMSAgentRegistry.InsufficientStake.selector, 1000 ether, 500 ether));
        registry.registerAgent(TEST_PUBLIC_KEY_HASH, 500 ether, TEST_METADATA, address(0));

        vm.stopPrank();
    }

    function test_GetAgentsByOwner() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 2000 ether);

        bytes32 agent1 = registry.registerAgent(keccak256("key1"), 1000 ether, TEST_METADATA, address(0));
        bytes32 agent2 = registry.registerAgent(keccak256("key2"), 1000 ether, TEST_METADATA, address(0));

        vm.stopPrank();

        bytes32[] memory agents = registry.getAgentsByOwner(agentOwner);
        assertEq(agents.length, 2);
        assertEq(agents[0], agent1);
        assertEq(agents[1], agent2);
    }

    // ============ Challenge Window Tests ============

    function test_FinalizeAgent_AfterChallengeWindow() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        // Fast forward 7 days
        vm.warp(block.timestamp + 7 days);

        registry.finalizeAgent(agentId);

        (,,, VAMSAgentRegistry.AgentStatus status,,,) = registry.getAgent(agentId);
        assertEq(uint256(status), uint256(VAMSAgentRegistry.AgentStatus.ACTIVE));
    }

    function test_FinalizeAgent_RevertBeforeChallengeWindow() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        // Only 3 days passed
        vm.warp(block.timestamp + 3 days);

        vm.expectRevert(
            abi.encodeWithSelector(VAMSAgentRegistry.ChallengeWindowNotExpired.selector, block.timestamp + 4 days)
        );
        registry.finalizeAgent(agentId);
    }

    function test_IsChallengeWindowExpired() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        assertFalse(registry.isChallengeWindowExpired(agentId));

        vm.warp(block.timestamp + 7 days);
        assertTrue(registry.isChallengeWindowExpired(agentId));
    }

    function test_GetChallengeWindowRemaining() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        assertEq(registry.getChallengeWindowRemaining(agentId), 7 days);

        vm.warp(block.timestamp + 3 days);
        assertEq(registry.getChallengeWindowRemaining(agentId), 4 days);

        vm.warp(block.timestamp + 5 days);
        assertEq(registry.getChallengeWindowRemaining(agentId), 0);
    }

    // ============ Merkle Root Tests ============

    function test_SubmitMerkleRoot() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));

        bytes32 merkleRoot = keccak256("state_root_1");
        registry.submitMerkleRoot(agentId, merkleRoot);
        vm.stopPrank();

        (,,,,,, bytes32 latestRoot) = registry.getAgent(agentId);
        assertEq(latestRoot, merkleRoot);
    }

    function test_SubmitMerkleRoot_RevertNotOwner() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        vm.startPrank(challenger);
        vm.expectRevert(VAMSAgentRegistry.NotAuthorizedCaller.selector);
        registry.submitMerkleRoot(agentId, keccak256("bad"));
        vm.stopPrank();
    }

    function test_MerkleHistory() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));

        registry.submitMerkleRoot(agentId, keccak256("root1"));
        vm.warp(block.timestamp + 1 hours);
        registry.submitMerkleRoot(agentId, keccak256("root2"));
        vm.stopPrank();

        VAMSAgentRegistry.MerkleSubmission[] memory history = registry.getMerkleHistory(agentId);
        assertEq(history.length, 2);
        assertEq(history[0].merkleRoot, keccak256("root1"));
        assertEq(history[1].merkleRoot, keccak256("root2"));
    }

    // ============ TEE Attestation Tests ============

    function test_UpdateTEEAttestation() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));

        bytes32 attestation = keccak256("sgx_attestation");
        registry.updateTEEAttestation(agentId, attestation);
        vm.stopPrank();

        // Note: teeAttestation is stored but not exposed in getAgent()
        // This test verifies the function doesn't revert
    }

    // ============ Challenge Tests ============

    function test_SubmitChallenge() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        vm.startPrank(challenger);
        token.approve(address(registry), 100 ether);
        registry.submitChallenge(agentId, keccak256("fraud_proof"), 100 ether, "ipfs://evidence");
        vm.stopPrank();

        assertEq(registry.totalChallenges(), 1);
        assertEq(token.balanceOf(address(registry)), 1100 ether); // 1000 agent + 100 challenger

        (,,, VAMSAgentRegistry.AgentStatus status,,,) = registry.getAgent(agentId);
        assertEq(uint256(status), uint256(VAMSAgentRegistry.AgentStatus.CHALLENGED));
    }

    function test_SubmitChallenge_RevertInsufficientStake() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        vm.startPrank(challenger);
        token.approve(address(registry), 50 ether);
        vm.expectRevert(abi.encodeWithSelector(VAMSAgentRegistry.InsufficientStake.selector, 100 ether, 50 ether));
        registry.submitChallenge(agentId, keccak256("fraud"), 50 ether, "ipfs://bad");
        vm.stopPrank();
    }

    function test_ResolveChallenge_FraudProven() public {
        // Register and challenge
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        vm.startPrank(challenger);
        token.approve(address(registry), 100 ether);
        bytes32 challengeId = registry.submitChallenge(agentId, keccak256("fraud_proof"), 100 ether, "ipfs://evidence");
        uint256 challengerStartBalance = token.balanceOf(challenger);
        vm.stopPrank();

        // Guardian resolves - fraud proven
        vm.startPrank(guardian);
        registry.resolveChallenge(challengeId, true, "");
        vm.stopPrank();

        (,,, VAMSAgentRegistry.AgentStatus status,,,) = registry.getAgent(agentId);
        assertEq(uint256(status), uint256(VAMSAgentRegistry.AgentStatus.SLASHED));

        // Check rewards
        // Challenger should get: initial stake (100) + 50% of agent stake (500) = 600
        assertEq(token.balanceOf(challenger), challengerStartBalance + 100 ether + 500 ether);
    }

    function test_ResolveChallenge_ChallengeRejected() public {
        // Register and challenge
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        vm.startPrank(challenger);
        token.approve(address(registry), 100 ether);
        bytes32 challengeId =
            registry.submitChallenge(agentId, keccak256("fake_proof"), 100 ether, "ipfs://fakevidence");
        uint256 challengerStartBalance = token.balanceOf(challenger); // Has paid 100
        vm.stopPrank();

        // Guardian resolves - challenge rejected
        vm.startPrank(guardian);
        registry.resolveChallenge(challengeId, false, "");
        vm.stopPrank();

        (,,, VAMSAgentRegistry.AgentStatus status,,,) = registry.getAgent(agentId);
        // Agent returns to ACTIVE state
        assertEq(uint256(status), uint256(VAMSAgentRegistry.AgentStatus.ACTIVE));

        // Challenger loses stake (balance unchanged except check they got nothing back)
        assertEq(token.balanceOf(challenger), challengerStartBalance);
    }

    // ============ Deregistration Tests ============

    function test_DeregisterAgent() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        // Finalize first
        vm.warp(block.timestamp + 7 days);
        registry.finalizeAgent(agentId);

        // Deregister
        vm.startPrank(agentOwner);
        uint256 startBalance = token.balanceOf(agentOwner);
        registry.deregisterAgent(agentId);
        vm.stopPrank();

        (,, uint256 stake, VAMSAgentRegistry.AgentStatus status,,,) = registry.getAgent(agentId);
        assertEq(stake, 0);
        assertEq(uint256(status), uint256(VAMSAgentRegistry.AgentStatus.DEREGISTERED));

        // Check balance returned
        assertEq(token.balanceOf(agentOwner), startBalance + 1000 ether);
    }

    function test_DeregisterAgent_RevertNotOwner() public {
        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        vm.warp(block.timestamp + 7 days);
        registry.finalizeAgent(agentId);

        vm.startPrank(challenger);
        vm.expectRevert(VAMSAgentRegistry.NotAuthorizedCaller.selector);
        registry.deregisterAgent(agentId);
        vm.stopPrank();
    }

    // ============ Admin Tests ============

    function test_Pause() public {
        vm.startPrank(guardian);
        registry.pause();
        vm.stopPrank();

        assertTrue(registry.paused());
    }

    function test_RegisterAgent_RevertWhenPaused() public {
        vm.prank(guardian);
        registry.pause();

        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        vm.expectRevert();
        registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();
    }

    function test_SetSlasher() public {
        address newSlasher = address(999);

        vm.prank(admin);
        registry.setSlasher(newSlasher);

        assertEq(registry.slasher(), newSlasher);
    }

    // ============ Fuzz Tests ============

    function testFuzz_RegisterAgent_StakeAboveMinimum(uint256 stake) public {
        vm.assume(stake >= 1000 ether && stake <= 10_000_000 ether);

        vm.startPrank(agentOwner);
        token.mint(agentOwner, stake);
        token.approve(address(registry), stake);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, stake, TEST_METADATA, address(0));
        vm.stopPrank();

        (,, uint256 actualStake,,,,) = registry.getAgent(agentId);
        assertEq(actualStake, stake);
    }

    function testFuzz_ChallengeWindow_TimePassed(uint256 timePassed) public {
        vm.assume(timePassed < 14 days);

        vm.startPrank(agentOwner);
        token.approve(address(registry), 1000 ether);
        bytes32 agentId = registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0));
        vm.stopPrank();

        vm.warp(block.timestamp + timePassed);

        if (timePassed >= 7 days) {
            assertTrue(registry.isChallengeWindowExpired(agentId));
        } else {
            assertFalse(registry.isChallengeWindowExpired(agentId));
        }
    }
}
