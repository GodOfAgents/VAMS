"""Explicit renewable authority over storage4, with unchanged V3 effect wire.

Unactivated source candidate. Current host policy, custody, transport, native PG
and recovery qualification remain separate requirements, never fixture inference.
"""
from abc import abstractmethod
from dataclasses import dataclass
from neuron.effect_authority_v3 import (
 PostgresEffectAuthorityV3,CurrentAuthorityPolicyV1,AuthorityStateV3,OperationStateV3,
 ObjectAuthorityScopeV3,ReconciliationRequiredV3,PENDING,
)
from neuron.effect_authority_store_v4 import (
 PostgresAuthorityDatabaseV4,authority_configuration_v4,GENERATIONS4,HEADS4,OPERATIONS4,
)
from neuron.effect_protocol_v3 import (
 EffectV3Error,ObjectFenceV3,integer,hash32,commitment,sign_receipt,verify_fence_ack,
 SignedEffectReceiptV3,
)

def generation_id_v4(scope):return commitment(b'VAMS:AUTHORITY-GENERATION:v4\0',scope.canonical_bytes())

class CurrentRenewalPolicyV1(CurrentAuthorityPolicyV1):
 @abstractmethod
 def assert_renewal_allowed(self,previous,successor,now):
  """Authenticate successor and absolute cumulative ceiling under host governance."""
  raise NotImplementedError

@dataclass(frozen=True)
class AuthorityStateV4(AuthorityStateV3):
 generation_id:bytes
 ordinal:int
 previous_generation:bytes|None

@dataclass(frozen=True)
class OperationStateV4(OperationStateV3):
 generation_id:bytes

class PostgresEffectAuthorityV4(PostgresEffectAuthorityV3):
 _database_class=PostgresAuthorityDatabaseV4
 _policy_class=CurrentRenewalPolicyV1
 _configuration=staticmethod(authority_configuration_v4)
 _scope_table=HEADS4
 _operation_table=OPERATIONS4

 @staticmethod
 def _generation_fields(scope,generation,ordinal,previous):
  if hash32(generation)!=generation_id_v4(scope):raise EffectV3Error('generation does not commit exact grant')
  integer(ordinal,positive=True)
  if (ordinal==1)!=(previous is None):raise EffectV3Error('invalid generation predecessor')
  if previous is not None:
   hash32(previous)
   if previous==generation:raise EffectV3Error('generation cannot precede itself')

 def _state(self,cursor,scope_id,now):
  cursor.execute(f'''SELECT g.scope_bytes,g.status,h.budget_limit,h.budget_reserved,h.budget_spent,
   g.fence_bytes,g.update_bytes,g.ack_bytes,g.generation_id,g.ordinal,g.previous_generation,
   g.closed_reserved,g.closed_spent FROM {HEADS4} h JOIN {GENERATIONS4} g
   ON g.scope_id=h.scope_id AND g.generation_id=h.current_generation WHERE h.scope_id=%s FOR UPDATE OF h,g''',(scope_id,))
  row=cursor.fetchone()
  if row is None:return None
  state=self._decode_state(scope_id,row[:8],now)
  generation=bytes(row[8]);ordinal=integer(row[9],positive=True);previous=bytes(row[10]) if row[10] is not None else None
  self._generation_fields(state.scope,generation,ordinal,previous)
  if state.status=='revoked':
   if integer(row[11])!=state.reserved or integer(row[12])!=state.spent or state.reserved!=0:
    raise EffectV3Error('closed generation budget snapshot mismatch')
  elif row[11] is not None or row[12] is not None:raise EffectV3Error('open generation carries a closure snapshot')
  return AuthorityStateV4(state.scope,state.status,state.reserved,state.spent,state.fence,state.update,state.ack,
   generation,ordinal,previous)

 def _historical_generation(self,cursor,scope_id,generation,head,now):
  hash32(generation)
  if generation==head.generation_id:return head
  cursor.execute(f'''SELECT scope_bytes,status,fence_bytes,update_bytes,ack_bytes,generation_id,
   ordinal,previous_generation,closed_reserved,closed_spent FROM {GENERATIONS4}
   WHERE scope_id=%s AND generation_id=%s''',(scope_id,generation))
  row=cursor.fetchone()
  if row is None or row[1]!='revoked':raise EffectV3Error('missing or unclosed historical generation')
  scope=ObjectAuthorityScopeV3.from_bytes(bytes(row[0]))
  original=self._decode_state(scope_id,(row[0],row[1],scope.budget_limit,row[8],row[9],row[2],row[3],row[4]),now)
  ordinal=integer(row[6],positive=True);previous=bytes(row[7]) if row[7] is not None else None
  self._generation_fields(scope,bytes(row[5]),ordinal,previous)
  if bytes(row[5])!=generation or ordinal>=head.ordinal or original.reserved!=0 or original.spent>head.spent:
   raise EffectV3Error('historical generation or cumulative budget continuity mismatch')
  return AuthorityStateV4(original.scope,original.status,original.reserved,original.spent,
   original.fence,original.update,original.ack,generation,ordinal,previous)

 def read_generation(self,scope_id,generation):
  now=self._now();hash32(scope_id);hash32(generation)
  with self.database.transaction() as cursor:
   head=self._state(cursor,scope_id,now)
   if head is None:raise EffectV3Error('missing scope head')
   return self._historical_generation(cursor,scope_id,generation,head,now)

 def _operation(self,cursor,proposal,state,now):
  cursor.execute(f'''SELECT proposal_bytes,admission_bytes,cost_units,status,result_bytes,scope_id,
   proposal_digest,generation_id FROM {OPERATIONS4} WHERE operation_id=%s''',(proposal.operation_id,))
  row=cursor.fetchone()
  if row is None:return None
  generation=hash32(bytes(row[7]));original=self._historical_generation(cursor,state.scope.scope_id,generation,state,now)
  operation=self._decode_operation(proposal,original,now,row[:7])
  if generation!=state.generation_id and operation.status in PENDING:
   raise ReconciliationRequiredV3('old-generation pending obligation prevents safe renewal')
  return OperationStateV4(operation.proposal,operation.admission,operation.status,operation.result,generation)

 def _insert_operation(self,cursor,proposal,state,admission):
  cursor.execute(f'''INSERT INTO {OPERATIONS4}(operation_id,scope_id,generation_id,proposal_bytes,
   proposal_digest,admission_bytes,admission_digest,nonce,cost_units,status,result_bytes)
   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'reserved',NULL)''',
   (proposal.operation_id,state.scope.scope_id,state.generation_id,proposal.canonical_bytes(),proposal.digest,
    admission.canonical_bytes(),admission.digest,proposal.context.nonce,proposal.cost_units))

 def _fence_update(self,scope):
  fence=ObjectFenceV3.from_context(scope.template,scope.fencing_token)
  update=sign_receipt(self._signer,purpose=2,subject=fence.digest,provider=fence.provider_id,
   epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
   issued_at=fence.issued_at,expires_at=fence.expires_at)
  return fence,update

 def _insert_generation(self,cursor,scope,ordinal,previous,fence,update):
  generation=generation_id_v4(scope)
  cursor.execute(f'''INSERT INTO {GENERATIONS4}(generation_id,scope_id,ordinal,previous_generation,
   scope_bytes,status,fence_bytes,update_bytes,ack_bytes,closed_reserved,closed_spent)
   VALUES(%s,%s,%s,%s,%s,'installing',%s,%s,NULL,NULL,NULL)''',
   (generation,scope.scope_id,ordinal,previous,scope.canonical_bytes(),fence.canonical_bytes(),update.canonical_bytes()))
  return generation

 def prepare_scope(self,scope):
  self._scope_policy(scope,self._now())
  with self.database.transaction() as cursor:
   self._lock(cursor,scope.scope_id)
   if self._state(cursor,scope.scope_id,self._now()) is not None:
    raise ReconciliationRequiredV3('existing head requires explicit renewal/reconciliation')
   self._scope_policy(scope,self._now());fence,update=self._fence_update(scope)
   generation=self._insert_generation(cursor,scope,1,None,fence,update)
   cursor.execute(f'''INSERT INTO {HEADS4}(scope_id,current_generation,budget_limit,budget_reserved,budget_spent)
    VALUES(%s,%s,%s,0,0)''',(scope.scope_id,generation,scope.budget_limit))
  return update

 def prepare_renewal(self,scope):
  self._scope_policy(scope,self._now())
  with self.database.transaction() as cursor:
   self._lock(cursor,scope.scope_id);old=self._state(cursor,scope.scope_id,self._now())
   if old is None or old.status!='revoked' or old.ack is None or old.reserved!=0:
    raise ReconciliationRequiredV3('renewal requires acknowledged closed authority and zero exposure')
   cursor.execute(f"SELECT COUNT(*) FROM {OPERATIONS4} WHERE scope_id=%s AND status IN ('reserved','dispatched','indeterminate')",(scope.scope_id,))
   pending=cursor.fetchone()
   if pending is None or integer(pending[0])!=0:raise ReconciliationRequiredV3('all prior obligations must reconcile before renewal')
   c=scope.template
   if (c.authority_epoch<=old.fence.authority_epoch or scope.fencing_token<=old.fence.fencing_token or
       c.policy_version<old.fence.policy_version or c.budget_unit!=old.scope.template.budget_unit or
       c.issued_at<old.ack.receipt.issued_at or scope.budget_limit<old.spent or
       c.policy_root!=old.fence.policy_root and c.policy_version==old.fence.policy_version):
    raise EffectV3Error('successor widens units/budget or fails acknowledged generation continuity')
   if self._policy.assert_renewal_allowed(old,scope,self._now()) is not None:raise EffectV3Error('unsupported renewal policy decision')
   self._scope_policy(scope,self._now())
   ordinal=integer(old.ordinal+1,positive=True);fence,update=self._fence_update(scope)
   generation=self._insert_generation(cursor,scope,ordinal,old.generation_id,fence,update)
   # Keep cumulative spend. A ceiling of10after spending3leaves7, not10.
   cursor.execute(f'UPDATE {HEADS4} SET current_generation=%s,budget_limit=%s WHERE scope_id=%s',
    (generation,scope.budget_limit,scope.scope_id))
  return update

 def activate_scope(self,scope_id,ack):
  with self.database.transaction() as cursor:
   self._lock(cursor,scope_id);state=self._state(cursor,scope_id,self._now())
   if state is None or state.status!='installing':raise EffectV3Error('generation is not installing')
   self._scope_policy(state.scope,self._now())
   verify_fence_ack(state.fence,state.update,ack,self.identity.provider,self._now(),authority=self.identity.authority)
   cursor.execute(f"UPDATE {GENERATIONS4} SET status='active',ack_bytes=%s WHERE generation_id=%s",
    (ack.canonical_bytes(),state.generation_id))

 def _begin_cutover(self,scope_id,fence,*,refresh):
  if type(fence) is not ObjectFenceV3 or fence.scope_id!=scope_id:raise EffectV3Error('matching cutover fence required')
  with self.database.transaction() as cursor:
   self._lock(cursor,scope_id);state=self._state(cursor,scope_id,self._now())
   allowed=(state is not None and state.status=='draining' and state.ack is None) if refresh else (
    state is not None and state.status in ('installing','active'))
   if not allowed:raise ReconciliationRequiredV3('cutover cannot replace closed/acknowledged history')
   old=state.fence
   if (fence.provider_id!=old.provider_id or fence.authority_epoch<=old.authority_epoch or
       fence.policy_version<old.policy_version or fence.fencing_token<=old.fencing_token or
       fence.policy_root!=old.policy_root and fence.policy_version==old.policy_version):
    raise EffectV3Error('cutover must advance same-provider authority/policy/fence')
   if self._policy.assert_fence_allowed(state.scope,fence,self._now()) is not None:raise EffectV3Error('unsupported cutover policy')
   now=self._now()
   if not fence.issued_at<=now<fence.expires_at:raise EffectV3Error('cutover is not current')
   update=sign_receipt(self._signer,purpose=2,subject=fence.digest,provider=fence.provider_id,
    epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
    issued_at=fence.issued_at,expires_at=fence.expires_at)
   cursor.execute(f"UPDATE {GENERATIONS4} SET status='draining',fence_bytes=%s,update_bytes=%s,ack_bytes=NULL WHERE generation_id=%s",
    (fence.canonical_bytes(),update.canonical_bytes(),state.generation_id))
  return update

 def record_fence_ack(self,scope_id,fence,update,ack):
  verify_fence_ack(fence,update,ack,self.identity.provider,self._now(),authority=self.identity.authority)
  with self.database.transaction() as cursor:
   self._lock(cursor,scope_id);state=self._state(cursor,scope_id,self._now())
   if state is None or state.status!='draining' or (state.fence,state.update)!=(fence,update):
    raise EffectV3Error('ack differs from current retained cutover')
   if state.ack is not None:
    if state.ack!=ack:raise EffectV3Error('conflicting cutover acknowledgement')
    return
   cursor.execute(f'UPDATE {GENERATIONS4} SET ack_bytes=%s WHERE generation_id=%s',(ack.canonical_bytes(),state.generation_id))

 def complete_revocation(self,scope_id):
  with self.database.transaction() as cursor:
   self._lock(cursor,scope_id);state=self._state(cursor,scope_id,self._now())
   if state is None or state.status!='draining' or state.ack is None or state.reserved!=0:
    raise ReconciliationRequiredV3('cutover requires acknowledgement and zero reserved budget')
   cursor.execute(f"SELECT COUNT(*) FROM {OPERATIONS4} WHERE scope_id=%s AND status IN ('reserved','dispatched','indeterminate')",(scope_id,))
   pending=cursor.fetchone()
   if pending is None or integer(pending[0])!=0:raise ReconciliationRequiredV3('unresolved obligations prevent closure')
   cursor.execute(f"UPDATE {GENERATIONS4} SET status='revoked',closed_reserved=0,closed_spent=%s WHERE generation_id=%s",
    (state.spent,state.generation_id))
