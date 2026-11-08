"""Versioned effect commitments. V1 bytes and consensus domains are untouched.

V2 is an additive LOCAL qualification protocol. MAC authentication models the
existing trusted-authority/provider boundary; it is not an independent operator
attestation, a live signature suite, or an authorization decision by itself.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import hmac
import re
import uuid

from neuron.vdso.codec import decode, encode_array
from neuron.vdso.keccak import keccak_256

MAX_INTEGER = (1 << 63) - 1
MAX_CONTENT_BYTES = 1_048_576


class ProtocolError(ValueError):
    pass


def integer(value, name):
    if type(value) is not int or not 0 <= value <= MAX_INTEGER:
        raise ProtocolError("invalid bounded integer: "+name)


def hash32(value, name):
    if type(value) is not bytes or len(value) != 32:
        raise ProtocolError("invalid commitment: "+name)


def identifier(value, name):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value, re.ASCII):
        raise ProtocolError("invalid identifier: "+name)


def operation_id(value):
    if type(value) is not str:
        raise ProtocolError("invalid operation identifier")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError) as error:
        raise ProtocolError("operation ID must be a canonical UUID") from error


def commitment(domain, raw):
    return keccak_256(domain + raw)


def arguments_commitment(target, object_key, content_hash):
    return commitment(b"VAMS:EFFECT-ARGUMENTS:v2", encode_array(
        (target.encode("ascii"), object_key.encode("ascii"), content_hash)))


def postcondition_commitment(domain, target, object_key, content_hash):
    return commitment(b"VAMS:EFFECT-POSTCONDITION:v2", encode_array(
        (domain, target.encode("ascii"), object_key.encode("ascii"), content_hash, 1)))


@dataclass(frozen=True)
class EffectProposalV2:
    principal_id: str
    principal_root: bytes
    intent_id: bytes
    operation_id: str
    capability_id: bytes
    implementation_digest: bytes
    runtime_digest: bytes
    authority_epoch: int
    policy_root: bytes
    policy_revision: int
    target_domain: bytes
    target: str
    object_key: str
    arguments_hash: bytes
    content_hash: bytes
    expected_version: int
    fencing_token: int
    cost_units: int
    expires_at: int
    nonce: bytes
    expected_postcondition: bytes
    schema_version: int = 2
    operation: int = 0  # immutable CREATE only

    def validate(self):
        if type(self.schema_version) is not int or self.schema_version != 2:
            raise ProtocolError("unsupported effect schema")
        if type(self.operation) is not int or self.operation != 0:
            raise ProtocolError("only immutable object creation is supported")
        identifier(self.principal_id, "principal_id")
        identifier(self.target, "target")
        operation_id(self.operation_id)
        for name in ("principal_root", "intent_id", "capability_id",
                     "implementation_digest", "runtime_digest", "policy_root",
                     "target_domain", "arguments_hash", "content_hash", "nonce",
                     "expected_postcondition"):
            hash32(getattr(self, name), name)
        for name in ("authority_epoch", "policy_revision", "expected_version",
                     "fencing_token", "cost_units", "expires_at"):
            integer(getattr(self, name), name)
        if self.expected_version != 0:
            raise ProtocolError("immutable creation requires absence/version zero")
        key = self.object_key
        if type(key) is not str or len(key) > 512 or not re.fullmatch(
                r"[A-Za-z0-9._/-]+", key, re.ASCII):
            raise ProtocolError("invalid object resource")
        if not key.startswith(self.principal_id+"/") or any(
                part in ("", ".", "..") for part in key.split("/")):
            raise ProtocolError("object resource escapes principal scope")
        if self.arguments_hash != arguments_commitment(self.target, key, self.content_hash):
            raise ProtocolError("arguments differ from exact effect")
        if self.expected_postcondition != postcondition_commitment(
                self.target_domain, self.target, key, self.content_hash):
            raise ProtocolError("postcondition differs from exact effect")

    def canonical_bytes(self):
        self.validate()
        # Positional order is frozen here; text identities use ASCII byte strings.
        return encode_array((
            self.schema_version, self.operation, self.principal_id.encode("ascii"),
            self.principal_root, self.intent_id, uuid.UUID(self.operation_id).bytes,
            self.capability_id, self.implementation_digest, self.runtime_digest,
            self.authority_epoch, self.policy_root, self.policy_revision,
            self.target_domain, self.target.encode("ascii"), self.object_key.encode("ascii"),
            self.arguments_hash, self.content_hash, self.expected_version,
            self.fencing_token, self.cost_units, self.expires_at, self.nonce,
            self.expected_postcondition,
        ))

    @classmethod
    def from_bytes(cls, raw):
        try:
            if type(raw) is not bytes or len(raw) > 4096:
                raise ProtocolError("invalid proposal size")
            wire = decode(raw)
            if type(wire) is not tuple or len(wire) != 23:
                raise ProtocolError("invalid proposal field count")
            value = cls(
                principal_id=wire[2].decode("ascii"), principal_root=wire[3],
                intent_id=wire[4], operation_id=str(uuid.UUID(bytes=wire[5])),
                capability_id=wire[6], implementation_digest=wire[7],
                runtime_digest=wire[8], authority_epoch=wire[9], policy_root=wire[10],
                policy_revision=wire[11], target_domain=wire[12],
                target=wire[13].decode("ascii"), object_key=wire[14].decode("ascii"),
                arguments_hash=wire[15], content_hash=wire[16], expected_version=wire[17],
                fencing_token=wire[18], cost_units=wire[19], expires_at=wire[20],
                nonce=wire[21], expected_postcondition=wire[22],
                schema_version=wire[0], operation=wire[1])
            if value.canonical_bytes() != raw:
                raise ProtocolError("noncanonical effect proposal")
            return value
        except (ValueError, TypeError, AttributeError, IndexError) as error:
            raise ProtocolError("invalid effect proposal encoding") from error

    @property
    def proposal_digest(self):
        return commitment(b"VAMS:EFFECT-PROPOSAL:v2", self.canonical_bytes())


def _message_bytes(message, authenticated=True):
    values = [2]
    for field in fields(message):
        if not authenticated and field.name == "authentication":
            continue
        value = getattr(message, field.name)
        if type(value) is str:
            if not value or len(value) > 512:
                raise ProtocolError("invalid message text")
            value = value.encode("ascii")
        elif type(value) is int:
            integer(value, field.name)
        elif type(value) is bytes:
            hash32(value, field.name)
        else:
            raise ProtocolError("invalid authenticated field")
        values.append(value)
    return encode_array(values)


class AuthenticatedMessage:
    DOMAIN = b""

    def unsigned_bytes(self):
        return _message_bytes(self, authenticated=False)

    def canonical_bytes(self):
        return _message_bytes(self)

    @property
    def receipt_digest(self):
        return commitment(self.DOMAIN, self.canonical_bytes())


@dataclass(frozen=True)
class AdmissionReceiptV2(AuthenticatedMessage):
    proposal_digest: bytes
    reservation_id: str
    authority_epoch: int
    policy_revision: int
    fencing_token: int
    cost_units: int
    expires_at: int
    issuer_id: str
    authentication: bytes
    DOMAIN = b"VAMS:EFFECT-ADMISSION:v2"


@dataclass(frozen=True)
class FenceUpdateV2(AuthenticatedMessage):
    principal_id: str
    principal_root: bytes
    target_domain: bytes
    target: str
    authority_epoch: int
    policy_revision: int
    fencing_token: int
    expires_at: int
    issuer_id: str
    authentication: bytes
    DOMAIN = b"VAMS:EFFECT-FENCE:v2"


@dataclass(frozen=True)
class FenceAcknowledgementV2(AuthenticatedMessage):
    update_digest: bytes
    provider_id: str
    authority_epoch: int
    policy_revision: int
    fencing_token: int
    observed_at: int
    authentication: bytes
    DOMAIN = b"VAMS:EFFECT-FENCE-ACK:v2"


@dataclass(frozen=True)
class ProviderRecordV2(AuthenticatedMessage):
    operation_id: str
    proposal_digest: bytes
    admission_digest: bytes
    content_hash: bytes
    postcondition_digest: bytes
    state_version: int
    committed_at: int
    provider_id: str
    authentication: bytes
    DOMAIN = b"VAMS:EFFECT-EXECUTION:v2"


@dataclass(frozen=True)
class FencedAbsenceV2(AuthenticatedMessage):
    operation_id: str
    proposal_digest: bytes
    fence_ack_digest: bytes
    query_nonce: bytes
    provider_id: str
    observed_at: int
    authentication: bytes
    DOMAIN = b"VAMS:EFFECT-FENCED-ABSENCE:v2"


def authenticate(message, key):
    if type(key) is not bytes or len(key) < 32:
        raise ProtocolError("authentication key is not sufficiently strong")
    return hmac.new(key, message.DOMAIN+message.unsigned_bytes(), hashlib.sha256).digest()


def verify_authentication(message, key):
    hash32(message.authentication, "authentication")
    if not hmac.compare_digest(message.authentication, authenticate(message, key)):
        raise ProtocolError("authenticated message does not match")


class AuthoritySignerV2:
    """Trusted local issuer primitive, only invoked after durable reservation.

    Possessing this object is authority to issue receipts. Never expose it or
    its key to a model, Service Block, arbitrary callback, or live route.
    """
    def __init__(self, issuer_id, key):
        identifier(issuer_id, "issuer")
        if type(key) is not bytes or len(key) < 32:
            raise ProtocolError("invalid local issuer key")
        self.issuer_id, self._key = issuer_id, key

    def verifier_key_is_distinct(self, other):
        return type(other) is bytes and not hmac.compare_digest(self._key, other)

    def _sign(self, value):
        from dataclasses import replace
        return replace(value, authentication=authenticate(value, self._key))

    def admit(self, proposal, *, reservation_id):
        proposal.validate()
        operation_id(reservation_id)
        if reservation_id != proposal.operation_id:
            raise ProtocolError("reservation and operation identity differ")
        return self._sign(AdmissionReceiptV2(
            proposal.proposal_digest, reservation_id, proposal.authority_epoch,
            proposal.policy_revision, proposal.fencing_token, proposal.cost_units,
            proposal.expires_at, self.issuer_id, b"\0"*32))

    def fence(self, proposal, authority_epoch, policy_revision, fencing_token):
        proposal.validate()
        return self._sign(FenceUpdateV2(
            proposal.principal_id, proposal.principal_root, proposal.target_domain,
            proposal.target, authority_epoch, policy_revision, fencing_token,
            proposal.expires_at, self.issuer_id, b"\0"*32))

    def verify(self, message):
        if message.issuer_id != self.issuer_id:
            raise ProtocolError("unknown authority issuer")
        verify_authentication(message, self._key)
