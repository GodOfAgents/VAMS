"""Public literal vectors; no signing, key custody, native chain or authority claim."""
import hashlib,json
from pathlib import Path
import unittest
from neuron.secp256k1 import SECP256K1_ORDER,verify_digest,verify_message

FIXTURE=Path(__file__).parent/'fixtures/raw-secp256k1-v1-vectors.json'

class RawSecp256k1VectorTests(unittest.TestCase):
    def setUp(self):self.vectors=json.loads(FIXTURE.read_text(encoding='utf-8'))
    def test_full_key_raw_wire_conforms_to_frozen_cross_language_vectors(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),'88fffa5039bd5d14e00d5fee04a34d8d9bedc39425d0d5d25c0336f6a0b47249')
        self.assertTrue(self.vectors['synthetic_only'])
        self.assertFalse(self.vectors['operator_consent_or_key_custody_evidence'])
        self.assertEqual(len(self.vectors['cases']),59)
        for case in self.vectors['cases']:
            with self.subTest(vector=case['id']):
                self.assertEqual(verify_digest(bytes.fromhex(case['public_key']),bytes.fromhex(case['digest']),bytes.fromhex(case['signature'])),case['expected'])
    def test_message_and_prehashed_digest_agree_without_double_hashing(self):
        case=next(c for c in self.vectors['cases'] if c['id']=='ordinary_sha256_message')
        message=bytes.fromhex(case['message_hex']);digest=bytes.fromhex(case['digest'])
        key=bytes.fromhex(case['public_key']);signature=bytes.fromhex(case['signature'])
        self.assertEqual(hashlib.sha256(message).digest(),digest)
        self.assertTrue(verify_message(key,message,signature));self.assertTrue(verify_digest(key,digest,signature))
        self.assertFalse(verify_message(key,digest,signature))
        self.assertFalse(verify_digest(key,hashlib.sha256(digest).digest(),signature))
    def test_joint_overflow_is_mathematical_digest_data_not_enrollment_consent(self):
        case=next(c for c in self.vectors['cases'] if c['id']=='joint_R_and_Q_x_overflow')
        key=bytes.fromhex(case['public_key']);signature=bytes.fromhex(case['signature'])
        x=int.from_bytes(key[:32],'big');r=int.from_bytes(signature[:32],'big');s=int.from_bytes(signature[32:],'big')
        self.assertGreaterEqual(x,SECP256K1_ORDER);self.assertEqual(x%SECP256K1_ORDER,r);self.assertEqual(r,s)
        self.assertEqual(case['digest'],'00'*32)
        self.assertEqual(case['kind'],'SYNTHETIC_EQUATION_NO_KNOWN_MESSAGE_PREIMAGE_OR_PRIVATE_KEY')
        self.assertNotIn('message_hex',case)
        self.assertTrue(verify_digest(key,bytes(32),signature))
