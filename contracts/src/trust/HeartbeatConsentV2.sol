// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Canonical unsigned heartbeat consent V2 data only.
/// @dev No authority, signature, challenge, Timelock, policy, or current-state
///      verification is performed. A successful parse grants no rights.
library HeartbeatConsentV2 {
    string internal constant BASE_DOMAIN = "VAMS:GATEWAY:HEARTBEAT-CONSENT-BASE:v2";
    string internal constant WITNESS_DOMAIN = "VAMS:GATEWAY:HEARTBEAT-CONSENT-WITNESS:v2";
    uint256 internal constant MAX_ENCODING_BYTES = 1024;
    uint256 internal constant BASE_FIELD_COUNT = 18;
    uint256 internal constant WITNESS_FIELD_COUNT = 8;
    uint8 internal constant MODE_ENROLL = 1;
    uint8 internal constant MODE_ROTATE_NORMAL = 2;
    uint8 internal constant MODE_RECOVER_LOST_KEY = 3;
    uint8 internal constant ROLE_OLD_KEY = 0x01;
    uint8 internal constant ROLE_NEW_KEY = 0x02;
    uint8 internal constant ROLE_MASK_ENROLL = ROLE_NEW_KEY;
    uint8 internal constant ROLE_MASK_ROTATE_NORMAL = ROLE_OLD_KEY | ROLE_NEW_KEY;
    uint8 internal constant ROLE_MASK_RECOVER_LOST_KEY = ROLE_NEW_KEY;

    error InvalidBaseIntent();
    error InvalidWitness();
    error EncodingTooLarge();

    struct BaseIntent {
        uint8 mode;
        uint8 sourceScheme;
        bytes32 authoritySourceDigest;
        address timelockAddress;
        bytes32 timelockCodeHash;
        bytes32 authorityConfigDigest;
        uint64 authorityChangeSequence;
        bytes32 policyRoot;
        uint64 policyVersion;
        uint64 authorityEpoch;
        bytes32 principalId;
        bytes32 proposedRecordDigest;
        bytes32 expectedRecordDigest;
        uint64 expectedGeneration;
        uint64 proposedGeneration;
        uint64 consentNonce;
        bytes32 timelockPredecessor;
        bytes32 timelockSalt;
    }

    struct Witness {
        bytes32 baseIntentDigest;
        bytes32 operationId;
        uint64 queuedEta;
        bytes32 postEtaChallengeCommitment;
        uint64 issuedAt;
        uint64 expiresAt;
        uint8 mode;
        uint8 requiredRoleMask;
    }

    function validBase(BaseIntent memory value) internal pure returns (bool) {
        if (!_validMode(value.mode) || value.sourceScheme != 1) return false;
        if (
            value.timelockAddress == address(0) || value.timelockCodeHash == bytes32(0) ||
            value.policyRoot == bytes32(0) || value.policyVersion == 0 || value.authorityEpoch == 0 ||
            value.principalId == bytes32(0) || value.proposedGeneration == 0
        ) return false;

        if (value.mode == MODE_ENROLL) {
            return value.expectedRecordDigest == bytes32(0) &&
                value.expectedGeneration == 0 && value.proposedGeneration == 1;
        }
        return value.expectedGeneration != 0 &&
            value.expectedGeneration != type(uint64).max &&
            value.proposedGeneration == value.expectedGeneration + 1;
    }

    function validWitness(Witness memory value) internal pure returns (bool) {
        if (!_validMode(value.mode) || value.issuedAt < value.queuedEta || value.expiresAt <= value.issuedAt) {
            return false;
        }
        return value.requiredRoleMask == _requiredRoleMask(value.mode);
    }

    function requiredRoleMask(uint8 mode) internal pure returns (bool ok, uint8 mask) {
        if (!_validMode(mode)) return (false, 0);
        return (true, _requiredRoleMask(mode));
    }

    function canonicalBaseBytes(BaseIntent memory value) internal pure returns (bytes memory raw) {
        if (!validBase(value)) revert InvalidBaseIntent();
        bytes[18] memory fields;
        fields[0] = abi.encodePacked(value.mode);
        fields[1] = abi.encodePacked(value.sourceScheme);
        fields[2] = abi.encodePacked(value.authoritySourceDigest);
        fields[3] = abi.encodePacked(value.timelockAddress);
        fields[4] = abi.encodePacked(value.timelockCodeHash);
        fields[5] = abi.encodePacked(value.authorityConfigDigest);
        fields[6] = abi.encodePacked(value.authorityChangeSequence);
        fields[7] = abi.encodePacked(value.policyRoot);
        fields[8] = abi.encodePacked(value.policyVersion);
        fields[9] = abi.encodePacked(value.authorityEpoch);
        fields[10] = abi.encodePacked(value.principalId);
        fields[11] = abi.encodePacked(value.proposedRecordDigest);
        fields[12] = abi.encodePacked(value.expectedRecordDigest);
        fields[13] = abi.encodePacked(value.expectedGeneration);
        fields[14] = abi.encodePacked(value.proposedGeneration);
        fields[15] = abi.encodePacked(value.consentNonce);
        fields[16] = abi.encodePacked(value.timelockPredecessor);
        fields[17] = abi.encodePacked(value.timelockSalt);
        raw = _encodeFrame(bytes.concat(bytes(BASE_DOMAIN), hex"00"), fields, BASE_FIELD_COUNT);
    }

    function canonicalWitnessBytes(Witness memory value) internal pure returns (bytes memory raw) {
        if (!validWitness(value)) revert InvalidWitness();
        bytes[18] memory fields;
        fields[0] = abi.encodePacked(value.baseIntentDigest);
        fields[1] = abi.encodePacked(value.operationId);
        fields[2] = abi.encodePacked(value.queuedEta);
        fields[3] = abi.encodePacked(value.postEtaChallengeCommitment);
        fields[4] = abi.encodePacked(value.issuedAt);
        fields[5] = abi.encodePacked(value.expiresAt);
        fields[6] = abi.encodePacked(value.mode);
        fields[7] = abi.encodePacked(value.requiredRoleMask);
        raw = _encodeFrame(bytes.concat(bytes(WITNESS_DOMAIN), hex"00"), fields, WITNESS_FIELD_COUNT);
    }

    function baseDigest(BaseIntent memory value) internal pure returns (bytes32) {
        return sha256(canonicalBaseBytes(value));
    }

    function witnessDigest(Witness memory value) internal pure returns (bytes32) {
        return sha256(canonicalWitnessBytes(value));
    }

    function matchesBaseData(Witness memory witness, BaseIntent memory base) internal pure returns (bool) {
        return validBase(base) && validWitness(witness) &&
            witness.baseIntentDigest == baseDigest(base) && witness.mode == base.mode &&
            witness.requiredRoleMask == _requiredRoleMask(base.mode);
    }

    function tryDecodeBaseCalldata(bytes calldata raw) internal pure returns (bool, BaseIntent memory) {
        if (raw.length > MAX_ENCODING_BYTES) return (false, _emptyBase());
        bytes memory boundedCopy = raw;
        return tryDecodeBase(boundedCopy);
    }

    function tryDecodeBase(bytes memory raw) internal pure returns (bool, BaseIntent memory) {
        if (raw.length > MAX_ENCODING_BYTES) return (false, _emptyBase());
        (bool ok, bytes[18] memory fields) = _parseFields(
            raw, bytes.concat(bytes(BASE_DOMAIN), hex"00"), BASE_FIELD_COUNT, false
        );
        if (!ok) return (false, _emptyBase());

        BaseIntent memory value;
        value.mode = uint8(fields[0][0]);
        value.sourceScheme = uint8(fields[1][0]);
        value.authoritySourceDigest = _word(fields[2]);
        value.timelockAddress = _address20(fields[3]);
        value.timelockCodeHash = _word(fields[4]);
        value.authorityConfigDigest = _word(fields[5]);
        value.authorityChangeSequence = _uint64(fields[6]);
        value.policyRoot = _word(fields[7]);
        value.policyVersion = _uint64(fields[8]);
        value.authorityEpoch = _uint64(fields[9]);
        value.principalId = _word(fields[10]);
        value.proposedRecordDigest = _word(fields[11]);
        value.expectedRecordDigest = _word(fields[12]);
        value.expectedGeneration = _uint64(fields[13]);
        value.proposedGeneration = _uint64(fields[14]);
        value.consentNonce = _uint64(fields[15]);
        value.timelockPredecessor = _word(fields[16]);
        value.timelockSalt = _word(fields[17]);
        if (!validBase(value)) return (false, _emptyBase());
        return (true, value);
    }

    function tryDecodeWitnessCalldata(bytes calldata raw) internal pure returns (bool, Witness memory) {
        if (raw.length > MAX_ENCODING_BYTES) return (false, _emptyWitness());
        bytes memory boundedCopy = raw;
        return tryDecodeWitness(boundedCopy);
    }

    function tryDecodeWitness(bytes memory raw) internal pure returns (bool, Witness memory) {
        if (raw.length > MAX_ENCODING_BYTES) return (false, _emptyWitness());
        (bool ok, bytes[18] memory fields) = _parseFields(
            raw, bytes.concat(bytes(WITNESS_DOMAIN), hex"00"), WITNESS_FIELD_COUNT, true
        );
        if (!ok) return (false, _emptyWitness());
        Witness memory value;
        value.baseIntentDigest = _word(fields[0]);
        value.operationId = _word(fields[1]);
        value.queuedEta = _uint64(fields[2]);
        value.postEtaChallengeCommitment = _word(fields[3]);
        value.issuedAt = _uint64(fields[4]);
        value.expiresAt = _uint64(fields[5]);
        value.mode = uint8(fields[6][0]);
        value.requiredRoleMask = uint8(fields[7][0]);
        if (!validWitness(value)) return (false, _emptyWitness());
        return (true, value);
    }

    function _encodeFrame(bytes memory domain, bytes[18] memory fields, uint256 count)
        private pure returns (bytes memory raw)
    {
        raw = abi.encodePacked(domain, bytes2(uint16(count)));
        for (uint256 i; i < count; ++i) {
            raw = bytes.concat(raw, bytes1(uint8(i + 1)), bytes2(uint16(fields[i].length)), fields[i]);
        }
        if (raw.length > MAX_ENCODING_BYTES) revert EncodingTooLarge();
    }

    function _parseFields(bytes memory raw, bytes memory domain, uint256 count, bool witness)
        private pure returns (bool, bytes[18] memory fields)
    {
        uint256 headerLength = domain.length + 2;
        if (raw.length < headerLength || raw.length > MAX_ENCODING_BYTES) return (false, fields);
        for (uint256 i; i < domain.length; ++i) if (raw[i] != domain[i]) return (false, fields);
        if (uint8(raw[domain.length]) != 0 || uint8(raw[domain.length + 1]) != count) return (false, fields);

        uint256 offset = headerLength;
        for (uint256 i; i < count; ++i) {
            if (raw.length - offset < 3 || uint8(raw[offset]) != i + 1) return (false, fields);
            uint256 length = (uint256(uint8(raw[offset + 1])) << 8) | uint8(raw[offset + 2]);
            offset += 3;
            if (length != _fieldWidth(witness, i) || raw.length - offset < length) return (false, fields);
            bytes memory field = new bytes(length);
            for (uint256 j; j < length; ++j) field[j] = raw[offset + j];
            fields[i] = field;
            offset += length;
        }
        if (offset != raw.length) return (false, fields);
        return (true, fields);
    }

    function _fieldWidth(bool witness, uint256 index) private pure returns (uint256) {
        if (witness) {
            if (index == 2 || index == 4 || index == 5) return 8;
            if (index == 6 || index == 7) return 1;
            return 32;
        }
        if (index == 0 || index == 1) return 1;
        if (index == 3) return 20;
        if (index == 6 || index == 8 || index == 9 || (index >= 13 && index <= 15)) return 8;
        return 32;
    }

    function _validMode(uint8 mode) private pure returns (bool) {
        return mode == MODE_ENROLL || mode == MODE_ROTATE_NORMAL || mode == MODE_RECOVER_LOST_KEY;
    }

    function _requiredRoleMask(uint8 mode) private pure returns (uint8) {
        if (mode == MODE_ENROLL) return ROLE_MASK_ENROLL;
        if (mode == MODE_ROTATE_NORMAL) return ROLE_MASK_ROTATE_NORMAL;
        if (mode == MODE_RECOVER_LOST_KEY) return ROLE_MASK_RECOVER_LOST_KEY;
        return 0;
    }

    function _word(bytes memory value) private pure returns (bytes32 result) {
        assembly ("memory-safe") { result := mload(add(value, 32)) }
    }

    function _address20(bytes memory value) private pure returns (address result) {
        bytes32 word = _word(value);
        result = address(uint160(uint256(word >> 96)));
    }

    function _uint64(bytes memory value) private pure returns (uint64 result) {
        for (uint256 i; i < 8; ++i) result = (result << 8) | uint8(value[i]);
    }

    function _emptyBase() private pure returns (BaseIntent memory value) {}
    function _emptyWitness() private pure returns (Witness memory value) {}
}
