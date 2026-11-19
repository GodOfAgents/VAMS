// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {IComposedSettlement} from "../../src/economic/IComposedSettlement.sol";
import {SettlementRegistryFixture, SettlementVerifierFixture} from "./ComposedSettlement.t.sol";

/// @dev Local adversarial token/wallet with actual ERC20 balance and allowance rules.
contract CallbackSettlementToken is ERC20 {
    address internal target;
    bytes internal payload;
    bool internal fromHook;
    bool internal transferHook;
    bool internal inside;
    uint256 public attempts;
    bool public nestedSucceeded;
    bytes4 public nestedError;

    constructor() ERC20("Callback fixture", "CB") {}
    function mint(address to,uint256 amount) external { _mint(to,amount); }
    function configure(address to,bytes calldata data,bool onFrom,bool onTransfer) external {
        target=to;payload=data;fromHook=onFrom;transferHook=onTransfer;
    }
    function execute(address to,bytes calldata data) external returns(bytes memory result) {
        (bool ok,bytes memory raw)=to.call(data);
        if(!ok) assembly ("memory-safe") { revert(add(raw,32),mload(raw)) }
        return raw;
    }
    function transferFrom(address from,address to,uint256 amount) public override returns(bool) {
        bool ok=super.transferFrom(from,to,amount);
        if(fromHook) _callback();
        return ok;
    }
    function transfer(address to,uint256 amount) public override returns(bool) {
        bool ok=super.transfer(to,amount);
        if(transferHook) _callback();
        return ok;
    }
    function _callback() internal {
        if(inside) return;
        inside=true;++attempts;
        (bool ok,bytes memory raw)=target.call(payload);
        nestedSucceeded=ok;
        nestedError=raw.length>=4 ? bytes4(raw) : bytes4(0);
        inside=false;
    }
}

/// @dev Only the genuine external bond-registry boundary is replaced. Never deployed.
contract CallbackSettlementBonds {
    enum Hook { None, Accept, Cancel }
    Hook internal hook;
    ComposedSettlement internal settlement;
    bytes internal payload;
    bool internal inside;
    bytes32 internal observedAllocation;
    uint256 public activeCount;
    uint256 public acceptCalls;
    uint256 public cancelCalls;
    uint256 public failAcceptAt;
    uint256 public failCancelAt;
    mapping(bytes32=>uint256) public activeAmount;
    uint256 public attempts;
    bool public nestedSucceeded;
    bytes4 public nestedError;
    bool public firstRowConsumed;
    bool public secondRowUnconsumedAtFirstCancel;
    uint256 public totalDuringFirstCancel;

    function canAcceptRequest(address,uint256) external pure returns(bool,string memory) { return(true,""); }
    function configure(ComposedSettlement s,Hook h,bytes calldata data,bytes32 allocation) external {
        settlement=s;hook=h;payload=data;observedAllocation=allocation;
    }
    function failures(uint256 acceptAt,uint256 cancelAt) external { failAcceptAt=acceptAt;failCancelAt=cancelAt; }
    function execute(address to,bytes calldata data) external returns(bytes memory) {
        (bool ok,bytes memory raw)=to.call(data);
        if(!ok) assembly ("memory-safe") { revert(add(raw,32),mload(raw)) }
        return raw;
    }
    function acceptRequest(address,bytes32 id,uint256 amount) external {
        ++acceptCalls;
        require(acceptCalls!=failAcceptAt,"synthetic accept unavailable");
        require(activeAmount[id]==0,"duplicate reservation");
        activeAmount[id]=amount;++activeCount;
        if(hook==Hook.Accept) _callback();
    }
    function completeRequest(address,bytes32) external pure { revert("not exercised"); }
    function cancelRequest(address,bytes32 id) external {
        ++cancelCalls;
        require(cancelCalls!=failCancelAt,"synthetic cancel unavailable");
        require(activeAmount[id]!=0,"missing reservation");
        delete activeAmount[id];--activeCount;
        if(cancelCalls==1 && observedAllocation!=0) {
            firstRowConsumed=settlement.refundedProviderShareV3(observedAllocation,0);
            secondRowUnconsumedAtFirstCancel=!settlement.refundedProviderShareV3(observedAllocation,1);
            totalDuringFirstCancel=settlement.totalEscrowed();
        }
        if(hook==Hook.Cancel) _callback();
    }
    function _callback() internal {
        if(inside) return;
        inside=true;++attempts;
        (bool ok,bytes memory raw)=address(settlement).call(payload);
        nestedSucceeded=ok;nestedError=raw.length>=4 ? bytes4(raw) : bytes4(0);
        inside=false;
    }
}

contract ComposedSettlementCallbackRegressionTest is Test {
    CallbackSettlementToken internal token;
    CallbackSettlementBonds internal bonds;
    ComposedSettlement internal settlement;
    address internal constant PROVIDER_A=address(0xA1);
    address internal constant PROVIDER_B=address(0xB2);
    uint256 internal constant TOTAL=300 ether;
    bytes4 internal constant REENTRY=bytes4(keccak256("ReentrancyGuardReentrantCall()"));

    function setUp() public {
        vm.warp(1_000_000);
        token=new CallbackSettlementToken();bonds=new CallbackSettlementBonds();
        settlement=new ComposedSettlement(address(this),address(token),address(bonds),address(0xFEE),
            address(new SettlementRegistryFixture()),address(new SettlementVerifierFixture()),address(this));
        token.mint(address(this),10_000 ether);token.approve(address(settlement),type(uint256).max);
        token.mint(address(token),10_000 ether);
        token.execute(address(token),abi.encodeCall(token.approve,(address(settlement),type(uint256).max)));
        token.mint(address(bonds),10_000 ether);
        bonds.execute(address(token),abi.encodeCall(token.approve,(address(settlement),type(uint256).max)));
    }
    function request() internal pure returns(IComposedSettlement.EscrowRequestV2 memory r) {
        r.providers=new address[](2);r.providers[0]=PROVIDER_A;r.providers[1]=PROVIDER_B;
        r.amounts=new uint256[](2);r.amounts[0]=100 ether;r.amounts[1]=200 ether;
        r.workloadHashes=new bytes32[](2);r.workloadHashes[0]=keccak256("A");r.workloadHashes[1]=keccak256("B");
        r.validForSeconds=300;r.blueprintHash=keccak256("callback-fixture");
    }
    function createAsBonds() internal returns(bytes32) {
        return abi.decode(bonds.execute(address(settlement),abi.encodeCall(settlement.createComposedEscrowV2,(request()))),(bytes32));
    }
    function assertSingleAllocation(bytes32 id) internal view {
        assertEq(settlement.allocationCount(),1);assertEq(settlement.totalEscrowed(),TOTAL);
        assertEq(token.balanceOf(address(settlement)),TOTAL);assertEq(bonds.activeCount(),2);
        assertEq(bonds.activeAmount(settlement.bondRequestIds(id,0)),100 ether);
        assertEq(bonds.activeAmount(settlement.bondRequestIds(id,1)),200 ether);
    }
    function test_tokenTransferFromCallbackCannotCreateNestedAllocation() public {
        token.configure(address(settlement),abi.encodeCall(settlement.createComposedEscrowV2,(request())),true,false);
        bytes32 id=settlement.createComposedEscrowV2(request());
        assertEq(token.attempts(),1);assertFalse(token.nestedSucceeded());assertEq(token.nestedError(),REENTRY);
        assertSingleAllocation(id);assertEq(token.balanceOf(address(token)),10_000 ether);
    }
    function test_bondAcceptCallbacksCannotCreateNestedAllocations() public {
        bonds.configure(settlement,CallbackSettlementBonds.Hook.Accept,
            abi.encodeCall(settlement.createComposedEscrowV2,(request())),0);
        bytes32 id=settlement.createComposedEscrowV2(request());
        assertEq(bonds.attempts(),2);assertFalse(bonds.nestedSucceeded());assertEq(bonds.nestedError(),REENTRY);
        assertSingleAllocation(id);assertEq(token.balanceOf(address(bonds)),10_000 ether);
    }
    function test_bondAcceptFailureRollsBackAllRowsBalancesAndCounterThenRetries() public {
        bonds.failures(2,0);
        vm.expectRevert("synthetic accept unavailable");settlement.createComposedEscrowV2(request());
        assertEq(settlement.allocationCount(),0);assertEq(settlement.totalEscrowed(),0);
        assertEq(token.balanceOf(address(this)),10_000 ether);assertEq(token.balanceOf(address(settlement)),0);
        assertEq(bonds.activeCount(),0);assertEq(bonds.acceptCalls(),0);
        bonds.failures(0,0);assertSingleAllocation(settlement.createComposedEscrowV2(request()));
    }
    function test_agentBondCancelCallbacksSeeConsumedRowAndCannotDoubleRefund() public {
        bytes32 id=createAsBonds();vm.warp(block.timestamp+301);
        bonds.configure(settlement,CallbackSettlementBonds.Hook.Cancel,
            abi.encodeCall(settlement.refundExpiredComposed,(id)),id);
        bonds.execute(address(settlement),abi.encodeCall(settlement.refundExpiredComposed,(id)));
        assertEq(bonds.attempts(),2);assertFalse(bonds.nestedSucceeded());assertEq(bonds.nestedError(),REENTRY);
        assertTrue(bonds.firstRowConsumed());assertTrue(bonds.secondRowUnconsumedAtFirstCancel());
        assertEq(bonds.totalDuringFirstCancel(),TOTAL);
        assertEq(bonds.cancelCalls(),2);assertEq(bonds.activeCount(),0);
        assertEq(settlement.totalEscrowed(),0);assertEq(token.balanceOf(address(bonds)),10_000 ether);
        assertEq(token.balanceOf(address(settlement)),0);
        vm.expectRevert("Nothing refundable");
        bonds.execute(address(settlement),abi.encodeCall(settlement.refundExpiredComposed,(id)));
    }
    function test_refundTokenCallbackFromActualAgentCannotRefundTwice() public {
        bytes32 id=abi.decode(token.execute(address(settlement),
            abi.encodeCall(settlement.createComposedEscrowV2,(request()))),(bytes32));
        vm.warp(block.timestamp+301);
        token.configure(address(settlement),abi.encodeCall(settlement.refundExpiredComposed,(id)),false,true);
        token.execute(address(settlement),abi.encodeCall(settlement.refundExpiredComposed,(id)));
        assertEq(token.attempts(),1);assertFalse(token.nestedSucceeded());assertEq(token.nestedError(),REENTRY);
        assertEq(token.balanceOf(address(token)),10_000 ether);assertEq(settlement.totalEscrowed(),0);
        assertEq(bonds.cancelCalls(),2);assertEq(bonds.activeCount(),0);
    }
    function test_secondCancelFailureRollsBackFirstRowAndAllLiabilitiesThenRetries() public {
        bytes32 id=settlement.createComposedEscrowV2(request());vm.warp(block.timestamp+301);
        bonds.failures(0,2);
        vm.expectRevert("synthetic cancel unavailable");settlement.refundExpiredComposed(id);
        assertFalse(settlement.refundedProviderShareV3(id,0));assertFalse(settlement.refundedProviderShareV3(id,1));
        assertEq(bonds.cancelCalls(),0);assertEq(token.balanceOf(address(this)),9_700 ether);
        assertSingleAllocation(id);
        bonds.failures(0,0);settlement.refundExpiredComposed(id);
        assertEq(token.balanceOf(address(this)),10_000 ether);assertEq(settlement.totalEscrowed(),0);
        assertEq(bonds.activeCount(),0);assertEq(bonds.cancelCalls(),2);
    }
}
