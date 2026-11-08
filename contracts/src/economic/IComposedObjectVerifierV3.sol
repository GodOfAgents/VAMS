// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {ObjectEffectV3 as O} from "../trust/ObjectEffectV3.sol";

/// @notice Current native-host consent/policy and signature authentication for object admission.
/// @dev Historical terminal resolution is verified against the settlement's retained obligation.
interface IComposedObjectVerifierV3 {
    function verifyObjectAdmissionV3(bytes calldata invocation, O.ExpectedRow calldata expected)
        external view returns (bool valid, O.AdmissionFacts memory facts);
    function verifyObjectCompletionV3(bytes calldata invocation, O.ExpectedTerminal calldata expected)
        external view returns (bool valid, bytes32 receiptDigest, bytes32 outputHash);
    function verifyObjectAbsenceV3(bytes calldata invocation, O.ExpectedTerminal calldata expected)
        external view returns (bool valid, bytes32 receiptDigest);
}
