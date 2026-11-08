// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {HeartbeatConsentV2 as Consent} from "./HeartbeatConsentV2.sol";
import {HeartbeatPrincipalV1 as Principal} from "./HeartbeatPrincipalV1.sol";
import {RawSecp256k1V1 as RawSecp256k1} from "./RawSecp256k1V1.sol";

/// @notice Verifies one body's raw64 low-S signature over a proposed consent role statement.
/// @dev This is proof of key possession for supplied canonical bytes only. It does not
///      authenticate queue, challenge, time, source, policy, state, governance, or consent use.
library HeartbeatConsentSignaturesV2 {
    string internal constant SIGNATURE_DOMAIN = "VAMS:GATEWAY:HEARTBEAT-CONSENT-SIGNATURE:v2";
    uint8 internal constant ALGORITHM_RAW_SECP256K1_SHA256_LOW_S = 1;

    /// @notice Check a signature from the record body key for one role required by its witness.
    /// @dev Exact protocol statement: domain || 0x00 || algorithm(0x01) || role ||
    ///      SHA256(canonical witness). SHA-256 is applied once to that statement;
    ///      RawSecp256k1V1 receives the precomputed digest and does not re-hash it.
    function verifyBodyKeySignature(
        bytes calldata baseRaw,
        bytes calldata witnessRaw,
        bytes calldata principalRaw,
        uint8 role,
        bytes calldata signature
    ) internal view returns (bool) {
        // Reject every variable-width ingress before a decoder or memory copy.
        if (
            baseRaw.length > Consent.MAX_ENCODING_BYTES ||
            witnessRaw.length > Consent.MAX_ENCODING_BYTES ||
            principalRaw.length > Principal.MAX_ENCODING_BYTES ||
            signature.length != 64 ||
            (role != Consent.ROLE_OLD_KEY && role != Consent.ROLE_NEW_KEY)
        ) return false;

        (bool baseOk, Consent.BaseIntent memory base) = Consent.tryDecodeBaseCalldata(baseRaw);
        if (!baseOk) return false;
        (bool witnessOk, Consent.Witness memory witness) = Consent.tryDecodeWitnessCalldata(witnessRaw);
        if (!witnessOk || !Consent.matchesBaseData(witness, base)) return false;
        if ((witness.requiredRoleMask & role) == 0) return false;
        (bool principalOk, Principal.Record memory record) = Principal.tryDecodeCalldata(principalRaw);
        if (!principalOk || record.principalId != base.principalId) return false;

        if (role == Consent.ROLE_NEW_KEY) {
            if (
                Principal.digest(record) != base.proposedRecordDigest ||
                record.principalGeneration != base.proposedGeneration ||
                record.policyRoot != base.policyRoot ||
                record.policyVersion != base.policyVersion ||
                record.authorityEpoch != base.authorityEpoch
            ) return false;
        } else {
            if (
                base.mode != Consent.MODE_ROTATE_NORMAL ||
                Principal.digest(record) != base.expectedRecordDigest ||
                record.principalGeneration != base.expectedGeneration
            ) return false;
        }

        bytes32 statementDigest = sha256(
            abi.encodePacked(
                SIGNATURE_DOMAIN,
                hex"00",
                bytes1(ALGORITHM_RAW_SECP256K1_SHA256_LOW_S),
                bytes1(role),
                Consent.witnessDigest(witness)
            )
        );
        return RawSecp256k1.verifyDigest(statementDigest, record.bodyPublicKey, signature);
    }

    /// @notice Verifies both normal-rotation body-key roles over one shared base and witness.
    /// @dev A true result proves key-possession facts for supplied records only; it grants no
    ///      authority and does not authenticate current state, Timelock, challenge, time or replay.
    function verifyNormalRotationSignaturePair(
        bytes calldata baseRaw,
        bytes calldata witnessRaw,
        bytes calldata oldPrincipalRaw,
        bytes calldata proposedPrincipalRaw,
        bytes calldata oldSignature,
        bytes calldata newSignature
    ) internal view returns (bool) {
        if (
            baseRaw.length > Consent.MAX_ENCODING_BYTES ||
            witnessRaw.length > Consent.MAX_ENCODING_BYTES ||
            oldPrincipalRaw.length > Principal.MAX_ENCODING_BYTES ||
            proposedPrincipalRaw.length > Principal.MAX_ENCODING_BYTES ||
            oldSignature.length != 64 || newSignature.length != 64
        ) return false;

        // Keep decoded records outside this six-calldata-argument stack frame.
        if (!_isNormalRotation(baseRaw, witnessRaw)) return false;
        if (!verifyBodyKeySignature(baseRaw, witnessRaw, oldPrincipalRaw, Consent.ROLE_OLD_KEY, oldSignature)) {
            return false;
        }
        return verifyBodyKeySignature(baseRaw, witnessRaw, proposedPrincipalRaw, Consent.ROLE_NEW_KEY, newSignature);
    }

    function _isNormalRotation(bytes calldata baseRaw, bytes calldata witnessRaw) private pure returns (bool) {
        (bool baseOk, Consent.BaseIntent memory base) = Consent.tryDecodeBaseCalldata(baseRaw);
        if (!baseOk || base.mode != Consent.MODE_ROTATE_NORMAL) return false;
        (bool witnessOk, Consent.Witness memory witness) = Consent.tryDecodeWitnessCalldata(witnessRaw);
        return witnessOk && Consent.matchesBaseData(witness, base) &&
            witness.requiredRoleMask == Consent.ROLE_MASK_ROTATE_NORMAL;
    }
}

