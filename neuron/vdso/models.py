"""VIR-Core v1 models and non-consensus VDSO canary policy models.

Every ``canonical_bytes`` method in this module mirrors ``vir-codec``.  Hashes
used by the consensus protocol concatenate the ASCII domain prefix and payload
directly.  The separately named :func:`neuron.vdso.keccak.domain_hash` remains
length-delimited and is used only by non-consensus canary/policy identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable, Optional, Tuple

from .codec import MAX_UINT64, decode, encode_array
from .keccak import domain_hash, keccak_256


SCHEMA_VERSION = 1
RUNTIME_VERSION = 1
MAX_OBJECT_ACCESSES = 64
INTENT_DOMAIN = b"VAMS:INTENT:v1"
WORKFLOW_DOMAIN = b"VAMS:WORKFLOW:v1"
RECEIPT_DOMAIN = b"VAMS:RECEIPT:v1"


class AccessMode(IntEnum):
    READ = 0
    CONSUME = 1
    RESERVE = 2
    ACCUMULATE = 3


class HostAuthority(IntEnum):
    POLYGON = 0
    CARDANO = 1


class DomainMode(IntEnum):
    LEGACY = 0
    SHADOW = 1
    VDSO = 2


class ExecutionTier(IntEnum):
    NATIVE_NON_ECONOMIC = 0
    BATCHED_VALIDITY = 1
    IMMEDIATE_DUAL_VALIDITY = 2


class SignatureSuite(IntEnum):
    SECP256K1 = 1
    SECP256K1_AND_ML_DSA_65 = 2


class FailureCode(IntEnum):
    SUCCESS = 0
    INVALID_SCHEMA = 1
    MALFORMED_ENCODING = 2
    NON_CANONICAL_ENCODING = 3
    BOUNDS_EXCEEDED = 4
    UNSUPPORTED_OPCODE = 5
    ARITHMETIC_OVERFLOW = 6
    ARITHMETIC_UNDERFLOW = 7
    DIVISION_BY_ZERO = 8
    STACK_UNDERFLOW = 9
    STACK_OVERFLOW = 10
    INVALID_PROGRAM = 11
    HOST_AUTHORITY_MISMATCH = 12
    STATE_DOMAIN_MISMATCH = 13
    STALE_OBJECT_VERSION = 14
    ACCESS_DENIED = 15
    FENCING_TOKEN_REQUIRED = 16
    INVALID_FENCING_TOKEN = 17
    OUT_OF_GAS = 18
    UNSUPPORTED_PROVER = 19
    UNCONFIGURED_PROVER = 20
    RECEIPT_MISMATCH = 21
    INTENT_EXPIRED = 22
    NON_CANONICAL_OBJECT_ORDER = 23
    DUPLICATE_OBJECT = 24
    PROGRAM_ID_MISMATCH = 25
    INPUT_COMMITMENT_MISMATCH = 26
    AUTHORITY_EPOCH_MISMATCH = 27
    OBJECT_SET_MISMATCH = 28
    UNSUPPORTED_VERSION = 29
    TRAILING_DATA = 30
    INVALID_OUTCOME = 31
    MISSING_HALT = 32
    TRAILING_INSTRUCTION_DATA = 33
    INPUT_OUT_OF_BOUNDS = 34
    STACK_NOT_SINGLETON = 35
    UNSUPPORTED_HOST_AUTHORITY = 36
    INVALID_SIGNATURE_SUITE = 37
    INVALID_EXECUTION_TIER = 38
    TIER_SIGNATURE_MISMATCH = 39
    EXECUTION_UNIT_LIMIT_EXCEEDED = 40
    OUTPUT_COMMITMENT_MISMATCH = 41
    INVALID_EXECUTION_LIMIT = 42
    UNSUPPORTED_POLICY_COMMITMENT = 43
    INVALID_SETTLEMENT_METADATA = 44


def _bytes32(name: str, value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) != 32:
        raise ValueError(f"{name} must be exactly 32 bytes")
    return value


def _uint64(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_UINT64:
        raise ValueError(f"{name} must be an unsigned 64-bit integer")
    return value


def _schema_version(value: int) -> int:
    _uint64("schema_version", value)
    if value != SCHEMA_VERSION:
        raise ValueError(f"schema_version must equal VIR-Core v{SCHEMA_VERSION}")
    return value


def _consensus_prefixed_hash(domain: bytes, payload: bytes) -> bytes:
    """Mirror ``vir-codec::prefixed_hash`` without length framing."""

    return keccak_256(domain + payload)


@dataclass(frozen=True)
class DomainAuthorityBinding:
    state_domain: bytes
    host_authority: HostAuthority
    authority_epoch: int

    def __post_init__(self) -> None:
        _bytes32("state_domain", self.state_domain)
        HostAuthority(self.host_authority)
        _uint64("authority_epoch", self.authority_epoch)

    def canonical_value(self) -> tuple:
        return (self.state_domain, int(self.host_authority), self.authority_epoch)


@dataclass(frozen=True)
class StateObjectHeader:
    schema_version: int
    object_id: bytes
    binding: DomainAuthorityBinding
    version: int
    state_commitment: bytes

    def __post_init__(self) -> None:
        _schema_version(self.schema_version)
        _bytes32("object_id", self.object_id)
        if not isinstance(self.binding, DomainAuthorityBinding):
            raise ValueError("binding must be a DomainAuthorityBinding")
        _uint64("version", self.version)
        _bytes32("state_commitment", self.state_commitment)

    def canonical_bytes(self) -> bytes:
        return encode_array(
            (
                self.schema_version,
                self.object_id,
                self.binding.canonical_value(),
                self.version,
                self.state_commitment,
            )
        )


@dataclass(frozen=True)
class ObjectAccess:
    object_id: bytes
    mode: AccessMode
    expected_version: int
    fencing_token: Optional[int] = None

    def __post_init__(self) -> None:
        _bytes32("object_id", self.object_id)
        mode = AccessMode(self.mode)
        _uint64("expected_version", self.expected_version)
        if self.fencing_token is not None:
            _uint64("fencing_token", self.fencing_token)
            if self.fencing_token == 0:
                raise ValueError("fencing_token must be nonzero")
        if mode == AccessMode.RESERVE and self.fencing_token is None:
            raise ValueError("reserve access requires a nonzero fencing_token")
        if mode != AccessMode.RESERVE and self.fencing_token is not None:
            raise ValueError("fencing_token is valid only for reserve access")

    def canonical_value(self) -> tuple:
        fence = () if self.fencing_token is None else (self.fencing_token,)
        return (self.object_id, int(self.mode), self.expected_version, fence)


@dataclass(frozen=True)
class UnsignedIntent:
    schema_version: int
    actor_root: bytes
    binding: DomainAuthorityBinding
    nonce: int
    valid_until_height: int
    program_id: bytes
    workflow_definition_hash: bytes
    accesses: Tuple[ObjectAccess, ...]
    input_commitment: bytes
    expected_output_commitment: bytes
    evidence_root: bytes
    sidecar_root: bytes
    signature_suite: SignatureSuite
    execution_tier: ExecutionTier
    max_execution_units: int
    max_settlement_cost: int

    def __post_init__(self) -> None:
        _schema_version(self.schema_version)
        if not isinstance(self.binding, DomainAuthorityBinding):
            raise ValueError("binding must be a DomainAuthorityBinding")
        for name in ("nonce", "valid_until_height", "max_execution_units", "max_settlement_cost"):
            _uint64(name, getattr(self, name))
        if self.max_execution_units == 0:
            raise ValueError("max_execution_units must be nonzero")
        for name in (
            "actor_root",
            "program_id",
            "workflow_definition_hash",
            "input_commitment",
            "expected_output_commitment",
            "evidence_root",
            "sidecar_root",
        ):
            _bytes32(name, getattr(self, name))
        SignatureSuite(self.signature_suite)
        ExecutionTier(self.execution_tier)
        if len(self.accesses) > MAX_OBJECT_ACCESSES:
            raise ValueError(f"object accesses exceed the VIR-Core limit of {MAX_OBJECT_ACCESSES}")
        if any(not isinstance(access, ObjectAccess) for access in self.accesses):
            raise ValueError("accesses must contain only ObjectAccess values")
        if tuple(sorted(self.accesses, key=lambda access: access.object_id)) != self.accesses:
            raise ValueError("object accesses must be sorted by object_id")
        if len({access.object_id for access in self.accesses}) != len(self.accesses):
            raise ValueError("object accesses must not contain duplicate object IDs")
        self.validate_execution_policy()

    def validate_execution_policy(self) -> None:
        """Recheck host/access and anti-downgrade rules at every boundary."""

        if self.max_settlement_cost > 0 and (
            self.execution_tier != ExecutionTier.IMMEDIATE_DUAL_VALIDITY
            or self.signature_suite
            != SignatureSuite.SECP256K1_AND_ML_DSA_65
        ):
            raise ValueError(
                "nonzero max_settlement_cost requires Tier 2 hybrid authorization"
            )
        if (
            self.execution_tier == ExecutionTier.IMMEDIATE_DUAL_VALIDITY
            and self.signature_suite != SignatureSuite.SECP256K1_AND_ML_DSA_65
        ):
            raise ValueError("Tier 2 intents require the hybrid authorization suite")
        for access in self.accesses:
            access.__post_init__()
            mode = AccessMode(access.mode)
            if self.binding.host_authority == HostAuthority.CARDANO and mode in {
                AccessMode.CONSUME,
                AccessMode.RESERVE,
            }:
                raise ValueError(
                    "Cardano authority supports only READ and ACCUMULATE access"
                )
            if mode != AccessMode.READ and (
                self.execution_tier != ExecutionTier.IMMEDIATE_DUAL_VALIDITY
                or self.signature_suite
                != SignatureSuite.SECP256K1_AND_ML_DSA_65
            ):
                raise ValueError(
                    f"{mode.name} access requires Tier 2 hybrid authorization"
                )

    def canonical_bytes(self) -> bytes:
        return encode_array(
            (
                self.schema_version,
                self.actor_root,
                self.binding.canonical_value(),
                self.nonce,
                self.valid_until_height,
                self.program_id,
                self.workflow_definition_hash,
                tuple(access.canonical_value() for access in self.accesses),
                self.input_commitment,
                self.expected_output_commitment,
                self.evidence_root,
                self.sidecar_root,
                int(self.signature_suite),
                int(self.execution_tier),
                self.max_execution_units,
                self.max_settlement_cost,
            )
        )

    @classmethod
    def from_canonical_bytes(cls, data: bytes) -> "UnsignedIntent":
        value = decode(data)
        if not isinstance(value, tuple) or len(value) != 16:
            raise ValueError("unsigned intent must be a sixteen-field array")
        binding_value = value[2]
        accesses_value = value[7]
        if not isinstance(binding_value, tuple) or len(binding_value) != 3:
            raise ValueError("intent domainAuthorityBinding must have three fields")
        if not isinstance(accesses_value, tuple):
            raise ValueError("intent accesses must be an array")
        try:
            binding = DomainAuthorityBinding(
                state_domain=binding_value[0],
                host_authority=HostAuthority(binding_value[1]),
                authority_epoch=binding_value[2],
            )
            accesses = []
            for raw_access in accesses_value:
                if not isinstance(raw_access, tuple) or len(raw_access) != 4:
                    raise ValueError("object access must have four fields")
                raw_fence = raw_access[3]
                if not isinstance(raw_fence, tuple) or len(raw_fence) > 1:
                    raise ValueError("object access fence must be [] or [token]")
                accesses.append(
                    ObjectAccess(
                        object_id=raw_access[0],
                        mode=AccessMode(raw_access[1]),
                        expected_version=raw_access[2],
                        fencing_token=raw_fence[0] if raw_fence else None,
                    )
                )
            return cls(
                schema_version=value[0],
                actor_root=value[1],
                binding=binding,
                nonce=value[3],
                valid_until_height=value[4],
                program_id=value[5],
                workflow_definition_hash=value[6],
                accesses=tuple(accesses),
                input_commitment=value[8],
                expected_output_commitment=value[9],
                evidence_root=value[10],
                sidecar_root=value[11],
                signature_suite=SignatureSuite(value[12]),
                execution_tier=ExecutionTier(value[13]),
                max_execution_units=value[14],
                max_settlement_cost=value[15],
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid canonical unsigned intent") from exc

    @property
    def intent_id(self) -> bytes:
        return _consensus_prefixed_hash(INTENT_DOMAIN, self.canonical_bytes())

    def workflow_id_for_runtime(self, runtime_version: int) -> bytes:
        if isinstance(runtime_version, bool) or not 0 <= runtime_version <= 0xFFFF:
            raise ValueError("runtime_version must be an unsigned 16-bit integer")
        return keccak_256(
            WORKFLOW_DOMAIN
            + self.intent_id
            + self.workflow_definition_hash
            + runtime_version.to_bytes(2, "big")
        )

    @property
    def workflow_id(self) -> bytes:
        return self.workflow_id_for_runtime(RUNTIME_VERSION)


@dataclass(frozen=True)
class TransitionReceipt:
    """Semantic receipt encoded exactly as ``vir-codec`` v1."""

    schema_version: int
    intent_id: bytes
    program_id: bytes
    binding: DomainAuthorityBinding
    pre_state_root: bytes
    post_state_root: bytes
    output_commitment: bytes
    gas_used: int
    failure_code: FailureCode = FailureCode.SUCCESS
    instruction_index: int = 0

    def __post_init__(self) -> None:
        _schema_version(self.schema_version)
        if not isinstance(self.binding, DomainAuthorityBinding):
            raise ValueError("binding must be a DomainAuthorityBinding")
        for name in (
            "intent_id",
            "program_id",
            "pre_state_root",
            "post_state_root",
            "output_commitment",
        ):
            _bytes32(name, getattr(self, name))
        _uint64("gas_used", self.gas_used)
        _uint64("instruction_index", self.instruction_index)
        if self.instruction_index > 0xFFFFFFFF:
            raise ValueError("instruction_index must be an unsigned 32-bit integer")
        code = FailureCode(self.failure_code)
        if code == FailureCode.SUCCESS and self.instruction_index != 0:
            raise ValueError("successful receipts must use instruction_index zero")

    def canonical_bytes(self) -> bytes:
        outcome = (
            (0,)
            if self.failure_code == FailureCode.SUCCESS
            else (1, int(self.failure_code), self.instruction_index)
        )
        return encode_array(
            (
                self.schema_version,
                self.intent_id,
                self.program_id,
                self.binding.canonical_value(),
                self.pre_state_root,
                self.post_state_root,
                self.output_commitment,
                self.gas_used,
                outcome,
            )
        )

    @property
    def receipt_hash(self) -> bytes:
        return _consensus_prefixed_hash(RECEIPT_DOMAIN, self.canonical_bytes())


@dataclass(frozen=True)
class SettlementMetadata:
    """Host settlement metadata kept cryptographically separate from receipts."""

    schema_version: int
    receipt_hash: bytes
    binding: DomainAuthorityBinding
    source_chain_reference: bytes
    source_transaction_hash: bytes
    settled_at_height: int
    bridge_proof_hash: bytes
    payload_hash: bytes

    def __post_init__(self) -> None:
        _schema_version(self.schema_version)
        if not isinstance(self.binding, DomainAuthorityBinding):
            raise ValueError("binding must be a DomainAuthorityBinding")
        for name in (
            "receipt_hash",
            "source_chain_reference",
            "source_transaction_hash",
            "bridge_proof_hash",
            "payload_hash",
        ):
            _bytes32(name, getattr(self, name))
        _uint64("settled_at_height", self.settled_at_height)
        zero = b"\x00" * 32
        if self.source_chain_reference != zero:
            if (
                self.source_transaction_hash == zero
                or self.bridge_proof_hash == zero
                or self.payload_hash == zero
                or self.bridge_proof_hash == self.payload_hash
            ):
                raise ValueError(
                    "cross-host settlement requires distinct nonzero proof and payload commitments"
                )
        elif (
            self.source_transaction_hash != zero
            or self.settled_at_height != 0
            or self.bridge_proof_hash != zero
            or self.payload_hash != zero
        ):
            raise ValueError("same-host settlement metadata must be all-zero")

    def canonical_bytes(self) -> bytes:
        return encode_array(
            (
                self.schema_version,
                self.receipt_hash,
                self.binding.canonical_value(),
                self.source_chain_reference,
                self.source_transaction_hash,
                self.settled_at_height,
                self.bridge_proof_hash,
                self.payload_hash,
            )
        )

    @classmethod
    def from_canonical_bytes(cls, data: bytes) -> "SettlementMetadata":
        value = decode(data)
        if not isinstance(value, tuple) or len(value) != 8:
            raise ValueError("settlement metadata must be an eight-field array")
        binding_value = value[2]
        if not isinstance(binding_value, tuple) or len(binding_value) != 3:
            raise ValueError("settlement domainAuthorityBinding must have three fields")
        try:
            binding = DomainAuthorityBinding(
                state_domain=binding_value[0],
                host_authority=HostAuthority(binding_value[1]),
                authority_epoch=binding_value[2],
            )
            return cls(
                schema_version=value[0],
                receipt_hash=value[1],
                binding=binding,
                source_chain_reference=value[3],
                source_transaction_hash=value[4],
                settled_at_height=value[5],
                bridge_proof_hash=value[6],
                payload_hash=value[7],
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid canonical settlement metadata") from exc


@dataclass(frozen=True)
class CapabilityRequirements:
    host_authority: HostAuthority
    access_mode: AccessMode
    execution_tier: ExecutionTier
    minimum_privacy_class: int
    maximum_cost: int
    required_da: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        HostAuthority(self.host_authority)
        AccessMode(self.access_mode)
        ExecutionTier(self.execution_tier)
        _uint64("minimum_privacy_class", self.minimum_privacy_class)
        _uint64("maximum_cost", self.maximum_cost)
        if any(name not in {"celestia", "near"} for name in self.required_da):
            raise ValueError("only Celestia and Near are live-capable VDSO DA routes")


@dataclass(frozen=True)
class AdapterProfile:
    adapter_id: bytes
    host_authority: HostAuthority
    access_modes: Tuple[AccessMode, ...]
    maximum_tier: ExecutionTier
    privacy_class: int
    estimated_cost: int
    estimated_latency_ms: int
    da_protocols: Tuple[str, ...]
    active: bool
    quarantined: bool
    mock_mode: bool
    stub: bool
    expires_at: int
    conformance_root: bytes

    def __post_init__(self) -> None:
        _bytes32("adapter_id", self.adapter_id)
        _bytes32("conformance_root", self.conformance_root)
        HostAuthority(self.host_authority)
        ExecutionTier(self.maximum_tier)
        for mode in self.access_modes:
            AccessMode(mode)
        for name in ("privacy_class", "estimated_cost", "estimated_latency_ms", "expires_at"):
            _uint64(name, getattr(self, name))


def state_root(headers: Iterable[StateObjectHeader]) -> bytes:
    """Compute a non-consensus ordered-set root for shadow comparisons."""

    ordered = tuple(sorted(headers, key=lambda header: header.object_id))
    if len({header.object_id for header in ordered}) != len(ordered):
        raise ValueError("state root input contains duplicate object IDs")
    return domain_hash(b"VAMS:OBJECT-SET:v1", tuple(header.canonical_bytes() for header in ordered))
