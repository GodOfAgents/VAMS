// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import {SLAEnforcer} from "../../src/sentinel/SLAEnforcer.sol";
import {ISLAEnforcer} from "../../src/interfaces/ISLAEnforcer.sol";
import {VAMSSlasher} from "../../src/slashing/VAMSSlasher.sol";
import {MockHardwareRegistry} from "./SLAEnforcer.t.sol";

/// @dev Deliberately adversarial local dependency. Never a live slashing adapter.
contract MediumCallbackSlasher {
    enum Mode { Success, StringFailure, CustomFailure, EmptyFailure, MalformedReturn, Callback }
    error Unavailable(uint256 code);
    SLAEnforcer internal enforcer;
    Mode internal mode;
    uint256 internal callbackIndex;
    bool internal inside;
    uint256 public calls;
    bool public callbackSucceeded;
    bytes4 public callbackFailure;

    function configure(SLAEnforcer e, Mode m, uint256 index) external {
        enforcer = e; mode = m; callbackIndex = index;
    }

    function slashSLA(address, VAMSSlasher.OffenseType, uint256)
        external returns (VAMSSlasher.SlashResult memory result)
    {
        ++calls;
        if (mode == Mode.StringFailure) revert("temporarily unavailable");
        if (mode == Mode.CustomFailure) revert Unavailable(7);
        if (mode == Mode.EmptyFailure) assembly ("memory-safe") { revert(0, 0) }
        if (mode == Mode.MalformedReturn) assembly ("memory-safe") { return(0, 0) }
        if (mode == Mode.Callback && !inside) {
            inside = true;
            (bool ok, bytes memory reason) = address(enforcer).call(
                abi.encodeCall(SLAEnforcer.retryPendingSlash, (callbackIndex))
            );
            callbackSucceeded = ok;
            if (reason.length >= 4) callbackFailure = bytes4(reason);
            inside = false;
        }
        result.slashAmount = 123;
    }
}

/// @notice Checks failure rollback and cross-index callbacks through production
/// SLAEnforcer. All keys, reports, roles and dependencies are synthetic fixtures.
contract SlitherMediumReentrancyTest is Test {
    using MessageHashUtils for bytes32;
    uint256 internal constant PUBLIC_TEST_KEY = 1;
    bytes32 internal constant NODE_A = bytes32(uint256(1));
    bytes32 internal constant NODE_B = bytes32(uint256(2));
    address internal constant PROVIDER = address(0x1234);
    SLAEnforcer internal enforcer;
    MockHardwareRegistry internal registry;
    MediumCallbackSlasher internal slasher;

    function setUp() public {
        vm.warp(1_000_000);
        registry = new MockHardwareRegistry();
        slasher = new MediumCallbackSlasher();
        SLAEnforcer implementation = new SLAEnforcer();
        enforcer = SLAEnforcer(address(new ERC1967Proxy(address(implementation), abi.encodeCall(
            SLAEnforcer.initialize, (address(this), address(registry), address(slasher))
        ))));
        registry.setNode(NODE_A, PROVIDER);
        registry.setNode(NODE_B, PROVIDER);
        enforcer.registerSentinel(vm.addr(PUBLIC_TEST_KEY));
        // Even a callback possessing the admin role must not bypass the guard.
        enforcer.grantRole(enforcer.ADMIN_ROLE(), address(slasher));
    }

    function test_retryCallbackCannotConsumeAnotherPendingSlash() public {
        _queue(NODE_A); _queue(NODE_B);
        slasher.configure(enforcer, MediumCallbackSlasher.Mode.Callback, 1);
        enforcer.retryPendingSlash(0);
        assertEq(slasher.calls(), 1);
        assertFalse(slasher.callbackSucceeded());
        assertEq(slasher.callbackFailure(), bytes4(keccak256("ReentrancyGuardReentrantCall()")));
        assertTrue(_retried(0));
        assertFalse(_retried(1));
        vm.expectRevert(abi.encodeWithSignature("Error(string)", "Already retried"));
        enforcer.retryPendingSlash(0);
        slasher.configure(enforcer, MediumCallbackSlasher.Mode.Success, 0);
        enforcer.retryPendingSlash(1);
        assertEq(slasher.calls(), 2);
        assertTrue(_retried(1));
    }

    function test_reportCallbackCannotConsumePendingRetry() public {
        _queue(NODE_A);
        slasher.configure(enforcer, MediumCallbackSlasher.Mode.Callback, 0);
        _report(NODE_B);
        assertEq(slasher.calls(), 1);
        assertFalse(slasher.callbackSucceeded());
        assertEq(slasher.callbackFailure(), bytes4(keccak256("ReentrancyGuardReentrantCall()")));
        assertFalse(_retried(0));
        assertEq(enforcer.pendingSlashCount(), 1);
    }

    function test_stringFailureResetsRetryAndLaterSuccessConsumesOnce() public {
        _queue(NODE_A);
        enforcer.retryPendingSlash(0);
        assertFalse(_retried(0));
        assertEq(slasher.calls(), 0);
        _succeed();
    }

    function testFuzz_nonStringFailureRollsBackRetryAndRemainsRecoverable(bool empty) public {
        _queue(NODE_A);
        slasher.configure(enforcer, empty ? MediumCallbackSlasher.Mode.EmptyFailure : MediumCallbackSlasher.Mode.CustomFailure, 0);
        if (empty) vm.expectRevert();
        else vm.expectRevert(abi.encodeWithSelector(MediumCallbackSlasher.Unavailable.selector, 7));
        enforcer.retryPendingSlash(0);
        assertFalse(_retried(0));
        assertEq(slasher.calls(), 0);
        _succeed();
    }

    function test_malformedSuccessfulCallCannotConsumePendingRetry() public {
        _queue(NODE_A);
        slasher.configure(enforcer, MediumCallbackSlasher.Mode.MalformedReturn, 0);
        vm.expectRevert();
        enforcer.retryPendingSlash(0);
        assertFalse(_retried(0));
        assertEq(slasher.calls(), 0);
        _succeed();
    }

    function _succeed() internal {
        slasher.configure(enforcer, MediumCallbackSlasher.Mode.Success, 0);
        enforcer.retryPendingSlash(0);
        assertTrue(_retried(0));
        assertEq(slasher.calls(), 1);
        assertEq(enforcer.pendingSlashCount(), 1);
    }

    function _queue(bytes32 node) internal {
        slasher.configure(enforcer, MediumCallbackSlasher.Mode.StringFailure, 0);
        _report(node);
    }

    function _retried(uint256 index) internal view returns (bool done) {
        (,,,, done) = enforcer.pendingSlashes(index);
    }

    function _report(bytes32 node) internal {
        ISLAEnforcer.SLAReport memory r = ISLAEnforcer.SLAReport(node, block.timestamp, 0, "synthetic", 1, "fixture");
        bytes32 body = keccak256(abi.encode(r.nodeId, r.timestamp, r.metricsScore,
            keccak256(bytes(r.challengeType)), r.daHeight, keccak256(bytes(r.daCommitment))));
        (uint8 v, bytes32 x, bytes32 y) = vm.sign(PUBLIC_TEST_KEY, body.toEthSignedMessageHash());
        enforcer.submitSLAReport(r, abi.encodePacked(x, y, v));
    }
}
