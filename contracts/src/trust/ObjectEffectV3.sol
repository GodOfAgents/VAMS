// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ActionContextV1} from "./ActionContextV1.sol";
import {GovernedObjectGrantV1 as G} from "./GovernedObjectGrantV1.sol";
import {EffectReceiptV3 as R} from "./EffectReceiptV3.sol";

/// @notice Exact V3 immutable-object receipt relations. No inference/TEE proof or dispatch authority.
library ObjectEffectV3 {
    uint256 private constant MAX = uint256(uint64(type(int64).max));
    struct Admission {
        G.Proposal proposal;
        G.Witness witness;
        bytes authorityKey;
        bytes providerKey;
        bytes admission;
    }
    struct ResolutionContext {
        G.Proposal proposal;
        R.Receipt admission;
        bytes authorityKey;
        bytes providerKey;
        uint256 admittedAt;
    }
    struct ExpectedRow {
        bytes32 allocationId;
        uint256 providerIndex;
        address agent;
        address provider;
        bytes32 workloadHash;
        uint256 amount;
        uint256 expiresAt;
    }
    struct AdmissionFacts {
        bytes32 proposalDigest;
        bytes32 admissionDigest;
        bytes32 operationId;
        bytes32 grantDigest;
        bytes32 authorityIssuer;
        bytes32 providerIssuer;
        bytes32 logicalWork;
        uint256 costUnits;
        uint256 grantBudget;
        uint256 authorityEpoch;
        uint256 fencingToken;
        bytes32 policyRoot;
        uint256 policyVersion;
    }
    struct ExpectedTerminal {
        bytes32 allocationId;
        uint256 providerIndex;
        bytes32 proposalDigest;
        bytes32 admissionDigest;
        bytes32 authorityIssuer;
        bytes32 providerIssuer;
        uint256 admittedAt;
    }
    struct Fence {
        bytes32 actorRoot;
        bytes32 providerId;
        bytes32 hostDomain;
        bytes32 policyRoot;
        uint256 rootScheme;
        uint256 chainId;
        uint256 authorityEpoch;
        uint256 policyVersion;
        uint256 fencingToken;
        uint256 issuedAt;
        uint256 expiresAt;
    }
    struct AbsenceEvidence {
        Fence fence;
        bytes update;
        bytes ack;
        bytes absent;
    }
    struct Acknowledgement { bool valid; bytes32 digest; uint256 issuedAt; }

    function valid(G.Proposal memory p) internal pure returns (bool) {
        ActionContextV1.Context memory c = p.context;
        return ActionContextV1.valid(c) && c.capabilities == 1 && c.modelId == 0 &&
            p.resourceId != 0 && p.costUnits <= c.budget && c.budget <= MAX &&
            p.fencingToken > 0 && p.fencingToken <= MAX && c.authorityEpoch <= MAX &&
            c.policyVersion <= MAX && c.issuedAt <= MAX && c.expiresAt <= MAX &&
            c.expiresAt - c.issuedAt <= 600 && c.actionHash == G.actionHash(p);
    }

    function digest(G.Proposal memory p) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-EFFECT:v3",hex"00",
            ActionContextV1.canonicalBytes(p.context),abi.encode(p.resourceId,p.costUnits,p.fencingToken)));
    }

    function postcondition(G.Proposal memory p) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-POSTCONDITION:v3",hex"00",
            abi.encode(G.operationId(p),p.resourceId,p.context.inputHash,uint256(1))));
    }

    /// @notice Stable logical work across authenticated attempts; authority/nonce may advance.
    /// @dev Cost units cannot be reinterpreted as a different unit on a retry.
    function logicalWork(G.Proposal memory p) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-LOGICAL-WORK:v1",hex"00",
            abi.encode(postcondition(p),p.context.budgetUnit,p.costUnits)));
    }

    function attemptId(AdmissionFacts memory facts, bytes32 allocationId, uint256 providerIndex,
        uint256 chainId, address settlement) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-SETTLEMENT-ATTEMPT:v1",hex"00",
            abi.encode(chainId,bytes32(uint256(uint160(settlement))),allocationId,providerIndex,
                facts.proposalDigest,facts.admissionDigest)));
    }

    function admission(G.Proposal memory p, bytes memory key, bytes memory envelope, uint256 now_)
        internal pure returns (bool ok, R.Receipt memory receipt) {
        (bool decoded,R.Receipt memory r,) = R.tryDecode(envelope);
        if (!decoded || !valid(p) || p.context.issuedAt > now_ || now_ >= p.context.expiresAt ||
            r.issuedAt < p.context.issuedAt || r.expiresAt > p.context.expiresAt) return (false,receipt);
        (ok,) = R.verify(envelope,key,expected(p,r.issuerId,digest(p),1),now_,false);
        return (ok,r);
    }

    function completion(G.Proposal memory p, R.Receipt memory admitted, bytes memory key,
        bytes memory envelope, uint256 admittedAt, uint256 now_) internal pure returns (bool ok,bytes32 receiptDigest) {
        uint256 committedAt;
        {
            (bool decoded,R.Receipt memory r,) = R.tryDecode(envelope);
            if (!decoded || !valid(p) || r.issuedAt < admittedAt || r.issuedAt < admitted.issuedAt ||
                r.issuedAt < p.context.issuedAt || r.issuedAt >= admitted.expiresAt ||
                r.issuedAt >= p.context.expiresAt) return (false,0);
            committedAt = r.issuedAt;
        }
        return providerReceipt(p,key,envelope,effectSubject(p,admitted,committedAt),now_);
    }

    function providerReceipt(G.Proposal memory p, bytes memory key, bytes memory envelope,
        bytes32 subject, uint256 now_) private pure returns (bool,bytes32) {
        (bool validKey,,bytes32 issuer) = R.issuer(key);
        if (!validKey) return (false,0);
        R.Expected memory e = expected(p,issuer,subject,4);
        return R.verify(envelope,key,e,now_,true);
    }

    function effectSubject(G.Proposal memory p, R.Receipt memory admitted, uint256 committedAt)
        internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-RESULT:v3",hex"00",
            abi.encode(digest(p),R.digest(admitted),p.context.inputHash,postcondition(p),uint256(1),committedAt)));
    }

    function fenceDigest(Fence memory f) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:OBJECT-FENCE:v3",hex"00",abi.encode(f)));
    }

    function absence(G.Proposal memory p, bytes memory authorityKey, bytes memory providerKey,
        AbsenceEvidence memory evidence, uint256 now_)
        internal pure returns (bool ok,bytes32 receiptDigest) {
        if (!validAbsenceFence(p,evidence.fence,now_)) return (false,0);
        (bool updateOK,bytes32 updateHash) = verifyFenceUpdate(evidence.fence,authorityKey,evidence.update);
        if (!updateOK) return (false,0);
        Acknowledgement memory ack = acknowledgement(providerKey,evidence,now_,updateHash);
        if (!ack.valid) return (false,0);
        return terminalAbsence(p,providerKey,evidence,ack.digest,ack.issuedAt,now_);
    }

    function validAbsenceFence(G.Proposal memory p, Fence memory f, uint256 now_) private pure returns (bool) {
        ActionContextV1.Context memory c = p.context;
        if (!valid(p) || f.actorRoot != c.actorRoot || f.rootScheme != c.rootScheme ||
            f.providerId != c.providerId || f.hostDomain != c.hostDomain || f.chainId != c.chainId ||
            f.policyRoot == 0 || f.policyVersion == 0 || f.policyVersion > MAX ||
            f.policyVersion < c.policyVersion ||
            (f.policyRoot != c.policyRoot && f.policyVersion == c.policyVersion) ||
            f.authorityEpoch <= c.authorityEpoch || f.authorityEpoch > MAX ||
            f.fencingToken <= p.fencingToken || f.fencingToken > MAX || f.chainId > MAX ||
            f.issuedAt > MAX || f.expiresAt > MAX || f.expiresAt <= f.issuedAt ||
            f.expiresAt - f.issuedAt > 600 || f.issuedAt > now_) return false;
        return true;
    }

    function terminalAbsence(G.Proposal memory p, bytes memory providerKey, AbsenceEvidence memory evidence,
        bytes32 ackHash, uint256 ackTime, uint256 now_) private pure returns (bool,bytes32) {
        (bool decoded,R.Receipt memory u,) = R.tryDecode(evidence.absent);
        if (!decoded || u.issuedAt < ackTime) return (false,0);
        (,,bytes32 provider) = R.issuer(providerKey);
        R.Expected memory e;
        e.issuerId = provider;
        e.subjectDigest = sha256(abi.encodePacked("VAMS:OBJECT-FENCED-ABSENCE:v3",hex"00",digest(p),ackHash));
        e.providerId = evidence.fence.providerId; e.purpose = 5;
        e.authorityEpoch = evidence.fence.authorityEpoch;
        e.policyVersion = evidence.fence.policyVersion; e.fencingToken = evidence.fence.fencingToken;
        return R.verify(evidence.absent,providerKey,e,now_,true);
    }

    function acknowledgement(bytes memory providerKey, AbsenceEvidence memory evidence,
        uint256 now_, bytes32 updateHash) private pure returns (Acknowledgement memory result) {
        Fence memory f = evidence.fence;
        (bool decoded,R.Receipt memory u,) = R.tryDecode(evidence.ack);
        if (!decoded || u.issuedAt < f.issuedAt || u.issuedAt >= f.expiresAt) return result;
        (,,bytes32 provider) = R.issuer(providerKey);
        R.Expected memory e;
        e.issuerId = provider; e.purpose = 3; e.providerId = f.providerId;
        e.authorityEpoch = f.authorityEpoch; e.policyVersion = f.policyVersion; e.fencingToken = f.fencingToken;
        e.subjectDigest = sha256(abi.encodePacked("VAMS:OBJECT-FENCE-ACK:v3",hex"00",fenceDigest(f),updateHash));
        (result.valid,result.digest) = R.verify(evidence.ack,providerKey,e,now_,true);
        result.issuedAt = u.issuedAt;
    }

    function verifyFenceUpdate(Fence memory f, bytes memory authorityKey, bytes memory update)
        private pure returns (bool,bytes32) {
        (bool decoded,R.Receipt memory u,) = R.tryDecode(update);
        if (!decoded || u.issuedAt != f.issuedAt || u.expiresAt != f.expiresAt) return (false,0);
        (,,bytes32 authority) = R.issuer(authorityKey);
        R.Expected memory e;
        e.issuerId = authority; e.subjectDigest = fenceDigest(f); e.providerId = f.providerId; e.purpose = 2;
        e.authorityEpoch = f.authorityEpoch; e.policyVersion = f.policyVersion; e.fencingToken = f.fencingToken;
        // Historical update authentication is only an input to provider-acknowledged
        // terminal absence. This helper never supplies dispatch permission.
        return R.verify(update,authorityKey,e,f.issuedAt,false);
    }

    function expected(G.Proposal memory p, bytes32 issuer, bytes32 subject, uint256 purpose)
        private pure returns (R.Expected memory) {
        return R.Expected(issuer,subject,p.context.providerId,purpose,p.context.authorityEpoch,
            p.context.policyVersion,p.fencingToken);
    }
}
