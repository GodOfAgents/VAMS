// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
// Dispute window (owner decision 10): earned payments are held 72 hours. Tests
// advance the clock across the window for each claim and restore it afterwards,
// so every original timeline and expectation is unchanged.
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
contract ObjectSettlementV3Test is Test {
    ComposedSettlement internal settlement;
    ProviderBondRegistry internal bonds;
    MockToken internal token;
    RestrictedTestnetPolicyV1 internal policy;
    VAMSTimelockController internal timelock;
    G.Proposal internal proposal;
    G.Witness internal witness;
    G.Witness internal otherActorWitness;
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
    function otherConsent(bytes32 d) internal pure returns (bytes memory) {
        (uint8 v,bytes32 r,bytes32 s)=vm.sign(4,d);return abi.encodePacked(r,s,v);
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
            address(new SettlementRegistryFixture()),address(router),address(this));
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
        G.Grant memory otherGrant=abi.decode(abi.encode(g),(G.Grant));
        otherGrant.actorRoot=bytes32(uint256(uint160(vm.addr(4))));
        bytes32 otherDigest=policy.objectGrantDigestV1(otherGrant);
        bytes32 leaf=sha256(abi.encodePacked("VAMS:OBJECT-GRANT-LEAF:v1",hex"00",grant));
        bytes32 otherLeaf=sha256(abi.encodePacked("VAMS:OBJECT-GRANT-LEAF:v1",hex"00",otherDigest));
        bytes32 root=sha256(abi.encodePacked("VAMS:OBJECT-GRANT-NODE:v1",hex"00",leaf,otherLeaf));
        bytes32[] memory siblings=new bytes32[](1);siblings[0]=otherLeaf;
        witness=G.Witness(g,consent(grant),siblings,0);
        siblings=new bytes32[](1);siblings[0]=leaf;
        otherActorWitness=G.Witness(otherGrant,otherConsent(otherDigest),siblings,1);
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
    function admit(bytes32 id,uint256 index) internal {
        O.Admission memory request=O.Admission(proposal,witness,key(1),key(2),admission);
        vm.prank(agent);settlement.admitObjectV3(id,index,request);
    }
    function refundExpired(bytes32 id) internal {vm.prank(agent);settlement.refundExpiredComposed(id);}
    function refundAbsent(bytes32 id) internal {vm.prank(agent);settlement.refundAbsentObjectV3(id,0);}
    function resolution() internal view returns (O.ResolutionContext memory) {
        return O.ResolutionContext(proposal,admitted,key(1),key(2),proposal.context.issuedAt);
    }
    function completion(uint256 when_) internal view returns (bytes memory) {
        G.Proposal memory p=proposal;
        bytes32 subject=sha256(abi.encodePacked("VAMS:OBJECT-RESULT:v3",hex"00",
            abi.encode(O.digest(p),R.digest(admitted),p.context.inputHash,O.postcondition(p),uint256(1),when_)));
        (,,bytes32 issuer)=R.issuer(key(2));
        return sign(R.Receipt(issuer,subject,p.context.providerId,4,p.context.authorityEpoch,
            p.context.policyVersion,p.fencingToken,when_,when_+50),2);
    }
    function absence() internal view returns(O.Fence memory f,bytes memory update,bytes memory ack,bytes memory absent) {
        return absencePolicy(proposal.context.policyVersion+1,proposal.context.policyRoot);
    }
    function absencePolicy(uint256 policyVersion,bytes32 policyRoot) internal view
        returns(O.Fence memory f,bytes memory update,bytes memory ack,bytes memory absent) {
        A.Context memory c=proposal.context;
        f=O.Fence(c.actorRoot,c.providerId,c.hostDomain,policyRoot,c.rootScheme,c.chainId,
            c.authorityEpoch+1,policyVersion,10,block.timestamp,block.timestamp+100);
        (,,bytes32 authority)=R.issuer(key(1));(,,bytes32 issuer)=R.issuer(key(2));
        R.Receipt memory r=R.Receipt(authority,O.fenceDigest(f),c.providerId,2,
            f.authorityEpoch,f.policyVersion,10,f.issuedAt,f.expiresAt);
        update=sign(r,1);
        bytes32 subject=sha256(abi.encodePacked("VAMS:OBJECT-FENCE-ACK:v3",hex"00",O.fenceDigest(f),R.digest(r)));
        r=R.Receipt(issuer,subject,c.providerId,3,f.authorityEpoch,f.policyVersion,10,f.issuedAt,f.expiresAt);
        ack=sign(r,2);
        subject=sha256(abi.encodePacked("VAMS:OBJECT-FENCED-ABSENCE:v3",hex"00",O.digest(proposal),R.digest(r)));
        r=R.Receipt(issuer,subject,c.providerId,5,f.authorityEpoch,f.policyVersion,10,f.issuedAt,f.expiresAt);
        absent=sign(r,2);
    }
    function test_expiryReservesOnlyAdmittedRowAndLateCompletionPaysOriginalProvider() public {
        bytes32 id=create(2);admit(id,0);
        uint256 committed=block.timestamp+1;bytes memory receipt=completion(committed);
        vm.warp(block.timestamp+301);refundExpired(id);
        assertEq(settlement.totalEscrowed(),AMOUNT);assertEq(token.balanceOf(address(settlement)),AMOUNT);
        assertEq(bonds.getBond(provider).pendingSettlements,AMOUNT);
        settlement.setTreasury(address(0xBAD));
        vm.prank(vm.addr(99));settlement.resolveObjectCompletionV3(id,0,resolution(),receipt);
        assertTrue(settlement.getEarnedDeliveryV3(id,0).accepted);
        vm.prank(vm.addr(99));vm.expectRevert();vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id,0); vm.warp(block.timestamp - 72 hours);
        vm.prank(provider);vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id,0); vm.warp(block.timestamp - 72 hours);
        assertEq(token.balanceOf(provider),99.95 ether);assertEq(token.balanceOf(address(0xFEE)),0.05 ether);
        assertEq(token.balanceOf(address(0xBAD)),0);assertEq(settlement.totalEscrowed(),0);
        assertFalse(settlement.verifiedProviderProofs(id,0));
        vm.expectRevert();settlement.resolveObjectCompletionV3(id,0,resolution(),receipt);
    }
    function test_absenceRequiresAllThreeSignedFactsAndRefundIsExactOnce() public {
        bytes32 id=create(1);admit(id,0);
        (O.Fence memory f,bytes memory u,bytes memory a,bytes memory x)=absence();
        vm.expectRevert();settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,hex"",a,x));
        vm.expectRevert();settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,u,hex"",x));
        vm.expectRevert();settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,u,a,hex""));
        settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,u,a,x));
        assertEq(bonds.getBond(provider).pendingSettlements,0);
        refundAbsent(id);assertEq(settlement.totalEscrowed(),0);
        assertEq(token.balanceOf(agent),10_000 ether);
        assertEq(settlement.objectGrantUsedV3(policy.objectGrantDigestV1(witness.grant)),0);
        vm.expectRevert();refundAbsent(id);
        vm.warp(block.timestamp+301);refundExpired(id);
        assertEq(token.balanceOf(agent),10_000 ether);
    }
    function test_timeoutNeverResolvesAbsenceAndPauseAllowsReconciliationOnly() public {
        bytes32 id=create(1);admit(id,0);bytes memory receipt=completion(block.timestamp+1);
        settlement.pause();vm.warp(block.timestamp+365 days);refundExpired(id);
        assertEq(settlement.totalEscrowed(),AMOUNT);
        vm.expectRevert();refundAbsent(id);
        settlement.resolveObjectCompletionV3(id,0,resolution(),receipt);
        vm.prank(provider);vm.expectRevert();vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id,0); vm.warp(block.timestamp - 72 hours);
        settlement.unpause();vm.prank(provider);vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id,0); vm.warp(block.timestamp - 72 hours);
        assertEq(settlement.totalEscrowed(),0);
    }
    function test_actorRevocationInvalidatesPendingAdmissionButRetainsCompletedLiability() public {
        bytes32 id=create(2);admit(id,0);bytes memory receipt=completion(block.timestamp+1);
        vm.prank(vm.addr(3));policy.revokeObjectGrantV1(witness.grant);
        vm.expectRevert();admit(id,1);vm.warp(block.timestamp+301);
        refundExpired(id);settlement.resolveObjectCompletionV3(id,0,resolution(),receipt);
        vm.prank(provider);vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id,0); vm.warp(block.timestamp - 72 hours);assertEq(settlement.totalEscrowed(),0);
    }
    function test_sameOperationCannotReserveTwoRowsOrUseLegacyProofRoute() public {
        bytes32 id=create(2);admit(id,0);vm.expectRevert();admit(id,1);
        vm.prank(provider);vm.expectRevert();settlement.issueDeliveryChallenge(id,0);
        bytes32 output=sha256("output");
        vm.prank(provider);vm.expectRevert();settlement.recordEarnedDeliveryV3(id,0,output,hex"01");
        assertEq(settlement.totalEscrowed(),2*AMOUNT);
    }
    function test_cumulativeNonTokenGrantBudgetCannotBeOverspentAcrossRows() public {
        bytes32 id=create(2);admit(id,0);
        G.Proposal memory p=proposal;p.resourceId=bytes32(uint256(2));p.context.actionHash=G.actionHash(p);
        R.Receipt memory r=admitted;r.subjectDigest=O.digest(p);
        bytes memory envelope=sign(r,1);
        vm.prank(agent);vm.expectRevert("Grant budget exhausted");
        settlement.admitObjectV3(id,1,O.Admission(p,witness,key(1),key(2),envelope));
    }
    function test_completionOutsideWindowWrongSignatureOrWrongSubjectCannotEarn() public {
        bytes32 id=create(1);admit(id,0);vm.warp(block.timestamp+500);
        bytes memory expiredReceipt=completion(admitted.expiresAt);
        vm.expectRevert();settlement.resolveObjectCompletionV3(id,0,resolution(),expiredReceipt);
        bytes memory receipt=completion(admitted.issuedAt+1);receipt[receipt.length-1]^=0x01;
        vm.expectRevert();settlement.resolveObjectCompletionV3(id,0,resolution(),receipt);
        assertEq(settlement.totalEscrowed(),AMOUNT);
    }
    function test_onlyFunderCanReserveAndWrongProviderKeyCannotAuthorize() public {
        bytes32 id=create(1);vm.prank(vm.addr(99));vm.expectRevert("Not the agent");
        settlement.admitObjectV3(id,0,O.Admission(proposal,witness,key(1),key(2),admission));
        vm.prank(agent);vm.expectRevert();settlement.admitObjectV3(id,0,O.Admission(proposal,witness,key(1),key(1),admission));
        assertEq(settlement.totalEscrowed(),AMOUNT);
    }
    function test_anotherFundersRowCannotConsumeThisActorsOperation() public {
        // Change the proposed root only; row-owner binding must reject before signature/policy checks.
        bytes32 id=create(1);G.Proposal memory p=proposal;p.context.actorRoot=bytes32(uint256(uint160(vm.addr(99))));
        p.context.actionHash=G.actionHash(p);
        vm.prank(agent);vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        settlement.admitObjectV3(id,0,O.Admission(p,witness,key(1),key(2),admission));
    }
    function test_validOtherActorGrantCannotConsumeFundersRow() public {
        bytes32 id=create(1);G.Proposal memory p=proposal;
        p.context.actorRoot=otherActorWitness.grant.actorRoot;p.context.actionHash=G.actionHash(p);
        (,,bytes32 authority)=R.issuer(key(1));(,,bytes32 providerIssuer)=R.issuer(key(2));
        assertTrue(policy.authorizesObjectV1(p,otherActorWitness,authority,providerIssuer),
            "The other actor's consent and current membership must independently pass");
        R.Receipt memory r=admitted;r.subjectDigest=O.digest(p);
        bytes memory envelope=sign(r,1);
        (bool signatureValid,)=O.admission(p,key(1),envelope,block.timestamp);assertTrue(signatureValid);
        O.Admission memory request=O.Admission(p,otherActorWitness,key(1),key(2),envelope);
        vm.prank(agent);vm.expectRevert(IComposedSettlement.InvalidDeliveryProof.selector);
        settlement.admitObjectV3(id,0,request);
        assertEq(uint256(settlement.getObjectObligationV3(id,0).resolution),0);
        assertEq(settlement.objectGrantUsedV3(policy.objectGrantDigestV1(otherActorWitness.grant)),0);
        assertEq(bonds.getBond(provider).pendingSettlements,AMOUNT);
    }
    function test_readmissionMustAdvanceBeyondAcknowledgedEpochAndFence() public {
        bytes32 id=create(2);admit(id,0);
        (O.Fence memory f,bytes memory u,bytes memory a,bytes memory x)=absence();
        settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,u,a,x));
        bytes32 root=proposal.context.policyRoot;
        timelock.execute(address(policy),0,abi.encodeCall(policy.configure,(root,4,4,5,1000 ether,1 hours)),0,bytes32(uint256(400)));
        G.Proposal memory p=proposal;p.context.authorityEpoch=4;p.context.policyVersion=4;p.fencingToken=11;
        p.context.actionHash=G.actionHash(p);
        R.Receipt memory r=admitted;r.authorityEpoch=4;r.policyVersion=4;r.fencingToken=11;r.subjectDigest=O.digest(p);
        O.Admission memory request=O.Admission(p,witness,key(1),key(2),sign(r,1));
        vm.prank(agent);vm.expectRevert("Operation already reserved or completed");settlement.admitObjectV3(id,1,request);
        timelock.execute(address(policy),0,abi.encodeCall(policy.configure,(root,5,5,5,1000 ether,1 hours)),0,bytes32(uint256(500)));
        p.context.authorityEpoch=5;p.context.policyVersion=5;p.fencingToken=10;p.context.actionHash=G.actionHash(p);
        r.authorityEpoch=5;r.policyVersion=5;r.fencingToken=10;r.subjectDigest=O.digest(p);
        request=O.Admission(p,witness,key(1),key(2),sign(r,1));
        vm.prank(agent);vm.expectRevert("Operation already reserved or completed");settlement.admitObjectV3(id,1,request);
        p.fencingToken=11;p.context.actionHash=G.actionHash(p);r.fencingToken=11;r.subjectDigest=O.digest(p);
        p.costUnits=5;p.context.actionHash=G.actionHash(p);r.subjectDigest=O.digest(p);
        request=O.Admission(p,witness,key(1),key(2),sign(r,1));
        vm.prank(agent);vm.expectRevert("Logical work changed");settlement.admitObjectV3(id,1,request);
        p.costUnits=6;p.context.actionHash=G.actionHash(p);r.subjectDigest=O.digest(p);
        request=O.Admission(p,witness,key(1),key(2),sign(r,1));
        vm.prank(agent);settlement.admitObjectV3(id,1,request);
        assertEq(settlement.objectGrantUsedV3(policy.objectGrantDigestV1(witness.grant)),6);
        assertAttemptHistory(id);
    }
    function assertAttemptHistory(bytes32 id) internal view {
        ComposedSettlement.ObjectObligationV3 memory old=settlement.getObjectObligationV3(id,0);
        ComposedSettlement.ObjectObligationV3 memory next=settlement.getObjectObligationV3(id,1);
        assertEq(uint256(old.resolution),uint256(ComposedSettlement.ObjectResolutionV3.ABSENT));
        assertEq(old.previousAttempt,bytes32(0));assertTrue(old.attemptId!=0);
        assertEq(next.previousAttempt,old.attemptId);assertTrue(next.attemptId!=old.attemptId);
        assertEq(next.operationId,old.operationId);assertEq(next.costUnits,old.costUnits);
        (bytes32 storedId,uint256 storedIndex)=settlement.objectAttemptsV3(old.attemptId);
        assertEq(storedId,id);assertEq(storedIndex,0);
        (storedId,storedIndex)=settlement.objectAttemptsV3(next.attemptId);
        assertEq(storedId,id);assertEq(storedIndex,1);
    }
    function test_retryCannotLowerAcknowledgedPolicyVersion() public {
        assertRetryPolicyFloor(proposal.context.policyVersion+100,proposal.context.policyRoot,false);
    }
    function test_retryCannotRebindAcknowledgedRootAtSamePolicyVersion() public {
        assertRetryPolicyFloor(5,sha256("authority-acknowledged-other-policy-root"),false);
    }
    function test_retryAcceptsSameAcknowledgedPolicyVersionAndRoot() public {
        assertRetryPolicyFloor(5,proposal.context.policyRoot,true);
    }
    function assertRetryPolicyFloor(uint256 acknowledgedVersion,bytes32 acknowledgedRoot,bool allowed) internal {
        bytes32 id=create(2);admit(id,0);
        (O.Fence memory f,bytes memory u,bytes memory a,bytes memory x)=
            absencePolicy(acknowledgedVersion,acknowledgedRoot);
        settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,u,a,x));
        // This is an actual, already-scheduled monotonic governance action. Its
        // epoch advances beyond the ack, but its version is below (or at the
        // different root of) that signed ack. No mocked policy Boolean is used.
        bytes32 root=proposal.context.policyRoot;
        timelock.execute(address(policy),0,abi.encodeCall(policy.configure,
            (root,5,5,5,1000 ether,1 hours)),0,bytes32(uint256(500)));
        G.Proposal memory p=proposal;
        p.context.policyVersion=5;p.context.authorityEpoch=5;p.fencingToken=11;
        p.context.nonce=sha256("retry-policy-floor-nonce");p.context.actionHash=G.actionHash(p);
        assertTrue(policy.authorizesObjectV1(p,witness,witness.grant.authorityIssuer,
            witness.grant.providerIssuer),"Current governed membership must independently pass");
        R.Receipt memory r=admitted;
        r.policyVersion=5;r.authorityEpoch=5;r.fencingToken=11;r.subjectDigest=O.digest(p);
        O.Admission memory request=O.Admission(p,witness,key(1),key(2),sign(r,1));
        vm.prank(agent);if (!allowed) vm.expectRevert("Policy generation regressed");
        settlement.admitObjectV3(id,1,request);
        assertEq(uint256(settlement.getObjectObligationV3(id,1).resolution),
            uint256(allowed ? ComposedSettlement.ObjectResolutionV3.RESERVED : ComposedSettlement.ObjectResolutionV3.NONE));
    }
    function test_noncanonicalTrailingAdmissionBytesCannotReserveFunds() public {
        bytes32 id=create(1);
        bytes memory raw=abi.encodeCall(settlement.admitObjectV3,(id,0,O.Admission(proposal,witness,key(1),key(2),admission)));
        raw=abi.encodePacked(raw,hex"00");
        vm.prank(agent);(bool ok,)=address(settlement).call(raw);assertFalse(ok);
        assertEq(uint256(settlement.getObjectObligationV3(id,0).resolution),0);
        assertEq(settlement.objectGrantUsedV3(policy.objectGrantDigestV1(witness.grant)),0);
    }
    function test_historicalReceiptMustMatchOriginalContextKeysAndAdmissionTime() public {
        bytes32 id=create(1);admit(id,0);bytes memory receipt=completion(block.timestamp+1);
        vm.warp(block.timestamp+301);
        O.ResolutionContext memory c=resolution();c.admittedAt+=1;
        vm.expectRevert();settlement.resolveObjectCompletionV3(id,0,c,receipt);
        c=resolution();c.providerKey=key(1);
        vm.expectRevert();settlement.resolveObjectCompletionV3(id,0,c,receipt);
        c=resolution();c.proposal.context.policyVersion+=1;
        vm.expectRevert();settlement.resolveObjectCompletionV3(id,0,c,receipt);
        assertFalse(settlement.getEarnedDeliveryV3(id,0).accepted);
        refundExpired(id);assertEq(settlement.totalEscrowed(),AMOUNT);
    }
    function test_pendingPolicyGenerationChangeRejectsNewReservationButKeepsOldClaim() public {
        bytes32 id=create(2);admit(id,0);bytes memory receipt=completion(block.timestamp+1);
        timelock.execute(address(policy),0,abi.encodeCall(policy.configure,
            (proposal.context.policyRoot,4,4,5,1000 ether,1 hours)),0,bytes32(uint256(400)));
        vm.expectRevert();admit(id,1);
        vm.warp(block.timestamp+301);refundExpired(id);
        settlement.resolveObjectCompletionV3(id,0,resolution(),receipt);
        vm.prank(provider);vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id,0); vm.warp(block.timestamp - 72 hours);assertEq(settlement.totalEscrowed(),0);
    }
    function test_terminalAbsenceCannotLaterBecomeCompletionOrPayment() public {
        bytes32 id=create(1);admit(id,0);bytes memory receipt=completion(block.timestamp+1);
        (O.Fence memory f,bytes memory u,bytes memory a,bytes memory x)=absence();
        settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,u,a,x));
        vm.warp(block.timestamp+2);
        vm.expectRevert();settlement.resolveObjectCompletionV3(id,0,resolution(),receipt);
        vm.prank(provider);vm.expectRevert();vm.warp(block.timestamp + 72 hours); settlement.claimEarnedProviderShareV3(id,0); vm.warp(block.timestamp - 72 hours);
        refundAbsent(id);assertEq(settlement.totalEscrowed(),0);
    }
    function test_signedAbsenceCannotRegressOrRebindPolicyGeneration() public {
        bytes32 id=create(1);admit(id,0);
        (O.Fence memory f,bytes memory u,bytes memory a,bytes memory x)=
            absencePolicy(proposal.context.policyVersion-1,proposal.context.policyRoot);
        vm.expectRevert();settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,u,a,x));
        (f,u,a,x)=absencePolicy(proposal.context.policyVersion,sha256("different-policy-root"));
        vm.expectRevert();settlement.resolveObjectAbsenceV3(id,0,resolution(),O.AbsenceEvidence(f,u,a,x));
        assertEq(settlement.totalEscrowed(),AMOUNT);
        assertEq(uint256(settlement.getObjectObligationV3(id,0).resolution),
            uint256(ComposedSettlement.ObjectResolutionV3.RESERVED));
    }
}
