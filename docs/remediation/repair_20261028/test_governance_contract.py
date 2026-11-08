"""Reference bytes/value tests only. Never substitute these for Aiken/ledger tests."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from .governance_contract import (
    Config, ContractError, DELAY_MS, LIFETIME_MS, Lock, Value, add_lock,
    authority_preimage, conserves, digest, fixture, intent_preimage,
    proposal_preimage, proposal_state_preimage, proposal_value,
    queue_intent, receipt_preimage, refunds, uint,
)


class GovernanceByteTests(unittest.TestCase):
    def setUp(self):
        self.c, self.p = fixture()

    def test_frozen_preimages_hash_independently(self):
        vectors = json.loads((Path(__file__).parent / 'GOLDEN-VECTORS.json').read_text())
        for row in vectors['asset_vectors']:
            self.assertEqual(hashlib.blake2b(bytes.fromhex(row['preimage_hex']), digest_size=32).hexdigest(), row['digest_hex'])
            self.assertEqual(len(bytes.fromhex(row['digest_hex'])), 32)

    def test_proposal_commits_all_immutable_request_fields(self):
        original = digest(proposal_preimage(self.c, self.p))
        for field in ('nonce', 'proposer', 'description_hash', 'action_hash', 'payload_hash', 'quorum', 'deadline'):
            old = getattr(self.p, field)
            new = old + 1 if type(old) is int else old[:-1] + bytes([old[-1] ^ 1])
            with self.subTest(field=field):
                self.assertNotEqual(digest(proposal_preimage(self.c, replace(self.p, **{field: new}))), original)
        alternate = replace(self.c, target_domains=(b'other/test',))
        self.assertNotEqual(digest(proposal_preimage(alternate, replace(self.p, target_domain=b'other/test'))), original)

    def test_authority_name_binds_seed_network_epoch_policy(self):
        original = digest(authority_preimage(self.c))
        for field, value in (('seed_tx_id', b'x' * 32), ('seed_index', 8), ('network_id', 1),
                             ('policy_epoch', 3), ('authority_policy_id', b'y' * 28)):
            with self.subTest(field=field):
                self.assertNotEqual(digest(authority_preimage(replace(self.c, **{field: value}))), original)

    def test_receipts_bind_voter_amount_direction_index_and_policies(self):
        lock = Lock(self.c.members[0], 100, True, 10, bytes(32))
        original = digest(receipt_preimage(self.c, self.p, lock, 0))
        for changed in (replace(lock, voter=self.c.members[1]), replace(lock, amount=101), replace(lock, support=False)):
            self.assertNotEqual(digest(receipt_preimage(self.c, self.p, changed, 0)), original)
        self.assertNotEqual(digest(receipt_preimage(self.c, self.p, lock, 1)), original)
        self.assertNotEqual(digest(receipt_preimage(replace(self.c, receipt_policy_id=b'R' * 28), self.p, lock, 0)), original)

    def test_vote_preserves_every_previous_record_exactly(self):
        first = add_lock(self.c, self.p, self.c.members[0], 100, True)
        second = add_lock(self.c, first, self.c.members[1], 900, False)
        self.assertEqual(second.locks[:-1], first.locks)
        self.assertEqual((second.yes, second.no), (10, 30))
        self.assertEqual([lock.weight for lock in second.locks], [10, 30])

    def test_duplicate_and_ninth_votes_reject(self):
        p = add_lock(self.c, self.p, self.c.members[0], 100, True)
        with self.assertRaises(ContractError):
            add_lock(self.c, p, self.c.members[0], 100, False)
        for index in range(2, 9):
            p = add_lock(self.c, p, bytes([index]) * 28, 100, True)
        with self.assertRaises(ContractError):
            add_lock(self.c, p, b'\x09' * 28, 100, True)

    def test_uint_and_lock_inputs_do_not_coerce(self):
        for bad in (True, 1.0, -1, 1 << 64):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                uint(bad, 8)
        for bad in (True, 1.0, -1, 0, 1_000_000_001):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                add_lock(self.c, self.p, self.c.members[0], bad, True)

    def test_queue_binds_passed_state_and_48_hour_delay(self):
        passed = replace(add_lock(self.c, self.p, self.c.members[0], 100, True), passed=True)
        intent = queue_intent(self.c, passed, 2000)
        self.assertEqual(intent.execute_after - intent.queue_time, 48 * 60 * 60 * 1000)
        self.assertEqual(intent.lifetime, LIFETIME_MS)
        self.assertEqual(intent.proposal_id, digest(proposal_state_preimage(passed)))
        with self.assertRaises(ContractError):
            queue_intent(self.c, self.p, 2000)
        with self.assertRaises(ContractError):
            queue_intent(self.c, passed, 1999)
        with self.assertRaises(ContractError):
            intent_preimage(self.c, replace(intent, execute_after=intent.queue_time + DELAY_MS // 2))

    def test_intent_binding_mutations_change_name(self):
        passed = replace(add_lock(self.c, self.p, self.c.members[0], 100, True), passed=True)
        intent = queue_intent(self.c, passed, 2000)
        original = digest(intent_preimage(self.c, intent))
        for field in ('proposal_id', 'proposal_asset', 'action_hash', 'payload_hash', 'proposer', 'nonce'):
            old = getattr(intent, field)
            new = old + 1 if type(old) is int else old[:-1] + bytes([old[-1] ^ 1])
            with self.subTest(field=field):
                self.assertNotEqual(digest(intent_preimage(self.c, replace(intent, **{field: new}))), original)
        later = replace(intent, queue_time=2001, execute_after=intent.execute_after + 1)
        self.assertNotEqual(digest(intent_preimage(self.c, later)), original)

    def test_member_and_policy_aliases_reject(self):
        for changed in (replace(self.c, members=(self.c.members[0],) * 5),
                        replace(self.c, receipt_policy_id=self.c.proposal_policy_id),
                        replace(self.c, vams_asset_name=b'x' * 33),
                        replace(self.c, target_domains=(b'',))):
            with self.assertRaises(ContractError):
                changed.validate()

    def test_maximum_voter_reserve_fits_unsigned_value_domain(self):
        replace(self.c, proposal_base_lovelace=(1 << 64) - 9, per_voter_refund_lovelace=1).validate()
        with self.assertRaises(ContractError):
            replace(self.c, proposal_base_lovelace=(1 << 64) - 1, per_voter_refund_lovelace=1).validate()


class GovernanceConservationTests(unittest.TestCase):
    def setUp(self):
        self.c, self.p = fixture()

    def test_vote_requires_real_vams_funding_and_separate_fee_backing(self):
        p = add_lock(self.c, self.p, self.c.members[0], 100, True)
        source = proposal_value(self.c, self.p)
        held = proposal_value(self.c, p)
        funding = Value(5_000_000, ((self.c.vams_policy_id, self.c.vams_asset_name, 100),))
        minted = ((self.c.receipt_policy_id, p.locks[0].receipt, 1),)
        self.assertTrue(conserves((source, funding), (held, Value(3_800_000)), minted, 200_000))
        self.assertFalse(conserves((source, Value(5_000_000)), (held, Value(3_800_000)), minted, 200_000))
        self.assertFalse(conserves((source, funding), (held, Value(4_000_000)), minted, 200_000))

    def test_terminal_refunds_conserve_every_asset_for_zero_to_eight_voters(self):
        for count in range(9):
            p = self.p
            for index in range(count):
                p = add_lock(self.c, p, bytes([index + 1]) * 28, (index + 1) ** 2, index % 2 == 0)
            burned = ((self.c.proposal_policy_id, p.asset, -1),) + tuple((self.c.receipt_policy_id, lock.receipt, -1) for lock in p.locks)
            payouts = refunds(self.c, p) + (Value(3_000_000), Value(800_000))
            with self.subTest(count=count):
                self.assertTrue(conserves((proposal_value(self.c, p), Value(1_000_000)), payouts, burned, 200_000))
                self.assertFalse(conserves((proposal_value(self.c, p), Value(1_000_000)), payouts[:-1], burned, 200_000))

    def test_queue_carries_base_into_intent_and_refunds_locked_tokens(self):
        p = replace(add_lock(self.c, self.p, self.c.members[0], 100, True), passed=True)
        i = queue_intent(self.c, p, 2000)
        authority_asset = digest(authority_preimage(self.c))
        authority = Value(5_000_000, ((self.c.authority_policy_id, authority_asset, 1),))
        target = Value(3_000_000, ((self.c.intent_policy_id, digest(intent_preimage(self.c, i)), 1),))
        minted = ((self.c.proposal_policy_id, p.asset, -1), (self.c.receipt_policy_id, p.locks[0].receipt, -1),
                  (self.c.intent_policy_id, digest(intent_preimage(self.c, i)), 1))
        outputs = (authority,) + refunds(self.c, p) + (target, Value(800_000))
        inputs = (authority, proposal_value(self.c, p), Value(1_000_000))
        self.assertTrue(conserves(inputs, outputs, minted, 200_000))
        self.assertFalse(conserves(inputs, outputs, minted[:-1], 200_000))
        self.assertFalse(conserves(inputs, (authority, target, Value(800_000)), minted, 200_000))

    def test_intent_burn_and_exact_proposer_refund(self):
        token = (self.c.intent_policy_id, b'I' * 32)
        held = Value(3_000_000, ((*token, 1),))
        burned = ((*token, -1),)
        self.assertTrue(conserves((held, Value(1_000_000)), (Value(3_000_000), Value(800_000)), burned, 200_000))
        self.assertFalse(conserves((held, Value(1_000_000)), (Value(2_999_999), Value(800_000)), burned, 200_000))
        self.assertFalse(conserves((held, Value(1_000_000)), (Value(3_000_000), Value(800_000)), (), 200_000))


if __name__ == '__main__':
    unittest.main()
