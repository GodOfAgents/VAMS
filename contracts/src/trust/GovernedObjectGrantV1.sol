// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ActionContextV1} from "./ActionContextV1.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/// @notice Actor consent and bounded membership in the responsible host's root.
/// @dev No effect proof, spending ledger, native finality or signing authority.
library GovernedObjectGrantV1 {
    uint256 internal constant MAX_INTEGER = uint256(uint64(type(int64).max));

    struct Grant {
        bytes32 actorRoot;
        bytes32 providerId;
        bytes32 runtimeId;
        bytes32 workflowId;
        bytes32 intentId;
        bytes32 target;
        bytes32 authorityIssuer;
        bytes32 providerIssuer;
        bytes32 nonce;
        uint256 budgetLimit;
        uint256 maxActionCost;
        uint256 maxScopeLifetime;
        uint256 validAfter;
        uint256 validUntil;
        bytes32[] resources;
    }
    struct Witness {
        Grant grant;
        bytes consent;
        bytes32[] siblings;
        uint256 index;
    }
    struct Proposal {
        ActionContextV1.Context context;
        bytes32 resourceId;
        uint256 costUnits;
        uint256 fencingToken;
    }
    struct Scope {
        ActionContextV1.Context context;
        bytes32[] resources;
        uint256 budgetLimit;
        uint256 maxActionCost;
        uint256 fencingToken;
    }

    function sortedResources(bytes32[] memory resources) internal pure returns (bool) {
        if (resources.length == 0 || resources.length > 64) return false;
        bytes32 previous;
        for (uint256 i; i < resources.length; ++i) {
            if (resources[i] <= previous) return false;
            previous = resources[i];
        }
        return true;
    }

    function valid(Grant memory g) internal pure returns (bool) {
        return g.actorRoot != 0 && uint256(g.actorRoot) >> 160 == 0 && g.providerId != 0 &&
            g.runtimeId != 0 && g.workflowId != 0 && g.intentId != 0 && g.target != 0 &&
            g.authorityIssuer != 0 && g.providerIssuer != 0 && g.authorityIssuer != g.providerIssuer &&
            g.nonce != 0 && g.budgetLimit > 0 && g.budgetLimit <= MAX_INTEGER &&
            g.maxActionCost <= g.budgetLimit && g.maxScopeLifetime > 0 && g.maxScopeLifetime <= 600 &&
            g.validAfter <= MAX_INTEGER && g.validUntil <= MAX_INTEGER &&
            g.validUntil > g.validAfter && g.validUntil - g.validAfter <= 24 hours &&
            sortedResources(g.resources);
    }

    function digest(Grant memory g, address policy, uint256 chainId, bytes32 host, bytes32 unit)
        internal pure returns (bytes32) {
        require(valid(g) && policy != address(0) && chainId > 0 && chainId <= MAX_INTEGER &&
            host != 0 && unit != 0, "Invalid object grant");
        // Fixed ABI words and raw sorted resources; no dynamic ABI offsets/JSON.
        bytes memory identity = abi.encode(g.actorRoot,g.providerId,g.runtimeId,g.workflowId,
            g.intentId,g.target,g.authorityIssuer,g.providerIssuer,g.nonce);
        bytes memory limits = abi.encode(g.budgetLimit,g.maxActionCost,g.maxScopeLifetime,
            g.validAfter,g.validUntil,g.resources.length);
        return sha256(abi.encodePacked("VAMS:OBJECT-GRANT:v1",hex"00",
            abi.encode(bytes32(uint256(uint160(policy))),chainId,host,unit),identity,limits,abi.encodePacked(g.resources)));
    }

    function member(bytes32 grantDigest, bytes32 root, bytes32[] memory siblings, uint256 index)
        internal pure returns (bool) {
        if (siblings.length > 32 || index >> siblings.length != 0) return false;
        bytes32 value = sha256(abi.encodePacked("VAMS:OBJECT-GRANT-LEAF:v1",hex"00",grantDigest));
        for (uint256 i; i < siblings.length; ++i) {
            if (siblings[i] == 0) return false;
            value = (index & 1) == 0
                ? sha256(abi.encodePacked("VAMS:OBJECT-GRANT-NODE:v1",hex"00",value,siblings[i]))
                : sha256(abi.encodePacked("VAMS:OBJECT-GRANT-NODE:v1",hex"00",siblings[i],value));
            index >>= 1;
        }
        return value == root;
    }

    function consented(Grant memory g, bytes32 grantDigest, bytes memory signature) internal pure returns (bool) {
        (address actor, ECDSA.RecoverError error,) = ECDSA.tryRecover(grantDigest,signature);
        return error == ECDSA.RecoverError.NoError && actor != address(0) &&
            bytes32(uint256(uint160(actor))) == g.actorRoot;
    }

    function matches(Grant memory g, ActionContextV1.Context memory c, bytes32 authority, bytes32 provider)
        internal pure returns (bool) {
        return c.rootScheme == 1 && c.capabilities == 1 && c.modelId == 0 &&
            c.actorRoot == g.actorRoot && c.providerId == g.providerId && c.runtimeId == g.runtimeId &&
            c.workflowId == g.workflowId && c.intentId == g.intentId && c.target == g.target &&
            authority == g.authorityIssuer && provider == g.providerIssuer &&
            c.budget <= g.budgetLimit && c.issuedAt >= g.validAfter && c.expiresAt <= g.validUntil &&
            c.expiresAt > c.issuedAt && c.expiresAt - c.issuedAt <= g.maxScopeLifetime &&
            c.budget <= MAX_INTEGER && c.issuedAt <= MAX_INTEGER && c.expiresAt <= MAX_INTEGER &&
            c.authorityEpoch <= MAX_INTEGER && c.policyVersion <= MAX_INTEGER;
    }

    function includes(bytes32[] memory resources, bytes32 resource) internal pure returns (bool) {
        for (uint256 i; i < resources.length; ++i) if (resources[i] == resource) return true;
        return false;
    }

    function operationId(Proposal memory p) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-OPERATION:v3",hex"00",
            abi.encode(p.context.actorRoot,p.context.rootScheme,p.context.workflowId,p.context.intentId,p.resourceId)));
    }
    function actionHash(Proposal memory p) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-ACTION:v3",hex"00",
            abi.encode(operationId(p),p.resourceId,p.context.inputHash,p.costUnits,p.fencingToken)));
    }
    function scopeDigest(Scope memory s) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-AUTHORITY-SCOPE:v3",hex"00",
            ActionContextV1.canonicalBytes(s.context),abi.encode(s.budgetLimit,s.maxActionCost,s.fencingToken,s.resources.length),
            abi.encodePacked(s.resources)));
    }
}
