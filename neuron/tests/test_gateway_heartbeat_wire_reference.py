"""Frozen independent frame references. Synthetic data only, not authority."""
import ast
from dataclasses import replace
import json
from pathlib import Path
import struct
import unittest
from gateway.heartbeat_authority_source_v1 import HeartbeatAuthoritySourceV1 as Source
from gateway.heartbeat_payload_v2 import HeartbeatObservationsV1 as Observations,HeartbeatPayloadV2 as Payload,HeartbeatPayloadDataError,MAX_M2_TIMESTAMP,PAYLOAD_DOMAIN
from gateway.heartbeat_principal_v1 import HeartbeatPrincipalV1 as Principal


def fixture():
    return json.loads((Path(__file__).parent/'fixtures/heartbeat-payload-v2-reference.json').read_text(encoding='utf-8'))

def objects():
    f=fixture();source=f['source'];fields=dict(f['payload_fields']);observations=dict(f['observations'])
    s=Source(source['scheme'],bytes.fromhex(source['network_context_digest']),bytes.fromhex(source['registry_address']),
        bytes.fromhex(source['registry_code_hash']),bytes.fromhex(source['policy_address']),
        bytes.fromhex(source['policy_code_hash']),source['registry_schema_version'])
    observations['skills']=tuple(observations['skills'])
    observations['cognitive_profile']=tuple(tuple(pair) for pair in observations['cognitive_profile'])
    obs=Observations(**observations)
    for name in ('authority_source_digest','principal_digest','principal_id','policy_root','body_public_key','m2_nonce'):
        fields[name]=bytes.fromhex(fields[name])
    p=Payload(**fields,observations_v1=obs)
    return f,s,obs,p,Principal.from_bytes(bytes.fromhex(f['principal_canonical_hex']))


class HeartbeatWireReferenceTests(unittest.TestCase):
    def test_source_and_observation_match_independent_frozen_preimages(self):
        f,s,obs,p,record=objects();expected=f['expected']
        self.assertEqual(s.canonical_bytes().hex(),expected['authority_source_hex'])
        self.assertEqual(s.digest.hex(),expected['authority_source_sha256'])
        self.assertEqual(obs.canonical_bytes().hex(),expected['observations_hex'])
        self.assertEqual(Observations.from_bytes(bytes.fromhex(expected['observations_hex'])),obs)

    def test_payload_text_binary_and_digest_domains_match_frozen_reference(self):
        f,s,obs,p,record=objects();expected=f['expected']
        self.assertEqual(p.canonical_bytes().hex(),expected['payload_binary_hex'])
        self.assertEqual(p.payload_text,expected['payload_text'])
        self.assertEqual(p.digest.hex(),expected['payload_text_sha256'])
        self.assertEqual(p.canonical_binary_digest.hex(),expected['canonical_binary_sha256'])
        self.assertNotEqual(p.digest,p.canonical_binary_digest)
        self.assertEqual(Payload.from_payload_text(expected['payload_text']),p)
        self.assertTrue(p.matches_record_data(record,s.digest,p.m2_nonce,p.m2_issued_at,p.m2_expires_at))

    def test_same_second_changed_generation_and_rewrapped_envelope_do_not_match(self):
        f,s,obs,p,record=objects()
        new_record=replace(record,principal_generation=record.principal_generation+1,
            policy_root=b'\x08'*32,policy_version=record.policy_version+1,authority_epoch=record.authority_epoch+1)
        self.assertFalse(p.matches_record_data(new_record,s.digest,p.m2_nonce,p.m2_issued_at,p.m2_expires_at))
        self.assertFalse(p.matches_record_data(record,s.digest,b'\x0a'*16,p.m2_issued_at,p.m2_expires_at))
        self.assertFalse(p.matches_record_data(record,s.digest,p.m2_nonce,p.m2_issued_at+1,p.m2_expires_at+1))
        other_source=replace(s,registry_address=b'\x12'*20)
        self.assertFalse(p.matches_record_data(record,other_source.digest,p.m2_nonce,p.m2_issued_at,p.m2_expires_at))

    def test_numeric_bits_are_wire_identity_not_python_equality(self):
        f,s,obs,p,record=objects()
        negative=replace(p,observations_v1=replace(obs,cost_per_hour=-0.0))
        positive=replace(p,observations_v1=replace(obs,cost_per_hour=0.0))
        integer=replace(p,observations_v1=replace(obs,cost_per_hour=0))
        decoded=Payload.from_payload_text(negative.payload_text)
        self.assertEqual(struct.pack('>d',decoded.observations_v1.cost_per_hour),bytes.fromhex('8000000000000000'))
        self.assertEqual(len({negative.digest,positive.digest,integer.digest}),3)

    def test_m2_timestamp_domain_matches_actual_outer_validator_and_wire_boundaries(self):
        # Execute only the actual pure timestamp validator; no framework import.
        source=Path(__file__).parents[2]/'gateway/request_auth.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_validate_timestamp_type')
        class FixtureAuthError(Exception):pass
        scope={'GatewayAuthenticationError':FixtureAuthError}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),scope)
        validate=scope['_validate_timestamp_type'];maximum=(1<<63)-1
        self.assertEqual(MAX_M2_TIMESTAMP,maximum)
        for value in (0,maximum-300,maximum):validate(value)
        f,authority,obs,p,record=objects()
        bound=replace(p,m2_issued_at=maximum-300,m2_expires_at=maximum)
        self.assertEqual(Payload.from_bytes(bound.canonical_bytes()),bound)
        self.assertEqual(Payload.from_payload_text(bound.payload_text),bound)
        self.assertTrue(bound.matches_record_data(record,authority.digest,p.m2_nonce,maximum-300,maximum))
        for value in (-1,True,1.0,None,1<<63,(1<<64)-1,1<<64):
            with self.subTest(value=value):
                with self.assertRaises(FixtureAuthError):validate(value)
                with self.assertRaises(HeartbeatPayloadDataError):replace(p,m2_issued_at=value)
                with self.assertRaises(HeartbeatPayloadDataError):replace(p,m2_expires_at=value)
                self.assertFalse(p.matches_record_data(record,authority.digest,p.m2_nonce,value,p.m2_expires_at))
                self.assertFalse(p.matches_record_data(record,authority.digest,p.m2_nonce,p.m2_issued_at,value))
        for field_id in (11,12):
            for value in (1<<63,(1<<64)-1):
                with self.subTest(field_id=field_id,value=value):
                    raw=bytearray(p.canonical_bytes());offset=len(PAYLOAD_DOMAIN)+2
                    for current in range(1,14):
                        self.assertEqual(raw[offset],current)
                        length=int.from_bytes(raw[offset+1:offset+3],'big');offset+=3
                        if current==field_id:
                            self.assertEqual(length,8);raw[offset:offset+8]=value.to_bytes(8,'big');break
                        offset+=length
                    with self.assertRaises(HeartbeatPayloadDataError):Payload.from_bytes(bytes(raw))
                    with self.assertRaises(HeartbeatPayloadDataError):Payload.from_payload_text('VAMS-HB2:'+bytes(raw).hex())
