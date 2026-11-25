// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {DeliveryDisputeFixture} from "./DeliveryDisputeFixture.sol";
import {DeliveryDisputeV1} from "../../src/economic/DeliveryDisputeV1.sol";

/// Resolver availability through the real governance path (F13 review follow-up).
/// The dispute resolver is the VAMSTimelockController itself, as in
/// DeployRestrictedTestnet: a proposer schedules `disputes.resolve`, the 48-hour delay
/// elapses, and any address executes. The proposer stands in for the governance Safe;
/// the Safe's signature threshold is NOT modelled here (custody is UNKNOWN until Phase 3).
/// The unit suite in DeliveryDisputeV1.t.sol uses a plain resolver address and does not
/// establish this path.
contract DeliveryDisputeGovernancePathTest is DeliveryDisputeFixture {
    address internal safeProposer;
    uint256 internal opSalt;

    function _proposers() internal override returns (address[] memory members) {
        safeProposer = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-SAFE-PROPOSER")));
        members = new address[](2);
        members[0] = address(this); // keeps the fixture's policy governance helper working
        members[1] = safeProposer;
    }

    /// Open executor, as in the deployed timelock (EXECUTOR_ROLE granted to address(0)).
    function _executors() internal pure override returns (address[] memory members) {
        members = new address[](1);
        members[0] = address(0);
    }

    function _resolverAddress() internal view override returns (address) {
        return address(timelock);
    }

    function _resolveCall(bytes32 id, uint256 index, bool uphold) internal pure returns (bytes memory) {
        return abi.encodeCall(DeliveryDisputeV1.resolve, (id, index, uphold));
    }

    function _schedule(bytes memory data) internal returns (bytes32 salt, bytes32 opId) {
        salt = bytes32(++opSalt);
        vm.prank(safeProposer);
        timelock.schedule(address(disputes), 0, data, bytes32(0), salt, 48 hours);
        opId = timelock.hashOperation(address(disputes), 0, data, bytes32(0), salt);
    }

    function _execute(bytes memory data, bytes32 salt) internal {
        vm.prank(stranger); // any address may execute a ready operation
        timelock.execute(address(disputes), 0, data, bytes32(0), salt);
    }

    function test_resolverIsTheTimelockAndSafeCannotBypassTheDelay() public {
        assertEq(disputes.resolver(), address(timelock));
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        vm.prank(safeProposer);
        vm.expectRevert(DeliveryDisputeV1.NotResolver.selector);
        disputes.resolve(id, 0, true);
        // Unscheduled and unready operations cannot execute.
        bytes memory data = _resolveCall(id, 0, true);
        vm.prank(stranger);
        vm.expectRevert();
        timelock.execute(address(disputes), 0, data, bytes32(0), bytes32(uint256(99)));
        (bytes32 salt,) = _schedule(data);
        vm.warp(block.timestamp + 48 hours - 1);
        vm.prank(stranger);
        vm.expectRevert();
        timelock.execute(address(disputes), 0, data, bytes32(0), salt);
        // A non-proposer cannot schedule at all.
        vm.prank(stranger);
        vm.expectRevert();
        timelock.schedule(address(disputes), 0, data, bytes32(0), bytes32(uint256(7)), 48 hours);
    }

    function test_upholdThroughScheduledOperationRefundsAgentAndBond() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        bytes memory data = _resolveCall(id, 0, true);
        (bytes32 salt,) = _schedule(data);
        vm.warp(block.timestamp + 48 hours);
        uint256 before = token.balanceOf(address(this));
        assertEq(disputes.openDisputeCount(address(this)), 1);
        _execute(data, salt);
        assertEq(token.balanceOf(address(this)) - before, ROW + BOND);
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.UPHELD));
        assertEq(disputes.totalBondsHeld(), 0);
        assertEq(disputes.openDisputeCount(address(this)), 0); // decision 10b: slot released
        assertBacking();
    }

    function test_rejectThroughScheduledOperationPaysProviderAndBond() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        bytes memory data = _resolveCall(id, 0, false);
        (bytes32 salt,) = _schedule(data);
        vm.warp(block.timestamp + 48 hours);
        uint256 providerBefore = token.balanceOf(provider);
        _execute(data, salt);
        assertEq(token.balanceOf(provider) - providerBefore, BOND);
        claim(id, 0);
        assertEq(token.balanceOf(provider) - providerBefore, BOND + PAYOUT);
        assertBacking();
    }

    /// Exact 14-day boundary. `resolve` needs block.timestamp < openedAt + 14 days.
    function test_latestExecutionOneSecondBeforeTheDeadlineStillResolves() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        uint256 opened = disputes.getDispute(id, 0).openedAt;
        vm.warp(opened + 14 days - 1 - 48 hours);
        bytes memory data = _resolveCall(id, 0, true);
        (bytes32 salt,) = _schedule(data);
        vm.warp(opened + 14 days - 1);
        _execute(data, salt);
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.UPHELD));
    }

    function test_operationReadyExactlyAtTheDeadlineFailsAndTimeoutForfeitsToProvider() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        uint256 opened = disputes.getDispute(id, 0).openedAt;
        vm.warp(opened + 14 days - 48 hours);
        bytes memory data = _resolveCall(id, 0, true);
        (bytes32 salt,) = _schedule(data);
        vm.warp(opened + 14 days);
        vm.prank(stranger);
        vm.expectRevert(); // underlying resolve reverts with ResolutionPeriodEnded
        timelock.execute(address(disputes), 0, data, bytes32(0), salt);
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.OPEN));
        // Late scheduling is the resolver's failure; the agreed consequence is decision 10a.
        uint256 agentBefore = token.balanceOf(address(this));
        uint256 providerBefore = token.balanceOf(provider);
        vm.prank(stranger); disputes.finalizeTimeout(id, 0);
        assertEq(token.balanceOf(address(this)), agentBefore);
        assertEq(token.balanceOf(provider) - providerBefore, BOND);
        assertBacking();
    }

    function test_cancelledOperationCannotResolve() public {
        bytes32 id = create(1); earn(id, 0); dispute(id, 0);
        bytes memory data = _resolveCall(id, 0, true);
        (bytes32 salt, bytes32 opId) = _schedule(data);
        vm.prank(safeProposer);
        timelock.cancel(opId);
        vm.warp(block.timestamp + 48 hours);
        vm.prank(stranger);
        vm.expectRevert();
        timelock.execute(address(disputes), 0, data, bytes32(0), salt);
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.OPEN));
        // The same operation can be scheduled again with a new salt while time remains.
        (bytes32 salt2,) = _schedule(data);
        vm.warp(block.timestamp + 48 hours);
        _execute(data, salt2);
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.UPHELD));
    }

    function test_failedExecutionLeavesDisputeAndDeadlineIntact() public {
        bytes32 id = create(2); earn(id, 0); earn(id, 1); dispute(id, 0);
        // Operation targets row 1, which has no open dispute: execution fails atomically.
        bytes memory wrong = _resolveCall(id, 1, true);
        (bytes32 salt,) = _schedule(wrong);
        vm.warp(block.timestamp + 48 hours);
        vm.prank(stranger);
        vm.expectRevert();
        timelock.execute(address(disputes), 0, wrong, bytes32(0), salt);
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.OPEN));
        assertEq(uint256(disputes.getDispute(id, 1).state), uint256(DeliveryDisputeV1.State.NONE));
        // The correct decision still resolves inside the original deadline.
        bytes memory right = _resolveCall(id, 0, true);
        (bytes32 salt2,) = _schedule(right);
        vm.warp(block.timestamp + 48 hours);
        _execute(right, salt2);
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.UPHELD));
        assertBacking();
    }
}
