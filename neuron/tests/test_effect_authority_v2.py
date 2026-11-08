"""Scope/coordinator contracts, not real PostgreSQL qualification."""
import hashlib
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from neuron.effect_authority_v2 import AuthorityScopeV2,execute_local_v2,principal_lock_key
from neuron.effect_proposal import ProtocolError,AuthoritySignerV2
from neuron.effect_gate_v2 import ObjectEffectBoundaryV2
from neuron.tests.test_effect_proposal_v2 import proposal


def scope():
    p=proposal()
    return AuthorityScopeV2(
        p.principal_id,p.principal_root,p.intent_id,p.capability_id,p.target_domain,
        p.target,p.implementation_digest,p.runtime_digest,p.policy_root,
        p.policy_revision,p.authority_epoch,p.fencing_token,p.expires_at,
        p.object_key,10,4)


class ScopeTests(unittest.TestCase):
    def test_shared_lock_preserves_legacy_did_unicode_and_ascii_keys(self):
        import hashlib
        for principal in ("did:example:alice", "principal-\u96ea"):
            with self.subTest(principal=principal):
                expected=int.from_bytes(hashlib.sha256(
                    b"VAMS:EFFECT-PRINCIPAL-LOCK:v2\0"+
                    principal.encode("utf-8")).digest()[:8],"big",signed=True)
                self.assertEqual(expected,principal_lock_key(principal))
        ascii_principal="ascii-principal"
        self.assertEqual(int.from_bytes(hashlib.sha256(
            b"VAMS:EFFECT-PRINCIPAL-LOCK:v2\0"+
            ascii_principal.encode("ascii")).digest()[:8],"big",signed=True),
            principal_lock_key(ascii_principal))

    def test_exact_scope_permits(self):
        scope().permits(proposal())

    def test_changed_authority_is_not_in_scope(self):
        for name,value in {
            "principal_root":b"x"*32,"intent_id":b"x"*32,"capability_id":b"x"*32,
            "implementation_digest":b"x"*32,"runtime_digest":b"x"*32,"policy_root":b"x"*32,
            "policy_revision":2,"authority_epoch":2,"fencing_token":2,
            "cost_units":5,"expires_at":201,
        }.items():
            with self.subTest(field=name),self.assertRaises(ProtocolError):
                scope().permits(replace(proposal(),**{name:value}))

    def test_invalid_scope_never_permits(self):
        for name,value in {
            "principal_id":"../bad","object_prefix":"other/object",
            "budget_limit":True,"max_action_cost":11,"expires_at":-1,
            "runtime_digest":b"x",
        }.items():
            with self.subTest(field=name),self.assertRaises(ProtocolError):
                replace(scope(),**{name:value}).validate()
        for principal in ("did:example:alice", "principal-\u96ea"):
            with self.subTest(v2_principal=principal),self.assertRaises(ProtocolError):
                replace(scope(),principal_id=principal).validate()

    def test_prefix_match_has_resource_boundary(self):
        with self.assertRaises(ProtocolError):
            replace(scope(),object_prefix="test-principal/obj").permits(proposal())


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{"VAMS_ENV":"test"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.signer=AuthoritySignerV2("issuer",b"a"*32)
        self.boundary=ObjectEffectBoundaryV2(str(Path(self.temp.name)/"provider.sqlite"),
            "test-provider",b"d"*32,b"m"*32,self.signer,b"o"*32,clock=lambda:100)
        self.boundary.advance_fence(self.signer.fence(proposal(),1,1,1))
        signer=self.signer

        class TestAuthority:
            """Test-only seam: deliberately NOT a PostgreSQL evidence source."""
            def __init__(self):
                self.reserved=0
                self.unknown=0
                self.committed=0
            def reserve(self,item):
                scope().permits(item)
                self.reserved+=1
                return signer.admit(item,reservation_id=item.operation_id)
            def mark_indeterminate(self,item):
                self.unknown+=1
            def accept_record(self,item,admission,record):
                self.committed+=1
                return record
        self.authority=TestAuthority()

    def test_coordinator_executes_observes_and_commits(self):
        result=execute_local_v2(self.authority,self.boundary,proposal(),b"synthetic-object")
        self.assertEqual(proposal().proposal_digest,result.proposal_digest)
        self.assertEqual(1,self.boundary.effect_count())
        self.assertEqual(1,self.authority.committed)

    def test_lost_ack_uses_lookup_without_resending(self):
        provider=self.boundary
        original=provider.commit
        calls=[]
        def lose_ack(*args):
            calls.append(1)
            original(*args)
            raise TimeoutError("synthetic lost acknowledgement")
        provider.commit=lose_ack
        execute_local_v2(self.authority,provider,proposal(),b"synthetic-object")
        self.assertEqual(1,len(calls))
        self.assertEqual(1,provider.effect_count())
        self.assertEqual(1,self.authority.unknown)
        self.assertEqual(1,self.authority.committed)

    def test_unknown_outcome_retains_reservation(self):
        self.boundary.commit=lambda *args: (_ for _ in ()).throw(TimeoutError("synthetic"))
        with self.assertRaises(ProtocolError):
            execute_local_v2(self.authority,self.boundary,proposal(),b"synthetic-object")
        self.assertEqual(1,self.authority.reserved)
        self.assertEqual(1,self.authority.unknown)
        self.assertEqual(0,self.authority.committed)
        self.assertEqual(0,self.boundary.effect_count())

    def test_fenced_absence_cannot_hide_committed_effect(self):
        self.boundary.commit(proposal(),self.signer.admit(proposal(),
            reservation_id=proposal().operation_id),b"synthetic-object")
        ack=self.boundary.advance_fence(self.signer.fence(proposal(),2,2,2))
        with self.assertRaises(ProtocolError):
            self.boundary.observe_fenced_absence(proposal(),ack,b"q"*32)

    def test_absence_requires_current_newer_authenticated_fence(self):
        old=self.boundary.advance_fence(self.signer.fence(proposal(),1,1,1))
        with self.assertRaises(ProtocolError):
            self.boundary.observe_fenced_absence(proposal(),old,b"q"*32)
        ack=self.boundary.advance_fence(self.signer.fence(proposal(),2,2,2))
        observation=self.boundary.observe_fenced_absence(proposal(),ack,b"q"*32)
        self.assertEqual(proposal().proposal_digest,observation.proposal_digest)
        self.assertEqual(ack.receipt_digest,observation.fence_ack_digest)
        self.assertEqual(0,self.boundary.effect_count())
        with self.assertRaises(ProtocolError):
            self.boundary.observe_fenced_absence(proposal(),
                replace(ack,authentication=b"x"*32),b"q"*32)


if __name__=="__main__":
    unittest.main()
