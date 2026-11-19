"""Local, unqualified payment-intent/policy candidate; no payment or signer service.

Payment approval has its own domain and public-only verifier. Object admission
signatures retain their original meaning. A successful check does not prove
funding, token support, signer custody, finality or a persisted budget reservation.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

from neuron.effect_attempts_v5 import ObjectAttemptV5, authority_context_id as v5_authority_context_id
from neuron.runtime_safety import load_runtime_policy
from neuron.signed_receipts import ORDER, ReceiptVerifierV3

UINT256_MAX = (1 << 256) - 1
MAX_INTENT_SECONDS = 600
MAX_CAPABILITY_SECONDS = 86400
INTENT_DOMAIN = b'VAMS:PAYMENT-INTENT:v1\0'
CAPABILITY_DOMAIN = b'VAMS:PAYMENT-CAPABILITY:v1\0'
APPROVAL_DOMAIN = b'VAMS:PAYMENT-APPROVAL:v1\0'
KEY_DOMAIN = b'VAMS:PAYMENT-APPROVAL-KEY:secp256k1:v1\0'
BUDGET_DOMAIN = b'VAMS:PAYMENT-BUDGET-DENOMINATION:v1\0'
# Fixed candidate semantics: exact EVM EIP-3009 transfer funding the existing row.
SCHEMA_VERSION = 1
SCHEME_EXACT = 1
TRANSFER_EIP3009 = 1
PURPOSE_ESCROW_FUNDING = 1
PROTOCOL_BPS = 5


class PaymentPolicyError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise PaymentPolicyError(message)


def _uint(value, *, positive=False):
    _require(type(value) is int and int(positive) <= value <= UINT256_MAX, 'invalid uint256')
    return value


def _hash(value):
    _require(type(value) is bytes and len(value) == 32 and value != bytes(32), 'nonzero bytes32 required')
    return value


def _address(value):
    _hash(value)
    _require(value[:12] == bytes(12), 'canonical nonzero padded EVM address required')
    return value


def _window(start, end, maximum):
    _uint(start); _uint(end)
    _require(0 < end - start <= maximum, 'invalid bounded validity')


def _tags(value):
    for name, expected in (('schema_version', 1), ('scheme', 1), ('transfer_method', 1), ('purpose', 1)):
        _require(type(getattr(value, name)) is int and getattr(value, name) == expected, 'unsupported payment version/scheme/purpose')


def _wire(value, domain, hashes_, integers):
    value.validate()
    return (domain + b''.join(getattr(value, name) for name in hashes_) +
            b''.join(getattr(value, name).to_bytes(32, 'big') for name in integers))


def _from_wire(cls, raw, domain, hashes_, integers, *, signature=False):
    size = len(domain) + 32 * (len(hashes_) + len(integers)) + (64 if signature else 0)
    _require(type(raw) is bytes and len(raw) == size and raw.startswith(domain), 'unsupported canonical payment encoding')
    offset = len(domain); values = {}
    for name in hashes_:
        values[name] = raw[offset:offset + 32]; offset += 32
    for name in integers:
        values[name] = int.from_bytes(raw[offset:offset + 32], 'big'); offset += 32
    if signature: values['signature'] = raw[offset:]
    value = cls(**values)
    _require(value.canonical_bytes() == raw, 'noncanonical payment encoding')
    return value


def _budget_fingerprint(value):
    # Stable across policy generations and maxima; monetary ledger binds it once
    # to budget_identity. Distinct budget_unit is never a currency conversion.
    return hashlib.sha256(BUDGET_DOMAIN + b''.join(getattr(value, name) for name in
        ('actor_root', 'payer', 'host_domain', 'budget_unit', 'asset', 'token_domain')) +
        b''.join(v.to_bytes(32, 'big') for v in (1, value.chain_id, value.decimals))).digest()


INTENT_HASH_FIELDS = ('operation_id', 'attempt_id', 'proposal_digest', 'admission_digest',
    'authority_context_id', 'actor_root', 'provider_id', 'host_domain', 'budget_unit', 'policy_root',
    'asset', 'token_domain', 'payer', 'payee', 'facilitator', 'nonce', 'service_block_id',
    'registry_terms_hash', 'builder', 'capability_digest', 'budget_identity')
INTENT_INT_FIELDS = ('authority_epoch', 'policy_version', 'chain_id', 'decimals', 'amount',
    'valid_after', 'valid_before', 'builder_bps', 'protocol_bps', 'schema_version', 'scheme',
    'transfer_method', 'purpose')


@dataclass(frozen=True)
class PaymentIntentV1:
    operation_id: bytes
    attempt_id: bytes
    proposal_digest: bytes
    admission_digest: bytes
    authority_context_id: bytes
    actor_root: bytes
    provider_id: bytes
    host_domain: bytes
    budget_unit: bytes
    policy_root: bytes
    asset: bytes
    token_domain: bytes
    payer: bytes
    payee: bytes
    facilitator: bytes
    nonce: bytes
    service_block_id: bytes
    registry_terms_hash: bytes
    builder: bytes
    capability_digest: bytes
    budget_identity: bytes
    authority_epoch: int
    policy_version: int
    chain_id: int
    decimals: int
    amount: int
    valid_after: int
    valid_before: int
    builder_bps: int
    protocol_bps: int = PROTOCOL_BPS
    schema_version: int = SCHEMA_VERSION
    scheme: int = SCHEME_EXACT
    transfer_method: int = TRANSFER_EIP3009
    purpose: int = PURPOSE_ESCROW_FUNDING

    def validate(self):
        for name in INTENT_HASH_FIELDS: _hash(getattr(self, name))
        for name in INTENT_INT_FIELDS: _uint(getattr(self, name))
        for name in ('actor_root', 'asset', 'payer', 'payee', 'facilitator', 'builder'): _address(getattr(self, name))
        _tags(self)
        _require(self.authority_epoch > 0 and self.policy_version > 0 and self.chain_id > 0 and self.amount > 0, 'missing payment scope/amount')
        _require(self.decimals <= 255 and self.builder_bps <= 5000 and self.protocol_bps == 5, 'unsupported asset/registry fee terms')
        _require(self.payer == self.actor_root, 'payer must be the admitted EVM actor root')
        _window(self.valid_after, self.valid_before, MAX_INTENT_SECONDS)

    def canonical_bytes(self):
        return _wire(self, INTENT_DOMAIN, INTENT_HASH_FIELDS, INTENT_INT_FIELDS)

    @classmethod
    def from_bytes(cls, raw):
        return _from_wire(cls, raw, INTENT_DOMAIN, INTENT_HASH_FIELDS, INTENT_INT_FIELDS)

    @property
    def budget_fingerprint(self):
        self.validate()
        return _budget_fingerprint(self)

    @property
    def digest(self):
        return hashlib.sha256(self.canonical_bytes()).digest()

    @classmethod
    def for_attempt(cls, attempt, **terms):
        _require(type(attempt) is ObjectAttemptV5, 'exact ObjectAttemptV5 required')
        attempt.validate(); p = attempt.proposal; c = p.context
        value = cls(operation_id=p.operation_id, attempt_id=attempt.attempt_id, proposal_digest=p.digest,
            admission_digest=attempt.admission.digest, authority_context_id=v5_authority_context_id(p),
            actor_root=c.actor_root, provider_id=c.provider_id, host_domain=c.host_domain,
            budget_unit=c.budget_unit, policy_root=c.policy_root, authority_epoch=c.authority_epoch,
            policy_version=c.policy_version, chain_id=c.chain_id, **terms)
        value.validate_for(attempt)
        return value

    def validate_for(self, attempt):
        self.validate()
        _require(type(attempt) is ObjectAttemptV5, 'exact ObjectAttemptV5 required')
        attempt.validate(); p = attempt.proposal; c = p.context
        expected = (p.operation_id, attempt.attempt_id, p.digest, attempt.admission.digest,
                    v5_authority_context_id(p), c.actor_root, c.provider_id, c.host_domain,
                    c.budget_unit, c.policy_root, c.authority_epoch, c.policy_version, c.chain_id)
        names = INTENT_HASH_FIELDS[:10] + ('authority_epoch', 'policy_version', 'chain_id')
        _require(tuple(getattr(self, name) for name in names) == expected, 'payment differs from exact retained attempt')
        _require(c.root_scheme == 1 and self.payee == attempt.row.settlement, 'payment must fund the admitted EVM escrow')
        _require(c.issued_at <= self.valid_after < self.valid_before <= c.expires_at, 'payment validity widens admitted authority')


CAPABILITY_HASH_FIELDS = ('actor_root', 'provider_id', 'host_domain', 'budget_unit', 'policy_root',
    'asset', 'token_domain', 'payer', 'payee', 'facilitator', 'budget_identity',
    'service_block_id', 'registry_terms_hash', 'builder')
CAPABILITY_INT_FIELDS = ('authority_epoch', 'policy_version', 'chain_id', 'decimals',
    'max_per_call', 'max_aggregate', 'valid_after', 'valid_before', 'builder_bps', 'protocol_bps',
    'schema_version', 'scheme', 'transfer_method', 'purpose', 'max_validity_seconds')


@dataclass(frozen=True)
class PaymentCapabilityV1:
    actor_root: bytes
    provider_id: bytes
    host_domain: bytes
    budget_unit: bytes
    policy_root: bytes
    asset: bytes
    token_domain: bytes
    payer: bytes
    payee: bytes
    facilitator: bytes
    budget_identity: bytes
    service_block_id: bytes
    registry_terms_hash: bytes
    builder: bytes
    authority_epoch: int
    policy_version: int
    chain_id: int
    decimals: int
    max_per_call: int
    max_aggregate: int
    valid_after: int
    valid_before: int
    builder_bps: int
    max_validity_seconds: int = MAX_INTENT_SECONDS
    protocol_bps: int = PROTOCOL_BPS
    schema_version: int = SCHEMA_VERSION
    scheme: int = SCHEME_EXACT
    transfer_method: int = TRANSFER_EIP3009
    purpose: int = PURPOSE_ESCROW_FUNDING

    def validate(self):
        for name in CAPABILITY_HASH_FIELDS: _hash(getattr(self, name))
        for name in CAPABILITY_INT_FIELDS: _uint(getattr(self, name))
        for name in ('actor_root', 'asset', 'payer', 'payee', 'facilitator', 'builder'): _address(getattr(self, name))
        _tags(self)
        _require(0 < self.max_per_call <= self.max_aggregate and self.chain_id > 0 and
                 self.authority_epoch > 0 and self.policy_version > 0, 'invalid capability budget/scope')
        _require(self.decimals <= 255 and self.builder_bps <= 5000 and self.protocol_bps == 5 and
                 self.payer == self.actor_root, 'unsupported capability asset/payer/fees')
        _require(0 < self.max_validity_seconds <= MAX_INTENT_SECONDS, 'invalid capability intent lifetime')
        _window(self.valid_after, self.valid_before, MAX_CAPABILITY_SECONDS)

    def canonical_bytes(self):
        return _wire(self, CAPABILITY_DOMAIN, CAPABILITY_HASH_FIELDS, CAPABILITY_INT_FIELDS)

    @property
    def budget_fingerprint(self):
        self.validate()
        return _budget_fingerprint(self)

    @property
    def digest(self):
        return hashlib.sha256(self.canonical_bytes()).digest()

    def permits(self, intent):
        self.validate(); _require(type(intent) is PaymentIntentV1, 'typed payment intent required'); intent.validate()
        names = CAPABILITY_HASH_FIELDS + ('authority_epoch', 'policy_version', 'chain_id', 'decimals',
                                          'builder_bps', 'protocol_bps', 'schema_version', 'scheme', 'transfer_method', 'purpose')
        _require(all(getattr(self, name) == getattr(intent, name) for name in names), 'payment exceeds exact capability scope')
        _require(intent.capability_digest == self.digest and intent.amount <= self.max_per_call and
                 self.valid_after <= intent.valid_after < intent.valid_before <= self.valid_before and
                 intent.valid_before - intent.valid_after <= self.max_validity_seconds,
                 'payment exceeds capability amount/validity')
        # Aggregate consumption is the monetary ledger's locked transaction duty.


APPROVAL_HASH_FIELDS = ('intent_digest', 'capability_digest', 'nonce', 'actor_root', 'provider_id',
                        'host_domain', 'policy_root', 'issuer_id')
APPROVAL_INT_FIELDS = ('authority_epoch', 'policy_version', 'issued_at', 'expires_at', 'schema_version', 'purpose')


@dataclass(frozen=True)
class PaymentApprovalV1:
    intent_digest: bytes
    capability_digest: bytes
    nonce: bytes
    actor_root: bytes
    provider_id: bytes
    host_domain: bytes
    policy_root: bytes
    issuer_id: bytes
    authority_epoch: int
    policy_version: int
    issued_at: int
    expires_at: int
    signature: bytes
    schema_version: int = 1
    purpose: int = PURPOSE_ESCROW_FUNDING

    def validate(self):
        for name in APPROVAL_HASH_FIELDS: _hash(getattr(self, name))
        for name in APPROVAL_INT_FIELDS: _uint(getattr(self, name))
        _address(self.actor_root)
        _require(type(self.schema_version) is int and self.schema_version == 1 and
                 type(self.purpose) is int and self.purpose == PURPOSE_ESCROW_FUNDING and
                 self.authority_epoch > 0 and self.policy_version > 0, 'unsupported approval scope')
        _require(type(self.signature) is bytes and len(self.signature) == 64, 'canonical payment signature required')
        r, s = int.from_bytes(self.signature[:32], 'big'), int.from_bytes(self.signature[32:], 'big')
        _require(0 < r < ORDER and 0 < s <= ORDER // 2, 'noncanonical payment signature')
        _window(self.issued_at, self.expires_at, MAX_INTENT_SECONDS)

    def unsigned_bytes(self):
        return _wire(self, APPROVAL_DOMAIN, APPROVAL_HASH_FIELDS, APPROVAL_INT_FIELDS)

    @property
    def digest(self):
        return hashlib.sha256(self.unsigned_bytes()).digest()

    def canonical_bytes(self):
        return self.unsigned_bytes() + self.signature

    @classmethod
    def from_bytes(cls, raw):
        return _from_wire(cls, raw, APPROVAL_DOMAIN, APPROVAL_HASH_FIELDS, APPROVAL_INT_FIELDS, signature=True)


@dataclass(frozen=True)
class PaymentApprovalVerifierV1:
    public_key_bytes: bytes

    def __post_init__(self):
        _require(type(self.public_key_bytes) is bytes and len(self.public_key_bytes) == 65 and
                 self.public_key_bytes[0] == 4, 'canonical public secp256k1 key required')
        try:
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), self.public_key_bytes)
        except ValueError:
            raise PaymentPolicyError('invalid payment approval public key') from None

    @property
    def issuer_id(self):
        return hashlib.sha256(KEY_DOMAIN + self.public_key_bytes).digest()

    def verify(self, intent, approval, now):
        _require(type(intent) is PaymentIntentV1 and type(approval) is PaymentApprovalV1, 'typed payment approval required')
        intent.validate(); approval.validate(); _uint(now)
        _require((approval.intent_digest, approval.capability_digest, approval.nonce, approval.actor_root,
                  approval.provider_id, approval.host_domain, approval.policy_root, approval.authority_epoch,
                  approval.policy_version, approval.issuer_id) ==
                 (intent.digest, intent.capability_digest, intent.nonce, intent.actor_root,
                  intent.provider_id, intent.host_domain, intent.policy_root, intent.authority_epoch,
                  intent.policy_version, self.issuer_id), 'payment approval context mismatch')
        _require(intent.valid_after <= approval.issued_at <= now < approval.expires_at <= intent.valid_before,
                 'payment approval is not current')
        r, s = int.from_bytes(approval.signature[:32], 'big'), int.from_bytes(approval.signature[32:], 'big')
        _require(0 < r < ORDER and 0 < s <= ORDER // 2, 'noncanonical payment signature')
        key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), self.public_key_bytes)
        try:
            key.verify(utils.encode_dss_signature(r, s), approval.digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        except InvalidSignature:
            raise PaymentPolicyError('invalid payment signature') from None
        return approval.digest


@dataclass(frozen=True)
class PaymentPolicyStateV1:
    enabled: bool
    capability_digest: bytes
    actor_root: bytes
    provider_id: bytes
    host_domain: bytes
    policy_root: bytes
    authority_epoch: int
    policy_version: int

    def validate(self):
        _require(type(self.enabled) is bool, 'known policy enablement required')
        for name in ('capability_digest', 'actor_root', 'provider_id', 'host_domain', 'policy_root'): _hash(getattr(self, name))
        _address(self.actor_root); _uint(self.authority_epoch, positive=True); _uint(self.policy_version, positive=True)


class PaymentPolicySourceV1(ABC):
    """Responsible host configures/authenticates this source; callers supply none.

    No network reader or authentic policy producer is qualified by this interface.
    UNKNOWN, stale, unavailable or incoherent state must fail closed at the source.
    """
    @abstractmethod
    def read_current(self):
        raise NotImplementedError


@dataclass(frozen=True)
class PaymentPolicyBindingV1:
    authority: ReceiptVerifierV3
    approval_verifier: PaymentApprovalVerifierV1
    capability: PaymentCapabilityV1
    source: PaymentPolicySourceV1
    _runtime_policy: object = field(init=False, repr=False)

    def __post_init__(self):
        policy = load_runtime_policy()
        _require(not policy.is_live, 'unqualified payment policy candidate cannot run live')
        _require(type(self.authority) is ReceiptVerifierV3 and
                 type(self.approval_verifier) is PaymentApprovalVerifierV1 and
                 type(self.capability) is PaymentCapabilityV1 and isinstance(self.source, PaymentPolicySourceV1),
                 'explicit configured policy/verifier/capability required')
        self.capability.validate()
        object.__setattr__(self, '_runtime_policy', policy)

    def _current(self):
        try:
            state = self.source.read_current()
        except Exception:
            raise PaymentPolicyError('current payment policy unavailable') from None
        _require(type(state) is PaymentPolicyStateV1, 'current payment policy UNKNOWN')
        state.validate(); c = self.capability
        _require(state.enabled and (state.capability_digest, state.actor_root, state.provider_id, state.host_domain,
                                   state.policy_root, state.authority_epoch, state.policy_version) ==
                 (c.digest, c.actor_root, c.provider_id, c.host_domain, c.policy_root, c.authority_epoch, c.policy_version),
                 'payment policy disabled or changed')
        return state

    def validate_new(self, intent, attempt, approval, now):
        _uint(now)
        _require(load_runtime_policy() == self._runtime_policy and not self._runtime_policy.is_live, 'payment runtime changed')
        before = self._current()
        _require(type(intent) is PaymentIntentV1 and type(attempt) is ObjectAttemptV5, 'typed payment/retained attempt required')
        intent.validate_for(attempt)
        attempt.authenticate_current(self.authority, now)
        self.capability.permits(intent)
        _require(intent.valid_after < now < intent.valid_before, 'transfer candidate is not within strict validity')
        self.approval_verifier.verify(intent, approval, now)
        _require(self._current() == before and load_runtime_policy() == self._runtime_policy, 'payment policy changed during validation')
        return intent.digest
