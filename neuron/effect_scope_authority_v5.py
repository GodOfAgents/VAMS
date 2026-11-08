"""Source-preparation V5 lifecycle for install, cutover, closure, and renewal.

This candidate is not integrated or qualified. It emits no signed V3/V4 or V5
wire changes and does not admit successor effects, verify native funding, settle,
or make a runtime available in live mode.
"""
from dataclasses import dataclass

from neuron.effect_attempt_journal_v5 import (
    GENERATION_DOMAIN_V5,
    PostgresAttemptJournalV5,
)
from neuron.effect_authority_store_v5 import (
    ATTEMPTS5,
    GENERATIONS5,
    HEADS5,
    MAX_GENERATION_ATTEMPTS5,
)
from neuron.effect_authority_v3 import (
    ObjectAuthorityScopeV3,
    ReconciliationRequiredV3,
)
from neuron.effect_authority_v4 import CurrentRenewalPolicyV1
from neuron.effect_initial_authority_v5 import PostgresInitialAttemptAuthorityV5
from neuron.effect_protocol_v3 import (
    EffectV3Error,
    ObjectFenceV3,
    SignedEffectReceiptV3,
    commitment,
    hash32,
    integer,
    sign_receipt,
    verify_fence_ack,
)


@dataclass(frozen=True)
class ScopeStateV5:
    scope: ObjectAuthorityScopeV3
    status: str
    reserved: int
    spent: int
    fence: ObjectFenceV3
    update: SignedEffectReceiptV3
    acknowledgement: SignedEffectReceiptV3 | None
    generation_id: bytes
    ordinal: int
    previous_generation: bytes | None
    closed_reserved: int | None
    closed_spent: int | None

    def __post_init__(self):
        if type(self.scope) is not ObjectAuthorityScopeV3:
            raise EffectV3Error('typed V5 authority scope required')
        if self.status not in ('installing', 'active', 'draining', 'revoked'):
            raise EffectV3Error('invalid V5 scope lifecycle state')
        hash32(self.generation_id, 'V5 generation')
        integer(self.ordinal, positive=True)
        integer(self.reserved)
        integer(self.spent)
        if self.previous_generation is not None:
            hash32(self.previous_generation, 'previous V5 generation')

    @property
    def ack(self):
        # Preserve the accepted renewal policy's previous-state interface.
        return self.acknowledgement


class PostgresScopeAuthorityV5(PostgresInitialAttemptAuthorityV5):
    """V5 lifecycle over the exact initial-attempt writer and PG5 store.

    Every returned authority update crosses a successfully exited transaction.
    Generation closure authenticates bounded journal histories, not row counts
    or mutable event/status labels. No method here dispatches or settles effects.
    """

    def __init__(self, database, identity, authority_signer, policy, **configuration):
        if not isinstance(policy, CurrentRenewalPolicyV1):
            raise EffectV3Error('authenticated V5 renewal governance contract required')
        super().__init__(database, identity, authority_signer, policy, **configuration)

    @staticmethod
    def _generation_id(scope):
        if type(scope) is not ObjectAuthorityScopeV3:
            raise EffectV3Error('typed canonical authority scope required')
        return commitment(GENERATION_DOMAIN_V5, scope.canonical_bytes())

    @staticmethod
    def _check_generation_link(generation_id, scope, ordinal, predecessor):
        if hash32(generation_id) != PostgresScopeAuthorityV5._generation_id(scope):
            raise EffectV3Error('V5 generation does not commit exact canonical scope')
        integer(ordinal, positive=True)
        if (ordinal == 1) != (predecessor is None):
            raise EffectV3Error('invalid V5 generation predecessor/ordinal')
        if predecessor is not None:
            hash32(predecessor)
            if predecessor == generation_id:
                raise EffectV3Error('V5 generation cannot precede itself')

    def _scope_identity(self, scope):
        scope.validate()
        c, identity = scope.template, self.identity
        if (c.provider_id, c.runtime_id, c.host_domain, c.target, c.chain_id) != (
                identity.provider_id, identity.runtime_id, identity.host_domain,
                identity.target, identity.chain_id):
            raise EffectV3Error('scope differs from configured provider/runtime/host/target/chain')

    def _scope_current(self, scope, now):
        self._scope_identity(scope)
        self._scope_policy(scope, now)
        current = self._now()
        if current < now or not scope.template.issued_at <= current < scope.template.expires_at:
            raise EffectV3Error('scope expired or clock moved backwards during governance check')
        # Re-evaluate the current governed grant after the clock read.
        self._scope_policy(scope, current)
        return current

    def _fence_update(self, scope, now):
        fence = ObjectFenceV3.from_context(scope.template, scope.fencing_token)
        if not fence.issued_at <= now < fence.expires_at:
            raise EffectV3Error('new V5 authority fence is not current')
        update = sign_receipt(
            self._signer,
            purpose=2,
            subject=fence.digest,
            provider=fence.provider_id,
            epoch=fence.authority_epoch,
            policy=fence.policy_version,
            fence=fence.fencing_token,
            issued_at=fence.issued_at,
            expires_at=fence.expires_at,
        )
        return fence, update

    def _scope_policy(self, scope, now):
        self._scope_identity(scope)
        c=scope.template
        if not c.issued_at<=now<c.expires_at:
            raise EffectV3Error('governed scope is not current')
        if self._policy.assert_scope_allowed(scope,now) is not None:
            raise EffectV3Error('current host governance denied or did not decide scope')

    def _insert_generation(self, cursor, scope, ordinal, predecessor, fence, update):
        generation_id = self._generation_id(scope)
        self._check_generation_link(generation_id, scope, ordinal, predecessor)
        cursor.execute(f'''INSERT INTO {GENERATIONS5}(
            generation_id,scope_id,ordinal,previous_generation,scope_bytes,status,
            fence_bytes,update_bytes,ack_bytes,closed_reserved,closed_spent)
            VALUES(%s,%s,%s,%s,%s,'installing',%s,%s,NULL,NULL,NULL)''', (
            generation_id, scope.scope_id, ordinal, predecessor, scope.canonical_bytes(),
            fence.canonical_bytes(), update.canonical_bytes(),
        ))
        if getattr(cursor, 'rowcount', 1) != 1:
            raise EffectV3Error('V5 generation insertion did not commit one row')
        return generation_id

    def _load_head_and_generation(self, cursor, scope_id, now, *, for_update, allow_installing=True):
        head = self._load_head(cursor, scope_id, for_update=for_update)
        generation = self._load_generation(
            cursor, scope_id, head[0], now, allow_installing=allow_installing,
        )
        if generation.scope.scope_id != scope_id:
            raise EffectV3Error('canonical scope differs from requested scope ID')
        self._scope_identity(generation.scope)
        if head[1] != generation.scope.template.budget_unit or head[2] != generation.scope.budget_limit:
            raise EffectV3Error('V5 head unit/absolute ceiling differs from canonical generation')
        if head[4] > head[2] or head[3] > head[2] - head[4]:
            raise EffectV3Error('V5 head violates cumulative budget ceiling')
        if generation.status == 'revoked':
            if (generation.closed_reserved != 0 or generation.closed_spent != head[4] or
                    head[3] != 0):
                raise EffectV3Error('revoked generation snapshot differs from cumulative head')
        elif generation.closed_reserved is not None or generation.closed_spent is not None:
            raise EffectV3Error('open V5 generation contains a closure snapshot')
        return head, ScopeStateV5(
            generation.scope, generation.status, head[3], head[4], generation.fence,
            generation.update, generation.acknowledgement, generation.generation_id,
            generation.ordinal, generation.previous_generation,
            generation.closed_reserved, generation.closed_spent,
        )

    def read_scope(self, scope_id):
        hash32(scope_id, 'scope ID')
        now = self._now()
        with self.database.transaction() as cursor:
            _, state = self._load_head_and_generation(
                cursor, scope_id, now, for_update=False, allow_installing=True,
            )
            return state

    def prepare_scope(self, scope):
        if type(scope) is not ObjectAuthorityScopeV3:
            raise EffectV3Error('typed canonical V5 authority scope required')
        now = self._scope_current(scope, self._now())
        with self.database.transaction() as cursor:
            self._lock_scope(cursor, scope.scope_id)
            now = self._scope_current(scope, self._now())
            cursor.execute(f'SELECT scope_id FROM {HEADS5} WHERE scope_id=%s', (scope.scope_id,))
            existing_head = cursor.fetchone()
            cursor.execute(f'SELECT generation_id FROM {GENERATIONS5} WHERE scope_id=%s LIMIT 1',
                (scope.scope_id,))
            existing_generation = cursor.fetchone()
            if existing_head is not None or existing_generation is not None:
                raise ReconciliationRequiredV3('existing V5 scope/history cannot be adopted or replaced')
            fence, update = self._fence_update(scope, now)
            now = self._scope_current(scope, self._now())
            if not fence.issued_at <= now < fence.expires_at:
                raise EffectV3Error('initial V5 fence expired before transaction commit')
            generation_id = self._insert_generation(cursor, scope, 1, None, fence, update)
            cursor.execute(f'''INSERT INTO {HEADS5}(
                scope_id,current_generation,budget_unit,budget_limit,budget_reserved,budget_spent)
                VALUES(%s,%s,%s,%s,0,0)''', (
                scope.scope_id, generation_id, scope.template.budget_unit, scope.budget_limit,
            ))
            if getattr(cursor, 'rowcount', 1) != 1:
                raise EffectV3Error('V5 initial scope head insertion did not commit one row')
        return update

    def activate_scope(self, scope_id, acknowledgement):
        hash32(scope_id, 'scope ID')
        if type(acknowledgement) is not SignedEffectReceiptV3:
            raise EffectV3Error('typed provider fence acknowledgement required')
        now = self._now()
        with self.database.transaction() as cursor:
            self._lock_scope(cursor, scope_id)
            head, state = self._load_head_and_generation(
                cursor, scope_id, now, for_update=True, allow_installing=True,
            )
            if state.status != 'installing':
                raise ReconciliationRequiredV3('only an installing V5 generation can activate')
            now = self._scope_current(state.scope, self._now())
            verify_fence_ack(state.fence, state.update, acknowledgement, self.identity.provider,
                now, authority=self.identity.authority)
            self._scope_current(state.scope, self._now())
            cursor.execute(f'''UPDATE {GENERATIONS5} SET status='active',ack_bytes=%s
                WHERE scope_id=%s AND generation_id=%s AND status='installing' AND ack_bytes IS NULL''', (
                acknowledgement.canonical_bytes(), scope_id, state.generation_id,
            ))
            if getattr(cursor, 'rowcount', None) != 1:
                raise ReconciliationRequiredV3('V5 installation changed before acknowledgement commit')
        return ScopeStateV5(state.scope, 'active', head[3], head[4], state.fence, state.update,
            acknowledgement, state.generation_id, state.ordinal, state.previous_generation, None, None)

    def _validate_cutover_fence(self, state, fence, now):
        if type(fence) is not ObjectFenceV3 or fence.scope_id != state.scope.scope_id:
            raise EffectV3Error('typed cutover fence must target exact retained scope')
        if (fence.actor_root, fence.root_scheme, fence.provider_id, fence.host_domain, fence.chain_id) != (
                state.scope.template.actor_root, state.scope.template.root_scheme,
                self.identity.provider_id, self.identity.host_domain, self.identity.chain_id):
            raise EffectV3Error('cutover changes actor/provider/host/chain authority')
        if not fence.issued_at <= now < fence.expires_at:
            raise EffectV3Error('cutover fence is expired or not yet valid')
        old = state.fence
        if (fence.provider_id != old.provider_id or
                fence.authority_epoch <= old.authority_epoch or
                fence.fencing_token <= old.fencing_token or
                fence.policy_version < old.policy_version or
                (fence.policy_root != old.policy_root and fence.policy_version == old.policy_version)):
            raise EffectV3Error('cutover must strictly advance epoch/fence and preserve policy continuity')
        if self._policy.assert_fence_allowed(state.scope, fence, now) is not None:
            raise EffectV3Error('current host governance denied or did not decide cutover')
        current = self._now()
        if current < now or not fence.issued_at <= current < fence.expires_at:
            raise EffectV3Error('cutover fence expired or clock moved during governance decision')
        return current

    def begin_revocation(self, scope_id, fence):
        hash32(scope_id, 'scope ID')
        now = self._now()
        with self.database.transaction() as cursor:
            self._lock_scope(cursor, scope_id)
            _, state = self._load_head_and_generation(
                cursor, scope_id, now, for_update=True, allow_installing=True,
            )
            if state.status not in ('installing', 'active'):
                raise ReconciliationRequiredV3('V5 revocation can begin only before acknowledged cutover')
            now = self._validate_cutover_fence(state, fence, self._now())
            _, update = self._fence_update_for_cutover(fence)
            self._validate_cutover_fence(state, fence, self._now())
            cursor.execute(f'''UPDATE {GENERATIONS5} SET status='draining',fence_bytes=%s,
                update_bytes=%s,ack_bytes=NULL WHERE scope_id=%s AND generation_id=%s
                AND status IN ('installing','active')''', (
                fence.canonical_bytes(), update.canonical_bytes(), scope_id, state.generation_id,
            ))
            if getattr(cursor, 'rowcount', None) != 1:
                raise ReconciliationRequiredV3('V5 generation changed before cutover update')
        return update

    def refresh_unacknowledged_cutover(self, scope_id, fence):
        hash32(scope_id, 'scope ID')
        now = self._now()
        with self.database.transaction() as cursor:
            self._lock_scope(cursor, scope_id)
            _, state = self._load_head_and_generation(
                cursor, scope_id, now, for_update=True, allow_installing=False,
            )
            if state.status != 'draining' or state.acknowledgement is not None:
                raise ReconciliationRequiredV3('only an unacknowledged draining fence can be refreshed')
            now = self._validate_cutover_fence(state, fence, self._now())
            _, update = self._fence_update_for_cutover(fence)
            self._validate_cutover_fence(state, fence, self._now())
            cursor.execute(f'''UPDATE {GENERATIONS5} SET fence_bytes=%s,update_bytes=%s
                WHERE scope_id=%s AND generation_id=%s AND status='draining' AND ack_bytes IS NULL''', (
                fence.canonical_bytes(), update.canonical_bytes(), scope_id, state.generation_id,
            ))
            if getattr(cursor, 'rowcount', None) != 1:
                raise ReconciliationRequiredV3('V5 cutover changed before refresh commit')
        return update

    def _fence_update_for_cutover(self, fence):
        update = sign_receipt(
            self._signer,
            purpose=2,
            subject=fence.digest,
            provider=fence.provider_id,
            epoch=fence.authority_epoch,
            policy=fence.policy_version,
            fence=fence.fencing_token,
            issued_at=fence.issued_at,
            expires_at=fence.expires_at,
        )
        return fence, update

    def record_fence_ack(self, scope_id, fence, update, acknowledgement):
        hash32(scope_id, 'scope ID')
        if (type(fence) is not ObjectFenceV3 or type(update) is not SignedEffectReceiptV3 or
                type(acknowledgement) is not SignedEffectReceiptV3):
            raise EffectV3Error('typed retained V3 fence/update/acknowledgement required')
        now = self._now()
        with self.database.transaction() as cursor:
            self._lock_scope(cursor, scope_id)
            _, state = self._load_head_and_generation(
                cursor, scope_id, now, for_update=True, allow_installing=False,
            )
            if (state.status != 'draining' or state.fence != fence or state.update != update):
                raise EffectV3Error('provider acknowledgement differs from retained current cutover')
            verify_fence_ack(fence, update, acknowledgement, self.identity.provider,
                self._now(), authority=self.identity.authority)
            if state.acknowledgement is not None:
                if state.acknowledgement != acknowledgement:
                    raise EffectV3Error('conflicting retained V5 fence acknowledgement')
                return state
            cursor.execute(f'''UPDATE {GENERATIONS5} SET ack_bytes=%s WHERE scope_id=%s
                AND generation_id=%s AND status='draining' AND ack_bytes IS NULL
                AND fence_bytes=%s AND update_bytes=%s''', (
                acknowledgement.canonical_bytes(), scope_id, state.generation_id,
                fence.canonical_bytes(), update.canonical_bytes(),
            ))
            if getattr(cursor, 'rowcount', None) != 1:
                raise ReconciliationRequiredV3('retained cutover changed before acknowledgement commit')
        return ScopeStateV5(state.scope, state.status, state.reserved, state.spent, state.fence,
            state.update, acknowledgement, state.generation_id, state.ordinal,
            state.previous_generation, state.closed_reserved, state.closed_spent)

    def _attempt_rows(self, cursor, scope_id, generation_id):
        cursor.execute(f'''SELECT operation_id,attempt_id FROM {ATTEMPTS5}
            WHERE scope_id=%s AND generation_id=%s
            ORDER BY operation_id,attempt_id LIMIT %s''',
            (scope_id, generation_id, MAX_GENERATION_ATTEMPTS5 + 1))
        rows = cursor.fetchall()
        if type(rows) is not list or len(rows) > MAX_GENERATION_ATTEMPTS5:
            raise ReconciliationRequiredV3('V5 generation exceeds its bounded attempt-history limit')
        result = []
        for row in rows:
            if type(row) not in (tuple, list) or len(row) != 2:
                raise EffectV3Error('V5 generation attempt index has invalid shape')
            result.append((hash32(row[0], 'logical operation'), hash32(row[1], 'attempt ID')))
        if result != sorted(set(result)):
            raise EffectV3Error('V5 generation attempt index is not unique/canonical')
        return tuple(result)

    def _lock_and_reload_generation(self, cursor, scope_id, now):
        # Read exact attempt identities, lock all operations in canonical order,
        # then scope; reload after locking and reject any changed indexed set.
        first_head = self._load_head(cursor, scope_id, for_update=False)
        first_rows = self._attempt_rows(cursor, scope_id, first_head[0])
        for operation_id in sorted({row[0] for row in first_rows}):
            self._lock_operation(cursor, operation_id)
        self._lock_scope(cursor, scope_id)
        head, state = self._load_head_and_generation(
            cursor, scope_id, now, for_update=True, allow_installing=False,
        )
        second_rows = self._attempt_rows(cursor, scope_id, head[0])
        if head[0] != first_head[0] or second_rows != first_rows:
            raise ReconciliationRequiredV3('V5 generation attempt set changed while acquiring locks')
        return head, state, second_rows

    def _previous_cumulative_spent(self, cursor, state, now):
        if state.previous_generation is None:
            if state.ordinal != 1:
                raise EffectV3Error('generation chain omits its predecessor')
            return 0
        predecessor = self._load_generation(
            cursor, state.scope.scope_id, state.previous_generation, now,
            allow_installing=False,
        )
        if (predecessor.status != 'revoked' or predecessor.acknowledgement is None or
                predecessor.closed_reserved != 0 or predecessor.closed_spent is None or
                predecessor.ordinal + 1 != state.ordinal or
                predecessor.generation_id != state.previous_generation):
            raise EffectV3Error('V5 predecessor lacks an authenticated closed budget snapshot')
        return predecessor.closed_spent

    def _audit_terminal_projection(self, cursor, state, head, attempt_rows, now):
        previous_spent = self._previous_cumulative_spent(cursor, state, now)
        completed_spend = 0
        pending_reservations = 0
        pending_count = 0
        for operation_id, attempt_id in attempt_rows:
            read, facts, _ = self._history(cursor, attempt_id, now)
            if (facts.attempt.proposal.operation_id != operation_id or
                    facts.scope_id != state.scope.scope_id or
                    facts.generation_id != state.generation_id):
                raise EffectV3Error('terminal attempt history differs from its indexed generation')
            if read.outcome == 'pending':
                pending_reservations += facts.attempt.proposal.cost_units
                pending_count += 1
            if read.outcome == 'completed':
                completed_spend += facts.attempt.proposal.cost_units
        if pending_reservations != head[3]:
            raise EffectV3Error('V5 pending attempt costs differ from the aggregate reserved head')
        if pending_count != 0 or head[3] != 0:
            raise ReconciliationRequiredV3('pending or unknown V5 attempts block generation closure')
        if previous_spent + completed_spend != head[4]:
            raise ReconciliationRequiredV3('V5 generation completion spend differs from cumulative head')
        return completed_spend

    def complete_revocation(self, scope_id):
        hash32(scope_id, 'scope ID')
        now = self._now()
        with self.database.transaction() as cursor:
            head, state, attempt_rows = self._lock_and_reload_generation(cursor, scope_id, now)
            if state.status not in ('draining', 'revoked') or state.acknowledgement is None:
                raise ReconciliationRequiredV3('V5 closure requires an acknowledged draining cutover')
            self._audit_terminal_projection(cursor, state, head, attempt_rows, self._now())
            if state.status == 'revoked':
                return state
            cursor.execute(f'''UPDATE {GENERATIONS5} SET status='revoked',closed_reserved=0,
                closed_spent=%s WHERE scope_id=%s AND generation_id=%s AND status='draining'
                AND ack_bytes=%s AND closed_reserved IS NULL AND closed_spent IS NULL''', (
                head[4], scope_id, state.generation_id, state.acknowledgement.canonical_bytes(),
            ))
            if getattr(cursor, 'rowcount', None) != 1:
                raise ReconciliationRequiredV3('V5 generation changed before closure snapshot commit')
        return ScopeStateV5(state.scope, 'revoked', 0, head[4], state.fence, state.update,
            state.acknowledgement, state.generation_id, state.ordinal, state.previous_generation,
            0, head[4])

    def prepare_renewal(self, successor_scope):
        if type(successor_scope) is not ObjectAuthorityScopeV3:
            raise EffectV3Error('typed successor V5 scope required')
        self._scope_identity(successor_scope)
        now = self._scope_current(successor_scope, self._now())
        with self.database.transaction() as cursor:
            head, old, attempts = self._lock_and_reload_generation(
                cursor, successor_scope.scope_id, self._now(),
            )
            if (old.status != 'revoked' or old.acknowledgement is None or
                    old.reserved != 0 or head[3] != 0 or old.closed_reserved != 0 or
                    old.closed_spent != head[4]):
                raise ReconciliationRequiredV3('V5 renewal requires a closed acknowledged generation')
            self._audit_terminal_projection(cursor, old, head, attempts, self._now())
            if successor_scope.scope_id != old.scope.scope_id:
                raise EffectV3Error('V5 renewal must preserve the exact authority scope identity')
            c, prior = successor_scope.template, old.scope.template
            if (c.provider_id, c.runtime_id, c.host_domain, c.target, c.chain_id) != (
                    prior.provider_id, prior.runtime_id, prior.host_domain,
                    prior.target, prior.chain_id):
                raise EffectV3Error('V5 renewal changes provider/runtime/host/target/chain')
            if (c.budget_unit != prior.budget_unit or
                    c.authority_epoch <= old.fence.authority_epoch or
                    successor_scope.fencing_token <= old.fence.fencing_token or
                    c.policy_version < old.fence.policy_version or
                    c.issued_at < old.acknowledgement.receipt.issued_at or
                    successor_scope.budget_limit < head[4] or
                    (c.policy_root != old.fence.policy_root and
                        c.policy_version == old.fence.policy_version)):
                raise EffectV3Error('V5 renewal regresses acknowledged fence/policy or cumulative budget')
            now = self._scope_current(successor_scope, self._now())
            if self._policy.assert_renewal_allowed(old, successor_scope, now) is not None:
                raise EffectV3Error('current host governance denied or did not decide V5 renewal')
            current = self._scope_current(successor_scope, self._now())
            if current < now:
                raise EffectV3Error('clock moved backwards during V5 renewal decision')
            fence, update = self._fence_update(successor_scope, current)
            if (fence.authority_epoch <= old.fence.authority_epoch or
                    fence.fencing_token <= old.fence.fencing_token):
                raise EffectV3Error('successor fence is not strictly newer than acknowledged cutover')
            current = self._scope_current(successor_scope, self._now())
            if current < now or not fence.issued_at <= current < fence.expires_at:
                raise EffectV3Error('successor grant/fence expired during renewal signing')
            if self._policy.assert_renewal_allowed(old, successor_scope, current) is not None:
                raise EffectV3Error('current host governance changed during V5 renewal signing')
            if old.ordinal >= (1 << 63) - 1:
                raise ReconciliationRequiredV3('V5 generation ordinal exhausted PostgreSQL BIGINT capacity')
            ordinal = integer(old.ordinal + 1, positive=True)
            generation_id = self._insert_generation(
                cursor, successor_scope, ordinal, old.generation_id, fence, update,
            )
            cursor.execute(f'''UPDATE {HEADS5} SET current_generation=%s,budget_limit=%s
                WHERE scope_id=%s AND current_generation=%s AND budget_reserved=0 AND budget_spent=%s''', (
                generation_id, successor_scope.budget_limit, successor_scope.scope_id,
                old.generation_id, head[4],
            ))
            if getattr(cursor, 'rowcount', None) != 1:
                raise ReconciliationRequiredV3('V5 head changed before cumulative renewal commit')
        return update

