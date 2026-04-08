// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../src/da/PerformanceAnchor.sol";
import "../../src/interfaces/IPerformanceAnchor.sol";

/**
 * @title MockSLAEnforcerForAnchor
 * @dev Minimal mock exposing `isSentinel(address)` for ACL checks.
 */
contract MockSLAEnforcerForAnchor {
    mapping(address => bool) public isSentinel;

    function setSentinel(address sentinel, bool status) external {
        isSentinel[sentinel] = status;
    }
}

contract PerformanceAnchorTest is Test {

    PerformanceAnchor public anchor;
    MockSLAEnforcerForAnchor public mockEnforcer;

    address admin = address(1);
    address sentinel = address(2);
    address provider = address(3);
    address stranger = address(4);

    bytes32 blobId1 = keccak256("celestia:1001:abc123");
    bytes32 blobId2 = keccak256("near:5001:def456");
    bytes32 reportHash1 = keccak256("report_data_1");
    bytes32 reportHash2 = keccak256("report_data_2");

    function setUp() public {
        // Deploy mock SLAEnforcer
        mockEnforcer = new MockSLAEnforcerForAnchor();
        mockEnforcer.setSentinel(sentinel, true);

        // Deploy PerformanceAnchor
        anchor = new PerformanceAnchor();
        anchor.initialize(admin, address(mockEnforcer));
    }

    // ============================================================
    //                   HAPPY PATH TESTS
    // ============================================================

    function test_commit_by_sentinel() public {
        vm.prank(sentinel);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );

        // Verify the anchor was stored
        IPerformanceAnchor.AnchorRecord memory record = anchor.getAnchor(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1
        );

        assertEq(record.reportHash, reportHash1);
        assertEq(record.provider, provider);
        assertEq(record.sentinel, sentinel);
        assertEq(uint8(record.protocol), uint8(IPerformanceAnchor.DAProtocol.CELESTIA));
        assertTrue(record.timestamp > 0);
    }

    function test_verify_anchor_matches() public {
        vm.prank(sentinel);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );

        bool matches = anchor.verifyAnchor(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1
        );
        assertTrue(matches);
    }

    function test_verify_anchor_wrong_hash() public {
        vm.prank(sentinel);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );

        bool matches = anchor.verifyAnchor(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash2  // Wrong hash
        );
        assertFalse(matches);
    }

    function test_verify_anchor_nonexistent() public view {
        bool matches = anchor.verifyAnchor(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1
        );
        assertFalse(matches);
    }

    function test_multi_protocol_anchors() public {
        vm.startPrank(sentinel);

        // Anchor on Celestia
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );

        // Anchor on Near DA
        anchor.commit(
            IPerformanceAnchor.DAProtocol.NEAR_DA,
            blobId2,
            reportHash2,
            provider
        );

        vm.stopPrank();

        // Verify both exist
        assertTrue(anchor.verifyAnchor(IPerformanceAnchor.DAProtocol.CELESTIA, blobId1, reportHash1));
        assertTrue(anchor.verifyAnchor(IPerformanceAnchor.DAProtocol.NEAR_DA, blobId2, reportHash2));

        // Statistics
        assertEq(anchor.totalAnchors(), 2);
        assertEq(anchor.anchorsPerProtocol(IPerformanceAnchor.DAProtocol.CELESTIA), 1);
        assertEq(anchor.anchorsPerProtocol(IPerformanceAnchor.DAProtocol.NEAR_DA), 1);
        assertEq(anchor.anchorsPerProvider(provider), 2);
    }

    function test_statistics_tracking() public {
        vm.prank(sentinel);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );

        assertEq(anchor.totalAnchors(), 1);
        assertEq(anchor.anchorsPerProtocol(IPerformanceAnchor.DAProtocol.CELESTIA), 1);
        assertEq(anchor.anchorsPerProtocol(IPerformanceAnchor.DAProtocol.NEAR_DA), 0);
        assertEq(anchor.anchorsPerProvider(provider), 1);
    }

    // ============================================================
    //                   ACCESS CONTROL TESTS
    // ============================================================

    function test_commit_unauthorized_reverts() public {
        vm.prank(stranger);
        vm.expectRevert(IPerformanceAnchor.UnauthorizedSentinel.selector);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );
    }

    function test_commit_unregistered_sentinel_reverts() public {
        address fakeSentinel = address(99);
        vm.prank(fakeSentinel);
        vm.expectRevert(IPerformanceAnchor.UnauthorizedSentinel.selector);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );
    }

    // ============================================================
    //                   VALIDATION TESTS
    // ============================================================

    function test_duplicate_commit_reverts() public {
        vm.startPrank(sentinel);

        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );

        // Same (protocol, blobId) should revert
        vm.expectRevert(IPerformanceAnchor.AnchorAlreadyExists.selector);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash2,  // Different hash, same key
            provider
        );

        vm.stopPrank();
    }

    function test_commit_zero_blobId_reverts() public {
        vm.prank(sentinel);
        vm.expectRevert(IPerformanceAnchor.InvalidParameters.selector);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            bytes32(0),
            reportHash1,
            provider
        );
    }

    function test_commit_zero_reportHash_reverts() public {
        vm.prank(sentinel);
        vm.expectRevert(IPerformanceAnchor.InvalidParameters.selector);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            bytes32(0),
            provider
        );
    }

    function test_commit_zero_provider_reverts() public {
        vm.prank(sentinel);
        vm.expectRevert(IPerformanceAnchor.InvalidParameters.selector);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            address(0)
        );
    }

    // ============================================================
    //                   ADMIN TESTS
    // ============================================================

    function test_setSLAEnforcer() public {
        address newEnforcer = address(100);
        vm.prank(admin);
        anchor.setSLAEnforcer(newEnforcer);
    }

    function test_setSLAEnforcer_unauthorized_reverts() public {
        bytes32 adminRole = anchor.ADMIN_ROLE();
        vm.expectRevert(
            abi.encodeWithSignature("AccessControlUnauthorizedAccount(address,bytes32)", stranger, adminRole)
        );
        vm.prank(stranger);
        anchor.setSLAEnforcer(address(100));
    }

    // ============================================================
    //                   EVENT TESTS
    // ============================================================

    function test_emit_PerformanceReportAnchored() public {
        vm.expectEmit(true, true, true, true);
        emit IPerformanceAnchor.PerformanceReportAnchored(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider,
            sentinel
        );

        vm.prank(sentinel);
        anchor.commit(
            IPerformanceAnchor.DAProtocol.CELESTIA,
            blobId1,
            reportHash1,
            provider
        );
    }
}
