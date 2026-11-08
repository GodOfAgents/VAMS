"""Action-bound PostgreSQL immutable-object provider, unqualified V3 candidate.

The policy source is a trusted authenticated dependency, not an arbitrary score
or remote Boolean. No live factory/CLI/HTTP route registers this candidate.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import time

from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3, FENCES, OBJECTS
from neuron.effect_protocol_v3 import (
    EffectV3Error, ObjectEffectV3, ObjectFenceV3, SignedEffectReceiptV3,
    hash32, word, integer, commitment, sign_receipt, verify_receipt,
    verify_admission, verify_admitted_obligation, verify_fence_update, fence_ack_subject, verify_fence_ack,
    effect_subject, verify_effect, absence_subject, MAX_CONTENT_BYTES,
)
from neuron.signed_receipts import ReceiptSignerV3, ReceiptVerifierV3
from neuron.runtime_safety import ImmutableRuntimeConfiguration, RuntimeConfigurationError, load_runtime_policy


class CurrentActionPolicyV1(ABC):
    """Implement using authenticated, current host RestrictedTestnetPolicyV1.

    Must reject DENY/UNKNOWN/unavailable/stale policy and unauthorized actor,
    provider/workload/target/resource/capability/budget before returning None.
    An implementation and reviewed host/key/finality manifests are REQUIRED for
    qualification. Local test subclasses do not establish authentic policy.
    """
    @abstractmethod
    def assert_allowed(self, proposal: ObjectEffectV3, now: int) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class ObjectProviderIdentityV3:
    provider_id: bytes
    host_domain: bytes
    runtime_id: bytes
    target: bytes
    chain_id: int
    authority: ReceiptVerifierV3
    provider: ReceiptVerifierV3

    @property
    def digest(self):
        for value in (self.provider_id, self.host_domain, self.runtime_id, self.target): hash32(value)
        integer(self.chain_id, positive=True)
        if type(self.authority) is not ReceiptVerifierV3 or type(self.provider) is not ReceiptVerifierV3:
            raise EffectV3Error('public-only authority/provider verifiers required')
        if self.authority.issuer_id == self.provider.issuer_id:
            raise EffectV3Error('authority and provider issuers must differ')
        return commitment(b'VAMS:OBJECT-PROVIDER-IDENTITY:v3\0', self.provider_id,
            self.host_domain, self.runtime_id, self.target, word(self.chain_id),
            self.authority.issuer_id, self.provider.issuer_id)


class PostgresObjectProviderV3(ImmutableRuntimeConfiguration):
    _immutable_runtime_fields = frozenset({'runtime_policy', 'database', 'identity', '_signer', '_policy', '_clock'})

    def __init__(self, database, identity, provider_signer, policy, *, clock=lambda: time.time_ns() // 1_000_000_000):
        self.runtime_policy = load_runtime_policy()
        # A policy interface/fixture is not a qualified current-host backend.
        # This unactivated protocol has no live factory or override.
        if self.runtime_policy.is_live:
            raise RuntimeConfigurationError("Unqualified object provider candidate cannot run in live mode")
        if type(identity) is not ObjectProviderIdentityV3 or type(database) is not PostgresEffectDatabaseV3:
            raise EffectV3Error('explicit V3 provider identity/database required')
        if database.configuration_hash != identity.digest:
            raise EffectV3Error('database belongs to another provider configuration')
        if type(provider_signer) is not ReceiptSignerV3 or provider_signer.verifier() != identity.provider:
            raise EffectV3Error('distinct configured provider signer required')
        if not isinstance(policy, CurrentActionPolicyV1) or not callable(clock):
            raise EffectV3Error('authenticated current policy source and clock required')
        self.database = database; self.identity = identity
        self._signer = provider_signer; self._policy = policy; self._clock = clock
        self._freeze_runtime_configuration()

    def _now(self):
        if load_runtime_policy() != self.runtime_policy:
            raise RuntimeConfigurationError('provider runtime configuration changed')
        return integer(self._clock())

    def _target(self, proposal):
        if type(proposal) is not ObjectEffectV3:
            raise EffectV3Error('typed V3 proposal required; local V1/V2 rejected')
        proposal.validate()
        c, i = proposal.context, self.identity
        if (c.provider_id, c.host_domain, c.runtime_id, c.target, c.chain_id) != (
                i.provider_id, i.host_domain, i.runtime_id, i.target, i.chain_id):
            raise EffectV3Error('proposal targets another provider/runtime/domain')

    def _policy_allows(self, proposal, now):
        proposal.require_current(now)
        if self._policy.assert_allowed(proposal, now) is not None:
            raise EffectV3Error('policy source returned an unsupported decision')
        current = self._now()
        if current < now:
            raise EffectV3Error('clock moved backwards during policy validation')
        proposal.require_current(current)
        return current

    @staticmethod
    def _lock(cursor, scope):
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', (int.from_bytes(scope[:8], 'big', signed=True),))

    def advance_fence(self, fence, update):
        now = self._now()
        verify_fence_update(fence, update, self.identity.authority, now)
        if (fence.provider_id, fence.host_domain, fence.chain_id) != (
                self.identity.provider_id, self.identity.host_domain, self.identity.chain_id):
            raise EffectV3Error('fence targets another provider/domain')
        with self.database.transaction() as cursor:
            self._lock(cursor, fence.scope_id)
            cursor.execute(f'SELECT fence_bytes,update_bytes,ack_bytes FROM {FENCES} WHERE scope_id=%s FOR UPDATE', (fence.scope_id,))
            old = cursor.fetchone()
            if old:
                previous = ObjectFenceV3.from_bytes(bytes(old[0]))
                if previous == fence and bytes(old[1]) == update.canonical_bytes():
                    ack = SignedEffectReceiptV3.from_bytes(bytes(old[2]))
                    verify_fence_ack(fence, update, ack, self.identity.provider, now, authority=self.identity.authority)
                    return ack
                if (fence.authority_epoch <= previous.authority_epoch or fence.policy_version < previous.policy_version or
                        fence.fencing_token <= previous.fencing_token or
                        fence.policy_root != previous.policy_root and fence.policy_version == previous.policy_version):
                    raise EffectV3Error('fence/authority/policy must advance monotonically')
            # Recheck after obtaining the same provider lock used by effects.
            now = self._now()
            verify_fence_update(fence, update, self.identity.authority, now)
            ack = sign_receipt(self._signer, purpose=3, subject=fence_ack_subject(fence, update),
                provider=fence.provider_id, epoch=fence.authority_epoch, policy=fence.policy_version,
                fence=fence.fencing_token, issued_at=now, expires_at=fence.expires_at)
            cursor.execute(f'''INSERT INTO {FENCES}(scope_id,fence_bytes,update_bytes,ack_bytes) VALUES(%s,%s,%s,%s)
                ON CONFLICT(scope_id) DO UPDATE SET fence_bytes=EXCLUDED.fence_bytes,
                update_bytes=EXCLUDED.update_bytes,ack_bytes=EXCLUDED.ack_bytes''',
                (fence.scope_id, fence.canonical_bytes(), update.canonical_bytes(), ack.canonical_bytes()))
        return ack

    def _verify_row(self, row, proposal, admission, now):
        if bytes(row[0]) != proposal.canonical_bytes() or bytes(row[1]) != admission.canonical_bytes():
            raise EffectV3Error('logical operation cannot be rebound to another proposal/admission')
        if hashlib.sha256(bytes(row[2])).digest() != proposal.context.input_hash:
            raise EffectV3Error('stored object differs from its admitted bytes')
        record = SignedEffectReceiptV3.from_bytes(bytes(row[3]))
        verify_effect(proposal, admission, record, self.identity.provider, now, authority=self.identity.authority)
        return record

    def lookup_fence(self, fence, update):
        """Recover a committed acknowledgement without resending an update."""
        now = self._now()
        verify_fence_update(fence, update, self.identity.authority, fence.issued_at)
        if (fence.provider_id, fence.host_domain, fence.chain_id) != (
                self.identity.provider_id, self.identity.host_domain, self.identity.chain_id):
            raise EffectV3Error('fence lookup targets another provider/domain')
        if fence.issued_at > now:
            raise EffectV3Error('future fence evidence')
        with self.database.transaction() as cursor:
            cursor.execute(f'SELECT fence_bytes,update_bytes,ack_bytes FROM {FENCES} WHERE scope_id=%s', (fence.scope_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            if bytes(row[0]) != fence.canonical_bytes() or bytes(row[1]) != update.canonical_bytes():
                raise EffectV3Error('retained fence differs; authority reconciliation required')
            ack = SignedEffectReceiptV3.from_bytes(bytes(row[2]))
            verify_fence_ack(fence, update, ack, self.identity.provider, now, authority=self.identity.authority)
        return ack

    def commit(self, proposal, admission, content):
        self._target(proposal)
        now = self._now()
        verify_admission(proposal, admission, self.identity.authority, now)
        now = self._policy_allows(proposal, now)
        if type(content) is not bytes or len(content) > MAX_CONTENT_BYTES or hashlib.sha256(content).digest() != proposal.context.input_hash:
            raise EffectV3Error('content differs from admitted bytes')
        fence = ObjectFenceV3.from_context(proposal.context, proposal.fencing_token)
        with self.database.transaction() as cursor:
            self._lock(cursor, fence.scope_id)
            cursor.execute(f'SELECT fence_bytes FROM {FENCES} WHERE scope_id=%s FOR UPDATE', (fence.scope_id,))
            current = cursor.fetchone()
            if current is None:
                raise EffectV3Error('provider fence not established')
            active = ObjectFenceV3.from_bytes(bytes(current[0]))
            if (active.actor_root, active.root_scheme, active.provider_id, active.host_domain, active.chain_id,
                    active.policy_root, active.authority_epoch, active.policy_version, active.fencing_token) != (
                    fence.actor_root, fence.root_scheme, fence.provider_id, fence.host_domain, fence.chain_id,
                    fence.policy_root, fence.authority_epoch, fence.policy_version, fence.fencing_token):
                raise EffectV3Error('stale or mismatched provider fence')
            now = self._now()
            verify_admission(proposal, admission, self.identity.authority, now)
            now = self._policy_allows(proposal, now)
            cursor.execute(f'SELECT proposal_bytes,admission_bytes,content,record_bytes FROM {OBJECTS} WHERE operation_id=%s', (proposal.operation_id,))
            old = cursor.fetchone()
            if old:
                return self._verify_row(old, proposal, admission, now)
            current = self._now()
            if current < now:
                raise EffectV3Error('clock moved backwards before effect')
            now = current
            verify_admission(proposal, admission, self.identity.authority, now)
            record = sign_receipt(self._signer, purpose=4, subject=effect_subject(proposal, admission, now),
                provider=self.identity.provider_id, epoch=proposal.context.authority_epoch,
                policy=proposal.context.policy_version, fence=proposal.fencing_token,
                issued_at=now, expires_at=proposal.context.expires_at)
            cursor.execute(f'''INSERT INTO {OBJECTS}(operation_id,scope_id,resource_id,proposal_bytes,admission_bytes,
                admission_digest,nonce,content,record_bytes) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (proposal.operation_id, fence.scope_id, proposal.resource_id, proposal.canonical_bytes(), admission.canonical_bytes(),
                 admission.digest, proposal.context.nonce, content, record.canonical_bytes()))
        return record  # Transaction commit completed before any receipt escapes.

    def lookup(self, proposal, admission):
        """Historical reconciliation read; never creates an effect or new approval."""
        self._target(proposal)
        now = self._now()
        verify_admitted_obligation(proposal, admission, self.identity.authority, now)
        with self.database.transaction() as cursor:
            cursor.execute(f'SELECT proposal_bytes,admission_bytes,content,record_bytes FROM {OBJECTS} WHERE operation_id=%s', (proposal.operation_id,))
            row = cursor.fetchone()
            return None if row is None else self._verify_row(row, proposal, admission, now)

    def prove_fenced_absence(self, proposal, fence, update, ack):
        """No timeout inference: authenticate a retained, newer provider fence."""
        self._target(proposal)
        now = self._now()
        verify_fence_ack(fence, update, ack, self.identity.provider, now, authority=self.identity.authority)
        if (fence.scope_id != ObjectFenceV3.from_context(proposal.context, proposal.fencing_token).scope_id or
                fence.provider_id != self.identity.provider_id or fence.authority_epoch <= proposal.context.authority_epoch or
                fence.fencing_token <= proposal.fencing_token):
            raise EffectV3Error('absence requires the same provider scope and a newer acknowledged fence')
        with self.database.transaction() as cursor:
            self._lock(cursor, fence.scope_id)
            cursor.execute(f'SELECT fence_bytes,update_bytes,ack_bytes FROM {FENCES} WHERE scope_id=%s FOR UPDATE', (fence.scope_id,))
            retained = cursor.fetchone()
            if retained is None or tuple(bytes(v) for v in retained) != (fence.canonical_bytes(), update.canonical_bytes(), ack.canonical_bytes()):
                raise EffectV3Error('fence acknowledgement is not retained by provider')
            cursor.execute(f'SELECT 1 FROM {OBJECTS} WHERE operation_id=%s', (proposal.operation_id,))
            if cursor.fetchone() is not None:
                raise EffectV3Error('effect exists; absence cannot be asserted')
            now = self._now()
            result = sign_receipt(self._signer, purpose=5, subject=absence_subject(proposal, ack),
                provider=self.identity.provider_id, epoch=fence.authority_epoch, policy=fence.policy_version,
                fence=fence.fencing_token, issued_at=now, expires_at=now + 1)
        return result
