"""Public synthetic ABI fixtures; no authentic policy, signing or effects."""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


class ObjectPolicyCallPresenceTests(unittest.TestCase):
    def test_typed_policy_call_producer_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('neuron.object_policy_calls_v1'),
            'The typed object-policy call producer is missing')


def fixtures(resources=2,depth=1,maximum=False):
    from neuron.action_context import ActionContextV1
    from neuron.effect_authority_v3 import ObjectAuthorityScopeV3
    from neuron.effect_protocol_v3 import ObjectEffectV3
    from neuron.effect_provider_v3 import ObjectProviderIdentityV3
    from neuron.object_grant_v1 import ObjectGrantDomainV1,GovernedObjectGrantV1,MAX_INTEGER
    from neuron.signed_receipts import ReceiptVerifierV3
    from neuron.object_policy_calls_v1 import ObjectGrantWitnessV1,ObjectPolicyCallsV1
    # Published curve generator and its negation are public verification fixtures.
    x=bytes.fromhex('79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798')
    y=bytes.fromhex('483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8')
    neg=((1<<256)-(1<<32)-977-int.from_bytes(y,'big')).to_bytes(32,'big')
    a=ReceiptVerifierV3(b'\x04'+x+y); b=ReceiptVerifierV3(b'\x04'+x+neg)
    domain=ObjectGrantDomainV1(b'\0'*12+b'\x22'*20,80002,b'\x05'*32,b'\x0d'*32)
    identity=ObjectProviderIdentityV3(b'\x02'*32,b'\x05'*32,b'\x03'*32,b'\0'*12+b'\x22'*20,80002,a,b)
    limit=MAX_INTEGER if maximum else 10
    values=tuple(i.to_bytes(32,'big') for i in range(1,resources+1))
    grant=GovernedObjectGrantV1(b'\0'*12+b'\x11'*20,identity.provider_id,identity.runtime_id,b'\x06'*32,
        b'\x07'*32,identity.target,a.issuer_id,b.issuer_id,b'\xc3'*32,limit,limit if maximum else 4,
        600,1000,2000,values)
    siblings=tuple(bytes([i+50])*32 for i in range(depth)); index=(1<<depth)-1
    # Structurally canonical, deliberately NOT valid actor consent.
    consent=(1).to_bytes(32,'big')+(2).to_bytes(32,'big')+b'\x1b'
    witness=ObjectGrantWitnessV1(grant,consent,siblings,index)
    from neuron.object_grant_v1 import membership_root
    root=membership_root(grant.leaf(domain),siblings,index)
    context=ActionContextV1(grant.actor_root,identity.provider_id,identity.runtime_id,b'\0'*32,
        domain.host_domain,grant.workflow_id,grant.intent_id,b'\x08'*32,hashlib.sha256(b'fixture-object').digest(),
        root,identity.target,b'\x0c'*32,domain.budget_unit,1,3,7,1,limit,1000,1100,80002)
    p=ObjectEffectV3(context,values[0],limit if maximum else 3,MAX_INTEGER if maximum else 9)
    p=replace(p,context=replace(context,action_hash=p.action_hash))
    scope=ObjectAuthorityScopeV3(p.context,values,limit,grant.max_action_cost,p.fencing_token)
    return ObjectPolicyCallsV1(domain,identity),p,scope,witness


class ObjectPolicyCallCodecTests(unittest.TestCase):
    def setUp(self):self.calls,self.proposal,self.scope,self.witness=fixtures()

    def test_frozen_full_call_bytes_and_existing_context_scope_digests(self):
        from neuron.object_policy_calls_v1 import OBJECT_SELECTOR,SCOPE_SELECTOR
        path=Path(__file__).parents[2]/'docs/remediation/repair_20261101/object-policy-calls-v1.json'
        rows=json.loads(path.read_text())['cases']
        for row,arguments in zip(rows,((1,0,False),(2,1,False),(64,32,True)),strict=True):
            c,p,s,w=fixtures(*arguments)
            self.assertEqual(c.object_call(p,w).calldata.hex(),row['object_call'])
            self.assertEqual(c.scope_call(s,w).calldata.hex(),row['scope_call'])
            self.assertEqual(p.context.digest.hex(),row['context_digest'])
            self.assertEqual(hashlib.sha256(s.canonical_bytes()).hexdigest(),row['scope_digest'])
            self.assertEqual(w.grant.digest(c.domain).hex(),row['grant_digest'])
            self.assertEqual(c.object_call(p,w).domain,c.domain)
        self.assertEqual(OBJECT_SELECTOR.hex(),'c76d3f1f'); self.assertEqual(SCOPE_SELECTOR.hex(),'c6a79e78')

    def test_both_entrypoints_require_their_exact_typed_input(self):
        for call in (self.calls.object_call,self.calls.scope_call):
            for value in (None,{},self.proposal.context,b''):
                with self.assertRaises(ValueError):call(value,self.witness)

    def test_witness_cannot_supply_its_own_issuer_pair(self):
        for name in ('authority_issuer','provider_issuer'):
            g=replace(self.witness.grant,**{name:b'x'*32})
            for call,value in ((self.calls.object_call,self.proposal),(self.calls.scope_call,self.scope)):
                with self.assertRaises(ValueError):call(value,replace(self.witness,grant=g))

    def test_configuration_is_typed_and_domains_agree(self):
        from neuron.object_policy_calls_v1 import ObjectPolicyCallsV1
        for domain,identity in (({},self.calls.identity),(self.calls.domain,{}),
                (replace(self.calls.domain,chain_id=1),self.calls.identity),
                (replace(self.calls.domain,host_domain=b'x'*32),self.calls.identity),
                (replace(self.calls.domain,policy_contract=b'x'*32),self.calls.identity)):
            with self.assertRaises(ValueError):ObjectPolicyCallsV1(domain,identity)

    def test_equal_configured_issuers_reject(self):
        from neuron.object_policy_calls_v1 import ObjectPolicyCallsV1
        with self.assertRaises(ValueError):ObjectPolicyCallsV1(self.calls.domain,
            replace(self.calls.identity,provider=self.calls.identity.authority))

    def test_context_cannot_cross_configured_runtime_domain(self):
        for name in ('provider_id','runtime_id','target','host_domain','budget_unit','chain_id'):
            value=1 if name=='chain_id' else b'x'*32
            c=replace(self.proposal.context,**{name:value})
            p=replace(self.proposal,context=c); p=replace(p,context=replace(c,action_hash=p.action_hash))
            with self.assertRaises(ValueError):self.calls.object_call(p,self.witness)
            with self.assertRaises(ValueError):self.calls.scope_call(replace(self.scope,template=c),self.witness)

    def test_untyped_or_fabricated_witness_shape_rejects(self):
        for value in ({},None,replace(self.witness,grant={})): 
            with self.assertRaises(ValueError):self.calls.object_call(self.proposal,value)

    def test_consent_length_type_low_s_r_and_v_are_structural_only(self):
        from neuron.signed_receipts import ORDER
        values=(None,'x'*65,bytearray(self.witness.consent),b'',b'x'*64,b'x'*66,
            b'\0'*32+self.witness.consent[32:],self.witness.consent[:32]+b'\0'*32+b'\x1b',
            self.witness.consent[:32]+(ORDER//2+1).to_bytes(32,'big')+b'\x1b',self.witness.consent[:-1]+b'\x00')
        for value in values:
            with self.assertRaises(ValueError):self.calls.object_call(self.proposal,replace(self.witness,consent=value))
        self.calls.object_call(self.proposal,self.witness) # Not proof that the consent verifies.

    def test_membership_shape_bounds(self):
        for siblings,index in (([],0),((b'\0'*32,),0),((b'x'*32,)*33,0),((b'x'*32,),2),
                ((b'x'*32,),True),((b'x'*32,),-1)):
            with self.assertRaises(ValueError):self.calls.object_call(self.proposal,
                replace(self.witness,siblings=siblings,index=index))

    def test_float_boolean_negative_and_overflow_integers_reject(self):
        for value in (True,1.0,-1,1<<256):
            for name in ('cost_units','fencing_token'):
                with self.assertRaises(ValueError):self.calls.object_call(replace(self.proposal,**{name:value}),self.witness)
            with self.assertRaises(ValueError):self.calls.scope_call(replace(self.scope,budget_limit=value),self.witness)

    def test_resource_arrays_reject_wrong_type_width_count_and_order(self):
        for values in ((),[],(b'x',),(b'\0'*32,),(b's'*32,b'r'*32),(b'r'*32,b'r'*32),tuple(i.to_bytes(32,'big') for i in range(1,66))):
            with self.assertRaises(ValueError):self.calls.scope_call(replace(self.scope,resources=values),self.witness)
            with self.assertRaises(ValueError):self.calls.object_call(self.proposal,
                replace(self.witness,grant=replace(self.witness.grant,resources=values)))

    def test_no_returned_boolean_or_policy_backend_interface(self):
        result=self.calls.object_call(self.proposal,self.witness)
        self.assertFalse(hasattr(self.calls,'assert_allowed'))
        self.assertFalse(hasattr(result,'allowed')); self.assertIs(type(result.calldata),bytes)

    def test_ordinary_repr_omits_consent_and_full_calldata(self):
        result=self.calls.object_call(self.proposal,self.witness)
        self.assertNotIn('calldata=',repr(result))
        self.assertNotIn('consent=',repr(self.witness))
        self.assertNotIn(repr(result.calldata),repr(result))


if __name__=='__main__':unittest.main()
