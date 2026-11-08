"""Stdlib journal tests with controlled database doubles and public signed fixtures.

These tests do not connect to PostgreSQL, exercise concurrency/ACLs, verify native
finality, or qualify a provider. Fixture keys and evidence are synthetic/public.
"""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import ec

from neuron import effect_attempt_journal_v5 as J
from neuron import effect_authority_store_v5 as S
from neuron.action_context import ActionContextV1
from neuron.effect_attempt_events_v5 import AttemptEventV5, next_event, reserved_payload
from neuron.effect_attempt_payloads_v5 import FencedAbsencePayloadV5
from neuron.effect_attempts_v5 import NativeObjectRowV1, ObjectAttemptV5, logical_work
from neuron.effect_authority_v3 import ObjectAuthorityScopeV3
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_protocol_v3 import EffectV3Error, ObjectEffectV3, ObjectFenceV3, SignedEffectReceiptV3
from neuron.effect_provider_v3 import ObjectProviderIdentityV3
from neuron.runtime_safety import RuntimeConfigurationError
from neuron.signed_receipts import ReceiptVerifierV3


def h(value):
    return hashlib.sha256(value).digest()


def synthetic_checks():
    # Synthetic placeholder definitions only. These intentionally do not
    # qualify a compiled PG18 schema and are never passed to a database.
    definitions = tuple(sorted(
        (table, 'CHECK (1 = ' + str(index + 1) + ')')
        for table, count in S._CHECK_COUNTS5.items()
        for index in range(count)
    ))
    return S.ExpectedChecksV5(S.MIGRATION5, h(b'SYNTHETIC-COMPILER-NOT-QUALIFIED'),
        h(b'SYNTHETIC-PROVENANCE-NOT-QUALIFIED'), 180000, definitions)


def read_fixture():
    return json.loads(Path(__file__).with_name('effect_attempt_v5_fixture.json').read_text(encoding='utf8'))


class MemoryRows:
    def __init__(self):
        self.attempts = {}
        self.work = {}
        self.generations = {}
        self.heads = {}
        self.events = {}
        self.completions = {}
        self.event_insert_count = 0
        self.completion_insert_count = 0
        self.head_update_count = 0


class JournalCursor:
    """SQL-shape-aware memory double; it is not a PostgreSQL emulator."""
    def __init__(self, rows):
        self.rows = rows
        self.result = None
        self.rowcount = -1

    def execute(self, query, params=()):
        self.result = None
        self.rowcount = -1
        if 'pg_advisory_xact_lock' in query:
            return
        if f'FROM {J.ATTEMPTS5} WHERE attempt_id=%s' in query and 'SELECT operation_id,scope_id' in query:
            row = self.rows.attempts.get(params[0])
            self.result = None if row is None else (row[1], row[5])
            return
        if f'FROM {J.ATTEMPTS5} WHERE attempt_id=%s' in query and 'SELECT attempt_id,operation_id' in query:
            self.result = self.rows.attempts.get(params[0])
            return
        if f'FROM {J.ATTEMPTS5}' in query and 'SELECT operation_id,attempt_no,logical_work' in query:
            row = self.rows.attempts.get(params[0])
            self.result = None if row is None else (row[1], row[2], row[3])
            return
        if f'FROM {J.WORK5}' in query:
            self.result = self.rows.work.get(params[0])
            return
        if f'FROM {J.GENERATIONS5}' in query:
            self.result = self.rows.generations.get((params[0], params[1]))
            return
        if f'FROM {J.HEADS5}' in query:
            self.result = self.rows.heads.get(params[0])
            return
        if f'FROM {J.EVENTS5}' in query and 'ORDER BY event_seq' in query:
            attempt_id = params[0]
            limit = params[1]
            self.result = list(self.rows.events.get(attempt_id, ()))[:limit]
            return
        if f'FROM {J.COMPLETIONS5} WHERE operation_id=%s' in query:
            self.result = self.rows.completions.get(params[0])
            return
        if query.startswith(f'INSERT INTO {J.EVENTS5}'):
            (operation_id, attempt_no, attempt_id, event_seq, predecessor_seq,
             kind, payload, payload_digest, event_digest) = params
            row = (event_seq, predecessor_seq, kind, payload, payload_digest, event_digest)
            event_rows = self.rows.events.setdefault(attempt_id, [])
            if any(item[0] == event_seq for item in event_rows):
                raise AssertionError('controlled fixture detected duplicate event insert')
            event_rows.append(row)
            event_rows.sort(key=lambda item: item[0])
            self.rows.event_insert_count += 1
            self.rowcount = 1
            return
        if query.startswith(f'INSERT INTO {J.COMPLETIONS5}'):
            operation_id, attempt_no, attempt_id, event_seq, receipt_bytes, receipt_digest = params
            if operation_id in self.rows.completions:
                raise AssertionError('controlled fixture detected duplicate completion insert')
            self.rows.completions[operation_id] = (attempt_no, attempt_id, event_seq, receipt_bytes, receipt_digest)
            self.rows.completion_insert_count += 1
            self.rowcount = 1
            return
        if query.startswith(f'UPDATE {J.HEADS5}'):
            if 'budget_spent=budget_spent+%s' in query:
                cost, spent_cost, scope_id, required_reserved, max_spent_cost = params
                head = self.rows.heads[scope_id]
                if head[3] < required_reserved or head[4] > head[2] - max_spent_cost:
                    self.rowcount = 0
                    return
                self.rows.heads[scope_id] = (head[0], head[1], head[2], head[3] - cost, head[4] + spent_cost)
            else:
                cost, scope_id, required_reserved = params
                head = self.rows.heads[scope_id]
                if head[3] < required_reserved:
                    self.rowcount = 0
                    return
                self.rows.heads[scope_id] = (head[0], head[1], head[2], head[3] - cost, head[4])
            self.rows.head_update_count += 1
            self.rowcount = 1
            return
        raise AssertionError('unexpected journal SQL shape: ' + query)

    def fetchone(self):
        if isinstance(self.result, list):
            return self.result[0] if self.result else None
        return self.result

    def fetchall(self):
        return self.result


class AttemptJournalV5Test(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.vector = read_fixture()
        self.proposal = ObjectEffectV3.from_bytes(bytes.fromhex(self.vector['proposal']))
        self.receipts = {name: SignedEffectReceiptV3.from_bytes(bytes.fromhex(value['bytes']))
            for name, value in self.vector['receipts'].items()}
        self.cutover_fence = ObjectFenceV3.from_bytes(bytes.fromhex(self.vector['fence']))
        self.authority = ReceiptVerifierV3(bytes.fromhex(self.vector['authority_public_verifier']['sec1_uncompressed_hex']))
        self.provider = ReceiptVerifierV3(bytes.fromhex(self.vector['provider_public_verifier']['sec1_uncompressed_hex']))
        context = self.proposal.context
        self.identity = ObjectProviderIdentityV3(
            context.provider_id, context.host_domain, context.runtime_id,
            context.target, context.chain_id, self.authority, self.provider,
        )
        self.scope = ObjectAuthorityScopeV3(
            context, (self.proposal.resource_id,), context.budget,
            self.proposal.cost_units, self.proposal.fencing_token,
        )
        self.generation_id = J.commitment(J.GENERATION_DOMAIN_V5, self.scope.canonical_bytes())
        self.native_row = NativeObjectRowV1(context.chain_id, context.target, h(b'first-native-allocation'), 0)
        self.attempt = ObjectAttemptV5(self.native_row, self.proposal, self.receipts['admission'], 1, None)
        self.rows = MemoryRows()
        self._seed_attempt()
        self.check_manifest = synthetic_checks()
        self.native_config_hash = h(b'SYNTHETIC-NATIVE-CONFIG-NOT-QUALIFIED')
        config_hash = S.authority_configuration_v5(
            self.identity, self.native_config_hash, 'fixture_runtime', 'fixture_owner', self.check_manifest,
        )
        self.database = S.PostgresAuthorityDatabaseV5(
            'postgresql://fixture.invalid/vams', config_hash,
            runtime_role='fixture_runtime', migration_role='fixture_owner',
            check_manifest=self.check_manifest,
        )
        self.now = 2000
        self.journal = J.PostgresAttemptJournalV5(
            self.database, self.identity, native_config_hash=self.native_config_hash,
            runtime_role='fixture_runtime', migration_role='fixture_owner',
            check_manifest=self.check_manifest, clock=lambda: self.now,
        )

    def _seed_attempt(self):
        proposal_bytes = self.proposal.canonical_bytes()
        admission_bytes = self.receipts['admission'].canonical_bytes()
        row_bytes = self.native_row.canonical_bytes()
        self.rows.attempts[self.attempt.attempt_id] = (
            self.attempt.attempt_id, self.proposal.operation_id, 1,
            logical_work(self.proposal), None, self.scope.scope_id, self.generation_id,
            self.native_row.chain_id, self.native_row.settlement, self.native_row.allocation_id,
            self.native_row.provider_index, row_bytes, h(row_bytes), proposal_bytes,
            self.proposal.digest, admission_bytes, self.receipts['admission'].digest,
            self.proposal.context.nonce, self.proposal.context.budget_unit, self.proposal.cost_units,
        )
        self.rows.work[self.proposal.operation_id] = (
            logical_work(self.proposal), proposal_bytes, self.proposal.digest,
            self.proposal.postcondition, self.proposal.context.budget_unit, self.proposal.cost_units,
        )
        update_bytes = self.receipts['update'].canonical_bytes()
        ack_bytes = self.receipts['ack'].canonical_bytes()
        self.rows.generations[(self.scope.scope_id, self.generation_id)] = (
            self.scope.canonical_bytes(), 'draining', self.cutover_fence.canonical_bytes(),
            update_bytes, ack_bytes, self.generation_id, 1, None, None, None,
        )
        self.rows.heads[self.scope.scope_id] = (
            self.generation_id, self.proposal.context.budget_unit,
            self.scope.budget_limit, self.proposal.cost_units, 0,
        )
        first = AttemptEventV5(self.attempt.attempt_id, 1, None, 'reserved',
            reserved_payload(self.attempt.link_digest, self.generation_id))
        self.rows.events[self.attempt.attempt_id] = [self._event_row(first, None)]

    @staticmethod
    def _event_row(event, predecessor_seq):
        return (event.sequence, predecessor_seq, event.kind, event.payload,
            event.payload_digest, event.digest)

    def _database_transaction(self):
        @contextmanager
        def transaction(_database):
            yield JournalCursor(self.rows)
        return patch.object(PostgresEffectDatabaseV3, 'transaction', transaction)

    def test_construction_is_bound_to_exact_storage_identity_and_never_connects(self):
        with self._database_transaction(), patch.object(PostgresEffectDatabaseV3, '_connect', side_effect=AssertionError('must not connect')):
            state = self.journal.read_attempt(self.attempt.attempt_id)
        self.assertEqual(state.outcome, 'pending')
        self.assertFalse(state.native_verified)
        with self.assertRaises(EffectV3Error):
            J.PostgresAttemptJournalV5(object(), self.identity,
                native_config_hash=self.native_config_hash, runtime_role='fixture_runtime',
                migration_role='fixture_owner', check_manifest=self.check_manifest)

    def test_configuration_mismatch_and_live_mode_fail_closed(self):
        bad = S.PostgresAuthorityDatabaseV5('postgresql://fixture.invalid/vams', h(b'wrong'),
            runtime_role='fixture_runtime', migration_role='fixture_owner', check_manifest=self.check_manifest)
        with self.assertRaises(EffectV3Error):
            J.PostgresAttemptJournalV5(bad, self.identity,
                native_config_hash=self.native_config_hash, runtime_role='fixture_runtime',
                migration_role='fixture_owner', check_manifest=self.check_manifest)
        with patch.object(J, 'load_runtime_policy', return_value=SimpleNamespace(is_live=True)), \
                self.assertRaises(RuntimeConfigurationError):
            J.PostgresAttemptJournalV5(self.database, self.identity,
                native_config_hash=self.native_config_hash, runtime_role='fixture_runtime',
                migration_role='fixture_owner', check_manifest=self.check_manifest)

    def test_funding_and_dispatch_payloads_are_not_native_verification(self):
        first = AttemptEventV5(self.attempt.attempt_id, 1, None, 'reserved',
            reserved_payload(self.attempt.link_digest, self.generation_id))
        funded = next_event(first, 'funded', b'caller supplied native JSON is opaque')
        dispatched = next_event(funded, 'dispatched', b'caller supplied dispatch marker is opaque')
        self.rows.events[self.attempt.attempt_id] = [
            self._event_row(first, None), self._event_row(funded, 1), self._event_row(dispatched, 2),
        ]
        with self._database_transaction():
            read = self.journal.read_attempt(self.attempt.attempt_id)
        self.assertEqual(read.outcome, 'pending')
        self.assertFalse(read.native_verified)
        self.assertEqual(read.events[-1].kind, 'dispatched')

    def test_expired_signed_completion_is_historical_terminal_and_spends_once(self):
        first = AttemptEventV5(self.attempt.attempt_id, 1, None, 'reserved',
            reserved_payload(self.attempt.link_digest, self.generation_id))
        funded = next_event(first, 'funded', b'unverified native claim')
        dispatched = next_event(funded, 'dispatched', b'unverified dispatch claim')
        self.rows.events[self.attempt.attempt_id] = [
            self._event_row(first, None), self._event_row(funded, 1), self._event_row(dispatched, 2),
        ]
        receipt = self.receipts['effect']
        self.assertLess(receipt.receipt.expires_at, self.now)
        with self._database_transaction():
            complete = self.journal.accept_effect(self.attempt.attempt_id, receipt)
            duplicate = self.journal.accept_effect(self.attempt.attempt_id, receipt)
        self.assertEqual(complete.outcome, 'completed')
        self.assertFalse(complete.native_verified)
        self.assertEqual(duplicate, complete)
        self.assertEqual(self.rows.heads[self.scope.scope_id][3:], (0, self.proposal.cost_units))
        self.assertEqual(self.rows.event_insert_count, 1)
        self.assertEqual(self.rows.completion_insert_count, 1)
        self.assertEqual(self.rows.head_update_count, 1)

    def test_authentic_completion_survives_missing_local_funding_marker(self):
        # Reconciliation cannot require an unavailable funding observation before
        # retaining an authentic permanent effect. Payment remains UNVERIFIED.
        for unknown in (False, True):
            with self.subTest(unknown=unknown):
                self.rows = MemoryRows()
                self._seed_attempt()
                with self._database_transaction():
                    if unknown:self.journal.mark_funding_unknown(self.attempt.attempt_id)
                    complete=self.journal.accept_effect(self.attempt.attempt_id,self.receipts['effect'])
                    duplicate=self.journal.accept_effect(self.attempt.attempt_id,self.receipts['effect'])
                self.assertEqual(complete,duplicate)
                self.assertEqual(complete.outcome,'completed')
                self.assertFalse(complete.native_verified)
                self.assertEqual(self.rows.heads[self.scope.scope_id][3:],(0,self.proposal.cost_units))
                self.assertEqual(self.rows.completion_insert_count,1)

    def test_unresolved_old_generation_cannot_consume_successor_budget(self):
        # An illegally advanced head must fail before consuming funds reserved
        # for a newer generation. The valid historical completion is still held
        # by its caller for explicit reconciliation; no payment is fabricated.
        first=AttemptEventV5(self.attempt.attempt_id,1,None,'reserved',
            reserved_payload(self.attempt.link_digest,self.generation_id))
        funded=next_event(first,'funded',b'unverified funding')
        self.rows.events[self.attempt.attempt_id]=[self._event_row(first,None),self._event_row(funded,1)]
        g=self.rows.generations[(self.scope.scope_id,self.generation_id)]
        self.rows.generations[(self.scope.scope_id,self.generation_id)]=g[:1]+('revoked',)+g[2:8]+(0,0)
        head=self.rows.heads[self.scope.scope_id]
        self.rows.heads[self.scope.scope_id]=(h(b'successor-generation'),)+head[1:]
        prior=self.rows.heads[self.scope.scope_id]
        with self._database_transaction(),self.assertRaises(EffectV3Error):
            self.journal.accept_effect(self.attempt.attempt_id,self.receipts['effect'])
        self.assertEqual(self.rows.heads[self.scope.scope_id],prior)
        self.assertEqual(self.rows.head_update_count,0)

    def test_expired_exact_acknowledged_absence_releases_once(self):
        payload = FencedAbsencePayloadV5(self.cutover_fence, self.receipts['update'],
            self.receipts['ack'], self.receipts['absence'])
        self.assertLess(self.receipts['absence'].receipt.expires_at, self.now)
        with self._database_transaction():
            absent = self.journal.accept_absence(self.attempt.attempt_id, payload)
            duplicate = self.journal.accept_absence(self.attempt.attempt_id, payload)
        self.assertEqual(absent.outcome, 'absent')
        self.assertFalse(absent.native_verified)
        self.assertEqual(duplicate, absent)
        self.assertEqual(self.rows.heads[self.scope.scope_id][3:], (0, 0))
        self.assertEqual(self.rows.event_insert_count, 1)
        self.assertEqual(self.rows.completion_insert_count, 0)
        self.assertEqual(self.rows.head_update_count, 1)
        self.assertEqual(self.rows.events[self.attempt.attempt_id][-1][2], 'absent')

    def test_absence_without_exact_retained_ack_cannot_release(self):
        row = self.rows.generations[(self.scope.scope_id, self.generation_id)]
        self.rows.generations[(self.scope.scope_id, self.generation_id)] = row[:4] + (None,) + row[5:]
        payload = FencedAbsencePayloadV5(self.cutover_fence, self.receipts['update'],
            self.receipts['ack'], self.receipts['absence'])
        with self._database_transaction(), self.assertRaises(EffectV3Error):
            self.journal.accept_absence(self.attempt.attempt_id, payload)
        self.assertEqual(self.rows.heads[self.scope.scope_id][3:], (self.proposal.cost_units, 0))
        self.assertEqual(self.rows.event_insert_count, 0)

    def test_tampered_attempt_identity_row_proposal_nonce_or_work_rejects(self):
        baseline = self.rows.attempts[self.attempt.attempt_id]
        mutations = {
            'row digest': (11, b'\x00' * 32),
            'proposal digest': (14, h(b'wrong-proposal')),
            'admission digest': (16, h(b'wrong-admission')),
            'nonce': (17, h(b'wrong-nonce')),
            'logical work': (3, h(b'wrong-work')),
        }
        for label, (index, value) in mutations.items():
            with self.subTest(label=label):
                self.rows.attempts[self.attempt.attempt_id] = baseline[:index] + (value,) + baseline[index + 1:]
                with self._database_transaction(), self.assertRaises(EffectV3Error):
                    self.journal.read_attempt(self.attempt.attempt_id)
                self.rows.attempts[self.attempt.attempt_id] = baseline

    def test_tampered_event_payload_hash_chain_and_forged_terminal_reject(self):
        original = list(self.rows.events[self.attempt.attempt_id])
        row = original[0]
        self.rows.events[self.attempt.attempt_id] = [row[:3] + (b'changed',) + row[4:]]
        with self._database_transaction(), self.assertRaises(EffectV3Error):
            self.journal.read_attempt(self.attempt.attempt_id)
        self.rows.events[self.attempt.attempt_id] = original

        first = AttemptEventV5(self.attempt.attempt_id, 1, None, 'reserved',
            reserved_payload(self.attempt.link_digest, self.generation_id))
        funded = next_event(first, 'funded', b'unverified')
        dispatched = next_event(funded, 'dispatched', b'unverified')
        forged = next_event(dispatched, 'completed', b'not a SignedEffectReceiptV3')
        self.rows.events[self.attempt.attempt_id] = [
            self._event_row(first, None), self._event_row(funded, 1),
            self._event_row(dispatched, 2), self._event_row(forged, 3),
        ]
        self.rows.completions[self.proposal.operation_id] = (
            1, self.attempt.attempt_id, 4, forged.payload, h(forged.payload),
        )
        with self._database_transaction(), self.assertRaises(EffectV3Error):
            self.journal.read_attempt(self.attempt.attempt_id)

    def test_missing_completion_row_or_conflicting_terminal_facts_reject_without_overwrite(self):
        first = AttemptEventV5(self.attempt.attempt_id, 1, None, 'reserved',
            reserved_payload(self.attempt.link_digest, self.generation_id))
        funded = next_event(first, 'funded', b'unverified')
        dispatched = next_event(funded, 'dispatched', b'unverified')
        complete = next_event(dispatched, 'completed', self.receipts['effect'].canonical_bytes())
        self.rows.events[self.attempt.attempt_id] = [
            self._event_row(first, None), self._event_row(funded, 1),
            self._event_row(dispatched, 2), self._event_row(complete, 3),
        ]
        with self._database_transaction(), self.assertRaises(EffectV3Error):
            self.journal.read_attempt(self.attempt.attempt_id)
        self.assertNotIn(self.proposal.operation_id, self.rows.completions)

    def test_completed_and_absent_conflicts_preserve_prior_terminal_facts(self):
        first = AttemptEventV5(self.attempt.attempt_id, 1, None, 'reserved',
            reserved_payload(self.attempt.link_digest, self.generation_id))
        funded = next_event(first, 'funded', b'unverified')
        dispatched = next_event(funded, 'dispatched', b'unverified')
        complete = next_event(dispatched, 'completed', self.receipts['effect'].canonical_bytes())
        self.rows.events[self.attempt.attempt_id] = [
            self._event_row(first, None), self._event_row(funded, 1),
            self._event_row(dispatched, 2), self._event_row(complete, 3),
        ]
        self.rows.completions[self.proposal.operation_id] = (
            1, self.attempt.attempt_id, 4, complete.payload, self.receipts['effect'].digest,
        )
        prior_events = list(self.rows.events[self.attempt.attempt_id])
        prior_head = self.rows.heads[self.scope.scope_id]
        payload = FencedAbsencePayloadV5(self.cutover_fence, self.receipts['update'],
            self.receipts['ack'], self.receipts['absence'])
        with self._database_transaction(), self.assertRaises(EffectV3Error):
            self.journal.accept_absence(self.attempt.attempt_id, payload)
        self.assertEqual(self.rows.events[self.attempt.attempt_id], prior_events)
        self.assertEqual(self.rows.heads[self.scope.scope_id], prior_head)

    def test_wrong_generation_scope_and_budget_metadata_reject(self):
        key = (self.scope.scope_id, self.generation_id)
        original = self.rows.generations[key]
        wrong = ObjectAuthorityScopeV3(self.scope.template, (h(b'other-resource'),),
            self.scope.budget_limit, self.scope.max_action_cost, self.scope.fencing_token)
        self.rows.generations[key] = (wrong.canonical_bytes(),) + original[1:]
        with self._database_transaction(), self.assertRaises(EffectV3Error):
            self.journal.read_attempt(self.attempt.attempt_id)
        self.rows.generations[key] = original
        self.rows.heads[self.scope.scope_id] = (
            self.generation_id, h(b'wrong-budget-unit'), self.scope.budget_limit,
            self.proposal.cost_units, 0,
        )
        with self._database_transaction(), self.assertRaises(EffectV3Error):
            self.journal.read_attempt(self.attempt.attempt_id)

    def test_mark_funding_unknown_is_append_only_and_does_not_release_budget(self):
        with self._database_transaction():
            first = self.journal.mark_funding_unknown(self.attempt.attempt_id)
            duplicate = self.journal.mark_funding_unknown(self.attempt.attempt_id)
        self.assertEqual(first.events[-1].kind, 'funding_unknown')
        self.assertEqual(duplicate, first)
        self.assertEqual(self.rows.heads[self.scope.scope_id][3:], (self.proposal.cost_units, 0))
        self.assertEqual(self.rows.event_insert_count, 1)
        self.assertEqual(self.rows.head_update_count, 0)


if __name__ == '__main__':
    unittest.main()
