// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {HeartbeatPrincipalV1 as P} from "../src/trust/HeartbeatPrincipalV1.sol";

contract HeartbeatPrincipalCodecHarness {
    function encode(P.Record memory r) external pure returns (bytes memory) { return P.canonicalBytes(r); }
    function decode(bytes calldata raw) external pure returns (bool,P.Record memory) { return P.tryDecodeCalldata(raw); }
}

/// @dev Local unsigned synthetic data tests, not enrollment or proof verification.
contract HeartbeatPrincipalV1Test is Test {
    function golden() internal pure returns (bytes memory) { return hex"56414d533a474154455741593a4845415254424541542d5052494e434950414c3a76310000120100205d3ece6d8181af33a7e09b213d73e8fce828f1fc2ea2a4291b89a1699a02e91802002079121d7d912632aaf935e2b08d31942fa6c2242e3d17dd751612188321f6d26d0300886469643a6b65793a3131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131040040111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111110500200303030303030303030303030303030303030303030303030303030303030303060040040404040404040404040404040404040404040404040404040404040404040404040404040404040404040404040404040404040404040404040404040404040700200505050505050505050505050505050505050505050505050505050505050505080020060606060606060606060606060606060606060606060606060606060606060609000f676174657761792e746573746e65740a0004504f53540b000a2f6865617274626561740c00000d002007070707070707070707070707070707070707070707070707070707070707070e000800000000000000030f0008000000000000000b1000080000000000000002110008000000006553f100120008000000006553f22c"; }
    function sample() internal pure returns (P.Record memory r) {
        bool ok; (ok,r)=P.tryDecode(golden()); require(ok,"Golden must decode");
    }
    function rejects(bytes memory raw) internal pure {
        (bool ok,P.Record memory r)=P.tryDecode(raw);
        assertFalse(ok); assertEq(r.principalId,bytes32(0)); assertEq(r.m2SignerPublicKey.length,0);
    }
    // Independent frame rewriting. No candidate encode/decode constructs mutations.
    function field(bytes memory raw,uint256 index,bytes memory replacement) internal pure returns (bytes memory out) {
        uint256 prefix=bytes("VAMS:GATEWAY:HEARTBEAT-PRINCIPAL:v1").length+3;
        out=new bytes(prefix); for(uint256 j;j<prefix;++j)out[j]=raw[j];
        uint256 at=prefix;
        for(uint256 i;i<18;++i){
            uint256 len=uint256(uint8(raw[at+1]))*256+uint8(raw[at+2]);at+=3;
            bytes memory value;
            if(i==index)value=replacement;
            else {value=new bytes(len);for(uint256 j;j<len;++j)value[j]=raw[at+j];}
            out=bytes.concat(out,bytes1(uint8(i+1)),bytes2(uint16(value.length)),value);at+=len;
        }
    }
    function test_independentPythonGoldenExactBytesAndDigest() public pure {
        P.Record memory r=sample();assertTrue(P.valid(r));
        assertEq(P.canonicalBytes(r),golden());assertEq(golden().length,617);
        assertEq(P.digest(r),0xbd695fde4585901bcbc2870cb07d2e0bafd597643d06556905f891129c097a3c);
        assertEq(r.principalId,0x5d3ece6d8181af33a7e09b213d73e8fce828f1fc2ea2a4291b89a1699a02e918);
        assertEq(r.nodeIdCommitment,0x79121d7d912632aaf935e2b08d31942fa6c2242e3d17dd751612188321f6d26d);
        assertEq(r.policyVersion,3);assertEq(r.authorityEpoch,11);assertEq(r.principalGeneration,2);
        assertEq(r.notBefore,1700000000);assertEq(r.expiresAt,1700000300);
    }
    function test_variableAudienceLengthsMatchIndependentReferences() public pure {
        P.Record memory r=sample();r.audience="g";
        assertEq(P.digest(r),0x98788082fa394b9c5f3102d16f7401dc03785f1b19e2cb3ce93736a2ca99b5c8);assertEq(P.canonicalBytes(r).length,603);
        bytes memory longName=new bytes(128);for(uint256 i;i<128;++i)longName[i]="a";
        r.audience=string(longName);assertEq(P.digest(r),0xad68f1401eb1a4bdb84eb86c43f1218c0e72064b2fed8f10c765fbe07428e663);
        assertEq(P.canonicalBytes(r).length,730);
        (bool ok,)=P.tryDecode(P.canonicalBytes(r));assertTrue(ok);
    }
    function test_everyTruncationRejectsWithZeroRecord() public pure {
        bytes memory raw=golden();
        for(uint256 len;len<raw.length;++len){
            bytes memory shortRaw=new bytes(len);for(uint256 i;i<len;++i)shortRaw[i]=raw[i];rejects(shortRaw);
        }
    }
    function test_wrongDomainCountOrderLengthAndTrailingReject() public pure {
        bytes memory raw=golden();raw[0]^=0x01;rejects(raw);
        raw=golden();uint256 start=bytes("VAMS:GATEWAY:HEARTBEAT-PRINCIPAL:v1").length+1;
        raw[start]=0x01;rejects(raw);raw=golden();raw[start+1]=0x11;rejects(raw);
        raw=golden();raw[start+2]=0x02;rejects(raw);
        raw=golden();raw[start+3]=0x01;raw[start+4]=0x01;rejects(raw);
        rejects(bytes.concat(golden(),hex"00"));rejects(new bytes(1025));
    }
    function test_eachFieldRejectsNoncanonicalWidth() public pure {
        uint256[18] memory lengths=[uint256(31),31,135,63,31,63,31,31,0,3,9,1,31,7,7,7,7,7];
        for(uint256 i;i<18;++i)rejects(field(golden(),i,new bytes(lengths[i])));
        for(uint256 i=13;i<18;++i)rejects(field(golden(),i,new bytes(9)));
        rejects(field(golden(),8,new bytes(129)));
        rejects(field(golden(),0,new bytes(257)));
    }
    function test_zeroIdentityAndReboundScopeReject() public pure {
        uint256[6] memory ids=[uint256(0),1,4,6,7,12];
        for(uint256 i;i<ids.length;++i)rejects(field(golden(),ids[i],new bytes(32)));
        rejects(field(golden(),0,abi.encodePacked(bytes32(uint256(1)))));
        rejects(field(golden(),6,abi.encodePacked(bytes32(uint256(2)))));
        rejects(field(golden(),7,abi.encodePacked(bytes32(uint256(3)))));
    }
    function test_didMustMatchLowercaseExactKeyBytes() public pure {
        P.Record memory r=sample();r.m2SignerPublicKey[0]=0xab;
        bytes memory did=bytes(r.m2SignerDid);did[8]="a";did[9]="b";r.m2SignerDid=string(did);
        assertTrue(P.valid(r));did[8]="A";r.m2SignerDid=string(did);assertFalse(P.valid(r));
        did[8]=0x80;r.m2SignerDid=string(did);assertFalse(P.valid(r));
        r=sample();did=bytes(r.m2SignerDid);did[0]="D";r.m2SignerDid=string(did);assertFalse(P.valid(r));
        rejects(field(golden(),3,new bytes(64)));
    }
    function test_audienceSyntaxParity() public pure {
        string[10] memory bad=[string(""),"A","a_1",".a","a.","-a","a-","a/b","a b",unicode"caf\u00e9"];
        for(uint256 i;i<bad.length;++i)rejects(field(golden(),8,bytes(bad[i])));
        string[5] memory good=[string("a"),"0","a..b","a--b","a.-0"];
        for(uint256 i;i<good.length;++i){(bool ok,)=P.tryDecode(field(golden(),8,bytes(good[i])));assertTrue(ok);}
    }
    function test_integerPositiveFieldsAndIntervalBoundaries() public pure {
        for(uint256 i=13;i<16;++i)rejects(field(golden(),i,new bytes(8)));
        P.Record memory r=sample();r.notBefore=0;r.expiresAt=1;assertTrue(P.valid(r));
        r.notBefore=type(uint64).max-1;r.expiresAt=type(uint64).max;
        r.policyVersion=type(uint64).max;r.authorityEpoch=type(uint64).max;r.principalGeneration=type(uint64).max;
        (bool ok,P.Record memory decoded)=P.tryDecode(P.canonicalBytes(r));assertTrue(ok);
        assertEq(decoded.expiresAt,type(uint64).max);assertEq(decoded.policyVersion,type(uint64).max);
        r.expiresAt=r.notBefore;assertFalse(P.valid(r));r.expiresAt=0;assertFalse(P.valid(r));
    }
    function test_routeScopeIsFixedWithoutQuery() public pure {
        rejects(field(golden(),9,bytes("post")));rejects(field(golden(),10,bytes("/Heartbeat")));
        rejects(field(golden(),11,bytes("x")));rejects(field(golden(),9,bytes("GET")));
        rejects(field(golden(),10,bytes("/heartbeat/")));
    }
    function test_keysHaveShapeOnlyAndCreateNoOwnershipProof() public pure {
        P.Record memory r=sample();r.m2SignerPublicKey=new bytes(64);r.bodyPublicKey=new bytes(64);
        bytes memory did=bytes(r.m2SignerDid);for(uint256 i=8;i<did.length;++i)did[i]="0";
        r.m2SignerDid=string(did);assertTrue(P.valid(r));
        (bool ok,)=P.tryDecode(P.canonicalBytes(r));assertTrue(ok);
    }
    function test_scopeIdStableAcrossKeyPolicyAndGenerationRotation() public pure {
        P.Record memory r=sample();bytes32 id=r.principalId;bytes32 first=P.digest(r);
        r.bodyPublicKey[0]^=0x01;r.certificateFingerprint=bytes32(uint256(5));
        r.policyVersion++;r.authorityEpoch++;r.principalGeneration++;
        assertEq(r.principalId,id);assertTrue(P.valid(r));assertTrue(P.digest(r)!=first);
        assertTrue(P.principalIdFor(r.hostDomain,bytes32(uint256(9)),r.nodeIdCommitment)!=id);
    }
    function test_invalidTypedEncodeReverts() public {
        HeartbeatPrincipalCodecHarness h=new HeartbeatPrincipalCodecHarness();P.Record memory r=sample();
        r.method="GET";vm.expectRevert("Invalid heartbeat principal");h.encode(r);
    }
    function test_calldataIngressBoundsBeforeMemoryDecoder() public {
        HeartbeatPrincipalCodecHarness h=new HeartbeatPrincipalCodecHarness();
        (bool ok,P.Record memory r)=h.decode(golden());assertTrue(ok);assertEq(P.canonicalBytes(r),golden());
        bytes memory boundary=new bytes(1024);bytes memory raw=golden();
        for(uint256 i;i<raw.length;++i)boundary[i]=raw[i];
        (ok,r)=h.decode(boundary);assertFalse(ok);assertEq(r.principalId,bytes32(0));
        (ok,r)=h.decode(new bytes(1025));assertFalse(ok);assertEq(r.principalId,bytes32(0));
        (ok,r)=h.decode(new bytes(65536));assertFalse(ok);assertEq(r.m2SignerPublicKey.length,0);
    }
    function testFuzz_decoderNeverAcceptsNoncanonicalBytes(bytes memory raw) public pure {
        vm.assume(raw.length<=1100);
        (bool ok,P.Record memory r)=P.tryDecode(raw);
        if(ok)assertEq(P.canonicalBytes(r),raw);
        else {assertEq(r.principalId,bytes32(0));assertEq(r.m2SignerPublicKey.length,0);}
    }
    function testFuzz_validUint64AndAudienceRoundTrip(uint64 epoch,uint64 generation,uint64 start,uint8 span) public pure {
        vm.assume(epoch>0 && generation>0 && start<type(uint64).max-256);
        P.Record memory r=sample();r.authorityEpoch=epoch;r.principalGeneration=generation;
        r.notBefore=start;r.expiresAt=start+uint64(span)+1;
        (bool ok,P.Record memory decoded)=P.tryDecode(P.canonicalBytes(r));assertTrue(ok);
        assertEq(decoded.authorityEpoch,epoch);assertEq(decoded.principalGeneration,generation);
        assertEq(decoded.notBefore,start);assertEq(decoded.expiresAt,r.expiresAt);
    }
}
