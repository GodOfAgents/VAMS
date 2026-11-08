// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {ActionContextV1 as A} from "../src/trust/ActionContextV1.sol";
import {GovernedObjectGrantV1 as G} from "../src/trust/GovernedObjectGrantV1.sol";
import {RestrictedTestnetPolicyV1 as Policy} from "../src/trust/RestrictedTestnetPolicyV1.sol";

/// @dev Independent Solidity producer. Captured full bytes are compared to the
///      Python fixture outside the VM. Invalid consent never proves eligibility.
contract ObjectPolicyCallTest is Test {
    function rep(uint8 v) internal pure returns(bytes32) {return bytes32(type(uint256).max/255*v);}

    function fixture(uint256 count,uint256 depth,bool maximum) internal pure returns(G.Proposal memory p,G.Witness memory w) {
        bytes32 authority=sha256(abi.encodePacked("VAMS:RECEIPT-KEY:secp256k1:v3",hex"00",
            hex"0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"));
        bytes32 provider=sha256(abi.encodePacked("VAMS:RECEIPT-KEY:secp256k1:v3",hex"00",
            hex"0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798b7c52588d95c3b9aa25b0403f1eef75702e84bb7597aabe663b82f6f04ef2777"));
        uint256 limit=maximum?uint256(uint64(type(int64).max)):10;
        G.Grant memory g;
        g.actorRoot=bytes32(uint256(uint160(address(0x1111111111111111111111111111111111111111))));
        g.providerId=rep(2);g.runtimeId=rep(3);g.workflowId=rep(6);g.intentId=rep(7);
        g.target=bytes32(uint256(uint160(address(0x2222222222222222222222222222222222222222))));
        g.authorityIssuer=authority;g.providerIssuer=provider;g.nonce=rep(195);
        g.budgetLimit=limit;g.maxActionCost=maximum?limit:4;g.maxScopeLifetime=600;
        g.validAfter=1000;g.validUntil=2000;g.resources=new bytes32[](count);
        for(uint256 i;i<count;++i)g.resources[i]=bytes32(i+1);
        bytes32 digest=G.digest(g,address(0x2222222222222222222222222222222222222222),80002,rep(5),rep(13));
        bytes32[] memory siblings=new bytes32[](depth);
        uint256 index=(uint256(1)<<depth)-1;
        bytes32 root=sha256(abi.encodePacked("VAMS:OBJECT-GRANT-LEAF:v1",hex"00",digest));
        for(uint256 i;i<depth;++i) {
            siblings[i]=rep(uint8(i+50));
            root=sha256(abi.encodePacked("VAMS:OBJECT-GRANT-NODE:v1",hex"00",siblings[i],root));
        }
        A.Context memory c;
        c.actorRoot=g.actorRoot;c.providerId=g.providerId;c.runtimeId=g.runtimeId;c.hostDomain=rep(5);
        c.workflowId=g.workflowId;c.intentId=g.intentId;c.actionHash=rep(8);c.inputHash=sha256("fixture-object");
        c.policyRoot=root;c.target=g.target;c.nonce=rep(12);c.budgetUnit=rep(13);
        c.rootScheme=1;c.authorityEpoch=3;c.policyVersion=7;c.capabilities=1;c.budget=limit;
        c.issuedAt=1000;c.expiresAt=1100;c.chainId=80002;
        uint256 fence=maximum?limit:9;
        p=G.Proposal(c,g.resources[0],maximum?limit:3,fence);
        p.context.actionHash=G.actionHash(p);
        // Public malformed actor signature: canonical shape does not grant rights.
        w=G.Witness(g,abi.encodePacked(bytes32(uint256(1)),bytes32(uint256(2)),uint8(27)),siblings,index);
    }
    function calls(uint256 count,uint256 depth,bool maximum,string memory name) internal {
        (G.Proposal memory p,G.Witness memory w)=fixture(count,depth,maximum);
        G.Scope memory s=G.Scope(p.context,w.grant.resources,w.grant.budgetLimit,w.grant.maxActionCost,p.fencingToken);
        bytes memory objectCall=abi.encodeCall(Policy.authorizesObjectV1,(p,w,w.grant.authorityIssuer,w.grant.providerIssuer));
        bytes memory scopeCall=abi.encodeCall(Policy.authorizesObjectScopeV1,(s,w,w.grant.authorityIssuer,w.grant.providerIssuer));
        assertEq(bytes4(objectCall),bytes4(hex"c76d3f1f"));
        assertEq(bytes4(scopeCall),bytes4(hex"c6a79e78"));
        bytes32 digest=G.digest(w.grant,address(0x2222222222222222222222222222222222222222),80002,rep(5),rep(13));
        assertFalse(G.consented(w.grant,digest,w.consent),"Dummy consent must not authorize");
        emit log_named_bytes(string.concat("object_",name),objectCall);
        emit log_named_bytes(string.concat("scope_",name),scopeCall);
        emit log_named_bytes32(string.concat("context_",name),A.digest(p.context));
        emit log_named_bytes32(string.concat("scope_digest_",name),G.scopeDigest(s));
        emit log_named_bytes32(string.concat("grant_",name),digest);
    }
    function test_minimumDynamicArrays() public {calls(1,0,false,"min");}
    function test_nestedDynamicArraysAndConsentPadding() public {calls(2,1,false,"nested");}
    function test_maximumResourcesDepthAndBoundedIntegers() public {calls(64,32,true,"max");}
}
