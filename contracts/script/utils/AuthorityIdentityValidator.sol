// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VAMSTimelockController} from "../../src/governance/VAMSTimelockController.sol";

interface IIdentityBoundSafeProxy {
    function masterCopy() external view returns (address);

    function getOwners() external view returns (address[] memory);

    function getThreshold() external view returns (uint256);

    function nonce() external view returns (uint256);

    function getModulesPaginated(address start, uint256 pageSize)
        external
        view
        returns (address[] memory modules, address next);

    function getStorageAt(uint256 offset, uint256 length) external view returns (bytes memory);
}

/// @notice Shared fail-closed identity checks for VAMS deployment scripts.
/// @dev Owner/threshold interface shape is insufficient. A deployment ceremony must
///      also pin the Safe proxy runtime, singleton address, and singleton runtime.
abstract contract AuthorityIdentityValidator {
    address private constant SAFE_MODULE_SENTINEL = address(0x1);
    uint256 private constant SAFE_GUARD_STORAGE_SLOT =
        0x4a204f620c8c5ccdca3fd54d003badd85ba500436a431f0cbda4f558c93c34c8;
    uint256 private constant SAFE_MODULE_GUARD_STORAGE_SLOT =
        0xb104e0b93118902c651344349b610029d694cfdec91c589c91ebafbcd0289947;
    uint256 private constant SAFE_FALLBACK_HANDLER_STORAGE_SLOT =
        0x6c9a6c4a39284e37ed1cf53d337577d14212a4870fb976a4366c693b939918d5;

    struct SafeIdentity {
        bytes32 proxyRuntimeCodeHash;
        address singleton;
        bytes32 singletonRuntimeCodeHash;
    }

    error InvalidSafe(address candidate, uint256 owners, uint256 threshold);
    error InvalidSafeIdentity(bytes32 proxyRuntimeCodeHash, address singleton, bytes32 singletonRuntimeCodeHash);
    error SafeProxyRuntimeMismatch(address candidate, bytes32 actual, bytes32 expected);
    error SafeSingletonMismatch(address candidate, address actual, address expected);
    error SafeSingletonRuntimeMismatch(address singleton, bytes32 actual, bytes32 expected);
    error InvalidSafeOwner(address candidate, uint256 ownerIndex, address owner);
    error UnsafeSafeNonce(address candidate, uint256 nonce);
    error UnsafeSafeModule(address candidate, address module);
    error UnsafeSafeExtension(address candidate, bytes32 slot, address extension);
    error TimelockRuntimeMismatch(address candidate, bytes32 actual, bytes32 expected);

    function expectedVAMSTimelockRuntimeCodeHash() public pure returns (bytes32) {
        return keccak256(type(VAMSTimelockController).runtimeCode);
    }

    function _requireSafe(
        address candidate,
        uint256 requiredOwners,
        uint256 requiredThreshold,
        SafeIdentity memory identity
    ) internal view {
        _requireSafeIdentity(identity);
        if (candidate == address(0) || candidate.code.length == 0) {
            revert InvalidSafe(candidate, 0, 0);
        }

        bytes32 proxyRuntimeCodeHash = candidate.codehash;
        if (proxyRuntimeCodeHash != identity.proxyRuntimeCodeHash) {
            revert SafeProxyRuntimeMismatch(candidate, proxyRuntimeCodeHash, identity.proxyRuntimeCodeHash);
        }

        address singleton;
        // Canonical SafeProxy runtimes expose slot-zero implementation identity
        // through the special-cased masterCopy() selector.
        try IIdentityBoundSafeProxy(candidate).masterCopy() returns (address candidateSingleton) {
            singleton = candidateSingleton;
        } catch {
            revert SafeSingletonMismatch(candidate, address(0), identity.singleton);
        }
        if (singleton != identity.singleton) {
            revert SafeSingletonMismatch(candidate, singleton, identity.singleton);
        }

        try IIdentityBoundSafeProxy(candidate).getOwners() returns (address[] memory owners) {
            try IIdentityBoundSafeProxy(candidate).getThreshold() returns (uint256 threshold) {
                if (owners.length != requiredOwners || threshold != requiredThreshold) {
                    revert InvalidSafe(candidate, owners.length, threshold);
                }
                _requireDistinctNonzeroOwners(candidate, owners);
                _requireNoSafeExtensions(candidate);
            } catch {
                revert InvalidSafe(candidate, owners.length, 0);
            }
        } catch {
            revert InvalidSafe(candidate, 0, 0);
        }
    }

    /// @dev Safe modules can execute without satisfying the owner threshold.
    ///      Guards and fallback handlers are also executable extensions. These
    ///      checks prove the current Safe is extension-free and has executed no
    ///      threshold transaction; operational evidence must separately prove
    ///      setup provenance and the absence of pre-approved hashes.
    function _requireNoSafeExtensions(address candidate) private view {
        try IIdentityBoundSafeProxy(candidate).nonce() returns (uint256 safeNonce) {
            if (safeNonce != 0) revert UnsafeSafeNonce(candidate, safeNonce);
        } catch {
            revert UnsafeSafeNonce(candidate, type(uint256).max);
        }

        try IIdentityBoundSafeProxy(candidate).getModulesPaginated(SAFE_MODULE_SENTINEL, 1) returns (
            address[] memory modules, address next
        ) {
            if (modules.length != 0 || next != SAFE_MODULE_SENTINEL) {
                revert UnsafeSafeModule(candidate, modules.length == 0 ? next : modules[0]);
            }
        } catch {
            revert UnsafeSafeModule(candidate, address(0));
        }

        _requireZeroSafeExtension(candidate, SAFE_GUARD_STORAGE_SLOT);
        _requireZeroSafeExtension(candidate, SAFE_MODULE_GUARD_STORAGE_SLOT);
        _requireZeroSafeExtension(candidate, SAFE_FALLBACK_HANDLER_STORAGE_SLOT);
    }

    function _requireZeroSafeExtension(address candidate, uint256 slot) private view {
        bytes memory value;
        try IIdentityBoundSafeProxy(candidate).getStorageAt(slot, 1) returns (bytes memory storedValue) {
            value = storedValue;
        } catch {
            revert UnsafeSafeExtension(candidate, bytes32(slot), address(0));
        }
        if (value.length != 32) {
            revert UnsafeSafeExtension(candidate, bytes32(slot), address(0));
        }
        bytes32 word;
        assembly ("memory-safe") {
            word := mload(add(value, 0x20))
        }
        if (word != bytes32(0)) {
            revert UnsafeSafeExtension(candidate, bytes32(slot), address(uint160(uint256(word))));
        }
    }

    function _requireKnownVAMSTimelockRuntime(address candidate) internal view {
        bytes32 expected = expectedVAMSTimelockRuntimeCodeHash();
        bytes32 actual = candidate.codehash;
        if (candidate == address(0) || candidate.code.length == 0 || actual != expected) {
            revert TimelockRuntimeMismatch(candidate, actual, expected);
        }
    }

    function _requireSafeIdentity(SafeIdentity memory identity) private view {
        if (
            identity.proxyRuntimeCodeHash == bytes32(0) || identity.singleton == address(0)
                || identity.singletonRuntimeCodeHash == bytes32(0) || identity.singleton.code.length == 0
        ) {
            revert InvalidSafeIdentity(
                identity.proxyRuntimeCodeHash, identity.singleton, identity.singletonRuntimeCodeHash
            );
        }

        bytes32 actualSingletonRuntimeCodeHash = identity.singleton.codehash;
        if (actualSingletonRuntimeCodeHash != identity.singletonRuntimeCodeHash) {
            revert SafeSingletonRuntimeMismatch(
                identity.singleton, actualSingletonRuntimeCodeHash, identity.singletonRuntimeCodeHash
            );
        }
    }

    function _requireDistinctNonzeroOwners(address candidate, address[] memory owners) private pure {
        for (uint256 i = 0; i < owners.length; ++i) {
            if (owners[i] == address(0)) revert InvalidSafeOwner(candidate, i, owners[i]);
            for (uint256 j = i + 1; j < owners.length; ++j) {
                if (owners[i] == owners[j]) revert InvalidSafeOwner(candidate, j, owners[j]);
            }
        }
    }
}
