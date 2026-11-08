"""Versioned attempt identities for the unchanged signed V3 object wire.

These values authenticate no host, funding, policy, finality or provider by
themselves. Storage5/current-native-state integration remains a separate consumer.
V3/V4 tables and their terminal rows must never be reinterpreted or overwritten.
"""
from dataclasses import dataclass

from neuron.effect_protocol_v3 import (
    EffectV3Error, ObjectEffectV3, SignedEffectReceiptV3, ObjectFenceV3,
    commitment, hash32, integer, word, verify_admission,
    verify_admitted_obligation, verify_fenced_absence,
)
from neuron.signed_receipts import ReceiptVerifierV3

LOGICAL_WORK_DOMAIN = b'VAMS:OBJECT-LOGICAL-WORK:v1\0'
NATIVE_ATTEMPT_DOMAIN = b'VAMS:OBJECT-SETTLEMENT-ATTEMPT:v1\0'
ATTEMPT_LINK_DOMAIN = b'VAMS:AUTHORITY-ATTEMPT-LINK:v5\0'
AUTHORITY_CONTEXT_DOMAIN = b'VAMS:SIGNED-AUTHORITY-CONTEXT:v5\0'


def address_word(value):
    hash32(value, 'EVM address')
    if value[:12] != b'\0' * 12:
        raise EffectV3Error('canonical padded EVM address required')
    return value


def logical_work(proposal):
    if type(proposal) is not ObjectEffectV3:
        raise EffectV3Error('typed V3 object proposal required')
    proposal.validate()
    return commitment(LOGICAL_WORK_DOMAIN, proposal.postcondition,
        proposal.context.budget_unit, word(proposal.cost_units))


def authority_context_id(proposal):
    """Digest only fields bound by the signed proposal; NOT a persisted lease ID.

    Storage5 must independently look up and validate its canonical scope/generation
    under current host governance. Caller metadata cannot appoint that generation.
    """
    logical_work(proposal)
    c=proposal.context
    hashes=(c.actor_root,c.provider_id,c.runtime_id,c.model_id,c.host_domain,
        c.workflow_id,c.intent_id,c.policy_root,c.target,c.budget_unit)
    integers=(c.root_scheme,c.authority_epoch,c.policy_version,c.capabilities,c.chain_id,proposal.fencing_token)
    return commitment(AUTHORITY_CONTEXT_DOMAIN,*hashes,*(word(v) for v in integers))


@dataclass(frozen=True)
class NativeObjectRowV1:
    chain_id: int
    settlement: bytes
    allocation_id: bytes
    provider_index: int

    def validate(self):
        integer(self.chain_id, positive=True)
        address_word(self.settlement)
        hash32(self.allocation_id, 'allocation')
        integer(self.provider_index)
        if self.provider_index >= 20:
            raise EffectV3Error('provider index exceeds native row bound')

    def canonical_bytes(self):
        self.validate()
        return word(self.chain_id) + self.settlement + self.allocation_id + word(self.provider_index)


def native_attempt_id(row, proposal, admission):
    if type(row) is not NativeObjectRowV1 or type(admission) is not SignedEffectReceiptV3:
        raise EffectV3Error('typed native row and signed admission required')
    logical_work(proposal)
    admission.canonical_bytes()
    if (row.chain_id, row.settlement) != (proposal.context.chain_id, proposal.context.target):
        raise EffectV3Error('funding row differs from proposal host')
    return commitment(NATIVE_ATTEMPT_DOMAIN, row.canonical_bytes(), proposal.digest, admission.digest)


def authenticate_fenced_absence_v5(proposal,admission,fence,update,ack,absence,*,authority,provider,now):
    """Historical signed absence, with the producer's policy continuity checks.

    This authenticates no native funding outcome or actual storage operation.
    """
    if type(proposal) is not ObjectEffectV3 or type(fence) is not ObjectFenceV3:
        raise EffectV3Error('typed retained proposal and fence required')
    verify_admitted_obligation(proposal,admission,authority,now)
    old=proposal.context
    if (fence.policy_version<old.policy_version or
            fence.policy_root!=old.policy_root and fence.policy_version==old.policy_version):
        raise EffectV3Error('absence cutover regresses or rebinds policy generation')
    verify_fenced_absence(proposal,fence,update,ack,absence,provider,now,authority=authority)
    return absence.digest


@dataclass(frozen=True)
class ObjectAttemptV5:
    row: NativeObjectRowV1
    proposal: ObjectEffectV3
    admission: SignedEffectReceiptV3
    ordinal: int
    previous_attempt: bytes | None

    def validate(self):
        native_attempt_id(self.row, self.proposal, self.admission)
        integer(self.ordinal, positive=True)
        if (self.ordinal == 1) != (self.previous_attempt is None):
            raise EffectV3Error('attempt predecessor and ordinal disagree')
        if self.previous_attempt is not None:
            hash32(self.previous_attempt, 'attempt predecessor')
            if self.previous_attempt == self.attempt_id:
                raise EffectV3Error('attempt cannot precede itself')

    @property
    def attempt_id(self):
        return native_attempt_id(self.row, self.proposal, self.admission)

    @property
    def link_digest(self):
        self.validate()
        return commitment(ATTEMPT_LINK_DOMAIN, self.proposal.operation_id,
            logical_work(self.proposal), self.attempt_id, word(self.ordinal),
            self.previous_attempt or b'\0' * 32, authority_context_id(self.proposal))

    def authenticate_current(self, authority, now):
        self.validate()
        if type(authority) is not ReceiptVerifierV3:
            raise EffectV3Error('configured public authority verifier required')
        verify_admission(self.proposal, self.admission, authority, now)

    def authenticate_history(self, authority, now):
        self.validate()
        if type(authority) is not ReceiptVerifierV3:
            raise EffectV3Error('configured public authority verifier required')
        # Historical authentication is for reconciliation, never dispatch permission.
        verify_admitted_obligation(self.proposal, self.admission, authority, now)


def authenticate_same_host_successor(previous, successor, fence, update, ack, absence,
        *, authority, provider, now):
    """Check retained retry history; native funding/current policy are STILL required.

    This helper covers same-provider native-host renewal. A host/provider migration
    needs its separate authentic handoff protocol, never a caller-set override.
    The core operation/logicalWork identities deliberately do not freeze that host.
    """
    if type(previous) is not ObjectAttemptV5 or type(successor) is not ObjectAttemptV5:
        raise EffectV3Error('typed retained predecessor and successor required')
    if type(fence) is not ObjectFenceV3 or type(provider) is not ReceiptVerifierV3:
        raise EffectV3Error('authenticated retained fencing evidence required')
    previous.authenticate_history(authority, now)
    successor.authenticate_current(authority, now)
    old = previous.proposal
    new = successor.proposal
    if (new.operation_id != old.operation_id or logical_work(new) != logical_work(old) or
            successor.previous_attempt != previous.attempt_id or successor.ordinal != previous.ordinal + 1 or
            authority_context_id(new) == authority_context_id(old)):
        raise EffectV3Error('retry changes logical work or retained attempt lineage')
    a, b = old.context, new.context
    if (a.provider_id, a.runtime_id, a.host_domain, a.chain_id, a.target) != (
            b.provider_id, b.runtime_id, b.host_domain, b.chain_id, b.target):
        raise EffectV3Error('separately authenticated provider/host/runtime migration required')
    authenticate_fenced_absence_v5(old,previous.admission,fence,update,ack,absence,
        authority=authority,provider=provider,now=now)
    if (b.authority_epoch <= fence.authority_epoch or new.fencing_token <= fence.fencing_token or
            b.policy_version < fence.policy_version or b.issued_at < ack.receipt.issued_at or
            b.policy_root != fence.policy_root and b.policy_version == fence.policy_version):
        raise EffectV3Error('retry does not follow acknowledged authority/policy/fence')
    return successor.link_digest
