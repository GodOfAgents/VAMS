"""Unactivated V3 authority: durable obligations, single dispatch and cutover.

Actual host-policy/custody/PG qualification is required. No HTTP/CLI route, implicit
reissue, provider migration, timeout refund or automatic execution retry is added.
"""
from abc import abstractmethod
from dataclasses import dataclass
import time

from neuron.action_context import ActionContextV1,HASH_FIELDS
from neuron.effect_protocol_v3 import (
    ObjectEffectV3,ObjectFenceV3,SignedEffectReceiptV3,EffectV3Error,integer,hash32,word,
    sign_receipt,verify_admission,verify_admitted_obligation,verify_effect,
    verify_fence_update,verify_fence_ack,verify_fenced_absence,ACTION_SIZE,MAX_ADMISSION_SECONDS,
)
from neuron.effect_provider_v3 import CurrentActionPolicyV1,ObjectProviderIdentityV3
from neuron.effect_authority_store_v3 import PostgresAuthorityDatabaseV3,authority_configuration,SCOPES,OPERATIONS
from neuron.signed_receipts import ReceiptSignerV3
from neuron.runtime_safety import ImmutableRuntimeConfiguration,RuntimeConfigurationError,load_runtime_policy

SCOPE_DOMAIN=b'VAMS:OBJECT-AUTHORITY-SCOPE:v3\0'
PENDING=('reserved','dispatched','indeterminate')


class ReconciliationRequiredV3(EffectV3Error):pass


@dataclass(frozen=True)
class ObjectAuthorityScopeV3:
    template:ActionContextV1
    resources:tuple[bytes,...]
    budget_limit:int
    max_action_cost:int
    fencing_token:int

    def validate(self):
        if type(self.template) is not ActionContextV1:raise EffectV3Error('typed authority template required')
        self.template.validate()
        if type(self.resources) is not tuple or not 1<=len(self.resources)<=64:
            raise EffectV3Error('bounded exact resource scope required')
        for value in self.resources:hash32(value,'resource')
        if tuple(sorted(set(self.resources)))!=self.resources:raise EffectV3Error('resources must be unique and sorted')
        integer(self.budget_limit,positive=True);integer(self.max_action_cost);integer(self.fencing_token,positive=True)
        c=self.template
        for value in (c.budget,c.issued_at,c.expires_at,c.authority_epoch,c.policy_version):integer(value)
        if not self.max_action_cost<=self.budget_limit<=c.budget:raise EffectV3Error('scope widens governed budget')
        if c.capabilities!=1 or c.model_id!=b'\0'*32 or c.expires_at-c.issued_at>MAX_ADMISSION_SECONDS:
            raise EffectV3Error('unsupported authority workload/lifetime')
        ObjectFenceV3.from_context(c,self.fencing_token)

    @property
    def scope_id(self):
        self.validate()
        return ObjectFenceV3.from_context(self.template,self.fencing_token).scope_id

    def canonical_bytes(self):
        self.validate()
        return SCOPE_DOMAIN+self.template.canonical_bytes()+b''.join(word(v) for v in (
            self.budget_limit,self.max_action_cost,self.fencing_token,len(self.resources)))+b''.join(self.resources)

    @classmethod
    def from_bytes(cls,raw):
        start=len(SCOPE_DOMAIN)+ACTION_SIZE
        if type(raw) is not bytes or not raw.startswith(SCOPE_DOMAIN) or not start+160<=len(raw)<=start+128+64*32:
            raise EffectV3Error('unsupported authority scope encoding')
        values=[int.from_bytes(raw[start+i*32:start+(i+1)*32],'big') for i in range(4)]
        if len(raw)!=start+128+values[3]*32:raise EffectV3Error('noncanonical resource count')
        result=cls(ActionContextV1.from_bytes(raw[len(SCOPE_DOMAIN):start]),
            tuple(raw[i:i+32] for i in range(start+128,len(raw),32)),*values[:3])
        if result.canonical_bytes()!=raw:raise EffectV3Error('noncanonical authority scope')
        return result

    def permits(self,proposal,now=None):
        self.validate();proposal.validate()
        c,t=proposal.context,self.template
        for name in HASH_FIELDS:
            if name not in ('action_hash','input_hash','nonce') and getattr(c,name)!=getattr(t,name):
                raise EffectV3Error('proposal exceeds authority binding: '+name)
        for name in ('root_scheme','authority_epoch','policy_version','capabilities','chain_id'):
            if getattr(c,name)!=getattr(t,name):raise EffectV3Error('proposal exceeds authority generation/domain')
        if (proposal.resource_id not in self.resources or proposal.fencing_token!=self.fencing_token or
                proposal.cost_units>self.max_action_cost or c.budget>self.budget_limit or
                c.issued_at<t.issued_at or c.expires_at>t.expires_at):
            raise EffectV3Error('proposal exceeds resource/cost/validity scope')
        if now is not None:proposal.require_current(now)


class CurrentAuthorityPolicyV1(CurrentActionPolicyV1):
    """Authenticate responsible-host grants, current action policy and cutover.

    Reviewed host/custody/finality and old-writer inventory are entry inputs. Test
    subclasses are fixtures. This interface is not an implemented policy backend.
    """
    @abstractmethod
    def assert_scope_allowed(self,scope:ObjectAuthorityScopeV3,now:int)->None:raise NotImplementedError
    @abstractmethod
    def assert_fence_allowed(self,scope:ObjectAuthorityScopeV3,fence:ObjectFenceV3,now:int)->None:raise NotImplementedError


@dataclass(frozen=True)
class AuthorityStateV3:
    scope:ObjectAuthorityScopeV3
    status:str
    reserved:int
    spent:int
    fence:ObjectFenceV3
    update:SignedEffectReceiptV3
    ack:SignedEffectReceiptV3|None


@dataclass(frozen=True)
class OperationStateV3:
    proposal:ObjectEffectV3
    admission:SignedEffectReceiptV3
    status:str
    result:SignedEffectReceiptV3|None


class PostgresEffectAuthorityV3(ImmutableRuntimeConfiguration):
    _database_class=PostgresAuthorityDatabaseV3
    _policy_class=CurrentAuthorityPolicyV1
    _configuration=staticmethod(authority_configuration)
    _scope_table=SCOPES
    _operation_table=OPERATIONS
    _immutable_runtime_fields=frozenset({'runtime_policy','database','identity','_signer','_policy','_clock'})

    def __init__(self,database,identity,authority_signer,policy,*,clock=lambda:time.time_ns()//1_000_000_000):
        self.runtime_policy=load_runtime_policy()
        # A policy interface/fixture is not a qualified current-host backend.
        # This unactivated protocol has no live factory or override.
        if self.runtime_policy.is_live:
            raise RuntimeConfigurationError("Unqualified effect authority candidate cannot run in live mode")
        if type(identity) is not ObjectProviderIdentityV3 or type(database) is not self._database_class:
            raise EffectV3Error('explicit V3 authority identity/database required')
        if database.configuration_hash!=self._configuration(identity):raise EffectV3Error('authority database identity mismatch')
        if type(authority_signer) is not ReceiptSignerV3 or authority_signer.verifier()!=identity.authority:
            raise EffectV3Error('configured authority signer required')
        if not isinstance(policy,self._policy_class) or not callable(clock):raise EffectV3Error('authenticated authority policy required')
        self.database=database;self.identity=identity;self._signer=authority_signer;self._policy=policy;self._clock=clock
        self._freeze_runtime_configuration()

    def _now(self):
        if load_runtime_policy()!=self.runtime_policy:raise RuntimeConfigurationError('authority runtime configuration changed')
        return integer(self._clock())

    def _target(self,proposal):
        if type(proposal) is not ObjectEffectV3:raise EffectV3Error('typed V3 proposal required')
        proposal.validate();c=proposal.context;i=self.identity
        if (c.provider_id,c.runtime_id,c.target,c.host_domain,c.chain_id)!=(i.provider_id,i.runtime_id,i.target,i.host_domain,i.chain_id):
            raise EffectV3Error('proposal targets another authority/provider binding')

    def _scope_policy(self,scope,now):
        scope.validate()
        c=scope.template;i=self.identity
        if (c.provider_id,c.runtime_id,c.target,c.host_domain,c.chain_id)!=(i.provider_id,i.runtime_id,i.target,i.host_domain,i.chain_id):
            raise EffectV3Error('scope targets another authority/provider')
        if not c.issued_at<=now<c.expires_at:raise EffectV3Error('scope is not current')
        if self._policy.assert_scope_allowed(scope,now) is not None:raise EffectV3Error('unsupported scope policy decision')
        current=self._now()
        if current<now or not c.issued_at<=current<c.expires_at:
            raise EffectV3Error('scope expired or clock moved backwards during policy validation')
        return current

    def _action_policy(self,proposal,now):
        proposal.require_current(now)
        if self._policy.assert_allowed(proposal,now) is not None:raise EffectV3Error('unsupported action policy decision')
        current=self._now()
        if current<now:raise EffectV3Error('clock moved backwards during action policy validation')
        proposal.require_current(current)
        return current

    @staticmethod
    def _lock(cursor,scope_id):
        cursor.execute('SELECT pg_advisory_xact_lock(%s)',(int.from_bytes(hash32(scope_id)[:8],'big',signed=True),))

    def _state(self,cursor,scope_id,now):
        cursor.execute(f'''SELECT scope_bytes,status,budget_limit,budget_reserved,budget_spent,
            fence_bytes,update_bytes,ack_bytes FROM {self._scope_table} WHERE scope_id=%s FOR UPDATE''',(scope_id,))
        row=cursor.fetchone()
        return self._decode_state(scope_id,row,now)

    def _decode_state(self,scope_id,row,now):
        if row is None:return None
        scope=ObjectAuthorityScopeV3.from_bytes(bytes(row[0]))
        if scope.scope_id!=scope_id or row[1] not in ('installing','active','draining','revoked'):
            raise EffectV3Error('persisted authority scope/status mismatch')
        limit,reserved,spent=(integer(v) for v in row[2:5])
        if limit!=scope.budget_limit or spent>limit or reserved>limit-spent:raise EffectV3Error('inconsistent authority budget')
        fence=ObjectFenceV3.from_bytes(bytes(row[5]));update=SignedEffectReceiptV3.from_bytes(bytes(row[6]))
        verify_fence_update(fence,update,self.identity.authority,fence.issued_at)
        if fence.scope_id!=scope_id or fence.provider_id!=self.identity.provider_id or fence.issued_at>now:
            raise EffectV3Error('persisted fence identity/time mismatch')
        initial=ObjectFenceV3.from_context(scope.template,scope.fencing_token)
        if row[1] in ('installing','active') and fence!=initial:raise EffectV3Error('active fence differs from grant')
        if row[1] in ('draining','revoked') and (fence.authority_epoch<=initial.authority_epoch or
                fence.fencing_token<=initial.fencing_token or fence.policy_version<initial.policy_version):
            raise EffectV3Error('revocation fence does not cut off the old grant')
        ack=SignedEffectReceiptV3.from_bytes(bytes(row[7])) if row[7] is not None else None
        if ack is not None:verify_fence_ack(fence,update,ack,self.identity.provider,now,authority=self.identity.authority)
        if row[1] in ('active','revoked') and ack is None:raise EffectV3Error('authority lacks provider acknowledgement')
        return AuthorityStateV3(scope,row[1],reserved,spent,fence,update,ack)

    def _operation(self,cursor,proposal,state,now):
        cursor.execute(f'''SELECT proposal_bytes,admission_bytes,cost_units,status,result_bytes,scope_id,
            proposal_digest FROM {self._operation_table} WHERE operation_id=%s''',(proposal.operation_id,))
        row=cursor.fetchone()
        return self._decode_operation(proposal,state,now,row)

    def _decode_operation(self,proposal,state,now,row):
        if row is None:return None
        if (bytes(row[0])!=proposal.canonical_bytes() or bytes(row[5])!=state.scope.scope_id or
                bytes(row[6])!=proposal.digest or integer(row[2])!=proposal.cost_units):
            raise EffectV3Error('logical operation cannot be rebound')
        state.scope.permits(proposal)
        admission=SignedEffectReceiptV3.from_bytes(bytes(row[1]))
        verify_admitted_obligation(proposal,admission,self.identity.authority,now)
        status=row[3]
        if status not in (*PENDING,'committed','rejected'):raise EffectV3Error('invalid operation state')
        if (row[4] is not None)!=(status in ('committed','rejected')):raise EffectV3Error('operation/result lifecycle mismatch')
        result=SignedEffectReceiptV3.from_bytes(bytes(row[4])) if row[4] is not None else None
        if status=='committed':verify_effect(proposal,admission,result,self.identity.provider,now,authority=self.identity.authority)
        if status=='rejected':
            if state.ack is None:raise EffectV3Error('rejected operation has no cutover acknowledgement')
            verify_fenced_absence(proposal,state.fence,state.update,state.ack,result,self.identity.provider,now,authority=self.identity.authority)
        return OperationStateV3(proposal,admission,status,result)

    def prepare_scope(self,scope):
        now=self._now();self._scope_policy(scope,now)
        with self.database.transaction() as cursor:
            self._lock(cursor,scope.scope_id)
            if self._state(cursor,scope.scope_id,now) is not None:raise ReconciliationRequiredV3('existing scope requires explicit reconciliation; no reissue')
            now=self._now();self._scope_policy(scope,now)
            fence=ObjectFenceV3.from_context(scope.template,scope.fencing_token)
            update=sign_receipt(self._signer,purpose=2,subject=fence.digest,provider=fence.provider_id,
                epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
                issued_at=fence.issued_at,expires_at=fence.expires_at)
            cursor.execute(f'''INSERT INTO {self._scope_table}(scope_id,scope_bytes,status,budget_limit,budget_reserved,
                budget_spent,fence_bytes,update_bytes,ack_bytes) VALUES(%s,%s,'installing',%s,0,0,%s,%s,NULL)''',
                (scope.scope_id,scope.canonical_bytes(),scope.budget_limit,fence.canonical_bytes(),update.canonical_bytes()))
        return update

    def read_scope(self,scope_id):
        now=self._now();hash32(scope_id)
        with self.database.transaction() as cursor:return self._state(cursor,scope_id,now)

    def activate_scope(self,scope_id,ack):
        now=self._now()
        with self.database.transaction() as cursor:
            self._lock(cursor,scope_id);state=self._state(cursor,scope_id,now)
            if state is None or state.status!='installing':raise EffectV3Error('scope is not installing')
            self._scope_policy(state.scope,self._now())
            verify_fence_ack(state.fence,state.update,ack,self.identity.provider,now,authority=self.identity.authority)
            cursor.execute(f"UPDATE {self._scope_table} SET status='active',ack_bytes=%s WHERE scope_id=%s",(ack.canonical_bytes(),scope_id))

    def _current_state(self,cursor,proposal,now):
        scope_id=ObjectFenceV3.from_context(proposal.context,proposal.fencing_token).scope_id
        self._lock(cursor,scope_id);state=self._state(cursor,scope_id,now)
        if state is None or state.status!='active':raise EffectV3Error('authority is absent, installing, draining or revoked')
        state.scope.permits(proposal,now)
        self._scope_policy(state.scope,now);self._action_policy(proposal,now)
        return state

    def reserve(self,proposal):
        self._target(proposal);now=self._now();self._action_policy(proposal,now)
        with self.database.transaction() as cursor:
            state=self._current_state(cursor,proposal,self._now())
            old=self._operation(cursor,proposal,state,self._now())
            if old is not None:
                if old.status!='reserved':raise ReconciliationRequiredV3('operation already dispatched or terminal; lookup only')
                verify_admission(proposal,old.admission,self.identity.authority,self._now())
                return old.admission
            cost=proposal.cost_units
            if cost>state.scope.budget_limit-state.spent-state.reserved:raise EffectV3Error('shared authority budget exhausted')
            now=self._action_policy(proposal,self._now())
            c=proposal.context
            admission=sign_receipt(self._signer,purpose=1,subject=proposal.digest,provider=c.provider_id,
                epoch=c.authority_epoch,policy=c.policy_version,fence=proposal.fencing_token,
                issued_at=now,expires_at=c.expires_at)
            self._insert_operation(cursor,proposal,state,admission)
            cursor.execute(f'UPDATE {self._scope_table} SET budget_reserved=budget_reserved+%s WHERE scope_id=%s',(cost,state.scope.scope_id))
        return admission

    def _insert_operation(self,cursor,proposal,state,admission):
        c=proposal.context;cost=proposal.cost_units
        cursor.execute(f'''INSERT INTO {self._operation_table}(operation_id,scope_id,proposal_bytes,proposal_digest,
            admission_bytes,admission_digest,nonce,cost_units,status,result_bytes)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'reserved',NULL)''',
            (proposal.operation_id,state.scope.scope_id,proposal.canonical_bytes(),proposal.digest,
             admission.canonical_bytes(),admission.digest,c.nonce,cost))

    def claim_dispatch(self,proposal,admission):
        self._target(proposal);now=self._now();verify_admission(proposal,admission,self.identity.authority,now)
        self._action_policy(proposal,now)
        with self.database.transaction() as cursor:
            state=self._current_state(cursor,proposal,self._now());old=self._operation(cursor,proposal,state,self._now())
            if old is None or old.admission!=admission or old.status!='reserved':
                raise ReconciliationRequiredV3('dispatch already claimed or obligation differs; lookup only')
            self._action_policy(proposal,self._now())
            cursor.execute(f"UPDATE {self._operation_table} SET status='dispatched' WHERE operation_id=%s",(proposal.operation_id,))

    def read_operation(self,proposal):
        self._target(proposal);now=self._now()
        scope_id=ObjectFenceV3.from_context(proposal.context,proposal.fencing_token).scope_id
        with self.database.transaction() as cursor:
            state=self._state(cursor,scope_id,now)
            return None if state is None else self._operation(cursor,proposal,state,now)

    def mark_indeterminate(self,proposal):
        self._target(proposal);now=self._now()
        scope_id=ObjectFenceV3.from_context(proposal.context,proposal.fencing_token).scope_id
        with self.database.transaction() as cursor:
            self._lock(cursor,scope_id);state=self._state(cursor,scope_id,now)
            if state is None:raise EffectV3Error('missing authority obligation')
            old=self._operation(cursor,proposal,state,now)
            if old is None:raise EffectV3Error('missing authority operation')
            if old.status in PENDING:
                cursor.execute(f"UPDATE {self._operation_table} SET status='indeterminate' WHERE operation_id=%s",(proposal.operation_id,))

    def accept_effect(self,proposal,admission,result):
        self._target(proposal);now=self._now()
        verify_effect(proposal,admission,result,self.identity.provider,now,authority=self.identity.authority)
        scope_id=ObjectFenceV3.from_context(proposal.context,proposal.fencing_token).scope_id
        with self.database.transaction() as cursor:
            self._lock(cursor,scope_id);state=self._state(cursor,scope_id,now)
            if state is None:raise EffectV3Error('missing authority obligation')
            old=self._operation(cursor,proposal,state,now)
            if old is None or old.admission!=admission:raise EffectV3Error('result differs from retained admission')
            if old.status=='committed':
                if old.result!=result:raise EffectV3Error('conflicting committed evidence')
                return old.result
            if old.status not in PENDING or state.reserved<proposal.cost_units:raise EffectV3Error('operation is not reconcilable')
            cursor.execute(f'''UPDATE {self._scope_table} SET budget_reserved=budget_reserved-%s,
                budget_spent=budget_spent+%s WHERE scope_id=%s''',(proposal.cost_units,proposal.cost_units,scope_id))
            cursor.execute(f"UPDATE {self._operation_table} SET status='committed',result_bytes=%s WHERE operation_id=%s",(result.canonical_bytes(),proposal.operation_id))
        return result

    def begin_revocation(self,scope_id,fence):
        return self._begin_cutover(scope_id,fence,refresh=False)

    def refresh_unacknowledged_cutover(self,scope_id,fence):
        """New, strictly stronger update; never resend an uncertain old update.

        No acknowledged cutover or terminal absence is replaced. An unreachable
        provider still blocks completion; refresh creates no dispatch authority.
        """
        return self._begin_cutover(scope_id,fence,refresh=True)

    def _begin_cutover(self,scope_id,fence,*,refresh):
        now=self._now()
        if type(fence) is not ObjectFenceV3 or fence.scope_id!=scope_id:raise EffectV3Error('typed matching cutover fence required')
        if not fence.issued_at<=now<fence.expires_at:raise EffectV3Error('cutover fence is not current')
        with self.database.transaction() as cursor:
            self._lock(cursor,scope_id);state=self._state(cursor,scope_id,now)
            allowed=(state is not None and state.status=='draining' and state.ack is None) if refresh else (
                state is not None and state.status in ('installing','active'))
            if not allowed:raise ReconciliationRequiredV3('cutover cannot replace an acknowledged/existing lifecycle')
            old=state.fence
            if (fence.provider_id!=old.provider_id or fence.authority_epoch<=old.authority_epoch or
                    fence.policy_version<old.policy_version or fence.fencing_token<=old.fencing_token or
                    fence.policy_root!=old.policy_root and fence.policy_version==old.policy_version):
                raise EffectV3Error('cutover must advance the same provider authority/fence/policy')
            if self._policy.assert_fence_allowed(state.scope,fence,self._now()) is not None:
                raise EffectV3Error('unsupported cutover policy decision')
            now=self._now()
            if not fence.issued_at<=now<fence.expires_at:raise EffectV3Error('cutover expired before signing')
            update=sign_receipt(self._signer,purpose=2,subject=fence.digest,provider=fence.provider_id,
                epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
                issued_at=fence.issued_at,expires_at=fence.expires_at)
            cursor.execute(f"UPDATE {self._scope_table} SET status='draining',fence_bytes=%s,update_bytes=%s,ack_bytes=NULL WHERE scope_id=%s",
                (fence.canonical_bytes(),update.canonical_bytes(),scope_id))
        return update

    def record_fence_ack(self,scope_id,fence,update,ack):
        now=self._now();verify_fence_ack(fence,update,ack,self.identity.provider,now,authority=self.identity.authority)
        with self.database.transaction() as cursor:
            self._lock(cursor,scope_id);state=self._state(cursor,scope_id,now)
            if state is None or state.status!='draining' or (state.fence,state.update)!=(fence,update):
                raise EffectV3Error('acknowledgement differs from retained cutover')
            if state.ack is not None and state.ack!=ack:raise EffectV3Error('conflicting provider acknowledgement')
            cursor.execute(f'UPDATE {self._scope_table} SET ack_bytes=%s WHERE scope_id=%s',(ack.canonical_bytes(),scope_id))

    def release_fenced_absence(self,proposal,admission,fence,update,ack,absence):
        self._target(proposal);now=self._now()
        verify_admitted_obligation(proposal,admission,self.identity.authority,now)
        verify_fenced_absence(proposal,fence,update,ack,absence,self.identity.provider,now,authority=self.identity.authority)
        scope_id=ObjectFenceV3.from_context(proposal.context,proposal.fencing_token).scope_id
        with self.database.transaction() as cursor:
            self._lock(cursor,scope_id);state=self._state(cursor,scope_id,now)
            if state is None or state.status!='draining' or (state.fence,state.update,state.ack)!=(fence,update,ack):
                raise EffectV3Error('absence differs from acknowledged retained cutover')
            old=self._operation(cursor,proposal,state,now)
            if old is None or old.admission!=admission:raise EffectV3Error('absence differs from retained obligation')
            if old.status=='rejected':
                if old.result!=absence:raise EffectV3Error('conflicting terminal absence evidence')
                return
            if old.status not in PENDING or state.reserved<proposal.cost_units:raise EffectV3Error('committed/inconsistent operation cannot refund')
            cursor.execute(f'UPDATE {self._scope_table} SET budget_reserved=budget_reserved-%s WHERE scope_id=%s',(proposal.cost_units,scope_id))
            cursor.execute(f"UPDATE {self._operation_table} SET status='rejected',result_bytes=%s WHERE operation_id=%s",(absence.canonical_bytes(),proposal.operation_id))

    def complete_revocation(self,scope_id):
        now=self._now()
        with self.database.transaction() as cursor:
            self._lock(cursor,scope_id);state=self._state(cursor,scope_id,now)
            if state is None or state.status!='draining' or state.ack is None:raise EffectV3Error('cutover lacks retained provider acknowledgement')
            cursor.execute(f"SELECT COUNT(*) FROM {self._operation_table} WHERE scope_id=%s AND status IN ('reserved','dispatched','indeterminate')",(scope_id,))
            row=cursor.fetchone()
            if row is None or row[0]!=0 or state.reserved!=0:raise ReconciliationRequiredV3('unresolved obligations prevent authority migration')
            cursor.execute(f"UPDATE {self._scope_table} SET status='revoked' WHERE scope_id=%s",(scope_id,))
