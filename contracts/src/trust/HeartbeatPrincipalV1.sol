// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Exact unsigned gateway principal data. Parsing grants no authority.
/// @dev No issuer, current policy, enrollment, revocation, signature, certificate
///      or curve validation is performed. Node commitments are supplied bytes32;
///      this library does not normalize or encode raw UTF-8 node identifiers.
library HeartbeatPrincipalV1 {
    uint256 internal constant MAX_ENCODING_BYTES = 1024;
    uint256 internal constant FIELD_COUNT = 18;

    struct Record {
        bytes32 principalId;
        bytes32 nodeIdCommitment;
        string m2SignerDid;
        bytes m2SignerPublicKey;
        bytes32 certificateFingerprint;
        bytes bodyPublicKey;
        bytes32 hostDomain;
        bytes32 serviceDomain;
        string audience;
        string method;
        string path;
        bytes query;
        bytes32 policyRoot;
        uint64 policyVersion;
        uint64 authorityEpoch;
        uint64 principalGeneration;
        uint64 notBefore;
        uint64 expiresAt;
    }

    function principalIdFor(bytes32 host, bytes32 service, bytes32 node) internal pure returns (bytes32) {
        return sha256(abi.encodePacked("VAMS:GATEWAY:HEARTBEAT-PRINCIPAL-ID:v1", hex"00", host, service, node));
    }

    function valid(Record memory r) internal pure returns (bool) {
        return r.principalId != 0 && r.nodeIdCommitment != 0 && r.certificateFingerprint != 0 &&
            r.hostDomain != 0 && r.serviceDomain != 0 && r.policyRoot != 0 &&
            r.principalId == principalIdFor(r.hostDomain, r.serviceDomain, r.nodeIdCommitment) &&
            r.bodyPublicKey.length == 64 && _didMatches(r.m2SignerDid, r.m2SignerPublicKey) &&
            _audienceValid(bytes(r.audience)) && bytes(r.method).length == 4 && bytes(r.path).length == 10 &&
            r.query.length == 0 && keccak256(bytes(r.method)) == keccak256("POST") &&
            keccak256(bytes(r.path)) == keccak256("/heartbeat") &&
            r.policyVersion > 0 && r.authorityEpoch > 0 && r.principalGeneration > 0 &&
            r.expiresAt > r.notBefore;
    }

    function canonicalBytes(Record memory r) internal pure returns (bytes memory raw) {
        require(valid(r), "Invalid heartbeat principal");
        bytes[18] memory fields;
        fields[0] = abi.encodePacked(r.principalId);
        fields[1] = abi.encodePacked(r.nodeIdCommitment);
        fields[2] = bytes(r.m2SignerDid);
        fields[3] = r.m2SignerPublicKey;
        fields[4] = abi.encodePacked(r.certificateFingerprint);
        fields[5] = r.bodyPublicKey;
        fields[6] = abi.encodePacked(r.hostDomain);
        fields[7] = abi.encodePacked(r.serviceDomain);
        fields[8] = bytes(r.audience);
        fields[9] = bytes(r.method);
        fields[10] = bytes(r.path);
        fields[11] = r.query;
        fields[12] = abi.encodePacked(r.policyRoot);
        fields[13] = abi.encodePacked(r.policyVersion);
        fields[14] = abi.encodePacked(r.authorityEpoch);
        fields[15] = abi.encodePacked(r.principalGeneration);
        fields[16] = abi.encodePacked(r.notBefore);
        fields[17] = abi.encodePacked(r.expiresAt);
        raw = abi.encodePacked("VAMS:GATEWAY:HEARTBEAT-PRINCIPAL:v1", hex"00", bytes2(uint16(FIELD_COUNT)));
        for (uint256 i; i < FIELD_COUNT; ++i) {
            raw = bytes.concat(raw, bytes1(uint8(i + 1)), bytes2(uint16(fields[i].length)), fields[i]);
        }
        require(raw.length <= MAX_ENCODING_BYTES, "Principal exceeds bound");
    }

    function digest(Record memory r) internal pure returns (bytes32) {
        return sha256(canonicalBytes(r));
    }

    /// @notice Contract ingress must use this overload to bound before copying.
    function tryDecodeCalldata(bytes calldata raw) internal pure returns (bool, Record memory) {
        if (raw.length > MAX_ENCODING_BYTES) {
            Record memory empty;
            return (false, empty);
        }
        return tryDecode(raw);
    }

    /// @notice Parse only canonical V1 bytes. Invalid input returns a zero record.
    /// @dev Caller memory allocation precedes this function; bounded raw length
    ///      limits this decoder, not the upstream transaction or transport.
    function tryDecode(bytes memory raw) internal pure returns (bool, Record memory) {
        Record memory empty;
        bytes memory domain = abi.encodePacked("VAMS:GATEWAY:HEARTBEAT-PRINCIPAL:v1", hex"00");
        if (raw.length > MAX_ENCODING_BYTES || raw.length < domain.length + 2) return (false, empty);
        for (uint256 i; i < domain.length; ++i) {
            if (raw[i] != domain[i]) return (false, empty);
        }
        uint256 offset = domain.length;
        if (uint8(raw[offset]) != 0 || uint8(raw[offset + 1]) != FIELD_COUNT) return (false, empty);
        offset += 2;
        bytes[18] memory fields;
        for (uint256 i; i < FIELD_COUNT; ++i) {
            if (raw.length - offset < 3 || uint8(raw[offset]) != i + 1) return (false, empty);
            uint256 length = uint256(uint8(raw[offset + 1])) * 256 + uint8(raw[offset + 2]);
            offset += 3;
            if (length > 256 || raw.length - offset < length || !_widthValid(i, length)) return (false, empty);
            fields[i] = new bytes(length);
            for (uint256 j; j < length; ++j) fields[i][j] = raw[offset + j];
            offset += length;
        }
        if (offset != raw.length) return (false, empty);
        Record memory r;
        r.principalId = _word(fields[0]);
        r.nodeIdCommitment = _word(fields[1]);
        r.m2SignerDid = string(fields[2]);
        r.m2SignerPublicKey = fields[3];
        r.certificateFingerprint = _word(fields[4]);
        r.bodyPublicKey = fields[5];
        r.hostDomain = _word(fields[6]);
        r.serviceDomain = _word(fields[7]);
        r.audience = string(fields[8]);
        r.method = string(fields[9]);
        r.path = string(fields[10]);
        r.query = fields[11];
        r.policyRoot = _word(fields[12]);
        r.policyVersion = _uint64(fields[13]);
        r.authorityEpoch = _uint64(fields[14]);
        r.principalGeneration = _uint64(fields[15]);
        r.notBefore = _uint64(fields[16]);
        r.expiresAt = _uint64(fields[17]);
        if (!valid(r)) return (false, empty);
        return (true, r);
    }

    function _widthValid(uint256 field, uint256 length) private pure returns (bool) {
        if (field == 0 || field == 1 || field == 4 || field == 6 || field == 7 || field == 12) return length == 32;
        if (field == 3 || field == 5) return length == 64;
        if (field >= 13) return length == 8;
        if (field == 2) return length == 136;
        if (field == 8) return length > 0 && length <= 128;
        if (field == 9) return length == 4;
        if (field == 10) return length == 10;
        return length == 0; // query, the only remaining field
    }

    function _word(bytes memory value) private pure returns (bytes32 result) {
        assembly ("memory-safe") { result := mload(add(value, 32)) }
    }

    function _uint64(bytes memory value) private pure returns (uint64 result) {
        for (uint256 i; i < 8; ++i) result = (result << 8) | uint8(value[i]);
    }

    function _didMatches(string memory did, bytes memory key) private pure returns (bool) {
        bytes memory text = bytes(did);
        if (text.length != 136 || key.length != 64) return false;
        bytes memory prefix = bytes("did:key:");
        for (uint256 i; i < prefix.length; ++i) if (text[i] != prefix[i]) return false;
        bytes memory alphabet = bytes("0123456789abcdef");
        for (uint256 i; i < key.length; ++i) {
            if (text[8 + i * 2] != alphabet[uint8(key[i]) >> 4] ||
                text[9 + i * 2] != alphabet[uint8(key[i]) & 15]) return false;
        }
        return true;
    }

    function _audienceValid(bytes memory value) private pure returns (bool) {
        if (value.length == 0 || value.length > 128) return false;
        if (!_lowerAlnum(value[0]) || !_lowerAlnum(value[value.length - 1])) return false;
        for (uint256 i = 1; i + 1 < value.length; ++i) {
            if (!_lowerAlnum(value[i]) && value[i] != bytes1(".") && value[i] != bytes1("-")) return false;
        }
        return true;
    }

    function _lowerAlnum(bytes1 value) private pure returns (bool) {
        return (value >= bytes1("a") && value <= bytes1("z")) || (value >= bytes1("0") && value <= bytes1("9"));
    }
}
