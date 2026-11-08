// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {ActionContextV1} from "../src/trust/ActionContextV1.sol";
import {GovernedObjectGrantV1 as G} from "../src/trust/GovernedObjectGrantV1.sol";
import {RestrictedTestnetPolicyV1} from "../src/trust/RestrictedTestnetPolicyV1.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";

interface IActorGrantRevocationV1 {
    function revokeObjectGrantV1(G.Grant calldata grant) external;
}

/// @dev Actual native grant/consent/governance algorithms with public VM fixtures.
///      No host reader, external effect, actual custody or finality qualification.
contract ObjectGrantPolicyTest is Test {
    RestrictedTestnetPolicyV1 internal policy;
    VAMSTimelockController internal timelock;
    G.Witness internal witness;
    G.Proposal internal proposal;
    uint256 internal actorKey;
    bytes32 internal root;
    bytes internal pendingUpdate;
    bytes32 internal constant UPDATE_SALT=keccak256("fixture-policy-generation-update");
    bytes32 internal constant ROUTE_SALT=keccak256("fixture-route-disable");
    bytes32 internal constant AUTHORITY=keccak256("fixture-public-authority-issuer-id");
    bytes32 internal constant PROVIDER=keccak256("fixture-public-provider-issuer-id");
    uint256 internal nonce;

    function rep(uint8 value) internal pure returns(bytes32) {return bytes32((type(uint256).max/255)*value);}
    function contextFixture() internal pure returns(ActionContextV1.Context memory c) {
        c.actorRoot=bytes32(uint256(uint160(address(0x1111111111111111111111111111111111111111))));
        c.providerId=rep(2);c.runtimeId=rep(3);c.hostDomain=rep(5);c.workflowId=rep(6);c.intentId=rep(7);
        c.actionHash=rep(8);c.inputHash=sha256("fixture-object");c.policyRoot=rep(10);
        c.target=bytes32(uint256(uint160(address(0x2222222222222222222222222222222222222222))));
        c.nonce=rep(12);c.budgetUnit=rep(13);c.rootScheme=1;c.authorityEpoch=3;c.policyVersion=7;
        c.capabilities=1;c.budget=10;c.issuedAt=1000;c.expiresAt=1100;c.chainId=80002;
    }
    function consent(bytes32 digest,uint256 key) internal pure returns(bytes memory) {
        (uint8 v,bytes32 r,bytes32 s)=vm.sign(key,digest);return abi.encodePacked(r,s,v);
    }
    function govern(bytes memory data) internal {
        bytes32 salt=bytes32(++nonce);
        timelock.schedule(address(policy),0,data,bytes32(0),salt,48 hours);
        vm.warp(block.timestamp+48 hours);
        timelock.execute(address(policy),0,data,bytes32(0),salt);
    }
    function setUp() public {
        vm.chainId(80002);
        address[] memory members=new address[](1);members[0]=address(this);
        timelock=new VAMSTimelockController(48 hours,members,members,address(this));
        policy=new RestrictedTestnetPolicyV1(address(timelock),rep(5),rep(13));
        actorKey=uint256(keccak256("LOCAL-ONLY-OBJECT-GRANT-CONSENT-FIXTURE"));
        ActionContextV1.Context memory c=contextFixture();c.actorRoot=bytes32(uint256(uint160(vm.addr(actorKey))));
        G.Grant memory g;
        g.actorRoot=c.actorRoot;g.providerId=c.providerId;g.runtimeId=c.runtimeId;g.workflowId=c.workflowId;
        g.intentId=c.intentId;g.target=c.target;g.authorityIssuer=AUTHORITY;g.providerIssuer=PROVIDER;g.nonce=rep(195);
        g.budgetLimit=10;g.maxActionCost=4;g.maxScopeLifetime=600;
        g.validAfter=block.timestamp+96 hours;g.validUntil=g.validAfter+24 hours;
        g.resources=new bytes32[](2);g.resources[0]=rep(114);g.resources[1]=rep(115);
        bytes32 digest=policy.objectGrantDigestV1(g);
        root=sha256(abi.encodePacked("VAMS:OBJECT-GRANT-LEAF:v1",hex"00",digest));
        witness=G.Witness(g,consent(digest,actorKey),new bytes32[](0),0);
        govern(abi.encodeCall(policy.configure,(root,1,1,1,100,600)));
        // Prepare edits before the grant's window opens, so update tests keep the
        // old approval unexpired when normal48h governance becomes executable.
        pendingUpdate=abi.encodeCall(policy.configure,(root,3,3,1,100,600));
        timelock.schedule(address(policy),0,pendingUpdate,bytes32(0),UPDATE_SALT,48 hours);
        timelock.schedule(address(policy),0,abi.encodeCall(policy.setEligibility,
            (ActionContextV1.workloadHash(c),c.providerId,c.target,false)),bytes32(0),ROUTE_SALT,48 hours);
        govern(abi.encodeCall(policy.setEligibility,(ActionContextV1.workloadHash(c),c.providerId,c.target,true)));
        c.policyRoot=root;c.policyVersion=policy.policyVersion();c.authorityEpoch=policy.authorityEpoch();
        c.issuedAt=block.timestamp;c.expiresAt=block.timestamp+100;
        G.Proposal memory p=G.Proposal(c,rep(114),3,9);p.context.actionHash=G.actionHash(p);proposal=p;
    }
    function allowed(G.Proposal memory p,G.Witness memory w) internal view returns(bool) {
        return policy.authorizesObjectV1(p,w,AUTHORITY,PROVIDER);
    }
    function scope() internal view returns(G.Scope memory s) {
        s=G.Scope(proposal.context,witness.grant.resources,10,4,9);
    }
    function scopeAllowed(G.Scope memory s) internal view returns(bool) {
        return policy.authorizesObjectScopeV1(s,witness,AUTHORITY,PROVIDER);
    }
    function test_exactActorConsentGovernedRootActionAndScopePass() public view {
        assertTrue(allowed(proposal,witness));assertTrue(scopeAllowed(scope()));
    }
    function test_actorCanPermanentlyRevokeItsOwnUnexpiredConsent() public {
        assertTrue(allowed(proposal,witness));
        G.Grant memory g=witness.grant;
        vm.prank(address(uint160(uint256(g.actorRoot))));
        (bool ok,)=address(policy).call(abi.encodeCall(IActorGrantRevocationV1.revokeObjectGrantV1,(g)));
        assertTrue(ok,"Owner revoke-only consent path is required");
        assertFalse(allowed(proposal,witness));assertFalse(scopeAllowed(scope()));
    }
    function test_onlyRootActorCanRevokeConsent() public {
        G.Grant memory g=witness.grant;
        vm.prank(vm.addr(actorKey+1));vm.expectRevert("Actor only");policy.revokeObjectGrantV1(g);
        assertTrue(allowed(proposal,witness));
    }
    function test_revocationIsIdempotentAndGovernanceCannotRestoreSameConsent() public {
        G.Grant memory g=witness.grant;address actor=address(uint160(uint256(g.actorRoot)));
        uint256 version=policy.policyVersion();uint256 epoch=policy.authorityEpoch();
        vm.prank(actor);policy.revokeObjectGrantV1(g);vm.prank(actor);policy.revokeObjectGrantV1(g);
        assertEq(policy.policyVersion(),version);assertEq(policy.authorityEpoch(),epoch);
        assertTrue(policy.revokedObjectGrants(policy.objectGrantDigestV1(g)));
        timelock.execute(address(policy),0,pendingUpdate,bytes32(0),UPDATE_SALT);
        G.Proposal memory p=proposal;p.context.policyVersion=policy.policyVersion();p.context.authorityEpoch=policy.authorityEpoch();
        assertFalse(allowed(p,witness));
    }
    function test_otherActorRevokingUncommittedGrantCannotInvalidateThisActor() public {
        G.Grant memory g=witness.grant;address other=vm.addr(actorKey+1);g.actorRoot=bytes32(uint256(uint160(other)));
        uint256 version=policy.policyVersion();uint256 epoch=policy.authorityEpoch();
        vm.prank(other);policy.revokeObjectGrantV1(g);
        assertEq(policy.policyVersion(),version);assertEq(policy.authorityEpoch(),epoch);
        assertTrue(allowed(proposal,witness));
    }
    function test_unboundGenericRuntimeAndSigningRoutesReject() public view {
        ActionContextV1.Context memory c=proposal.context;assertFalse(policy.authorizes(c));
        c.capabilities=2;assertFalse(policy.authorizes(c));c.capabilities=5;assertFalse(policy.authorizes(c));
    }
    function test_missingOrWrongActorConsentRejectsDespiteMembership() public {
        G.Witness memory w=witness;w.consent=hex"";assertFalse(allowed(proposal,w));
        w.consent=consent(policy.objectGrantDigestV1(w.grant),actorKey+1);assertFalse(allowed(proposal,w));
    }
    function test_malformedHighSAndInvalidVConsentReject() public view {
        G.Witness memory w=witness;w.consent=hex"01";assertFalse(allowed(proposal,w));
        w=witness;w.consent[64]=bytes1(uint8(0));assertFalse(allowed(proposal,w));
        w=witness;bytes32 r;bytes32 s;uint8 v;
        bytes memory signature=w.consent;
        assembly("memory-safe") {r:=mload(add(signature,32)) s:=mload(add(signature,64)) v:=byte(0,mload(add(signature,96)))}
        uint256 order=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
        w.consent=abi.encodePacked(r,bytes32(order-uint256(s)),uint8(v==27?28:27));
        assertFalse(allowed(proposal,w));
    }
    function test_wrongMembershipIndexSiblingAndUnboundedProofReject() public view {
        G.Witness memory w=witness;w.index=1;assertFalse(allowed(proposal,w));
        w=witness;w.siblings=new bytes32[](1);w.siblings[0]=rep(212);assertFalse(allowed(proposal,w));
        w.siblings=new bytes32[](33);assertFalse(allowed(proposal,w));
    }
    function test_actorConsentCannotWidenGovernedBudgetWithoutNewRoot() public {
        G.Witness memory w=witness;w.grant.budgetLimit=20;
        w.consent=consent(policy.objectGrantDigestV1(w.grant),actorKey);
        assertFalse(allowed(proposal,w));
    }
    function test_expectedRuntimeIssuerRolesCannotSwapOrInventAuthority() public view {
        assertFalse(policy.authorizesObjectV1(proposal,witness,PROVIDER,AUTHORITY));
        assertFalse(policy.authorizesObjectV1(proposal,witness,AUTHORITY,AUTHORITY));
        assertFalse(policy.authorizesObjectScopeV1(scope(),witness,rep(99),PROVIDER));
    }
    function test_contextActorProviderRuntimeWorkflowIntentAndTargetAreExact() public view {
        for(uint256 i;i<6;++i) {
            G.Proposal memory p=proposal;
            if(i==0)p.context.actorRoot=bytes32(uint256(uint160(address(0xBAD))));
            if(i==1)p.context.providerId=rep(99);if(i==2)p.context.runtimeId=rep(99);
            if(i==3)p.context.workflowId=rep(99);if(i==4)p.context.intentId=rep(99);if(i==5)p.context.target=rep(99);
            p.context.actionHash=G.actionHash(p);assertFalse(allowed(p,witness));
        }
    }
    function test_wrongChainHostUnitsRootVersionAndEpochReject() public view {
        for(uint256 i;i<6;++i) {
            G.Proposal memory p=proposal;
            if(i==0)p.context.chainId=1;if(i==1)p.context.hostDomain=rep(99);
            if(i==2)p.context.budgetUnit=rep(99);if(i==3)p.context.policyRoot=rep(99);
            if(i==4)p.context.policyVersion++;if(i==5)p.context.authorityEpoch++;
            assertFalse(allowed(p,witness));
        }
    }
    function test_modelAndCardanoSchemeRemainUnsupportedHere() public view {
        G.Proposal memory p=proposal;p.context.modelId=rep(99);assertFalse(allowed(p,witness));
        p=proposal;p.context.rootScheme=2;assertFalse(allowed(p,witness));
    }
    function test_actualActionHashBindsResourceCostFenceAndInput() public view {
        G.Proposal memory p=proposal;p.resourceId=rep(115);assertFalse(allowed(p,witness));
        p.context.actionHash=G.actionHash(p);assertTrue(allowed(p,witness));
        p=proposal;p.costUnits=4;assertFalse(allowed(p,witness));
        p.context.actionHash=G.actionHash(p);assertTrue(allowed(p,witness));
        p=proposal;p.fencingToken++;assertFalse(allowed(p,witness));
        p=proposal;p.context.inputHash=rep(99);p.context.actionHash=G.actionHash(p);assertFalse(allowed(p,witness));
    }
    function test_zeroCostIsAllowedButCostAboveCeilingRejects() public view {
        G.Proposal memory p=proposal;p.costUnits=0;p.context.actionHash=G.actionHash(p);assertTrue(allowed(p,witness));
        p.costUnits=5;p.context.actionHash=G.actionHash(p);assertFalse(allowed(p,witness));
    }
    function test_zeroAndOverflowFencingTokensReject() public view {
        G.Proposal memory p=proposal;p.fencingToken=0;p.context.actionHash=G.actionHash(p);assertFalse(allowed(p,witness));
        p.fencingToken=uint256(uint64(type(int64).max))+1;p.context.actionHash=G.actionHash(p);assertFalse(allowed(p,witness));
    }
    function test_scopeResourceSubsetIsBoundedSortedUniqueAndExact() public view {
        G.Scope memory s=scope();s.resources=new bytes32[](1);s.resources[0]=rep(115);assertTrue(scopeAllowed(s));
        s.resources[0]=rep(116);assertFalse(scopeAllowed(s));s.resources=new bytes32[](0);assertFalse(scopeAllowed(s));
        s=scope();s.resources[1]=s.resources[0];assertFalse(scopeAllowed(s));
        s=scope();s.resources[0]=rep(115);s.resources[1]=rep(114);assertFalse(scopeAllowed(s));
    }
    function test_scopeCannotWidenBudgetCostOrFence() public view {
        G.Scope memory s=scope();s.budgetLimit=11;assertFalse(scopeAllowed(s));
        s=scope();s.maxActionCost=5;assertFalse(scopeAllowed(s));
        s=scope();s.fencingToken=0;assertFalse(scopeAllowed(s));
    }
    function test_expiredFutureOrOverlongContextRejects() public {
        G.Proposal memory p=proposal;p.context.issuedAt=block.timestamp+1;assertFalse(allowed(p,witness));
        p=proposal;p.context.expiresAt=p.context.issuedAt+601;assertFalse(allowed(p,witness));
        vm.warp(proposal.context.expiresAt);assertFalse(allowed(proposal,witness));
    }
    function test_unexpiredPendingContextRevokesAndRequiresCurrentGeneration() public {
        assertTrue(allowed(proposal,witness));
        timelock.execute(address(policy),0,pendingUpdate,bytes32(0),UPDATE_SALT);
        assertLt(block.timestamp,proposal.context.expiresAt);assertFalse(allowed(proposal,witness));
        G.Proposal memory p=proposal;p.context.policyVersion=policy.policyVersion();p.context.authorityEpoch=policy.authorityEpoch();
        assertTrue(allowed(p,witness)); // Eligibility only; no duplicate dispatch/operation is authorized by a view.
    }
    function test_routeRevocationDeniesEvenAfterGenerationRefresh() public {
        ActionContextV1.Context memory c=proposal.context;
        timelock.execute(address(policy),0,abi.encodeCall(policy.setEligibility,
            (ActionContextV1.workloadHash(c),c.providerId,c.target,false)),bytes32(0),ROUTE_SALT);
        G.Proposal memory p=proposal;p.context.policyVersion=policy.policyVersion();p.context.authorityEpoch=policy.authorityEpoch();
        assertFalse(allowed(p,witness));
    }
    function test_delegatedIssuerCannotConfigureItsOwnRoot() public {
        vm.expectRevert("Governance only");policy.configure(root,3,3,1,100,600);
    }
    function test_newRootCannotBypassFortyEightHourDelay() public {
        bytes memory data=abi.encodeCall(policy.configure,(root,4,4,1,100,600));bytes32 salt=keccak256("not-ready");
        timelock.schedule(address(policy),0,data,bytes32(0),salt,48 hours);
        vm.expectRevert();timelock.execute(address(policy),0,data,bytes32(0),salt);
        assertTrue(allowed(proposal,witness));
    }
    function test_grantConsentDigestBindsContractChainHostAndUnits() public view {
        G.Grant memory g=witness.grant;
        bytes32 digest=G.digest(g,address(policy),80002,rep(5),rep(13));
        assertTrue(G.consented(g,digest,witness.consent));
        assertFalse(G.consented(g,G.digest(g,address(0xBAD),80002,rep(5),rep(13)),witness.consent));
        assertFalse(G.consented(g,G.digest(g,address(policy),80003,rep(5),rep(13)),witness.consent));
        assertFalse(G.consented(g,G.digest(g,address(policy),80002,rep(99),rep(13)),witness.consent));
        assertFalse(G.consented(g,G.digest(g,address(policy),80002,rep(5),rep(99)),witness.consent));
    }
    function test_invalidGrantStructureFailsClosed() public view {
        G.Witness memory w=witness;w.grant.providerIssuer=AUTHORITY;assertFalse(allowed(proposal,w));
        w=witness;w.grant.validUntil=w.grant.validAfter+24 hours+1;assertFalse(allowed(proposal,w));
        w=witness;w.grant.resources[1]=w.grant.resources[0];assertFalse(allowed(proposal,w));
        w=witness;w.grant.budgetLimit=type(uint256).max;assertFalse(allowed(proposal,w));
    }
    function testFuzz_contextBudgetCannotExceedActorCeiling(uint64 value) public view {
        G.Proposal memory p=proposal;p.context.budget=bound(value,11,uint256(uint64(type(int64).max)));
        assertFalse(allowed(p,witness));
    }
    function test_pythonGrantAndPositionedMerkleGolden() public pure {
        G.Grant memory g;
        g.actorRoot=bytes32(uint256(uint160(address(0x1111111111111111111111111111111111111111))));
        g.providerId=rep(2);g.runtimeId=rep(3);g.workflowId=rep(6);g.intentId=rep(7);
        g.target=bytes32(uint256(uint160(address(0x2222222222222222222222222222222222222222))));
        g.authorityIssuer=rep(161);g.providerIssuer=rep(178);g.nonce=rep(195);
        g.budgetLimit=10;g.maxActionCost=4;g.maxScopeLifetime=600;g.validAfter=1000;g.validUntil=2000;
        g.resources=new bytes32[](2);g.resources[0]=rep(114);g.resources[1]=rep(115);
        bytes32 digest=G.digest(g,address(0x2222222222222222222222222222222222222222),80002,rep(5),rep(13));
        assertEq(digest,0x7460a446c01284adf2b64280d57a49bf968dad3682bebfa7d3a305f79e82ab3f);
        bytes32[] memory siblings=new bytes32[](1);siblings[0]=rep(212);
        assertTrue(G.member(digest,0x0f6d51fee97b3dee24b23ff1ba081c625ef16aa381617491409bb5709ad9f2be,siblings,0));
        assertTrue(G.member(digest,0x4fdc81f69338047c17e64ec6751268d4fb43e17e656499f59726a1a06ff607ed,siblings,1));
        assertFalse(G.member(digest,0x0f6d51fee97b3dee24b23ff1ba081c625ef16aa381617491409bb5709ad9f2be,siblings,1));
    }
    function test_pythonExistingScopeV3GoldenEncodingIsPreserved() public pure {
        ActionContextV1.Context memory c=contextFixture();
        G.Proposal memory p=G.Proposal(c,rep(114),3,9);p.context.actionHash=G.actionHash(p);
        bytes32[] memory resources=new bytes32[](2);resources[0]=rep(114);resources[1]=rep(115);
        assertEq(G.scopeDigest(G.Scope(p.context,resources,10,4,9)),
            0xd6c72ed2bb008b6b9d4e6e7e5cfd023885d81b4548845f035a529c2386074bea);
    }
}
