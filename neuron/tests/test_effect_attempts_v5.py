"""Pure identity/history regressions. No PostgreSQL/native-finality/provider qualification."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from cryptography.hazmat.primitives.asymmetric import ec
from neuron.effect_attempts_v5 import (
    ObjectAttemptV5, NativeObjectRowV1, logical_work, native_attempt_id,
    authenticate_same_host_successor, authority_context_id,
)
from neuron.effect_protocol_v3 import (
    ObjectEffectV3, ObjectFenceV3, SignedEffectReceiptV3, EffectV3Error, sign_receipt,
)
from neuron.signed_receipts import ReceiptSignerV3


def h(value):
    return hashlib.sha256(value).digest()


class ObjectAttemptV5Test(unittest.TestCase):
    def setUp(self):
        v=json.loads(Path(__file__).with_name('effect_attempt_v5_fixture.json').read_text(encoding='utf8'))
        self.vector=v
        self.proposal=ObjectEffectV3.from_bytes(bytes.fromhex(v['proposal']))
        self.receipts={n:SignedEffectReceiptV3.from_bytes(bytes.fromhex(r['bytes'])) for n,r in v['receipts'].items()}
        self.fence=ObjectFenceV3.from_bytes(bytes.fromhex(v['fence']))
        # Public synthetic fixtures only; neither a real issuer nor custody material.
        self.authority=ReceiptSignerV3(ec.derive_private_key(1,ec.SECP256K1()))
        self.provider=ReceiptSignerV3(ec.derive_private_key(2,ec.SECP256K1()))
        c=self.proposal.context
        row=NativeObjectRowV1(c.chain_id,c.target,h(b'first-native-allocation'),0)
        self.previous=ObjectAttemptV5(row,self.proposal,self.receipts['admission'],1,None)

    def successor(self, *, now=1005, **changes):
        p=self.proposal
        c=replace(p.context,authority_epoch=5,policy_version=9,issued_at=now,expires_at=now+100,
            nonce=h(b'successor-action-nonce'))
        p=replace(p,context=c,fencing_token=11)
        context_changes=changes.pop('context_changes',{})
        p=replace(p,context=replace(p.context,**context_changes),**changes)
        p=replace(p,context=replace(p.context,action_hash=p.action_hash))
        c=p.context
        receipt=sign_receipt(self.authority,purpose=1,subject=p.digest,provider=c.provider_id,
            epoch=c.authority_epoch,policy=c.policy_version,fence=p.fencing_token,
            issued_at=c.issued_at,expires_at=c.expires_at)
        row=NativeObjectRowV1(c.chain_id,c.target,h(b'next-native-allocation'),1)
        return ObjectAttemptV5(row,p,receipt,2,self.previous.attempt_id)

    def check(self, successor, *, now=1005, **receipts):
        values=dict(update=self.receipts['update'],ack=self.receipts['ack'],absence=self.receipts['absence'])
        values.update(receipts)
        return authenticate_same_host_successor(self.previous,successor,self.fence,
            **values,authority=self.authority.verifier(),provider=self.provider.verifier(),now=now)

    def test_stable_operation_and_work_but_distinct_attempt_and_link(self):
        next_=self.successor()
        self.assertEqual(self.proposal.operation_id,next_.proposal.operation_id)
        self.assertEqual(logical_work(self.proposal),logical_work(next_.proposal))
        self.assertNotEqual(self.previous.attempt_id,next_.attempt_id)
        self.assertEqual(self.check(next_),next_.link_digest)
        self.assertEqual(self.previous.admission,self.receipts['admission'])

    def test_historical_expired_absence_can_authorize_current_retry_history(self):
        next_=self.successor(now=2000)
        self.assertLess(self.receipts['absence'].receipt.expires_at,2000)
        self.assertEqual(self.check(next_,now=2000),next_.link_digest)

    def test_current_authentication_does_not_accept_expired_successor(self):
        next_=self.successor()
        with self.assertRaises(ValueError):self.check(next_,now=2000)
        # Recovery-only verification is separate and creates no dispatch authority.
        next_.authenticate_history(self.authority.verifier(),2000)

    def test_equal_epoch_or_fence_rejects(self):
        for changes in ({'fencing_token':10},{'context_changes':{'authority_epoch':4}}):
            with self.subTest(changes=changes),self.assertRaises(EffectV3Error):
                self.check(self.successor(**changes))

    def test_input_resource_unit_and_cost_cannot_rebind_logical_work(self):
        cases=({'cost_units':2},{'resource_id':h(b'another-resource')},
            {'context_changes':{'input_hash':h(b'another-input')}},
            {'context_changes':{'budget_unit':h(b'another-unit')}})
        for changes in cases:
            with self.subTest(changes=changes),self.assertRaises(EffectV3Error):
                self.check(self.successor(**changes))

    def test_wrong_predecessor_ordinal_or_generation_rejects(self):
        next_=self.successor()
        for changes in ({'previous_attempt':h(b'wrong-predecessor')},{'ordinal':3}):
            with self.subTest(changes=changes),self.assertRaises(EffectV3Error):
                self.check(replace(next_,**changes))

    def test_missing_ack_or_wrong_absence_never_proves_successor(self):
        with self.assertRaises(ValueError):self.check(self.successor(),ack=self.receipts['effect'])
        with self.assertRaises(ValueError):self.check(self.successor(),absence=self.receipts['effect'])

    def test_native_row_host_and_index_are_bound(self):
        next_=self.successor()
        with self.assertRaises(EffectV3Error):replace(next_,row=replace(next_.row,provider_index=20)).validate()
        with self.assertRaises(EffectV3Error):replace(next_,row=replace(next_.row,chain_id=80003)).validate()
        with self.assertRaises(EffectV3Error):replace(next_,row=replace(next_.row,settlement=b'\x01'*32)).validate()

    def test_metadata_types_and_predecessor_shape_reject(self):
        next_=self.successor()
        for changes in ({'ordinal':True},{'ordinal':0},{'previous_attempt':None},
                {'previous_attempt':next_.attempt_id}):
            with self.subTest(changes=changes),self.assertRaises(EffectV3Error):replace(next_,**changes).validate()

    def test_altered_signature_is_not_authenticated_by_typed_metadata(self):
        next_=self.successor();r=next_.admission
        r=replace(r,signature=r.signature[:-1]+bytes([r.signature[-1]^1]))
        malformed=replace(next_,admission=r)
        malformed.validate()
        with self.assertRaises(ValueError):malformed.authenticate_current(self.authority.verifier(),1005)

    def test_core_identity_allows_host_migration_but_local_renewal_needs_handoff(self):
        next_=self.successor(context_changes={'chain_id':80003,'target':bytes.fromhex('00'*12+'33'*20)})
        self.assertEqual(self.proposal.operation_id,next_.proposal.operation_id)
        self.assertEqual(logical_work(self.proposal),logical_work(next_.proposal))
        with self.assertRaisesRegex(EffectV3Error,'migration required'):self.check(next_)

    def test_runtime_replacement_needs_authenticated_migration_but_preserves_core_work(self):
        next_=self.successor(context_changes={'runtime_id':h(b'updated-runtime')})
        self.assertEqual(self.proposal.operation_id,next_.proposal.operation_id)
        self.assertEqual(logical_work(self.proposal),logical_work(next_.proposal))
        with self.assertRaisesRegex(EffectV3Error,'migration required'):self.check(next_)

    def test_caller_cannot_supply_generation_metadata_as_authenticated_context(self):
        next_=self.successor()
        with self.assertRaises(TypeError):replace(next_,generation_id=h(b'invented-generation'))
        before=authority_context_id(next_.proposal)
        changed=self.successor(context_changes={'authority_epoch':6})
        self.assertNotEqual(before,authority_context_id(changed.proposal))

    def test_domains_and_native_attempt_words_match_independent_sha256(self):
        p=self.previous
        expected=h(b'VAMS:OBJECT-LOGICAL-WORK:v1\0'+p.proposal.postcondition+
            p.proposal.context.budget_unit+p.proposal.cost_units.to_bytes(32,'big'))
        self.assertEqual(logical_work(p.proposal),expected)
        expected=h(b'VAMS:OBJECT-SETTLEMENT-ATTEMPT:v1\0'+p.row.chain_id.to_bytes(32,'big')+
            p.row.settlement+p.row.allocation_id+p.row.provider_index.to_bytes(32,'big')+
            p.proposal.digest+p.admission.digest)
        self.assertEqual(native_attempt_id(p.row,p.proposal,p.admission),expected)


if __name__=='__main__':unittest.main()
