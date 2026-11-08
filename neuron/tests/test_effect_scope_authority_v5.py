"""Controlled-double lifecycle tests; not PostgreSQL/native qualification."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import ec

from neuron import effect_authority_store_v5 as S
from neuron import effect_attempt_journal_v5 as J
from neuron import effect_initial_authority_v5 as I
from neuron import effect_scope_authority_v5 as L
from neuron.effect_attempt_events_v5 import AttemptEventV5, reserved_payload
from neuron.effect_attempts_v5 import NativeObjectRowV1
from neuron.effect_authority_v3 import ObjectAuthorityScopeV3, ReconciliationRequiredV3
from neuron.effect_protocol_v3 import (
    EffectV3Error, ObjectEffectV3, ObjectFenceV3, SignedEffectReceiptV3,
    absence_subject, effect_subject, fence_ack_subject, sign_receipt,
)
from neuron.effect_provider_v3 import ObjectProviderIdentityV3
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.runtime_safety import RuntimeConfigurationError
from neuron.signed_receipts import ReceiptSignerV3, ReceiptVerifierV3

# Import fixture behavior as a module namespace. Imported TestCase classes are
# never re-exported into this module or collected a second time.
from neuron.tests import test_effect_initial_authority_v5 as InitialHelpers


def h(value):
    return hashlib.sha256(value).digest()


def fixture_data():
    path = Path(__file__).with_name('effect_attempt_v5_fixture.json')
    return json.loads(path.read_text(encoding='utf8'))


def synthetic_checks():
    definitions = tuple(sorted(
        (table, 'CHECK (1 = ' + str(index + 1) + ')')
        for table, count in S._CHECK_COUNTS5.items()
        for index in range(count)
    ))
    return S.ExpectedChecksV5(S.MIGRATION5, h(b'SYNTHETIC-COMPILER-NOT-QUALIFIED'),
        h(b'SYNTHETIC-PROVENANCE-NOT-QUALIFIED'), 180000, definitions)


class FixtureRenewalPolicy(L.CurrentRenewalPolicyV1):
    """Fixture callback contract only; not authenticated host policy."""
    def __init__(self):
        self.denials = set()
        self.calls = []

    def _decision(self, name):
        self.calls.append(name)
        return False if name in self.denials else None

    def assert_allowed(self, proposal, now):
        return self._decision('action')

    def assert_scope_allowed(self, scope, now):
        return self._decision('scope')

    def assert_fence_allowed(self, scope, fence, now):
        return self._decision('fence')

    def assert_renewal_allowed(self, previous, successor, now):
        # Existing policy contract receives the complete previous authority
        # state, including cumulative spend and the retained acknowledged fence.
        if previous.ack is None or previous.reserved!=0 or previous.spent<0:
            raise AssertionError('renewal lost previous authority/budget facts')
        self.previous_renewal_state=previous
        return self._decision('renewal')


class LifecycleRows:
    def __init__(self):
        self.attempts = {}
        self.work = {}
        self.generations = {}
        self.heads = {}
        self.events = {}
        self.completions = {}
        self.event_insert_count = 0
        self.completion_insert_count = 0
        self.head_update_count = 0


class LifecycleCursor(InitialHelpers.WriterCursor):
    def execute(self, query, params=()):
        self.result = None
        self.rowcount = -1
        if f'FROM {L.HEADS5} WHERE scope_id=%s' in query and 'SELECT scope_id' in query:
            self.result = None if params[0] not in self.rows.heads else (params[0],)
            return
        if f'FROM {L.GENERATIONS5} WHERE scope_id=%s LIMIT 1' in query:
            matches = [key[1] for key in self.rows.generations if key[0] == params[0]]
            self.result = None if not matches else (matches[0],)
            return
        if f'FROM {L.GENERATIONS5} WHERE scope_id=%s AND generation_id=%s' in query:
            self.result = self.rows.generations.get((params[0], params[1]))
            return
        if f'FROM {L.ATTEMPTS5}' in query and 'ORDER BY operation_id,attempt_id' in query:
            scope_id, generation_id, limit = params
            self.result = sorted((row[1], row[0]) for row in self.rows.attempts.values()
                if row[5] == scope_id and row[6] == generation_id)[:limit]
            return
        if query.startswith(f'INSERT INTO {L.GENERATIONS5}'):
            (generation_id, scope_id, ordinal, predecessor, scope_bytes,
             fence_bytes, update_bytes) = params
            key = (scope_id, generation_id)
            if key in self.rows.generations:
                raise EffectV3Error('fixture generation uniqueness conflict')
            self.rows.generations[key] = (scope_bytes, 'installing', fence_bytes,
                update_bytes, None, generation_id, ordinal, predecessor, None, None)
            self.rowcount = 1
            return
        if query.startswith(f'INSERT INTO {L.HEADS5}'):
            scope_id, generation_id, unit, limit = params
            if scope_id in self.rows.heads:
                raise EffectV3Error('fixture head uniqueness conflict')
            self.rows.heads[scope_id] = (generation_id, unit, limit, 0, 0)
            self.rowcount = 1
            return
        if query.startswith(f'UPDATE {L.GENERATIONS5} SET status=\'active\''):
            ack, scope_id, generation_id = params
            key = (scope_id, generation_id); row = self.rows.generations[key]
            if row[1] != 'installing' or row[4] is not None:
                self.rowcount = 0; return
            self.rows.generations[key] = (row[0], 'active', row[2], row[3], ack, *row[5:])
            self.rowcount = 1
            return
        if query.startswith(f'UPDATE {L.GENERATIONS5} SET status=\'draining\''):
            fence, update, scope_id, generation_id = params
            key=(scope_id,generation_id);row=self.rows.generations[key]
            self.rows.generations[key]=(row[0],'draining',fence,update,None,*row[5:])
            self.rowcount=1;return
        if query.startswith(f'UPDATE {L.GENERATIONS5} SET fence_bytes=%s,update_bytes=%s'):
            fence, update, scope_id, generation_id = params
            key=(scope_id,generation_id);row=self.rows.generations[key]
            self.rows.generations[key]=(row[0],row[1],fence,update,row[4],*row[5:])
            self.rowcount=1;return
        if query.startswith(f'UPDATE {L.GENERATIONS5} SET ack_bytes=%s'):
            ack, scope_id, generation_id, fence, update = params
            key=(scope_id,generation_id);row=self.rows.generations[key]
            if row[1]!='draining' or row[4] is not None or row[2]!=fence or row[3]!=update:
                self.rowcount=0;return
            self.rows.generations[key]=(row[0],row[1],row[2],row[3],ack,*row[5:])
            self.rowcount=1;return
        if query.startswith(f'UPDATE {L.GENERATIONS5} SET status=\'revoked\''):
            spent, scope_id, generation_id, ack = params
            key=(scope_id,generation_id);row=self.rows.generations[key]
            if row[4]!=ack or row[8] is not None or row[9] is not None:
                self.rowcount=0;return
            self.rows.generations[key]=(row[0],'revoked',row[2],row[3],row[4],
                *row[5:8],0,spent)
            self.rowcount=1;return
        if query.startswith(f'UPDATE {L.HEADS5} SET current_generation=%s'):
            generation_id, limit, scope_id, old_generation, spent = params
            head=self.rows.heads[scope_id]
            if head[0]!=old_generation or head[3]!=0 or head[4]!=spent:
                self.rowcount=0;return
            self.rows.heads[scope_id]=(generation_id,head[1],limit,head[3],head[4])
            self.rowcount=1;return
        return super().execute(query, params)


class ScopeAuthorityV5Test(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'VAMS_ENV':'test'}, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)
        connection_guard=patch.object(S.PostgresAuthorityDatabaseV5,'_connect',
            side_effect=AssertionError('controlled lifecycle tests must not connect'))
        connection_guard.start();self.addCleanup(connection_guard.stop)
        vector = fixture_data()
        self.proposal = ObjectEffectV3.from_bytes(bytes.fromhex(vector['proposal']))
        context = self.proposal.context
        self.scope = ObjectAuthorityScopeV3(context, (self.proposal.resource_id,),
            context.budget, self.proposal.cost_units, self.proposal.fencing_token)
        self.identity = ObjectProviderIdentityV3(
            context.provider_id, context.host_domain, context.runtime_id, context.target,
            context.chain_id, ReceiptVerifierV3(bytes.fromhex(vector['authority_public_verifier']['sec1_uncompressed_hex'])),
            ReceiptVerifierV3(bytes.fromhex(vector['provider_public_verifier']['sec1_uncompressed_hex'])),
        )
        self.signer = ReceiptSignerV3(ec.derive_private_key(1, ec.SECP256K1()))
        self.provider = ReceiptSignerV3(ec.derive_private_key(2, ec.SECP256K1()))
        self.check_manifest = synthetic_checks()
        self.native_hash = h(b'SYNTHETIC-NATIVE-CONFIG-NOT-QUALIFIED')
        config = S.authority_configuration_v5(self.identity, self.native_hash,
            'fixture_runtime','fixture_owner',self.check_manifest)
        self.database = S.PostgresAuthorityDatabaseV5('postgresql://fixture.invalid/vams', config,
            runtime_role='fixture_runtime',migration_role='fixture_owner',check_manifest=self.check_manifest)
        self.rows = LifecycleRows()
        self.now = context.issued_at + 1
        self.policy = FixtureRenewalPolicy()
        self.authority = L.PostgresScopeAuthorityV5(self.database,self.identity,self.signer,self.policy,
            native_config_hash=self.native_hash,runtime_role='fixture_runtime',
            migration_role='fixture_owner',check_manifest=self.check_manifest,clock=lambda:self.now)

    def transaction(self):
        rows=self.rows
        @contextmanager
        def fake_transaction(_database):
            import copy
            before=copy.deepcopy(vars(rows))
            try:
                yield LifecycleCursor(rows)
            except BaseException:
                vars(rows).clear();vars(rows).update(before)
                raise
        return patch.object(PostgresEffectDatabaseV3,'transaction',fake_transaction)

    def _sign(self, signer, purpose, subject, fence, *, issued_at=None):
        at = fence.issued_at if issued_at is None else issued_at
        return sign_receipt(signer,purpose=purpose,subject=subject,provider=fence.provider_id,
            epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
            issued_at=at,expires_at=fence.expires_at)

    def _ack(self, fence, update):
        return self._sign(self.provider,3,fence_ack_subject(fence,update),fence,
            issued_at=max(fence.issued_at,self.now))

    def _cutover(self, base, *, epoch=None, policy=None, root=None, fencing=None,
            issued=None, expires=None):
        return replace(base,
            authority_epoch=base.authority_epoch+1 if epoch is None else epoch,
            policy_version=base.policy_version if policy is None else policy,
            policy_root=base.policy_root if root is None else root,
            fencing_token=base.fencing_token+1 if fencing is None else fencing,
            issued_at=self.now if issued is None else issued,
            expires_at=base.expires_at if expires is None else expires)

    def _activate_fresh_scope(self):
        with self.transaction():
            update=self.authority.prepare_scope(self.scope)
            installing=self.authority.read_scope(self.scope.scope_id)
        self.assertEqual(installing.status,'installing')
        self.assertEqual(installing.reserved,0);self.assertEqual(installing.spent,0)
        ack=self._ack(installing.fence,update)
        with self.transaction():
            active=self.authority.activate_scope(self.scope.scope_id,ack)
        self.assertEqual(active.status,'active')
        return active

    def _reserve(self, proposal=None, allocation=None):
        proposal=proposal or self.proposal
        row=NativeObjectRowV1(proposal.context.chain_id,proposal.context.target,
            allocation or h(b'allocation-'+proposal.resource_id),0)
        with self.transaction():
            return self.authority.reserve_initial_attempt(proposal,row)

    def _completion_receipt(self, attempt, fence):
        committed=self.now
        return sign_receipt(self.provider,purpose=4,
            subject=effect_subject(attempt.proposal,attempt.admission,committed),
            provider=fence.provider_id,epoch=attempt.proposal.context.authority_epoch,
            policy=attempt.proposal.context.policy_version,fence=attempt.proposal.fencing_token,
            issued_at=committed,expires_at=attempt.proposal.context.expires_at)

    def _cutover_and_ack(self, state, fence=None):
        new_fence=fence or self._cutover(state.fence)
        with self.transaction():
            update=self.authority.begin_revocation(state.scope.scope_id,new_fence)
        ack=self._ack(new_fence,update)
        with self.transaction():
            result=self.authority.record_fence_ack(state.scope.scope_id,new_fence,update,ack)
        return new_fence,update,ack,result

    def _successor_scope(self, old, *, epoch=None, policy=None, root=None,
            fencing=None, budget_limit=None, resources=None):
        c=replace(old.scope.template,
            authority_epoch=old.fence.authority_epoch+1 if epoch is None else epoch,
            policy_version=old.fence.policy_version if policy is None else policy,
            policy_root=old.fence.policy_root if root is None else root,
            issued_at=self.now,
            expires_at=max(old.scope.template.expires_at,self.now+100))
        selected_resources=old.scope.resources if resources is None else tuple(sorted(resources))
        return ObjectAuthorityScopeV3(c,selected_resources,
            old.scope.budget_limit if budget_limit is None else budget_limit,
            old.scope.max_action_cost,
            old.fence.fencing_token+1 if fencing is None else fencing)

    def test_install_ack_activate_then_initial_reservation_only_after_activation(self):
        with self.transaction():
            update=self.authority.prepare_scope(self.scope)
            state=self.authority.read_scope(self.scope.scope_id)
            with self.assertRaises(EffectV3Error):
                self.authority.reserve_initial_attempt(self.proposal,
                    NativeObjectRowV1(self.proposal.context.chain_id,self.proposal.context.target,h(b'premature'),0))
        self.assertEqual(state.status,'installing')
        self.assertFalse(self.rows.attempts)
        ack=self._ack(state.fence,update)
        with self.transaction():active=self.authority.activate_scope(self.scope.scope_id,ack)
        attempt=self._reserve()
        self.assertEqual(active.status,'active')
        self.assertEqual(self.rows.heads[self.scope.scope_id][3],attempt.proposal.cost_units)

    def test_fresh_scope_rejects_forged_or_wrong_ack_and_never_adopts_rows(self):
        with self.transaction(): update=self.authority.prepare_scope(self.scope)
        with self.transaction():state=self.authority.read_scope(self.scope.scope_id)
        bad=replace(self._ack(state.fence,update),signature=b'\0'*64)
        with self.transaction(),self.assertRaises(ValueError):
            self.authority.activate_scope(self.scope.scope_id,bad)
        self.assertEqual(self.rows.generations[(self.scope.scope_id,state.generation_id)][1],'installing')
        with self.transaction(),self.assertRaises(ReconciliationRequiredV3):
            self.authority.prepare_scope(self.scope)

    def test_expired_old_scope_can_cut_over_but_expired_new_fence_cannot(self):
        state=self._activate_fresh_scope()
        self.now=state.scope.template.expires_at+10
        # Host policy still decides the cutover; the old grant need not be current.
        fence=self._cutover(state.fence,issued=self.now,expires=self.now+100)
        with self.transaction():update=self.authority.begin_revocation(state.scope.scope_id,fence)
        self.assertIn('fence',self.policy.calls)
        expired=replace(fence,authority_epoch=fence.authority_epoch+1,
            fencing_token=fence.fencing_token+1,issued_at=self.now-10,expires_at=self.now-1)
        with self.transaction(),self.assertRaises(EffectV3Error):
            self.authority.refresh_unacknowledged_cutover(state.scope.scope_id,expired)

    def test_equal_epoch_or_fence_policy_rollback_and_root_rebind_are_rejected(self):
        state=self._activate_fresh_scope()
        bads=(
            self._cutover(state.fence,epoch=state.fence.authority_epoch,
                fencing=state.fence.fencing_token+1),
            self._cutover(state.fence,epoch=state.fence.authority_epoch+1,
                fencing=state.fence.fencing_token),
            self._cutover(state.fence,policy=state.fence.policy_version-1),
            self._cutover(state.fence,root=h(b'rebound-root')),
        )
        for fence in bads:
            with self.subTest(fence=fence),self.transaction(),self.assertRaises(EffectV3Error):
                self.authority.begin_revocation(state.scope.scope_id,fence)

    def test_refresh_is_strict_and_stale_ack_cannot_overwrite_current_update(self):
        state=self._activate_fresh_scope()
        first=self._cutover(state.fence)
        with self.transaction():old_update=self.authority.begin_revocation(state.scope.scope_id,first)
        second=self._cutover(first,epoch=first.authority_epoch+1,fencing=first.fencing_token+1)
        with self.transaction():new_update=self.authority.refresh_unacknowledged_cutover(state.scope.scope_id,second)
        stale_ack=self._ack(first,old_update)
        with self.transaction(),self.assertRaises(EffectV3Error):
            self.authority.record_fence_ack(state.scope.scope_id,first,old_update,stale_ack)
        exact_ack=self._ack(second,new_update)
        with self.transaction():self.authority.record_fence_ack(state.scope.scope_id,second,new_update,exact_ack)
        with self.transaction(),self.assertRaises(ReconciliationRequiredV3):
            self.authority.refresh_unacknowledged_cutover(state.scope.scope_id,
                self._cutover(second,epoch=second.authority_epoch+1,fencing=second.fencing_token+1))

    def test_pending_zero_cost_attempt_and_corrupt_terminal_both_block_closure(self):
        # Use a second in-scope resource and a fresh operation ID with zero cost.
        resource=h(b'zero-cost-resource')
        resources=tuple(sorted((self.proposal.resource_id,resource)))
        self.scope=ObjectAuthorityScopeV3(self.scope.template,resources,self.scope.budget_limit,
            self.scope.max_action_cost,self.scope.fencing_token)
        active=self._activate_fresh_scope()
        zero=self._zero_cost_proposal(resource)
        attempt=self._reserve(zero,h(b'zero-cost-allocation'))
        fence,update,ack,_=self._cutover_and_ack(active)
        with self.transaction(),self.assertRaises(ReconciliationRequiredV3):
            self.authority.complete_revocation(self.scope.scope_id)
        self.assertEqual(self.rows.generations[(self.scope.scope_id,active.generation_id)][1],'draining')
        # Resolve with authentic absence, then corrupt a retained terminal digest.
        absence=self._absence(attempt,fence,update,ack)
        with self.transaction():self.authority.accept_absence(attempt.attempt_id,absence)
        completion=self.rows.events[attempt.attempt_id][-1]
        self.rows.events[attempt.attempt_id][-1]=completion[:5]+(h(b'corrupt-event'),)
        with self.transaction(),self.assertRaises(EffectV3Error):
            self.authority.complete_revocation(self.scope.scope_id)

    def _zero_cost_proposal(self, resource):
        c=self.scope.template
        draft=ObjectEffectV3(c,resource,0,self.scope.fencing_token)
        context=replace(c,action_hash=draft.action_hash,nonce=h(b'zero-cost-nonce'))
        return ObjectEffectV3(context,resource,0,self.scope.fencing_token)

    def _absence(self, attempt, fence, update, ack):
        receipt=self._sign(self.provider,5,absence_subject(attempt.proposal,ack),fence,
            issued_at=max(self.now,ack.receipt.issued_at))
        from neuron.effect_attempt_payloads_v5 import FencedAbsencePayloadV5
        return FencedAbsencePayloadV5(fence,update,ack,receipt)

    def test_terminal_completion_and_absence_close_and_renew_without_budget_reset(self):
        active=self._activate_fresh_scope()
        attempt=self._reserve()
        receipt=self._completion_receipt(attempt,active.fence)
        with self.transaction():completed=self.authority.accept_effect(attempt.attempt_id,receipt)
        fence,update,ack,_=self._cutover_and_ack(active)
        with self.transaction():closed=self.authority.complete_revocation(self.scope.scope_id)
        self.assertEqual(closed.status,'revoked')
        self.assertEqual(closed.reserved,0)
        self.assertEqual(closed.spent,attempt.proposal.cost_units)
        new_resource=h(b'new-work-after-renewal')
        successor=self._successor_scope(closed,budget_limit=closed.spent+attempt.proposal.cost_units,
            resources=(closed.scope.resources[0],new_resource))
        with self.transaction():new_update=self.authority.prepare_renewal(successor)
        with self.transaction():renewed=self.authority.read_scope(successor.scope_id)
        self.assertEqual(self.policy.previous_renewal_state.spent,closed.spent)
        self.assertEqual(self.policy.previous_renewal_state.ack,closed.ack)
        self.assertEqual(renewed.status,'installing')
        self.assertEqual(renewed.spent,closed.spent)
        new_ack=self._ack(renewed.fence,new_update)
        with self.transaction():active_new=self.authority.activate_scope(successor.scope_id,new_ack)
        self.assertEqual(active_new.spent,completed.attempt.proposal.cost_units)
        draft=ObjectEffectV3(successor.template,new_resource,attempt.proposal.cost_units,
            successor.fencing_token)
        new_context=replace(successor.template,action_hash=draft.action_hash,
            nonce=h(b'renewed-work-nonce'),budget=successor.budget_limit)
        new_proposal=ObjectEffectV3(new_context,new_resource,attempt.proposal.cost_units,
            successor.fencing_token)
        new_attempt=self._reserve(new_proposal,h(b'renewed-work-allocation'))
        self.assertNotEqual(new_attempt.proposal.operation_id,attempt.proposal.operation_id)
        self.assertEqual(self.rows.heads[successor.scope_id][3:],
            (new_attempt.proposal.cost_units,completed.attempt.proposal.cost_units))

    def test_absence_closure_requires_ack_and_authenticated_exact_terminal(self):
        active=self._activate_fresh_scope();attempt=self._reserve()
        with self.transaction():update=self.authority.begin_revocation(active.scope.scope_id,self._cutover(active.fence))
        with self.transaction(),self.assertRaises(ReconciliationRequiredV3):
            self.authority.complete_revocation(active.scope.scope_id)
        with self.transaction():state=self.authority.read_scope(active.scope.scope_id)
        wrong=self._ack(state.fence,update)
        bad=replace(wrong,signature=b'\0'*64)
        with self.transaction(),self.assertRaises(ValueError):
            self.authority.record_fence_ack(active.scope.scope_id,state.fence,update,bad)
        with self.transaction():self.authority.record_fence_ack(active.scope.scope_id,state.fence,update,wrong)
        payload=self._absence(attempt,state.fence,update,wrong)
        with self.transaction():self.authority.accept_absence(attempt.attempt_id,payload)
        with self.transaction():closed=self.authority.complete_revocation(active.scope.scope_id)
        self.assertEqual(closed.spent,0);self.assertEqual(closed.reserved,0)

    def test_renewal_denial_policy_regression_and_budget_below_spend_reject(self):
        active=self._activate_fresh_scope();attempt=self._reserve()
        receipt=self._completion_receipt(attempt,active.fence)
        with self.transaction():self.authority.accept_effect(attempt.attempt_id,receipt)
        self._cutover_and_ack(active)
        with self.transaction():closed=self.authority.complete_revocation(self.scope.scope_id)
        denied=self._successor_scope(closed)
        self.policy.denials.add('renewal')
        with self.transaction(),self.assertRaises(EffectV3Error):self.authority.prepare_renewal(denied)
        self.policy.denials.clear()
        bads=(
            self._successor_scope(closed,epoch=closed.fence.authority_epoch),
            self._successor_scope(closed,fencing=closed.fence.fencing_token),
            self._successor_scope(closed,policy=closed.fence.policy_version-1),
            self._successor_scope(closed,root=h(b'changed-without-version'),policy=closed.fence.policy_version),
            self._successor_scope(closed,budget_limit=closed.spent-1),
        )
        for bad in bads:
            with self.subTest(scope=bad),self.transaction(),self.assertRaises(EffectV3Error):
                self.authority.prepare_renewal(bad)

    def test_wrong_scope_identity_and_live_mode_reject_before_storage_use(self):
        wrong=replace(self.scope,resources=(h(b'elsewhere'),))
        # Scope ID is shared by design; a conflicting row/grant must not be adopted.
        with self.transaction():self.authority.prepare_scope(self.scope)
        with self.transaction(),self.assertRaises(ReconciliationRequiredV3):self.authority.prepare_scope(wrong)
        with patch.object(J,'load_runtime_policy',return_value=type('Live',(),{'is_live':True})()), \
                self.assertRaises(RuntimeConfigurationError):
            L.PostgresScopeAuthorityV5(self.database,self.identity,self.signer,self.policy,
                native_config_hash=self.native_hash,runtime_role='fixture_runtime',
                migration_role='fixture_owner',check_manifest=self.check_manifest)

    def test_generation_attempt_audit_has_fixed_256_row_bound(self):
        active=self._activate_fresh_scope()
        for index in range(L.MAX_GENERATION_ATTEMPTS5+1):
            operation=h(b'bounded-operation-'+index.to_bytes(4,'big'))
            attempt=h(b'bounded-attempt-'+index.to_bytes(4,'big'))
            row=[attempt,operation,1,h(b'logical'),None,self.scope.scope_id,active.generation_id]
            self.rows.attempts[attempt]=tuple(row)
        with self.transaction(),self.assertRaises(ReconciliationRequiredV3):
            self.authority._attempt_rows(LifecycleCursor(self.rows),
                self.scope.scope_id,active.generation_id)


if __name__ == '__main__':
    unittest.main()
