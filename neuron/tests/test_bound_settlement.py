"""Unit boundary fixtures only; no RPC/network qualification is implied."""
from types import SimpleNamespace
import hashlib
import unittest
from neuron.composer.settlement import (
    SettlementDeployment, SettlementTransactionBuilder, SettlementBuildError, ZERO32,
)

REG='0x'+'11'*20
SET='0x'+'22'*20
PROVIDER='0x'+'33'*20
BUILDER='0x'+'44'*20

class Call:
    def __init__(self,value,seen):self.value,self.seen=value,seen
    def call(self,*,block_identifier):
        self.seen.append(block_identifier)
        return self.value

class BoundSettlementTests(unittest.TestCase):
    def setUp(self):
        self.seen=[]; self.block_hash=b'b'*32
        self.code={REG:b'registry-code', SET:b'settlement-code'}
        self.eth=SimpleNamespace(chain_id=80002,
            get_code=lambda address,block_identifier:self.code[address], get_block=self.block)
        self.row=[b's'*32, BUILDER,'name','AI','description',ZERO32,'cid',500,0,0,
            True,True,1,0,b'm'*32,ZERO32,0,BUILDER,1,False,ZERO32]
        self.registry=SimpleNamespace(address=REG,functions=SimpleNamespace(
            getServiceBlock=lambda id:Call(self.row,self.seen)))
        self.settlement=SimpleNamespace(address=SET,functions=SimpleNamespace(
            serviceBlockRegistry=lambda:Call(REG,self.seen),
            getServiceTermsHash=lambda id:Call(b't'*32,self.seen)))
        self.deployment=SettlementDeployment(80002,SET,REG,
            hashlib.sha256(self.code[SET]).digest(),hashlib.sha256(self.code[REG]).digest())
        self.builder=SettlementTransactionBuilder(SimpleNamespace(eth=self.eth),self.registry,self.settlement,self.deployment)

    def block(self,number):return {'number':42,'hash':self.block_hash}
    def request(self,**kw):
        args=dict(providers=[PROVIDER],amounts=[10**18],valid_for_seconds=3600,
            blueprint_hash=b'p'*32,service_block_id=b's'*32,workload_hashes=[b'w'*32])
        args.update(kw)
        return self.builder.build(**args)

    def test_exact_integer_amounts_and_real_id_preserved(self):
        value=self.request()
        self.assertEqual(value.amounts,(10**18,))
        self.assertEqual(value.service_block_id,b's'*32)
        self.assertEqual(value.expected_terms_hash,b't'*32)
        self.assertEqual(set(self.seen),{42})

    def test_float_bool_negative_and_overflow_amounts_reject(self):
        for amount in (1.0,True,0,-1,1<<256):
            with self.subTest(amount=amount),self.assertRaises(SettlementBuildError):self.request(amounts=[amount])

    def test_unregistered_raw_request_has_zero_terms(self):
        self.assertEqual(self.request(service_block_id=ZERO32).expected_terms_hash,ZERO32)

    def test_stale_or_substituted_chain_identity_rejects(self):
        self.eth.chain_id=1
        with self.assertRaises(SettlementBuildError):self.request()
        self.eth.chain_id=80002; self.code[REG]=b'other-runtime'
        with self.assertRaises(SettlementBuildError):self.request()

    def test_manifest_listing_and_fee_boundaries_reject(self):
        for index,bad in ((0,b'f'*32),(7,5001),(7,True),(10,False),(11,False),
                          (14,ZERO32),(18,0),(19,True),(17,PROVIDER)):
            old=self.row[index]; self.row[index]=bad
            with self.subTest(index=index,bad=bad),self.assertRaises(SettlementBuildError):self.request()
            self.row[index]=old

    def test_changed_observed_block_rejects(self):
        self.eth.get_block=lambda number:{'number':42,'hash':b'a'*32 if number=='latest' else b'b'*32}
        with self.assertRaises(SettlementBuildError):self.request()

    def test_rpc_error_is_bounded_and_does_not_expose_endpoint(self):
        def fail(number):raise RuntimeError('secret-provider-url')
        self.eth.get_block=fail
        with self.assertRaises(SettlementBuildError) as caught:self.request()
        self.assertNotIn('secret-provider-url',str(caught.exception))

if __name__=='__main__':unittest.main()
