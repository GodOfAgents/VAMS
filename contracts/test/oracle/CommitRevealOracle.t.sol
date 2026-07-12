// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {CommitRevealOracle} from "../../src/oracle/CommitRevealOracle.sol";
import {OracleRegistry, IOracleRegistry} from "../../src/oracle/OracleRegistry.sol";

contract CommitRevealOracleTest is Test {
    OracleRegistry internal registry;
    CommitRevealOracle internal oracle;
    bytes32 internal constant FALLBACK = keccak256("VAMS_ORACLE_STALE");

    function setUp() public {
        registry = new OracleRegistry(address(this));
        oracle = new CommitRevealOracle(
            address(this),
            address(registry),
            IOracleRegistry.Category.PRICE,
            FALLBACK
        );
    }

    function test_staleRequestResolvesToFixedFallback() public {
        uint256 requestId = oracle.createRequest();
        (, uint256 deadline,,) = oracle.requests(requestId);
        vm.warp(deadline + 1);

        oracle.resolveStaleRequest(requestId);

        (bool resolved, bytes32 value) = oracle.getResult(requestId);
        assertTrue(resolved);
        assertEq(value, FALLBACK);
    }

    function test_staleFallbackCannotBeTriggeredBeforeDeadline() public {
        uint256 requestId = oracle.createRequest();
        vm.expectRevert(CommitRevealOracle.RequestNotStale.selector);
        oracle.resolveStaleRequest(requestId);
    }

    function test_staleFallbackCannotBeReplayed() public {
        uint256 requestId = oracle.createRequest();
        (, uint256 deadline,,) = oracle.requests(requestId);
        vm.warp(deadline + 1);
        oracle.resolveStaleRequest(requestId);

        vm.expectRevert(CommitRevealOracle.RequestAlreadyResolved.selector);
        oracle.resolveStaleRequest(requestId);
    }
}
