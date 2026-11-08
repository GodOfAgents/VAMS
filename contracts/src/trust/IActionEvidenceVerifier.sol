// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {ActionContextV1} from "./ActionContextV1.sol";

interface IActionEvidenceVerifier {
    // Authenticity/binding primitive only. A protected application must validate
    // its issued challenge and current policy; a direct call grants no authority.
    function verifyAction(ActionContextV1.Context calldata context, bytes32 outputHash, bytes calldata evidence)
        external view returns (bool);
}
