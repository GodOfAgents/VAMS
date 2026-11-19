"""Synthetic catalog/configuration regression tests; not native PG18 proof."""
from dataclasses import replace
import os
import unittest
from unittest.mock import patch

from neuron import effect_authority_store_v5 as S
from neuron.effect_protocol_v3 import EffectV3Error, commitment
from neuron.runtime_safety import RuntimeConfigurationError
from neuron.payments import v5_extension_v1 as E
from neuron.tests import test_effect_attempt_journal_v5 as F
from neuron.tests import test_payment_ledger_v1 as P
from neuron.tests import test_effect_authority_store_v5 as A


class GraphCursor:
    """Full unfiltered catalog rows, deliberately synthetic, with mutations."""
    def __init__(self, manifest):
        self.queries, self.answer = [], None
        self.absent = (None,) * 4
        self.relations = [(t, 'fixture_owner', 'r', 'p', False, False, False, True, True) for t in E.TABLES]
        self.constraints = [tuple(row) + (True, True, False, False, True, 0, 0) for row in manifest.constraints]
        self.keys, self.triggers = [], []
        for oid, (child, cols, parent, refs) in enumerate(S.PostgresAuthorityDatabaseV5._foreign_keys + E.PAYMENT_KEYS, 1):
            self.keys.append((oid, child, list(cols), parent, list(refs), True, True, False, False, 'a', 'a', 's', True))
            for table, function, type_ in ((child, 'check_ins', 5), (child, 'check_upd', 17),
                                          (parent, 'noaction_del', 9), (parent, 'noaction_upd', 17)):
                self.triggers.append((table, oid, True, 'O', 'pg_catalog.RI_FKey_' + function,
                                      type_, False, False, 0, True, True, True))

    def execute(self, query, params=()):
        self.queries.append((query, params))
        if query.startswith('LOCK TABLE '):
            self.answer = None
        elif query.startswith('SELECT pg_catalog.to_regclass'):
            self.answer = self.absent
        elif 't.relowner::regrole' in query:
            self.answer = self.relations
        elif 'pg_catalog.pg_get_constraintdef(c.oid,true)' in query:
            self.answer = self.constraints
        elif "c.contype='f'" in query:
            selected = set(params[0])
            self.answer = [row for row in self.keys if row[1] in selected or row[3] in selected]
        elif 'FROM pg_catalog.pg_trigger tr' in query:
            self.answer = [row for row in self.triggers if row[0] in set(params[0])]
        else:
            raise AssertionError('unhandled synthetic query')

    def fetchone(self):
        return self.answer

    def fetchall(self):
        return self.answer


class PaymentV5ExtensionV1Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)
        self.f = F.AttemptJournalV5Test('runTest')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.manifest = P.synthetic_manifest()

    def configuration(self, manifest=None):
        return S.authority_configuration_v5(self.f.identity, self.f.native_config_hash,
            'fixture_runtime', 'fixture_owner', self.f.check_manifest, payment_manifest=manifest)

    def database(self, stage=None, manifest=None):
        return S.PostgresAuthorityDatabaseV5('postgresql://fixture.invalid/vams', self.configuration(manifest),
            runtime_role='fixture_runtime', migration_role='fixture_owner', check_manifest=self.f.check_manifest,
            payment_manifest=manifest, payment_stage=stage)

    def verify(self, cursor):
        return self.database('present', self.manifest)._verify_foreign_keys_and_triggers(cursor, list(S._TABLES5))

    def test_default_configuration_bytes_and_manifest_binding(self):
        expected = commitment(b'VAMS:AUTHORITY-STORE:v5\0', self.f.identity.digest, self.f.native_config_hash,
            b'fixture_runtime\0fixture_owner', S.MIGRATION5, self.f.check_manifest.digest)
        self.assertEqual(self.configuration(), expected)
        self.assertNotEqual(self.configuration(self.manifest), expected)
        changed = replace(self.manifest, provenance_identity=P.P.h(b'different SYNTHETIC provenance'))
        self.assertNotEqual(self.configuration(self.manifest), self.configuration(changed))
        self.assertEqual(self.database('absent', self.manifest).configuration_hash,
                         self.database('present', self.manifest).configuration_hash)

    def test_explicit_profile_types_versions_stages_and_immutability(self):
        for manifest, stage in ((None, 'present'), (self.manifest, None), (self.manifest, 'auto'),
                                (object(), 'present'), (replace(self.manifest, server_version_num=180001), 'present')):
            with self.subTest(stage=stage, manifest=type(manifest).__name__), self.assertRaises((EffectV3Error, ValueError)):
                E.validate_profile(manifest, stage, 180000)
        db = self.database('absent', self.manifest)
        for name, value in (('payment_stage', 'present'), ('payment_manifest', None)):
            with self.subTest(field=name), self.assertRaises(RuntimeConfigurationError):
                setattr(db, name, value)

    def test_default_v5_rejects_actual_extra_incoming_payment_graph(self):
        cursor = GraphCursor(self.manifest)
        with self.assertRaisesRegex(EffectV3Error, 'foreign keys absent or unexpected'):
            self.database()._verify_foreign_keys_and_triggers(cursor, list(S._TABLES5))

    def test_absent_rejects_every_partial_or_complete_installation(self):
        db = self.database('absent', self.manifest)
        for positions in ((0,), (1,), (2,), (3,), (0, 1, 2, 3)):
            cursor = GraphCursor(self.manifest)
            cursor.absent = tuple(E.TABLES[n] if n in positions else None for n in range(4))
            with self.subTest(positions=positions), self.assertRaisesRegex(EffectV3Error, 'existing relations'):
                db._verify_foreign_keys_and_triggers(cursor, list(S._TABLES5))
        cursor = GraphCursor(self.manifest)
        cursor.keys = cursor.keys[:12]; cursor.triggers = cursor.triggers[:48]
        db._verify_foreign_keys_and_triggers(cursor, list(S._TABLES5))

    def test_present_complete_graph_and_both_trigger_endpoints(self):
        cursor = GraphCursor(self.manifest)
        self.verify(cursor)
        trigger_params = [p for q, p in cursor.queries if 'FROM pg_catalog.pg_trigger tr' in q]
        self.assertEqual(trigger_params, [(list(S._TABLES5) + list(E.TABLES),)])
        self.assertEqual(len(cursor.keys), 16)
        self.assertEqual(len(cursor.triggers), 64)

    def test_present_rejects_missing_extra_and_changed_foreign_keys(self):
        for defect in ('missing', 'extra', 'column', 'cascade', 'unenforced', 'deferrable', 'duplicate_oid'):
            cursor = GraphCursor(self.manifest)
            if defect == 'missing': cursor.keys.pop()
            elif defect == 'extra': cursor.keys.append((99, 'public.unselected', ['x'], S.WORK5, ['operation_id'], True, True, False, False, 'a', 'a', 's', True))
            else:
                row = list(cursor.keys[-1])
                index, value = {'column': (2, ['wrong']), 'cascade': (10, 'c'), 'unenforced': (6, False),
                                'deferrable': (7, True), 'duplicate_oid': (0, 1)}[defect]
                row[index] = value; cursor.keys[-1] = tuple(row)
            with self.subTest(defect=defect), self.assertRaises(EffectV3Error): self.verify(cursor)

    def test_present_rejects_missing_extra_and_changed_triggers(self):
        for defect in ('missing', 'extra', 'function', 'disabled', 'external', 'arguments', 'timing'):
            cursor = GraphCursor(self.manifest)
            if defect == 'missing': cursor.triggers.pop()
            elif defect == 'extra': cursor.triggers.append(cursor.triggers[-1])
            else:
                row = list(cursor.triggers[-1])
                index, value = {'function': (4, 'public.RI_FKey_noaction_upd'), 'disabled': (3, 'D'),
                                'external': (2, False), 'arguments': (8, 1), 'timing': (6, True)}[defect]
                row[index] = value; cursor.triggers[-1] = tuple(row)
            with self.subTest(defect=defect), self.assertRaises(EffectV3Error): self.verify(cursor)

    def test_present_rejects_relation_and_compiled_manifest_drift(self):
        for defect in ('missing', 'owner', 'partition', 'inheritance', 'rule', 'constraint', 'not_enforced'):
            cursor = GraphCursor(self.manifest)
            if defect == 'missing': cursor.relations.pop()
            elif defect in ('constraint', 'not_enforced'):
                row = list(cursor.constraints[0]); row[2 if defect == 'constraint' else 4] = 'changed' if defect == 'constraint' else False
                cursor.constraints[0] = tuple(row)
            else:
                row = list(cursor.relations[0])
                index, value = {'owner': (1, 'wrong'), 'partition': (6, True), 'inheritance': (7, False), 'rule': (8, False)}[defect]
                row[index] = value; cursor.relations[0] = tuple(row)
            with self.subTest(defect=defect), self.assertRaises(EffectV3Error): self.verify(cursor)

    def test_combined_locks_precede_first_ordinary_select_and_graph_precedes_meta(self):
        db = self.database('present', self.manifest)
        queries = []
        class Cursor:
            answer = None
            def execute(_, query, params=()):
                queries.append(query)
                if query.startswith('SELECT session_user'): _.answer = ('fixture_runtime',) * 2
                elif "current_setting('server_version_num')" in query: _.answer = (180000,)
                elif query.startswith('SELECT version,migration_hash'): _.answer = (5, S.MIGRATION5, db.configuration_hash)
            def fetchone(_): return _.answer
        def graph(_, cursor):
            self.assertFalse(any(q.startswith('SELECT version,migration_hash') for q in queries))
            queries.append('SYNTHETIC GRAPH ORACLE')
        with patch.object(S.PostgresAuthorityDatabaseV5, '_verify_unique_keys', graph), \
             patch.object(S.PostgresAuthorityDatabaseV5, '_verify_check_constraints'), \
             patch.object(S.PostgresAuthorityDatabaseV5, '_verify_owners_and_privileges'):
            db._verify_schema(Cursor())
        first = next(i for i, q in enumerate(queries) if q.startswith('SELECT '))
        self.assertEqual(first, len(S._TABLES5) + len(E.TABLES))
        self.assertEqual(queries[:first], ['LOCK TABLE ONLY ' + t + ' IN SHARE UPDATE EXCLUSIVE MODE'
                                        for t in list(S._TABLES5) + list(E.TABLES)])

    def test_journal_reconstructs_manifest_bound_configuration(self):
        db = self.database('present', self.manifest)
        journal = F.J.PostgresAttemptJournalV5(db, self.f.identity, native_config_hash=self.f.native_config_hash,
            runtime_role='fixture_runtime', migration_role='fixture_owner', check_manifest=self.f.check_manifest)
        self.assertIs(journal.database, db)
        wrong = S.PostgresAuthorityDatabaseV5('postgresql://fixture.invalid/vams', self.configuration(),
            runtime_role='fixture_runtime', migration_role='fixture_owner', check_manifest=self.f.check_manifest,
            payment_manifest=self.manifest, payment_stage='present')
        with self.assertRaisesRegex(EffectV3Error, 'another identity/configuration'):
            F.J.PostgresAttemptJournalV5(wrong, self.f.identity, native_config_hash=self.f.native_config_hash,
                runtime_role='fixture_runtime', migration_role='fixture_owner', check_manifest=self.f.check_manifest)

    def test_ledger_requires_matching_profile_and_present_cannot_migrate(self):
        fixture = P.PaymentLedgerV1Tests('runTest')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        with self.assertRaisesRegex(P.L.PaymentLedgerError, 'matching explicitly configured'):
            P.L.PaymentLedgerV1(self.f.database, self.f.journal, fixture.p.binding(), self.manifest)
        changed = replace(fixture.schema, provenance_identity=P.P.h(b'different SYNTHETIC provenance'))
        with self.assertRaisesRegex(P.L.PaymentLedgerError, 'matching explicitly configured'):
            P.L.PaymentLedgerV1(fixture.f.database, fixture.f.journal, fixture.p.binding(), changed)
        with self.assertRaisesRegex(P.L.PaymentLedgerError, 'explicit absent'):
            fixture.ledger.migrate('postgresql://fixture.invalid/owner')

    def test_post_ddl_graph_validation_precedes_commit_and_failure_rolls_back(self):
        fixture = P.PaymentLedgerV1Tests('runTest')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        fixture.f.database = self.database('absent', self.manifest)
        fixture.f.journal = F.J.PostgresAttemptJournalV5(fixture.f.database, fixture.f.identity,
            native_config_hash=fixture.f.native_config_hash, runtime_role='fixture_runtime',
            migration_role='fixture_owner', check_manifest=fixture.f.check_manifest, clock=lambda: fixture.f.now)
        ledger = fixture.build_ledger()
        class MigrationCursor(A.SimpleCursor):
            def execute(self, query, params=()):
                if isinstance(query, str):
                    return super().execute(query, params)
                # psycopg2.sql grants are only recorded by this transport double.
                self.queries.append((query, params)); self.answer = None
        for fail in (False, True):
            cursor = MigrationCursor(existing=(None,))
            connection = A.ConnectionFixture(cursor)
            def check(db, selected):
                self.assertEqual(connection.commits, 0)
                self.assertTrue(any(isinstance(q, str) and 'CREATE TABLE public.vams_payment_events_v1' in q for q, p in cursor.queries))
                self.assertIs(db, fixture.f.database)
                if fail: raise EffectV3Error('SYNTHETIC post-DDL graph denial')
            with self.subTest(fail=fail), \
                 patch.object(S.PostgresAuthorityDatabaseV5, '_connect_migration', return_value=connection), \
                 patch.object(S.PostgresAuthorityDatabaseV5, '_check_roles_and_migration_session'), \
                 patch.object(S.PostgresAuthorityDatabaseV5, '_verify_schema'), \
                 patch.object(S.PostgresAuthorityDatabaseV5, '_verify_payment_extension_present', check):
                if fail:
                    with self.assertRaisesRegex(EffectV3Error, 'post-DDL graph denial'):
                        ledger.migrate('postgresql://fixture.invalid/owner')
                    self.assertEqual(connection.commits, 0)
                    self.assertEqual(connection.rollbacks, 1)
                else:
                    ledger.migrate('postgresql://fixture.invalid/owner')
                    self.assertEqual(connection.commits, 1)
                self.assertEqual(connection.closes, 1)
        self.assertEqual(ledger.database.payment_stage, 'absent')


if __name__ == '__main__':
    unittest.main()
