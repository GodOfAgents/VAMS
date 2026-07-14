// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VDSOTypes} from "../VDSOTypes.sol";

/// @notice Minimum identity surface for a VDSO execution adapter.
interface IVAMSExecutionAdapter {
    function host() external view returns (VDSOTypes.Host);

    function capabilityMask() external view returns (uint256);

    /// @notice Versioned evidence-mode declaration used to reject mock/stub adapters.
    function evidenceMode() external view returns (bytes32);

    /// @notice Verifies host settlement evidence against the semantic transition.
    /// @dev Implementations must fail closed and bind every settlement field to
    ///      transitionHash. Settlement remains outside the semantic commitment.
    function verifySettlement(
        bytes32 transitionHash,
        VDSOTypes.SettlementMetadata calldata settlement,
        bytes calldata settlementProof
    ) external view returns (bool);
}
