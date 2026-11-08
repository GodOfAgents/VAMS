// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {RestrictedPolicyRuntimeV1 as Runtime} from "../src/trust/RestrictedPolicyRuntimeV1.sol";
import {RestrictedTestnetPolicyV1} from "../src/trust/RestrictedTestnetPolicyV1.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";

/// @dev Source-only tests for compiler-runtime identity. They do not establish trusted config.
contract RestrictedPolicyRuntimeV1Test is Test {
    bytes32 private constant HOST = keccak256("runtime-check-host-a");
    bytes32 private constant UNIT = keccak256("runtime-check-budget-unit-a");

    function _newTimelock() private returns (VAMSTimelockController) {
        address[] memory proposers = new address[](1);
        proposers[0] = address(this);
        address[] memory executors = new address[](1);
        executors[0] = address(0);
        return new VAMSTimelockController(48 hours, proposers, executors, address(this));
    }

    function _newPolicy(address governance, bytes32 host, bytes32 unit)
        private returns (RestrictedTestnetPolicyV1)
    {
        return new RestrictedTestnetPolicyV1(governance, host, unit);
    }

    function test_deployedPolicyMatchesCapturedRuntimeAndAllImmutablePatches() public {
        VAMSTimelockController timelock = _newTimelock();
        RestrictedTestnetPolicyV1 policy = _newPolicy(address(timelock), HOST, UNIT);
        assertEq(address(policy).code.length, Runtime.EXPECTED_RUNTIME_LENGTH);
        assertLt(address(policy).code.length, 24576);
        assertEq(address(policy).codehash, Runtime.expectedCodeHash(address(timelock), HOST, UNIT));
        assertTrue(Runtime.matches(address(policy), address(timelock), HOST, UNIT));
    }

    function test_eachImmutableBindingMismatchIsRejected() public {
        VAMSTimelockController timelockA = _newTimelock();
        VAMSTimelockController timelockB = _newTimelock();
        RestrictedTestnetPolicyV1 policy = _newPolicy(address(timelockA), HOST, UNIT);

        assertFalse(Runtime.matches(address(policy), address(timelockB), HOST, UNIT));
        assertFalse(Runtime.matches(address(policy), address(timelockA), bytes32(uint256(HOST) ^ 1), UNIT));
        assertFalse(Runtime.matches(address(policy), address(timelockA), HOST, bytes32(uint256(UNIT) ^ 1)));
    }

    function test_missingBindingsAndNoCodeAreDenied() public view {
        assertEq(Runtime.expectedCodeHash(address(0), HOST, UNIT), bytes32(0));
        assertEq(Runtime.expectedCodeHash(address(1), bytes32(0), UNIT), bytes32(0));
        assertEq(Runtime.expectedCodeHash(address(1), HOST, bytes32(0)), bytes32(0));
        assertFalse(Runtime.matches(address(0), address(1), HOST, UNIT));
        assertFalse(Runtime.matches(address(1), address(1), HOST, UNIT));
    }

    function test_revertingGetterShapedCodeIsNotCalledOrTrusted() public {
        RevertingGetterShape fake = new RevertingGetterShape();
        assertFalse(Runtime.matches(address(fake), address(1), HOST, UNIT));
    }

    function test_sameLengthModifiedRuntimeIsRejected() public {
        address fake = address(0xBEEF);
        bytes memory altered = new bytes(Runtime.EXPECTED_RUNTIME_LENGTH);
        altered[0] = 0x60;
        vm.etch(fake, altered);
        assertEq(fake.code.length, Runtime.EXPECTED_RUNTIME_LENGTH);
        assertFalse(Runtime.matches(fake, address(1), HOST, UNIT));
    }

    function testFuzz_variedNonzeroHostAndUnitMatchActualDeployments(bytes32 host, bytes32 unit) public {
        vm.assume(host != bytes32(0) && unit != bytes32(0));
        VAMSTimelockController timelock = _newTimelock();
        RestrictedTestnetPolicyV1 policy = _newPolicy(address(timelock), host, unit);
        assertTrue(Runtime.matches(address(policy), address(timelock), host, unit));
    }
}

/// @dev Any attempted external getter call reverts; the identity check should never call it.
contract RevertingGetterShape {
    function governance() external pure returns (address) { revert("getter called"); }
    function hostDomain() external pure returns (bytes32) { revert("getter called"); }
    function budgetUnit() external pure returns (bytes32) { revert("getter called"); }
    fallback() external { revert("fallback called"); }
}
