// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Vm} from "forge-std/Vm.sol";
import {HeartbeatConsentV2 as Consent} from "../src/trust/HeartbeatConsentV2.sol";
import {HeartbeatPrincipalV1 as Principal} from "../src/trust/HeartbeatPrincipalV1.sol";
import {HeartbeatConsentSignaturesV2 as Signatures} from "../src/trust/HeartbeatConsentSignaturesV2.sol";

/// @dev Local verifier call surface only; it does not write registry or consent state.
contract HeartbeatConsentSignaturesV2Harness {
    function verify(
        bytes calldata baseRaw,
        bytes calldata witnessRaw,
        bytes calldata principalRaw,
        uint8 role,
        bytes calldata signature
    ) external view returns (bool) {
        return Signatures.verifyBodyKeySignature(baseRaw, witnessRaw, principalRaw, role, signature);
    }
    function verifyNormalRotationPair(
        bytes calldata baseRaw,
        bytes calldata witnessRaw,
        bytes calldata oldPrincipalRaw,
        bytes calldata proposedPrincipalRaw,
        bytes calldata oldSignature,
        bytes calldata newSignature
    ) external view returns (bool) {
        return Signatures.verifyNormalRotationSignaturePair(
            baseRaw, witnessRaw, oldPrincipalRaw, proposedPrincipalRaw, oldSignature, newSignature
        );
    }
}

contract HeartbeatConsentSignaturesV2Tests is Test {
    uint256 private constant N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
    string private constant DOMAIN = "VAMS:GATEWAY:HEARTBEAT-CONSENT-SIGNATURE:v2";
    HeartbeatConsentSignaturesV2Harness private harness;

    struct SignedPair {
        bytes baseRaw;
        bytes witnessRaw;
        bytes oldRaw;
        bytes newRaw;
        bytes oldSignature;
        bytes newSignature;
        uint256 newScalar;
    }

    function setUp() public {
        harness = new HeartbeatConsentSignaturesV2Harness();
    }

    function testNormalRotationRequiresOldAndNewBodyKeysForSameWitness() public {
        (bytes memory baseRaw, bytes memory witnessRaw, bytes memory oldRaw, bytes memory newRaw,
            uint256 oldScalar, uint256 newScalar) = _pair(Consent.MODE_ROTATE_NORMAL);
        bytes32 oldDigest = _signatureDigest(witnessRaw, Consent.ROLE_OLD_KEY);
        bytes32 newDigest = _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY);
        assertTrue(harness.verify(baseRaw, witnessRaw, oldRaw, Consent.ROLE_OLD_KEY, _sign(oldScalar, oldDigest)));
        assertTrue(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY, _sign(newScalar, newDigest)));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_OLD_KEY, _sign(newScalar, oldDigest)));
        assertFalse(harness.verify(baseRaw, witnessRaw, oldRaw, Consent.ROLE_NEW_KEY, _sign(oldScalar, newDigest)));
    }

    function testNormalRotationPairRequiresBothRoleSignaturesOverOneIntentAndWitness() public {
        SignedPair memory p = _signedPair(Consent.MODE_ROTATE_NORMAL);
        assertTrue(harness.verifyNormalRotationPair(p.baseRaw, p.witnessRaw, p.oldRaw, p.newRaw, p.oldSignature, p.newSignature));
        assertTrue(harness.verify(p.baseRaw, p.witnessRaw, p.oldRaw, Consent.ROLE_OLD_KEY, p.oldSignature));
        assertTrue(harness.verify(p.baseRaw, p.witnessRaw, p.newRaw, Consent.ROLE_NEW_KEY, p.newSignature));
        assertFalse(harness.verifyNormalRotationPair(p.baseRaw, p.witnessRaw, p.oldRaw, p.newRaw, new bytes(0), p.newSignature));
        assertFalse(harness.verifyNormalRotationPair(p.baseRaw, p.witnessRaw, p.oldRaw, p.newRaw, p.oldSignature, new bytes(64)));
        assertFalse(harness.verifyNormalRotationPair(p.baseRaw, p.witnessRaw, p.oldRaw, p.newRaw, p.newSignature, p.oldSignature));
        assertFalse(harness.verifyNormalRotationPair(p.baseRaw, p.witnessRaw, p.oldRaw, p.newRaw,
            _sign(4, _signatureDigest(p.witnessRaw, Consent.ROLE_OLD_KEY)), p.newSignature));
        assertFalse(harness.verifyNormalRotationPair(p.baseRaw, p.witnessRaw, p.oldRaw, p.newRaw,
            p.oldSignature, bytes.concat(p.newSignature, hex"00")));
    }

    function testNormalRotationPairRejectsSplitWitness() public {
        SignedPair memory p = _signedPair(Consent.MODE_ROTATE_NORMAL);
        (bool witnessOk, Consent.Witness memory changed) = Consent.tryDecodeWitness(p.witnessRaw);
        assertTrue(witnessOk);
        changed.operationId = bytes32(uint256(0x31));
        bytes memory changedWitness = Consent.canonicalWitnessBytes(changed);
        bytes memory splitNew = _sign(p.newScalar, _signatureDigest(changedWitness, Consent.ROLE_NEW_KEY));
        assertFalse(harness.verifyNormalRotationPair(
            p.baseRaw, changedWitness, p.oldRaw, p.newRaw, p.oldSignature, splitNew
        ));
    }

    function testNormalRotationPairRejectsEnrollmentAndRecoveryModes() public {
        uint8[2] memory modes = [Consent.MODE_ENROLL, Consent.MODE_RECOVER_LOST_KEY];
        for (uint256 i; i < modes.length; ++i) {
            SignedPair memory p = _signedPair(modes[i]);
            assertFalse(harness.verifyNormalRotationPair(
                p.baseRaw, p.witnessRaw, p.oldRaw, p.newRaw, p.oldSignature, p.newSignature
            ));
        }
    }
    function testEnrollmentAndRecoveryRequireNewKeyOnly() public {
        uint8[2] memory modes = [Consent.MODE_ENROLL, Consent.MODE_RECOVER_LOST_KEY];
        for (uint256 i; i < modes.length; ++i) {
            (bytes memory baseRaw, bytes memory witnessRaw, bytes memory oldRaw, bytes memory newRaw,
                uint256 oldScalar, uint256 newScalar) = _pair(modes[i]);
            assertTrue(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
                _sign(newScalar, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY))));
            assertFalse(harness.verify(baseRaw, witnessRaw, oldRaw, Consent.ROLE_OLD_KEY,
                _sign(oldScalar, _signatureDigest(witnessRaw, Consent.ROLE_OLD_KEY))));
        }
    }

    function testStatementDomainAlgorithmRoleAndSingleSha256() public {
        (bytes memory baseRaw, bytes memory witnessRaw,, bytes memory newRaw,, uint256 newScalar) =
            _pair(Consent.MODE_ENROLL);
        (bool ok, Consent.Witness memory witness) = Consent.tryDecodeWitness(witnessRaw);
        assertTrue(ok);
        bytes memory proposedStatement = abi.encodePacked(
            DOMAIN, hex"00", bytes1(uint8(1)), bytes1(Consent.ROLE_NEW_KEY), Consent.witnessDigest(witness)
        );
        bytes32 expectedDigest = sha256(proposedStatement);
        assertEq(_signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY), expectedDigest);
        assertTrue(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            _sign(newScalar, expectedDigest)));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            _sign(newScalar, sha256(abi.encodePacked(expectedDigest)))));
        assertNotEq(_signatureDigest(witnessRaw, Consent.ROLE_OLD_KEY), expectedDigest);
    }

    function testWrongKeysAndRolesCannotSubstitute() public {
        (bytes memory baseRaw, bytes memory witnessRaw, bytes memory oldRaw, bytes memory newRaw,
            uint256 oldScalar, uint256 newScalar) = _pair(Consent.MODE_ROTATE_NORMAL);
        Vm.Wallet memory unrelated = vm.createWallet(4);
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            _sign(oldScalar, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY))));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            _sign(4, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY))));
        assertFalse(harness.verify(baseRaw, witnessRaw, oldRaw, Consent.ROLE_NEW_KEY,
            _sign(oldScalar, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY))));
        assertTrue(unrelated.publicKeyX != 0 && newScalar != 0); // synthetic fixture keys only
    }

    function testWitnessMutationInvalidatesSignature() public {
        (bytes memory baseRaw, bytes memory witnessRaw,, bytes memory newRaw,, uint256 newScalar) =
            _pair(Consent.MODE_RECOVER_LOST_KEY);
        bytes memory signature = _sign(newScalar, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY));
        (bool ok, Consent.Witness memory witness) = Consent.tryDecodeWitness(witnessRaw);
        assertTrue(ok);
        witness.operationId = bytes32(uint256(0x31));
        bytes memory changedWitness = Consent.canonicalWitnessBytes(witness);
        assertFalse(harness.verify(baseRaw, changedWitness, newRaw, Consent.ROLE_NEW_KEY, signature));
    }

    function testBaseMutationAndReboundWitnessStillInvalidateSignature() public {
        (bytes memory baseRaw, bytes memory witnessRaw,, bytes memory newRaw,, uint256 newScalar) =
            _pair(Consent.MODE_ROTATE_NORMAL);
        bytes memory signature = _sign(newScalar, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY));
        (bool baseOk, Consent.BaseIntent memory base) = Consent.tryDecodeBase(baseRaw);
        (bool witnessOk, Consent.Witness memory witness) = Consent.tryDecodeWitness(witnessRaw);
        assertTrue(baseOk && witnessOk);
        base.consentNonce += 1;
        witness.baseIntentDigest = Consent.baseDigest(base);
        bytes memory changedBase = Consent.canonicalBaseBytes(base);
        bytes memory reboundWitness = Consent.canonicalWitnessBytes(witness);
        assertFalse(harness.verify(changedBase, reboundWitness, newRaw, Consent.ROLE_NEW_KEY, signature));
    }

    function testWrongRecordPolicyGenerationAndBadBodyPointReject() public {
        (bytes memory baseRaw, bytes memory witnessRaw, bytes memory oldRaw, bytes memory newRaw,, uint256 newScalar) =
            _pair(Consent.MODE_ROTATE_NORMAL);
        bytes memory signature = _sign(newScalar, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY));
        assertFalse(harness.verify(baseRaw, witnessRaw, oldRaw, Consent.ROLE_NEW_KEY, signature));
        (bool ok, Principal.Record memory record) = Principal.tryDecode(newRaw);
        assertTrue(ok);
        record.policyVersion += 1;
        assertFalse(harness.verify(baseRaw, witnessRaw, Principal.canonicalBytes(record), Consent.ROLE_NEW_KEY, signature));
        (ok, record) = Principal.tryDecode(newRaw);
        assertTrue(ok);
        record.principalGeneration += 1;
        assertFalse(harness.verify(baseRaw, witnessRaw, Principal.canonicalBytes(record), Consent.ROLE_NEW_KEY, signature));
        (bool baseOk, Consent.BaseIntent memory base) = Consent.tryDecodeBase(baseRaw);
        (bool witnessOk, Consent.Witness memory witness) = Consent.tryDecodeWitness(witnessRaw);
        assertTrue(baseOk && witnessOk);
        (ok, record) = Principal.tryDecode(newRaw);
        assertTrue(ok);
        record.bodyPublicKey = new bytes(64);
        base.proposedRecordDigest = Principal.digest(record);
        witness.baseIntentDigest = Consent.baseDigest(base);
        assertFalse(harness.verify(Consent.canonicalBaseBytes(base), Consent.canonicalWitnessBytes(witness),
            Principal.canonicalBytes(record), Consent.ROLE_NEW_KEY, signature));
    }

    function testMalformedWidthsAndHighSReject() public {
        (bytes memory baseRaw, bytes memory witnessRaw,, bytes memory newRaw,, uint256 newScalar) =
            _pair(Consent.MODE_ENROLL);
        bytes memory signature = _sign(newScalar, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY, new bytes(63)));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY, new bytes(65)));
        bytes32 digest = _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY);
        (, bytes32 r, bytes32 s) = vm.sign(newScalar, digest);
        uint256 lowS = uint256(s) > N / 2 ? N - uint256(s) : uint256(s);
        assertTrue(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            abi.encodePacked(r, bytes32(lowS))));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            abi.encodePacked(r, bytes32(N - lowS))));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            abi.encodePacked(r, bytes32(N - 1))));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            abi.encodePacked(bytes32(0), bytes32(lowS))));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            abi.encodePacked(bytes32(N), bytes32(lowS))));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, Consent.ROLE_NEW_KEY,
            abi.encodePacked(r, bytes32(N))));
        assertTrue(signature.length == 64);
    }

    function testMalformedCanonicalFramesAndOversizeInputsReturnFalse() public {
        (bytes memory baseRaw, bytes memory witnessRaw,, bytes memory newRaw,, uint256 newScalar) =
            _pair(Consent.MODE_ENROLL);
        bytes memory signature = _sign(newScalar, _signatureDigest(witnessRaw, Consent.ROLE_NEW_KEY));
        assertFalse(harness.verify(bytes.concat(baseRaw, hex"00"), witnessRaw, newRaw, Consent.ROLE_NEW_KEY, signature));
        assertFalse(harness.verify(baseRaw, bytes.concat(witnessRaw, hex"00"), newRaw, Consent.ROLE_NEW_KEY, signature));
        assertFalse(harness.verify(baseRaw, witnessRaw, bytes.concat(newRaw, hex"00"), Consent.ROLE_NEW_KEY, signature));
        assertFalse(harness.verify(new bytes(1025), witnessRaw, newRaw, Consent.ROLE_NEW_KEY, signature));
        assertFalse(harness.verify(baseRaw, new bytes(1025), newRaw, Consent.ROLE_NEW_KEY, signature));
        assertFalse(harness.verify(baseRaw, witnessRaw, new bytes(1025), Consent.ROLE_NEW_KEY, signature));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, 0, signature));
        assertFalse(harness.verify(baseRaw, witnessRaw, newRaw, 3, signature));
    }

    function testValidSignatureDoesNotAuthenticateInventedChallengeOrNativeFacts() public {
        (bytes memory baseRaw, bytes memory witnessRaw,, bytes memory newRaw,, uint256 newScalar) =
            _pair(Consent.MODE_RECOVER_LOST_KEY);
        (bool ok, Consent.Witness memory witness) = Consent.tryDecodeWitness(witnessRaw);
        assertTrue(ok);
        witness.operationId = bytes32(0);
        witness.postEtaChallengeCommitment = bytes32(0);
        bytes memory untrustedWitness = Consent.canonicalWitnessBytes(witness);
        assertTrue(harness.verify(baseRaw, untrustedWitness, newRaw, Consent.ROLE_NEW_KEY,
            _sign(newScalar, _signatureDigest(untrustedWitness, Consent.ROLE_NEW_KEY))));
        // This library returns a signature check only; no actual operation, clock, store, or authority is supplied.
    }

    function _signedPair(uint8 mode) private returns (SignedPair memory p) {
        uint256 oldScalar;
        (p.baseRaw, p.witnessRaw, p.oldRaw, p.newRaw, oldScalar, p.newScalar) = _pair(mode);
        p.oldSignature = _sign(oldScalar, _signatureDigest(p.witnessRaw, Consent.ROLE_OLD_KEY));
        p.newSignature = _sign(p.newScalar, _signatureDigest(p.witnessRaw, Consent.ROLE_NEW_KEY));
    }

    function _pair(uint8 mode) private returns (
        bytes memory baseRaw, bytes memory witnessRaw, bytes memory oldRaw, bytes memory newRaw,
        uint256 oldScalar, uint256 newScalar
    ) {
        oldScalar = 1;
        newScalar = 2;
        Vm.Wallet memory oldWallet = vm.createWallet(oldScalar);
        Vm.Wallet memory newWallet = vm.createWallet(newScalar);
        Principal.Record memory oldRecord = _record(oldWallet, 4);
        Principal.Record memory newRecord = _record(newWallet, mode == Consent.MODE_ENROLL ? 1 : 5);
        Consent.BaseIntent memory base;
        base.mode = mode;
        base.sourceScheme = 1;
        base.authoritySourceDigest = bytes32(uint256(0x10));
        base.timelockAddress = address(uint160(0x2020202020202020202020202020202020202020));
        base.timelockCodeHash = bytes32(uint256(0x21));
        base.authorityConfigDigest = bytes32(uint256(0x22));
        base.authorityChangeSequence = 9;
        base.policyRoot = newRecord.policyRoot;
        base.policyVersion = newRecord.policyVersion;
        base.authorityEpoch = newRecord.authorityEpoch;
        base.principalId = newRecord.principalId;
        base.proposedRecordDigest = Principal.digest(newRecord);
        base.expectedRecordDigest = mode == Consent.MODE_ENROLL ? bytes32(0) : Principal.digest(oldRecord);
        base.expectedGeneration = mode == Consent.MODE_ENROLL ? 0 : 4;
        base.proposedGeneration = newRecord.principalGeneration;
        base.consentNonce = 8;
        base.timelockPredecessor = bytes32(uint256(0x23));
        base.timelockSalt = bytes32(uint256(0x24));
        Consent.Witness memory witness;
        witness.baseIntentDigest = Consent.baseDigest(base);
        witness.operationId = bytes32(uint256(0x25));
        witness.queuedEta = 172800;
        witness.postEtaChallengeCommitment = bytes32(uint256(0x26));
        witness.issuedAt = 172801;
        witness.expiresAt = 172900;
        witness.mode = mode;
        if (mode == Consent.MODE_ROTATE_NORMAL) {
            witness.requiredRoleMask = Consent.ROLE_MASK_ROTATE_NORMAL;
        } else if (mode == Consent.MODE_ENROLL) {
            witness.requiredRoleMask = Consent.ROLE_MASK_ENROLL;
        } else {
            witness.requiredRoleMask = Consent.ROLE_MASK_RECOVER_LOST_KEY;
        }
        baseRaw = Consent.canonicalBaseBytes(base);
        witnessRaw = Consent.canonicalWitnessBytes(witness);
        oldRaw = Principal.canonicalBytes(oldRecord);
        newRaw = Principal.canonicalBytes(newRecord);
    }

    function _record(Vm.Wallet memory bodyWallet, uint64 generation)
        private returns (Principal.Record memory record)
    {
        Vm.Wallet memory m2Wallet = vm.createWallet(3);
        bytes memory bodyKey = _publicKey(bodyWallet);
        bytes memory m2Key = _publicKey(m2Wallet);
        record.principalId = Principal.principalIdFor(bytes32(uint256(5)), bytes32(uint256(6)), bytes32(uint256(7)));
        record.nodeIdCommitment = bytes32(uint256(7));
        record.m2SignerDid = string(abi.encodePacked("did:key:", _hex(m2Key)));
        record.m2SignerPublicKey = m2Key;
        record.certificateFingerprint = bytes32(uint256(3));
        record.bodyPublicKey = bodyKey;
        record.hostDomain = bytes32(uint256(5));
        record.serviceDomain = bytes32(uint256(6));
        record.audience = "gateway.testnet";
        record.method = "POST";
        record.path = "/heartbeat";
        record.query = bytes("");
        record.policyRoot = bytes32(uint256(7));
        record.policyVersion = 3;
        record.authorityEpoch = 11;
        record.principalGeneration = generation;
        record.notBefore = 1700000000;
        record.expiresAt = 1700000300;
    }

    function _publicKey(Vm.Wallet memory wallet) private pure returns (bytes memory) {
        return abi.encodePacked(bytes32(wallet.publicKeyX), bytes32(wallet.publicKeyY));
    }

    function _hex(bytes memory raw) private pure returns (bytes memory out) {
        bytes memory alphabet = bytes("0123456789abcdef");
        out = new bytes(raw.length * 2);
        for (uint256 i; i < raw.length; ++i) {
            uint8 value = uint8(raw[i]);
            out[i * 2] = alphabet[value >> 4];
            out[i * 2 + 1] = alphabet[value & 0x0f];
        }
    }

    function _signatureDigest(bytes memory witnessRaw, uint8 role) private pure returns (bytes32) {
        (bool ok, Consent.Witness memory witness) = Consent.tryDecodeWitness(witnessRaw);
        require(ok, "fixture witness must decode");
        return sha256(abi.encodePacked(DOMAIN, hex"00", bytes1(uint8(1)), bytes1(role), Consent.witnessDigest(witness)));
    }

    function _sign(uint256 scalar, bytes32 digest) private returns (bytes memory) {
        (, bytes32 r, bytes32 s) = vm.sign(scalar, digest);
        uint256 lowS = uint256(s) > N / 2 ? N - uint256(s) : uint256(s);
        return abi.encodePacked(r, bytes32(lowS));
    }


    function testIndependentLiteralEnrollmentNew() public {
        bytes memory witnessRaw = hex"56414d533a474154455741593a4845415254424541542d434f4e53454e542d5749544e4553533a7632000008010020852d7f587dee5d780ce44e33873ec0a005dc1f00bdefa4a9fb807b30e487ecce0200202525252525252525252525252525252525252525252525252525252525252525030008000000000002a3000400202626262626262626262626262626262626262626262626262626262626262626050008000000000002a301060008000000000002a3640700010108000102";
        assertEq(_signatureDigest(witnessRaw, 2), hex"10b5453692592b58060527611b91cf651136ba89eb4a67e79b30d152eafab0f0");
        assertTrue(harness.verify(hex"56414d533a474154455741593a4845415254424541542d434f4e53454e542d424153453a7632000012010001010200010103002010101010101010101010101010101010101010101010101010101010101010100400142020202020202020202020202020202020202020050020212121212121212121212121212121212121212121212121212121212121212106002022222222222222222222222222222222222222222222222222222222222222220700080000000000000009080020070707070707070707070707070707070707070707070707070707070707070709000800000000000000030a0008000000000000000b0b002002a7b4075a07dedd81f11b9ab38f30b67c76a67c19d856d7234a75f0f79614890c00208c99839373585b0dbdbe5cb4125fa0cd89f0236134261652e1621c58c3739c200d002000000000000000000000000000000000000000000000000000000000000000000e000800000000000000000f00080000000000000001100008000000000000000811002023232323232323232323232323232323232323232323232323232323232323231200202424242424242424242424242424242424242424242424242424242424242424", witnessRaw, hex"56414d533a474154455741593a4845415254424541542d5052494e434950414c3a763100001201002002a7b4075a07dedd81f11b9ab38f30b67c76a67c19d856d7234a75f0f7961489020020963d7cbc840749cd78eea0ab7ef6af94e31e9cbd1ec38a75b8f805bffcd72bf10300886469643a6b65793a6639333038613031393235386333313034393334346638356638396435323239623533316338343538333666393962303836303166313133626365303336663933383866376230663633326465383134306665333337653632613337663335363635303061393939333463323233316236636239666437353834623865363732040040f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9388f7b0f632de8140fe337e62a37f3566500a99934c2231b6cb9fd7584b8e6720500200303030303030303030303030303030303030303030303030303030303030303060040c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee51ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a0700200505050505050505050505050505050505050505050505050505050505050505080020060606060606060606060606060606060606060606060606060606060606060609000f676174657761792e746573746e65740a0004504f53540b000a2f6865617274626561740c00000d002007070707070707070707070707070707070707070707070707070707070707070e000800000000000000030f0008000000000000000b1000080000000000000001110008000000006553f100120008000000006553f22c", 2, hex"796271c9c4e85d0f31b7dd52d0eb607d38e8c9492a11e696a772d7e0801d153949ef91a1a90a26798773a189f589ea4b871dadddafb0d37312a00e1583a45800"));
    }
    function testIndependentLiteralNormalOld() public {
        bytes memory witnessRaw = hex"56414d533a474154455741593a4845415254424541542d434f4e53454e542d5749544e4553533a763200000801002092fe065d9b122c35a2e64bb9cee353e718bbeede7ba91f6c5b70a3c0a080b07e0200202525252525252525252525252525252525252525252525252525252525252525030008000000000002a3000400202626262626262626262626262626262626262626262626262626262626262626050008000000000002a301060008000000000002a3640700010208000103";
        assertEq(_signatureDigest(witnessRaw, 1), hex"dfef8c8fec8f357ddfe497e9a37cd3bbc0e1973769076443ea4f9be8ca563b79");
        assertTrue(harness.verify(hex"56414d533a474154455741593a4845415254424541542d434f4e53454e542d424153453a7632000012010001020200010103002010101010101010101010101010101010101010101010101010101010101010100400142020202020202020202020202020202020202020050020212121212121212121212121212121212121212121212121212121212121212106002022222222222222222222222222222222222222222222222222222222222222220700080000000000000009080020070707070707070707070707070707070707070707070707070707070707070709000800000000000000030a0008000000000000000b0b002002a7b4075a07dedd81f11b9ab38f30b67c76a67c19d856d7234a75f0f79614890c0020548fd7183d8a9c8147cc55d8ced92403024ce612492eaeaa122b37cbb2032ff80d00206599c8d6f6d52a34c462727f8c0a90cc0e85c85705dadd948f5f8e73828977ac0e000800000000000000040f00080000000000000005100008000000000000000811002023232323232323232323232323232323232323232323232323232323232323231200202424242424242424242424242424242424242424242424242424242424242424", witnessRaw, hex"56414d533a474154455741593a4845415254424541542d5052494e434950414c3a763100001201002002a7b4075a07dedd81f11b9ab38f30b67c76a67c19d856d7234a75f0f7961489020020963d7cbc840749cd78eea0ab7ef6af94e31e9cbd1ec38a75b8f805bffcd72bf10300886469643a6b65793a6639333038613031393235386333313034393334346638356638396435323239623533316338343538333666393962303836303166313133626365303336663933383866376230663633326465383134306665333337653632613337663335363635303061393939333463323233316236636239666437353834623865363732040040f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9388f7b0f632de8140fe337e62a37f3566500a99934c2231b6cb9fd7584b8e672050020030303030303030303030303030303030303030303030303030303030303030306004079be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b80700200505050505050505050505050505050505050505050505050505050505050505080020060606060606060606060606060606060606060606060606060606060606060609000f676174657761792e746573746e65740a0004504f53540b000a2f6865617274626561740c00000d002007070707070707070707070707070707070707070707070707070707070707070e000800000000000000030f0008000000000000000b1000080000000000000004110008000000006553f100120008000000006553f22c", 1, hex"671ab63a240d8a6ae38ec9dd9bb36dfceea43e4d4885980ef908c6774f18c7d35da33a9559f65dd9656b2e7ac2fb38875a224030a366e830e8eae5c17e190435"));
    }
    function testIndependentLiteralNormalNew() public {
        bytes memory witnessRaw = hex"56414d533a474154455741593a4845415254424541542d434f4e53454e542d5749544e4553533a763200000801002092fe065d9b122c35a2e64bb9cee353e718bbeede7ba91f6c5b70a3c0a080b07e0200202525252525252525252525252525252525252525252525252525252525252525030008000000000002a3000400202626262626262626262626262626262626262626262626262626262626262626050008000000000002a301060008000000000002a3640700010208000103";
        assertEq(_signatureDigest(witnessRaw, 2), hex"cc7817f94540b3e07876468d0227e9cb9251c6d11e9c13d775dae8bc6b06e989");
        assertTrue(harness.verify(hex"56414d533a474154455741593a4845415254424541542d434f4e53454e542d424153453a7632000012010001020200010103002010101010101010101010101010101010101010101010101010101010101010100400142020202020202020202020202020202020202020050020212121212121212121212121212121212121212121212121212121212121212106002022222222222222222222222222222222222222222222222222222222222222220700080000000000000009080020070707070707070707070707070707070707070707070707070707070707070709000800000000000000030a0008000000000000000b0b002002a7b4075a07dedd81f11b9ab38f30b67c76a67c19d856d7234a75f0f79614890c0020548fd7183d8a9c8147cc55d8ced92403024ce612492eaeaa122b37cbb2032ff80d00206599c8d6f6d52a34c462727f8c0a90cc0e85c85705dadd948f5f8e73828977ac0e000800000000000000040f00080000000000000005100008000000000000000811002023232323232323232323232323232323232323232323232323232323232323231200202424242424242424242424242424242424242424242424242424242424242424", witnessRaw, hex"56414d533a474154455741593a4845415254424541542d5052494e434950414c3a763100001201002002a7b4075a07dedd81f11b9ab38f30b67c76a67c19d856d7234a75f0f7961489020020963d7cbc840749cd78eea0ab7ef6af94e31e9cbd1ec38a75b8f805bffcd72bf10300886469643a6b65793a6639333038613031393235386333313034393334346638356638396435323239623533316338343538333666393962303836303166313133626365303336663933383866376230663633326465383134306665333337653632613337663335363635303061393939333463323233316236636239666437353834623865363732040040f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9388f7b0f632de8140fe337e62a37f3566500a99934c2231b6cb9fd7584b8e6720500200303030303030303030303030303030303030303030303030303030303030303060040c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee51ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a0700200505050505050505050505050505050505050505050505050505050505050505080020060606060606060606060606060606060606060606060606060606060606060609000f676174657761792e746573746e65740a0004504f53540b000a2f6865617274626561740c00000d002007070707070707070707070707070707070707070707070707070707070707070e000800000000000000030f0008000000000000000b1000080000000000000005110008000000006553f100120008000000006553f22c", 2, hex"c7a542c0557eeec497de372cc1ba309fef0f4eeb0ab2ff2daad6aa97a10ea3f76a624cafe1100677dbe86b74291c9e46cc27cee49656d04830ebb5f74fdbd25c"));
    }
    function testIndependentLiteralRecoveryNew() public {
        bytes memory witnessRaw = hex"56414d533a474154455741593a4845415254424541542d434f4e53454e542d5749544e4553533a7632000008010020070e3f16631c561347bbc9d59a7554ea56f4c81ec9192652bf28f64b1e8e39420200202525252525252525252525252525252525252525252525252525252525252525030008000000000002a3000400202626262626262626262626262626262626262626262626262626262626262626050008000000000002a301060008000000000002a3640700010308000102";
        assertEq(_signatureDigest(witnessRaw, 2), hex"1c3b4334a88e94cc76ae43c0c3389f4df8b52eda09cdca436879f24c16650166");
        assertTrue(harness.verify(hex"56414d533a474154455741593a4845415254424541542d434f4e53454e542d424153453a7632000012010001030200010103002010101010101010101010101010101010101010101010101010101010101010100400142020202020202020202020202020202020202020050020212121212121212121212121212121212121212121212121212121212121212106002022222222222222222222222222222222222222222222222222222222222222220700080000000000000009080020070707070707070707070707070707070707070707070707070707070707070709000800000000000000030a0008000000000000000b0b002002a7b4075a07dedd81f11b9ab38f30b67c76a67c19d856d7234a75f0f79614890c0020548fd7183d8a9c8147cc55d8ced92403024ce612492eaeaa122b37cbb2032ff80d00206599c8d6f6d52a34c462727f8c0a90cc0e85c85705dadd948f5f8e73828977ac0e000800000000000000040f00080000000000000005100008000000000000000811002023232323232323232323232323232323232323232323232323232323232323231200202424242424242424242424242424242424242424242424242424242424242424", witnessRaw, hex"56414d533a474154455741593a4845415254424541542d5052494e434950414c3a763100001201002002a7b4075a07dedd81f11b9ab38f30b67c76a67c19d856d7234a75f0f7961489020020963d7cbc840749cd78eea0ab7ef6af94e31e9cbd1ec38a75b8f805bffcd72bf10300886469643a6b65793a6639333038613031393235386333313034393334346638356638396435323239623533316338343538333666393962303836303166313133626365303336663933383866376230663633326465383134306665333337653632613337663335363635303061393939333463323233316236636239666437353834623865363732040040f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9388f7b0f632de8140fe337e62a37f3566500a99934c2231b6cb9fd7584b8e6720500200303030303030303030303030303030303030303030303030303030303030303060040c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee51ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a0700200505050505050505050505050505050505050505050505050505050505050505080020060606060606060606060606060606060606060606060606060606060606060609000f676174657761792e746573746e65740a0004504f53540b000a2f6865617274626561740c00000d002007070707070707070707070707070707070707070707070707070707070707070e000800000000000000030f0008000000000000000b1000080000000000000005110008000000006553f100120008000000006553f22c", 2, hex"7a041f3498babda494a28345adaa2cc48e331ad4792135e00d6434382b7861cf617dec7aaff06990f25bd65db740fcd5a2cf65462dba1a00e61544f978094acd"));
    }
}


