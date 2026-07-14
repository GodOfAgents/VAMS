// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

contract KnownSafeSingletonFixture {}

/// @dev Storage-backed fixture: every instance has the same runtime code hash,
///      while singleton, owner set, and threshold remain instance state.
contract KnownSafeProxyFixture {
    address private _singleton;
    address[] private _owners;
    uint256 private _threshold;

    constructor(address singleton_, uint256 ownerCount, uint256 threshold_, uint160 ownerBase) {
        _singleton = singleton_;
        _threshold = threshold_;
        for (uint256 i = 0; i < ownerCount; ++i) {
            // Test-only bounded fixture values.
            // forge-lint: disable-next-line(unsafe-typecast)
            _owners.push(address(ownerBase + uint160(i)));
        }
    }

    function getOwners() external view returns (address[] memory) {
        return _owners;
    }

    function masterCopy() external view returns (address) {
        return _singleton;
    }

    function getThreshold() external view returns (uint256) {
        return _threshold;
    }
}

/// @dev Implements the complete queried interface but is not the pinned proxy runtime.
contract ShapeOnlySafeFixture {
    address private _singleton;
    address[] private _owners;
    uint256 private _threshold;

    constructor(address singleton_, uint256 ownerCount, uint256 threshold_) {
        _singleton = singleton_;
        _threshold = threshold_;
        for (uint256 i = 0; i < ownerCount; ++i) {
            // Test-only bounded fixture values.
            // forge-lint: disable-next-line(unsafe-typecast)
            _owners.push(address(uint160(0xA000 + i)));
        }
    }

    function getOwners() external view returns (address[] memory) {
        return _owners;
    }

    function masterCopy() external view returns (address) {
        return _singleton;
    }

    function getThreshold() external view returns (uint256) {
        return _threshold;
    }
}

contract ShapeOnlyTimelockFixture is AccessControl {
    bytes32 public constant PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
    bytes32 public constant CANCELLER_ROLE = keccak256("CANCELLER_ROLE");
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");

    uint256 private _minimumDelay;

    constructor(uint256 minimumDelay, address governanceSafe, bool openExecution) {
        _minimumDelay = minimumDelay;
        _grantRole(PROPOSER_ROLE, governanceSafe);
        _grantRole(CANCELLER_ROLE, governanceSafe);
        if (openExecution) _grantRole(EXECUTOR_ROLE, address(0));
    }

    function getMinDelay() external view returns (uint256) {
        return _minimumDelay;
    }
}
