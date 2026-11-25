// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {DeliveryDisputeFixture} from "./DeliveryDisputeFixture.sol";
import {DeliveryDisputeV1} from "../../src/economic/DeliveryDisputeV1.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {IComposedDeliveryVerifier} from "../../src/economic/IComposedDeliveryVerifier.sol";
import {ActionContextV1} from "../../src/trust/ActionContextV1.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/// Owner decision 10b acceptance: bond floor (MIN_BOND) and per-agent open-dispute cap.
/// Design: docs/remediation/repair_20261125/F13-BOND-FLOOR-DISPUTE-CAP-DESIGN.md, section 6.
contract DeliveryDisputeFloorCapTest is DeliveryDisputeFixture {
    error InjectedTokenFailure();
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

    function test_twentyFirstOpenDisputeRevertsUntilEachOutcomeReleasesASlot() public {
        for (uint8 outcome; outcome < 3; ++outcome) _capReuseAfterOutcome(outcome);
    }

    function _capReuseAfterOutcome(uint8 outcome) internal {
        bytes32 full = _earnedEscrow(address(this), 20, SMALL);
        bytes32 extra = _earnedEscrow(address(this), 1, SMALL);
        for (uint256 i; i < 20; ++i) _open(address(this), full, i);
        assertEq(disputes.openDisputeCount(address(this)), 20);
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.TooManyOpenDisputes.selector, address(this), 20));
        disputes.openDispute(extra, 0, keccak256("reason"));
        _closeRow(full, outcome);
        assertEq(disputes.openDisputeCount(address(this)), 19);
        // A timeout also expires the old extra row's dispute window. Use newly
        // earned work to test the released slot without bypassing that window.
        if (outcome == 2) extra = _earnedEscrow(address(this), 1, SMALL);
        _open(address(this), extra, 0);
        assertEq(disputes.openDisputeCount(address(this)), 20);
        for (uint256 i = 1; i < 20; ++i) {
            if (block.timestamp >= disputes.getDispute(full, i).openedAt + 14 days) {
                disputes.finalizeTimeout(full, i);
            } else {
                vm.prank(resolver); disputes.resolve(full, i, false);
            }
        }
        _closeRow(extra, 1);
        assertEq(disputes.openDisputeCount(address(this)), 0);
        assertBacking();
    }

    /// Local token fault injection exercises received-amount validation rather
    /// than an allowance failure. It does not qualify a live fee-on-transfer token.
    function test_shortReceivedBondRollsBackDisputeAndCount() public {
        bytes32 id = _earnedEscrow(address(this), 1, SMALL);
        uint256 before = token.balanceOf(address(this));
        vm.mockCall(address(token),
            abi.encodeCall(IERC20.transferFrom, (address(this), address(disputes), uint256(1e18))),
            abi.encode(true)); // token reports success but transfers nothing
        vm.expectRevert(abi.encodeWithSelector(DeliveryDisputeV1.BondTransferMismatch.selector, 1e18, 0));
        disputes.openDispute(id, 0, keccak256("short-received"));
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.NONE));
        assertEq(disputes.openDisputeCount(address(this)), 0);
        assertEq(disputes.totalBondsHeld(), 0);
        assertEq(token.balanceOf(address(this)), before);
        assertBacking();
        vm.clearMockedCalls();
        _open(address(this), id, 0);
        assertEq(disputes.openDisputeCount(address(this)), 1);
        assertBacking();
    }

    function test_outgoingBondFailurePreservesStateAndSlotUntilRetry() public {
        for (uint8 outcome; outcome < 3; ++outcome) _bondExitFailure(outcome);
    }

    function _bondExitFailure(uint8 outcome) internal {
        bytes32 id = _earnedEscrow(address(this), 1, SMALL);
        _open(address(this), id, 0);
        if (outcome == 2) vm.warp(disputes.getDispute(id, 0).openedAt + 14 days);
        address recipient = outcome == 0 ? address(this) : provider;
        uint256 agentBefore = token.balanceOf(address(this));
        uint256 escrowBefore = settlement.totalEscrowed();
        vm.mockCallRevert(address(token), abi.encodeCall(IERC20.transfer, (recipient, uint256(1e18))),
            abi.encodeWithSelector(InjectedTokenFailure.selector));
        vm.expectRevert(InjectedTokenFailure.selector);
        if (outcome == 2) {
            disputes.finalizeTimeout(id, 0);
        } else {
            vm.prank(resolver); disputes.resolve(id, 0, outcome == 0);
        }
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.OPEN));
        assertEq(disputes.openDisputeCount(address(this)), 1);
        assertEq(disputes.totalBondsHeld(), 1e18);
        assertEq(token.balanceOf(address(this)), agentBefore);
        assertEq(settlement.totalEscrowed(), escrowBefore);
        assertFalse(settlement.refundedProviderShareV3(id, 0));
        assertBacking();
        vm.clearMockedCalls();
        _closeRow(id, outcome);
        assertEq(disputes.openDisputeCount(address(this)), 0);
        assertEq(disputes.totalBondsHeld(), 0);
        assertBacking();
    }

    function test_refundTransferFailureRollsBackSettlementAndDispute() public {
        bytes32 id = _earnedEscrow(address(this), 1, SMALL);
        _open(address(this), id, 0);
        uint256 escrowBefore = settlement.totalEscrowed();
        vm.mockCallRevert(address(token), abi.encodeCall(IERC20.transfer, (address(this), SMALL)),
            abi.encodeWithSelector(InjectedTokenFailure.selector));
        vm.prank(resolver);
        vm.expectRevert(InjectedTokenFailure.selector);
        disputes.resolve(id, 0, true);
        assertEq(uint256(disputes.getDispute(id, 0).state), uint256(DeliveryDisputeV1.State.OPEN));
        assertEq(disputes.openDisputeCount(address(this)), 1);
        assertEq(disputes.totalBondsHeld(), 1e18);
        assertEq(settlement.totalEscrowed(), escrowBefore);
        assertFalse(settlement.refundedProviderShareV3(id, 0));
        assertBacking();
        vm.clearMockedCalls();
        vm.prank(resolver); disputes.resolve(id, 0, true);
        assertEq(disputes.openDisputeCount(address(this)), 0);
        assertTrue(settlement.refundedProviderShareV3(id, 0));
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

    function _closeRow(bytes32 id, uint8 outcome) internal {
        uint256 deadline = disputes.getDispute(id, 0).openedAt + 14 days;
        if (outcome == 2 && block.timestamp < deadline) vm.warp(deadline);
        if (block.timestamp >= deadline) {
            disputes.finalizeTimeout(id, 0);
        } else {
            vm.prank(resolver); disputes.resolve(id, 0, outcome == 0);
        }
    }

    function _assertEnumeratedCounts(bytes32[] memory ids, address[] memory owners, uint256 used) internal view {
        uint256 countA;
        uint256 countB;
        for (uint256 i; i < used; ++i) {
            DeliveryDisputeV1.Dispute memory d = disputes.getDispute(ids[i], 0);
            assertEq(d.agent, owners[i]);
            if (d.state == DeliveryDisputeV1.State.OPEN) {
                if (owners[i] == address(this)) ++countA;
                else ++countB;
            }
        }
        assertEq(disputes.openDisputeCount(address(this)), countA);
        assertEq(disputes.openDisputeCount(agent2), countB);
        assertBacking();
    }

    /// Interleave fresh opens and outcomes across two agents, including new work
    /// after a timeout warp. Enumerate stored OPEN entries as the counter oracle.
    /// The bounded trace is not an exhaustive state-space or Sybil proof.
    function testFuzz_openCountEqualsOpenDisputesPerAgent(uint8 rowsA, uint8 rowsB, uint256 seed) public {
        uint256 steps = 2 + bound(rowsA, 1, 6) + bound(rowsB, 1, 6);
        bytes32[] memory ids = new bytes32[](steps);
        address[] memory owners = new address[](steps);
        for (uint256 step; step < steps; ++step) {
            uint256 draw = uint256(keccak256(abi.encode(seed, step)));
            address agent = step == 0 ? address(this) : step == 1 ? agent2 : draw % 2 == 0 ? address(this) : agent2;
            owners[step] = agent;
            ids[step] = _earnedEscrow(agent, 1, SMALL);
            _open(agent, ids[step], 0);
            _assertEnumeratedCounts(ids, owners, step + 1);
            uint256 selected = (draw >> 8) % (step + 1);
            if (disputes.getDispute(ids[selected], 0).state == DeliveryDisputeV1.State.OPEN) {
                _closeRow(ids[selected], uint8((draw >> 32) % 3));
            }
            _assertEnumeratedCounts(ids, owners, step + 1);
        }
        for (uint256 i; i < steps; ++i) {
            if (disputes.getDispute(ids[i], 0).state == DeliveryDisputeV1.State.OPEN) _closeRow(ids[i], uint8(i % 3));
            _assertEnumeratedCounts(ids, owners, steps);
        }
        assertEq(disputes.totalBondsHeld(), 0);
    }
}
