"""Public-boundary tests for the additive local EffectProposal v2 contract."""
import hashlib
import os
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from neuron.effect_proposal import (
    EffectProposalV2, AdmissionReceiptV2, AuthoritySignerV2, FenceUpdateV2,
    ProviderRecordV2, ProtocolError, arguments_commitment, postcondition_commitment,
)
from neuron.effect_gate_v2 import ObjectEffectBoundaryV2


def proposal(**changes):
    principal = "test-principal"
    content = b"synthetic-object"
    digest = hashlib.sha256(content).digest()
    fields = dict(
        principal_id=principal, principal_root=b'a'*32, intent_id=b"i"*32,
        operation_id="00000000-0000-4000-8000-000000000001",
        capability_id=b"c"*32, implementation_digest=b"m"*32,
        runtime_digest=b"r"*32, authority_epoch=1, policy_root=b"p"*32,
        policy_revision=1, target_domain=b"d"*32, target="test-provider",
        object_key=principal+"/object", arguments_hash=arguments_commitment(
            "test-provider", principal+"/object", digest),
        content_hash=digest, expected_version=0, fencing_token=1,
        cost_units=3, expires_at=200, nonce=b"n"*32,
        expected_postcondition=postcondition_commitment(
            b"d"*32, "test-provider", principal+"/object", digest),
    )
    fields.update(changes)
    return EffectProposalV2(**fields)


class ProposalTests(unittest.TestCase):
    def test_roundtrip_and_stable_versioned_commitment(self):
        item = proposal()
        self.assertEqual(item, EffectProposalV2.from_bytes(item.canonical_bytes()))
        self.assertEqual(b"\x97\x02", item.canonical_bytes()[:2])
        self.assertEqual(32, len(item.proposal_digest))
        self.assertNotEqual(hashlib.sha256(item.canonical_bytes()).digest(), item.proposal_digest)

    def test_all_authority_fields_change_commitment(self):
        original = proposal()
        for field, value in {
            "intent_id": b"x"*32, "operation_id": str(uuid.UUID(int=2)),
            "capability_id": b"x"*32, "implementation_digest": b"x"*32,
            "runtime_digest": b"x"*32, "authority_epoch": 2, "policy_root": b"x"*32,
            "policy_revision": 2, "target_domain": b"x"*32, "fencing_token": 2,
            "cost_units": 4, "expires_at": 201, "nonce": b"x"*32,
        }.items():
            with self.subTest(field=field):
                changed = replace(original, **{field: value})
                # Domain changes require the matching postcondition.
                if field == "target_domain":
                    changed = replace(changed, expected_postcondition=postcondition_commitment(
                        value, changed.target, changed.object_key, changed.content_hash))
                self.assertNotEqual(original.proposal_digest, changed.proposal_digest)

    def test_malformed_values_reject(self):
        for field, value in {
            "cost_units": True, "authority_epoch": -1, "expires_at": 1 << 63,
            "nonce": b"short", "principal_id": "../escape", "object_key": "other/object",
            "operation_id": "not-a-uuid", "expected_version": 1, "schema_version": 1,
            "operation": 1, "arguments_hash": b"x"*32, "expected_postcondition": b"x"*32,
        }.items():
            with self.subTest(field=field), self.assertRaises((ProtocolError, ValueError)):
                replace(proposal(), **{field: value}).canonical_bytes()

    def test_noncanonical_trailing_or_wrong_shape_reject(self):
        for raw in (proposal().canonical_bytes()+b"\x00", b"\x80", b"\xa0", b"\x98\x17\x01"):
            with self.subTest(raw=raw[:4]), self.assertRaises((ProtocolError, ValueError)):
                EffectProposalV2.from_bytes(raw)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"VAMS_ENV": "test"})
        self.environment.start()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.temp.cleanup)
        self.now = 100
        self.signer = AuthoritySignerV2("test-issuer", b"a"*32)
        self.boundary = ObjectEffectBoundaryV2(
            str(Path(self.temp.name)/"provider.sqlite"), "test-provider", b"d"*32,
            b"m"*32, self.signer, b"o"*32, clock=lambda: self.now)
        self.fence(self.signer.fence(proposal(), 1, 1, 1), now=100)

    def commit(self, item, receipt, content, *, now):
        self.now = now
        return self.boundary.commit(item, receipt, content)

    def fence(self, update, *, now):
        self.now = now
        return self.boundary.advance_fence(update)

    def admit(self, item=None):
        item = item or proposal()
        return self.signer.admit(item, reservation_id=item.operation_id)

    def test_exact_allowed_effect_and_idempotent_duplicate(self):
        item = proposal()
        first = self.commit(item, self.admit(item), b"synthetic-object", now=100)
        second = self.commit(item, self.admit(item), b"synthetic-object", now=101)
        self.assertEqual(first, second)
        self.assertEqual(1, self.boundary.effect_count())
        self.assertEqual(hashlib.sha256(b"synthetic-object").digest(), first.content_hash)
        self.assertEqual(item.proposal_digest, first.proposal_digest)
        self.boundary.verify_record(first, item)

    def test_exact_receipt_cannot_authorize_mutated_proposal(self):
        original = proposal()
        receipt = self.admit(original)
        for field, value in {
            "authority_epoch": 2, "policy_revision": 2, "fencing_token": 2,
            "cost_units": 4, "runtime_digest": b"x"*32, "capability_id": b"x"*32,
            "intent_id": b"x"*32, "expires_at": 201, "nonce": b"x"*32,
        }.items():
            with self.subTest(field=field), self.assertRaises(ProtocolError):
                self.commit(replace(original, **{field:value}), receipt,
                                     b"synthetic-object", now=100)
        self.assertEqual(0, self.boundary.effect_count())

    def _assert_writer_lock_rechecks_expiry(self, operation):
        import sqlite3
        from contextlib import contextmanager
        from threading import Event, Thread

        lock_attempted = Event()
        original_transaction = self.boundary._transaction

        @contextmanager
        def traced_transaction():
            # Signal transaction entry, not a clock sample. The production
            # clock must run after BEGIN IMMEDIATE acquires this lock.
            lock_attempted.set()
            with original_transaction() as db:
                yield db

        self.boundary._transaction = traced_transaction
        writer = sqlite3.connect(str(Path(self.temp.name)/"provider.sqlite"),
                                 timeout=3, isolation_level=None)
        writer.execute("BEGIN IMMEDIATE")
        result = {}

        def run():
            try:
                operation()
            except BaseException as error:
                result["error"] = error

        worker = Thread(target=run)
        worker.start()
        self.assertTrue(lock_attempted.wait(timeout=1), "provider did not enter write transaction")
        self.now = 201
        writer.rollback()
        writer.close()
        worker.join(timeout=4)
        self.assertFalse(worker.is_alive(), "provider remained blocked after lock release")
        self.assertIsInstance(result.get("error"), ProtocolError)

    def test_expiry_is_rechecked_after_writer_lock_before_new_effect(self):
        item = proposal()
        admission = self.admit(item)
        self._assert_writer_lock_rechecks_expiry(
            lambda: self.boundary.commit(item, admission, b"synthetic-object"))
        self.assertEqual(0, self.boundary.effect_count())

    def test_expiry_is_rechecked_after_writer_lock_before_fence_advance(self):
        import sqlite3
        update = self.signer.fence(proposal(), 2, 2, 2)
        self._assert_writer_lock_rechecks_expiry(
            lambda: self.boundary.advance_fence(update))
        with sqlite3.connect(str(Path(self.temp.name)/"provider.sqlite")) as db:
            row = db.execute(
                "SELECT epoch,revision,fence FROM vams_effect_v2_fences WHERE principal=?",
                ("test-principal",)).fetchone()
        self.assertEqual((1, 1, 1), row)

    def test_forged_or_changed_admission_rejects_before_effect(self):
        receipt = self.admit()
        for changed in (
            replace(receipt, authentication=b"z"*32),
            replace(receipt, issuer_id="other"),
            replace(receipt, cost_units=4),
            replace(receipt, reservation_id=str(uuid.UUID(int=3))),
        ):
            with self.subTest(receipt=changed.issuer_id), self.assertRaises(ProtocolError):
                self.commit(proposal(), changed, b"synthetic-object", now=100)
        self.assertEqual(0, self.boundary.effect_count())

    def test_wrong_content_expiry_missing_fence_and_target_reject(self):
        item = proposal()
        for content, now in ((b"changed",100),(b"synthetic-object",200)):
            with self.subTest(now=now), self.assertRaises(ProtocolError):
                self.commit(item,self.admit(item),content,now=now)
        for changed in (proposal(authority_epoch=2),proposal(implementation_digest=b"x"*32)):
            with self.assertRaises(ProtocolError):
                self.commit(changed,self.admit(changed),b"synthetic-object",now=100)
        self.assertEqual(0,self.boundary.effect_count())

    def test_fence_update_is_authenticated_and_strictly_monotonic(self):
        update=self.signer.fence(proposal(),2,2,2)
        with self.assertRaises(ProtocolError):
            self.fence(replace(update,authentication=b"x"*32),now=100)
        acknowledgement=self.fence(update,now=100)
        self.boundary.verify_fence_ack(acknowledgement,update)
        with self.assertRaises(ProtocolError):
            self.commit(proposal(),self.admit(),b"synthetic-object",now=100)
        with self.assertRaises(ProtocolError):
            self.fence(self.signer.fence(proposal(),1,1,1),now=100)
        self.assertEqual(0,self.boundary.effect_count())

    def test_old_committed_receipt_can_be_read_after_revocation_without_effect(self):
        item=proposal()
        receipt=self.commit(item,self.admit(),b"synthetic-object",now=100)
        self.fence(self.signer.fence(item,2,2,2),now=101)
        self.assertEqual(receipt,self.boundary.lookup(item.operation_id))
        self.assertEqual(receipt,self.commit(item,self.admit(),b"synthetic-object",now=250))
        self.assertEqual(1,self.boundary.effect_count())

    def test_new_operation_cannot_overwrite_immutable_key(self):
        self.commit(proposal(),self.admit(),b"synthetic-object",now=100)
        changed=proposal(operation_id=str(uuid.UUID(int=4)),nonce=b"x"*32)
        with self.assertRaises(ProtocolError):
            self.commit(changed,self.admit(changed),b"synthetic-object",now=100)
        self.assertEqual(1,self.boundary.effect_count())

    def test_same_operation_cannot_be_rebound(self):
        self.commit(proposal(),self.admit(),b"synthetic-object",now=100)
        changed=proposal(cost_units=4)
        with self.assertRaises(ProtocolError):
            self.commit(changed,self.admit(changed),b"synthetic-object",now=100)
        self.assertEqual(1,self.boundary.effect_count())

    def test_receipt_tamper_and_wrong_obligation_reject(self):
        record=self.commit(proposal(),self.admit(),b"synthetic-object",now=100)
        with self.assertRaises(ProtocolError):
            self.boundary.verify_record(replace(record,content_hash=b"x"*32),proposal())
        with self.assertRaises(ProtocolError):
            self.boundary.verify_record(record,proposal(cost_units=4))

    def test_unknown_lookup_is_absent_and_read_does_not_create_effect(self):
        self.assertIsNone(self.boundary.lookup(str(uuid.UUID(int=100))))
        self.assertEqual(0,self.boundary.effect_count())

    def test_live_mode_never_instantiates_local_boundary(self):
        with patch.dict(os.environ,{"VAMS_ENV":"testnet"}),self.assertRaises(ProtocolError):
            ObjectEffectBoundaryV2(str(Path(self.temp.name)/"blocked.sqlite"),
                "test-provider",b"d"*32,b"m"*32,self.signer,b"o"*32)
        self.assertFalse((Path(self.temp.name)/"blocked.sqlite").exists())

    def test_concurrent_duplicates_commit_exactly_one_object(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        item=proposal()
        admission=self.admit(item)
        def run():
            barrier.wait(timeout=3)
            return self.boundary.commit(item,admission,b"synthetic-object")
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures=[workers.submit(run) for _ in range(2)]
            records=[future.result(timeout=5) for future in futures]
        self.assertEqual(records[0],records[1])
        self.assertEqual(1,self.boundary.effect_count())

    def test_nonce_cannot_authorize_a_second_object(self):
        item=proposal()
        self.commit(item,self.admit(item),b"synthetic-object",now=100)
        key="test-principal/second"
        changed=replace(item,operation_id=str(uuid.UUID(int=99)),object_key=key,
            arguments_hash=arguments_commitment(item.target,key,item.content_hash),
            expected_postcondition=postcondition_commitment(
                item.target_domain,item.target,key,item.content_hash))
        with self.assertRaises(ProtocolError):
            self.commit(changed,self.admit(changed),b"synthetic-object",now=100)
        self.assertIsNone(self.boundary.lookup(changed.operation_id))
        self.assertEqual(1,self.boundary.effect_count())

    def test_object_readback_detects_storage_tampering(self):
        import sqlite3
        self.commit(proposal(),self.admit(),b"synthetic-object",now=100)
        with sqlite3.connect(str(Path(self.temp.name)/"provider.sqlite")) as db:
            db.execute("UPDATE vams_effect_v2_objects SET content=?",(b"tampered",))
        with self.assertRaises(ProtocolError):
            self.boundary.lookup(proposal().operation_id)

    def test_committed_effect_survives_reopen(self):
        record=self.commit(proposal(),self.admit(),b"synthetic-object",now=100)
        reopened=ObjectEffectBoundaryV2(str(Path(self.temp.name)/"provider.sqlite"),
            "test-provider",b"d"*32,b"m"*32,self.signer,b"o"*32)
        self.assertEqual(record,reopened.lookup(proposal().operation_id))
        self.assertEqual(1,reopened.effect_count())


if __name__=="__main__":
    unittest.main()
