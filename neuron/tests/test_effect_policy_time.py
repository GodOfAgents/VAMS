"""Post-policy timing regressions; real fixture signatures, queued SQL, no PG."""
from unittest.mock import patch

from neuron.effect_authority_v3 import PostgresEffectAuthorityV3
from neuron.effect_authority_v4 import PostgresEffectAuthorityV4,CurrentRenewalPolicyV1,generation_id_v4
from neuron.effect_authority_store_v4 import PostgresAuthorityDatabaseV4,authority_configuration_v4
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_provider_v3 import PostgresObjectProviderV3
from neuron.effect_protocol_v3 import EffectV3Error
from neuron.tests.test_effect_authority_v3 import AuthorityFixture
from neuron.tests.test_effect_provider_v3 import ControlledConnection
from neuron.tests import test_effect_renewal_v4 as renewal_fixtures


class DelayedFixturePolicy(CurrentRenewalPolicyV1):
    """Explicit fixture controlling elapsed time, not authenticated host policy."""
    def __init__(self,fixture,name,call,time):
        self.fixture=fixture;self.name=name;self.call=call;self.time=time;self.counts={}
    def check(self,name):
        self.counts[name]=self.counts.get(name,0)+1
        if name==self.name and self.counts[name]==self.call:self.fixture.now=self.time
    def assert_allowed(self,p,now):return self.check('action')
    def assert_scope_allowed(self,s,now):return self.check('scope')
    def assert_fence_allowed(self,s,f,now):return self.check('fence')
    def assert_renewal_allowed(self,previous,successor,now):return self.check('renewal')


class EffectPolicyTimeTests(AuthorityFixture):
    def authority_with(self,policy):
        return PostgresEffectAuthorityV3(self.database,self.identity,self.authority_signer,policy,clock=lambda:self.now)

    def assert_denied_without_new_effect(self,call,connection,signer):
        result=None;denied=False
        with patch.object(signer,'sign',wraps=signer.sign) as signing:
            try:result=call()
            except EffectV3Error:denied=True
        self.assertEqual({'denied':denied,'result':result,'signs':signing.call_count,
            'mutations':len(self.mutations(connection))},
            {'denied':True,'result':None,'signs':0,'mutations':0})

    def test_slow_final_provider_policy_cannot_create_expired_effect(self):
        policy=DelayedFixturePolicy(self,'action',2,self.proposal.context.expires_at)
        database=PostgresEffectDatabaseV3('postgresql://synthetic-unused',self.identity.digest)
        provider=PostgresObjectProviderV3(database,self.identity,self.provider_signer,policy,clock=lambda:self.now)
        connection=ControlledConnection(self.identity,((self.fence.canonical_bytes(),),None))
        with patch.object(database,'_connect',return_value=connection):
            self.assert_denied_without_new_effect(lambda:provider.commit(self.proposal,self.admission,b'fixture-object'),connection,self.provider_signer)

    def test_slow_final_authority_policy_cannot_sign_expired_admission(self):
        authority=self.authority_with(DelayedFixturePolicy(self,'action',3,self.proposal.context.expires_at))
        connection=self.connection(self.state_row(reserved=0),None)
        with patch.object(self.database,'_connect',return_value=connection):
            self.assert_denied_without_new_effect(lambda:authority.reserve(self.proposal),connection,self.authority_signer)

    def test_slow_final_dispatch_policy_cannot_mark_expired_work_dispatched(self):
        authority=self.authority_with(DelayedFixturePolicy(self,'action',3,self.proposal.context.expires_at))
        connection=self.connection(self.state_row(),self.operation_row())
        with patch.object(self.database,'_connect',return_value=connection):
            self.assert_denied_without_new_effect(lambda:authority.claim_dispatch(self.proposal,self.admission),connection,self.authority_signer)

    def test_slow_scope_policy_cannot_persist_expired_grant(self):
        authority=self.authority_with(DelayedFixturePolicy(self,'scope',2,self.scope.template.expires_at))
        connection=self.connection(None)
        with patch.object(self.database,'_connect',return_value=connection):
            self.assert_denied_without_new_effect(lambda:authority.prepare_scope(self.scope),connection,self.authority_signer)

    def test_slow_renewal_scope_policy_cannot_sign_or_persist_expired_successor(self):
        _,scope=renewal_fixtures.RenewalV4Tests.successor(self)
        database=PostgresAuthorityDatabaseV4('postgresql://synthetic-unused',authority_configuration_v4(self.identity))
        authority=PostgresEffectAuthorityV4(database,self.identity,self.authority_signer,
            DelayedFixturePolicy(self,'scope',2,scope.template.expires_at),clock=lambda:self.now)
        f,u,a=self.cutover()
        closed=(self.scope.canonical_bytes(),'revoked',10,0,3,f.canonical_bytes(),u.canonical_bytes(),a.canonical_bytes(),
            generation_id_v4(self.scope),1,None,0,3)
        connection=renewal_fixtures.HistoryConnection(self.identity,(closed,(0,)))
        with patch.object(database,'_connect',return_value=connection):
            self.assert_denied_without_new_effect(lambda:authority.prepare_renewal(scope),connection,self.authority_signer)

    def test_backward_time_during_policy_cannot_create_admission(self):
        authority=self.authority_with(DelayedFixturePolicy(self,'action',3,self.now-1))
        connection=self.connection(self.state_row(reserved=0),None)
        with patch.object(self.database,'_connect',return_value=connection):
            self.assert_denied_without_new_effect(lambda:authority.reserve(self.proposal),connection,self.authority_signer)

    def test_valid_provider_delay_uses_fresh_receipt_time(self):
        policy=DelayedFixturePolicy(self,'action',2,self.now+1)
        database=PostgresEffectDatabaseV3('postgresql://synthetic-unused',self.identity.digest)
        provider=PostgresObjectProviderV3(database,self.identity,self.provider_signer,policy,clock=lambda:self.now)
        connection=ControlledConnection(self.identity,((self.fence.canonical_bytes(),),None))
        with patch.object(database,'_connect',return_value=connection):
            result=provider.commit(self.proposal,self.admission,b'fixture-object')
        self.assertEqual(result.receipt.issued_at,self.now)
        self.assertEqual(len(connection.inserts),1)

    def test_slow_final_provider_lookup_cannot_create_expired_effect(self):
        policy=DelayedFixturePolicy(self,'unused',1,self.now)
        database=PostgresEffectDatabaseV3('postgresql://synthetic-unused',self.identity.digest)
        provider=PostgresObjectProviderV3(database,self.identity,self.provider_signer,policy,clock=lambda:self.now)
        connection=ControlledConnection(self.identity,((self.fence.canonical_bytes(),),None))
        fetch=connection.fetchone
        def delayed_lookup():
            row=fetch()
            if row is None:self.now=self.proposal.context.expires_at
            return row
        with patch.object(database,'_connect',return_value=connection),patch.object(connection,'fetchone',side_effect=delayed_lookup):
            self.assert_denied_without_new_effect(lambda:provider.commit(self.proposal,self.admission,b'fixture-object'),connection,self.provider_signer)
