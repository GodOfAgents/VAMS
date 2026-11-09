// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
// Dispute window (owner decision 10): earned payments are held 72 hours. Tests
// advance the clock across the window for each claim and restore it afterwards,
// so every original timeline and expectation is unchanged.
import {Test} from "forge-std/Test.sol";
import {VAMSToken} from "../src/token/VAMSToken.sol";
import {ComposedSettlement} from "../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../src/economic/IComposedSettlement.sol";
import {IComposedDeliveryVerifier} from "../src/economic/IComposedDeliveryVerifier.sol";
import {ActionContextV1} from "../src/trust/ActionContextV1.sol";
import {RestrictedTestnetPolicyV1} from "../src/trust/RestrictedTestnetPolicyV1.sol";
import {ActionDeliveryVerifierV1} from "../src/trust/ActionDeliveryVerifierV1.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";

// Explicit collaborator fixtures: this suite tests application/policy wiring,
// NOT authentic hardware, SNARKs, provider bonding or live ledger qualification.
contract NonCryptographicActionBackendFixture {
    bool public accepting = true;
    function setAccepting(bool value) external { accepting = value; }
    function verifyAction(ActionContextV1.Context calldata, bytes32, bytes calldata) external view returns (bool) {
        return accepting;
    }
}
contract BondAdmissionFixture {
    function canAcceptRequest(address, uint256) external pure returns (bool, string memory) { return (true, ""); }
    function acceptRequest(address, bytes32, uint256) external {}
    function completeRequest(address, bytes32) external {}
    function cancelRequest(address, bytes32) external {}
}
contract UnusedRawBlueprintRegistryFixture {}

contract SettlementActionPolicyTest is Test {
    VAMSToken internal token;
    ComposedSettlement internal settlement;
    RestrictedTestnetPolicyV1 internal policy;
    VAMSTimelockController internal timelock;
    NonCryptographicActionBackendFixture internal backend;
    ActionContextV1.Context internal template;
    address internal provider;
    uint256 internal governanceNonce;
    bytes32 internal workload;

    function govern(bytes memory data) internal {
        bytes32 salt=bytes32(++governanceNonce);
        timelock.schedule(address(policy),0,data,bytes32(0),salt,48 hours);
        vm.warp(block.timestamp+48 hours);
        timelock.execute(address(policy),0,data,bytes32(0),salt);
    }

    function setUp() public {
        vm.chainId(80002);
        provider=vm.addr(uint256(keccak256("LOCAL-ONLY-PROVIDER-PIPELINE-20261027")));
        token=new VAMSToken(address(this),address(this));
        address[] memory members=new address[](1); members[0]=address(this);
        timelock=new VAMSTimelockController(48 hours,members,members,address(this));
        policy=new RestrictedTestnetPolicyV1(address(timelock),keccak256("amoy-fixture"),keccak256("faucet-base-units"));
        backend=new NonCryptographicActionBackendFixture();
        ActionDeliveryVerifierV1 router=new ActionDeliveryVerifierV1(address(policy),address(policy).codehash,
            address(backend),address(backend).codehash,address(backend),address(backend).codehash);
        settlement=new ComposedSettlement(address(this),address(token),address(new BondAdmissionFixture()),
            address(0xFEE),address(new UnusedRawBlueprintRegistryFixture()),address(router),address(this));
        token.approve(address(settlement),type(uint256).max);
        template.actorRoot=bytes32(uint256(uint160(provider))); template.providerId=template.actorRoot;
        template.runtimeId=keccak256("runtime"); template.modelId=keccak256("model");
        template.workflowId=keccak256("workflow"); template.inputHash=keccak256("exact-input");
        template.hostDomain=policy.hostDomain(); template.budgetUnit=policy.budgetUnit();
        template.target=bytes32(uint256(uint160(address(settlement)))); template.rootScheme=1;
        template.chainId=block.chainid; template.capabilities=4; template.budget=100 ether;
        workload=ActionContextV1.workloadHash(template);
        govern(abi.encodeCall(policy.configure,(keccak256("policy"),1,1,4,100 ether,1 hours)));
        govern(abi.encodeCall(policy.setEligibility,(ActionContextV1.workloadHash(template),template.providerId,template.target,true)));
        govern(abi.encodeCall(policy.setInitiator,(address(this),true)));
    }

    function create() internal returns (bytes32 id) {
        address[] memory providers=new address[](1);providers[0]=provider;
        uint256[] memory amounts=new uint256[](1);amounts[0]=100 ether;
        bytes32[] memory workloads=new bytes32[](1);workloads[0]=workload;
        id=settlement.createComposedEscrowV2(IComposedSettlement.EscrowRequestV2(
            providers,amounts,1 hours,keccak256("blueprint"),bytes32(0),bytes32(0),workloads));
    }

    function challenge(bytes32 id) internal returns (ActionContextV1.Context memory c) {
        vm.prank(provider); settlement.issueDeliveryChallenge(id,0);
        IComposedDeliveryVerifier.ExpectedDelivery memory expected=settlement.getExpectedDelivery(id,0);
        c=template; c.actionHash=expected.context; c.intentId=id; c.nonce=expected.nonce;
        c.issuedAt=expected.issuedAt; c.expiresAt=expected.expiresAt; c.policyRoot=expected.policyRoot;
        c.policyVersion=expected.policyVersion; c.authorityEpoch=expected.authorityEpoch;
    }

    function proof(ActionContextV1.Context memory c) internal pure returns (bytes memory) {
        return abi.encode(c,uint8(1),hex"01"); // Noncryptographic collaborator fixture only.
    }

    function claim(bytes32 id, ActionContextV1.Context memory c) internal {
        vm.prank(provider);
        settlement.recordEarnedDeliveryV3(id, 0, keccak256("output"), proof(c));
        if (settlement.getEarnedDeliveryV3(id, 0).accepted && !settlement.getProviderAlloc(id, 0).claimed) {
            vm.prank(provider);
            vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id, 0); vm.warp(block.timestamp - 72 hours);
        }
    }

    function test_applicationPolicyPipelineWithFixtureBackend() public {
        bytes32 id=create(); ActionContextV1.Context memory c=challenge(id);
        claim(id,c);
        assertEq(token.balanceOf(provider),99.95 ether);
        assertEq(token.balanceOf(address(0xFEE)),0.05 ether);
        assertTrue(settlement.getProviderAlloc(id,0).claimed);
        vm.expectRevert(abi.encodeWithSelector(IComposedSettlement.ProviderAlreadyClaimed.selector,id,0));
        claim(id,c);
    }

    function test_falseBackendProducesZeroTransfer() public {
        bytes32 id=create(); ActionContextV1.Context memory c=challenge(id);
        backend.setAccepting(false);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        claim(id,c);
        assertEq(token.balanceOf(provider),0);
        assertEq(token.balanceOf(address(settlement)),100 ether);
        assertFalse(settlement.getProviderAlloc(id,0).claimed);
    }

    function test_noncanonicalOuterProofCannotPay() public {
        bytes32 id=create();ActionContextV1.Context memory c=challenge(id);
        bytes memory altered=bytes.concat(proof(c),hex"00");
        vm.prank(provider);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        settlement.recordEarnedDeliveryV3(id,0,keccak256("output"),altered);
        assertEq(token.balanceOf(provider),0);
    }

    function test_wrongWorkloadAmountRootAndJobProduceZeroTransfers() public {
        bytes32 id=create(); ActionContextV1.Context memory c=challenge(id);
        c.inputHash=keccak256("other-input");
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);claim(id,c);
        c=challenge(id);c.budget=99 ether;
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);claim(id,c);
        c=challenge(id);c.actorRoot=bytes32(uint256(0xBAD));
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);claim(id,c);
        c=challenge(id);c.intentId=keccak256("other-job");
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);claim(id,c);
        assertEq(token.balanceOf(provider),0);
        assertFalse(settlement.getProviderAlloc(id,0).claimed);
    }

    function test_previousChallengeCannotAuthorizeAfterReplacement() public {
        bytes32 id=create();ActionContextV1.Context memory old=challenge(id);
        ActionContextV1.Context memory current=challenge(id);
        assertTrue(old.nonce!=current.nonce);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);claim(id,old);
        claim(id,current);
    }

    function test_expiredChallengeCannotPayAndRefundRemainsAvailable() public {
        bytes32 id=create();ActionContextV1.Context memory c=challenge(id);
        vm.warp(c.expiresAt);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);claim(id,c);
        vm.warp(settlement.getComposedAllocation(id).expiresAt+1);
        uint256 before=token.balanceOf(address(this));
        settlement.refundExpiredComposed(id);
        assertEq(token.balanceOf(address(this))-before,100 ether);
    }

    function test_stillUnexpiredChallengeInvalidatedByTimelockedPolicyChange() public {
        bytes memory update=abi.encodeCall(policy.setEligibility,(ActionContextV1.workloadHash(template),template.providerId,template.target,false));
        bytes32 salt=keccak256("revoke-route");
        timelock.schedule(address(policy),0,update,bytes32(0),salt,48 hours);
        vm.warp(block.timestamp+48 hours-10);
        bytes32 id=create();ActionContextV1.Context memory c=challenge(id);
        vm.warp(block.timestamp+10);
        timelock.execute(address(policy),0,update,bytes32(0),salt);
        assertLt(block.timestamp,c.expiresAt);
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);claim(id,c);
        assertEq(token.balanceOf(provider),0);
    }

    function test_directUnapprovedInitiatorCannotFundEscrow() public {
        govern(abi.encodeCall(policy.setInitiator,(address(this),false)));
        vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        create();
        assertEq(settlement.allocationCount(),0);
        assertEq(token.balanceOf(address(settlement)),0);
    }
}
