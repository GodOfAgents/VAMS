// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {ActionContextV1} from "./ActionContextV1.sol";
import {RestrictedTestnetPolicyV1} from "./RestrictedTestnetPolicyV1.sol";
import {IActionEvidenceVerifier} from "./IActionEvidenceVerifier.sol";
import {IComposedSettlement} from "../economic/IComposedSettlement.sol";
import {IComposedDeliveryVerifier} from "../economic/IComposedDeliveryVerifier.sol";
import {IComposedObjectVerifierV3} from "../economic/IComposedObjectVerifierV3.sol";
import {GovernedObjectGrantV1 as G} from "./GovernedObjectGrantV1.sol";
import {EffectReceiptV3 as R} from "./EffectReceiptV3.sol";
import {ObjectEffectV3 as O} from "./ObjectEffectV3.sol";

/// @notice Current-policy router for exact requested workloads and challenge-bound evidence.
/// @dev Deployment requires separately qualified backend code/dependency identities.
contract ActionDeliveryVerifierV1 is IComposedDeliveryVerifier, IComposedObjectVerifierV3 {
    RestrictedTestnetPolicyV1 public immutable policy;
    IActionEvidenceVerifier public immutable sgx;
    IActionEvidenceVerifier public immutable ezkl;
    bytes32 public immutable policyCodeHash;
    bytes32 public immutable sgxCodeHash;
    bytes32 public immutable ezklCodeHash;

    constructor(address policy_, bytes32 policyHash, address sgx_, bytes32 sgxHash,
        address ezkl_, bytes32 ezklHash) {
        require(policy_.code.length > 0 && policy_.codehash == policyHash, "Policy identity mismatch");
        require(sgx_.code.length > 0 && sgx_.codehash == sgxHash, "SGX identity mismatch");
        require(ezkl_.code.length > 0 && ezkl_.codehash == ezklHash, "EZKL identity mismatch");
        policy = RestrictedTestnetPolicyV1(policy_); policyCodeHash = policyHash;
        sgx = IActionEvidenceVerifier(sgx_); sgxCodeHash = sgxHash;
        ezkl = IActionEvidenceVerifier(ezkl_); ezklCodeHash = ezklHash;
    }

    function authorizeEscrow(address actor, address[] calldata providers, bytes32[] calldata workloads,
        uint256 total, uint256 validity) external view returns (bool) {
        return address(policy).codehash == policyCodeHash && policy.authorizesEscrow(
            actor, providers, workloads, total, validity, bytes32(uint256(uint160(msg.sender))));
    }

    function challengePolicy(address provider, bytes32 workload, uint256 amount)
        external view returns (bytes32 root, uint256 version, uint256 epoch) {
        require(address(policy).codehash == policyCodeHash && policy.authorizesChallenge(
            provider, workload, amount, bytes32(uint256(uint160(msg.sender)))), "Challenge not authorized");
        return (policy.policyRoot(), policy.policyVersion(), policy.authorityEpoch());
    }

    function verifyDelivery(ExpectedDelivery calldata expected, bytes32 outputHash, bytes calldata proof)
        external view returns (bool valid, bytes32 replayKey) {
        (ActionContextV1.Context memory c, uint8 scheme, bytes memory evidence) = abi.decode(
            proof, (ActionContextV1.Context, uint8, bytes));
        if (keccak256(proof) != keccak256(abi.encode(c, scheme, evidence))) return (false, 0);
        if (address(policy).codehash != policyCodeHash || !ActionContextV1.valid(c) || c.rootScheme != 1 ||
            c.actorRoot != bytes32(uint256(uint160(expected.provider))) || c.providerId != c.actorRoot ||
            c.target != bytes32(uint256(uint160(msg.sender))) || c.actionHash != expected.context ||
            c.intentId != expected.intentId ||
            ActionContextV1.workloadHash(c) != expected.workloadHash || c.budget != expected.amount ||
            c.capabilities != 4 || c.nonce != expected.nonce || c.issuedAt != expected.issuedAt ||
            c.expiresAt != expected.expiresAt || c.policyRoot != expected.policyRoot ||
            c.policyVersion != expected.policyVersion || c.authorityEpoch != expected.authorityEpoch ||
            !policy.authorizes(c)) return (false, 0);
        IActionEvidenceVerifier backend;
        if (scheme == 1 && address(sgx).codehash == sgxCodeHash) backend = sgx;
        else if (scheme == 2 && address(ezkl).codehash == ezklCodeHash) backend = ezkl;
        else return (false, 0);
        try backend.verifyAction(c, outputHash, evidence) returns (bool ok) { valid = ok; }
        catch { return (false, 0); }
        if (valid) replayKey = sha256(abi.encode("VAMS:DELIVERY-NONCE:v1", c.chainId,
            c.target, c.actorRoot, c.authorityEpoch, c.nonce));
    }

    /// @notice Stateless ABI/proof work stays in this pinned verifier. The settlement
    /// keeps its typed ABI and supplies its exact invocation plus native row state.
    function verifyObjectAdmissionV3(bytes calldata invocation, O.ExpectedRow calldata expected)
        external view returns (bool valid, O.AdmissionFacts memory facts) {
        if (!_invocation(invocation,IComposedSettlement.admitObjectV3.selector)) return (false,facts);
        (bytes32 id,uint256 index,O.Admission memory request)=abi.decode(invocation[4:],(bytes32,uint256,O.Admission));
        if (id!=expected.allocationId || index!=expected.providerIndex ||
            keccak256(invocation[4:])!=keccak256(abi.encode(id,index,request))) return (false,facts);
        return _verifyObjectAdmission(request,expected);
    }

    function _verifyObjectAdmission(O.Admission memory request,O.ExpectedRow calldata row)
        private view returns (bool valid,O.AdmissionFacts memory f) {
        if (address(policy).codehash!=policyCodeHash || request.authorityKey.length!=65 ||
            request.providerKey.length!=65 || request.admission.length>512 ||
            request.witness.grant.resources.length>64 || request.witness.siblings.length>32 ||
            request.witness.consent.length!=65 || !_objectRowAllowed(request.proposal,row)) return (false,f);
        (bool authorityOK,,bytes32 authority)=R.issuer(request.authorityKey);
        (bool providerOK,,bytes32 provider)=R.issuer(request.providerKey);
        if (!authorityOK || !providerOK || authority==provider ||
            !policy.authorizesObjectV1(request.proposal,request.witness,authority,provider)) return (false,f);
        R.Receipt memory receipt;
        (valid,receipt)=O.admission(request.proposal,request.authorityKey,request.admission,block.timestamp);
        if (!valid || receipt.issuerId!=authority) return (false,f);
        f.proposalDigest=O.digest(request.proposal);f.admissionDigest=R.digest(receipt);
        f.operationId=G.operationId(request.proposal);f.grantDigest=policy.objectGrantDigestV1(request.witness.grant);
        f.authorityIssuer=authority;f.providerIssuer=provider;f.costUnits=request.proposal.costUnits;
        f.logicalWork=O.logicalWork(request.proposal);
        f.grantBudget=request.witness.grant.budgetLimit;f.authorityEpoch=request.proposal.context.authorityEpoch;
        f.fencingToken=request.proposal.fencingToken;
        f.policyRoot=request.proposal.context.policyRoot;
        f.policyVersion=request.proposal.context.policyVersion;
    }

    function _objectRowAllowed(G.Proposal memory p,O.ExpectedRow calldata row) private view returns (bool) {
        ActionContextV1.Context memory c=p.context;
        if (c.rootScheme!=1 || c.actorRoot!=bytes32(uint256(uint160(row.agent))) ||
            c.providerId!=bytes32(uint256(uint160(row.provider))) ||
            c.target!=bytes32(uint256(uint160(msg.sender))) || c.chainId!=block.chainid ||
            c.expiresAt>row.expiresAt || block.timestamp>=row.expiresAt ||
            ActionContextV1.workloadHash(c)!=row.workloadHash) return false;
        address[] memory providers=new address[](1);providers[0]=row.provider;
        bytes32[] memory workloads=new bytes32[](1);workloads[0]=row.workloadHash;
        return policy.authorizesEscrow(row.agent,providers,workloads,row.amount,
            row.expiresAt-block.timestamp,bytes32(uint256(uint160(msg.sender))));
    }

    /// @dev Historical relations authenticate only the caller's retained obligation.
    /// They cannot grant dispatch authority, change policy or transfer funds.
    function verifyObjectCompletionV3(bytes calldata invocation,O.ExpectedTerminal calldata expected)
        external view returns (bool valid,bytes32 receiptDigest,bytes32 outputHash) {
        if (!_invocation(invocation,IComposedSettlement.resolveObjectCompletionV3.selector)) return (false,0,0);
        (bytes32 id,uint256 index,O.ResolutionContext memory c,bytes memory receipt)=
            abi.decode(invocation[4:],(bytes32,uint256,O.ResolutionContext,bytes));
        if (receipt.length>512 || keccak256(invocation[4:])!=keccak256(abi.encode(id,index,c,receipt)) ||
            !_matchesTerminal(expected,id,index,c)) return (false,0,0);
        (valid,receiptDigest)=O.completion(c.proposal,c.admission,c.providerKey,receipt,c.admittedAt,block.timestamp);
        if (valid) outputHash=c.proposal.context.inputHash;
    }

    function verifyObjectAbsenceV3(bytes calldata invocation,O.ExpectedTerminal calldata expected)
        external view returns (bool valid,bytes32 receiptDigest) {
        if (!_invocation(invocation,IComposedSettlement.resolveObjectAbsenceV3.selector)) return (false,0);
        (bytes32 id,uint256 index,O.ResolutionContext memory c,O.AbsenceEvidence memory evidence)=
            abi.decode(invocation[4:],(bytes32,uint256,O.ResolutionContext,O.AbsenceEvidence));
        if (evidence.update.length>512 || evidence.ack.length>512 || evidence.absent.length>512 ||
            evidence.fence.issuedAt<c.admittedAt ||
            keccak256(invocation[4:])!=keccak256(abi.encode(id,index,c,evidence)) ||
            !_matchesTerminal(expected,id,index,c)) return (false,0);
        return O.absence(c.proposal,c.authorityKey,c.providerKey,evidence,block.timestamp);
    }

    function _invocation(bytes calldata raw,bytes4 selector) private pure returns (bool) {
        return raw.length>=4 && raw.length<=8192 && bytes4(raw[:4])==selector;
    }

    function _matchesTerminal(O.ExpectedTerminal calldata e,bytes32 id,uint256 index,
        O.ResolutionContext memory c) private view returns (bool) {
        return e.allocationId==id && e.providerIndex==index && e.admittedAt==c.admittedAt &&
            c.authorityKey.length==65 && c.providerKey.length==65 &&
            c.proposal.context.target==bytes32(uint256(uint160(msg.sender))) &&
            O.digest(c.proposal)==e.proposalDigest && R.digest(c.admission)==e.admissionDigest &&
            sha256(abi.encodePacked("VAMS:RECEIPT-KEY:secp256k1:v3",hex"00",c.authorityKey))==e.authorityIssuer &&
            sha256(abi.encodePacked("VAMS:RECEIPT-KEY:secp256k1:v3",hex"00",c.providerKey))==e.providerIssuer;
    }
}
