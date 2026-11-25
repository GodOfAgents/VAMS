// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {DeliveryDisputeFixture} from "./DeliveryDisputeFixture.sol";
import {DeliveryDisputeV1} from "../../src/economic/DeliveryDisputeV1.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {IComposedDeliveryVerifier} from "../../src/economic/IComposedDeliveryVerifier.sol";
import {ActionContextV1} from "../../src/trust/ActionContextV1.sol";

/// Characterization of dispute economics (F13 bond-sufficiency analysis, 2026-11-25).
/// These tests pin CURRENT behavior so the analysis rests on executed facts. They are not
/// acceptance of the bond size: they show where the 5% bond does and does not impose a cost.
contract DeliveryDisputeEconomicsTest is DeliveryDisputeFixture {
    function _admitSelfAsProvider() internal {
        govern(abi.encodeCall(policy.setEligibility,
            (workload, bytes32(uint256(uint160(address(this)))), template.target, true)));
    }

    function _createRow(address p, uint256 amount) internal returns (bytes32 id) {
        address[] memory providers = new address[](1); providers[0] = p;
        uint256[] memory amounts = new uint256[](1); amounts[0] = amount;
        bytes32[] memory workloads = new bytes32[](1); workloads[0] = workload;
        id = settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("blueprint"), bytes32(0), bytes32(0), workloads));
    }

    function _earnAs(bytes32 id, address p) internal {
        vm.prank(p); settlement.issueDeliveryChallenge(id, 0);
        IComposedDeliveryVerifier.ExpectedDelivery memory e = settlement.getExpectedDelivery(id, 0);
        ActionContextV1.Context memory c = template;
        c.budget = settlement.getProviderAlloc(id, 0).amount; // bind the real row amount
        c.actorRoot = bytes32(uint256(uint160(p))); c.providerId = c.actorRoot;
        c.actionHash = e.context; c.intentId = id; c.nonce = e.nonce; c.issuedAt = e.issuedAt;
        c.expiresAt = e.expiresAt; c.policyRoot = e.policyRoot; c.policyVersion = e.policyVersion;
        c.authorityEpoch = e.authorityEpoch;
        vm.prank(p); settlement.recordEarnedDeliveryV3(id, 0, keccak256("output"), abi.encode(c, uint8(1), hex"01"));
    }

    /// Admission gate: an address governance has not made an initiator cannot open an escrow,
    /// so in the restricted profile a collusion ring needs governance-admitted identities.
    function test_unadmittedInitiatorCannotCreateEscrow() public {
        address[] memory providers = new address[](1); providers[0] = provider;
        uint256[] memory amounts = new uint256[](1); amounts[0] = ROW;
        bytes32[] memory workloads = new bytes32[](1); workloads[0] = workload;
        deal(address(token), stranger, ROW);
        vm.startPrank(stranger);
        token.approve(address(settlement), ROW);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("blueprint"), bytes32(0), bytes32(0), workloads));
        vm.stopPrank();
    }

    /// Collusion limit: when the agent is also the provider, every outcome returns the bond to
    /// the same controller. Timeout and reject cost only the 5 bps protocol fee; uphold costs nothing.
    function test_selfDealingDisputeCostsOnlyTheProtocolFee() public {
        _admitSelfAsProvider();
        uint256[3] memory expectedCost = [FEE, FEE, uint256(0)]; // timeout, reject, uphold
        for (uint256 outcome; outcome < 3; ++outcome) {
            uint256 start = token.balanceOf(address(this));
            bytes32 id = _createRow(address(this), ROW);
            _earnAs(id, address(this));
            disputes.openDispute(id, 0, keccak256("self"));
            if (outcome == 0) {
                vm.warp(block.timestamp + 14 days);
                disputes.finalizeTimeout(id, 0);
            } else {
                vm.prank(resolver); disputes.resolve(id, 0, outcome == 2);
            }
            if (outcome != 2) {
                vm.warp(block.timestamp + 72 hours);
                settlement.claimEarnedProviderShareV3(id, 0);
            }
            assertEq(start - token.balanceOf(address(this)), expectedCost[outcome]);
            assertBacking();
        }
    }

    /// Dust: rows still have no minimum amount, but since decision 10b a 1-unit row posts the
    /// MIN_BOND floor (1 VAMS) instead of a 1-unit bond. On testnet VAMS has no market value,
    /// so this shows the mechanism, not economic deterrence.
    function test_dustRowDisputePostsTheBondFloor() public {
        bytes32 id = _createRow(provider, 1);
        _earnAs(id, provider);
        uint256 before = token.balanceOf(address(this));
        disputes.openDispute(id, 0, keccak256("dust"));
        assertEq(before - token.balanceOf(address(this)), disputes.MIN_BOND());
        assertEq(disputes.getDispute(id, 0).bond, disputes.MIN_BOND());
        assertEq(disputes.totalBondsHeld(), disputes.MIN_BOND());
    }

    /// Uphold refunds the whole row: no protocol fee and no builder share are charged, so a
    /// mistaken uphold transfers the full row amount from provider to agent.
    function test_upholdRefundsFullRowWithoutFee() public {
        bytes32 id = _createRow(provider, ROW);
        _earnAs(id, provider);
        uint256 start = token.balanceOf(address(this));
        disputes.openDispute(id, 0, keccak256("reason"));
        vm.prank(resolver); disputes.resolve(id, 0, true);
        assertEq(token.balanceOf(address(this)) - (start - BOND), ROW + BOND);
        assertEq(token.balanceOf(TREASURY), 0);
        assertEq(token.balanceOf(provider), 0);
    }
}
