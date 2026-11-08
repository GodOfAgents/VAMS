// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {ComposedSettlement} from "../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../src/economic/IComposedSettlement.sol";
import {ProviderBondRegistry} from "../src/economic/ProviderBondRegistry.sol";
import {ActionContextV1 as A} from "../src/trust/ActionContextV1.sol";
import {GovernedObjectGrantV1 as G} from "../src/trust/GovernedObjectGrantV1.sol";
import {EffectReceiptV3 as R} from "../src/trust/EffectReceiptV3.sol";
import {ObjectEffectV3 as O} from "../src/trust/ObjectEffectV3.sol";
import {RestrictedTestnetPolicyV1} from "../src/trust/RestrictedTestnetPolicyV1.sol";
import {ActionDeliveryVerifierV1} from "../src/trust/ActionDeliveryVerifierV1.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";
import {MockToken,SettlementRegistryFixture} from "./economic/ComposedSettlement.t.sol";
import {EarnedProofBackendFixture} from "./EarnedDeliveryPolicy.t.sol";

/// Actual policy, actor consent, asymmetric receipts, settlement and bond ledger in the
/// local VM. Public fixture keys 1/2/3 are not custody, external effects or live evidence.
contract LateReservationRegressionTest is Test {
    ComposedSettlement internal settlement;
    ProviderBondRegistry internal bonds;
    MockToken internal token;
    RestrictedTestnetPolicyV1 internal policy;
    VAMSTimelockController internal timelock;
    G.Proposal internal proposal;
    G.Witness internal witness;
    bytes internal admission;
    R.Receipt internal admitted;
    address internal provider;
    address internal agent;
    uint256 internal governanceNonce;
    uint256 internal constant AMOUNT = 100 ether;

    function key(uint256 n) internal pure returns (bytes memory) {
        if (n == 1) return hex"0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8";
        return hex"04c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee51ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a";
    }
    function sign(R.Receipt memory r,uint256 n) internal pure returns (bytes memory) {
        (,bytes32 x,bytes32 y)=vm.sign(n,R.digest(r));
        return abi.encodePacked("VAMS:EFFECT-SIGNED:v3",hex"00","VAMS:SIGNED-RECEIPT:v3",hex"00",
            abi.encode(r),x,y);
    }
    function consent(bytes32 d) internal pure returns (bytes memory) {
        (uint8 v,bytes32 r,bytes32 s)=vm.sign(3,d);return abi.encodePacked(r,s,v);
    }
    function govern(bytes memory data) internal {
        bytes32 salt=bytes32(++governanceNonce);
        timelock.schedule(address(policy),0,data,0,salt,48 hours);
        vm.warp(block.timestamp+48 hours);timelock.execute(address(policy),0,data,0,salt);
    }
    function setUp() public {
        vm.chainId(80002);vm.warp(1_000_000);provider=vm.addr(2);agent=vm.addr(3);
        token=new MockToken();bonds=new ProviderBondRegistry();
        bonds.initialize(address(this),address(token),address(0x1A5));
        address[] memory members=new address[](1);members[0]=address(this);
        timelock=new VAMSTimelockController(48 hours,members,members,address(this));
        policy=new RestrictedTestnetPolicyV1(address(timelock),sha256("native-host-fixture"),sha256("governed-cost-unit"));
        EarnedProofBackendFixture backend=new EarnedProofBackendFixture();
        ActionDeliveryVerifierV1 router=new ActionDeliveryVerifierV1(address(policy),address(policy).codehash,
            address(backend),address(backend).codehash,address(backend),address(backend).codehash);
        settlement=new ComposedSettlement(address(this),address(token),address(bonds),address(0xFEE),
            address(new SettlementRegistryFixture()),address(router));
        bonds.grantRole(bonds.ESCROW_ROLE(),address(settlement));
        token.mint(agent,10_000 ether);token.mint(provider,10_000 ether);
        vm.prank(provider);bonds.registerProvider(10_000 ether,1_000 ether);
        A.Context memory c;
        c.actorRoot=bytes32(uint256(uint160(vm.addr(3))));c.providerId=bytes32(uint256(uint160(provider)));
        c.runtimeId=sha256("immutable-object-runtime");c.hostDomain=policy.hostDomain();
        c.workflowId=sha256("workflow");c.intentId=sha256("logical-intent");c.inputHash=sha256("exact-object-bytes");
        c.target=bytes32(uint256(uint160(address(settlement))));c.nonce=sha256("action-nonce");
        c.budgetUnit=policy.budgetUnit();c.rootScheme=1;c.capabilities=1;c.budget=10;c.chainId=80002;
        (,,bytes32 authority)=R.issuer(key(1));(,,bytes32 providerIssuer)=R.issuer(key(2));
        G.Grant memory g;
        g.actorRoot=c.actorRoot;g.providerId=c.providerId;g.runtimeId=c.runtimeId;g.workflowId=c.workflowId;
        g.intentId=c.intentId;g.target=c.target;g.authorityIssuer=authority;g.providerIssuer=providerIssuer;
        g.nonce=sha256("grant-nonce");g.budgetLimit=10;g.maxActionCost=6;g.maxScopeLifetime=600;
        g.validAfter=block.timestamp+6 days;g.validUntil=g.validAfter+1 days;
        g.resources=new bytes32[](2);g.resources[0]=bytes32(uint256(1));g.resources[1]=bytes32(uint256(2));
        bytes32 grant=policy.objectGrantDigestV1(g);
        bytes32 root=sha256(abi.encodePacked("VAMS:OBJECT-GRANT-LEAF:v1",hex"00",grant));
        witness=G.Witness(g,consent(grant),new bytes32[](0),0);
        govern(abi.encodeCall(policy.configure,(root,1,1,5,1000 ether,1 hours)));
        timelock.schedule(address(policy),0,abi.encodeCall(policy.configure,(root,4,4,5,1000 ether,1 hours)),
            0,bytes32(uint256(400)),48 hours);
        timelock.schedule(address(policy),0,abi.encodeCall(policy.configure,(root,5,5,5,1000 ether,1 hours)),
            0,bytes32(uint256(500)),48 hours);
        govern(abi.encodeCall(policy.setEligibility,(A.workloadHash(c),c.providerId,c.target,true)));
        govern(abi.encodeCall(policy.setInitiator,(agent,true)));
        c.policyRoot=root;c.policyVersion=policy.policyVersion();c.authorityEpoch=policy.authorityEpoch();
        c.issuedAt=block.timestamp;c.expiresAt=block.timestamp+100;
        G.Proposal memory p=G.Proposal(c,bytes32(uint256(1)),6,9);p.context.actionHash=G.actionHash(p);proposal=p;
        admitted=R.Receipt(authority,O.digest(p),c.providerId,1,c.authorityEpoch,c.policyVersion,9,c.issuedAt,c.expiresAt);
        admission=sign(admitted,1);
    }
    function create(uint256 count) internal returns (bytes32) {
        address[] memory providers=new address[](count);uint256[] memory amounts=new uint256[](count);
        bytes32[] memory workloads=new bytes32[](count);
        for(uint256 i;i<count;++i){providers[i]=provider;amounts[i]=AMOUNT;workloads[i]=A.workloadHash(proposal.context);}
        IComposedSettlement.EscrowRequestV2 memory request=IComposedSettlement.EscrowRequestV2(providers,amounts,300,
            sha256("blueprint"),0,0,workloads);
        vm.prank(agent);return settlement.createComposedEscrowV2(request);
    }

    function test_admittedFundsCannotBeRefundedWhileCompletionIsUnresolved() public {
        bytes32 id=create(1);
        O.Admission memory request=O.Admission(proposal,witness,key(1),key(2),admission);
        vm.prank(agent);
        (bool accepted,)=address(settlement).call(abi.encodeCall(ILateAdmissionProbe44.admitObjectV3,(id,0,request)));
        vm.warp(block.timestamp+301);
        vm.prank(agent);settlement.refundExpiredComposed(id);
        assertEq(settlement.totalEscrowed(),AMOUNT,"Unresolved admitted obligation lost its funding");
        assertTrue(accepted,"Native admission must actually succeed");
    }
}
interface ILateAdmissionProbe44 {
    function admitObjectV3(bytes32 id,uint256 index,O.Admission calldata request) external;
}
