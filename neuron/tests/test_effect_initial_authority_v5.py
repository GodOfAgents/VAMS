"""Atomic writer/caller fixtures. No PostgreSQL, custody or native funding proof."""
from contextlib import contextmanager
from dataclasses import replace
import copy
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import ec
from neuron.tests import test_effect_attempt_journal_v5 as F
from neuron import effect_initial_authority_v5 as A
from neuron.effect_authority_v3 import CurrentAuthorityPolicyV1
from neuron.effect_attempt_journal_v5 import PostgresAttemptJournalV5
from neuron.effect_protocol_v3 import ObjectFenceV3,EffectV3Error,sign_receipt,fence_ack_subject
from neuron.signed_receipts import ReceiptSignerV3
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3


class FixturePolicy(CurrentAuthorityPolicyV1):
    # Local callback doubles, not an authenticated current native host backend.
    def __init__(self):self.calls=0;self.deny_at=None
    def check(self):
        self.calls+=1
        if self.calls==self.deny_at:raise EffectV3Error('fixture current policy denied')
    def assert_allowed(self,proposal,now):return self.check()
    def assert_scope_allowed(self,scope,now):return self.check()
    def assert_fence_allowed(self,scope,fence,now):raise AssertionError('not used')


class WriterCursor(F.JournalCursor):
    def execute(self,query,params=()):
        if query.startswith(f'SELECT COUNT(*) FROM {A.ATTEMPTS5}'):
            override=getattr(self.rows,'override_generation_count',None)
            count=override if override is not None else sum(
                r[5]==params[0] and r[6]==params[1] for r in self.rows.attempts.values())
            self.result=(count,);return
        if f'SELECT attempt_id FROM {A.ATTEMPTS5} WHERE operation_id=%s' in query:
            rows=sorted((r for r in self.rows.attempts.values() if r[1]==params[0]),key=lambda r:r[2],reverse=True)
            self.result=[(r[0],) for r in rows[:2]];return
        if query.startswith(f'INSERT INTO {A.WORK5}'):
            op,*row=params
            if op in self.rows.work:raise EffectV3Error('fixture unique work')
            self.rows.work[op]=tuple(row);self.rowcount=1;return
        if query.startswith(f'INSERT INTO {A.ATTEMPTS5}'):
            if params[0] in self.rows.attempts:raise EffectV3Error('fixture unique attempt')
            self.rows.attempts[params[0]]=tuple(params);self.rowcount=1;return
        if query.startswith(f'UPDATE {A.HEADS5} SET budget_reserved=budget_reserved+%s'):
            cost,scope,generation,required=params;head=self.rows.heads[scope]
            if head[0]!=generation or head[3]>head[2]-head[4]-required:self.rowcount=0;return
            self.rows.heads[scope]=(head[0],head[1],head[2],head[3]+cost,head[4])
            self.rows.head_update_count+=1;self.rowcount=1;return
        return super().execute(query,params)


class InitialAuthorityV5Test(unittest.TestCase):
    def setUp(self):
        self.f=F.AttemptJournalV5Test('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.rows=F.MemoryRows();self.f._seed_attempt()
        self.f.rows.attempts.clear();self.f.rows.work.clear();self.f.rows.events.clear()
        self.f.now=self.f.proposal.context.issued_at+1
        self.signer=ReceiptSignerV3(ec.derive_private_key(1,ec.SECP256K1()))
        provider=ReceiptSignerV3(ec.derive_private_key(2,ec.SECP256K1()))
        fence=ObjectFenceV3.from_context(self.f.scope.template,self.f.scope.fencing_token)
        def sign(signer,purpose,subject):
            return sign_receipt(signer,purpose=purpose,subject=subject,provider=fence.provider_id,
                epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
                issued_at=fence.issued_at,expires_at=fence.expires_at)
        update=sign(self.signer,2,fence.digest)
        ack=sign(provider,3,fence_ack_subject(fence,update))
        self.f.rows.generations[(self.f.scope.scope_id,self.f.generation_id)]=(
            self.f.scope.canonical_bytes(),'active',fence.canonical_bytes(),update.canonical_bytes(),
            ack.canonical_bytes(),self.f.generation_id,1,None,None,None)
        h=self.f.rows.heads[self.f.scope.scope_id]
        self.f.rows.heads[self.f.scope.scope_id]=h[:3]+(0,0)
        self.policy=FixturePolicy()
        self.writer=A.PostgresInitialAttemptAuthorityV5(self.f.database,self.f.identity,self.signer,self.policy,
            native_config_hash=self.f.native_config_hash,runtime_role='fixture_runtime',
            migration_role='fixture_owner',check_manifest=self.f.check_manifest,clock=lambda:self.f.now)

    def transaction(self,*,fail_event=False,ambiguous_close=False):
        f=self.f
        @contextmanager
        def transaction(database):
            before=copy.deepcopy(vars(f.rows))
            cursor=WriterCursor(f.rows)
            execute=cursor.execute
            def guarded(query,params=()):
                if fail_event and query.startswith(f'INSERT INTO {A.EVENT_INSERT.split("INSERT INTO ")[1].split("(")[0]}'):
                    raise EffectV3Error('fixture write failure')
                return execute(query,params)
            cursor.execute=guarded
            try:yield cursor
            except BaseException:
                vars(f.rows).clear();vars(f.rows).update(before);raise
            if ambiguous_close:raise EffectV3Error('fixture UNKNOWN after committed close')
        return patch.object(PostgresEffectDatabaseV3,'transaction',transaction)

    def reserve(self):return self.writer.reserve_initial_attempt(self.f.proposal,self.f.native_row)

    def test_initial_reservation_and_signed_credential_share_one_transaction(self):
        with self.transaction():
            attempt=self.reserve()
            read=self.writer.read_attempt(attempt.attempt_id)
        self.assertEqual(read.outcome,'pending');self.assertFalse(read.native_verified)
        self.assertEqual(read.attempt,attempt)
        self.assertEqual(self.f.rows.heads[self.f.scope.scope_id][3:],(self.f.proposal.cost_units,0))
        self.assertEqual(self.f.rows.event_insert_count,1)

    def test_untyped_identity_or_provider_signer_cannot_issue_initial_authority(self):
        kw=dict(native_config_hash=self.f.native_config_hash,runtime_role='fixture_runtime',
            migration_role='fixture_owner',check_manifest=self.f.check_manifest)
        with self.assertRaises(EffectV3Error):
            A.PostgresInitialAttemptAuthorityV5(self.f.database,object(),self.signer,self.policy,**kw)
        provider=ReceiptSignerV3(ec.derive_private_key(2,ec.SECP256K1()))
        with self.assertRaises(EffectV3Error):
            A.PostgresInitialAttemptAuthorityV5(self.f.database,self.f.identity,provider,self.policy,**kw)

    def test_identical_initial_lookup_returns_retained_signature_and_never_reserves_twice(self):
        with self.transaction():
            first=self.reserve()
            with patch.object(A,'sign_receipt',side_effect=AssertionError('must not sign again')):
                second=self.reserve()
        self.assertEqual(first,second)
        self.assertEqual(self.f.rows.head_update_count,1)

    def test_generation_capacity_rejects_before_signing_or_unclosable_reservation(self):
        # Bounded generation audit must still cover zero-cost work; a token/cost
        # ceiling alone cannot bound how many distinct attempts exist.
        self.f.rows.override_generation_count=256
        with self.transaction(),self.assertRaises(EffectV3Error):self.reserve()
        self.assertFalse(self.f.rows.attempts)
        self.assertEqual(self.f.rows.head_update_count,0)

    def test_last_supported_generation_slot_still_reserves(self):
        self.f.rows.override_generation_count=255
        with self.transaction():attempt=self.reserve()
        self.assertIn(attempt.attempt_id,self.f.rows.attempts)

    def test_zero_cost_work_still_consumes_bounded_generation_capacity(self):
        self.f.rows.override_generation_count=256
        proposal=replace(self.f.proposal,cost_units=0)
        proposal=replace(proposal,context=replace(proposal.context,action_hash=proposal.action_hash))
        proposal.validate()
        with self.transaction(),self.assertRaises(EffectV3Error):
            self.writer.reserve_initial_attempt(proposal,self.f.native_row)
        self.assertFalse(self.f.rows.attempts)

    def test_malformed_generation_count_fails_before_signing(self):
        for count in (True,-1,'256',257):
            self.f.rows.override_generation_count=count
            with self.subTest(count=count),self.transaction(),self.assertRaises(EffectV3Error):self.reserve()
            self.assertFalse(self.f.rows.attempts)

    def test_partial_insert_failure_rolls_back_and_returns_no_admission(self):
        with self.transaction(fail_event=True),self.assertRaises(EffectV3Error):self.reserve()
        self.assertFalse(self.f.rows.work);self.assertFalse(self.f.rows.attempts)
        self.assertEqual(self.f.rows.heads[self.f.scope.scope_id][3:],(0,0))

    def test_commit_close_ambiguity_does_not_retry_or_return_a_credential(self):
        with self.transaction(ambiguous_close=True),self.assertRaises(EffectV3Error):self.reserve()
        self.assertEqual(len(self.f.rows.attempts),1)
        self.assertEqual(self.f.rows.head_update_count,1)
        # A future recovery must query this exact identity; there is no second
        # invocation, new nonce or external transaction in this fixture.

    def test_policy_denial_or_unknown_prevents_signature_release_and_writes(self):
        for call in (1,2,3,4,5,6):
            with self.subTest(call=call):
                self.policy.calls=0;self.policy.deny_at=call
                with self.transaction(),self.assertRaises(EffectV3Error):self.reserve()
                self.assertFalse(self.f.rows.attempts)
                self.assertEqual(self.f.rows.head_update_count,0)

    def test_missing_ack_or_exhausted_budget_prevents_admission(self):
        key=(self.f.scope.scope_id,self.f.generation_id);g=self.f.rows.generations[key]
        self.f.rows.generations[key]=g[:4]+(None,)+g[5:]
        with self.transaction(),self.assertRaises(EffectV3Error):self.reserve()
        self.f.rows.generations[key]=g
        h=self.f.rows.heads[self.f.scope.scope_id]
        self.f.rows.heads[self.f.scope.scope_id]=h[:3]+(0,h[2])
        with self.transaction(),self.assertRaises(EffectV3Error):self.reserve()
        self.assertFalse(self.f.rows.attempts)

    def test_unknown_funding_is_lookup_only_and_cannot_reissue(self):
        with self.transaction():
            attempt=self.reserve();self.writer.mark_funding_unknown(attempt.attempt_id)
            with self.assertRaises(EffectV3Error):self.reserve()
        self.assertEqual(self.f.rows.head_update_count,1)

    def test_signed_completion_after_unknown_funding_is_permanent_and_does_not_pay(self):
        # Build a genuine fixture completion for this exact returned admission;
        # the retained other fixture signature must not be substituted.
        from neuron.effect_protocol_v3 import effect_subject
        with self.transaction():
            attempt=self.reserve();self.writer.mark_funding_unknown(attempt.attempt_id)
            c=attempt.proposal.context;committed=self.f.now
            provider=ReceiptSignerV3(ec.derive_private_key(2,ec.SECP256K1()))
            receipt=sign_receipt(provider,purpose=4,subject=effect_subject(attempt.proposal,attempt.admission,committed),
                provider=c.provider_id,epoch=c.authority_epoch,policy=c.policy_version,
                fence=attempt.proposal.fencing_token,issued_at=committed,expires_at=c.expires_at)
            self.f.now=c.expires_at+100
            result=self.writer.accept_effect(attempt.attempt_id,receipt)
            again=self.writer.accept_effect(attempt.attempt_id,receipt)
            self.assertEqual(result,again)
        self.assertEqual(result.outcome,'completed');self.assertFalse(result.native_verified)
        self.assertEqual(self.f.rows.heads[self.f.scope.scope_id][3:],(0,attempt.proposal.cost_units))
        self.assertEqual(self.f.rows.completion_insert_count,1)

    def test_wrong_host_or_changed_native_row_cannot_rebind_existing_work(self):
        with self.transaction():
            self.reserve()
            with self.assertRaises(EffectV3Error):
                self.writer.reserve_initial_attempt(self.f.proposal,replace(self.f.native_row,provider_index=1))
            with self.assertRaises(EffectV3Error):
                self.writer.reserve_initial_attempt(self.f.proposal,replace(self.f.native_row,chain_id=123))
        self.assertEqual(self.f.rows.head_update_count,1)


if __name__=='__main__':unittest.main()
