// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {VAMSToken} from "../../src/token/VAMSToken.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {IComposedDeliveryVerifier} from "../../src/economic/IComposedDeliveryVerifier.sol";
import {ActionContextV1} from "../../src/trust/ActionContextV1.sol";
import {RestrictedTestnetPolicyV1} from "../../src/trust/RestrictedTestnetPolicyV1.sol";
import {ActionDeliveryVerifierV1} from "../../src/trust/ActionDeliveryVerifierV1.sol";
import {VAMSTimelockController} from "../../src/governance/VAMSTimelockController.sol";

/// F13 acceptance gaps (2026-11-09) against the real ActionDeliveryVerifierV1
/// and RestrictedTestnetPolicyV1. The evidence backend is a noncryptographic
/// fixture: authentic SGX/EZKL evidence is F06/F07 and is not tested here.
contract F13AcceptingBackendFixture {
    function verifyAction(ActionContextV1.Context calldata, bytes32, bytes calldata) external pure returns (bool) {
        return true;
    }
}
contract F13BondFixture {
    function canAcceptRequest(address, uint256) external pure returns (bool, string memory) { return (true, ""); }
    function acceptRequest(address, bytes32, uint256) external {}
    function completeRequest(address, bytes32) external {}
    function cancelRequest(address, bytes32) external {}
}
contract F13UnusedRegistryFixture {}

contract ComposedSettlementF13AcceptanceTest is Test {
    VAMSToken internal token;
    ComposedSettlement internal settlement;
    ComposedSettlement internal otherSettlement;
    RestrictedTestnetPolicyV1 internal policy;
    VAMSTimelockController internal timelock;
    ActionDeliveryVerifierV1 internal router;
    ActionContextV1.Context internal template;
    address internal provider;
    address internal stranger;
    uint256 internal governanceNonce;
    bytes32 internal workload;

    function govern(bytes memory data) internal {
        bytes32 salt = bytes32(++governanceNonce);
        timelock.schedule(address(policy), 0, data, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        timelock.execute(address(policy), 0, data, bytes32(0), salt);
    }

    function setUp() public {
        vm.chainId(80002);
        provider = vm.addr(uint256(keccak256("LOCAL-ONLY-F13-PROVIDER-20261109")));
        stranger = vm.addr(uint256(keccak256("LOCAL-ONLY-F13-STRANGER-20261109")));
        token = new VAMSToken(address(this), address(this));
        address[] memory members = new address[](1); members[0] = address(this);
        timelock = new VAMSTimelockController(48 hours, members, members, address(this));
        policy = new RestrictedTestnetPolicyV1(address(timelock), keccak256("amoy-fixture"), keccak256("faucet-base-units"));
        F13AcceptingBackendFixture backend = new F13AcceptingBackendFixture();
        router = new ActionDeliveryVerifierV1(address(policy), address(policy).codehash,
            address(backend), address(backend).codehash, address(backend), address(backend).codehash);
        settlement = new ComposedSettlement(address(this), address(token), address(new F13BondFixture()),
            address(0xFEE), address(new F13UnusedRegistryFixture()), address(router));
        otherSettlement = new ComposedSettlement(address(this), address(token), address(new F13BondFixture()),
            address(0xFEE), address(new F13UnusedRegistryFixture()), address(router));
        token.approve(address(settlement), type(uint256).max);
        token.approve(address(otherSettlement), type(uint256).max);
        template.actorRoot = bytes32(uint256(uint160(provider))); template.providerId = template.actorRoot;
        template.runtimeId = keccak256("runtime"); template.modelId = keccak256("model");
        template.workflowId = keccak256("workflow"); template.inputHash = keccak256("exact-input");
        template.hostDomain = policy.hostDomain(); template.budgetUnit = policy.budgetUnit();
        template.target = bytes32(uint256(uint160(address(settlement)))); template.rootScheme = 1;
        template.chainId = block.chainid; template.capabilities = 4; template.budget = 100 ether;
        workload = ActionContextV1.workloadHash(template);
        govern(abi.encodeCall(policy.configure, (keccak256("policy"), 1, 1, 4, 100 ether, 1 hours)));
        govern(abi.encodeCall(policy.setEligibility, (workload, template.providerId, template.target, true)));
        govern(abi.encodeCall(policy.setEligibility,
            (workload, template.providerId, bytes32(uint256(uint160(address(otherSettlement)))), true)));
        govern(abi.encodeCall(policy.setInitiator, (address(this), true)));
    }

    function create(ComposedSettlement target, bytes32 blueprint) internal returns (bytes32 id) {
        address[] memory providers = new address[](1); providers[0] = provider;
        uint256[] memory amounts = new uint256[](1); amounts[0] = 100 ether;
        bytes32[] memory workloads = new bytes32[](1); workloads[0] = workload;
        id = target.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, blueprint, bytes32(0), bytes32(0), workloads));
    }

    function challenge(ComposedSettlement target, bytes32 id) internal returns (ActionContextV1.Context memory c) {
        vm.prank(provider); target.issueDeliveryChallenge(id, 0);
        IComposedDeliveryVerifier.ExpectedDelivery memory expected = target.getExpectedDelivery(id, 0);
        c = template; c.target = bytes32(uint256(uint160(address(target))));
        c.actionHash = expected.context; c.intentId = id; c.nonce = expected.nonce;
        c.issuedAt = expected.issuedAt; c.expiresAt = expected.expiresAt; c.policyRoot = expected.policyRoot;
        c.policyVersion = expected.policyVersion; c.authorityEpoch = expected.authorityEpoch;
    }

    function proof(ActionContextV1.Context memory c) internal pure returns (bytes memory) {
        return abi.encode(c, uint8(1), hex"01");
    }

    function claimOn(ComposedSettlement target, bytes32 id, ActionContextV1.Context memory c) internal {
        vm.prank(provider);
        target.claimProviderShareV2(id, 0, keccak256("output"), proof(c));
    }

    /// Wrong domain: a context declaring another chain is rejected by policy.
    function test_proofDeclaringAnotherChainCannotPay() public {
        bytes32 id = create(settlement, keccak256("bp")); ActionContextV1.Context memory c = challenge(settlement, id);
        c.chainId = 1;
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector); claimOn(settlement, id, c);
        assertEq(token.balanceOf(provider), 0);
    }

    /// Wrong domain: a context naming another settlement contract is rejected.
    function test_proofTargetingAnotherSettlementCannotPay() public {
        bytes32 id = create(settlement, keccak256("bp")); ActionContextV1.Context memory c = challenge(settlement, id);
        c.target = bytes32(uint256(uint160(address(otherSettlement))));
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector); claimOn(settlement, id, c);
        assertEq(token.balanceOf(provider), 0);
    }

    /// A valid proof for one settlement deployment cannot pay on another.
    function test_proofFromOneDeploymentCannotPayAnother() public {
        bytes32 a = create(settlement, keccak256("bp"));
        bytes32 b = create(otherSettlement, keccak256("bp"));
        ActionContextV1.Context memory forA = challenge(settlement, a);
        challenge(otherSettlement, b);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector); claimOn(otherSettlement, b, forA);
        claimOn(settlement, a, forA);
        assertEq(token.balanceOf(provider), 99.95 ether);
    }

    /// A valid proof for one allocation cannot pay a second allocation with
    /// identical provider, workload and amount.
    function test_proofFromOneAllocationCannotPayAnother() public {
        bytes32 first = create(settlement, keccak256("bp-1"));
        bytes32 second = create(settlement, keccak256("bp-2"));
        ActionContextV1.Context memory forFirst = challenge(settlement, first);
        ActionContextV1.Context memory forSecond = challenge(settlement, second);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector); claimOn(settlement, second, forFirst);
        claimOn(settlement, first, forFirst);
        claimOn(settlement, second, forSecond);
        assertEq(token.balanceOf(provider), 2 * 99.95 ether);
    }

    /// Wrong intent: same nonce and context but another intent ID is rejected.
    function test_wrongIntentWithCurrentNonceCannotPay() public {
        bytes32 id = create(settlement, keccak256("bp")); ActionContextV1.Context memory c = challenge(settlement, id);
        c.intentId = bytes32(uint256(id) ^ 1);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector); claimOn(settlement, id, c);
    }

    /// Paid once: the recorded proof cannot be reused after payment, and the
    /// provider cannot obtain a fresh challenge for a paid row.
    function test_paidRowCannotBeChallengedOrPaidAgain() public {
        bytes32 id = create(settlement, keccak256("bp")); ActionContextV1.Context memory c = challenge(settlement, id);
        claimOn(settlement, id, c);
        vm.prank(provider);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.ProviderAlreadyClaimed.selector, id, 0));
        settlement.issueDeliveryChallenge(id, 0);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.ProviderAlreadyClaimed.selector, id, 0));
        claimOn(settlement, id, c);
        assertEq(token.balanceOf(provider), 99.95 ether);
    }

    /// Unauthorized verifiers: granting the historical VERIFIER_ROLE confers
    /// no approval or payment power.
    function test_grantedVerifierRoleCannotApproveOrPay() public {
        bytes32 id = create(settlement, keccak256("bp"));
        settlement.grantRole(settlement.VERIFIER_ROLE(), stranger);
        vm.startPrank(stranger);
        vm.expectRevert(IComposedSettlement.LegacyInterfaceDisabled.selector);
        settlement.verifyProviderProof(id, 0);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.ProviderMismatch.selector, provider, stranger));
        settlement.issueDeliveryChallenge(id, 0);
        vm.stopPrank();
        vm.prank(provider);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.DeliveryNotEarned.selector, id, 0));
        settlement.claimEarnedProviderShareV3(id, 0);
        assertEq(token.balanceOf(provider), 0);
        assertEq(token.balanceOf(stranger), 0);
    }

    /// Only the provider can open a challenge; a stranger cannot reset it.
    function test_strangerCannotReplaceProvidersChallenge() public {
        bytes32 id = create(settlement, keccak256("bp")); ActionContextV1.Context memory c = challenge(settlement, id);
        vm.prank(stranger);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.ProviderMismatch.selector, provider, stranger));
        settlement.issueDeliveryChallenge(id, 0);
        claimOn(settlement, id, c);
    }

    /// Expiry preserves refund even while paused and after a stale challenge.
    function test_expiryRefundWorksWhilePausedAfterStaleChallenge() public {
        bytes32 id = create(settlement, keccak256("bp")); challenge(settlement, id);
        settlement.pause();
        vm.warp(settlement.getComposedAllocation(id).expiresAt + 1);
        uint256 before = token.balanceOf(address(this));
        settlement.refundExpiredComposed(id);
        assertEq(token.balanceOf(address(this)) - before, 100 ether);
        assertEq(token.balanceOf(address(settlement)), 0);
    }
}
