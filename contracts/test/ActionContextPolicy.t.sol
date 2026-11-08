// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {ActionContextV1} from "../src/trust/ActionContextV1.sol";
import {RestrictedTestnetPolicyV1} from "../src/trust/RestrictedTestnetPolicyV1.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";

contract ActionContextPolicyTest is Test {
    VAMSTimelockController internal timelock;
    RestrictedTestnetPolicyV1 internal policy;
    function setUp() public {
        vm.chainId(80002);
        address[] memory signers = new address[](1); signers[0] = address(this);
        timelock = new VAMSTimelockController(48 hours, signers, signers, address(this));
        ActionContextV1.Context memory c = sample();
        policy = new RestrictedTestnetPolicyV1(address(timelock), c.hostDomain, c.budgetUnit);
    }
    function sample() internal pure returns (ActionContextV1.Context memory c) {
        c.actorRoot = 0x0000000000000000000000001111111111111111111111111111111111111111;
        c.providerId = 0x0202020202020202020202020202020202020202020202020202020202020202;
        c.runtimeId = 0x0303030303030303030303030303030303030303030303030303030303030303;
        c.modelId = 0x0000000000000000000000000000000000000000000000000000000000000000;
        c.hostDomain = 0x0505050505050505050505050505050505050505050505050505050505050505;
        c.workflowId = 0x0606060606060606060606060606060606060606060606060606060606060606;
        c.intentId = 0x0707070707070707070707070707070707070707070707070707070707070707;
        c.actionHash = 0x0808080808080808080808080808080808080808080808080808080808080808;
        c.inputHash = 0x0909090909090909090909090909090909090909090909090909090909090909;
        c.policyRoot = 0x0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a;
        c.target = 0x0000000000000000000000002222222222222222222222222222222222222222;
        c.nonce = 0x0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c;
        c.budgetUnit = 0x0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d;
        c.rootScheme = 1;
        c.authorityEpoch = 3;
        c.policyVersion = 7;
        c.capabilities = 1;
        c.budget = 4096;
        c.issuedAt = 1000;
        c.expiresAt = 1100;
        c.chainId = 80002;
    }
    function govern(bytes memory callData, bytes32 salt) internal {
        timelock.schedule(address(policy),0,callData,bytes32(0),salt,48 hours);
        vm.warp(block.timestamp+48 hours);
        timelock.execute(address(policy),0,callData,bytes32(0),salt);
    }
    function enable() internal returns (ActionContextV1.Context memory c) {
        c=sample();
        c.capabilities=4; // Generic admission is the settlement route only.
        govern(abi.encodeCall(policy.configure,(c.policyRoot,1,1,4,10000,1000)),keccak256("configure"));
        govern(abi.encodeCall(policy.setEligibility,(ActionContextV1.workloadHash(c),c.providerId,c.target,true)),keccak256("route"));
        c.policyVersion=policy.policyVersion(); c.authorityEpoch=policy.authorityEpoch();
        c.issuedAt=block.timestamp; c.expiresAt=block.timestamp+100;
    }
    function test_sharedPythonGoldenBytes() public pure {
        ActionContextV1.Context memory c=sample();
        assertEq(ActionContextV1.digest(c),0xefd6951ca159fbf351df14023724120c4e70a01ac4941a03933d770de5699573);
        assertEq(ActionContextV1.workloadHash(c),0x5dbb01a6f281f8d3ec48200fbc372246d2ea6693692942e09258e66d5f7c2e5f);
        assertEq(ActionContextV1.canonicalBytes(c).length,695);
    }
    function test_defaultPolicyNeverAuthorizes() public view { assertFalse(policy.authorizes(sample())); }
    function test_realTimelockEnablesExactBoundedRoute() public {
        ActionContextV1.Context memory c=enable();
        assertTrue(policy.authorizes(c));
        c.budget=10001; assertFalse(policy.authorizes(c)); c.budget=4096;
        c.target=bytes32(uint256(0xBAD)); assertFalse(policy.authorizes(c));
    }
    function test_policyUpdateRevokesStillUnexpiredApproval() public {
        ActionContextV1.Context memory c=enable();
        bytes memory update=abi.encodeCall(policy.configure,(keccak256("new-policy"),3,3,4,10000,1000));
        bytes32 salt=keccak256("update");
        timelock.schedule(address(policy),0,update,bytes32(0),salt,48 hours);
        vm.warp(block.timestamp+48 hours-10);
        c.issuedAt=block.timestamp; c.expiresAt=block.timestamp+100;
        assertTrue(policy.authorizes(c));
        vm.warp(block.timestamp+10);
        timelock.execute(address(policy),0,update,bytes32(0),salt);
        assertLt(block.timestamp,c.expiresAt);
        assertFalse(policy.authorizes(c));
    }
    function test_delegatedCallerCannotWidenPolicy() public {
        vm.expectRevert("Governance only");
        policy.configure(keccak256("forged"),1,1,7,type(uint256).max,100);
    }
    function test_timeAndDomainChangesDeny() public {
        ActionContextV1.Context memory c=enable();
        c.chainId=1; assertFalse(policy.authorizes(c)); c.chainId=block.chainid;
        c.policyVersion++; assertFalse(policy.authorizes(c)); c.policyVersion--;
        c.authorityEpoch++; assertFalse(policy.authorizes(c)); c.authorityEpoch--;
        vm.warp(c.expiresAt); assertFalse(policy.authorizes(c));
    }
    function test_unknownTimelockCannotSupplyPolicy() public {
        vm.expectRevert("Unknown timelock runtime");
        new RestrictedTestnetPolicyV1(address(0xBAD),bytes32(uint256(1)),bytes32(uint256(2)));
    }
}
