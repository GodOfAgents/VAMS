// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {DeliveryDisputeFixture} from "./DeliveryDisputeFixture.sol";
import {DeliveryDisputeV1} from "../../src/economic/DeliveryDisputeV1.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {IComposedDeliveryVerifier} from "../../src/economic/IComposedDeliveryVerifier.sol";
import {ActionContextV1} from "../../src/trust/ActionContextV1.sol";

/// Owner decision 10b acceptance: bond floor (MIN_BOND) and per-agent open-dispute cap.
/// Design: docs/remediation/repair_20261125/F13-BOND-FLOOR-DISPUTE-CAP-DESIGN.md, section 6.
contract DeliveryDisputeFloorCapTest is DeliveryDisputeFixture {
    uint256 internal constant SMALL = 5 ether; // 5% = 0.25 VAMS, below the 1 VAMS floor
    address internal agent2;

    function setUp() public override {
        super.setUp();
        agent2 = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-AGENT-2")));
        govern(abi.encodeCall(policy.setInitiator, (agent2, true)));
        token.transfer(agent2, 1_000 ether);
        vm.startPrank(agent2);
        token.approve(address(settlement), type(uint256).max);
        token.approve(address(disputes), type(uint256).max);
        vm.stopPrank();
    }

    /// Escrow of `rows` rows of `amount`, alternating the two admitted providers, created by `agent`.
    function _escrow(address agent, uint256 rows, uint256 amount) internal returns (bytes32 id) {
        address[] memory providers = new address[](rows);
        uint256[] memory amounts = new uint256[](rows);
        bytes32[] memory workloads = new bytes32[](rows);
        for (uint256 i; i < rows; ++i) {
            providers[i] = i % 2 == 0 ? provider : provider2; amounts[i] = amount; workloads[i] = workload;
        }
        vm.prank(agent);
        id = settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("blueprint"), bytes32(0), bytes32(0), workloads));
    }

    function _earnRow(bytes32 id, uint256 index) internal {
        IComposedSettlement.ProviderAlloc memory row = settlement.getProviderAlloc(id, index);
        vm.prank(row.provider); settlement.issueDeliveryChallenge(id, index);
        IComposedDeliveryVerifier.ExpectedDelivery memory e = settlement.getExpectedDelivery(id, index);
        ActionContextV1.Context memory c = template;
        c.budget = row.amount;
        c.actorRoot = bytes32(uint256(uint160(row.provider))); c.providerId = c.actorRoot;
        c.actionHash = e.context; c.intentId = id; c.nonce = e.nonce; c.issuedAt = e.issuedAt;
        c.expiresAt = e.expiresAt; c.policyRoot = e.policyRoot; c.policyVersion = e.policyVersion;
        c.authorityEpoch = e.authorityEpoch;
        vm.prank(row.provider);
        settlement.recordEarnedDeliveryV3(id, index, keccak256("output"), abi.encode(c, uint8(1), hex"01"));
    }

    function _earnedEscrow(address agent, uint256 rows, uint256 amount) internal returns (bytes32 id) {
        id = _escrow(agent, rows, amount);
        for (uint256 i; i < rows; ++i) _earnRow(id, i);
    }

    function _open(address agent, bytes32 id, uint256 index) internal {
        vm.prank(agent); disputes.openDispute(id, index, keccak256("reason"));
    }

    // ---- 1. parameters -----------------------------------------------------------------

    function test_parametersMatchOwnerDecision10b() public view {
        assertEq(disputes.MIN_BOND(), 1e18);
        assertEq(disputes.MAX_OPEN_DISPUTES_PER_AGENT(), 20);
        assertEq(disputes.MAX_OPEN_DISPUTES_PER_AGENT(), settlement.MAX_PROVIDERS());
    }

    // ---- 2. floor ------------------------------------------------------------------------

    function test_bondFloorCrossoverIsExact() public view {
        assertEq(disputes.bondFor(1), 1e18);
        assertEq(disputes.bondFor(20e18 - 1), 1e18); // ceil(5%) = 1e18 here too
        assertEq(disputes.bondFor(20e18), 1e18);      // proportional equals the floor
        assertEq(disputes.bondFor(20e18 + 1), 1e18 + 1); // proportional, rounded up, above the floor
        assertEq(disputes.bondFor(100 ether), 5 ether);
    }

    function testFuzz_bondIsFloorOrRoundedUpProportional(uint256 amount) public view {
        amount = bound(amount, 1, 1e30);
        uint256 proportional = (amount * 500 + 9_999) / 10_000;
        uint256 expected = proportional > 1e18 ? proportional : 1e18;
        assertEq(disputes.bondFor(amount), expected);
        assertGe(disputes.bondFor(amount), 1e18);
        assertGe(disputes.bondFor(amount) * 10_000, amount * 500);
    }

    function test_smallRowPostsTheFloorAndShortAllowanceReverts() public {
        bytes32 id = _earnedEscrow(address(this), 1, SMALL);
        token.approve(address(disputes), 1e18 - 1);
        vm.expectRevert();
        disputes.openDispute(id, 0, keccak256("reason"));
        assertEq(disputes.openDisputeCount(address(this)), 0);
        token.approve(address(disputes), type(uint256).max);
        uint256 before = token.balanceOf(address(this));
        disputes.openDispute(id, 0, keccak256("reason"));
        assertEq(before - token.balanceOf(address(this)), 1e18);
        assertEq(disputes.getDispute(id, 0).bond, 1e18);
        assertBacking();
    }

    // ---- 3. cap ----------------------------------------------------------------------------

    function test_twentyFirstOpenDisputeRevertsUntilAnOutcomeReleasesASlot() public {
        bytes32 full = _earnedEscrow(address(this), 20, SMALL);
        bytes32 extra = _earnedEscrow(address(this), 1, SMALL);
        for (uint256 i; i < 20; ++i) _open(address(this), full, i);
        assertEq(disputes.openDisputeCount(address(this)), 20);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.TooManyOpenDisputes.selector, address(this), 20));
        disputes.openDispute(extra, 0, keccak256("reason"));
        vm.prank(resolver); disputes.resolve(full, 0, true);
        assertEq(disputes.openDisputeCount(address(this)), 19);
        _open(address(this), extra, 0);
        assertEq(disputes.openDisputeCount(address(this)), 20);
        assertBacking();
    }

    function test_upholdRejectAndTimeoutEachReleaseOneSlot() public {
        bytes32 id = _earnedEscrow(address(this), 3, SMALL);
        for (uint256 i; i < 3; ++i) _open(address(this), id, i);
        assertEq(disputes.openDisputeCount(address(this)), 3);
        vm.prank(resolver); disputes.resolve(id, 0, true);
        assertEq(disputes.openDisputeCount(address(this)), 2);
        vm.prank(resolver); disputes.resolve(id, 1, false);
        assertEq(disputes.openDisputeCount(address(this)), 1);
        vm.warp(block.timestamp + 14 days);
        disputes.finalizeTimeout(id, 2);
        assertEq(disputes.openDisputeCount(address(this)), 0);
        assertBacking();
    }

    // ---- 5. independence ----------------------------------------------------------------------

    function test_oneAgentAtTheCapDoesNotBlockAnother() public {
        bytes32 full = _earnedEscrow(address(this), 20, SMALL);
        for (uint256 i; i < 20; ++i) _open(address(this), full, i);
        bytes32 other = _earnedEscrow(agent2, 1, SMALL);
        _open(agent2, other, 0);
        assertEq(disputes.openDisputeCount(agent2), 1);
        assertEq(disputes.openDisputeCount(address(this)), 20);
    }

    // ---- 4. counter invariant ------------------------------------------------------------------

    /// Random opens and outcomes over two agents: after every step each agent's counter equals
    /// its number of OPEN disputes, and balances equal recorded liabilities.
    function testFuzz_openCountEqualsOpenDisputesPerAgent(uint8 rowsA, uint8 rowsB, uint256 seed) public {
        uint256 na = bound(rowsA, 1, 6);
        uint256 nb = bound(rowsB, 1, 6);
        bytes32 idA = _earnedEscrow(address(this), na, SMALL);
        bytes32 idB = _earnedEscrow(agent2, nb, SMALL);
        for (uint256 i; i < na; ++i) _open(address(this), idA, i);
        for (uint256 i; i < nb; ++i) _open(agent2, idB, i);
        uint256 openA = na;
        uint256 openB = nb;
        bool timedWarp;
        for (uint256 step; step < na + nb; ++step) {
            bool pickA = step < na;
            uint256 index = pickA ? step : step - na;
            bytes32 id = pickA ? idA : idB;
            uint256 outcome = uint256(keccak256(abi.encode(seed, step))) % 3;
            if (outcome == 2) {
                if (!timedWarp) { vm.warp(block.timestamp + 14 days); timedWarp = true; }
                disputes.finalizeTimeout(id, index);
            } else {
                if (timedWarp) { // the resolver's deadline has passed for every dispute
                    disputes.finalizeTimeout(id, index);
                } else {
                    vm.prank(resolver); disputes.resolve(id, index, outcome == 0);
                }
            }
            if (pickA) --openA; else --openB;
            assertEq(disputes.openDisputeCount(address(this)), openA);
            assertEq(disputes.openDisputeCount(agent2), openB);
            assertBacking();
        }
        assertEq(disputes.totalBondsHeld(), 0);
    }
}
