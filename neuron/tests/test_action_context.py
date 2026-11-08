from dataclasses import replace
import json
from pathlib import Path
import unittest
from neuron.action_context import ActionContextV1, ActionContextError, WIRE_FIELDS

def sample():
    hashes={name:bytes([i+1])*32 for i,name in enumerate(WIRE_FIELDS[:13])}
    hashes['actor_root']=b'\0'*12+b'\x11'*20
    hashes['target']=b'\0'*12+b'\x22'*20
    hashes['model_id']=b'\0'*32
    return ActionContextV1(**hashes,root_scheme=1,authority_epoch=3,policy_version=7,
        capabilities=1,budget=4096,issued_at=1000,expires_at=1100,chain_id=80002)

class ActionContextTests(unittest.TestCase):
    def test_roundtrip_has_one_exact_encoding(self):
        value=sample()
        self.assertEqual(ActionContextV1.from_bytes(value.canonical_bytes()),value)
        for raw in (value.canonical_bytes()+b'\0',value.canonical_bytes()[1:],b'{}'):
            with self.assertRaises(ActionContextError):ActionContextV1.from_bytes(raw)

    def test_every_field_changes_digest(self):
        value=sample()
        for name in WIRE_FIELDS:
            old=getattr(value,name)
            changed=old+1 if type(old) is int else old[:-1]+bytes([old[-1]^1])
            if name=='root_scheme':changed=2
            with self.subTest(name=name):self.assertNotEqual(replace(value,**{name:changed}).digest,value.digest)

    def test_invalid_types_ranges_and_roots_reject(self):
        for name,bad in [('budget',True),('budget',1.0),('budget',-1),('nonce',b'x'),
                         ('root_scheme',3),('actor_root',b'x'*32),('expires_at',1000),('chain_id',0)]:
            with self.subTest(name=name,bad=bad),self.assertRaises(ActionContextError):
                replace(sample(),**{name:bad}).canonical_bytes()

    def test_frozen_golden_vector(self):
        path=Path(__file__).parents[2]/'docs/remediation/repair_20261027/action-context-v1.json'
        fixture=json.loads(path.read_text())
        value=sample()
        self.assertEqual(value.canonical_bytes().hex(),fixture['canonical_hex'])
        self.assertEqual(value.digest.hex(),fixture['sha256'])
        self.assertEqual(value.workload_hash.hex(),fixture['workload_sha256'])

if __name__=='__main__':unittest.main()
