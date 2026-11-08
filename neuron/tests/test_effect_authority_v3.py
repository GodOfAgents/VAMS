"""Real ECDSA fixture keys, queued driver calls; NOT native PG/host assurance."""
from dataclasses import replace
import json
from pathlib import Path
import os
import unittest
from unittest.mock import patch

from neuron.effect_authority_v3 import (
    ObjectAuthorityScopeV3,CurrentAuthorityPolicyV1,PostgresEffectAuthorityV3,
    ReconciliationRequiredV3,AuthorityStateV3,
)
from neuron.effect_authority_store_v3 import (
    PostgresAuthorityDatabaseV3,authority_configuration,AUTH_META,AUTH_MIGRATION_HASH,SCOPES,OPERATIONS,
)
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_provider_v3 import PostgresObjectProviderV3,ObjectProviderIdentityV3
from neuron.effect_coordinator_v3 import ObjectEffectCoordinatorV3,DirectObjectProviderTransportV3
from neuron.effect_protocol_v3 import (
    EffectV3Error,ObjectFenceV3,SignedEffectReceiptV3,sign_receipt,verify_admission,
    verify_effect,effect_subject,fence_ack_subject,absence_subject,
)
from neuron.runtime_safety import LiveModeSafetyError,RuntimeConfigurationError
from neuron.signed_receipts import ReceiptError
from neuron.tests.test_effect_protocol_v3 import fixture_proposal,fixture_signer,fixture_admission
from neuron.tests.test_effect_provider_v3 import ControlledConnection


class FixtureAuthorityPolicy(CurrentAuthorityPolicyV1):
    def __init__(self):self.calls=[];self.deny=None;self.result=None
    def check(self,name):
        self.calls.append(name)
        if self.deny==name:raise EffectV3Error('fixture policy DENY/UNKNOWN')
        return self.result
    def assert_allowed(self,proposal,now):return self.check('action')
    def assert_scope_allowed(self,scope,now):return self.check('scope')
    def assert_fence_allowed(self,scope,fence,now):return self.check('fence')


class AuthorityConnection(ControlledConnection):
    def __init__(self,identity,rows=(),**kwargs):
        super().__init__(identity,rows,**kwargs)
        self.rows[0]=(3,AUTH_MIGRATION_HASH,authority_configuration(identity))
        self.operation_inserts=[]
    def execute(self,sql,params=None):
        super().execute(sql,params)
        if sql.startswith('INSERT INTO '+OPERATIONS):self.operation_inserts.append(params)


class AuthorityFixture(unittest.TestCase):
    def setUp(self):
        environment={'VAMS_ENV':'test',**{n:os.environ[n] for n in ('SystemRoot','WINDIR') if n in os.environ}}
        self.environment=patch.dict(os.environ,environment,clear=True)
        self.environment.start();self.addCleanup(self.environment.stop)
        self.now=1050;self.proposal=fixture_proposal(budget=10)
        self.scope=ObjectAuthorityScopeV3(self.proposal.context,(b'r'*32,b's'*32),10,4,9)
        self.authority_signer,self.provider_signer=fixture_signer(),fixture_signer()
        c=self.proposal.context
        self.identity=ObjectProviderIdentityV3(c.provider_id,c.host_domain,c.runtime_id,c.target,c.chain_id,
            self.authority_signer.verifier(),self.provider_signer.verifier())
        self.database=PostgresAuthorityDatabaseV3('postgresql://synthetic-unused',authority_configuration(self.identity))
        self.policy=FixtureAuthorityPolicy()
        self.authority=PostgresEffectAuthorityV3(self.database,self.identity,self.authority_signer,self.policy,clock=lambda:self.now)
        self.fence=ObjectFenceV3.from_context(c,9)
        self.update,self.ack=self.evidence(self.fence)
        self.admission=fixture_admission(self.proposal,self.authority_signer)

    def evidence(self,fence):
        update=sign_receipt(self.authority_signer,purpose=2,subject=fence.digest,provider=fence.provider_id,
            epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
            issued_at=fence.issued_at,expires_at=fence.expires_at)
        ack=sign_receipt(self.provider_signer,purpose=3,subject=fence_ack_subject(fence,update),provider=fence.provider_id,
            epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
            issued_at=self.now,expires_at=fence.expires_at)
        return update,ack

    def state_row(self,*,status='active',reserved=3,spent=0,fence=None,update=None,ack='default'):
        fence=fence or self.fence;update=update or self.update
        ack=self.ack if ack=='default' else ack
        return (self.scope.canonical_bytes(),status,10,reserved,spent,fence.canonical_bytes(),update.canonical_bytes(),
            ack.canonical_bytes() if ack is not None else None)

    def operation_row(self,*,status='reserved',result=None,admission=None,proposal=None):
        proposal=proposal or self.proposal;admission=admission or self.admission
        return (proposal.canonical_bytes(),admission.canonical_bytes(),proposal.cost_units,status,
            result.canonical_bytes() if result is not None else None,self.scope.scope_id,proposal.digest)

    def connection(self,*rows,**kwargs):return AuthorityConnection(self.identity,rows,**kwargs)
    def names(self,connection):return [e[0] for e in connection.events]
    def mutations(self,connection):return [e for e in connection.events if e[0]=='execute' and e[1].startswith(('INSERT','UPDATE','DELETE','CREATE'))]
    def record(self,admission=None):
        admission=admission or self.admission;p=self.proposal
        return sign_receipt(self.provider_signer,purpose=4,subject=effect_subject(p,admission,1050),
            provider=p.context.provider_id,epoch=3,policy=7,fence=9,issued_at=1050,expires_at=1100)

    def cutover(self):
        fence=replace(self.fence,authority_epoch=4,policy_version=8,fencing_token=10)
        update,ack=self.evidence(fence)
        return fence,update,ack


class AuthorityV3Tests(AuthorityFixture):
    def test_scope_roundtrip_and_exact_resource_encoding(self):
        self.assertEqual(ObjectAuthorityScopeV3.from_bytes(self.scope.canonical_bytes()),self.scope)
        self.scope.permits(self.proposal,self.now)
        for raw in (self.scope.canonical_bytes()+b'\0',self.scope.canonical_bytes()[:-1],b'{}'):
            with self.assertRaises(EffectV3Error):ObjectAuthorityScopeV3.from_bytes(raw)

    def test_frozen_authority_scope_vector(self):
        vector=json.loads((Path(__file__).parents[2]/'docs/remediation/repair_20261030/authority-scope-v3.json').read_text())
        self.assertEqual(self.scope.canonical_bytes().hex(),vector['canonical_hex'])
        self.assertEqual(self.scope.scope_id.hex(),vector['scope_id'])

    def test_scope_rejects_duplicate_unsorted_unbounded_resources_and_budget_widening(self):
        for changes in ({'resources':()}, {'resources':(b'r'*32,b'r'*32)}, {'resources':(b's'*32,b'r'*32)},
                        {'resources':tuple(i.to_bytes(32,'big') for i in range(1,66))},
                        {'budget_limit':11},{'budget_limit':True},{'max_action_cost':11},{'fencing_token':0}):
            with self.subTest(changes=changes),self.assertRaises(EffectV3Error):replace(self.scope,**changes).validate()

    def test_scope_binds_workflow_intent_root_policy_resource_and_generation(self):
        for changes in ({'workflow_id':b'x'*32},{'intent_id':b'x'*32},{'actor_root':b'\0'*12+b'x'*20},
                        {'policy_root':b'x'*32},{'policy_version':8},{'authority_epoch':4},{'budget':11}):
            with self.assertRaises(EffectV3Error):self.scope.permits(fixture_proposal(**({'budget':10}|changes)))
        changed=replace(self.proposal,resource_id=b'X'*32)
        changed=replace(changed,context=replace(changed.context,action_hash=changed.action_hash))
        with self.assertRaises(EffectV3Error):self.scope.permits(changed)

    def test_authority_constructor_does_not_connect(self):
        with patch.object(self.database,'_connect',side_effect=AssertionError('constructor I/O')):
            PostgresEffectAuthorityV3(self.database,self.identity,self.authority_signer,self.policy)

    def test_provider_database_or_wrong_signer_cannot_be_authority(self):
        provider_database=PostgresEffectDatabaseV3('postgresql://synthetic-unused',self.identity.digest)
        for database,signer in ((provider_database,self.authority_signer),(self.database,self.provider_signer)):
            with self.assertRaises(EffectV3Error):PostgresEffectAuthorityV3(database,self.identity,signer,self.policy)

    def test_mutable_identity_and_runtime_drift_reject(self):
        with self.assertRaises(RuntimeConfigurationError):self.authority.identity=None
        with patch.dict(os.environ,{'VAMS_ENV':'production'},clear=True),patch.object(self.database,'_connect',side_effect=AssertionError('driver reached')):
            with self.assertRaises(LiveModeSafetyError):self.authority.reserve(self.proposal)

    def test_scope_policy_denial_precedes_database_or_signing(self):
        self.policy.deny='scope'
        with patch.object(self.database,'_connect',side_effect=AssertionError('driver reached')), \
             patch.object(self.authority_signer,'sign',side_effect=AssertionError('signing reached')),self.assertRaises(EffectV3Error):
            self.authority.prepare_scope(self.scope)

    def test_prepare_scope_commits_installing_before_update_escapes(self):
        connection=self.connection(None)
        with patch.object(self.database,'_connect',return_value=connection):update=self.authority.prepare_scope(self.scope)
        self.assertEqual(update.receipt.purpose,2)
        self.assertEqual(self.names(connection)[-2:],['commit','close'])
        self.assertEqual(len(self.mutations(connection)),1)
        self.assertIn("'installing'",self.mutations(connection)[0][1])

    def test_existing_or_uncertain_scope_cannot_be_implicitly_reissued(self):
        connection=self.connection(self.state_row(status='installing',reserved=0,ack=None))
        with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(ReconciliationRequiredV3):
            self.authority.prepare_scope(self.scope)
        self.assertEqual(self.mutations(connection),[])

    def test_installation_needs_exact_provider_ack_and_commit(self):
        connection=self.connection(self.state_row(status='installing',reserved=0,ack=None))
        with patch.object(self.database,'_connect',return_value=connection):self.authority.activate_scope(self.scope.scope_id,self.ack)
        self.assertIn("status='active'",self.mutations(connection)[0][1])
        self.assertEqual(self.names(connection)[-2:],['commit','close'])

    def test_forged_installation_ack_cannot_activate(self):
        forged=replace(self.ack,signature=b'\0'*64)
        connection=self.connection(self.state_row(status='installing',reserved=0,ack=None))
        with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(ReceiptError):
            self.authority.activate_scope(self.scope.scope_id,forged)
        self.assertEqual(self.mutations(connection),[])

    def test_new_reservation_persists_exact_admission_nonce_cost_and_budget(self):
        connection=self.connection(self.state_row(reserved=0),None)
        with patch.object(self.database,'_connect',return_value=connection):admission=self.authority.reserve(self.proposal)
        verify_admission(self.proposal,admission,self.identity.authority,self.now)
        row=connection.operation_inserts[0]
        self.assertEqual(row[:4],(self.proposal.operation_id,self.scope.scope_id,self.proposal.canonical_bytes(),self.proposal.digest))
        self.assertEqual(row[6:],(self.proposal.context.nonce,3))
        self.assertEqual(SignedEffectReceiptV3.from_bytes(row[4]),admission)
        self.assertEqual(self.mutations(connection)[1][2],(3,self.scope.scope_id))
        self.assertEqual(self.names(connection)[-2:],['commit','close'])

    def test_unknown_reservation_commit_never_returns_an_admission(self):
        connection=self.connection(self.state_row(reserved=0),None,commit_error=RuntimeError('unknown reserve commit'))
        with patch.object(self.database,'_connect',return_value=connection),self.assertRaisesRegex(RuntimeError,'unknown reserve'):
            self.authority.reserve(self.proposal)
        self.assertEqual(len(connection.operation_inserts),1)
        self.assertEqual(self.names(connection).count('commit'),1)

    def test_draining_or_installing_authority_does_not_return_old_pending_admission(self):
        fence,update,ack=self.cutover()
        rows=(self.state_row(status='draining',fence=fence,update=update,ack=ack),
              self.state_row(status='installing',reserved=0,ack=None))
        for row in rows:
            connection=self.connection(row)
            with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):
                self.authority.reserve(self.proposal)
            self.assertEqual(self.mutations(connection),[])

    def test_policy_denial_revalidates_pending_admission_before_any_database(self):
        self.policy.deny='action'
        with patch.object(self.database,'_connect',side_effect=AssertionError('driver reached')),self.assertRaises(EffectV3Error):
            self.authority.reserve(self.proposal)

    def test_expired_pending_admission_is_not_reissued(self):
        self.now=1100
        with patch.object(self.database,'_connect',side_effect=AssertionError('driver reached')),self.assertRaises(EffectV3Error):
            self.authority.reserve(self.proposal)

    def test_shared_budget_exhaustion_has_no_signature_or_writes(self):
        connection=self.connection(self.state_row(reserved=6,spent=2),None)
        with patch.object(self.database,'_connect',return_value=connection), \
             patch.object(self.authority_signer,'sign',side_effect=AssertionError('signing reached')),self.assertRaises(EffectV3Error):
            self.authority.reserve(self.proposal)
        self.assertEqual(self.mutations(connection),[])

    def test_reserved_admission_is_current_and_byte_identical(self):
        connection=self.connection(self.state_row(),self.operation_row())
        with patch.object(self.database,'_connect',return_value=connection):
            self.assertEqual(self.authority.reserve(self.proposal),self.admission)
        self.assertEqual(self.mutations(connection),[])

    def test_dispatched_and_terminal_operations_require_reconciliation(self):
        for status,result in (('dispatched',None),('indeterminate',None),('committed',self.record())):
            connection=self.connection(self.state_row(),self.operation_row(status=status,result=result))
            with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(ReconciliationRequiredV3):
                self.authority.reserve(self.proposal)
            self.assertEqual(self.mutations(connection),[])

    def test_dispatch_claim_commits_exactly_once(self):
        connection=self.connection(self.state_row(),self.operation_row())
        with patch.object(self.database,'_connect',return_value=connection):
            self.authority.claim_dispatch(self.proposal,self.admission)
        self.assertEqual(len(self.mutations(connection)),1)
        self.assertIn("status='dispatched'",self.mutations(connection)[0][1])
        second=self.connection(self.state_row(),self.operation_row(status='dispatched'))
        with patch.object(self.database,'_connect',return_value=second),self.assertRaises(ReconciliationRequiredV3):
            self.authority.claim_dispatch(self.proposal,self.admission)
        self.assertEqual(self.mutations(second),[])

    def test_changed_proposal_cannot_rebind_stable_operation(self):
        changed=fixture_proposal(budget=10,nonce=b'N'*32)
        self.assertEqual(changed.operation_id,self.proposal.operation_id)
        connection=self.connection(self.state_row(),self.operation_row())
        with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):
            self.authority.reserve(changed)

    def test_scope_ledger_limit_or_schema_mismatch_rejects(self):
        row=list(self.state_row());row[2]=11
        connection=self.connection(tuple(row))
        with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):self.authority.reserve(self.proposal)
        bad=self.connection();bad.rows[0]=(2,AUTH_MIGRATION_HASH,authority_configuration(self.identity))
        with patch.object(self.database,'_connect',return_value=bad),self.assertRaises(EffectV3Error):self.authority.read_scope(self.scope.scope_id)

    def test_authenticated_completed_effect_moves_reserved_to_spent(self):
        result=self.record();connection=self.connection(self.state_row(),self.operation_row(status='dispatched'))
        with patch.object(self.database,'_connect',return_value=connection):
            self.assertEqual(self.authority.accept_effect(self.proposal,self.admission,result),result)
        self.assertEqual(self.mutations(connection)[0][2],(3,3,self.scope.scope_id))
        self.assertIn("status='committed'",self.mutations(connection)[1][1])

    def test_completed_effect_reconciles_after_policy_expiry_and_cutover(self):
        result=self.record();fence,update,ack=self.cutover()
        self.now=2000;self.policy.deny='action'
        connection=self.connection(self.state_row(status='draining',fence=fence,update=update,ack=ack),self.operation_row(status='indeterminate'))
        with patch.object(self.database,'_connect',return_value=connection):
            self.assertEqual(self.authority.accept_effect(self.proposal,self.admission,result),result)
        self.assertEqual(self.policy.calls,[])

    def test_repeat_committed_result_does_not_spend_twice(self):
        result=self.record()
        connection=self.connection(self.state_row(reserved=0,spent=3),self.operation_row(status='committed',result=result))
        with patch.object(self.database,'_connect',return_value=connection):self.assertEqual(self.authority.accept_effect(self.proposal,self.admission,result),result)
        self.assertEqual(self.mutations(connection),[])

    def test_forged_result_cannot_move_budget(self):
        with patch.object(self.database,'_connect',side_effect=AssertionError('driver reached')),self.assertRaises(ReceiptError):
            self.authority.accept_effect(self.proposal,self.admission,replace(self.record(),signature=b'\0'*64))

    def test_timeout_only_marks_indeterminate_and_retains_budget(self):
        connection=self.connection(self.state_row(),self.operation_row(status='dispatched'))
        with patch.object(self.database,'_connect',return_value=connection):self.authority.mark_indeterminate(self.proposal)
        self.assertEqual(len(self.mutations(connection)),1)
        self.assertIn("status='indeterminate'",self.mutations(connection)[0][1])
        self.assertFalse(any('budget_reserved=' in e[1] for e in self.mutations(connection)))

    def test_begin_revocation_stops_new_work_before_provider_ack(self):
        fence,_,_=self.cutover();connection=self.connection(self.state_row())
        with patch.object(self.database,'_connect',return_value=connection):update=self.authority.begin_revocation(self.scope.scope_id,fence)
        self.assertEqual(update.receipt.authority_epoch,4)
        self.assertIn("status='draining'",self.mutations(connection)[0][1])
        self.assertIn('ack_bytes=NULL',self.mutations(connection)[0][1])
        self.assertEqual(self.names(connection)[-2:],['commit','close'])

    def test_interrupted_expired_installation_can_only_cancel_via_newer_fence(self):
        self.now=1200
        fence=replace(self.fence,authority_epoch=4,policy_version=8,fencing_token=10,issued_at=1200,expires_at=1300)
        connection=self.connection(self.state_row(status='installing',reserved=0,ack=None))
        with patch.object(self.database,'_connect',return_value=connection):update=self.authority.begin_revocation(self.scope.scope_id,fence)
        self.assertEqual(update.receipt.fencing_token,10)
        self.assertIn("status='draining'",self.mutations(connection)[0][1])

    def test_cutover_wrong_provider_or_nonmonotone_policy_rejects(self):
        for changes in ({'provider_id':b'X'*32},{'authority_epoch':3},{'fencing_token':9},
                        {'policy_version':6},{'policy_root':b'X'*32,'policy_version':7}):
            fence=replace(self.cutover()[0],**changes);connection=self.connection(self.state_row())
            with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):
                self.authority.begin_revocation(self.scope.scope_id,fence)
            self.assertEqual(self.mutations(connection),[])

    def test_cutover_expiring_during_policy_check_is_not_signed_or_persisted(self):
        fence,_,_=self.cutover();connection=self.connection(self.state_row())
        def delay(*args):self.now=1100
        with patch.object(self.database,'_connect',return_value=connection), \
             patch.object(self.policy,'assert_fence_allowed',side_effect=delay),self.assertRaises(EffectV3Error):
            self.authority.begin_revocation(self.scope.scope_id,fence)
        self.assertEqual(self.mutations(connection),[])

    def test_live_postgres_connection_cannot_downgrade_certificate_verification(self):
        import sys,types
        calls=[]
        driver=types.ModuleType('psycopg2')
        driver.connect=lambda *args,**kwargs:calls.append((args,kwargs)) or object()
        for mode in ('staging','testnet','production'):
            with patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),patch.dict(sys.modules,{'psycopg2':driver}):
                database=PostgresAuthorityDatabaseV3('postgresql://synthetic-unused?sslmode=disable',authority_configuration(self.identity))
                database._connect()
            self.assertEqual(calls[-1][1].get('sslmode'),'verify-full')
            self.assertEqual(calls[-1][1].get('application_name'),'vams-effect-authority-v3')
            self.assertIn('search_path=pg_catalog',calls[-1][1]['options'])

    def test_live_postgres_pins_tcp_host_and_disables_gss_tls_bypass(self):
        import sys,types
        calls=[];driver=types.ModuleType('psycopg2')
        driver.connect=lambda *args,**kwargs:calls.append(kwargs) or object()
        with patch.dict(os.environ,{'VAMS_ENV':'production'},clear=True),patch.dict(sys.modules,{'psycopg2':driver}):
            database=PostgresAuthorityDatabaseV3('postgresql://db.example:6543/db?host=%2Ftmp&gssencmode=prefer',authority_configuration(self.identity))
            database._connect()
        self.assertEqual(calls[0].get('host'),'db.example')
        self.assertEqual(calls[0].get('port'),6543)
        self.assertEqual(calls[0].get('gssencmode'),'disable')

    def test_live_postgres_refuses_implicit_unix_or_encoded_socket_hosts(self):
        import sys,types
        for dsn in ('postgresql:///db','postgresql://%2Ftmp/db','postgresql://hostA,hostB/db'):
            calls=[];driver=types.ModuleType('psycopg2')
            driver.connect=lambda *args,**kwargs:calls.append(kwargs) or object()
            with self.subTest(dsn=dsn),patch.dict(os.environ,{'VAMS_ENV':'production'},clear=True), \
                 patch.dict(sys.modules,{'psycopg2':driver}),self.assertRaises(EffectV3Error):
                PostgresAuthorityDatabaseV3(dsn,authority_configuration(self.identity))._connect()
            self.assertEqual(calls,[])

    def test_expired_unacknowledged_cutover_can_get_a_stronger_new_fence(self):
        old,old_update,_=self.cutover();self.now=1200
        stronger=replace(old,authority_epoch=5,policy_version=9,fencing_token=11,issued_at=1200,expires_at=1300)
        connection=self.connection(self.state_row(status='draining',fence=old,update=old_update,ack=None))
        with patch.object(self.database,'_connect',return_value=connection):
            update=self.authority.refresh_unacknowledged_cutover(self.scope.scope_id,stronger)
        self.assertEqual(update.receipt.fencing_token,11)
        self.assertIn("status='draining'",self.mutations(connection)[0][1])
        self.assertNotIn('budget_reserved=',self.mutations(connection)[0][1])

    def test_acknowledged_cutover_cannot_be_refreshed_or_history_replaced(self):
        old,old_update,old_ack=self.cutover()
        stronger=replace(old,authority_epoch=5,policy_version=9,fencing_token=11)
        connection=self.connection(self.state_row(status='draining',fence=old,update=old_update,ack=old_ack))
        with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(ReconciliationRequiredV3):
            self.authority.refresh_unacknowledged_cutover(self.scope.scope_id,stronger)
        self.assertEqual(self.mutations(connection),[])

    def test_record_ack_is_not_a_refund_or_revocation_completion(self):
        fence,update,ack=self.cutover()
        connection=self.connection(self.state_row(status='draining',fence=fence,update=update,ack=None))
        with patch.object(self.database,'_connect',return_value=connection):self.authority.record_fence_ack(self.scope.scope_id,fence,update,ack)
        self.assertEqual(len(self.mutations(connection)),1)
        self.assertNotIn('budget_reserved=',self.mutations(connection)[0][1])
        self.assertNotIn("status='revoked'",self.mutations(connection)[0][1])

    def absence(self,fence,ack):
        return sign_receipt(self.provider_signer,purpose=5,subject=absence_subject(self.proposal,ack),
            provider=fence.provider_id,epoch=fence.authority_epoch,policy=fence.policy_version,
            fence=fence.fencing_token,issued_at=self.now,expires_at=self.now+1)

    def test_fenced_absence_releases_exact_reserved_cost_once(self):
        fence,update,ack=self.cutover();absence=self.absence(fence,ack)
        connection=self.connection(self.state_row(status='draining',fence=fence,update=update,ack=ack),self.operation_row(status='indeterminate'))
        with patch.object(self.database,'_connect',return_value=connection):
            self.authority.release_fenced_absence(self.proposal,self.admission,fence,update,ack,absence)
        self.assertEqual(self.mutations(connection)[0][2],(3,self.scope.scope_id))
        self.assertIn("status='rejected'",self.mutations(connection)[1][1])
        repeated=self.connection(self.state_row(status='draining',reserved=0,fence=fence,update=update,ack=ack),self.operation_row(status='rejected',result=absence))
        with patch.object(self.database,'_connect',return_value=repeated):self.authority.release_fenced_absence(self.proposal,self.admission,fence,update,ack,absence)
        self.assertEqual(self.mutations(repeated),[])

    def test_committed_operation_cannot_also_refund_by_absence(self):
        fence,update,ack=self.cutover();absence=self.absence(fence,ack)
        connection=self.connection(self.state_row(status='draining',reserved=0,spent=3,fence=fence,update=update,ack=ack),
            self.operation_row(status='committed',result=self.record()))
        with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):
            self.authority.release_fenced_absence(self.proposal,self.admission,fence,update,ack,absence)
        self.assertEqual(self.mutations(connection),[])

    def test_revocation_cannot_finish_without_ack_or_with_unresolved_operations(self):
        fence,update,ack=self.cutover()
        for retained_ack,pending,reserved in ((None,None,0),(ack,1,0),(ack,0,3)):
            rows=[self.state_row(status='draining',reserved=reserved,fence=fence,update=update,ack=retained_ack)]
            if retained_ack is not None:rows.append((pending,))
            connection=self.connection(*rows)
            with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):
                self.authority.complete_revocation(self.scope.scope_id)
            self.assertEqual(self.mutations(connection),[])

    def test_revocation_finishes_only_after_ack_and_zero_obligations(self):
        fence,update,ack=self.cutover()
        connection=self.connection(self.state_row(status='draining',reserved=0,spent=3,fence=fence,update=update,ack=ack),(0,))
        with patch.object(self.database,'_connect',return_value=connection):self.authority.complete_revocation(self.scope.scope_id)
        self.assertIn("status='revoked'",self.mutations(connection)[0][1])

    def test_explicit_authority_migration_rejects_partial_schema_and_reads_back_pin(self):
        partial=self.connection();partial.rows=[(AUTH_META,None,None)]
        with patch.object(self.database,'_connect',return_value=partial),self.assertRaises(EffectV3Error):self.database.migrate()
        fresh=self.connection();fresh.rows=[(None,None,None),(3,AUTH_MIGRATION_HASH,authority_configuration(self.identity))]
        with patch.object(self.database,'_connect',return_value=fresh):self.database.migrate()
        self.assertEqual(sum(e[1].startswith('CREATE TABLE ') for e in fresh.events if e[0]=='execute'),3)


class CoordinatorV3Tests(AuthorityFixture):
    """Actual V3 authority/provider algorithms connected through queued drivers."""
    def setUp(self):
        super().setUp()
        self.provider_database=PostgresEffectDatabaseV3('postgresql://synthetic-unused',self.identity.digest)
        self.provider=PostgresObjectProviderV3(self.provider_database,self.identity,self.provider_signer,self.policy,clock=lambda:self.now)
        self.transport=DirectObjectProviderTransportV3(self.provider)
        self.coordinator=ObjectEffectCoordinatorV3(self.authority,self.transport)

    def provider_connection(self,*rows,**kwargs):return ControlledConnection(self.identity,rows,**kwargs)
    def plans(self,*operations):return [self.connection(self.state_row(),self.operation_row(status=status)) for status in operations]

    def test_composed_positive_path_reserves_claims_commits_and_reconciles(self):
        authorities=self.plans('reserved','reserved','dispatched')
        provider=self.provider_connection((self.fence.canonical_bytes(),),None)
        with patch.object(self.database,'_connect',side_effect=authorities),patch.object(self.provider_database,'_connect',return_value=provider):
            result=self.coordinator.execute(self.proposal,b'fixture-object')
        verify_effect(self.proposal,self.admission,result,self.identity.provider,self.now,authority=self.identity.authority)
        self.assertEqual(len(provider.inserts),1)
        self.assertIn("status='dispatched'",self.mutations(authorities[1])[0][1])
        self.assertIn("status='committed'",self.mutations(authorities[2])[-1][1])

    def test_new_admission_flows_from_committed_reservation_through_provider(self):
        reserve=self.connection(self.state_row(reserved=0),None)
        authorities=[reserve]
        def authority_connection():
            if not reserve.operation_inserts:return reserve
            admission=SignedEffectReceiptV3.from_bytes(reserve.operation_inserts[0][4])
            status='reserved' if len(authorities)==1 else 'dispatched'
            connection=self.connection(self.state_row(),self.operation_row(status=status,admission=admission))
            authorities.append(connection);return connection
        provider=self.provider_connection((self.fence.canonical_bytes(),),None)
        with patch.object(self.database,'_connect',side_effect=authority_connection),patch.object(self.provider_database,'_connect',return_value=provider):
            result=self.coordinator.execute(self.proposal,b'fixture-object')
        admission=SignedEffectReceiptV3.from_bytes(reserve.operation_inserts[0][4])
        verify_effect(self.proposal,admission,result,self.identity.provider,self.now,authority=self.identity.authority)
        self.assertEqual(provider.inserts[0][4],admission.canonical_bytes())
        self.assertEqual(admission.receipt.issued_at,self.now)
        self.assertEqual(len(authorities),3)
        self.assertTrue(all(self.names(connection)[-2:]==['commit','close'] for connection in authorities))

    def test_composed_cutover_persists_actual_provider_ack_without_releasing_budget(self):
        fence,_,_=self.cutover()
        begin=self.connection(self.state_row());authorities=[begin]
        def authority_connection():
            mutations=self.mutations(begin)
            if not mutations:return begin
            update=SignedEffectReceiptV3.from_bytes(mutations[0][2][1])
            connection=self.connection(self.state_row(status='draining',fence=fence,update=update,ack=None))
            authorities.append(connection);return connection
        provider=self.provider_connection((self.fence.canonical_bytes(),self.update.canonical_bytes(),self.ack.canonical_bytes()))
        with patch.object(self.database,'_connect',side_effect=authority_connection),patch.object(self.provider_database,'_connect',return_value=provider):
            ack=self.coordinator.start_cutover(self.scope.scope_id,fence)
        self.assertEqual(ack.receipt.authority_epoch,4)
        self.assertEqual(len(authorities),2)
        self.assertEqual(self.mutations(authorities[1])[0][2][0],ack.canonical_bytes())
        self.assertFalse(any('budget_reserved=' in event[1] for connection in authorities for event in self.mutations(connection)))

    def test_composed_fenced_absence_releases_only_exact_retained_obligation(self):
        fence,update,ack=self.cutover()
        state=self.state_row(status='draining',fence=fence,update=update,ack=ack)
        read_operation=self.connection(state,self.operation_row(status='indeterminate'))
        read_scope=self.connection(state)
        release=self.connection(state,self.operation_row(status='indeterminate'))
        provider=self.provider_connection((fence.canonical_bytes(),update.canonical_bytes(),ack.canonical_bytes()),None)
        with patch.object(self.database,'_connect',side_effect=[read_operation,read_scope,release]), \
             patch.object(self.provider_database,'_connect',return_value=provider):absence=self.coordinator.reconcile_absence(self.proposal)
        self.assertEqual(absence.receipt.purpose,5)
        self.assertEqual(self.mutations(release)[0][2],(3,self.scope.scope_id))
        self.assertIn("status='rejected'",self.mutations(release)[1][1])
        self.assertEqual(provider.inserts,[])

    def test_uncertain_dispatch_claim_never_calls_provider(self):
        reserve,claim=self.plans('reserved','reserved');claim.commit_error=RuntimeError('unknown dispatch claim commit')
        with patch.object(self.database,'_connect',side_effect=[reserve,claim]), \
             patch.object(self.provider_database,'_connect',side_effect=AssertionError('provider called')),self.assertRaisesRegex(RuntimeError,'unknown dispatch'):
            self.coordinator.execute(self.proposal,b'fixture-object')

    def test_lost_effect_ack_uses_lookup_without_repeating_commit(self):
        authorities=self.plans('reserved','reserved','dispatched','indeterminate')
        provider_commit=self.provider_connection((self.fence.canonical_bytes(),),None)
        provider_calls=[]
        def provider_connection():
            provider_calls.append('db')
            if len(provider_calls)==1:return provider_commit
            row=provider_commit.inserts[0]
            return self.provider_connection((row[3],row[4],row[7],row[8]))
        real_commit=self.provider.commit
        def lose_ack(*args):real_commit(*args);raise RuntimeError('controlled lost acknowledgement')
        with patch.object(self.database,'_connect',side_effect=authorities),patch.object(self.provider_database,'_connect',side_effect=provider_connection), \
             patch.object(self.provider,'commit',side_effect=lose_ack) as commit:
            result=self.coordinator.execute(self.proposal,b'fixture-object')
        self.assertEqual(commit.call_count,1);self.assertEqual(len(provider_commit.inserts),1)
        self.assertEqual(len(provider_calls),2)
        self.assertEqual(result.receipt.purpose,4)

    def test_timeout_and_empty_lookup_keep_obligation_without_resend(self):
        authorities=self.plans('reserved','reserved','dispatched')
        with patch.object(self.database,'_connect',side_effect=authorities), \
             patch.object(self.provider,'commit',side_effect=RuntimeError('controlled timeout')) as commit, \
             patch.object(self.provider,'lookup',return_value=None) as lookup,self.assertRaises(ReconciliationRequiredV3):
            self.coordinator.execute(self.proposal,b'fixture-object')
        self.assertEqual(commit.call_count,1);self.assertEqual(lookup.call_count,1)
        self.assertIn("status='indeterminate'",self.mutations(authorities[-1])[0][1])
        reread=self.connection(self.state_row(),self.operation_row(status='indeterminate'))
        with patch.object(self.database,'_connect',return_value=reread),patch.object(self.provider,'commit',side_effect=AssertionError('resend')), \
             patch.object(self.provider,'lookup',return_value=None),self.assertRaises(ReconciliationRequiredV3):self.coordinator.reconcile(self.proposal)

    def test_completed_reconciliation_after_expiry_never_calls_provider_or_policy(self):
        result=self.record();self.now=2000;self.policy.deny='action'
        connection=self.connection(self.state_row(reserved=0,spent=3),self.operation_row(status='committed',result=result))
        with patch.object(self.database,'_connect',return_value=connection),patch.object(self.provider_database,'_connect',side_effect=AssertionError('provider call')):
            self.assertEqual(self.coordinator.reconcile(self.proposal),result)
        self.assertEqual(self.policy.calls,[])

    def test_unknown_old_provider_blocks_cutover_and_never_switches_identity(self):
        fence,update,ack=self.cutover()
        state=self.connection(self.state_row(status='draining',fence=fence,update=update,ack=None))
        with patch.object(self.database,'_connect',return_value=state),patch.object(self.provider,'lookup_fence',side_effect=RuntimeError('provider unavailable')), \
             patch.object(self.provider,'advance_fence',side_effect=AssertionError('resend')),self.assertRaises(ReconciliationRequiredV3):
            self.coordinator.reconcile_cutover(self.scope.scope_id)
        self.assertEqual(self.mutations(state),[])

    def test_old_protocol_or_other_identity_transport_cannot_compose(self):
        with self.assertRaises(EffectV3Error):ObjectEffectCoordinatorV3(self.authority,object())
        with self.assertRaises(EffectV3Error):DirectObjectProviderTransportV3(object())


if __name__=='__main__':unittest.main()
