// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {HeartbeatConsentSignaturesV2} from "./HeartbeatConsentSignaturesV2.sol";
import {HeartbeatConsentV2 as Consent} from "./HeartbeatConsentV2.sol";
import {HeartbeatPrincipalV1 as Principal} from "./HeartbeatPrincipalV1.sol";

/// @notice Stateless adapter so the pinned calldata-only signature library can verify a relayed frame.
/// @dev A true result is only key-possession evidence over supplied bytes, never authority.
contract HeartbeatConsentVerificationRouterV2 {
    struct PrincipalView {
        bytes32 principalId;
        bytes bodyPublicKey;
        bytes32 hostDomain;
        bytes32 serviceDomain;
        bytes32 policyRoot;
        uint64 policyVersion;
        uint64 authorityEpoch;
        uint64 principalGeneration;
        uint64 notBefore;
        uint64 expiresAt;
    }

    /// @notice Decode canonical consent bytes through the exact-pinned router.
    /// @dev Parsing and base/witness binding only; this is not authority or authorization.
    function decodeConsent(bytes calldata baseRaw, bytes calldata witnessRaw)
        external pure returns (bool, Consent.BaseIntent memory, Consent.Witness memory)
    {
        (bool baseOk, Consent.BaseIntent memory base) = Consent.tryDecodeBaseCalldata(baseRaw);
        (bool witnessOk, Consent.Witness memory witness) = Consent.tryDecodeWitnessCalldata(witnessRaw);
        if (!baseOk || !witnessOk || !Consent.matchesBaseData(witness, base)) {
            return (false, base, witness);
        }
        return (true, base, witness);
    }

    /// @notice Decode canonical principal bytes and return their existing V1 digest.
    /// @dev Raw bytes only; malformed input returns false, an empty record, and a zero digest.
    function decodePrincipal(bytes calldata principalRaw)
        external pure returns (bool, PrincipalView memory viewRecord, bytes32 digest)
    {
        (bool ok, Principal.Record memory record) = Principal.tryDecodeCalldata(principalRaw);
        if (!ok) return (false, viewRecord, bytes32(0));
        viewRecord.principalId = record.principalId;
        viewRecord.bodyPublicKey = record.bodyPublicKey;
        viewRecord.hostDomain = record.hostDomain;
        viewRecord.serviceDomain = record.serviceDomain;
        viewRecord.policyRoot = record.policyRoot;
        viewRecord.policyVersion = record.policyVersion;
        viewRecord.authorityEpoch = record.authorityEpoch;
        viewRecord.principalGeneration = record.principalGeneration;
        viewRecord.notBefore = record.notBefore;
        viewRecord.expiresAt = record.expiresAt;
        return (true, viewRecord, Principal.digest(record));
    }

    function verifyNormalPair(
        bytes calldata baseRaw,
        bytes calldata witnessRaw,
        bytes calldata oldRecordRaw,
        bytes calldata proposedRecordRaw,
        bytes calldata oldSignature,
        bytes calldata newSignature
    ) external view returns (bool) {
        return HeartbeatConsentSignaturesV2.verifyNormalRotationSignaturePair(
            baseRaw, witnessRaw, oldRecordRaw, proposedRecordRaw, oldSignature, newSignature
        );
    }

    function verifyRecoveryNew(
        bytes calldata baseRaw,
        bytes calldata witnessRaw,
        bytes calldata proposedRecordRaw,
        bytes calldata newSignature
    ) external view returns (bool) {
        (bool ok, Consent.BaseIntent memory base) = Consent.tryDecodeBaseCalldata(baseRaw);
        if (!ok || base.mode != Consent.MODE_RECOVER_LOST_KEY) return false;
        return HeartbeatConsentSignaturesV2.verifyBodyKeySignature(
            baseRaw, witnessRaw, proposedRecordRaw, Consent.ROLE_NEW_KEY, newSignature
        );
    }
}
