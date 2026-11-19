"""BYTEA-view transport fixtures, not native psycopg2/PostgreSQL qualification.

Real journal parsing/signature/history/budget consumers execute. Only cursor
transport and a bounded database transaction are doubles; no driver registration,
schema oracle bypass claim, signing service, provider or network is introduced.
"""
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

from neuron.tests import test_effect_attempt_journal_v5 as F

J = F.J


def bytea_views(value):
    if type(value) is bytes:
        return memoryview(value)
    if type(value) is tuple:
        return tuple(bytea_views(item) for item in value)
    if type(value) is list:
        return [bytea_views(item) for item in value]
    return value


class ByteaViewCursor(F.JournalCursor):
    def fetchone(self):
        return bytea_views(super().fetchone())

    def fetchall(self):
        return bytea_views(super().fetchall())


class PgByteaV5Tests(unittest.TestCase):
    def setUp(self):
        self.f = F.AttemptJournalV5Test('runTest')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)

    def test_exact_bytes_and_views_normalize_to_immutable_identical_bytes(self):
        raw = F.h(b'public BYTEA fixture')
        self.assertIs(J._stored_bytes(raw, 32), raw)
        self.assertEqual(J._stored_bytes(memoryview(raw), 32), raw)
        backing = bytearray(raw)
        normalized = J._stored_bytes(memoryview(backing), 32)
        backing[0] ^= 1
        self.assertIs(type(normalized), bytes)
        self.assertEqual(normalized, raw)
        self.assertEqual(J._stored_bytes(memoryview(b'')), b'')

    def test_nonbytes_types_and_bytes_subclasses_are_not_coerced(self):
        class BytesSubclass(bytes): pass
        class Coercible:
            calls = 0
            def __bytes__(self):
                self.calls += 1
                return bytes(32)
        coercible = Coercible()
        for value in (None, True, 32, 'x' * 32, [0] * 32, (0,) * 32, bytearray(32), BytesSubclass(32), coercible):
            with self.subTest(type=type(value).__name__), self.assertRaises(J.EffectV3Error):
                J._stored_bytes(value, 32)
        self.assertEqual(coercible.calls, 0)

    def test_length_checks_are_identical_for_bytes_and_views(self):
        for size in (0, 1, 31, 33, 64):
            for wrap in (lambda value: value, memoryview):
                with self.subTest(size=size, wrapped=wrap is memoryview), self.assertRaisesRegex(J.EffectV3Error, 'fixture field has invalid encoding'):
                    J._stored_bytes(wrap(bytes(size)), 32, 'fixture field')

    def test_released_view_is_a_controlled_encoding_error(self):
        value = memoryview(bytes(32)); value.release()
        with self.assertRaisesRegex(J.EffectV3Error, '^released field has invalid encoding$') as caught:
            J._stored_bytes(value, 32, 'released field')
        self.assertTrue(caught.exception.__suppress_context__)

    def test_exact_noncontiguous_view_uses_only_its_own_bytes(self):
        source = bytes(range(64))
        view = memoryview(source)[::2]
        self.assertEqual(J._stored_bytes(view, 32), source[::2])
        self.assertIs(type(J._stored_bytes(view, 32)), bytes)

    def test_generation_consumer_authenticates_identical_bytea_view_facts(self):
        f = self.f
        baseline = f.journal._load_generation(F.JournalCursor(f.rows), f.scope.scope_id, f.generation_id, f.now)
        observed = f.journal._load_generation(ByteaViewCursor(f.rows), f.scope.scope_id, f.generation_id, f.now)
        self.assertEqual(observed, baseline)
        self.assertEqual(observed.scope.canonical_bytes(), f.scope.canonical_bytes())
        self.assertEqual(observed.acknowledgement.canonical_bytes(), f.receipts['ack'].canonical_bytes())

    def test_head_consumer_preserves_exact_budget_and_locking_variants(self):
        f = self.f
        for locked in (False, True):
            with self.subTest(for_update=locked):
                baseline = f.journal._load_head(F.JournalCursor(f.rows), f.scope.scope_id, for_update=locked)
                observed = f.journal._load_head(ByteaViewCursor(f.rows), f.scope.scope_id, for_update=locked)
                self.assertEqual(observed, baseline)
                self.assertTrue(all(type(item) is bytes for item in observed[:2]))

    def test_real_history_accepts_all_bytea_views_without_changing_state(self):
        f = self.f; before = deepcopy(vars(f.rows))
        baseline = f.journal._history(F.JournalCursor(f.rows), f.attempt.attempt_id, f.now)
        observed = f.journal._history(ByteaViewCursor(f.rows), f.attempt.attempt_id, f.now)
        self.assertEqual(observed, baseline)
        self.assertEqual(observed[0].outcome, 'pending')
        self.assertFalse(observed[0].native_verified)
        self.assertEqual(vars(f.rows), before)

    def test_view_transport_does_not_bypass_digest_nonce_event_or_head_validation(self):
        f = self.f; before = deepcopy(vars(f.rows))
        for field in ('proposal_digest', 'nonce', 'event_digest', 'head_unit'):
            vars(f.rows).clear(); vars(f.rows).update(deepcopy(before))
            if field in ('proposal_digest', 'nonce'):
                row = list(f.rows.attempts[f.attempt.attempt_id]); row[14 if field == 'proposal_digest' else 17] = F.h(b'wrong retained ' + field.encode())
                f.rows.attempts[f.attempt.attempt_id] = tuple(row)
            elif field == 'event_digest':
                row = list(f.rows.events[f.attempt.attempt_id][0]); row[5] = F.h(b'wrong event digest')
                f.rows.events[f.attempt.attempt_id][0] = tuple(row)
            else:
                row = list(f.rows.heads[f.scope.scope_id]); row[1] = F.h(b'wrong budget unit')
                f.rows.heads[f.scope.scope_id] = tuple(row)
            mutated = deepcopy(vars(f.rows))
            with self.subTest(field=field), self.assertRaises(J.EffectV3Error):
                f.journal._history(ByteaViewCursor(f.rows), f.attempt.attempt_id, f.now)
            self.assertEqual(vars(f.rows), mutated)

    def test_released_views_fail_in_actual_generation_head_and_history_consumers(self):
        f = self.f; before = deepcopy(vars(f.rows))
        for field in ('scope', 'head', 'operation'):
            vars(f.rows).clear(); vars(f.rows).update(deepcopy(before))
            value = memoryview(bytes(32)); value.release()
            if field == 'scope':
                key = (f.scope.scope_id, f.generation_id)
                row = list(f.rows.generations[key]); row[0] = value; f.rows.generations[key] = tuple(row)
                call = lambda: f.journal._load_generation(ByteaViewCursor(f.rows), f.scope.scope_id, f.generation_id, f.now)
                label = 'scope encoding'
            elif field == 'head':
                row = list(f.rows.heads[f.scope.scope_id]); row[0] = value; f.rows.heads[f.scope.scope_id] = tuple(row)
                call = lambda: f.journal._load_head(ByteaViewCursor(f.rows), f.scope.scope_id, for_update=False)
                label = 'head generation'
            else:
                row = list(f.rows.attempts[f.attempt.attempt_id]); row[1] = value; f.rows.attempts[f.attempt.attempt_id] = tuple(row)
                call = lambda: f.journal._history(ByteaViewCursor(f.rows), f.attempt.attempt_id, f.now)
                label = 'operation ID'
            with self.subTest(field=field), self.assertRaisesRegex(J.EffectV3Error, '^' + label + ' has invalid encoding$'):
                call()
            self.assertEqual(f.rows.event_insert_count, 0)
            self.assertEqual(f.rows.head_update_count, 0)

    def test_real_completion_reconciliation_with_views_spends_once(self):
        f = self.f
        @contextmanager
        def transaction(_database):
            yield ByteaViewCursor(f.rows)
        with patch.object(F.PostgresEffectDatabaseV3, 'transaction', transaction), \
             patch.object(F.PostgresEffectDatabaseV3, '_connect', side_effect=AssertionError('NO NATIVE PG IN FIXTURE')):
            result = f.journal.accept_effect(f.attempt.attempt_id, f.receipts['effect'])
            duplicate = f.journal.accept_effect(f.attempt.attempt_id, f.receipts['effect'])
            retained = f.journal.read_attempt(f.attempt.attempt_id)
        self.assertEqual(result.outcome, 'completed')
        self.assertEqual(duplicate, result)
        self.assertEqual(retained, result)
        self.assertFalse(result.native_verified)
        self.assertEqual(f.rows.heads[f.scope.scope_id][3:], (0, f.proposal.cost_units))
        self.assertEqual((f.rows.event_insert_count, f.rows.completion_insert_count, f.rows.head_update_count), (1, 1, 1))


if __name__ == '__main__':
    unittest.main()
