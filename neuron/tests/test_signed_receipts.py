from dataclasses import replace
import unittest
from cryptography.hazmat.primitives.asymmetric import ec
from neuron.signed_receipts import ReceiptSignerV3, ReceiptV3, ReceiptError, ORDER

class SignedReceiptTests(unittest.TestCase):
    def setUp(self):
        self.signer=ReceiptSignerV3(ec.generate_private_key(ec.SECP256K1()))
        self.verifier=self.signer.verifier()
        self.receipt=ReceiptV3(1,self.verifier.issuer_id,b'a'*32,b'p'*32,2,3,4,1000,1100)
        self.expected=dict(purpose=1,subject_digest=b'a'*32,provider_id=b'p'*32,
            authority_epoch=2,policy_version=3,fencing_token=4,now=1050)

    def test_real_signature_verifies_without_signing_authority(self):
        signature=self.signer.sign(self.receipt)
        self.assertEqual(self.verifier.verify(self.receipt,signature,**self.expected),self.receipt.digest)
        self.assertFalse(hasattr(self.verifier,'sign'))
        with self.assertRaises(ReceiptError):ReceiptSignerV3(self.verifier)

    def test_public_key_cannot_forge_receipt(self):
        with self.assertRaises(ReceiptError):self.verifier.verify(self.receipt,b'\0'*64,**self.expected)
        other=ReceiptSignerV3(ec.generate_private_key(ec.SECP256K1()))
        forged=replace(self.receipt,issuer_id=other.verifier().issuer_id)
        with self.assertRaises(ReceiptError):self.verifier.verify(forged,other.sign(forged),**self.expected)

    def test_all_scope_fields_are_bound(self):
        signature=self.signer.sign(self.receipt)
        for name in ('purpose','subject_digest','provider_id','authority_epoch','policy_version','fencing_token','issued_at','expires_at'):
            value=getattr(self.receipt,name)
            changed=value+1 if type(value) is int else b'x'*32
            with self.subTest(name=name),self.assertRaises(ReceiptError):
                self.verifier.verify(replace(self.receipt,**{name:changed}),signature,**self.expected)

    def test_stale_policy_expiry_and_future_issue_reject(self):
        signature=self.signer.sign(self.receipt)
        for args in ({'policy_version':4},{'authority_epoch':3},{'fencing_token':5},{'now':1100},{'now':999}):
            expected=self.expected|args
            with self.subTest(args=args),self.assertRaises(ReceiptError):self.verifier.verify(self.receipt,signature,**expected)

    def test_high_s_signature_and_v2_mac_reject(self):
        signature=self.signer.sign(self.receipt)
        high=signature[:32]+(ORDER-int.from_bytes(signature[32:],'big')).to_bytes(32,'big')
        for invalid in (high,b'm'*32,signature+b'\0'):
            with self.assertRaises(ReceiptError):self.verifier.verify(self.receipt,invalid,**self.expected)

    def test_historical_evidence_cannot_become_current_authority(self):
        effect=replace(self.receipt,purpose=4)
        signature=self.signer.sign(effect)
        expected=self.expected|{'purpose':4,'now':1200}
        with self.assertRaises(ReceiptError):self.verifier.verify(effect,signature,**expected)
        self.assertEqual(self.verifier.verify_evidence(effect,signature,**expected),effect.digest)
        with self.assertRaises(ReceiptError):self.verifier.verify_evidence(self.receipt,self.signer.sign(self.receipt),**self.expected)

    def test_expected_scope_does_not_accept_boolean_aliases(self):
        signature=self.signer.sign(self.receipt)
        with self.assertRaises(ReceiptError):self.verifier.verify(self.receipt,signature,**(self.expected|{'purpose':True}))

if __name__=='__main__':unittest.main()
