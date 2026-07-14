// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VAMSTimelockController} from "../../src/governance/VAMSTimelockController.sol";

interface IIdentityBoundSafeProxy {
    function masterCopy() external view returns (address);

    function getOwners() external view returns (address[] memory);

    function getThreshold() external view returns (uint256);
}

/// @notice Shared fail-closed identity checks for VAMS deployment scripts.
/// @dev Owner/threshold interface shape is insufficient. A deployment ceremony must
///      also pin the Safe proxy runtime, singleton address, and singleton runtime.
abstract contract AuthorityIdentityValidator {
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
            } catch {
                revert InvalidSafe(candidate, owners.length, 0);
            }
        } catch {
            revert InvalidSafe(candidate, 0, 0);
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
