// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {OperationAwareVAMSTimelockControllerV3 as Lock} from "../src/governance/OperationAwareVAMSTimelockControllerV3.sol";
import {HeartbeatConsentPolicyV3 as Policy} from "../src/trust/HeartbeatConsentPolicyV3.sol";
import {HeartbeatAuthoritySourceV3 as Source} from "../src/trust/HeartbeatAuthoritySourceV3.sol";
import {HeartbeatConsentVerificationRouterV2 as Router} from "../src/trust/HeartbeatConsentVerificationRouterV2.sol";
import {HeartbeatAuthorityTypesV3 as Types, IHeartbeatCustodyAuthorityAdapterV1} from "../src/trust/HeartbeatAuthorityTypesV3.sol";

/// @dev Synthetic constructor fixture only; no approved custody or authority.
contract RuntimeIdentityCustodyFixtureCurrent12 is IHeartbeatCustodyAuthorityAdapterV1 {
    function currentCustodyState() external pure returns (Types.CustodyState memory) {
        return Types.CustodyState(1, 1, bytes32(uint256(1)));
    }
}

/// @dev Measurement is independent of package84's literal pins. No enrollment or activation.
contract RuntimeIdentityCurrent12Tests is Test {
    function _lock(uint256 delay) private returns (Lock) {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        return new Lock(delay, proposers, executors, address(this));
    }

    function _measure(address first, address second, bytes memory compiled, string memory label) private {
        require(first != second, "distinct deployed instances required");
        require(first.code.length != 0 && second.code.length != 0, "deployed code required");
        require(first.codehash == keccak256(compiled), "first compiled/deployed keccak mismatch");
        require(second.codehash == keccak256(compiled), "second compiled/deployed keccak mismatch");
        require(sha256(first.code) == sha256(compiled), "first compiled/deployed SHA mismatch");
        require(sha256(second.code) == sha256(compiled), "second compiled/deployed SHA mismatch");
        emit log_named_uint(string.concat("COMPILED_", label, "_BYTES"), compiled.length);
        emit log_named_bytes32(string.concat("COMPILED_", label, "_KECCAK256"), keccak256(compiled));
        emit log_named_bytes32(string.concat("COMPILED_", label, "_SHA256"), sha256(compiled));
        _record(first, string.concat(label, "_FIRST"));
        _record(second, string.concat(label, "_SECOND"));
    }

    function _record(address deployed, string memory label) private {
        emit log_named_address(string.concat("DEPLOYED_", label, "_ADDRESS"), deployed);
        emit log_named_uint(string.concat("DEPLOYED_", label, "_BYTES"), deployed.code.length);
        emit log_named_bytes32(string.concat("DEPLOYED_", label, "_KECCAK256"), deployed.codehash);
        emit log_named_bytes32(string.concat("DEPLOYED_", label, "_SHA256"), sha256(deployed.code));
    }

    function testMeasureTimelockV3CurrentRuntime() public {
        Lock first = _lock(48 hours);
        Lock second = _lock(49 hours);
        require(first.getMinDelay() != second.getMinDelay(), "distinct constructor state required");
        _measure(address(first), address(second), type(Lock).runtimeCode, "TL3");
    }

    function testMeasurePolicyV3CurrentRuntime() public {
        Policy first = new Policy(address(_lock(48 hours)), keccak256(type(Source).runtimeCode));
        Policy second = new Policy(address(_lock(49 hours)), keccak256(type(Source).runtimeCode));
        require(first.governance() != second.governance(), "distinct constructor state required");
        _measure(address(first), address(second), type(Policy).runtimeCode, "POLICY3");
    }

    function _source(uint256 delay, bytes32 network) private returns (Source) {
        Lock lock = _lock(delay);
        Policy policy = new Policy(address(lock), keccak256(type(Source).runtimeCode));
        RuntimeIdentityCustodyFixtureCurrent12 custody = new RuntimeIdentityCustodyFixtureCurrent12();
        return new Source(address(lock), address(policy), address(custody), address(custody).codehash, block.chainid, network);
    }

    function testMeasureSourceV3CurrentRuntime() public {
        Source first = _source(48 hours, bytes32(uint256(1)));
        Source second = _source(49 hours, bytes32(uint256(2)));
        require(first.timelock() != second.timelock(), "distinct timelock constructor state required");
        require(first.policy() != second.policy(), "distinct policy constructor state required");
        require(first.custodyAdapter() != second.custodyAdapter(), "distinct custody constructor state required");
        require(first.networkContextDigest() != second.networkContextDigest(), "distinct network state required");
        _measure(address(first), address(second), type(Source).runtimeCode, "SOURCE3");
    }

    function testMeasureRouterV2CurrentRuntime() public {
        // RouterV2 is stateless and has no constructor arguments; only instance address differs.
        Router first = new Router();
        Router second = new Router();
        _measure(address(first), address(second), type(Router).runtimeCode, "ROUTER2");
    }
}
