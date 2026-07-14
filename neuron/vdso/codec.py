"""Restricted deterministic CBOR shared with ``vir-codec``.

The consensus subset contains only unsigned 64-bit integers, byte strings,
and definite positional arrays.  Text, maps, tags, floats, booleans, null,
negative integers, indefinite lengths, and non-minimal integer forms are not
part of the VIR-Core wire language.
"""

from __future__ import annotations

from typing import Any, Iterable


MAX_UINT64 = (1 << 64) - 1


class CanonicalEncodingError(ValueError):
    """Raised when a value is outside the VDSO canonical CBOR subset."""


def _head(major: int, value: int) -> bytes:
    if value < 0 or value > MAX_UINT64:
        raise CanonicalEncodingError("CBOR integer argument is outside uint64")
    prefix = major << 5
    if value < 24:
        return bytes((prefix | value,))
    if value <= 0xFF:
        return bytes((prefix | 24, value))
    if value <= 0xFFFF:
        return bytes((prefix | 25,)) + value.to_bytes(2, "big")
    if value <= 0xFFFFFFFF:
        return bytes((prefix | 26,)) + value.to_bytes(4, "big")
    return bytes((prefix | 27,)) + value.to_bytes(8, "big")


def encode(value: Any) -> bytes:
    """Encode one value using the exact VIR-Core consensus CBOR subset."""

    # ``bool`` is an ``int`` subclass in Python and must be rejected first.
    if isinstance(value, bool):
        raise CanonicalEncodingError("booleans are forbidden in VIR-Core CBOR")
    if isinstance(value, int):
        if value < 0:
            raise CanonicalEncodingError("negative integers are forbidden in VIR-Core CBOR")
        return _head(0, value)
    if isinstance(value, bytes):
        return _head(2, len(value)) + value
    if isinstance(value, (tuple, list)):
        return _head(4, len(value)) + b"".join(encode(item) for item in value)
    raise CanonicalEncodingError(f"unsupported canonical type: {type(value).__name__}")


def encode_array(items: Iterable[Any]) -> bytes:
    """Encode an iterable as a fixed-length canonical CBOR array."""

    return encode(tuple(items))


class _Decoder:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def _read(self, length: int) -> bytes:
        end = self.offset + length
        if end > len(self.data):
            raise CanonicalEncodingError("truncated VIR-Core CBOR")
        value = self.data[self.offset : end]
        self.offset = end
        return value

    def _argument(self, additional: int) -> int:
        if additional <= 23:
            return additional
        lengths = {24: 1, 25: 2, 26: 4, 27: 8}
        length = lengths.get(additional)
        if length is None:
            raise CanonicalEncodingError("indefinite or reserved CBOR length is forbidden")
        value = int.from_bytes(self._read(length), "big")
        minimum = {1: 24, 2: 1 << 8, 4: 1 << 16, 8: 1 << 32}[length]
        if value < minimum:
            raise CanonicalEncodingError("non-minimal CBOR integer encoding")
        return value

    def value(self, *, depth: int = 0) -> Any:
        if depth > 32:
            raise CanonicalEncodingError("VIR-Core CBOR nesting exceeds 32 levels")
        initial = self._read(1)[0]
        major = initial >> 5
        argument = self._argument(initial & 0x1F)
        if major == 0:
            return argument
        if major == 2:
            if argument > 1_048_576:
                raise CanonicalEncodingError("VIR-Core byte string exceeds 1 MiB")
            return self._read(argument)
        if major == 4:
            if argument > 1_024:
                raise CanonicalEncodingError("VIR-Core array exceeds 1,024 items")
            return tuple(self.value(depth=depth + 1) for _ in range(argument))
        raise CanonicalEncodingError(
            "VIR-Core CBOR permits only unsigned integers, bytes, and arrays"
        )


def decode(data: bytes) -> Any:
    """Decode one canonical value from the exact VIR-Core CBOR subset."""

    if not isinstance(data, bytes):
        raise CanonicalEncodingError("VIR-Core CBOR input must be bytes")
    decoder = _Decoder(data)
    value = decoder.value()
    if decoder.offset != len(data):
        raise CanonicalEncodingError("trailing data after VIR-Core CBOR value")
    return value
