// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

library RootSignatureV1 {
    /// @dev Canonical r||s low-S ECDSA over an already domain-separated SHA-256 digest.
    function valid(address root, bytes32 digest, bytes memory signature) internal view returns (bool) {
        if (root == address(0) || root.code.length != 0 || signature.length != 64) return false;
        (bytes32 r, bytes32 s) = abi.decode(signature, (bytes32, bytes32));
        (address signer, ECDSA.RecoverError error,) = ECDSA.tryRecover(digest, 27, r, s);
        if (error == ECDSA.RecoverError.NoError && signer == root) return true;
        (signer, error,) = ECDSA.tryRecover(digest, 28, r, s);
        return error == ECDSA.RecoverError.NoError && signer == root;
    }
}
