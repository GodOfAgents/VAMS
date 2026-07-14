"""Small dependency-free Keccak-256 implementation for VDSO identifiers.

Python's :mod:`hashlib` exposes NIST SHA3-256, which has different padding and
must never be substituted for Ethereum-compatible Keccak-256.  The Rust
runtime remains the consensus reference; this implementation is a canary
mirror guarded by shared known-answer and cross-language vectors.
"""

from __future__ import annotations

from typing import Iterable, List


_MASK_64 = (1 << 64) - 1
_ROUND_CONSTANTS = (
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
)
_ROTATION_OFFSETS = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)


def _rotl64(value: int, amount: int) -> int:
    if amount == 0:
        return value & _MASK_64
    return ((value << amount) | (value >> (64 - amount))) & _MASK_64


def _permutation(state: List[int]) -> None:
    for round_constant in _ROUND_CONSTANTS:
        columns = [
            state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20]
            for x in range(5)
        ]
        deltas = [columns[(x - 1) % 5] ^ _rotl64(columns[(x + 1) % 5], 1) for x in range(5)]
        for y in range(5):
            for x in range(5):
                state[x + 5 * y] ^= deltas[x]

        rotated = [0] * 25
        for y in range(5):
            for x in range(5):
                rotated[y + 5 * ((2 * x + 3 * y) % 5)] = _rotl64(
                    state[x + 5 * y], _ROTATION_OFFSETS[x][y]
                )

        for y in range(5):
            row = rotated[5 * y : 5 * y + 5]
            for x in range(5):
                state[x + 5 * y] = (
                    row[x] ^ ((~row[(x + 1) % 5]) & row[(x + 2) % 5])
                ) & _MASK_64

        state[0] ^= round_constant


def keccak_256(data: bytes) -> bytes:
    """Return Ethereum-compatible Keccak-256 for *data*."""

    if not isinstance(data, bytes):
        raise TypeError("Keccak input must be bytes")

    rate = 136
    padded = bytearray(data)
    padded.append(0x01)
    padded.extend(b"\x00" * ((rate - (len(padded) % rate)) % rate))
    padded[-1] |= 0x80

    state = [0] * 25
    for offset in range(0, len(padded), rate):
        block = padded[offset : offset + rate]
        for lane in range(rate // 8):
            start = lane * 8
            state[lane] ^= int.from_bytes(block[start : start + 8], "little")
        _permutation(state)

    output = bytearray()
    while len(output) < 32:
        for lane in range(rate // 8):
            output.extend(state[lane].to_bytes(8, "little"))
            if len(output) >= 32:
                break
        if len(output) < 32:
            _permutation(state)
    return bytes(output[:32])


def domain_hash(domain: bytes, parts: Iterable[bytes]) -> bytes:
    """Hash an unambiguous length-delimited, domain-separated message."""

    if not domain or len(domain) > 255:
        raise ValueError("Hash domain must contain between 1 and 255 bytes")
    encoded = bytearray((len(domain),))
    encoded.extend(domain)
    for part in parts:
        if not isinstance(part, bytes):
            raise TypeError("Hash parts must be bytes")
        encoded.extend(len(part).to_bytes(4, "big"))
        encoded.extend(part)
    return keccak_256(bytes(encoded))
