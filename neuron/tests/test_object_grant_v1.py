"""Pure public codec fixtures, not authentic host policy, custody or consent."""
from dataclasses import replace
import json
from pathlib import Path
import unittest
from neuron.object_grant_v1 import (
    GovernedObjectGrantV1,ObjectGrantDomainV1,ObjectGrantError,membership_root,MAX_INTEGER,
)

def fixture_domain():
    return ObjectGrantDomainV1(b'\0'*12+b'\x22'*20,80002,b'\x05'*32,b'\x0d'*32)

def fixture_grant():
    return GovernedObjectGrantV1(b'\0'*12+b'\x11'*20,b'\x02'*32,b'\x03'*32,b'\x06'*32,
        b'\x07'*32,b'\0'*12+b'\x22'*20,b'\xa1'*32,b'\xb2'*32,b'\xc3'*32,
        10,4,600,1000,2000,(b'r'*32,b's'*32))

class ObjectGrantCodecV1Tests(unittest.TestCase):
    def setUp(self):self.domain=fixture_domain();self.grant=fixture_grant()
    def test_frozen_exact_bytes_and_membership(self):
        vector=json.loads((Path(__file__).parents[2]/'docs/remediation/repair_20261030/object-grant-v1.json').read_text())
        self.assertEqual(self.grant.canonical_bytes(self.domain).hex(),vector['canonical_hex'])
        self.assertEqual(self.grant.digest(self.domain).hex(),vector['grant_digest'])
        self.assertEqual(self.grant.leaf(self.domain).hex(),vector['leaf'])
        for index in (0,1):
            self.assertEqual(membership_root(self.grant.leaf(self.domain),(b'\xd4'*32,),index).hex(),vector['positioned_roots'][str(index)])
    def test_actor_provider_runtime_workflow_intent_target_and_issuers_bind(self):
        for name in ('actor_root','provider_id','runtime_id','workflow_id','intent_id','target','authority_issuer','provider_issuer','nonce'):
            value=b'\0'*12+b'X'*20 if name=='actor_root' else b'X'*32
            self.assertNotEqual(replace(self.grant,**{name:value}).digest(self.domain),self.grant.digest(self.domain))
    def test_host_contract_chain_domain_and_units_bind(self):
        for name,value in (('policy_contract',b'\0'*12+b'X'*20),('chain_id',80003),('host_domain',b'X'*32),('budget_unit',b'X'*32)):
            self.assertNotEqual(self.grant.digest(replace(self.domain,**{name:value})),self.grant.digest(self.domain))
    def test_limits_window_and_resources_bind(self):
        for name,value in (('budget_limit',11),('max_action_cost',3),('max_scope_lifetime',599),
                           ('valid_after',999),('valid_until',2001),('resources',(b'r'*32,))):
            self.assertNotEqual(replace(self.grant,**{name:value}).digest(self.domain),self.grant.digest(self.domain))
    def test_issuer_role_reuse_and_noncanonical_actor_reject(self):
        for change in ({'provider_issuer':self.grant.authority_issuer},{'actor_root':b'X'*32}):
            with self.assertRaises(ObjectGrantError):replace(self.grant,**change).validate()
    def test_float_boolean_negative_and_overflow_reject(self):
        for value in (True,1.0,-1,MAX_INTEGER+1):
            with self.assertRaises(ObjectGrantError):replace(self.grant,budget_limit=value).validate()
    def test_zero_cost_and_maximum_integer_are_explicit(self):
        replace(self.grant,max_action_cost=0).validate()
        replace(self.grant,budget_limit=MAX_INTEGER,max_action_cost=MAX_INTEGER).validate()
        for change in ({'budget_limit':0},{'max_action_cost':11}):
            with self.assertRaises(ObjectGrantError):replace(self.grant,**change).validate()
    def test_resources_are_bounded_sorted_unique_nonzero(self):
        for resources in ((),(b's'*32,b'r'*32),(b'r'*32,b'r'*32),(b'\0'*32,),[b'r'*32],tuple(i.to_bytes(32,'big') for i in range(1,66))):
            with self.assertRaises(ObjectGrantError):replace(self.grant,resources=resources).validate()
        replace(self.grant,resources=tuple(i.to_bytes(32,'big') for i in range(1,65))).validate()
    def test_lifetime_and_window_boundaries(self):
        replace(self.grant,valid_until=self.grant.valid_after+86400).validate()
        for change in ({'max_scope_lifetime':0},{'max_scope_lifetime':601},{'valid_until':1000},{'valid_until':87401}):
            with self.assertRaises(ObjectGrantError):replace(self.grant,**change).validate()
    def test_missing_identities_and_untyped_domain_reject(self):
        with self.assertRaises(ObjectGrantError):replace(self.grant,nonce=b'\0'*32).validate()
        with self.assertRaises(ObjectGrantError):self.grant.digest({})
        with self.assertRaises(ObjectGrantError):self.grant.digest(replace(self.domain,policy_contract=b'X'*32))
    def test_single_leaf_requires_zero_index_and_no_alias(self):
        leaf=self.grant.leaf(self.domain);self.assertEqual(membership_root(leaf,(),0),leaf)
        for index in (1,-1,True):
            with self.assertRaises(ObjectGrantError):membership_root(leaf,(),index)
    def test_proof_position_depth_and_domain_are_bound(self):
        leaf=self.grant.leaf(self.domain)
        self.assertNotEqual(membership_root(leaf,(b'\xd4'*32,),0),membership_root(leaf,(b'\xd4'*32,),1))
        for siblings,index in (((b'\0'*32,),0),((b'\xd4'*32,)*33,0),((b'\xd4'*32,),2),([b'\xd4'*32],0)):
            with self.assertRaises(ObjectGrantError):membership_root(leaf,siblings,index)

if __name__=='__main__':unittest.main()
