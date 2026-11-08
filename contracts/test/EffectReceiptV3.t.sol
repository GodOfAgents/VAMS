// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {EffectReceiptV3} from "../src/trust/EffectReceiptV3.sol";

/// @notice Synthetic codec tests only; private key 1 is public test material, not custody evidence.
contract EffectReceiptV3Test is Test {
    uint256 private constant SYNTHETIC_KEY = 1;
    uint256 private constant SECP256K1_N =
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
    uint256 private constant SECP256K1_HALF_N = SECP256K1_N / 2;

    bytes32 private constant GENERATOR_X =
        0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798;
    bytes32 private constant GENERATOR_Y =
        0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8;

    function _receipt(uint256 purpose) private pure returns (EffectReceiptV3.Receipt memory r) {
        (bool validIssuer,, bytes32 issuerId) = EffectReceiptV3.issuer(_publicKey());
        require(validIssuer, "synthetic generator point must be accepted");
        r.issuerId = issuerId;
        r.subjectDigest = keccak256("SYNTHETIC-RECEIPT-SUBJECT");
        r.providerId = keccak256("SYNTHETIC-RECEIPT-PROVIDER");
        r.purpose = purpose;
        r.authorityEpoch = 2;
        r.policyVersion = 3;
        r.fencingToken = 4;
        r.issuedAt = 1_000;
        r.expiresAt = 1_100;
    }

    function _expected(EffectReceiptV3.Receipt memory r)
        private
        pure
        returns (EffectReceiptV3.Expected memory expected)
    {
        expected = EffectReceiptV3.Expected({
            issuerId: r.issuerId,
            subjectDigest: r.subjectDigest,
            providerId: r.providerId,
            purpose: r.purpose,
            authorityEpoch: r.authorityEpoch,
            policyVersion: r.policyVersion,
            fencingToken: r.fencingToken
        });
    }

    function _publicKey() private pure returns (bytes memory) {
        return abi.encodePacked(bytes1(0x04), GENERATOR_X, GENERATOR_Y);
    }

    function _envelope(EffectReceiptV3.Receipt memory r, bytes memory signature)
        private
        pure
        returns (bytes memory)
    {
        return abi.encodePacked(
            _signedDomain(),
            _receiptDomain(),
            abi.encode(r),
            signature
        );
    }

    function _sign(EffectReceiptV3.Receipt memory r) private returns (bytes memory signature) {
        bytes32 receiptDigest = EffectReceiptV3.digest(r);
        (, bytes32 rWord, bytes32 sWord) = vm.sign(SYNTHETIC_KEY, receiptDigest);
        if (uint256(sWord) > SECP256K1_HALF_N) {
            sWord = bytes32(SECP256K1_N - uint256(sWord));
        }
        signature = abi.encodePacked(rWord, sWord);
    }

    function _signed(EffectReceiptV3.Receipt memory r)
        private
        returns (bytes memory envelope, bytes memory signature)
    {
        signature = _sign(r);
        envelope = _envelope(r, signature);
    }

    function _signedDomain() private pure returns (bytes memory) {
        return abi.encodePacked("VAMS:EFFECT-SIGNED:v3", bytes1(0));
    }

    function _receiptDomain() private pure returns (bytes memory) {
        return abi.encodePacked("VAMS:SIGNED-RECEIPT:v3", bytes1(0));
    }

    function _keyDomain() private pure returns (bytes memory) {
        return abi.encodePacked("VAMS:RECEIPT-KEY:secp256k1:v3", bytes1(0));
    }

    function _overwriteWord(bytes memory envelope, uint256 wordIndex, bytes32 value)
        private
        pure
        returns (bytes memory)
    {
        uint256 offset = _signedDomain().length + _receiptDomain().length + wordIndex * 32;
        for (uint256 i; i < 32; ++i) envelope[offset + i] = value[i];
        return envelope;
    }

    function _truncate(bytes memory data) private pure returns (bytes memory shorter) {
        shorter = new bytes(data.length - 1);
        for (uint256 i; i < shorter.length; ++i) shorter[i] = data[i];
    }

    function test_decodePreservesExactWireAndDigestExcludesWrapperAndSignature() public {
        EffectReceiptV3.Receipt memory r = _receipt(4);
        (bytes memory envelope, bytes memory signature) = _signed(r);
        (bool ok, EffectReceiptV3.Receipt memory decoded, bytes memory decodedSignature) =
            EffectReceiptV3.tryDecode(envelope);

        assertTrue(ok);
        assertEq(decoded.issuerId, r.issuerId);
        assertEq(decoded.subjectDigest, r.subjectDigest);
        assertEq(decoded.providerId, r.providerId);
        assertEq(decoded.purpose, r.purpose);
        assertEq(decoded.authorityEpoch, r.authorityEpoch);
        assertEq(decoded.policyVersion, r.policyVersion);
        assertEq(decoded.fencingToken, r.fencingToken);
        assertEq(decoded.issuedAt, r.issuedAt);
        assertEq(decoded.expiresAt, r.expiresAt);
        assertEq(keccak256(decodedSignature), keccak256(signature));
        assertEq(envelope.length, _signedDomain().length + _receiptDomain().length + 9 * 32 + 64);
        assertEq(
            EffectReceiptV3.digest(r),
            sha256(
                abi.encodePacked(
                    _receiptDomain(), abi.encode(r)
                )
            )
        );
        assertTrue(EffectReceiptV3.digest(r) != sha256(envelope));
    }

    function test_issuerRequiresCanonicalUncompressedOnCurvePublicKey() public {
        bytes memory publicKey = _publicKey();
        (bool ok, address signer, bytes32 issuerId) = EffectReceiptV3.issuer(publicKey);
        assertTrue(ok);
        assertEq(signer, vm.addr(SYNTHETIC_KEY));
        assertEq(
            issuerId,
            sha256(abi.encodePacked(_keyDomain(), publicKey))
        );

        (ok,,) = EffectReceiptV3.issuer(hex"0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798");
        assertFalse(ok); // compressed keys are not decoded or accepted

        bytes memory wrongPrefix = _publicKey();
        wrongPrefix[0] = 0x02;
        (ok,,) = EffectReceiptV3.issuer(wrongPrefix);
        assertFalse(ok);

        bytes memory xOutsideField = _publicKey();
        bytes32 fieldPrime = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F;
        for (uint256 i; i < 32; ++i) xOutsideField[1 + i] = fieldPrime[i];
        (ok,,) = EffectReceiptV3.issuer(xOutsideField);
        assertFalse(ok);

        bytes memory offCurve = _publicKey();
        offCurve[64] = bytes1(uint8(offCurve[64]) ^ 1);
        (ok,,) = EffectReceiptV3.issuer(offCurve);
        assertFalse(ok);
    }

    function test_verifyRequiresExpectedIssuerContextAndCurrentTimeWindow() public {
        EffectReceiptV3.Receipt memory r = _receipt(4);
        (bytes memory envelope,) = _signed(r);
        EffectReceiptV3.Expected memory expected = _expected(r);

        (bool ok, bytes32 verifiedDigest) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_000, false);
        assertTrue(ok);
        assertEq(verifiedDigest, EffectReceiptV3.digest(r));
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_099, false);
        assertTrue(ok);
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 999, false);
        assertFalse(ok);
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_100, false);
        assertFalse(ok);

        expected.issuerId = keccak256("wrong-issuer");
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_050, false);
        assertFalse(ok);
        expected = _expected(r);
        expected.subjectDigest = keccak256("wrong-subject");
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_050, false);
        assertFalse(ok);
        expected = _expected(r);
        expected.providerId = keccak256("wrong-provider");
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_050, false);
        assertFalse(ok);
        expected = _expected(r);
        expected.purpose = 3;
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_050, false);
        assertFalse(ok);
        expected = _expected(r);
        expected.authorityEpoch += 1;
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_050, false);
        assertFalse(ok);
        expected = _expected(r);
        expected.policyVersion += 1;
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_050, false);
        assertFalse(ok);
        expected = _expected(r);
        expected.fencingToken += 1;
        (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_050, false);
        assertFalse(ok);

        bytes memory otherKey = _publicKey();
        bytes32 negatedY = bytes32(
            0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F - uint256(GENERATOR_Y)
        );
        for (uint256 i; i < 32; ++i) otherKey[33 + i] = negatedY[i];
        (ok,) = EffectReceiptV3.verify(envelope, otherKey, _expected(r), 1_050, false);
        assertFalse(ok);

    }

    function test_rejectsMalformedEnvelopeAndReceiptBoundsWithoutRevert() public {
        EffectReceiptV3.Receipt memory r = _receipt(4);
        (bytes memory envelope, bytes memory signature) = _signed(r);
        (bool ok,,) = EffectReceiptV3.tryDecode(abi.encodePacked(envelope, bytes1(0)));
        assertFalse(ok);
        (ok,,) = EffectReceiptV3.tryDecode(_truncate(envelope));
        assertFalse(ok);

        bytes memory wrongSignedDomain = envelope;
        wrongSignedDomain[0] = bytes1(uint8(wrongSignedDomain[0]) ^ 1);
        (ok,,) = EffectReceiptV3.tryDecode(wrongSignedDomain);
        assertFalse(ok);

        bytes memory wrongReceiptDomain = envelope;
        wrongReceiptDomain[_signedDomain().length] = bytes1(uint8(wrongReceiptDomain[_signedDomain().length]) ^ 1);
        (ok,,) = EffectReceiptV3.tryDecode(wrongReceiptDomain);
        assertFalse(ok);

        (ok,,) = EffectReceiptV3.tryDecode(_overwriteWord(envelope, 3, bytes32(0)));
        assertFalse(ok);

        for (uint256 wordIndex; wordIndex < 3; ++wordIndex) {
            (ok,,) = EffectReceiptV3.tryDecode(_overwriteWord(envelope, wordIndex, bytes32(0)));
            assertFalse(ok);
        }
        for (uint256 wordIndex = 4; wordIndex <= 6; ++wordIndex) {
            (ok,,) = EffectReceiptV3.tryDecode(_overwriteWord(envelope, wordIndex, bytes32(0)));
            assertFalse(ok);
        }
        (ok,,) = EffectReceiptV3.tryDecode(_overwriteWord(envelope, 3, bytes32(0)));
        assertFalse(ok);
        (ok,,) = EffectReceiptV3.tryDecode(_overwriteWord(envelope, 3, bytes32(uint256(6))));
        assertFalse(ok);
        (ok,,) = EffectReceiptV3.tryDecode(_overwriteWord(envelope, 8, bytes32(r.issuedAt)));
        assertFalse(ok);
        assertEq(signature.length, 64);
    }

    function test_rejectsInvalidAndHighSRawSignatures() public {
        EffectReceiptV3.Receipt memory r = _receipt(4);
        (bytes memory envelope, bytes memory signature) = _signed(r);
        EffectReceiptV3.Expected memory expected = _expected(r);
        (bool ok,) = EffectReceiptV3.verify(envelope, _publicKey(), expected, 1_050, false);
        assertTrue(ok);

        bytes memory tampered = envelope;
        tampered[tampered.length - 1] = bytes1(uint8(tampered[tampered.length - 1]) ^ 1);
        (ok,) = EffectReceiptV3.verify(tampered, _publicKey(), expected, 1_050, false);
        assertFalse(ok);

        bytes32 rWord;
        bytes32 sWord;
        assembly ("memory-safe") {
            rWord := mload(add(signature, 32))
            sWord := mload(add(signature, 64))
        }
        bytes memory highS = abi.encodePacked(rWord, bytes32(SECP256K1_N - 1));
        (ok,) = EffectReceiptV3.verify(_envelope(r, highS), _publicKey(), expected, 1_050, false);
        assertFalse(ok);

        bytes memory highR = abi.encodePacked(bytes32(SECP256K1_N), sWord);
        (ok,) = EffectReceiptV3.verify(_envelope(r, highR), _publicKey(), expected, 1_050, false);
        assertFalse(ok);
    }

    function test_historicalVerificationOnlyAllowsPurposesThreeThroughFive() public {
        for (uint256 purpose = 3; purpose <= 5; ++purpose) {
            EffectReceiptV3.Receipt memory r = _receipt(purpose);
            (bytes memory envelope,) = _signed(r);
            (bool ok,) = EffectReceiptV3.verify(envelope, _publicKey(), _expected(r), 1_200, true);
            assertTrue(ok);
            (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), _expected(r), 999, true);
            assertFalse(ok);
            (ok,) = EffectReceiptV3.verify(envelope, _publicKey(), _expected(r), 1_200, false);
            assertFalse(ok);
        }

        for (uint256 purpose = 1; purpose <= 2; ++purpose) {
            EffectReceiptV3.Receipt memory r = _receipt(purpose);
            (bytes memory envelope,) = _signed(r);
            (bool ok,) = EffectReceiptV3.verify(envelope, _publicKey(), _expected(r), 1_200, true);
            assertFalse(ok);
        }
    }
}
