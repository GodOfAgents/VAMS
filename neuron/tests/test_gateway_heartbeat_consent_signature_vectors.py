"""Independent signed literal compatibility; synthetic keys, no native consent."""
import hashlib,json
from pathlib import Path
import unittest
from gateway.heartbeat_consent_signatures_v2 import body_key_statement,verify_body_key_signature,verify_normal_rotation_signature_pair
from gateway.heartbeat_principal_v1 import HeartbeatPrincipalV1

class HeartbeatConsentSignatureVectorTests(unittest.TestCase):
    def setUp(self):
        p=Path(__file__).parent/'fixtures/heartbeat-body-signature-v2-vectors.json'
        raw=p.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'6076687ffcefea2be4f3348cced299e71eb9312fc1b2f533b7b4e6d292761e9b')
        self.cases=json.loads(raw)['cases'];self.assertEqual(len(self.cases),4)

    def test_independent_signed_literal_statements_keys_and_signatures(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                args=self._arguments(case)
                statement=body_key_statement(args['witness_raw'],case['role'])
                self.assertEqual(statement.hex(),case['statement_hex'])
                self.assertEqual(hashlib.sha256(statement).hexdigest(),case['statement_sha256'])
                self.assertEqual(HeartbeatPrincipalV1.from_bytes(args['principal_raw']).body_public_key.hex(),case['public_key_hex'])
                self.assertTrue(verify_body_key_signature(**args))

    def test_fixed_normal_old_new_vectors_form_one_paired_signature_result(self):
        by_id={case['id']:case for case in self.cases}
        old,new=by_id['normal_old'],by_id['normal_new']
        self.assertEqual(old['base_hex'],new['base_hex'])
        self.assertEqual(old['witness_hex'],new['witness_hex'])
        args=dict(base_raw=bytes.fromhex(old['base_hex']),witness_raw=bytes.fromhex(old['witness_hex']),
            old_principal_raw=bytes.fromhex(old['principal_hex']),proposed_principal_raw=bytes.fromhex(new['principal_hex']),
            old_signature=bytes.fromhex(old['signature_hex']),new_signature=bytes.fromhex(new['signature_hex']))
        self.assertTrue(verify_normal_rotation_signature_pair(**args))
        self.assertFalse(verify_normal_rotation_signature_pair(**{**args,'old_signature':args['new_signature']}))
        split_witness=bytes.fromhex(by_id['recovery_new']['witness_hex'])
        self.assertFalse(verify_normal_rotation_signature_pair(**{**args,'witness_raw':split_witness}))
    def test_literal_role_reuse_context_mutation_and_high_s_reject(self):
        order=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
        for case in self.cases:
            with self.subTest(case=case['id']):
                args=self._arguments(case);base=args['base_raw'];signature=args['signature']
                high_s=signature[:32]+(order-int.from_bytes(signature[32:],'big')).to_bytes(32,'big')
                self.assertFalse(verify_body_key_signature(**{**args,'role':3-case['role']}))
                self.assertFalse(verify_body_key_signature(**{**args,'base_raw':base[:-1]+bytes((base[-1]^1,))}))
                self.assertFalse(verify_body_key_signature(**{**args,'signature':high_s}))

    @staticmethod
    def _arguments(case):
        return dict(base_raw=bytes.fromhex(case['base_hex']),witness_raw=bytes.fromhex(case['witness_hex']),principal_raw=bytes.fromhex(case['principal_hex']),role=case['role'],signature=bytes.fromhex(case['signature_hex']))

if __name__=='__main__':unittest.main()

