"""Unsigned EVM authority-source descriptor; constructing data grants no rights.

This codec does not authenticate a network, deployment, code hash, governance,
current state, or non-proxy status. The reviewed reader/profile must establish
those facts. Cardano remains required and has no supported descriptor here yet.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

DOMAIN = b"VAMS:GATEWAY:AUTHORITY-SOURCE:v1\x00"
EVM_NETWORK_DOMAIN = b"VAMS:GATEWAY:EVM-NETWORK:v1\x00"
MAX_ENCODING_BYTES = 512
FIELD_WIDTHS = (1, 32, 20, 32, 20, 32, 2)


class HeartbeatAuthoritySourceDataError(ValueError):
    """Malformed or unsupported unsigned source data."""


def _identity(value: object, length: int) -> bytes:
    if type(value) is not bytes or len(value) != length or not any(value):
        raise HeartbeatAuthoritySourceDataError("invalid authority-source identity")
    return value


def evm_network_context_digest(chain_id: int, genesis_block_hash: bytes) -> bytes:
    """Hash supplied network data only; does not discover or verify a network."""
    if type(chain_id) is not int or not 1 <= chain_id < (1 << 256):
        raise HeartbeatAuthoritySourceDataError("invalid EVM chain identifier")
    genesis = _identity(genesis_block_hash, 32)
    return hashlib.sha256(EVM_NETWORK_DOMAIN + chain_id.to_bytes(32, "big") + genesis).digest()


@dataclass(frozen=True)
class HeartbeatAuthoritySourceV1:
    scheme: int
    network_context_digest: bytes
    registry_address: bytes
    registry_code_hash: bytes
    policy_address: bytes
    policy_code_hash: bytes
    registry_schema_version: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if type(self.scheme) is not int or self.scheme != 1:
            raise HeartbeatAuthoritySourceDataError("unsupported authority-source scheme")
        if type(self.registry_schema_version) is not int or self.registry_schema_version != 1:
            raise HeartbeatAuthoritySourceDataError("unsupported registry schema")
        _identity(self.network_context_digest, 32)
        _identity(self.registry_address, 20)
        _identity(self.registry_code_hash, 32)
        _identity(self.policy_address, 20)
        _identity(self.policy_code_hash, 32)

    def canonical_bytes(self) -> bytes:
        self.validate()
        fields = (self.scheme.to_bytes(1, "big"), self.network_context_digest,
                  self.registry_address, self.registry_code_hash, self.policy_address,
                  self.policy_code_hash, self.registry_schema_version.to_bytes(2, "big"))
        return DOMAIN + len(fields).to_bytes(2, "big") + b"".join(
            bytes((i,)) + len(value).to_bytes(2, "big") + value
            for i, value in enumerate(fields, 1)
        )

    @property
    def digest(self) -> bytes:
        return hashlib.sha256(self.canonical_bytes()).digest()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "HeartbeatAuthoritySourceV1":
        if type(raw) is not bytes or len(raw) > MAX_ENCODING_BYTES:
            raise HeartbeatAuthoritySourceDataError("invalid authority-source frame")
        offset = len(DOMAIN) + 2
        if len(raw) < offset or not raw.startswith(DOMAIN) or raw[len(DOMAIN):offset] != b"\x00\x07":
            raise HeartbeatAuthoritySourceDataError("invalid authority-source frame")
        fields = []
        for field_id, width in enumerate(FIELD_WIDTHS, 1):
            if len(raw) - offset < 3:
                raise HeartbeatAuthoritySourceDataError("truncated authority-source field")
            if raw[offset] != field_id or int.from_bytes(raw[offset + 1:offset + 3], "big") != width:
                raise HeartbeatAuthoritySourceDataError("noncanonical authority-source field")
            offset += 3
            if len(raw) - offset < width:
                raise HeartbeatAuthoritySourceDataError("truncated authority-source field")
            fields.append(raw[offset:offset + width])
            offset += width
        if offset != len(raw):
            raise HeartbeatAuthoritySourceDataError("trailing authority-source bytes")
        parsed = cls(int.from_bytes(fields[0], "big"), *fields[1:6], int.from_bytes(fields[6], "big"))
        if parsed.canonical_bytes() != raw:
            raise HeartbeatAuthoritySourceDataError("noncanonical authority-source frame")
        return parsed
