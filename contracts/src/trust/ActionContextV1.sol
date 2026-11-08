// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Shared fixed-word action encoding; constructing a context grants no authority.
library ActionContextV1 {
    struct Context {
        bytes32 actorRoot;
        bytes32 providerId;
        bytes32 runtimeId;
        bytes32 modelId;
        bytes32 hostDomain;
        bytes32 workflowId;
        bytes32 intentId;
        bytes32 actionHash;
        bytes32 inputHash;
        bytes32 policyRoot;
        bytes32 target;
        bytes32 nonce;
        bytes32 budgetUnit;
        uint256 rootScheme;
        uint256 authorityEpoch;
        uint256 policyVersion;
        uint256 capabilities;
        uint256 budget;
        uint256 issuedAt;
        uint256 expiresAt;
        uint256 chainId;
    }

    function valid(Context memory c) internal pure returns (bool) {
        if (c.actorRoot == 0 || c.providerId == 0 || c.runtimeId == 0 || c.hostDomain == 0 ||
            c.workflowId == 0 || c.intentId == 0 || c.actionHash == 0 || c.inputHash == 0 ||
            c.policyRoot == 0 || c.target == 0 || c.nonce == 0 || c.budgetUnit == 0 ||
            c.authorityEpoch == 0 || c.policyVersion == 0 || c.capabilities == 0 || c.chainId == 0 ||
            c.expiresAt <= c.issuedAt) return false;
        if (c.rootScheme == 1) return uint256(c.actorRoot) >> 160 == 0;
        if (c.rootScheme == 2) return uint256(c.actorRoot) >> 224 == 0;
        return false;
    }

    function canonicalBytes(Context memory c) internal pure returns (bytes memory) {
        require(valid(c), "Invalid action context");
        return abi.encodePacked("VAMS:ACTION-CONTEXT:v1", hex"00", abi.encode(c));
    }

    function digest(Context memory c) internal pure returns (bytes32) {
        return sha256(canonicalBytes(c));
    }

    function workloadHash(Context memory c) internal pure returns (bytes32) {
        return sha256(abi.encode(c.runtimeId, c.modelId, c.workflowId, c.inputHash));
    }

    /// @notice Parse only the exact v1 frame; decoding creates no authority.
    /// @dev Invalid frames return false and an all-zero context. All payload
    ///      fields are static bytes32/uint256, so exact-length ABI decode is total.
    function tryDecode(bytes memory raw) internal pure returns (bool, Context memory) {
        Context memory empty = Context(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0
        );
        bytes memory domain = hex"56414d533a414354494f4e2d434f4e544558543a763100";
        if (raw.length != domain.length + 21 * 32) return (false, empty);
        for (uint256 i; i < domain.length; ++i) {
            if (raw[i] != domain[i]) return (false, empty);
        }
        bytes memory words = new bytes(21 * 32);
        for (uint256 i; i < words.length; ++i) words[i] = raw[domain.length + i];
        Context memory decoded = abi.decode(words, (Context));
        if (!valid(decoded)) return (false, empty);
        return (true, decoded);
    }
}
