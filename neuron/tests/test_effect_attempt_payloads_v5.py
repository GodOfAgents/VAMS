"""Signed absence decoding/authentication fixtures; no native funding outcome."""
from dataclasses import replace
import json
from pathlib import Path
import unittest
from cryptography.hazmat.primitives.asymmetric import ec
from neuron.effect_attempt_payloads_v5 import FencedAbsencePayloadV5,ABSENCE_SIZE,ABSENCE_DOMAIN,FENCE_SIZE
from neuron.effect_protocol_v3 import (
    ObjectEffectV3,ObjectFenceV3,SignedEffectReceiptV3,EffectV3Error,sign_receipt,
    fence_ack_subject,absence_subject,verify_fenced_absence,
)
from neuron.signed_receipts import ReceiptSignerV3,ReceiptVerifierV3


class FencedAbsencePayloadV5Test(unittest.TestCase):
    def setUp(self):
        self.v=json.loads(Path(__file__).with_name('effect_attempt_v5_fixture.json').read_text(encoding='utf8'))
        self.p=ObjectEffectV3.from_bytes(bytes.fromhex(self.v['proposal']))
        self.r={n:SignedEffectReceiptV3.from_bytes(bytes.fromhex(r['bytes'])) for n,r in self.v['receipts'].items()}
        self.f=ObjectFenceV3.from_bytes(bytes.fromhex(self.v['fence']))
        self.authority=ReceiptVerifierV3(bytes.fromhex(self.v['authority_public_verifier']['sec1_uncompressed_hex']))
        self.provider=ReceiptVerifierV3(bytes.fromhex(self.v['provider_public_verifier']['sec1_uncompressed_hex']))
        self.payload=FencedAbsencePayloadV5(self.f,self.r['update'],self.r['ack'],self.r['absence'])
    def authenticate(self,payload):
        return payload.authenticate(self.p,self.r['admission'],authority=self.authority,provider=self.provider,now=2000)

    def signed(self,fence):
        # Public synthetic private scalars1/2 only, never custody material.
        a=ReceiptSignerV3(ec.derive_private_key(1,ec.SECP256K1()))
        p=ReceiptSignerV3(ec.derive_private_key(2,ec.SECP256K1()))
        def sign(signer,purpose,subject,time):
            return sign_receipt(signer,purpose=purpose,subject=subject,provider=fence.provider_id,
                epoch=fence.authority_epoch,policy=fence.policy_version,fence=fence.fencing_token,
                issued_at=time,expires_at=fence.expires_at)
        update=sign(a,2,fence.digest,fence.issued_at)
        ack=sign(p,3,fence_ack_subject(fence,update),fence.issued_at+1)
        absence=sign(p,5,absence_subject(self.p,ack),fence.issued_at+2)
        return FencedAbsencePayloadV5(fence,update,ack,absence)

    def test_roundtrip_preserves_exact_v3_fence_and_receipt_bytes(self):
        raw=self.payload.canonical_bytes();self.assertEqual(len(raw),ABSENCE_SIZE)
        self.assertEqual(FencedAbsencePayloadV5.from_bytes(raw),self.payload)
        self.assertEqual(self.authenticate(self.payload),self.r['absence'].digest)
        self.assertLess(self.r['absence'].receipt.expires_at,2000)

    def test_noncanonical_length_domain_or_embedded_receipt_rejects(self):
        raw=self.payload.canonical_bytes()
        for value in (raw[:-1],raw+b'\0',b'X'+raw[1:]):
            with self.subTest(length=len(value)),self.assertRaises(ValueError):FencedAbsencePayloadV5.from_bytes(value)
        bad=bytearray(raw);bad[len(ABSENCE_DOMAIN)+FENCE_SIZE]^=1
        with self.assertRaises(ValueError):FencedAbsencePayloadV5.from_bytes(bytes(bad))

    def test_parsing_is_not_authentication(self):
        r=self.payload.absence;r=replace(r,signature=r.signature[:-1]+bytes([r.signature[-1]^1]))
        bad=replace(self.payload,absence=r)
        parsed=FencedAbsencePayloadV5.from_bytes(bad.canonical_bytes())
        with self.assertRaises(ValueError):self.authenticate(parsed)

    def test_provider_key_cannot_replace_authority_update(self):
        with self.assertRaises(ValueError):self.authenticate(replace(self.payload,update=self.r['ack']))

    def test_signed_regressed_or_rebound_policy_is_not_terminal_absence(self):
        import hashlib
        old=self.p.context
        cases=(replace(self.f,policy_version=old.policy_version-1),
            replace(self.f,policy_version=old.policy_version,policy_root=hashlib.sha256(b'other-policy').digest()))
        for fence in cases:
            payload=self.signed(fence)
            # Establish the missing relation in the retained local V3 helper;
            # old encodings/helpers stay local, the V5 consumer adds the check.
            verify_fenced_absence(self.p,fence,payload.update,payload.acknowledgement,
                payload.absence,self.provider,2000,authority=self.authority)
            with self.subTest(version=fence.policy_version),self.assertRaises(EffectV3Error):self.authenticate(payload)

    def test_wrong_receipt_context_or_order_cannot_close_attempt(self):
        with self.assertRaises(ValueError):self.authenticate(replace(self.payload,absence=self.r['effect']))
        with self.assertRaises(ValueError):self.authenticate(replace(self.payload,acknowledgement=self.r['absence']))


if __name__=='__main__':unittest.main()
