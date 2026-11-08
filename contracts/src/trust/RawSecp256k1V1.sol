// SPDX-License-Identifier: MIT
// Adapted from OpenZeppelin Contracts v5.3.0 P256.sol (source SHA-256:
// 0d7bb2f2b5e0ceb0e1a28523ee179c1aee5980cb793df739dd9ccf87170dffe2).
// Copyright (c) 2016-2025 the respective authors.
pragma solidity ^0.8.20;

import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";

/// @notice Full-key secp256k1 verification for the existing raw r||s / x||y wire format.
/// @dev New, unaudited arithmetic adaptation. It verifies a supplied SHA-256 digest only;
///      callers must construct and hash the exact consent preimage. It grants no authority.
library RawSecp256k1V1 {
    struct JPoint {
        uint256 x;
        uint256 y;
        uint256 z;
    }

    // SEC 2 secp256k1 domain parameters. P is the coordinate field modulus; N is the
    // prime subgroup order. Keep field and scalar arithmetic separated throughout.
    uint256 internal constant GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798;
    uint256 internal constant GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8;
    uint256 internal constant P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F;
    uint256 internal constant N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
    uint256 private constant B = 7;
    uint256 private constant HALF_N = N / 2;

    /// @notice Verify an already-computed 32-byte SHA-256 digest against full raw public-key bytes.
    /// @dev publicKey is exactly x||y; signature is exactly r||s. No prefix, recovery byte,
    ///      DER, ERC-2098 packing, address truncation, or alternative hash is accepted.
    function verifyDigest(bytes32 digest, bytes memory publicKey, bytes memory signature)
        internal view returns (bool)
    {
        if (publicKey.length != 64 || signature.length != 64) return false;

        bytes32 r;
        bytes32 s;
        bytes32 qx;
        bytes32 qy;
        assembly ("memory-safe") {
            r := mload(add(signature, 0x20))
            s := mload(add(signature, 0x40))
            qx := mload(add(publicKey, 0x20))
            qy := mload(add(publicKey, 0x40))
        }
        if (!_isProperSignature(r, s) || !isValidPublicKey(qx, qy)) return false;
        if (!_hasModExp()) return false;

        JPoint[16] memory points = _preComputeJacobianPoints(uint256(qx), uint256(qy));
        (bool inverseOk, uint256 w) = _tryInverse(uint256(s), N);
        if (!inverseOk) return false;

        // ECDSA uses e as an integer reduced modulo N by the multiplication below.
        uint256 u1 = mulmod(uint256(digest), w, N);
        uint256 u2 = mulmod(uint256(r), w, N);
        (bool finite, uint256 x, ) = _jMultShamir(points, u1, u2);
        return finite && x % N == uint256(r);
    }

    /// @notice Bounded calldata entrypoint; rejects wrong widths before copying to memory.
    function verifyDigestCalldata(bytes32 digest, bytes calldata publicKey, bytes calldata signature)
        internal view returns (bool)
    {
        if (publicKey.length != 64 || signature.length != 64) return false;
        return verifyDigest(digest, publicKey, signature);
    }

    /// @notice Check that (x,y) is a finite affine secp256k1 point.
    function isValidPublicKey(bytes32 x, bytes32 y) internal pure returns (bool result) {
        assembly ("memory-safe") {
            let p := P
            let lhs := mulmod(y, y, p)
            // secp256k1 is y^2 = x^3 + 7 (A=0); coordinates must be canonical field elements.
            let rhs := addmod(mulmod(mulmod(x, x, p), x, p), B, p)
            result := and(and(lt(x, p), lt(y, p)), eq(lhs, rhs))
        }
    }

    function _isProperSignature(bytes32 r, bytes32 s) private pure returns (bool) {
        return uint256(r) > 0 && uint256(r) < N && uint256(s) > 0 && uint256(s) <= HALF_N;
    }

    /// @dev Require an actual 32-byte MODEXP result before using Math.tryModExp.
    ///      A call to an empty address can succeed with no returndata and stale output memory.
    function _hasModExp() private view returns (bool supported) {
        bytes memory input = abi.encode(uint256(32), uint256(32), uint256(32), uint256(2), uint256(1), uint256(3));
        bytes memory output = new bytes(32);
        uint256 returnLength;
        assembly ("memory-safe") {
            let success := staticcall(gas(), 0x05, add(input, 0x20), mload(input), add(output, 0x20), 0x20)
            returnLength := returndatasize()
            supported := and(success, eq(returnLength, 0x20))
        }
        return supported && abi.decode(output, (uint256)) == 2;
    }
    /// @dev MODEXP at 0x05 is not assumed available. The product check also rejects the
    ///      empty-precompile success/zero-output behavior documented by OpenZeppelin Math.
    function _tryInverse(uint256 value, uint256 modulus) private view returns (bool ok, uint256 inverse) {
        if (value == 0 || modulus <= 2) return (false, 0);
        (ok, inverse) = Math.tryModExp(value, modulus - 2, modulus);
        if (!ok || mulmod(value, inverse, modulus) != 1) return (false, 0);
    }

    /// @dev Convert Jacobian to affine and reject infinity or unsupported/incorrect MODEXP output.
    function _affineFromJacobian(uint256 jx, uint256 jy, uint256 jz)
        private view returns (bool finite, uint256 ax, uint256 ay)
    {
        if (jz == 0) return (false, 0, 0);
        (bool inverseOk, uint256 zinv) = _tryInverse(jz, P);
        if (!inverseOk) return (false, 0, 0);
        uint256 p = P;
        assembly ("memory-safe") {
            let zzinv := mulmod(zinv, zinv, p)
            ax := mulmod(jx, zzinv, p)
            ay := mulmod(jy, mulmod(zzinv, zinv, p), p)
        }
        return (true, ax, ay);
    }

    /// @dev Jacobian addition. Equality is dispatched after the equal-point test's
    ///      temporary arithmetic is out of scope, keeping the generic Yul path bounded.
    ///      Opposite points stay in the generic path and produce z=0 (infinity).
    function _jAdd(JPoint memory p1, uint256 x2, uint256 y2, uint256 z2)
        private pure returns (uint256 rx, uint256 ry, uint256 rz)
    {
        if (_samePoint(p1, x2, y2, z2)) return _jDouble(x2, y2, z2);
        return _jAddUnequal(p1, x2, y2, z2);
    }

    function _samePoint(JPoint memory p1, uint256 x2, uint256 y2, uint256 z2)
        private pure returns (bool equal)
    {
        assembly ("memory-safe") {
            let p := P
            let z1 := mload(add(p1, 0x40))
            let zz1 := mulmod(z1, z1, p)
            let z2sq := mulmod(z2, z2, p)
            let s1 := mulmod(mload(add(p1, 0x20)), mulmod(z2sq, z2, p), p)
            let r := addmod(mulmod(y2, mulmod(zz1, z1, p), p), sub(p, s1), p)
            let u1 := mulmod(mload(p1), z2sq, p)
            let h := addmod(mulmod(x2, zz1, p), sub(p, u1), p)
            equal := and(iszero(r), iszero(h))
        }
    }

    function _jAddUnequal(JPoint memory p1, uint256 x2, uint256 y2, uint256 z2)
        private pure returns (uint256 rx, uint256 ry, uint256 rz)
    {
        assembly ("memory-safe") {
            let p := P
            let z1 := mload(add(p1, 0x40))
            let zz1 := mulmod(z1, z1, p)
            let z2sq := mulmod(z2, z2, p)
            let s1 := mulmod(mload(add(p1, 0x20)), mulmod(z2sq, z2, p), p)
            let r := addmod(mulmod(y2, mulmod(zz1, z1, p), p), sub(p, s1), p)
            let u1 := mulmod(mload(p1), z2sq, p)
            let h := addmod(mulmod(x2, zz1, p), sub(p, u1), p)
            let hh := mulmod(h, h, p)
            rx := addmod(
                addmod(mulmod(r, r, p), sub(p, mulmod(h, hh, p)), p),
                sub(p, mulmod(2, mulmod(u1, hh, p), p)),
                p
            )
            ry := addmod(
                mulmod(r, addmod(mulmod(u1, hh, p), sub(p, rx), p), p),
                sub(p, mulmod(s1, mulmod(h, hh, p), p)),
                p
            )
            rz := mulmod(h, mulmod(z1, z2, p), p)
        }
    }
    /// @dev Jacobian doubling specialized for y^2=x^3+7, so m=3*x^2.
    function _jDouble(uint256 x, uint256 y, uint256 z)
        private pure returns (uint256 rx, uint256 ry, uint256 rz)
    {
        assembly ("memory-safe") {
            let p := P
            let yy := mulmod(y, y, p)
            let m := mulmod(3, mulmod(x, x, p), p)
            let ss := mulmod(4, mulmod(x, yy, p), p)
            rx := addmod(mulmod(m, m, p), sub(p, mulmod(2, ss, p)), p)
            ry := addmod(mulmod(m, addmod(ss, sub(p, rx), p), p), sub(p, mulmod(8, mulmod(yy, yy, p), p)), p)
            rz := mulmod(2, mulmod(y, z, p), p)
        }
    }

    /// @dev Strauss/Shamir double-scalar multiplication G*u1 + Q*u2, consuming 2 bits/round.
    function _jMultShamir(JPoint[16] memory points, uint256 u1, uint256 u2)
        private view returns (bool finite, uint256 x, uint256 y)
    {
        uint256 z;
        unchecked {
            for (uint256 i = 0; i < 128; ++i) {
                if (z > 0) {
                    (x, y, z) = _jDouble(x, y, z);
                    (x, y, z) = _jDouble(x, y, z);
                }
                uint256 pos = ((u1 >> 252) & 0xc) | ((u2 >> 254) & 0x3);
                if (points[pos].z != 0) {
                    if (z == 0) {
                        (x, y, z) = (points[pos].x, points[pos].y, points[pos].z);
                    } else {
                        (x, y, z) = _jAdd(points[pos], x, y, z);
                    }
                }
                u1 <<= 2;
                u2 <<= 2;
            }
        }
        return _affineFromJacobian(x, y, z);
    }

    /// @dev Precompute 0..3 multiples of Q and G. A valid affine Q and secp256k1's
    ///      prime-order cofactor-one group make Q,2Q,3Q and G,2G,3G non-infinity.
    function _preComputeJacobianPoints(uint256 qx, uint256 qy)
        private pure returns (JPoint[16] memory points)
    {
        points[0x00] = JPoint(0, 0, 0);
        points[0x01] = JPoint(qx, qy, 1);
        points[0x04] = JPoint(GX, GY, 1);
        points[0x02] = _jDoublePoint(points[0x01]);
        points[0x08] = _jDoublePoint(points[0x04]);
        points[0x03] = _jAddPoint(points[0x01], points[0x02]);
        points[0x05] = _jAddPoint(points[0x01], points[0x04]);
        points[0x06] = _jAddPoint(points[0x02], points[0x04]);
        points[0x07] = _jAddPoint(points[0x03], points[0x04]);
        points[0x09] = _jAddPoint(points[0x01], points[0x08]);
        points[0x0a] = _jAddPoint(points[0x02], points[0x08]);
        points[0x0b] = _jAddPoint(points[0x03], points[0x08]);
        points[0x0c] = _jAddPoint(points[0x04], points[0x08]);
        points[0x0d] = _jAddPoint(points[0x01], points[0x0c]);
        points[0x0e] = _jAddPoint(points[0x02], points[0x0c]);
        points[0x0f] = _jAddPoint(points[0x03], points[0x0c]);
    }

    function _jAddPoint(JPoint memory p1, JPoint memory p2) private pure returns (JPoint memory) {
        (uint256 x, uint256 y, uint256 z) = _jAdd(p1, p2.x, p2.y, p2.z);
        return JPoint(x, y, z);
    }

    function _jDoublePoint(JPoint memory point) private pure returns (JPoint memory) {
        (uint256 x, uint256 y, uint256 z) = _jDouble(point.x, point.y, point.z);
        return JPoint(x, y, z);
    }
}