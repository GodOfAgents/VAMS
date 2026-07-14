// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VDSOCanaryAccess} from "./VDSOCanaryAccess.sol";
import {VDSOTypes} from "./VDSOTypes.sol";
import {VAMSAdapterRegistry} from "./VAMSAdapterRegistry.sol";

/// @title VAMSCapabilityRouter
/// @notice Deterministic, fail-closed selection of active execution adapters.
contract VAMSCapabilityRouter is VDSOCanaryAccess {
    VAMSAdapterRegistry public immutable adapterRegistry;

    error InvalidRouteRequirements();
    error NoCapableAdapter();

    constructor(address admin, address pauser, address registry) VDSOCanaryAccess(admin, pauser) {
        if (registry.code.length == 0) revert InvalidAddress();
        adapterRegistry = VAMSAdapterRegistry(registry);
    }

    /// @notice Selects the numerically lowest qualifying adapter ID.
    /// @dev Selection is independent of candidate ordering and never relaxes
    ///      host, verifier, or capability requirements.
    function selectAdapter(
        bytes32[] calldata candidateAdapterIds,
        uint256 requiredCapabilities,
        VDSOTypes.Host requiredHost,
        bytes32 verifierId
    ) external view returns (bytes32 selectedAdapterId) {
        _requireNotPaused();
        if (
            candidateAdapterIds.length == 0 || requiredCapabilities == 0 || requiredHost == VDSOTypes.Host.NONE
                || verifierId == bytes32(0)
        ) revert InvalidRouteRequirements();

        for (uint256 i = 0; i < candidateAdapterIds.length; ++i) {
            bytes32 adapterId = candidateAdapterIds[i];
            if (
                adapterRegistry.isActiveAndCapable(adapterId, requiredCapabilities, requiredHost, verifierId)
                    && (selectedAdapterId == bytes32(0) || uint256(adapterId) < uint256(selectedAdapterId))
            ) {
                selectedAdapterId = adapterId;
            }
        }

        if (selectedAdapterId == bytes32(0)) revert NoCapableAdapter();
    }
}
