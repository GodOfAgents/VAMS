"""Explicit unregistered V3 orchestration; indeterminate effects are lookup-only.

Direct transport is a trusted-process seam, not authenticated inter-host transport
or independent observation. No retries, provider switching or legacy promotion.
"""
from abc import ABC,abstractmethod
from dataclasses import dataclass
import hashlib

from neuron.effect_authority_v3 import PostgresEffectAuthorityV3,ReconciliationRequiredV3
from neuron.effect_provider_v3 import PostgresObjectProviderV3
from neuron.effect_protocol_v3 import EffectV3Error,ObjectFenceV3,MAX_CONTENT_BYTES


class ObjectEffectTransportV3(ABC):
    @property
    @abstractmethod
    def identity(self):raise NotImplementedError
    @abstractmethod
    def commit(self,proposal,admission,content):raise NotImplementedError
    @abstractmethod
    def lookup(self,proposal,admission):raise NotImplementedError
    @abstractmethod
    def advance_fence(self,fence,update):raise NotImplementedError
    @abstractmethod
    def lookup_fence(self,fence,update):raise NotImplementedError
    @abstractmethod
    def prove_fenced_absence(self,proposal,fence,update,ack):raise NotImplementedError


@dataclass(frozen=True)
class DirectObjectProviderTransportV3(ObjectEffectTransportV3):
    provider:PostgresObjectProviderV3
    def __post_init__(self):
        if type(self.provider) is not PostgresObjectProviderV3:raise EffectV3Error('typed V3 provider required')
    @property
    def identity(self):return self.provider.identity
    def commit(self,proposal,admission,content):return self.provider.commit(proposal,admission,content)
    def lookup(self,proposal,admission):return self.provider.lookup(proposal,admission)
    def advance_fence(self,fence,update):return self.provider.advance_fence(fence,update)
    def lookup_fence(self,fence,update):return self.provider.lookup_fence(fence,update)
    def prove_fenced_absence(self,proposal,fence,update,ack):return self.provider.prove_fenced_absence(proposal,fence,update,ack)


@dataclass(frozen=True)
class ObjectEffectCoordinatorV3:
    _authority_class=PostgresEffectAuthorityV3
    authority:PostgresEffectAuthorityV3
    transport:ObjectEffectTransportV3
    def __post_init__(self):
        if type(self.authority) is not self._authority_class or not isinstance(self.transport,ObjectEffectTransportV3):
            raise EffectV3Error('explicit V3 authority/transport composition required')
        if self.transport.identity!=self.authority.identity:raise EffectV3Error('transport identity differs from authority configuration')

    def _mark_unknown(self,proposal):
        try:self.authority.mark_indeterminate(proposal)
        except Exception:pass  # Keep lookup/reconciliation possible during authority outage.

    def _accept(self,proposal,admission,result):
        try:return self.authority.accept_effect(proposal,admission,result)
        except Exception:
            self._mark_unknown(proposal)
            raise

    def execute(self,proposal,content):
        proposal.validate()
        if type(content) is not bytes or len(content)>MAX_CONTENT_BYTES or hashlib.sha256(content).digest()!=proposal.context.input_hash:
            raise EffectV3Error('content differs from exact admitted effect')
        admission=self.authority.reserve(proposal)
        # An uncertain dispatch-claim commit cannot invoke the provider. A new
        # attempt must use reconcile(), which never invokes commit().
        self.authority.claim_dispatch(proposal,admission)
        try:result=self.transport.commit(proposal,admission,content)
        except Exception:
            self._mark_unknown(proposal)
            try:result=self.transport.lookup(proposal,admission)
            except Exception:raise ReconciliationRequiredV3('provider outcome unavailable; obligation retained') from None
            if result is None:raise ReconciliationRequiredV3('provider outcome indeterminate; obligation retained') from None
        return self._accept(proposal,admission,result)

    def reconcile(self,proposal):
        operation=self.authority.read_operation(proposal)
        if operation is None:raise ReconciliationRequiredV3('no retained obligation; never infer authority from a timeout')
        if operation.status=='committed':return operation.result
        if operation.status=='rejected':raise EffectV3Error('operation already closed by authenticated fenced absence')
        try:result=self.transport.lookup(proposal,operation.admission)
        except Exception:raise ReconciliationRequiredV3('provider unreachable; obligation retained') from None
        if result is None:raise ReconciliationRequiredV3('no authenticated execution evidence; obligation retained')
        return self._accept(proposal,operation.admission,result)

    def install(self,scope):
        update=self.authority.prepare_scope(scope)
        fence=ObjectFenceV3.from_context(scope.template,scope.fencing_token)
        try:ack=self.transport.advance_fence(fence,update)
        except Exception:raise ReconciliationRequiredV3('initial fence outcome unknown; lookup acknowledgement before proceeding') from None
        self.authority.activate_scope(scope.scope_id,ack)
        return ack

    def start_cutover(self,scope_id,fence):
        update=self.authority.begin_revocation(scope_id,fence)
        try:ack=self.transport.advance_fence(fence,update)
        except Exception:raise ReconciliationRequiredV3('old provider fencing unavailable; cutover remains draining') from None
        self.authority.record_fence_ack(scope_id,fence,update,ack)
        return ack

    def reconcile_cutover(self,scope_id):
        state=self.authority.read_scope(scope_id)
        if state is None:raise ReconciliationRequiredV3('no retained fence update')
        if state.ack is not None:return state.ack
        try:ack=self.transport.lookup_fence(state.fence,state.update)
        except Exception:raise ReconciliationRequiredV3('old provider unreachable; authority cannot migrate') from None
        if ack is None:raise ReconciliationRequiredV3('no acknowledged provider fence; authority cannot migrate')
        if state.status=='installing':self.authority.activate_scope(scope_id,ack)
        elif state.status=='draining':self.authority.record_fence_ack(scope_id,state.fence,state.update,ack)
        else:raise EffectV3Error('unexpected fence lifecycle')
        return ack

    def reconcile_absence(self,proposal):
        operation=self.authority.read_operation(proposal)
        if operation is None or operation.status=='committed':raise EffectV3Error('missing or completed operation cannot refund by absence')
        if operation.status=='rejected':return operation.result
        scope_id=ObjectFenceV3.from_context(proposal.context,proposal.fencing_token).scope_id
        state=self.authority.read_scope(scope_id)
        if state is None or state.status!='draining' or state.ack is None:
            raise ReconciliationRequiredV3('absence requires an acknowledged retained cutover')
        absence=self.transport.prove_fenced_absence(proposal,state.fence,state.update,state.ack)
        self.authority.release_fenced_absence(proposal,operation.admission,state.fence,state.update,state.ack,absence)
        return absence
