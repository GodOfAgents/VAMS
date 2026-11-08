"""Real signatures/queued SQL calls, not native PG or authenticated host policy."""
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from neuron.effect_authority_v3 import ObjectAuthorityScopeV3,ReconciliationRequiredV3
from neuron.effect_authority_v4 import CurrentRenewalPolicyV1,PostgresEffectAuthorityV4,generation_id_v4
from neuron.effect_authority_store_v4 import (
 PostgresAuthorityDatabaseV4,authority_configuration_v4,META4,MIGRATION4,GENERATIONS4,HEADS4,OPERATIONS4,
)
from neuron.effect_coordinator_v3 import ObjectEffectCoordinatorV3,DirectObjectProviderTransportV3
from neuron.effect_coordinator_v4 import ObjectEffectCoordinatorV4
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_provider_v3 import PostgresObjectProviderV3
from neuron.effect_protocol_v3 import (
 EffectV3Error,ObjectFenceV3,SignedEffectReceiptV3,absence_subject,sign_receipt,
)
from neuron.tests.test_effect_authority_v3 import AuthorityFixture,AuthorityConnection
from neuron.tests.test_effect_protocol_v3 import fixture_proposal
from neuron.tests.test_effect_provider_v3 import ControlledConnection


class FixtureRenewalPolicy(CurrentRenewalPolicyV1):
 def __init__(self):self.calls=[];self.deny=None;self.renewal_result=None
 def check(self,name):
  self.calls.append(name)
  if self.deny==name:raise EffectV3Error('fixture policy DENY/UNKNOWN')
 def assert_allowed(self,p,now):return self.check('action')
 def assert_scope_allowed(self,s,now):return self.check('scope')
 def assert_fence_allowed(self,s,f,now):return self.check('fence')
 def assert_renewal_allowed(self,previous,successor,now):self.check('renewal');return self.renewal_result


class HistoryConnection(AuthorityConnection):
 def __init__(self,identity,rows=(),**kwargs):
  super().__init__(identity,rows,**kwargs)
  self.rows[0]=(4,MIGRATION4,authority_configuration_v4(identity))
  self.generation_inserts=[]
 def execute(self,sql,params=None):
  super().execute(sql,params)
  if sql.startswith('INSERT INTO '+GENERATIONS4):self.generation_inserts.append(params)
  if sql.startswith('INSERT INTO '+OPERATIONS4):self.operation_inserts.append(params)


class RenewalV4Tests(AuthorityFixture):
 def setUp(self):
  super().setUp()
  self.v3_authority=self.authority;self.v3_database=self.database;self.v3_policy=self.policy
  self.database=PostgresAuthorityDatabaseV4('postgresql://synthetic-unused',authority_configuration_v4(self.identity))
  self.policy=FixtureRenewalPolicy()
  self.authority=PostgresEffectAuthorityV4(self.database,self.identity,self.authority_signer,self.policy,clock=lambda:self.now)
  self.old_generation=generation_id_v4(self.scope)

 def connection(self,*rows,**kwargs):return HistoryConnection(self.identity,rows,**kwargs)
 def successor(self,**changes):
  context=dict(budget=10,authority_epoch=5,policy_version=9,intent_id=b'I'*32,issued_at=1050,expires_at=1150)
  context.update(changes);p=fixture_proposal(**context)
  p=replace(p,fencing_token=11);p=replace(p,context=replace(p.context,action_hash=p.action_hash))
  return p,ObjectAuthorityScopeV3(p.context,self.scope.resources,10,4,11)

 def head(self,scope=None,*,status='active',reserved=3,spent=0,ordinal=1,previous=None,fence=None,update=None,ack='default'):
  scope=scope or self.scope;fence=fence or ObjectFenceV3.from_context(scope.template,scope.fencing_token)
  if update is None:
   if scope==self.scope:update=self.update
   else:update,_=self.evidence(fence)
  if ack=='default':
   if scope==self.scope and fence==self.fence:ack=self.ack
   else:
    from neuron.effect_protocol_v3 import fence_ack_subject
    ack=sign_receipt(self.provider_signer,purpose=3,subject=fence_ack_subject(fence,update),provider=fence.provider_id,
     epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
     issued_at=self.now,expires_at=fence.expires_at)
  return (scope.canonical_bytes(),status,scope.budget_limit,reserved,spent,fence.canonical_bytes(),update.canonical_bytes(),
   ack.canonical_bytes() if ack is not None else None,generation_id_v4(scope),ordinal,previous,
   0 if status=='revoked' else None,spent if status=='revoked' else None)

 def closed(self,spent=3):
  f,u,a=self.cutover()
  return self.head(status='revoked',reserved=0,spent=spent,fence=f,update=u,ack=a)

 def history(self,spent=3):
  f,u,a=self.cutover()
  return (self.scope.canonical_bytes(),'revoked',f.canonical_bytes(),u.canonical_bytes(),a.canonical_bytes(),
   self.old_generation,1,None,0,spent)

 def operation(self,*,status='reserved',result=None,proposal=None,admission=None,generation=None):
  return (*self.operation_row(status=status,result=result,proposal=proposal,admission=admission),generation or self.old_generation)

 def test_frozen_generation_commitments_keep_same_actor_scope(self):
  vector=json.loads((Path(__file__).parents[2]/'docs/remediation/repair_20261030/generation-identity-v4.json').read_text())
  _,successor=self.successor()
  self.assertEqual(self.old_generation.hex(),vector['first_generation'])
  self.assertEqual(generation_id_v4(successor).hex(),vector['successor_generation'])
  self.assertEqual(successor.scope_id,self.scope.scope_id)

 def test_version3_storage_or_policy_cannot_be_implicitly_adopted(self):
  for database,policy in ((self.v3_database,self.policy),(self.database,self.v3_policy)):
   with self.assertRaises(EffectV3Error):PostgresEffectAuthorityV4(database,self.identity,self.authority_signer,policy)
  provider=PostgresObjectProviderV3(PostgresEffectDatabaseV3('postgresql://synthetic-unused',self.identity.digest),
   self.identity,self.provider_signer,self.policy,clock=lambda:self.now)
  transport=DirectObjectProviderTransportV3(provider)
  with self.assertRaises(EffectV3Error):ObjectEffectCoordinatorV3(self.authority,transport)
  self.assertIs(ObjectEffectCoordinatorV4(self.authority,transport).authority,self.authority)

 def test_fresh_scope_creates_first_generation_and_zero_cumulative_head_atomically(self):
  connection=self.connection(None)
  with patch.object(self.database,'_connect',return_value=connection):update=self.authority.prepare_scope(self.scope)
  self.assertEqual(connection.generation_inserts[0][:4],(self.old_generation,self.scope.scope_id,1,None))
  self.assertEqual(self.mutations(connection)[1][2],(self.scope.scope_id,self.old_generation,10))
  self.assertEqual(update.receipt.purpose,2)
  self.assertEqual(self.names(connection)[-2:],['commit','close'])

 def test_successor_retains_predecessor_and_never_resets_cumulative_spent(self):
  _,scope=self.successor();connection=self.connection(self.closed(),(0,))
  with patch.object(self.database,'_connect',return_value=connection):update=self.authority.prepare_renewal(scope)
  row=connection.generation_inserts[0]
  self.assertEqual(row[:4],(generation_id_v4(scope),self.scope.scope_id,2,self.old_generation))
  mutations=self.mutations(connection)
  self.assertEqual(len(mutations),2)
  self.assertTrue(mutations[1][1].startswith('UPDATE '+HEADS4))
  self.assertNotIn('budget_spent=',mutations[1][1]);self.assertNotIn('budget_reserved=',mutations[1][1])
  self.assertFalse(any(e[1].startswith('UPDATE '+GENERATIONS4) for e in mutations))
  self.assertEqual(update.receipt.authority_epoch,5)

 def test_no_active_draining_installing_or_unacknowledged_generation_can_renew(self):
  _,scope=self.successor();f,u,a=self.cutover()
  for row in (self.head(),self.head(status='installing',reserved=0,ack=None),
              self.head(status='draining',fence=f,update=u,ack=a),
              self.head(status='revoked',reserved=0,spent=3,fence=f,update=u,ack=None)):
   connection=self.connection(row)
   with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):
    self.authority.prepare_renewal(scope)
   self.assertEqual(self.mutations(connection),[])

 def test_unresolved_zero_cost_operations_block_renewal(self):
  _,scope=self.successor();connection=self.connection(self.closed(),(1,))
  with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(ReconciliationRequiredV3):
   self.authority.prepare_renewal(scope)
  self.assertEqual(self.mutations(connection),[])

 def test_new_ceiling_cannot_forgive_spend_or_change_budget_units(self):
  _,scope=self.successor()
  for successor in (replace(scope,budget_limit=2,max_action_cost=2),
                    replace(scope,template=replace(scope.template,budget_unit=b'X'*32))):
   connection=self.connection(self.closed(),(0,))
   with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):
    self.authority.prepare_renewal(successor)
   self.assertEqual(self.mutations(connection),[])

 def test_epoch_fence_policy_and_issued_time_cannot_rollback(self):
  for changes in ({'authority_epoch':4},{'policy_version':7},{'issued_at':1000,'expires_at':1100}):
   _,scope=self.successor(**changes);connection=self.connection(self.closed(),(0,))
   with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):self.authority.prepare_renewal(scope)
  _,scope=self.successor();scope=replace(scope,fencing_token=10)
  connection=self.connection(self.closed(),(0,))
  with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):self.authority.prepare_renewal(scope)

 def test_responsible_policy_denial_or_boolean_cannot_authorize_renewal(self):
  for deny,result in (('renewal',None),(None,True)):
   self.policy.deny=deny;self.policy.renewal_result=result;_,scope=self.successor()
   connection=self.connection(self.closed(),(0,))
   with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):self.authority.prepare_renewal(scope)
   self.assertEqual(self.mutations(connection),[])

 def test_new_ack_is_required_before_renewed_dispatch(self):
  p,scope=self.successor();connection=self.connection(self.head(scope,status='installing',reserved=0,spent=3,ordinal=2,previous=self.old_generation,ack=None))
  with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):self.authority.reserve(p)
  self.assertEqual(self.mutations(connection),[])

 def test_cumulative_spend_leaves_only_remaining_budget(self):
  p,scope=self.successor();connection=self.connection(self.head(scope,reserved=0,spent=8,ordinal=2,previous=self.old_generation),None)
  with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):self.authority.reserve(p)
  self.assertEqual(self.mutations(connection),[])

 def test_new_operation_persists_current_generation_identity(self):
  p,scope=self.successor();connection=self.connection(self.head(scope,reserved=0,spent=3,ordinal=2,previous=self.old_generation),None)
  with patch.object(self.database,'_connect',return_value=connection):admission=self.authority.reserve(p)
  self.assertEqual(connection.operation_inserts[0][2],generation_id_v4(scope))
  self.assertEqual(connection.operation_inserts[0][5],admission.canonical_bytes())
  self.assertEqual(self.mutations(connection)[1][2],(3,self.scope.scope_id))

 def test_old_completed_operation_reads_against_original_closed_grant(self):
  _,scope=self.successor();result=self.record()
  connection=self.connection(self.head(scope,reserved=0,spent=3,ordinal=2,previous=self.old_generation),
   self.operation(status='committed',result=result),self.history())
  self.policy.deny='action'
  with patch.object(self.database,'_connect',return_value=connection):operation=self.authority.read_operation(self.proposal)
  self.assertEqual(operation.result,result);self.assertEqual(operation.generation_id,self.old_generation)
  self.assertEqual(self.policy.calls,[]);self.assertEqual(self.mutations(connection),[])

 def test_repeat_old_earned_completion_never_spends_new_generation_budget(self):
  _,scope=self.successor();result=self.record()
  connection=self.connection(self.head(scope,reserved=0,spent=3,ordinal=2,previous=self.old_generation),
   self.operation(status='committed',result=result),self.history())
  with patch.object(self.database,'_connect',return_value=connection):self.assertEqual(self.authority.accept_effect(self.proposal,self.admission,result),result)
  self.assertEqual(self.mutations(connection),[])

 def test_old_fenced_absence_remains_verifiable_after_renewal(self):
  _,scope=self.successor();f,u,a=self.cutover()
  absence=sign_receipt(self.provider_signer,purpose=5,subject=absence_subject(self.proposal,a),provider=f.provider_id,
   epoch=f.authority_epoch,policy=f.policy_version,fence=f.fencing_token,issued_at=self.now,expires_at=self.now+1)
  connection=self.connection(self.head(scope,reserved=0,spent=0,ordinal=2,previous=self.old_generation),
   self.operation(status='rejected',result=absence),self.history(spent=0))
  with patch.object(self.database,'_connect',return_value=connection):operation=self.authority.read_operation(self.proposal)
  self.assertEqual(operation.result,absence);self.assertEqual(self.mutations(connection),[])

 def test_missing_tampered_or_reset_budget_history_rejects(self):
  _,scope=self.successor();result=self.record()
  bad=list(self.history());bad[5]=b'X'*32
  for historical,spent in ((None,3),(tuple(bad),3),(self.history(),0)):
   connection=self.connection(self.head(scope,reserved=0,spent=spent,ordinal=2,previous=self.old_generation),
    self.operation(status='committed',result=result),historical)
   with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):self.authority.read_operation(self.proposal)

 def test_old_pending_history_cannot_hide_behind_new_generation(self):
  _,scope=self.successor();connection=self.connection(self.head(scope,reserved=0,spent=3,ordinal=2,previous=self.old_generation),
   self.operation(status='dispatched'),self.history())
  with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(ReconciliationRequiredV3):self.authority.read_operation(self.proposal)

 def test_reused_logical_operation_cannot_be_rebound_under_successor(self):
  p,scope=self.successor(intent_id=self.proposal.context.intent_id)
  self.assertEqual(p.operation_id,self.proposal.operation_id)
  connection=self.connection(self.head(scope,reserved=0,spent=3,ordinal=2,previous=self.old_generation),
   self.operation(status='committed',result=self.record()),self.history())
  with patch.object(self.database,'_connect',return_value=connection),self.assertRaises(EffectV3Error):self.authority.reserve(p)
  self.assertEqual(self.mutations(connection),[])

 def test_unknown_renewal_commit_never_returns_update_or_retries(self):
  _,scope=self.successor();connection=self.connection(self.closed(),(0,),commit_error=RuntimeError('unknown renewal commit'))
  with patch.object(self.database,'_connect',return_value=connection),self.assertRaisesRegex(RuntimeError,'unknown renewal'):
   self.authority.prepare_renewal(scope)
  self.assertEqual(len(connection.generation_inserts),1);self.assertEqual(self.names(connection).count('commit'),1)

 def test_closure_retains_final_ack_and_cumulative_snapshot(self):
  f,u,a=self.cutover();connection=self.connection(self.head(status='draining',reserved=0,spent=3,fence=f,update=u,ack=a),(0,))
  with patch.object(self.database,'_connect',return_value=connection):self.authority.complete_revocation(self.scope.scope_id)
  mutation=self.mutations(connection)[0]
  self.assertTrue(mutation[1].startswith('UPDATE '+GENERATIONS4));self.assertEqual(mutation[2],(3,self.old_generation))
  self.assertIn('closed_spent=',mutation[1]);self.assertNotIn('ack_bytes=',mutation[1])

 def test_storage4_fresh_migration_and_legacy_version_rejection(self):
  connection=self.connection();connection.rows=[(None,None,None,None),(4,MIGRATION4,authority_configuration_v4(self.identity))]
  with patch.object(self.database,'_connect',return_value=connection):self.database.migrate()
  self.assertEqual(sum(e[1].startswith('CREATE TABLE ') for e in connection.events if e[0]=='execute'),4)
  bad=self.connection();bad.rows[0]=(3,MIGRATION4,authority_configuration_v4(self.identity))
  with patch.object(self.database,'_connect',return_value=bad),self.assertRaises(EffectV3Error):self.authority.read_scope(self.scope.scope_id)

 def test_renewal_composes_with_actual_provider_fence_and_new_ack(self):
  _,scope=self.successor();prepare=self.connection(self.closed(),(0,));connections=[prepare]
  def authority_connection():
   if not prepare.generation_inserts:return prepare
   update=SignedEffectReceiptV3.from_bytes(prepare.generation_inserts[0][6])
   connection=self.connection(self.head(scope,status='installing',reserved=0,spent=3,ordinal=2,
    previous=self.old_generation,update=update,ack=None));connections.append(connection);return connection
  f,u,a=self.cutover()
  provider_database=PostgresEffectDatabaseV3('postgresql://synthetic-unused',self.identity.digest)
  provider=PostgresObjectProviderV3(provider_database,self.identity,self.provider_signer,self.policy,clock=lambda:self.now)
  provider_connection=ControlledConnection(self.identity,((f.canonical_bytes(),u.canonical_bytes(),a.canonical_bytes()),))
  coordinator=ObjectEffectCoordinatorV4(self.authority,DirectObjectProviderTransportV3(provider))
  with patch.object(self.database,'_connect',side_effect=authority_connection),patch.object(provider_database,'_connect',return_value=provider_connection):
   ack=coordinator.renew(scope)
  self.assertEqual(ack.receipt.authority_epoch,5);self.assertEqual(len(connections),2)
  self.assertIn("status='active'",self.mutations(connections[1])[0][1])
  self.assertEqual(self.mutations(connections[1])[0][2][0],ack.canonical_bytes())


if __name__=='__main__':unittest.main()
