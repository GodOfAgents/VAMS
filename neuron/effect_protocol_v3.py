"""Action-bound asymmetric object-effect protocol. V1/V2 bytes remain local.

These values authenticate commitments, not issuer custody, live policy, native
chain finality, inference correctness or an independently operated provider.
"""
from dataclasses import dataclass
import hashlib

from neuron.action_context import ActionContextV1, DOMAIN as ACTION_DOMAIN
from neuron.signed_receipts import ReceiptV3, ReceiptVerifierV3, ReceiptSignerV3, DOMAIN as RECEIPT_DOMAIN

MAX_INTEGER = (1 << 63) - 1
MAX_CONTENT_BYTES = 1_048_576
MAX_ADMISSION_SECONDS = 600
WRITE_IMMUTABLE_OBJECT = 1
OBJECT_DOMAIN = b'VAMS:OBJECT-EFFECT:v3\0'
FENCE_DOMAIN = b'VAMS:OBJECT-FENCE:v3\0'
SIGNED_DOMAIN = b'VAMS:EFFECT-SIGNED:v3\0'
ACTION_SIZE = len(ACTION_DOMAIN) + 21 * 32
RECEIPT_SIZE = len(RECEIPT_DOMAIN) + 9 * 32


class EffectV3Error(ValueError):
    pass


def hash32(value, name='commitment'):
    if type(value) is not bytes or len(value) != 32 or value == b'\0' * 32:
        raise EffectV3Error('invalid ' + name)
    return value


def integer(value, *, positive=False):
    if type(value) is not int or not int(positive) <= value <= MAX_INTEGER:
        raise EffectV3Error('invalid bounded integer')
    return value


def word(value):
    return integer(value).to_bytes(32, 'big')


def commitment(domain, *parts):
    return hashlib.sha256(domain + b''.join(parts)).digest()


@dataclass(frozen=True)
class ObjectEffectV3:
    context: ActionContextV1
    resource_id: bytes
    cost_units: int
    fencing_token: int

    @property
    def operation_id(self):
        # Stable across retry, authority changes and provider/chain migration.
        # A changed proposal with this ID must be reconciled, never overwritten.
        c = self.context
        return commitment(b'VAMS:OBJECT-OPERATION:v3\0', c.actor_root,
            c.root_scheme.to_bytes(32, 'big'), c.workflow_id, c.intent_id, self.resource_id)

    @property
    def action_hash(self):
        return commitment(b'VAMS:OBJECT-ACTION:v3\0', self.operation_id, self.resource_id,
            self.context.input_hash, word(self.cost_units), word(self.fencing_token))

    @property
    def postcondition(self):
        return commitment(b'VAMS:OBJECT-POSTCONDITION:v3\0', self.operation_id,
            self.resource_id, self.context.input_hash, word(1))

    def validate(self):
        if type(self.context) is not ActionContextV1:
            raise EffectV3Error('typed action context required')
        self.context.validate()
        hash32(self.resource_id, 'resource')
        integer(self.cost_units)
        integer(self.fencing_token, positive=True)
        c = self.context
        for value in (c.authority_epoch, c.policy_version, c.issued_at, c.expires_at, c.budget):
            integer(value)
        if c.capabilities != WRITE_IMMUTABLE_OBJECT or c.model_id != b'\0' * 32:
            raise EffectV3Error('only the immutable-object workload is supported')
        if self.cost_units > c.budget or c.expires_at - c.issued_at > MAX_ADMISSION_SECONDS:
            raise EffectV3Error('effect exceeds budget or bounded lifetime')
        if c.action_hash != self.action_hash:
            raise EffectV3Error('action context does not bind the object effect')

    def require_current(self, now):
        self.validate()
        integer(now)
        if not self.context.issued_at <= now < self.context.expires_at:
            raise EffectV3Error('effect authorization is not current')

    def canonical_bytes(self):
        self.validate()
        return OBJECT_DOMAIN + self.context.canonical_bytes() + self.resource_id + word(self.cost_units) + word(self.fencing_token)

    @property
    def digest(self):
        return hashlib.sha256(self.canonical_bytes()).digest()

    @classmethod
    def from_bytes(cls, raw):
        if type(raw) is not bytes or len(raw) != len(OBJECT_DOMAIN) + ACTION_SIZE + 96 or not raw.startswith(OBJECT_DOMAIN):
            raise EffectV3Error('unsupported object-effect encoding')
        start = len(OBJECT_DOMAIN)
        result = cls(ActionContextV1.from_bytes(raw[start:start + ACTION_SIZE]),
            raw[start + ACTION_SIZE:start + ACTION_SIZE + 32],
            int.from_bytes(raw[-64:-32], 'big'), int.from_bytes(raw[-32:], 'big'))
        result.validate()
        if result.canonical_bytes() != raw:
            raise EffectV3Error('noncanonical object-effect encoding')
        return result


@dataclass(frozen=True)
class SignedEffectReceiptV3:
    receipt: ReceiptV3
    signature: bytes

    @property
    def digest(self):
        return self.receipt.digest

    def canonical_bytes(self):
        if type(self.receipt) is not ReceiptV3 or type(self.signature) is not bytes or len(self.signature) != 64:
            raise EffectV3Error('typed asymmetric receipt required')
        return SIGNED_DOMAIN + self.receipt.canonical_bytes() + self.signature

    @classmethod
    def from_bytes(cls, raw):
        if type(raw) is not bytes or len(raw) != len(SIGNED_DOMAIN) + RECEIPT_SIZE + 64 or not raw.startswith(SIGNED_DOMAIN + RECEIPT_DOMAIN):
            raise EffectV3Error('unsupported signed receipt encoding')
        body = raw[len(SIGNED_DOMAIN) + len(RECEIPT_DOMAIN):-64]
        words = [body[i:i + 32] for i in range(0, len(body), 32)]
        values = [int.from_bytes(w, 'big') for w in words[3:]]
        receipt = ReceiptV3(values[0], words[0], words[1], words[2], *values[1:])
        result = cls(receipt, raw[-64:])
        if result.canonical_bytes() != raw:
            raise EffectV3Error('noncanonical signed receipt')
        return result


def sign_receipt(signer, *, purpose, subject, provider, epoch, policy, fence, issued_at, expires_at):
    if type(signer) is not ReceiptSignerV3:
        raise EffectV3Error('private issuer handle required for issuing a receipt')
    receipt = ReceiptV3(purpose, signer.verifier().issuer_id, subject, provider,
        epoch, policy, fence, issued_at, expires_at)
    return SignedEffectReceiptV3(receipt, signer.sign(receipt))


def verify_receipt(signed, verifier, *, purpose, subject, provider, epoch, policy, fence, now, historical=False):
    integer(now)
    if type(signed) is not SignedEffectReceiptV3 or type(verifier) is not ReceiptVerifierV3:
        raise EffectV3Error('typed signed receipt and public verifier required')
    signed.canonical_bytes()
    expected = dict(purpose=purpose, subject_digest=subject, provider_id=provider,
        authority_epoch=epoch, policy_version=policy, fencing_token=fence, now=now)
    if historical:
        if purpose not in (3, 4, 5) or now < signed.receipt.issued_at:
            raise EffectV3Error('historical authorization is forbidden')
        # Fence acknowledgements are authenticated historical facts only; never
        # reusable dispatch authority. Exact retained update matching is required.
        expected['now'] = signed.receipt.issued_at
    return verifier.verify(signed.receipt, signed.signature, **expected)


def verify_admission(proposal, signed, authority, now):
    proposal.require_current(now)
    verify_admitted_obligation(proposal, signed, authority, now)
    c = proposal.context
    verify_receipt(signed, authority, purpose=1, subject=proposal.digest,
        provider=c.provider_id, epoch=c.authority_epoch, policy=c.policy_version,
        fence=proposal.fencing_token, now=now)


def verify_admitted_obligation(proposal, signed, authority, now):
    """Historical authority authentication for recovery only, never dispatch."""
    proposal.validate()
    integer(now)
    if type(signed) is not SignedEffectReceiptV3 or signed.receipt.issued_at > now:
        raise EffectV3Error('missing or future admitted obligation')
    c = proposal.context
    verify_receipt(signed, authority, purpose=1, subject=proposal.digest,
        provider=c.provider_id, epoch=c.authority_epoch, policy=c.policy_version,
        fence=proposal.fencing_token, now=signed.receipt.issued_at)
    if signed.receipt.issued_at < c.issued_at or signed.receipt.expires_at > c.expires_at:
        raise EffectV3Error('admission widens action validity')


@dataclass(frozen=True)
class ObjectFenceV3:
    actor_root: bytes
    provider_id: bytes
    host_domain: bytes
    policy_root: bytes
    root_scheme: int
    chain_id: int
    authority_epoch: int
    policy_version: int
    fencing_token: int
    issued_at: int
    expires_at: int

    def canonical_bytes(self):
        for value in (self.actor_root, self.provider_id, self.host_domain, self.policy_root):
            hash32(value)
        for value in (self.root_scheme, self.chain_id, self.authority_epoch, self.policy_version, self.fencing_token):
            integer(value, positive=True)
        integer(self.issued_at); integer(self.expires_at)
        if self.root_scheme not in (1, 2) or self.actor_root[:12 if self.root_scheme == 1 else 4] != b'\0' * (12 if self.root_scheme == 1 else 4):
            raise EffectV3Error('invalid actor root scheme')
        if not 0 < self.expires_at - self.issued_at <= MAX_ADMISSION_SECONDS:
            raise EffectV3Error('invalid fencing validity')
        return FENCE_DOMAIN + self.actor_root + self.provider_id + self.host_domain + self.policy_root + b''.join(
            word(v) for v in (self.root_scheme, self.chain_id, self.authority_epoch, self.policy_version,
                             self.fencing_token, self.issued_at, self.expires_at))

    @property
    def digest(self):
        return hashlib.sha256(self.canonical_bytes()).digest()

    @property
    def scope_id(self):
        self.canonical_bytes()
        return commitment(b'VAMS:OBJECT-FENCE-SCOPE:v3\0', self.actor_root,
            word(self.root_scheme), self.host_domain, word(self.chain_id))

    @classmethod
    def from_bytes(cls, raw):
        if type(raw) is not bytes or len(raw) != len(FENCE_DOMAIN) + 11 * 32 or not raw.startswith(FENCE_DOMAIN):
            raise EffectV3Error('unsupported fence encoding')
        body = raw[len(FENCE_DOMAIN):]
        words = [body[i:i + 32] for i in range(0, len(body), 32)]
        result = cls(*words[:4], *(int.from_bytes(w, 'big') for w in words[4:]))
        if result.canonical_bytes() != raw:
            raise EffectV3Error('noncanonical fence encoding')
        return result

    @classmethod
    def from_context(cls, context, token):
        context.validate()
        result = cls(context.actor_root, context.provider_id, context.host_domain, context.policy_root,
            context.root_scheme, context.chain_id, context.authority_epoch, context.policy_version,
            token, context.issued_at, context.expires_at)
        result.canonical_bytes()
        return result


def verify_fence_update(fence, signed, authority, now):
    if type(fence) is not ObjectFenceV3:
        raise EffectV3Error('typed fence required')
    verify_receipt(signed, authority, purpose=2, subject=fence.digest, provider=fence.provider_id,
        epoch=fence.authority_epoch, policy=fence.policy_version, fence=fence.fencing_token, now=now)
    if signed.receipt.issued_at != fence.issued_at or signed.receipt.expires_at != fence.expires_at:
        raise EffectV3Error('fence validity mismatch')


def fence_ack_subject(fence, update):
    return commitment(b'VAMS:OBJECT-FENCE-ACK:v3\0', fence.digest, update.digest)


def verify_fence_ack(fence, update, ack, provider, now, *, authority):
    # Authenticate the original issuer too; a provider cannot invent an
    # authority update and make it valid by acknowledging its own forgery.
    verify_fence_update(fence, update, authority, fence.issued_at)
    verify_receipt(ack, provider, purpose=3, subject=fence_ack_subject(fence, update),
        provider=fence.provider_id, epoch=fence.authority_epoch, policy=fence.policy_version,
        fence=fence.fencing_token, now=now, historical=True)
    if not fence.issued_at <= ack.receipt.issued_at < fence.expires_at:
        raise EffectV3Error('fencing acknowledgement outside authorized window')


def effect_subject(proposal, admission, committed_at):
    return commitment(b'VAMS:OBJECT-RESULT:v3\0', proposal.digest, admission.digest,
        proposal.context.input_hash, proposal.postcondition, word(1), word(committed_at))


def verify_effect(proposal, admission, record, provider, now, *, authority):
    proposal.validate()
    if type(admission) is not SignedEffectReceiptV3 or type(record) is not SignedEffectReceiptV3:
        raise EffectV3Error('typed admission/effect evidence required')
    verify_admitted_obligation(proposal, admission, authority, now)
    c = proposal.context
    committed = record.receipt.issued_at
    if not max(c.issued_at, admission.receipt.issued_at) <= committed < min(c.expires_at, admission.receipt.expires_at):
        raise EffectV3Error('effect occurred outside admitted validity')
    verify_receipt(record, provider, purpose=4, subject=effect_subject(proposal, admission, committed),
        provider=c.provider_id, epoch=c.authority_epoch, policy=c.policy_version,
        fence=proposal.fencing_token, now=now, historical=True)


def absence_subject(proposal, ack):
    return commitment(b'VAMS:OBJECT-FENCED-ABSENCE:v3\0', proposal.digest, ack.digest)


def verify_fenced_absence(proposal, fence, update, ack, absence, provider, now, *, authority):
    proposal.validate()
    verify_fence_ack(fence, update, ack, provider, now, authority=authority)
    old = ObjectFenceV3.from_context(proposal.context, proposal.fencing_token)
    if (fence.scope_id != old.scope_id or fence.provider_id != proposal.context.provider_id or
            fence.authority_epoch <= proposal.context.authority_epoch or fence.fencing_token <= proposal.fencing_token):
        raise EffectV3Error('absence requires the same provider and a newer acknowledged fence')
    verify_receipt(absence, provider, purpose=5, subject=absence_subject(proposal, ack),
        provider=fence.provider_id, epoch=fence.authority_epoch, policy=fence.policy_version,
        fence=fence.fencing_token, now=now, historical=True)
    if absence.receipt.issued_at < ack.receipt.issued_at:
        raise EffectV3Error('absence predates the acknowledged cutover')
