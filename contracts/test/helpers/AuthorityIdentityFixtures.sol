// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

contract KnownSafeSingletonFixture {}

/// @dev Storage-backed fixture: every instance has the same runtime code hash,
///      while singleton, owner set, and threshold remain instance state.
contract KnownSafeProxyFixture {
    address private constant MODULE_SENTINEL = address(0x1);
    uint256 private constant GUARD_STORAGE_SLOT = 0x4a204f620c8c5ccdca3fd54d003badd85ba500436a431f0cbda4f558c93c34c8;
    uint256 private constant MODULE_GUARD_STORAGE_SLOT =
        0xb104e0b93118902c651344349b610029d694cfdec91c589c91ebafbcd0289947;
    uint256 private constant FALLBACK_HANDLER_STORAGE_SLOT =
        0x6c9a6c4a39284e37ed1cf53d337577d14212a4870fb976a4366c693b939918d5;

    address private _singleton;
    address[] private _owners;
    uint256 private _threshold;
    uint256 private _nonce;
    address[] private _modules;
    address private _guard;
    address private _moduleGuard;
    address private _fallbackHandler;
    bool private _revertNonceQuery;
    bool private _revertModuleQuery;
    bool private _malformedModulePage;
    bool private _revertStorageQuery;
    bool private _malformedStorageValue;

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

    function nonce() external view returns (uint256) {
        require(!_revertNonceQuery, "nonce query disabled");
        return _nonce;
    }

    function getModulesPaginated(address start, uint256 pageSize)
        external
        view
        returns (address[] memory modules, address next)
    {
        require(!_revertModuleQuery, "module query disabled");
        require(start == MODULE_SENTINEL && pageSize > 0, "invalid page");
        if (_malformedModulePage) return (new address[](0), address(0x2));
        if (_modules.length == 0) return (new address[](0), MODULE_SENTINEL);
        modules = new address[](1);
        modules[0] = _modules[0];
        return (modules, MODULE_SENTINEL);
    }

    function getStorageAt(uint256 offset, uint256 length) external view returns (bytes memory data) {
        require(!_revertStorageQuery, "storage query disabled");
        require(length == 1, "invalid length");
        if (_malformedStorageValue) return new bytes(31);
        bytes32 value;
        if (offset == GUARD_STORAGE_SLOT) {
            value = bytes32(uint256(uint160(_guard)));
        } else if (offset == MODULE_GUARD_STORAGE_SLOT) {
            value = bytes32(uint256(uint160(_moduleGuard)));
        } else if (offset == FALLBACK_HANDLER_STORAGE_SLOT) {
            value = bytes32(uint256(uint160(_fallbackHandler)));
        }
        data = new bytes(32);
        assembly ("memory-safe") {
            mstore(add(data, 0x20), value)
        }
    }

    function enableTestModule(address module) external {
        _modules.push(module);
    }

    function setTestNonce(uint256 safeNonce) external {
        _nonce = safeNonce;
    }

    function setTestGuard(address guard) external {
        _guard = guard;
    }

    function setTestModuleGuard(address moduleGuard) external {
        _moduleGuard = moduleGuard;
    }

    function setTestFallbackHandler(address fallbackHandler) external {
        _fallbackHandler = fallbackHandler;
    }

    function setTestQueryFailures(bool nonceQuery, bool moduleQuery, bool storageQuery) external {
        _revertNonceQuery = nonceQuery;
        _revertModuleQuery = moduleQuery;
        _revertStorageQuery = storageQuery;
    }

    function setTestMalformedModulePage(bool malformed) external {
        _malformedModulePage = malformed;
    }

    function setTestMalformedStorageValue(bool malformed) external {
        _malformedStorageValue = malformed;
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
