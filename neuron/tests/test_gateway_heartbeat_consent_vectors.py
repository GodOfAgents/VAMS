"""Independent literal and adversarial checks of proposed unsigned consent bytes."""
from dataclasses import fields,replace
import hashlib,json
from pathlib import Path
import unittest
from gateway.heartbeat_consent_v2 import HeartbeatConsentBaseIntentV2 as Base,HeartbeatConsentWitnessV2 as Witness,HeartbeatConsentDataError as DataError

INTEGER_FIELDS={'mode','source_scheme','authority_change_sequence','policy_version','authority_epoch','expected_generation','proposed_generation','consent_nonce','queued_eta','issued_at','expires_at','required_role_mask'}
def values(data):return {name:int(value) if name in INTEGER_FIELDS else bytes.fromhex(value) for name,value in data.items()}

class HeartbeatConsentLiteralVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((Path(__file__).parent/'fixtures/heartbeat-consent-v2-vectors.json').read_text(encoding='utf-8'))
        cls.cases={case['id']:case for case in cls.fixture['cases']}

    def test_independent_literal_bytes_and_exact_single_sha256(self):
        for case in self.cases.values():
            for kind,model in (('base',Base),('witness',Witness)):
                with self.subTest(case=case['id'],kind=kind):
                    encoded=bytes.fromhex(case[kind+'_hex']);obj=model(**values(case[kind]))
                    self.assertEqual(obj.canonical_bytes(),encoded)
                    self.assertEqual(model.from_bytes(encoded),obj)
                    self.assertEqual(obj.digest.hex(),case[kind+'_sha256'])
                    self.assertNotEqual(obj.digest,hashlib.sha256(obj.digest).digest())
                    self.assertNotEqual(obj.digest,hashlib.sha256(case[kind+'_hex'].encode('ascii')).digest())
            self.assertTrue(Witness(**values(case['witness'])).matches_base_data(Base(**values(case['base']))))

    def test_every_base_field_changes_the_commitment_or_is_rejected(self):
        case=self.cases['normal_rotation'];original=Base(**values(case['base']));witness=Witness(**values(case['witness']))
        must_reject={'source_scheme','expected_generation','proposed_generation'}
        for field in fields(original):
            value=getattr(original,field.name)
            change=value+1 if type(value) is int else value[:-1]+bytes((value[-1]^1,))
            with self.subTest(field=field.name):
                if field.name in must_reject:
                    with self.assertRaises(DataError):replace(original,**{field.name:change})
                else:
                    altered=replace(original,**{field.name:change})
                    self.assertNotEqual(altered.digest,original.digest)
                    self.assertFalse(witness.matches_base_data(altered))

    def test_every_witness_field_changes_the_commitment_or_is_rejected(self):
        case=self.cases['normal_rotation'];original=Witness(**values(case['witness']))
        for field in fields(original):
            value=getattr(original,field.name)
            change=(value-1 if field.name=='issued_at' else value+1) if type(value) is int else value[:-1]+bytes((value[-1]^1,))
            with self.subTest(field=field.name):
                if field.name in ('mode','required_role_mask'):
                    with self.assertRaises(DataError):replace(original,**{field.name:change})
                else:self.assertNotEqual(replace(original,**{field.name:change}).digest,original.digest)

    def test_structural_match_does_not_authenticate_operation_or_challenge(self):
        case=self.cases['normal_rotation'];base=Base(**values(case['base']));witness=Witness(**values(case['witness']))
        for changes in ({'operation_id':bytes(32)},{'post_eta_challenge_commitment':bytes(32)},{'queued_eta':0}):
            other=replace(witness,**changes)
            self.assertTrue(other.matches_base_data(base))
            self.assertNotEqual(other.digest,witness.digest)
        recovered=replace(witness,mode=3,required_role_mask=2)
        self.assertFalse(recovered.matches_base_data(base))
        self.assertFalse(witness.matches_base_data(None))
        self.assertFalse(any('signature' in field.name for field in fields(witness)))

    def test_full_uint64_domain_and_distinct_identity_sentinels(self):
        maximum=(1<<64)-1;case=self.cases['normal_maximum_u64'];base=Base(**values(case['base']));witness=Witness(**values(case['witness']))
        self.assertEqual(base.policy_version,maximum);self.assertEqual(base.authority_epoch,maximum)
        self.assertEqual(base.proposed_generation,maximum);self.assertEqual(base.consent_nonce,maximum)
        self.assertEqual(witness.expires_at,maximum);self.assertGreater(witness.issued_at,(1<<63)-1)
        for field in ('authority_change_sequence','policy_version','authority_epoch','expected_generation','proposed_generation','consent_nonce'):
            for invalid in (True,-1,maximum+1):
                with self.subTest(base_field=field,value=invalid),self.assertRaises(DataError):replace(base,**{field:invalid})
        for field in ('queued_eta','issued_at','expires_at'):
            for invalid in (True,-1,maximum+1):
                with self.subTest(witness_field=field,value=invalid),self.assertRaises(DataError):replace(witness,**{field:invalid})
        for field in ('principal_id','policy_root','timelock_code_hash','timelock_address'):
            with self.subTest(identity=field),self.assertRaises(DataError):replace(base,**{field:bytes(len(getattr(base,field)))})
        for field in ('policy_version','authority_epoch'):
            with self.subTest(positive=field),self.assertRaises(DataError):replace(base,**{field:0})

    def test_every_truncation_and_malformed_frame_denies(self):
        case=self.cases['normal_rotation']
        for kind,model in (('base',Base),('witness',Witness)):
            raw=bytes.fromhex(case[kind+'_hex']);domain=bytes.fromhex(self.fixture[kind+'_domain_hex']);offset=len(domain)+2
            for cut in range(len(raw)):
                with self.subTest(kind=kind,cut=cut),self.assertRaises(DataError):model.from_bytes(raw[:cut])
            malformed=[raw+b'\x00',raw+bytes(1025),raw[:-1]+bytes(2)]
            for tag in (0,2,255):malformed.append(raw[:offset]+bytes((tag,))+raw[offset+1:])
            malformed.append(raw[:len(domain)]+b'\x00\x00'+raw[offset:])
            malformed.append(raw[:offset+1]+b'\x00\x00'+raw[offset+3:])
            malformed.append(raw[:offset+1]+b'\xff\xff'+raw[offset+3:])
            for bad in (*malformed,None,True,raw.hex(),bytearray(raw)):
                with self.subTest(kind=kind,bad_type=type(bad).__name__),self.assertRaises(DataError):model.from_bytes(bad)
