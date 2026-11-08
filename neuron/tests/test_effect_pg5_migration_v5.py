"""Migration protocol regressions using controlled driver doubles only.

These tests are source-preparation artifacts. They do not connect to PostgreSQL
and do not establish PostgreSQL snapshot, lock, role, or concurrency behavior.
"""
import sys
import types
import os
import hashlib
import json
import unittest
from unittest.mock import patch

from neuron.tests import test_effect_authority_store_v5 as base_fixtures

S = base_fixtures.S
DriverError = base_fixtures.DriverError


class TraceConnection:
    """One pinned synthetic backend; no real driver connection is possible."""
    def __init__(self, *, existing=(None,) * 8, failure=None, pid=7412,
                 mismatch_phase=None, meta_ok=True):
        self.existing = existing
        self.failure = failure
        self.pid = pid
        self.mismatch_phase = mismatch_phase
        self.meta_ok = meta_ok
        self.trace = []
        self.mode = 'unconfigured'
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.session_lock = False
        self.transaction_lock_seen = False
        self.closed = False
        self.cursor_object = TraceCursor(self)
        self.ddl_issued=0
        self.pid_reads=0
        self.meta_override=None

    def set_session(self, **settings):
        if self.failure=='SESSION':
            raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')
        self.autocommit=settings.get('autocommit')
        if settings.get('autocommit') is True:
            self.mode = 'autocommit'
        elif settings.get('isolation_level') == 'SERIALIZABLE' and settings.get('autocommit') is False:
            self.mode = 'serializable'
        else:
            self.trace.append(('bad_set_session', self.mode, settings))
        self.trace.append(('set_session', self.mode, dict(settings)))

    def cursor(self):
        if self.closed:
            raise AssertionError('cursor requested after close')
        return self.cursor_object

    def commit(self):
        self.commits += 1
        self.trace.append(('commit', self.mode, self.session_lock))
        if self.failure == 'COMMIT':
            raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')

    def rollback(self):
        self.rollbacks += 1
        self.trace.append(('rollback', self.mode))

    def close(self):
        self.closes += 1
        self.closed = True
        self.session_lock = False
        self.trace.append(('close', self.mode, 'session-lock-released'))
        if self.failure == 'CLOSE':
            raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')


class TraceCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = None
        self.last_query = ''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        c = self.connection
        query = str(query)
        normalized = ' '.join(query.split())
        self.last_query = normalized
        c.trace.append(('sql', c.mode, normalized, params))

        if c.failure == 'SESSION' and c.mode == 'autocommit' and 'pg_roles' in query:
            raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')
        if c.failure == 'BODY' and c.mode == 'autocommit' and 'to_regclass' in query:
            raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')
        if normalized.startswith('CREATE TABLE'):
            c.ddl_issued+=1
            if c.failure=='COLLISION' or c.failure=='COLLISION_AFTER_3' and c.ddl_issued==3:
                raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')

        if 'pg_advisory_xact_lock' in query:
            c.transaction_lock_seen = True
            self.rows = (None,)
        elif 'pg_advisory_lock' in query:
            if c.failure=='LOCK_TIMEOUT':raise DriverError('SYNTHETIC_PRIVATE_LOCK_TIMEOUT')
            c.session_lock = True
            if c.failure=='CONTROL_CHANGED':c.meta_ok=False
            self.rows = (None, c.pid)
        elif 'to_regclass' in query:
            observed_pid = c.pid + 1 if c.mismatch_phase == 'preflight' else c.pid
            if 'pg_backend_pid' in query:
                self.rows = (observed_pid,) + tuple(c.existing)
            else:
                self.rows = tuple(c.existing)
        elif 'pg_backend_pid' in query:
            if c.mode=='serializable':c.pid_reads+=1
            mismatch = (c.mismatch_phase == 'transaction' and c.mode == 'serializable') or (
                c.mismatch_phase == 'preflight' and c.mode == 'autocommit') or (
                c.mismatch_phase=='final' and c.mode=='serializable' and c.pid_reads>1)
            observed_pid = c.pid + 1 if mismatch else c.pid
            if 'session_user::text,current_user::text' in query:
                self.rows = ('fixture_owner', 'fixture_owner', observed_pid)
            else:
                self.rows = (observed_pid,)
        elif 'session_user::text,current_user::text' in query:
            self.rows = ('fixture_owner', 'fixture_owner')
        elif 'has_schema_privilege' in query:
            self.rows = ('fixture_owner', 'fixture_owner', True)
        elif 'FROM pg_catalog.pg_roles WHERE rolname=ANY' in query:
            self.rows = [
                ('fixture_runtime', False, False, False, False),
                ('fixture_owner', False, False, False, False),
            ]
        elif 'WITH RECURSIVE inherited' in query:
            self.rows = (False, False)
        elif "current_setting('server_version_num')" in query:
            self.rows = (180000,)
        elif 'SELECT version,migration_hash,configuration_hash' in query:
            self.rows = (5, c.meta_override if c.meta_override is not None else S.MIGRATION5 if c.meta_ok else b'\0' * 32,
                         base_fixtures.h(b'config'))
        elif normalized.startswith('CREATE TABLE'):
            self.rows = None
        else:
            self.rows = None

    def fetchone(self):
        if isinstance(self.rows, list):
            return self.rows[0] if self.rows else None
        return self.rows

    def fetchall(self):
        return self.rows if isinstance(self.rows, list) else []


class MigrationProtocolV5Test(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.db = base_fixtures.AuthorityStoreV5Test().database()
        # This controlled module lets the production error mapper recognize only
        # our synthetic driver errors. It supplies no connect function.
        self.driver = types.ModuleType('psycopg2')
        self.driver.Error = DriverError
        self.patcher = patch.dict(sys.modules, {'psycopg2': self.driver})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def run_migration(self, connection, *, schema_helpers=True):
        connect_calls = []
        connect = lambda dsn: connect_calls.append(dsn) or connection
        def role_guard(cursor):
            connection.trace.append(('role-guard', connection.mode))
            if connection.failure == 'SESSION':
                raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')
        helpers = (
            patch.object(self.db, '_check_roles_and_migration_session', side_effect=role_guard),
            patch.object(self.db, '_grant_runtime_privileges',
                         side_effect=lambda cursor, role: connection.trace.append(('grant', connection.mode, role))),
        )
        for helper in helpers:
            helper.start()
            self.addCleanup(helper.stop)
        # Exercise the real _verify_schema orchestration while replacing only
        # the detailed catalog algorithms already covered by the source suite.
        if schema_helpers:
            for name in ('_verify_unique_keys', '_verify_check_constraints', '_verify_owners_and_privileges'):
                p = patch.object(self.db, name,
                    side_effect=lambda cursor, _name=name: connection.trace.append(('catalog-guard', _name, connection.mode)))
                p.start()
                self.addCleanup(p.stop)
        pconnect = patch.object(self.db, '_connect_migration', side_effect=connect)
        pconnect.start()
        self.addCleanup(pconnect.stop)
        self.db.migrate('postgresql://fixture.invalid/migration')
        return connect_calls

    @staticmethod
    def sql_events(connection, mode=None):
        return [e for e in connection.trace if e[0] == 'sql' and (mode is None or e[1] == mode)]

    def test_existing_schema_autocommit_lock_then_fresh_inspection_then_lock8(self):
        c = TraceConnection(existing=(101,) * 8)
        self.run_migration(c)
        self.assertEqual(c.trace[0][0:2], ('set_session', 'autocommit'))
        sql = self.sql_events(c)
        lock_i = next(i for i, e in enumerate(sql) if 'pg_advisory_lock' in e[2])
        inspect_i = next(i for i, e in enumerate(sql) if 'to_regclass' in e[2])
        role_i = next(i for i, e in enumerate(c.trace) if e[0] == 'role-guard')
        session_lock_trace_i = next(i for i, e in enumerate(c.trace)
                                    if e[0] == 'sql' and 'pg_advisory_lock' in e[2])
        self.assertLess(role_i, session_lock_trace_i)
        self.assertLess(lock_i, inspect_i)
        self.assertTrue(all(e[1] == 'autocommit' for e in sql[:inspect_i + 1]))
        self.assertIn('pg_backend_pid', sql[lock_i][2])
        self.assertIn('pg_backend_pid', sql[inspect_i][2])
        self.assertFalse(any('pg_advisory_xact_lock' in e[2] for e in sql))
        self.assertFalse(c.transaction_lock_seen)
        serial = self.sql_events(c, 'serializable')
        self.assertGreaterEqual(len(serial), 8 + 1 + 1 + 1)  # locks, role, server, META, optional PID checks
        self.assertTrue(all(e[2].startswith('LOCK TABLE ONLY ') for e in serial[:8]))
        first_select = next(i for i, e in enumerate(serial) if e[2].lstrip().startswith('SELECT'))
        self.assertEqual(first_select, 8)
        self.assertEqual(c.commits, 1)
        self.assertEqual(c.closes, 1)
        self.assertFalse(c.session_lock)
        self.assertEqual([e[0] for e in c.trace if e[0] in ('commit', 'close')], ['commit', 'close'])
        self.assertTrue(next(e for e in c.trace if e[0]=='commit')[2])

    def test_fresh_schema_creates_eight_tables_atomically_without_if_not_exists(self):
        c = TraceConnection(existing=(None,) * 8)
        self.run_migration(c)
        serial = self.sql_events(c, 'serializable')
        creates = [e for e in serial if e[2].startswith('CREATE TABLE')]
        self.assertEqual(len(creates), len(S.DDL5))
        self.assertTrue(all('IF NOT EXISTS' not in e[2].upper() for e in creates))
        first_create = next(i for i, e in enumerate(serial) if e[2].startswith('CREATE TABLE'))
        last_create = max(i for i, e in enumerate(serial) if e[2].startswith('CREATE TABLE'))
        meta = next(i for i, e in enumerate(serial) if 'INSERT INTO ' + S.META5 in e[2])
        locks = [i for i, e in enumerate(serial) if e[2].startswith('LOCK TABLE ONLY ')]
        self.assertLess(first_create, last_create)
        self.assertLess(last_create, meta)
        self.assertGreaterEqual(len(locks), 8)
        self.assertGreater(min(locks), meta)
        self.assertEqual(c.commits, 1)

    def test_partial_schema_rejects_without_ddl_grants_or_commit(self):
        c = TraceConnection(existing=(101, None, None, None, None, None, None, None))
        with self.assertRaises(S.EffectV3Error):
            self.run_migration(c)
        sql = self.sql_events(c)
        self.assertFalse(any(e[2].startswith('CREATE TABLE') for e in sql))
        self.assertFalse(any(e[0] == 'grant' for e in c.trace))
        self.assertEqual(c.commits, 0)
        self.assertEqual(c.rollbacks, 1)
        self.assertEqual(c.closes, 1)

    def test_existing_schema_mismatch_rejects_after_locks_without_repair(self):
        c = TraceConnection(existing=(101,) * 8, meta_ok=False)
        with self.assertRaises(S.EffectV3Error):
            self.run_migration(c)
        serial = self.sql_events(c, 'serializable')
        self.assertTrue(all(e[2].startswith('LOCK TABLE ONLY ') for e in serial[:8]))
        self.assertFalse(any(e[2].startswith('CREATE TABLE') for e in serial))
        self.assertEqual(c.commits, 0)
        self.assertEqual(c.rollbacks, 1)

    def test_fresh_ddl_collision_rolls_back_without_adoption_or_retry(self):
        c = TraceConnection(existing=(None,) * 8, failure='COLLISION')
        connects = []
        p = patch.object(self.db, '_connect_migration', side_effect=lambda dsn: connects.append(dsn) or c)
        p.start(); self.addCleanup(p.stop)
        with patch.object(self.db, '_check_roles_and_migration_session'), \
             patch.object(self.db, '_grant_runtime_privileges'), \
             patch.object(self.db, '_verify_unique_keys'), \
             patch.object(self.db, '_verify_check_constraints'), \
             patch.object(self.db, '_verify_owners_and_privileges'), \
             self.assertRaises(base_fixtures.EffectPersistenceErrorV3) as caught:
            self.db.migrate('postgresql://fixture.invalid/migration')
        self.assertEqual(caught.exception.stage, 'BODY')
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(len(connects), 1)
        self.assertEqual(c.commits, 0)
        self.assertEqual(c.rollbacks, 1)
        self.assertFalse(c.session_lock)

    def test_backend_identity_is_checked_after_preflight_and_before_existing_body(self):
        for mismatch_phase in ('preflight', 'transaction','final'):
            with self.subTest(mismatch_phase=mismatch_phase):
                c = TraceConnection(existing=(101,) * 8, mismatch_phase=mismatch_phase)
                # The synthetic cursor exposes the mismatch at the explicit PID
                # query; a compliant implementation must fail before META/data.
                with self.assertRaises((S.EffectV3Error, base_fixtures.EffectPersistenceErrorV3)):
                    self.run_migration(c)
                self.assertEqual(c.commits, 0)
                self.assertEqual(c.rollbacks, 1)
                self.assertFalse(c.session_lock)

    def test_session_body_commit_and_close_failures_never_retry(self):
        for failure in ('SESSION', 'BODY', 'COMMIT', 'CLOSE'):
            with self.subTest(failure=failure):
                c = TraceConnection(existing=(101,) * 8, failure=failure)
                connects = []
                p = patch.object(self.db, '_connect_migration', side_effect=lambda dsn: connects.append(dsn) or c)
                p.start(); self.addCleanup(p.stop)
                with patch.object(self.db, '_check_roles_and_migration_session'), \
                     patch.object(self.db, '_verify_unique_keys'), \
                     patch.object(self.db, '_verify_check_constraints'), \
                     patch.object(self.db, '_verify_owners_and_privileges'), \
                     self.assertRaises(base_fixtures.EffectPersistenceErrorV3) as caught:
                    self.db.migrate('postgresql://fixture.invalid/migration')
                self.assertEqual(len(connects), 1)
                self.assertEqual(caught.exception.outcome, 'UNKNOWN')
                self.assertNotIn('SYNTHETIC_PRIVATE', str(caught.exception))
                self.assertIsNone(caught.exception.__context__)
                if failure == 'COMMIT':
                    self.assertEqual(caught.exception.stage, 'COMMIT')
                elif failure == 'CLOSE':
                    self.assertEqual(caught.exception.stage, 'CLOSE')
                else:
                    self.assertIn(caught.exception.stage, ('SESSION', 'BODY'))

    def test_no_explicit_session_unlock_or_second_connection(self):
        c = TraceConnection(existing=(101,) * 8)
        connects = self.run_migration(c)
        self.assertEqual(connects, ['postgresql://fixture.invalid/migration'])
        self.assertFalse(any('pg_advisory_unlock' in e[2] for e in self.sql_events(c)))
        self.assertEqual(c.closes, 1)
        self.assertFalse(c.session_lock)

    def test_pre_snapshot_protocol_meta_is_rejected_without_adoption(self):
        # Exact legacy fingerprint algorithm: no session/snapshot discriminator.
        # The consumer must reject that old META even though DDL/ACL/limits match.
        legacy=hashlib.sha256(b'VAMS:AUTHORITY-PG-MIGRATION:v5\0'+
            '\n'.join(S.DDL5).encode('ascii')+b'\0'+
            json.dumps(S.PRIVILEGE_PROFILE5,sort_keys=True,separators=(',',':')).encode('ascii')+b'\0'+
            json.dumps(S.AUTHORITY_LIMITS5,sort_keys=True,separators=(',',':')).encode('ascii')).digest()
        self.assertNotEqual(legacy,S.MIGRATION5)
        c=TraceConnection(existing=(101,)*8);c.meta_override=legacy
        with self.assertRaisesRegex(S.EffectV3Error,'version/configuration mismatch'):
            self.run_migration(c)
        self.assertEqual(c.commits,0)
        self.assertFalse(any(e[0]=='grant' for e in c.trace))
        self.assertFalse(any(e[2].startswith(('CREATE TABLE','INSERT INTO')) for e in self.sql_events(c)))

    def test_session_lock_timeout_never_starts_protected_transaction_or_retries(self):
        c=TraceConnection(existing=(101,)*8,failure='LOCK_TIMEOUT')
        with self.assertRaises(base_fixtures.EffectPersistenceErrorV3) as caught:self.run_migration(c)
        self.assertEqual(caught.exception.outcome,'UNKNOWN')
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(c.commits,0);self.assertEqual(c.closes,1)
        self.assertFalse(any(e[0]=='set_session' and e[1]=='serializable' for e in c.trace))
        self.assertNotIn('SYNTHETIC_PRIVATE',str(caught.exception))

    def test_collision_after_partial_ddl_rolls_back_before_grants_meta_or_commit(self):
        c=TraceConnection(failure='COLLISION_AFTER_3')
        with self.assertRaises(base_fixtures.EffectPersistenceErrorV3):self.run_migration(c)
        self.assertEqual(c.ddl_issued,3);self.assertEqual(c.commits,0)
        self.assertEqual(c.rollbacks,1);self.assertEqual(c.closes,1)
        self.assertFalse(any(e[0]=='grant' for e in c.trace))
        self.assertFalse(any(e[2].startswith('INSERT INTO') for e in self.sql_events(c)))

    def test_changed_control_after_session_wait_rejects_for_meta_reason(self):
        # A control-change double, not an MVCC/two-session PostgreSQL simulation.
        c=TraceConnection(existing=(101,)*8,failure='CONTROL_CHANGED')
        with self.assertRaisesRegex(S.EffectV3Error,'version/configuration mismatch'):
            self.run_migration(c)
        self.assertEqual(c.commits,0);self.assertEqual(c.rollbacks,1)
        serial=self.sql_events(c,'serializable')
        self.assertTrue(all(e[2].startswith('LOCK TABLE ONLY ') for e in serial[:8]))


if __name__ == '__main__':
    unittest.main()
