// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {ActionContextV1 as A} from "../src/trust/ActionContextV1.sol";
import {AutomataSgxActionVerifierV1 as SGX,DcapHeaderV1} from "../src/trust/AutomataSgxActionVerifierV1.sol";
import {ActionDeliveryVerifierV1} from "../src/trust/ActionDeliveryVerifierV1.sol";
import {RestrictedTestnetPolicyV1 as Policy} from "../src/trust/RestrictedTestnetPolicyV1.sol";
import {VAMSTimelockController as Timelock} from "../src/governance/VAMSTimelockController.sol";
import {IComposedDeliveryVerifier as Delivery} from "../src/economic/IComposedDeliveryVerifier.sol";

// Deliberately non-authentic verifier/collateral responses, public VM signatures.
// No certificates, TCB freshness, hardware, actual custody or live qualification.
contract DcapCollateral38 {}
contract DcapUnusedRoute38 {
    function verifyAction(A.Context calldata,bytes32,bytes calldata) external pure returns(bool){return false;}
}
contract DcapMetadata38 {
    address internal router;
    uint16 internal version=3;
    uint8 internal versionMode;
    uint8 internal routerMode;
    bytes internal report;
    constructor(address value){router=value;}
    function setMetadata(address value,uint16 v,uint8 vm_,uint8 rm_) external {
        router=value;version=v;versionMode=vm_;routerMode=rm_;
    }
    function setReport(bytes memory value) external {report=value;}
    function response(uint8 mode,uint256 value) private pure {
        if(mode==1)revert("Controlled getter unavailable");
        if(mode==0)return;
        // Return deliberately invalid ABI directly from the external getter.
        assembly ("memory-safe") {
            let p:=mload(0x40)
            mstore(0x40,add(p,4096))
            mstore(p,value)
            switch mode
            case 2 {return(p,0)}
            case 3 {return(p,31)}
            case 4 {mstore(add(p,32),0) return(p,64)}
            case 5 {mstore(p,or(value,shl(255,1))) return(p,32)}
            case 6 {return(p,4096)}
        }
    }
    function quoteVersion() external view returns(uint16){response(versionMode,version);return version;}
    function pccsRouter() external view returns(address){response(routerMode,uint160(router));return router;}
    function verifyQuote(DcapHeaderV1 calldata,bytes calldata,uint32) external view returns(bool,bytes memory){return(true,report);}
}

contract DcapBackendBindingTest is Test {
    DcapMetadata38 internal backend;
    DcapCollateral38 internal collateral;
    SGX internal adapter;
    A.Context internal c;
    uint256 internal actor;
    bytes32 internal outputHash=sha256("public-binding-fixture-output");
    bytes32 internal constant ENCLAVE=keccak256("PUBLIC-BINDING-FIXTURE-ENCLAVE");
    bytes32 internal constant SIGNER=keccak256("PUBLIC-BINDING-FIXTURE-SIGNER");
    function setUp() public {
        vm.warp(1000);vm.chainId(80002);
        actor=uint256(keccak256("PUBLIC-VM-ONLY-DCAP-BINDING-38"));
        c.actorRoot=bytes32(uint256(uint160(vm.addr(actor))));c.providerId=c.actorRoot;
        c.runtimeId=keccak256("runtime");c.hostDomain=keccak256("host");c.workflowId=keccak256("workflow");
        c.intentId=keccak256("intent");c.actionHash=keccak256("action");c.inputHash=keccak256("input");
        c.policyRoot=keccak256("policy");c.target=bytes32(uint256(uint160(address(this))));c.nonce=keccak256("nonce");
        c.budgetUnit=keccak256("unit");c.rootScheme=1;c.authorityEpoch=1;c.policyVersion=1;
        c.capabilities=4;c.budget=100;c.issuedAt=1000;c.expiresAt=1100;c.chainId=80002;
        collateral=new DcapCollateral38();backend=new DcapMetadata38(address(collateral));
        adapter=new SGX(address(backend),address(backend).codehash,address(collateral),address(collateral).codehash,
            ENCLAVE,SIGNER,c.runtimeId,1,7);
    }
    function put(bytes memory data,uint256 offset,bytes memory value) internal pure {
        for(uint256 i;i<value.length;++i)data[offset+i]=value[i];
    }
    function evidence() internal returns(bytes memory) {
        bytes memory quote=new bytes(1020);quote[0]=0x03;quote[2]=0x02;
        put(quote,12,hex"939a7233f79c4ca9940a0db3957f0607");
        put(quote,112,abi.encode(ENCLAVE));put(quote,176,abi.encode(SIGNER));
        quote[306]=0x01;quote[432]=0x48;quote[433]=0x02;
        bytes32 digest=A.digest(c);
        put(quote,368,abi.encode(sha256(abi.encodePacked("VAMS:SGX-ACTION:v1",hex"00",abi.encode(digest,c.actorRoot,outputHash)))));
        bytes memory body=new bytes(384);for(uint256 i;i<384;++i)body[i]=quote[48+i];
        backend.setReport(abi.encodePacked(uint16(3),uint16(1),uint8(0),bytes6(0),body));
        bytes32 control=sha256(abi.encodePacked("VAMS:SGX-ROOT-CONTROL:v1",hex"00",abi.encode(digest,outputHash,sha256(quote))));
        (,bytes32 r,bytes32 s)=vm.sign(actor,control);return abi.encode(quote,abi.encode(r,s));
    }
    function test_matchingCurrentMetadataKeepsPositiveControl() public {
        assertTrue(adapter.verifyAction(c,outputHash,evidence()));
    }
    function test_routerAddressDriftRejectsEvenWithSameCollateralCode() public {
        bytes memory proof=evidence();assertTrue(adapter.verifyAction(c,outputHash,proof));
        DcapCollateral38 other=new DcapCollateral38();assertEq(address(other).codehash,address(collateral).codehash);
        bytes32 code=address(backend).codehash;backend.setMetadata(address(other),3,0,0);
        assertEq(address(backend).codehash,code);assertFalse(adapter.verifyAction(c,outputHash,proof));
    }
    function test_quoteVersionDriftRejectsWithSameBackendCode() public {
        bytes memory proof=evidence();bytes32 code=address(backend).codehash;
        backend.setMetadata(address(collateral),4,0,0);assertEq(address(backend).codehash,code);
        assertFalse(adapter.verifyAction(c,outputHash,proof));
    }
    function getter(uint8 vm_,uint8 rm_) internal {
        bytes memory proof=evidence();backend.setMetadata(address(collateral),3,vm_,rm_);
        assertFalse(adapter.verifyAction(c,outputHash,proof));
    }
    function test_versionGetterRevertRejects() public {getter(1,0);}
    function test_routerGetterRevertRejects() public {getter(0,1);}
    function test_versionGetterMalformedEncodingsReject() public {for(uint8 mode=2;mode<=6;++mode)getter(mode,0);}
    function test_routerGetterMalformedEncodingsReject() public {for(uint8 mode=2;mode<=6;++mode)getter(0,mode);}
    function govern(Timelock t,Policy p,bytes memory data,uint256 salt) internal {
        t.schedule(address(p),0,data,bytes32(0),bytes32(salt),48 hours);vm.warp(block.timestamp+48 hours);
        t.execute(address(p),0,data,bytes32(0),bytes32(salt));
    }
    function test_actualPolicyAndDeliveryRouterRejectChangedCollateralBinding() public {
        address[] memory members=new address[](1);members[0]=address(this);
        Timelock t=new Timelock(48 hours,members,members,address(this));
        Policy p=new Policy(address(t),c.hostDomain,c.budgetUnit);
        govern(t,p,abi.encodeCall(p.configure,(c.policyRoot,1,1,4,100,600)),1);
        govern(t,p,abi.encodeCall(p.setEligibility,(A.workloadHash(c),c.providerId,c.target,true)),2);
        c.policyVersion=p.policyVersion();c.authorityEpoch=p.authorityEpoch();c.issuedAt=block.timestamp;c.expiresAt=block.timestamp+100;
        DcapUnusedRoute38 unused=new DcapUnusedRoute38();
        ActionDeliveryVerifierV1 router=new ActionDeliveryVerifierV1(address(p),address(p).codehash,
            address(adapter),address(adapter).codehash,address(unused),address(unused).codehash);
        Delivery.ExpectedDelivery memory expected=Delivery.ExpectedDelivery(c.actionHash,address(uint160(uint256(c.actorRoot))),
            A.workloadHash(c),c.budget,c.nonce,c.issuedAt,c.expiresAt,c.policyRoot,c.policyVersion,c.authorityEpoch,c.intentId);
        bytes memory proof=abi.encode(c,uint8(1),evidence());
        (bool valid,bytes32 replayKey)=router.verifyDelivery(expected,outputHash,proof);assertTrue(valid);assertTrue(replayKey!=0);
        DcapCollateral38 other=new DcapCollateral38();backend.setMetadata(address(other),3,0,0);
        (valid,replayKey)=router.verifyDelivery(expected,outputHash,proof);assertFalse(valid);assertEq(replayKey,bytes32(0));
    }
}
