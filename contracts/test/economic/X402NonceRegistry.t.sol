// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/economic/X402NonceRegistry.sol";

/**
 * @title X402NonceRegistryTest
 * @notice Comprehensive tests for X402NonceRegistry contract
 */
contract X402NonceRegistryTest is BaseTest {
    X402NonceRegistry public registry;

    function setUp() public override {
        super.setUp();

        // Deploy registry
        registry = new X402NonceRegistry();
        registry.initialize(admin, address(0)); // No escrow manager for basic tests
        vm.label(address(registry), "X402NonceRegistry");

        // Grant settler role to provider1 using admin
        vm.startPrank(admin);
        registry.grantRole(registry.SETTLER_ROLE(), provider1);
        vm.stopPrank();
    }

    // ============ Initialization Tests ============

    function test_Initialize_SetsAdmin() public view {
        assertTrue(registry.hasRole(registry.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(registry.hasRole(registry.ADMIN_ROLE(), admin));
    }

    function test_Initialize_RevertsOnDoubleInit() public {
        vm.expectRevert();
        registry.initialize(admin, address(0));
    }

    function test_Initialize_RevertsOnZeroAdmin() public {
        X402NonceRegistry newRegistry = new X402NonceRegistry();
        vm.expectRevert(IX402NonceRegistry.ZeroAddress.selector);
        newRegistry.initialize(address(0), address(0));
    }

    // ============ Nonce Validity Tests ============

    function test_IsNonceValid_ReturnsTrueForUnused() public view {
        assertTrue(registry.isNonceValid(agent1, 1));
        assertTrue(registry.isNonceValid(agent1, 100));
        assertTrue(registry.isNonceValid(agent1, type(uint256).max));
    }

    function test_IsNonceValid_ReturnsFalseForUsed() public {
        bytes32 receiptHash = keccak256("receipt1");
        bytes32 escrowId = keccak256("escrow1");

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);

        assertFalse(registry.isNonceValid(agent1, 1));
    }

    function test_GetNonceInfo_ReturnsCorrectInfo() public {
        bytes32 receiptHash = keccak256("receipt1");
        bytes32 escrowId = keccak256("escrow1");

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);

        IX402NonceRegistry.NonceInfo memory info = registry.getNonceInfo(agent1, 1);

        assertTrue(info.used);
        assertEq(info.receiptHash, receiptHash);
        assertEq(info.escrowId, escrowId);
        assertEq(info.consumedAt, block.timestamp);
    }

    // ============ Nonce Consumption Tests ============

    function test_ConsumeNonce_MarksAsUsed() public {
        bytes32 receiptHash = keccak256("receipt1");
        bytes32 escrowId = keccak256("escrow1");

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);

        assertFalse(registry.isNonceValid(agent1, 1));
    }

    function test_ConsumeNonce_EmitsEvent() public {
        bytes32 receiptHash = keccak256("receipt1");
        bytes32 escrowId = keccak256("escrow1");

        vm.expectEmit(true, true, true, true);
        emit IX402NonceRegistry.NonceConsumed(agent1, 1, receiptHash, escrowId);

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);
    }

    function test_ConsumeNonce_RevertsOnReplay() public {
        bytes32 receiptHash = keccak256("receipt1");
        bytes32 escrowId = keccak256("escrow1");

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);

        vm.prank(provider1);
        vm.expectRevert(abi.encodeWithSelector(IX402NonceRegistry.NonceAlreadyUsed.selector, agent1, 1));
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);
    }

    function test_ConsumeNonce_RevertsIfNotSettler() public {
        bytes32 receiptHash = keccak256("receipt1");
        bytes32 escrowId = keccak256("escrow1");

        vm.prank(user1);
        vm.expectRevert();
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);
    }

    function test_ConsumeNonce_DifferentAgentsSameNonce() public {
        bytes32 receiptHash1 = keccak256("receipt1");
        bytes32 receiptHash2 = keccak256("receipt2");
        bytes32 escrowId = keccak256("escrow1");

        vm.startPrank(provider1);

        // Same nonce for different agents should work
        registry.consumeNonce(agent1, 1, receiptHash1, escrowId);
        registry.consumeNonce(agent2, 1, receiptHash2, escrowId);

        vm.stopPrank();

        assertFalse(registry.isNonceValid(agent1, 1));
        assertFalse(registry.isNonceValid(agent2, 1));
    }

    function test_ConsumeNonce_UpdatesTotalConsumed() public {
        bytes32 receiptHash = keccak256("receipt1");
        bytes32 escrowId = keccak256("escrow1");

        uint256 before = registry.totalNoncesConsumed();

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);

        assertEq(registry.totalNoncesConsumed(), before + 1);
    }

    // ============ Receipt Tracking Tests ============

    function test_IsReceiptClaimed_TracksByHash() public {
        bytes32 receiptHash = keccak256("unique-receipt");
        bytes32 escrowId = keccak256("escrow1");

        assertFalse(registry.isReceiptClaimed(receiptHash));

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);

        assertTrue(registry.isReceiptClaimed(receiptHash));
    }

    function test_ConsumeNonce_RevertsOnDuplicateReceipt() public {
        bytes32 receiptHash = keccak256("duplicate-receipt");
        bytes32 escrowId = keccak256("escrow1");

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, receiptHash, escrowId);

        // Try with different nonce but same receipt
        vm.prank(provider1);
        vm.expectRevert(abi.encodeWithSelector(IX402NonceRegistry.ReceiptAlreadyClaimed.selector, receiptHash));
        registry.consumeNonce(agent1, 2, receiptHash, escrowId);
    }

    // ============ Batch Operations Tests ============

    function test_BatchConsumeNonces_ProcessesAll() public {
        address[] memory agents = new address[](3);
        agents[0] = agent1;
        agents[1] = agent1;
        agents[2] = agent2;

        uint256[] memory nonces = new uint256[](3);
        nonces[0] = 1;
        nonces[1] = 2;
        nonces[2] = 1;

        bytes32[] memory receiptHashes = new bytes32[](3);
        receiptHashes[0] = keccak256("r1");
        receiptHashes[1] = keccak256("r2");
        receiptHashes[2] = keccak256("r3");

        bytes32[] memory escrowIds = new bytes32[](3);
        escrowIds[0] = keccak256("e1");
        escrowIds[1] = keccak256("e2");
        escrowIds[2] = keccak256("e3");

        vm.prank(provider1);
        registry.batchConsumeNonces(agents, nonces, receiptHashes, escrowIds);

        assertFalse(registry.isNonceValid(agent1, 1));
        assertFalse(registry.isNonceValid(agent1, 2));
        assertFalse(registry.isNonceValid(agent2, 1));
    }

    function test_BatchConsumeNonces_RevertsOnArrayMismatch() public {
        address[] memory agents = new address[](2);
        uint256[] memory nonces = new uint256[](3);
        bytes32[] memory receiptHashes = new bytes32[](2);
        bytes32[] memory escrowIds = new bytes32[](2);

        vm.prank(provider1);
        vm.expectRevert("Array length mismatch");
        registry.batchConsumeNonces(agents, nonces, receiptHashes, escrowIds);
    }

    function test_BatchConsumeNonces_EmitsMultipleEvents() public {
        address[] memory agents = new address[](2);
        agents[0] = agent1;
        agents[1] = agent2;

        uint256[] memory nonces = new uint256[](2);
        nonces[0] = 1;
        nonces[1] = 2;

        bytes32[] memory receiptHashes = new bytes32[](2);
        receiptHashes[0] = keccak256("r1");
        receiptHashes[1] = keccak256("r2");

        bytes32[] memory escrowIds = new bytes32[](2);
        escrowIds[0] = keccak256("e1");
        escrowIds[1] = keccak256("e2");

        vm.expectEmit(true, true, true, true);
        emit IX402NonceRegistry.NonceConsumed(agent1, 1, receiptHashes[0], escrowIds[0]);

        vm.expectEmit(true, true, true, true);
        emit IX402NonceRegistry.NonceConsumed(agent2, 2, receiptHashes[1], escrowIds[1]);

        vm.prank(provider1);
        registry.batchConsumeNonces(agents, nonces, receiptHashes, escrowIds);
    }

    // ============ Authorization Tests ============

    function test_AuthorizeSettler_Works() public {
        assertFalse(registry.hasRole(registry.SETTLER_ROLE(), user1));

        vm.prank(admin);
        registry.authorizeSettler(user1);

        assertTrue(registry.hasRole(registry.SETTLER_ROLE(), user1));
    }

    function test_DeauthorizeSettler_Works() public {
        vm.prank(admin);
        registry.authorizeSettler(user1);

        assertTrue(registry.hasRole(registry.SETTLER_ROLE(), user1));

        vm.prank(admin);
        registry.deauthorizeSettler(user1);

        assertFalse(registry.hasRole(registry.SETTLER_ROLE(), user1));
    }

    function test_AuthorizedSettler_CanConsume() public {
        vm.prank(admin);
        registry.authorizeSettler(user1);

        vm.prank(user1);
        registry.consumeNonce(agent1, 1, keccak256("r"), keccak256("e"));

        assertFalse(registry.isNonceValid(agent1, 1));
    }

    function test_IsAuthorizedSettler_ReturnsCorrect() public {
        assertFalse(registry.isAuthorizedSettler(user1));

        vm.prank(admin);
        registry.authorizeSettler(user1);

        assertTrue(registry.isAuthorizedSettler(user1));
    }

    // ============ Highest Nonce Tracking Tests ============

    function test_GetHighestUsedNonce_TracksCorrectly() public {
        bytes32 escrowId = keccak256("e");

        vm.startPrank(provider1);

        registry.consumeNonce(agent1, 5, keccak256("r1"), escrowId);
        assertEq(registry.getHighestUsedNonce(agent1), 5);

        registry.consumeNonce(agent1, 10, keccak256("r2"), escrowId);
        assertEq(registry.getHighestUsedNonce(agent1), 10);

        // Lower nonce shouldn't change highest
        registry.consumeNonce(agent1, 3, keccak256("r3"), escrowId);
        assertEq(registry.getHighestUsedNonce(agent1), 10);

        vm.stopPrank();
    }

    function test_GetNextNonce_FindsUnused() public {
        bytes32 escrowId = keccak256("e");

        // Initially, next nonce should be 0
        assertEq(registry.getNextNonce(agent1), 0);

        vm.startPrank(provider1);

        // Consume nonce 0
        registry.consumeNonce(agent1, 0, keccak256("r0"), escrowId);

        // Next should be 1
        assertEq(registry.getNextNonce(agent1), 1);

        vm.stopPrank();
    }

    // ============ Pause Tests ============

    function test_Pause_BlocksConsumption() public {
        vm.prank(admin);
        registry.pause();

        vm.prank(provider1);
        vm.expectRevert();
        registry.consumeNonce(agent1, 1, keccak256("r"), keccak256("e"));
    }

    function test_Unpause_EnablesConsumption() public {
        vm.prank(admin);
        registry.pause();

        vm.prank(admin);
        registry.unpause();

        vm.prank(provider1);
        registry.consumeNonce(agent1, 1, keccak256("r"), keccak256("e"));

        assertFalse(registry.isNonceValid(agent1, 1));
    }

    // ============ Fuzz Tests ============

    function testFuzz_ConsumeNonce(address agent, uint256 nonce, bytes32 receipt) public {
        vm.assume(agent != address(0));
        vm.assume(receipt != bytes32(0));

        bytes32 escrowId = keccak256(abi.encodePacked(agent, nonce));

        assertTrue(registry.isNonceValid(agent, nonce));

        vm.prank(provider1);
        registry.consumeNonce(agent, nonce, receipt, escrowId);

        assertFalse(registry.isNonceValid(agent, nonce));
        assertTrue(registry.isReceiptClaimed(receipt));
    }

    function testFuzz_DifferentAgentsSameNonce(uint256 nonce) public {
        bytes32 receipt1 = keccak256(abi.encodePacked("r1", nonce));
        bytes32 receipt2 = keccak256(abi.encodePacked("r2", nonce));
        bytes32 escrowId = keccak256("e");

        vm.startPrank(provider1);

        registry.consumeNonce(agent1, nonce, receipt1, escrowId);
        registry.consumeNonce(agent2, nonce, receipt2, escrowId);

        vm.stopPrank();

        assertFalse(registry.isNonceValid(agent1, nonce));
        assertFalse(registry.isNonceValid(agent2, nonce));
    }

    function testFuzz_HighestNonceTracking(uint256 nonce1, uint256 nonce2) public {
        nonce1 = bound(nonce1, 0, 1000);
        nonce2 = bound(nonce2, 0, 1000);
        vm.assume(nonce1 != nonce2);

        bytes32 escrowId = keccak256("e");

        vm.startPrank(provider1);

        registry.consumeNonce(agent1, nonce1, keccak256(abi.encode(nonce1)), escrowId);
        uint256 expected1 = nonce1;
        assertEq(registry.getHighestUsedNonce(agent1), expected1);

        registry.consumeNonce(agent1, nonce2, keccak256(abi.encode(nonce2)), escrowId);
        uint256 expected2 = nonce1 > nonce2 ? nonce1 : nonce2;
        assertEq(registry.getHighestUsedNonce(agent1), expected2);

        vm.stopPrank();
    }
}
