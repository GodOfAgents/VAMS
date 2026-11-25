// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {VAMSToken} from "../../src/token/VAMSToken.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {DeliveryDisputeV1} from "../../src/economic/DeliveryDisputeV1.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {IComposedDeliveryVerifier} from "../../src/economic/IComposedDeliveryVerifier.sol";
import {ActionContextV1} from "../../src/trust/ActionContextV1.sol";
import {RestrictedTestnetPolicyV1} from "../../src/trust/RestrictedTestnetPolicyV1.sol";
import {ActionDeliveryVerifierV1} from "../../src/trust/ActionDeliveryVerifierV1.sol";
import {VAMSTimelockController} from "../../src/governance/VAMSTimelockController.sol";

/// Dispute window acceptance (owner decision 10) against the real
/// ActionDeliveryVerifierV1 and RestrictedTestnetPolicyV1. The evidence backend
/// is a noncryptographic fixture; authentic SGX/EZKL evidence is F06/F07.
contract DisputeAcceptingBackendFixture {
    function verifyAction(ActionContextV1.Context calldata, bytes32, bytes calldata) external pure returns (bool) {
        return true;
    }
}
contract DisputeBondFixture {
    function canAcceptRequest(address, uint256) external pure returns (bool, string memory) { return (true, ""); }
    function acceptRequest(address, bytes32, uint256) external {}
    function completeRequest(address, bytes32) external {}
    function cancelRequest(address, bytes32) external {}
}
contract DisputeUnusedRegistryFixture {}

abstract contract DeliveryDisputeFixture is Test {
    VAMSToken internal token;
    ComposedSettlement internal settlement;
    DeliveryDisputeV1 internal disputes;
    RestrictedTestnetPolicyV1 internal policy;
    VAMSTimelockController internal timelock;
    ActionContextV1.Context internal template;
    address internal provider;
    address internal provider2;
    address internal resolver;
    address internal stranger;
    uint256 internal governanceNonce;
    bytes32 internal workload;
    uint256 internal constant ROW = 100 ether;
    uint256 internal constant BOND = 5 ether; // ceil(5% of ROW)
    uint256 internal constant PAYOUT = 99.95 ether; // ROW minus 5 bps fee, no builder
    uint256 internal constant FEE = 0.05 ether;
    address internal constant TREASURY = address(0xFEE);

    function govern(bytes memory data) internal {
        bytes32 salt = bytes32(++governanceNonce);
        timelock.schedule(address(policy), 0, data, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
        timelock.execute(address(policy), 0, data, bytes32(0), salt);
    }

    function setUp() public virtual {
        vm.chainId(80002);
        provider = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-PROVIDER-1")));
        provider2 = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-PROVIDER-2")));
        stranger = vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-STRANGER")));
        token = new VAMSToken(address(this), address(this));
        timelock = new VAMSTimelockController(48 hours, _proposers(), _executors(), address(this));
        resolver = _resolverAddress();
        policy = new RestrictedTestnetPolicyV1(address(timelock), keccak256("amoy-fixture"), keccak256("faucet-base-units"));
        DisputeAcceptingBackendFixture backend = new DisputeAcceptingBackendFixture();
        ActionDeliveryVerifierV1 router = new ActionDeliveryVerifierV1(address(policy), address(policy).codehash,
            address(backend), address(backend).codehash, address(backend), address(backend).codehash);
        settlement = new ComposedSettlement(address(this), address(token), address(new DisputeBondFixture()),
            TREASURY, address(new DisputeUnusedRegistryFixture()), address(router), resolver);
        disputes = settlement.disputes();
        token.approve(address(settlement), type(uint256).max);
        token.approve(address(disputes), type(uint256).max);
        template.runtimeId = keccak256("runtime"); template.modelId = keccak256("model");
        template.workflowId = keccak256("workflow"); template.inputHash = keccak256("exact-input");
        template.hostDomain = policy.hostDomain(); template.budgetUnit = policy.budgetUnit();
        template.target = bytes32(uint256(uint160(address(settlement)))); template.rootScheme = 1;
        template.chainId = block.chainid; template.capabilities = 4; template.budget = ROW;
        workload = ActionContextV1.workloadHash(template);
        govern(abi.encodeCall(policy.configure, (keccak256("policy"), 1, 1, 4, 2 * ROW, 1 hours)));
        govern(abi.encodeCall(policy.setEligibility, (workload, bytes32(uint256(uint160(provider))), template.target, true)));
        govern(abi.encodeCall(policy.setEligibility, (workload, bytes32(uint256(uint160(provider2))), template.target, true)));
        govern(abi.encodeCall(policy.setInitiator, (address(this), true)));
    }

    // ---- helpers ------------------------------------------------------------

    function create(uint256 rows) internal returns (bytes32 id) {
        address[] memory providers = new address[](rows);
        uint256[] memory amounts = new uint256[](rows);
        bytes32[] memory workloads = new bytes32[](rows);
        for (uint256 i; i < rows; ++i) {
            providers[i] = i == 0 ? provider : provider2; amounts[i] = ROW; workloads[i] = workload;
        }
        id = settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers, amounts, 1 hours, keccak256("blueprint"), bytes32(0), bytes32(0), workloads));
    }

    function who(uint256 index) internal view returns (address) {
        return index == 0 ? provider : provider2;
    }

    function earn(bytes32 id, uint256 index) internal {
        address p = who(index);
        vm.prank(p); settlement.issueDeliveryChallenge(id, index);
        IComposedDeliveryVerifier.ExpectedDelivery memory e = settlement.getExpectedDelivery(id, index);
        ActionContextV1.Context memory c = template;
        c.actorRoot = bytes32(uint256(uint160(p))); c.providerId = c.actorRoot;
        c.actionHash = e.context; c.intentId = id; c.nonce = e.nonce; c.issuedAt = e.issuedAt;
        c.expiresAt = e.expiresAt; c.policyRoot = e.policyRoot; c.policyVersion = e.policyVersion;
        c.authorityEpoch = e.authorityEpoch;
        vm.prank(p); settlement.recordEarnedDeliveryV3(id, index, keccak256("output"), abi.encode(c, uint8(1), hex"01"));
    }

    function claim(bytes32 id, uint256 index) internal {
        vm.prank(who(index)); settlement.claimEarnedProviderShareV3(id, index);
    }

    function dispute(bytes32 id, uint256 index) internal {
        disputes.openDispute(id, index, keccak256("reason"));
    }

    function assertBacking() internal view {
        assertEq(token.balanceOf(address(settlement)), settlement.totalEscrowed());
        assertEq(token.balanceOf(address(disputes)), disputes.totalBondsHeld());
    }

    /// Hooks for governance-path tests. Defaults reproduce the original unit fixture.
    function _proposers() internal virtual returns (address[] memory members) {
        members = new address[](1); members[0] = address(this);
    }

    function _executors() internal virtual returns (address[] memory members) {
        members = new address[](1); members[0] = address(this);
    }

    function _resolverAddress() internal virtual returns (address) {
        return vm.addr(uint256(keccak256("LOCAL-ONLY-DISPUTE-RESOLVER")));
    }
}
