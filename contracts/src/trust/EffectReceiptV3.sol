// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Bounded decoder and ECDSA verifier for the unchanged Python V3 receipt wire.
/// @dev This authenticates a signed commitment only. It does not establish issuer
///      custody, provider independence, durable execution, native chain finality,
///      or current policy. Callers must supply retained expected identities.
library EffectReceiptV3 {
    uint256 private constant SECP256K1_P =
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F;
    uint256 private constant SECP256K1_N =
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
    uint256 private constant SECP256K1_HALF_N = SECP256K1_N / 2;
    uint256 private constant WORDS = 9;
    uint256 private constant SIGNATURE_LENGTH = 64;

    struct Receipt {
        bytes32 issuerId;
        bytes32 subjectDigest;
        bytes32 providerId;
        uint256 purpose;
        uint256 authorityEpoch;
        uint256 policyVersion;
        uint256 fencingToken;
        uint256 issuedAt;
        uint256 expiresAt;
    }

    struct Expected {
        bytes32 issuerId;
        bytes32 subjectDigest;
        bytes32 providerId;
        uint256 purpose;
        uint256 authorityEpoch;
        uint256 policyVersion;
        uint256 fencingToken;
    }

    /// @notice Decode only the exact SIGNED_DOMAIN || RECEIPT_DOMAIN || 9-word || r||s envelope.
    /// @return ok False for every malformed length, prefix, purpose or receipt bound.
    /// @return receipt Zeroed when decoding fails.
    /// @return signature The raw 64-byte r||s value when decoding succeeds.
    function tryDecode(bytes memory envelope)
        internal
        pure
        returns (bool ok, Receipt memory receipt, bytes memory signature)
    {
        bytes memory signedDomain = _signedDomain();
        bytes memory receiptDomain = _receiptDomain();
        uint256 bodyOffset = signedDomain.length + receiptDomain.length;
        uint256 expectedLength = bodyOffset + WORDS * 32 + SIGNATURE_LENGTH;
        if (envelope.length != expectedLength) return (false, receipt, new bytes(0));
        if (!_matches(envelope, 0, signedDomain)) return (false, receipt, new bytes(0));
        if (!_matches(envelope, signedDomain.length, receiptDomain)) {
            return (false, receipt, new bytes(0));
        }

        receipt.issuerId = _readWord(envelope, bodyOffset);
        receipt.subjectDigest = _readWord(envelope, bodyOffset + 32);
        receipt.providerId = _readWord(envelope, bodyOffset + 64);
        receipt.purpose = uint256(_readWord(envelope, bodyOffset + 96));
        receipt.authorityEpoch = uint256(_readWord(envelope, bodyOffset + 128));
        receipt.policyVersion = uint256(_readWord(envelope, bodyOffset + 160));
        receipt.fencingToken = uint256(_readWord(envelope, bodyOffset + 192));
        receipt.issuedAt = uint256(_readWord(envelope, bodyOffset + 224));
        receipt.expiresAt = uint256(_readWord(envelope, bodyOffset + 256));
        if (!_validReceipt(receipt)) return (false, Receipt(0, 0, 0, 0, 0, 0, 0, 0, 0), new bytes(0));

        signature = new bytes(SIGNATURE_LENGTH);
        uint256 signatureOffset = bodyOffset + WORDS * 32;
        for (uint256 i; i < SIGNATURE_LENGTH; ++i) {
            signature[i] = envelope[signatureOffset + i];
        }
        return (true, receipt, signature);
    }

    /// @notice Hash the unchanged V3 receipt body; wrapper domain and signature are excluded.
    function digest(Receipt memory receipt) internal pure returns (bytes32) {
        require(_validReceipt(receipt), "EffectReceiptV3: invalid receipt");
        bytes memory receiptDomain = _receiptDomain();
        return sha256(
            abi.encodePacked(
                receiptDomain,
                abi.encode(receipt)
            )
        );
    }

    /// @notice Validate a canonical uncompressed secp256k1 point and derive its EOA and issuer ID.
    function issuer(bytes memory publicKey)
        internal
        pure
        returns (bool ok, address signer, bytes32 issuerId)
    {
        if (publicKey.length != 65 || publicKey[0] != 0x04) return (false, address(0), bytes32(0));

        bytes32 xWord;
        bytes32 yWord;
        assembly ("memory-safe") {
            xWord := mload(add(publicKey, 33))
            yWord := mload(add(publicKey, 65))
        }
        uint256 x = uint256(xWord);
        uint256 y = uint256(yWord);
        if (x >= SECP256K1_P || y >= SECP256K1_P) return (false, address(0), bytes32(0));

        uint256 ySquared = mulmod(y, y, SECP256K1_P);
        uint256 xSquared = mulmod(x, x, SECP256K1_P);
        uint256 xCubed = mulmod(xSquared, x, SECP256K1_P);
        uint256 curveRight = addmod(xCubed, 7, SECP256K1_P);
        if (ySquared != curveRight) return (false, address(0), bytes32(0));

        signer = address(uint160(uint256(keccak256(abi.encodePacked(xWord, yWord)))));
        issuerId = sha256(abi.encodePacked(_receiptKeyDomain(), publicKey));
        return (true, signer, issuerId);
    }

    /// @notice Verify a V3 receipt against retained expected context and public-key identity.
    /// @dev Malformed envelopes, keys, expected context, signatures and time ranges return
    ///      (false, 0); the function does not expose caller-controlled issuer booleans.
    function verify(
        bytes memory envelope,
        bytes memory publicKey,
        Expected memory expected,
        uint256 now_,
        bool historical
    ) internal pure returns (bool ok, bytes32 receiptDigest) {
        (bool decoded, Receipt memory receipt, bytes memory signature) = tryDecode(envelope);
        if (!decoded || !_validExpected(expected)) return (false, bytes32(0));
        if (
            receipt.issuerId != expected.issuerId ||
            receipt.subjectDigest != expected.subjectDigest ||
            receipt.providerId != expected.providerId ||
            receipt.purpose != expected.purpose ||
            receipt.authorityEpoch != expected.authorityEpoch ||
            receipt.policyVersion != expected.policyVersion ||
            receipt.fencingToken != expected.fencingToken
        ) return (false, bytes32(0));

        (bool validKey, address expectedSigner, bytes32 derivedIssuer) = issuer(publicKey);
        if (!validKey || derivedIssuer != expected.issuerId) return (false, bytes32(0));

        if (historical) {
            if (receipt.purpose < 3 || now_ < receipt.issuedAt) return (false, bytes32(0));
        } else if (now_ < receipt.issuedAt || now_ >= receipt.expiresAt) {
            return (false, bytes32(0));
        }

        bytes32 rWord;
        bytes32 sWord;
        assembly ("memory-safe") {
            rWord := mload(add(signature, 32))
            sWord := mload(add(signature, 64))
        }
        uint256 r = uint256(rWord);
        uint256 s = uint256(sWord);
        if (r == 0 || r >= SECP256K1_N || s == 0 || s > SECP256K1_HALF_N) {
            return (false, bytes32(0));
        }

        receiptDigest = digest(receipt);
        address recovered = ecrecover(receiptDigest, 27, rWord, sWord);
        if (recovered != expectedSigner) recovered = ecrecover(receiptDigest, 28, rWord, sWord);
        if (recovered != expectedSigner || recovered == address(0)) return (false, bytes32(0));
        return (true, receiptDigest);
    }

    function _validReceipt(Receipt memory receipt) private pure returns (bool) {
        return receipt.issuerId != bytes32(0) && receipt.subjectDigest != bytes32(0) &&
            receipt.providerId != bytes32(0) && receipt.purpose >= 1 && receipt.purpose <= 5 &&
            receipt.authorityEpoch > 0 && receipt.policyVersion > 0 && receipt.fencingToken > 0 &&
            receipt.expiresAt > receipt.issuedAt;
    }

    function _validExpected(Expected memory expected) private pure returns (bool) {
        return expected.issuerId != bytes32(0) && expected.subjectDigest != bytes32(0) &&
            expected.providerId != bytes32(0) && expected.purpose >= 1 && expected.purpose <= 5 &&
            expected.authorityEpoch > 0 && expected.policyVersion > 0 && expected.fencingToken > 0;
    }

    function _matches(bytes memory data, uint256 offset, bytes memory expected) private pure returns (bool) {
        for (uint256 i; i < expected.length; ++i) {
            if (data[offset + i] != expected[i]) return false;
        }
        return true;
    }

    function _signedDomain() private pure returns (bytes memory) {
        return abi.encodePacked("VAMS:EFFECT-SIGNED:v3", bytes1(0));
    }

    function _receiptDomain() private pure returns (bytes memory) {
        return abi.encodePacked("VAMS:SIGNED-RECEIPT:v3", bytes1(0));
    }

    function _receiptKeyDomain() private pure returns (bytes memory) {
        return abi.encodePacked("VAMS:RECEIPT-KEY:secp256k1:v3", bytes1(0));
    }

    function _readWord(bytes memory data, uint256 offset) private pure returns (bytes32 value) {
        assembly ("memory-safe") {
            value := mload(add(add(data, 32), offset))
        }
    }
}
