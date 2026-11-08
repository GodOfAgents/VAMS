"""Source-preparation journal for authenticated V5 attempt outcomes.

This module deliberately does not admit, dispatch, fund, verify native chain
finality, refund on timeout, create successor attempts, sign receipts, or write
settlement observations. It has not been integrated or run against PostgreSQL.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import time

from neuron.effect_attempt_events_v5 import (
    AttemptEventV5,
    MAX_EVENTS,
    next_event,
    reserved_payload,
    unknown_payload,
)
from neuron.effect_attempt_payloads_v5 import FencedAbsencePayloadV5
from neuron.effect_attempts_v5 import (
    NativeObjectRowV1,
    ObjectAttemptV5,
    logical_work,
    native_attempt_id,
)
from neuron.effect_authority_store_v5 import (
    ATTEMPTS5,
    COMPLETIONS5,
    EVENTS5,
    GENERATIONS5,
    HEADS5,
    WORK5,
    ExpectedChecksV5,
    PostgresAuthorityDatabaseV5,
    authority_configuration_v5,
)
from neuron.effect_protocol_v3 import (
    EffectV3Error,
    ObjectFenceV3,
    ObjectEffectV3,
    SignedEffectReceiptV3,
    commitment,
    hash32,
    integer,
    verify_admitted_obligation,
    verify_effect,
    verify_fence_ack,
    verify_fence_update,
)
from neuron.effect_provider_v3 import ObjectProviderIdentityV3
from neuron.effect_authority_v3 import ObjectAuthorityScopeV3
from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    RuntimeConfigurationError,
    load_runtime_policy,
)


GENERATION_DOMAIN_V5 = b'VAMS:AUTHORITY-GENERATION:v5\0'
EVENT_INSERT = f'''INSERT INTO {EVENTS5}(
    operation_id,attempt_no,attempt_id,event_seq,predecessor_event_seq,kind,
    payload_bytes,payload_digest,event_digest)
    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)'''


@dataclass(frozen=True)
class AttemptJournalReadV5:
    """One attempt's authenticated history; never a native funding assertion."""
    attempt: ObjectAttemptV5
    scope_generation_id: bytes
    events: tuple[AttemptEventV5, ...]
    outcome: str
    terminal_evidence: SignedEffectReceiptV3 | FencedAbsencePayloadV5 | None
    native_verified: bool = False

    def __post_init__(self):
        hash32(self.scope_generation_id)
        if type(self.events) is not tuple or self.outcome not in ('pending', 'completed', 'absent'):
            raise EffectV3Error('invalid bounded attempt read result')
        if self.native_verified is not False:
            raise EffectV3Error('this journal never verifies native funding')


@dataclass(frozen=True)
class _GenerationFactsV5:
    scope: ObjectAuthorityScopeV3
    status: str
    fence: ObjectFenceV3
    update: SignedEffectReceiptV3
    acknowledgement: SignedEffectReceiptV3 | None
    generation_id: bytes
    ordinal: int
    previous_generation: bytes | None
    closed_reserved: int | None
    closed_spent: int | None


@dataclass(frozen=True)
class _AttemptFactsV5:
    attempt: ObjectAttemptV5
    scope_id: bytes
    generation_id: bytes
    proposal_bytes: bytes
    admission_bytes: bytes
    nonce: bytes
    row_bytes: bytes
    work_proposal: ObjectEffectV3
    generation: _GenerationFactsV5


def _stored_bytes(value, length=None, label='stored bytes'):
    if type(value) is not bytes or (length is not None and len(value) != length):
        raise EffectV3Error(label + ' has invalid encoding')
    return value


def _stored_integer(value, *, positive=False, label='stored integer'):
    try:
        return integer(value, positive=positive)
    except EffectV3Error:
        raise EffectV3Error(label + ' has invalid encoding') from None


class PostgresAttemptJournalV5(ImmutableRuntimeConfiguration):
    """Append authenticated outcomes into immutable attempt/event facts.

    Funding/dispatched payloads are opaque unverified native data. Only signed
    provider completion or exact retained fenced-absence evidence can close an
    attempt and change the V5 budget head. Native settlement is separate.
    """

    _immutable_runtime_fields = frozenset({
        'runtime_policy', 'database', 'identity', 'native_config_hash',
        'runtime_role', 'migration_role', 'check_manifest', '_clock',
    })

    def __init__(self, database, identity, *, native_config_hash, runtime_role,
            migration_role, check_manifest, clock=lambda: time.time_ns() // 1_000_000_000):
        self.runtime_policy = load_runtime_policy()
        if self.runtime_policy.is_live:
            raise RuntimeConfigurationError('Unqualified attempt journal cannot run in live mode')
        if type(database) is not PostgresAuthorityDatabaseV5:
            raise EffectV3Error('exact configured PostgreSQL authority storage5 required')
        if type(identity) is not ObjectProviderIdentityV3:
            raise EffectV3Error('typed authority/provider public identity required')
        if type(check_manifest) is not ExpectedChecksV5:
            raise EffectV3Error('explicit V5 PostgreSQL check manifest required')
        check_manifest.validate()
        native_config_hash = hash32(native_config_hash, 'native configuration hash')
        if (database.runtime_role != runtime_role or database.migration_role != migration_role or
                type(runtime_role) is not str or type(migration_role) is not str or
                database.check_manifest.digest != check_manifest.digest):
            raise EffectV3Error('journal and database role/check configuration differ')
        expected = authority_configuration_v5(
            identity, native_config_hash, runtime_role, migration_role, check_manifest,
        )
        if database.configuration_hash != expected:
            raise EffectV3Error('authority storage5 belongs to another identity/configuration')
        if not callable(clock):
            raise EffectV3Error('explicit journal clock required')
        self.database = database
        self.identity = identity
        self.native_config_hash = native_config_hash
        self.runtime_role = runtime_role
        self.migration_role = migration_role
        self.check_manifest = check_manifest
        self._clock = clock
        self._freeze_runtime_configuration()

    def _now(self):
        if load_runtime_policy() != self.runtime_policy or self.runtime_policy.is_live:
            raise RuntimeConfigurationError('attempt journal runtime policy changed or became live')
        return _stored_integer(self._clock(), label='journal time')

    @staticmethod
    def _lock_operation(cursor, operation_id):
        operation_id = hash32(operation_id, 'logical operation')
        key = int.from_bytes(hashlib.sha256(
            b'VAMS:ATTEMPT-OP-LOCK:v5\0' + operation_id).digest()[:8], 'big', signed=True)
        cursor.execute('SELECT pg_catalog.pg_advisory_xact_lock(%s)', (key,))

    @staticmethod
    def _lock_scope(cursor, scope_id):
        # Match the existing V3/V4 authority scope lock exactly.
        scope_id = hash32(scope_id, 'authority scope')
        key = int.from_bytes(scope_id[:8], 'big', signed=True)
        cursor.execute('SELECT pg_catalog.pg_advisory_xact_lock(%s)', (key,))

    def _locate_attempt(self, cursor, attempt_id):
        hash32(attempt_id, 'native attempt')
        cursor.execute(f'SELECT operation_id,scope_id FROM {ATTEMPTS5} WHERE attempt_id=%s', (attempt_id,))
        row = cursor.fetchone()
        if row is None or type(row) not in (tuple, list) or len(row) != 2:
            raise EffectV3Error('retained V5 attempt is missing or malformed')
        return (_stored_bytes(row[0], 32, 'operation ID'),
                _stored_bytes(row[1], 32, 'scope ID'))

    def _load_generation(self, cursor, scope_id, generation_id, now, *, allow_installing=False):
        cursor.execute(f'''SELECT scope_bytes,status,fence_bytes,update_bytes,ack_bytes,
            generation_id,ordinal,previous_generation,closed_reserved,closed_spent
            FROM {GENERATIONS5} WHERE scope_id=%s AND generation_id=%s''',
            (scope_id, generation_id))
        row = cursor.fetchone()
        if row is None or type(row) not in (tuple, list) or len(row) != 10:
            raise EffectV3Error('retained V5 authority generation is missing or malformed')
        scope_bytes = _stored_bytes(row[0], label='scope encoding')
        scope = ObjectAuthorityScopeV3.from_bytes(scope_bytes)
        status = row[1]
        if type(allow_installing) is not bool:
            raise EffectV3Error('explicit generation phase required')
        allowed=('installing','active','draining','revoked') if allow_installing else ('active','draining','revoked')
        if status not in allowed:
            raise EffectV3Error('attempt references a non-operational authority generation')
        stored_generation_id = _stored_bytes(row[5], 32, 'generation ID')
        actual_generation_id = commitment(GENERATION_DOMAIN_V5, scope.canonical_bytes())
        if (stored_generation_id != generation_id or actual_generation_id != generation_id or
                scope.scope_id != scope_id):
            raise EffectV3Error('stored canonical scope does not derive the attempt generation')
        ordinal = _stored_integer(row[6], positive=True, label='generation ordinal')
        previous = None if row[7] is None else _stored_bytes(row[7], 32, 'previous generation')
        if (ordinal == 1) != (previous is None) or (previous is not None and previous == generation_id):
            raise EffectV3Error('stored generation predecessor is inconsistent')
        fence = ObjectFenceV3.from_bytes(_stored_bytes(row[2], label='generation fence'))
        update = SignedEffectReceiptV3.from_bytes(_stored_bytes(row[3], label='generation update'))
        verify_fence_update(fence, update, self.identity.authority, fence.issued_at)
        initial = ObjectFenceV3.from_context(scope.template, scope.fencing_token)
        if (fence.scope_id != scope_id or fence.provider_id != self.identity.provider_id or
                fence.host_domain != self.identity.host_domain or fence.chain_id != self.identity.chain_id):
            raise EffectV3Error('retained generation fence identity mismatch')
        if status in ('installing','active') and fence != initial:
            raise EffectV3Error('initial generation fence differs from canonical grant')
        if status in ('draining', 'revoked') and (
                fence.authority_epoch <= initial.authority_epoch or
                fence.fencing_token <= initial.fencing_token or
                fence.policy_version < initial.policy_version or
                (fence.policy_root != initial.policy_root and fence.policy_version == initial.policy_version)):
            raise EffectV3Error('retained cutover does not strictly fence the canonical grant')
        ack = None if row[4] is None else SignedEffectReceiptV3.from_bytes(
            _stored_bytes(row[4], label='generation acknowledgement'))
        if ack is not None:
            verify_fence_ack(fence, update, ack, self.identity.provider, now,
                authority=self.identity.authority)
        if status=='installing' and ack is not None:
            raise EffectV3Error('installing generation cannot already be acknowledged')
        if status == 'active' and ack is None:
            raise EffectV3Error('active generation has no retained provider acknowledgement')
        closed_reserved = None if row[8] is None else _stored_integer(row[8], label='closed reserved')
        closed_spent = None if row[9] is None else _stored_integer(row[9], label='closed spent')
        if status == 'revoked':
            if closed_reserved != 0 or closed_spent is None:
                raise EffectV3Error('revoked generation budget snapshot is malformed')
            if ack is None:
                raise EffectV3Error('revoked generation lacks retained fence acknowledgement')
        elif closed_reserved is not None or closed_spent is not None:
            raise EffectV3Error('open generation contains a closure snapshot')
        return _GenerationFactsV5(scope, status, fence, update, ack,
            generation_id, ordinal, previous, closed_reserved, closed_spent)

    def _load_attempt_facts(self, cursor, attempt_id, now):
        cursor.execute(f'''SELECT attempt_id,operation_id,attempt_no,logical_work,predecessor_attempt_id,
            scope_id,generation_id,native_chain_id,native_contract,allocation_id,allocation_index,
            row_bytes,row_digest,proposal_bytes,proposal_digest,admission_bytes,admission_digest,
            nonce,budget_unit,cost_units FROM {ATTEMPTS5} WHERE attempt_id=%s''', (attempt_id,))
        row = cursor.fetchone()
        if row is None or type(row) not in (tuple, list) or len(row) != 20:
            raise EffectV3Error('retained V5 attempt is missing or malformed')
        stored_attempt_id = _stored_bytes(row[0], 32, 'attempt ID')
        operation_id = _stored_bytes(row[1], 32, 'operation ID')
        attempt_no = _stored_integer(row[2], positive=True, label='attempt ordinal')
        stored_logical_work = _stored_bytes(row[3], 32, 'logical work')
        predecessor = None if row[4] is None else _stored_bytes(row[4], 32, 'attempt predecessor')
        scope_id = _stored_bytes(row[5], 32, 'scope ID')
        generation_id = _stored_bytes(row[6], 32, 'generation ID')
        chain_id = _stored_integer(row[7], positive=True, label='native chain ID')
        contract = _stored_bytes(row[8], 32, 'native contract')
        allocation_id = _stored_bytes(row[9], 32, 'allocation ID')
        allocation_index = _stored_integer(row[10], label='allocation index')
        row_bytes = _stored_bytes(row[11], 128, 'native row')
        row_digest = _stored_bytes(row[12], 32, 'native row digest')
        proposal_bytes = _stored_bytes(row[13], label='proposal bytes')
        proposal_digest = _stored_bytes(row[14], 32, 'proposal digest')
        admission_bytes = _stored_bytes(row[15], label='admission bytes')
        admission_digest = _stored_bytes(row[16], 32, 'admission digest')
        nonce = _stored_bytes(row[17], 32, 'proposal nonce')
        budget_unit = _stored_bytes(row[18], 32, 'budget unit')
        cost_units = _stored_integer(row[19], label='cost units')

        proposal = ObjectEffectV3.from_bytes(proposal_bytes)
        admission = SignedEffectReceiptV3.from_bytes(admission_bytes)
        native_row = NativeObjectRowV1(chain_id, contract, allocation_id, allocation_index)
        native_row.validate()
        if (hashlib.sha256(row_bytes).digest() != row_digest or
                native_row.canonical_bytes() != row_bytes or
                proposal.digest != proposal_digest or
                admission.digest != admission_digest or
                proposal.context.nonce != nonce or
                (proposal.operation_id, proposal.cost_units, proposal.context.budget_unit) !=
                (operation_id, cost_units, budget_unit)):
            raise EffectV3Error('stored V5 attempt bytes/digests/nonce are inconsistent')
        attempt = ObjectAttemptV5(native_row, proposal, admission, attempt_no, predecessor)
        attempt.validate()
        if (stored_attempt_id != attempt_id or attempt.attempt_id != stored_attempt_id or
                native_attempt_id(native_row, proposal, admission) != stored_attempt_id or
                logical_work(proposal) != stored_logical_work):
            raise EffectV3Error('stored V5 attempt identity/logical-work commitment mismatch')

        cursor.execute(f'''SELECT logical_work,initial_proposal_bytes,initial_proposal_digest,
            postcondition,budget_unit,cost_units FROM {WORK5} WHERE operation_id=%s''', (operation_id,))
        work = cursor.fetchone()
        if work is None or type(work) not in (tuple, list) or len(work) != 6:
            raise EffectV3Error('immutable V5 logical-work row is missing or malformed')
        work_id = _stored_bytes(work[0], 32, 'work digest')
        work_proposal_bytes = _stored_bytes(work[1], label='initial proposal')
        work_proposal_digest = _stored_bytes(work[2], 32, 'initial proposal digest')
        work_proposal = ObjectEffectV3.from_bytes(work_proposal_bytes)
        work_postcondition = _stored_bytes(work[3], 32, 'work postcondition')
        work_budget_unit = _stored_bytes(work[4], 32, 'work budget unit')
        work_cost = _stored_integer(work[5], label='work cost')
        if (work_proposal.digest != work_proposal_digest or
                work_proposal.operation_id != operation_id or
                logical_work(work_proposal) != work_id or stored_logical_work != work_id or
                work_postcondition != work_proposal.postcondition or
                work_budget_unit != work_proposal.context.budget_unit or
                work_cost != work_proposal.cost_units or
                logical_work(proposal) != logical_work(work_proposal)):
            raise EffectV3Error('immutable V5 logical-work row does not match attempt history')
        if attempt_no == 1 and (work_proposal_bytes != proposal_bytes or work_proposal_digest != proposal_digest):
            raise EffectV3Error('first attempt differs from immutable initial proposal')
        if attempt_no > 1:
            if predecessor is None:
                raise EffectV3Error('successor attempt lacks exact predecessor')
            cursor.execute(f'''SELECT operation_id,attempt_no,logical_work FROM {ATTEMPTS5}
                WHERE attempt_id=%s''', (predecessor,))
            previous = cursor.fetchone()
            if (previous is None or type(previous) not in (tuple, list) or len(previous) != 3 or
                    _stored_bytes(previous[0], 32, 'predecessor operation') != operation_id or
                    _stored_integer(previous[1], positive=True, label='predecessor ordinal') != attempt_no - 1 or
                    _stored_bytes(previous[2], 32, 'predecessor logical work') != stored_logical_work):
                raise EffectV3Error('attempt predecessor does not match immediate stable-work history')

        generation = self._load_generation(cursor, scope_id, generation_id, now)
        if generation.scope.template.budget_unit != budget_unit:
            raise EffectV3Error('attempt budget unit differs from canonical scope')
        generation.scope.permits(proposal)
        verify_admitted_obligation(proposal, admission, self.identity.authority, now)
        if (proposal.context.provider_id, proposal.context.host_domain, proposal.context.runtime_id,
                proposal.context.target, proposal.context.chain_id) != (
                self.identity.provider_id, self.identity.host_domain, self.identity.runtime_id,
                self.identity.target, self.identity.chain_id):
            raise EffectV3Error('attempt provider binding differs from configured public identity')
        return _AttemptFactsV5(attempt, scope_id, generation_id, proposal_bytes,
            admission_bytes, nonce, row_bytes, work_proposal, generation)

    def _load_events(self, cursor, facts):
        cursor.execute(f'''SELECT event_seq,predecessor_event_seq,kind,payload_bytes,
            payload_digest,event_digest FROM {EVENTS5} WHERE attempt_id=%s
            ORDER BY event_seq LIMIT %s''', (facts.attempt.attempt_id, MAX_EVENTS + 1))
        rows = cursor.fetchall()
        if type(rows) is not list or len(rows) > MAX_EVENTS:
            raise EffectV3Error('attempt event history exceeds fixed bound or is malformed')
        events = []
        for index, row in enumerate(rows, start=1):
            if type(row) not in (tuple, list) or len(row) != 6:
                raise EffectV3Error('attempt event row has invalid shape')
            seq = _stored_integer(row[0], positive=True, label='event sequence')
            predecessor_seq = None if row[1] is None else _stored_integer(row[1], positive=True,
                label='event predecessor sequence')
            kind = row[2]
            if type(kind) is not str:
                raise EffectV3Error('attempt event kind has invalid type')
            payload = _stored_bytes(row[3], label='event payload')
            payload_digest = _stored_bytes(row[4], 32, 'event payload digest')
            event_digest = _stored_bytes(row[5], 32, 'event digest')
            previous = events[-1] if events else None
            if (seq != index or predecessor_seq != (None if previous is None else previous.sequence)):
                raise EffectV3Error('attempt event sequence/predecessor gap')
            event = AttemptEventV5(facts.attempt.attempt_id, seq,
                None if previous is None else previous.digest, kind, payload)
            event.validate()
            if event.payload_digest != payload_digest or event.digest != event_digest:
                raise EffectV3Error('attempt event payload/hash mismatch')
            if previous is not None:
                event.follows(previous)
            elif payload != reserved_payload(facts.attempt.link_digest, facts.generation_id):
                raise EffectV3Error('first reserved event does not bind canonical attempt/generation')
            events.append(event)
        if not events or events[0].kind != 'reserved':
            raise EffectV3Error('attempt lacks its immutable initial reservation event')
        return tuple(events)

    def _load_head(self, cursor, scope_id, *, for_update):
        suffix = ' FOR UPDATE' if for_update else ''
        cursor.execute(f'''SELECT current_generation,budget_unit,budget_limit,budget_reserved,budget_spent
            FROM {HEADS5} WHERE scope_id=%s{suffix}''', (scope_id,))
        row = cursor.fetchone()
        if row is None or type(row) not in (tuple, list) or len(row) != 5:
            raise EffectV3Error('V5 mutable budget head is missing or malformed')
        head = (
            _stored_bytes(row[0], 32, 'head generation'),
            _stored_bytes(row[1], 32, 'head budget unit'),
            _stored_integer(row[2], positive=True, label='head budget limit'),
            _stored_integer(row[3], label='head reserved budget'),
            _stored_integer(row[4], label='head spent budget'),
        )
        if head[4] > head[2] or head[3] > head[2] - head[4]:
            raise EffectV3Error('V5 mutable budget head violates cumulative limits')
        return head

    def _completion_row(self, cursor, operation_id):
        cursor.execute(f'''SELECT attempt_no,attempt_id,completion_event_seq,receipt_bytes,receipt_digest
            FROM {COMPLETIONS5} WHERE operation_id=%s''', (operation_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        if type(row) not in (tuple, list) or len(row) != 5:
            raise EffectV3Error('V5 completion row is malformed')
        return (
            _stored_integer(row[0], positive=True, label='completion attempt number'),
            _stored_bytes(row[1], 32, 'completion attempt ID'),
            _stored_integer(row[2], positive=True, label='completion event sequence'),
            _stored_bytes(row[3], label='completion receipt'),
            _stored_bytes(row[4], 32, 'completion receipt digest'),
        )

    def _history(self, cursor, attempt_id, now):
        operation_id, scope_id = self._locate_attempt(cursor, attempt_id)
        self._lock_operation(cursor, operation_id)
        self._lock_scope(cursor, scope_id)
        facts = self._load_attempt_facts(cursor, attempt_id, now)
        if facts.attempt.proposal.operation_id != operation_id or facts.scope_id != scope_id:
            raise EffectV3Error('attempt identity changed while locking history')
        head = self._load_head(cursor, scope_id, for_update=False)
        if head[1] != facts.attempt.proposal.context.budget_unit:
            raise EffectV3Error('budget head unit differs from immutable work')
        if facts.generation.closed_spent is not None and facts.generation.closed_spent > head[4]:
            raise EffectV3Error('closed generation spend exceeds cumulative budget head')
        events = self._load_events(cursor, facts)
        completion = self._completion_row(cursor, operation_id)
        tail = events[-1]
        if tail.kind not in ('completed','absent') and (
                facts.generation.status=='revoked' or head[0]!=facts.generation_id):
            raise EffectV3Error('unresolved prior generation requires explicit reconciliation')
        if tail.kind == 'completed':
            receipt = SignedEffectReceiptV3.from_bytes(tail.payload)
            verify_effect(facts.attempt.proposal, facts.attempt.admission, receipt,
                self.identity.provider, now, authority=self.identity.authority)
            if (completion is None or completion[0] != facts.attempt.ordinal or
                    completion[1] != facts.attempt.attempt_id or completion[2] != tail.sequence or
                    completion[3] != tail.payload or completion[4] != receipt.digest):
                raise EffectV3Error('authenticated completion event and immutable completion row differ')
            outcome = 'completed'
            evidence = receipt
        elif tail.kind == 'absent':
            payload = FencedAbsencePayloadV5.from_bytes(tail.payload)
            self._authenticate_absence_facts(facts, payload, now)
            if completion is not None and completion[1] == facts.attempt.attempt_id:
                raise EffectV3Error('same attempt is both completed and absent')
            outcome = 'absent'
            evidence = payload
        else:
            if completion is not None:
                raise EffectV3Error('logical completion contradicts a nonterminal attempt history')
            outcome = 'pending'
            evidence = None
        return AttemptJournalReadV5(facts.attempt, facts.generation_id, events, outcome, evidence), facts, head

    def _authenticate_absence_facts(self, facts, payload, now):
        generation = facts.generation
        if (generation.status not in ('draining', 'revoked') or generation.acknowledgement is None or
                payload.fence.canonical_bytes() != generation.fence.canonical_bytes() or
                payload.update.canonical_bytes() != generation.update.canonical_bytes() or
                payload.acknowledgement.canonical_bytes() != generation.acknowledgement.canonical_bytes()):
            raise EffectV3Error('absence does not match the exact retained acknowledged generation cutover')
        payload.authenticate(facts.attempt.proposal, facts.attempt.admission,
            authority=self.identity.authority, provider=self.identity.provider, now=now)

    def read_attempt(self, attempt_id):
        now = self._now()
        with self.database.transaction() as cursor:
            result, _, _ = self._history(cursor, attempt_id, now)
            return result

    def _append_event(self, cursor, facts, events, kind, payload):
        previous = events[-1]
        event = next_event(previous, kind, payload)
        if event.sequence > MAX_EVENTS:
            raise EffectV3Error('attempt event history reached its fixed bound')
        cursor.execute(EVENT_INSERT, (
            facts.attempt.proposal.operation_id,
            facts.attempt.ordinal,
            facts.attempt.attempt_id,
            event.sequence,
            previous.sequence,
            event.kind,
            event.payload,
            event.payload_digest,
            event.digest,
        ))
        return events + (event,)

    def _release_or_spend(self, cursor, facts, cost, *, spend):
        head = self._load_head(cursor, facts.scope_id, for_update=True)
        if (head[0] != facts.generation_id or facts.generation.status=='revoked' or
                head[1] != facts.attempt.proposal.context.budget_unit or head[3] < cost):
            raise EffectV3Error('V5 budget reservation does not cover this pending attempt')
        if spend:
            if head[4] > head[2] - cost:
                raise EffectV3Error('V5 cumulative budget would exceed its configured limit')
            cursor.execute(f'''UPDATE {HEADS5} SET budget_reserved=budget_reserved-%s,
                budget_spent=budget_spent+%s WHERE scope_id=%s AND budget_reserved>=%s
                AND budget_spent<=budget_limit-%s''',
                (cost, cost, facts.scope_id, cost, cost))
        else:
            cursor.execute(f'''UPDATE {HEADS5} SET budget_reserved=budget_reserved-%s
                WHERE scope_id=%s AND budget_reserved>=%s''', (cost, facts.scope_id, cost))
        if getattr(cursor, 'rowcount', None) != 1:
            raise EffectV3Error('V5 budget head changed or reservation was already consumed')

    def accept_effect(self, attempt_id, signed_receipt):
        if type(signed_receipt) is not SignedEffectReceiptV3:
            raise EffectV3Error('typed signed V3 provider receipt required')
        receipt_bytes = signed_receipt.canonical_bytes()
        now = self._now()
        with self.database.transaction() as cursor:
            result, facts, head = self._history(cursor, attempt_id, now)
            if result.outcome == 'completed':
                if result.terminal_evidence != signed_receipt:
                    raise EffectV3Error('conflicting provider completion evidence')
                return result
            if result.outcome == 'absent':
                raise EffectV3Error('authenticated absence conflicts with provider completion')
            completion = self._completion_row(cursor, facts.attempt.proposal.operation_id)
            if completion is not None:
                raise EffectV3Error('logical operation already has a permanent completion')
            verify_effect(facts.attempt.proposal, facts.attempt.admission, signed_receipt,
                self.identity.provider, now, authority=self.identity.authority)
            completed_events = self._append_event(cursor, facts, result.events, 'completed', receipt_bytes)
            completed_event = completed_events[-1]
            cursor.execute(f'''INSERT INTO {COMPLETIONS5}(
                operation_id,attempt_no,attempt_id,completion_event_seq,receipt_bytes,receipt_digest)
                VALUES(%s,%s,%s,%s,%s,%s)''', (
                facts.attempt.proposal.operation_id,
                facts.attempt.ordinal,
                facts.attempt.attempt_id,
                completed_event.sequence,
                receipt_bytes,
                signed_receipt.digest,
            ))
            self._release_or_spend(cursor, facts, facts.attempt.proposal.cost_units, spend=True)
            return AttemptJournalReadV5(facts.attempt, facts.generation_id, completed_events,
                'completed', signed_receipt, False)

    def accept_absence(self, attempt_id, absence_payload):
        if type(absence_payload) is not FencedAbsencePayloadV5:
            raise EffectV3Error('typed retained fenced-absence payload required')
        payload_bytes = absence_payload.canonical_bytes()
        now = self._now()
        with self.database.transaction() as cursor:
            result, facts, _ = self._history(cursor, attempt_id, now)
            if result.outcome == 'absent':
                if result.terminal_evidence != absence_payload:
                    raise EffectV3Error('conflicting authenticated absence evidence')
                return result
            if result.outcome == 'completed':
                raise EffectV3Error('permanent completion conflicts with fenced absence')
            completion = self._completion_row(cursor, facts.attempt.proposal.operation_id)
            if completion is not None:
                raise EffectV3Error('logical operation already has a permanent completion')
            self._authenticate_absence_facts(facts, absence_payload, now)
            new_events = self._append_event(cursor, facts, result.events, 'absent', payload_bytes)
            self._release_or_spend(cursor, facts, facts.attempt.proposal.cost_units, spend=False)
            return AttemptJournalReadV5(facts.attempt, facts.generation_id, new_events,
                'absent', absence_payload, False)

    def mark_funding_unknown(self, attempt_id):
        now = self._now()
        with self.database.transaction() as cursor:
            result, facts, _ = self._history(cursor, attempt_id, now)
            if result.outcome != 'pending':
                raise EffectV3Error('terminal attempt cannot be marked funding-unknown')
            tail = result.events[-1]
            if tail.kind == 'funding_unknown':
                return result
            if tail.kind != 'reserved':
                raise EffectV3Error('funding can be marked unknown only from the initial reservation')
            payload = unknown_payload(facts.attempt.attempt_id, funding=True)
            events = self._append_event(cursor, facts, result.events, 'funding_unknown', payload)
            return AttemptJournalReadV5(facts.attempt, facts.generation_id, events,
                'pending', None, False)
