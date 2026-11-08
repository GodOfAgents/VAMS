"""Synthetic public-fixture signatures only; no enrolled keys or native authority."""
from dataclasses import replace
import hashlib
import unittest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec,utils

from gateway.heartbeat_consent_v2 import HeartbeatConsentBaseIntentV2,HeartbeatConsentWitnessV2
from gateway.heartbeat_principal_v1 import HeartbeatPrincipalV1,node_id_commitment,principal_id_commitment
from gateway.heartbeat_consent_signatures_v2 import body_key_statement,verify_body_key_signature,verify_normal_rotation_signature_pair

_N=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_DOMAIN=b"VAMS:GATEWAY:HEARTBEAT-CONSENT-SIGNATURE:v2\x00"

def _key(scalar):return ec.derive_private_key(scalar,ec.SECP256K1())
def _public(key):
    numbers=key.public_key().public_numbers()
    return numbers.x.to_bytes(32,'big')+numbers.y.to_bytes(32,'big')
def _sign(key,message):
    # Independent producer: direct cryptography DER, literal order and raw64 conversion.
    r,s=utils.decode_dss_signature(key.sign(message,ec.ECDSA(hashes.SHA256())))
    return r.to_bytes(32,'big')+min(s,_N-s).to_bytes(32,'big')
def _statement(witness,role):return _DOMAIN+bytes((1,role))+hashlib.sha256(witness.canonical_bytes()).digest()
def _record(key,generation):
    host,service=b'\x05'*32,b'\x06'*32
    node=node_id_commitment('public-consent-fixture',host_domain=host,service_domain=service)
    m2=_public(_key(3))
    return HeartbeatPrincipalV1(principal_id=principal_id_commitment(host_domain=host,service_domain=service,node_id_commitment=node),
        node_id_commitment=node,m2_signer_did='did:key:'+m2.hex(),m2_signer_public_key=m2,certificate_fingerprint=b'\x03'*32,
        body_public_key=_public(key),host_domain=host,service_domain=service,audience='gateway.testnet',method='POST',path='/heartbeat',query=b'',
        policy_root=b'\x07'*32,policy_version=3,authority_epoch=11,principal_generation=generation,not_before=1700000000,expires_at=1700000300)
def _pair(mode=2):
    old=_record(_key(1),4);proposed=_record(_key(2),1 if mode==1 else 5)
    base=HeartbeatConsentBaseIntentV2(mode=mode,source_scheme=1,authority_source_digest=b'\x10'*32,timelock_address=b'\x20'*20,
        timelock_code_hash=b'\x21'*32,authority_config_digest=b'\x22'*32,authority_change_sequence=9,policy_root=proposed.policy_root,
        policy_version=proposed.policy_version,authority_epoch=proposed.authority_epoch,principal_id=proposed.principal_id,
        proposed_record_digest=proposed.digest,expected_record_digest=bytes(32) if mode==1 else old.digest,
        expected_generation=0 if mode==1 else 4,proposed_generation=proposed.principal_generation,consent_nonce=8,
        timelock_predecessor=b'\x23'*32,timelock_salt=b'\x24'*32)
    witness=HeartbeatConsentWitnessV2(base_intent_digest=base.digest,operation_id=b'\x25'*32,queued_eta=172800,
        post_eta_challenge_commitment=b'\x26'*32,issued_at=172801,expires_at=172900,mode=mode,required_role_mask=3 if mode==2 else 2)
    return base,witness,old,proposed
def _verify(base,witness,record,role,signature):
    return verify_body_key_signature(base_raw=base.canonical_bytes(),witness_raw=witness.canonical_bytes(),principal_raw=record.canonical_bytes(),role=role,signature=signature)

class HeartbeatConsentBodySignatureTests(unittest.TestCase):
    def test_statement_matches_independent_literal_domain_algorithm_role_and_hash_once(self):
        _,witness,_,_=_pair()
        for role in (1,2):self.assertEqual(body_key_statement(witness.canonical_bytes(),role),_statement(witness,role))
        self.assertNotEqual(_statement(witness,1),_statement(witness,2))

    def test_normal_rotation_verifies_distinct_old_and_new_body_keys(self):
        base,witness,old,new=_pair()
        self.assertTrue(_verify(base,witness,old,1,_sign(_key(1),_statement(witness,1))))
        self.assertTrue(_verify(base,witness,new,2,_sign(_key(2),_statement(witness,2))))
        self.assertFalse(_verify(base,witness,new,1,_sign(_key(2),_statement(witness,1))))
        self.assertFalse(_verify(base,witness,old,2,_sign(_key(1),_statement(witness,2))))

    def test_enrollment_and_recovery_verify_new_body_key_only_without_governance_claim(self):
        for mode in (1,3):
            base,witness,old,new=_pair(mode)
            self.assertTrue(_verify(base,witness,new,2,_sign(_key(2),_statement(witness,2))))
            self.assertFalse(_verify(base,witness,old,1,_sign(_key(1),_statement(witness,1))))
            with self.assertRaises(ValueError):body_key_statement(witness.canonical_bytes(),1)

    def test_m2_key_and_unrelated_key_cannot_substitute_for_body_key(self):
        base,witness,_,new=_pair()
        for key in (_key(1),_key(3),_key(4)):
            self.assertFalse(_verify(base,witness,new,2,_sign(key,_statement(witness,2))))

    def test_each_witness_binding_invalidates_existing_signature(self):
        base,witness,_,new=_pair();signature=_sign(_key(2),_statement(witness,2))
        changes=dict(base_intent_digest=b'\x30'*32,operation_id=b'\x31'*32,queued_eta=172799,
            post_eta_challenge_commitment=b'\x32'*32,issued_at=172802,expires_at=172901)
        for name,value in changes.items():
            with self.subTest(field=name):self.assertFalse(_verify(base,replace(witness,**{name:value}),new,2,signature))

    def test_all_base_fields_are_committed_by_the_witness(self):
        base,witness,_,new=_pair();signature=_sign(_key(2),_statement(witness,2))
        changes=dict(authority_source_digest=b'\x30'*32,timelock_address=b'\x31'*20,timelock_code_hash=b'\x32'*32,
            authority_config_digest=b'\x33'*32,authority_change_sequence=10,policy_root=b'\x34'*32,policy_version=4,authority_epoch=12,
            principal_id=b'\x35'*32,proposed_record_digest=b'\x36'*32,expected_record_digest=b'\x37'*32,consent_nonce=9,
            timelock_predecessor=b'\x38'*32,timelock_salt=b'\x39'*32)
        for name,value in changes.items():
            with self.subTest(field=name):self.assertFalse(_verify(replace(base,**{name:value}),witness,new,2,signature))
        changed=replace(base,expected_generation=5,proposed_generation=6)
        self.assertFalse(_verify(changed,witness,new,2,signature))
        self.assertFalse(_verify(replace(base,mode=3),witness,new,2,signature))

    def test_exact_record_digest_generation_and_new_policy_are_required(self):
        base,witness,old,new=_pair();signature=_sign(_key(2),_statement(witness,2))
        for changed in (replace(new,certificate_fingerprint=b'\x44'*32),replace(new,body_public_key=_public(_key(4))),replace(new,principal_generation=6)):
            self.assertFalse(_verify(base,witness,changed,2,signature))
        for field,value in (('policy_root',b'\x45'*32),('policy_version',4),('authority_epoch',12),('proposed_generation',6)):
            changed=replace(base,**({field:value,'expected_generation':5} if field=='proposed_generation' else {field:value}))
            changed_witness=replace(witness,base_intent_digest=changed.digest)
            self.assertFalse(_verify(changed,changed_witness,new,2,_sign(_key(2),_statement(changed_witness,2))))
        changed=replace(old,principal_generation=3)
        self.assertFalse(_verify(base,witness,changed,1,_sign(_key(1),_statement(witness,1))))

    def test_role_reuse_and_wrong_purpose_hashes_are_rejected(self):
        base,witness,_,new=_pair()
        messages=(_statement(witness,1),witness.canonical_bytes(),witness.digest,hashlib.sha256(_statement(witness,2)).digest(),b'OTHER:'+_statement(witness,2))
        for message in messages:self.assertFalse(_verify(base,witness,new,2,_sign(_key(2),message)))

    def test_malformed_scalars_high_s_and_bad_points_reject(self):
        base,witness,_,new=_pair();signature=_sign(_key(2),_statement(witness,2))
        r,s=signature[:32],int.from_bytes(signature[32:],'big')
        for bad in (b'',signature[:-1],signature+b'\x00',bytes(64),r+(_N-s).to_bytes(32,'big'),_N.to_bytes(32,'big')+signature[32:],r+_N.to_bytes(32,'big')):
            self.assertFalse(_verify(base,witness,new,2,bad))
        bad_record=replace(new,body_public_key=bytes(64));bad_base=replace(base,proposed_record_digest=bad_record.digest)
        bad_witness=replace(witness,base_intent_digest=bad_base.digest)
        self.assertFalse(_verify(bad_base,bad_witness,bad_record,2,signature))

    def test_noncanonical_raw_frames_and_wrong_python_types_reject(self):
        base,witness,_,new=_pair();signature=_sign(_key(2),_statement(witness,2))
        args=dict(base_raw=base.canonical_bytes(),witness_raw=witness.canonical_bytes(),principal_raw=new.canonical_bytes(),role=2,signature=signature)
        for name in ('base_raw','witness_raw','principal_raw'):
            for bad in (args[name]+b'\x00',args[name][:-1],b'x'*1025,bytearray(args[name]),None):
                self.assertFalse(verify_body_key_signature(**{**args,name:bad}))
        for role in (0,3,255,True,2.0,None):self.assertFalse(verify_body_key_signature(**{**args,'role':role}))
        for sig in (None,bytearray(signature),'not-a-signature'):self.assertFalse(verify_body_key_signature(**{**args,'signature':sig}))

    def test_normal_rotation_pair_requires_both_signatures_over_same_base_and_witness(self):
        base,witness,old,new=_pair()
        old_signature=_sign(_key(1),_statement(witness,1))
        new_signature=_sign(_key(2),_statement(witness,2))
        args=dict(base_raw=base.canonical_bytes(),witness_raw=witness.canonical_bytes(),
            old_principal_raw=old.canonical_bytes(),proposed_principal_raw=new.canonical_bytes(),
            old_signature=old_signature,new_signature=new_signature)
        self.assertTrue(verify_normal_rotation_signature_pair(**args))
        self.assertFalse(verify_normal_rotation_signature_pair(**{**args,'old_signature':b''}))
        self.assertFalse(verify_normal_rotation_signature_pair(**{**args,'new_signature':bytes(64)}))
        self.assertFalse(verify_normal_rotation_signature_pair(**{**args,'old_signature':new_signature,'new_signature':old_signature}))
        self.assertFalse(verify_normal_rotation_signature_pair(**{**args,'old_signature':_sign(_key(4),_statement(witness,1))}))
        changed_witness=replace(witness,operation_id=b'\x27'*32)
        split_args={**args,'witness_raw':changed_witness.canonical_bytes(),
            'new_signature':_sign(_key(2),_statement(changed_witness,2))}
        self.assertFalse(verify_normal_rotation_signature_pair(**split_args))
        self.assertFalse(verify_normal_rotation_signature_pair(**{**args,'base_raw':base.canonical_bytes()+b'\x00'}))
        self.assertFalse(verify_normal_rotation_signature_pair(**{**args,'new_signature':new_signature[:-1]}))

    def test_normal_rotation_pair_rejects_enrollment_and_recovery_modes(self):
        for mode in (1,3):
            base,witness,old,new=_pair(mode)
            args=dict(base_raw=base.canonical_bytes(),witness_raw=witness.canonical_bytes(),
                old_principal_raw=old.canonical_bytes(),proposed_principal_raw=new.canonical_bytes(),
                old_signature=_sign(_key(1),_statement(witness,1)),
                new_signature=_sign(_key(2),_statement(witness,2)))
            self.assertFalse(verify_normal_rotation_signature_pair(**args))
    def test_signed_untrusted_native_facts_do_not_become_native_evidence(self):
        # The module intentionally has no clock/current-state/store. These invented
        # operation/challenge values and old synthetic times can carry a valid KEY
        # signature; an actual consent consumer must still reject unauthenticated facts.
        base,witness,_,new=_pair(3)
        witness=replace(witness,operation_id=bytes(32),post_eta_challenge_commitment=bytes(32))
        self.assertTrue(_verify(base,witness,new,2,_sign(_key(2),_statement(witness,2))))

if __name__=='__main__':unittest.main()

