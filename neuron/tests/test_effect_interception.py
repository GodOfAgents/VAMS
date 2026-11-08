"""Controlled schema replies/body observation, not native PostgreSQL semantics."""
import copy
import unittest
from unittest.mock import patch

from neuron.tests import test_effect_unique_keys as fixtures


class InterceptionCatalogConnection(fixtures.CatalogConnection):
    """Supply only the columns requested by the retained/candidate SELECT.

    Flags describe a fixture table state. This deliberately does not execute SQL,
    install triggers, emulate RLS/rules, or model lock compatibility/DDL races.
    """
    def __init__(self, version, migration, catalog, states=None):
        super().__init__(version, migration, catalog)
        self.states = states or {}
        self.inspect_interception = False

    def execute(self, sql, params=None):
        super().execute(sql, params)
        if "c.contype IN ('p','u')" in sql:
            self.inspect_interception = all(text in sql for text in (
                't.relrowsecurity', 't.relforcerowsecurity',
                'pg_catalog.pg_trigger', 'pg_catalog.pg_rewrite',
            ))

    def fetchall(self):
        additional = fixtures.additional_catalog_rows(self.catalog_query,self.catalog_tables)
        if additional is not None:
            return additional
        rows = [tuple(row[:22]) for row in self.catalog]
        if self.inspect_interception:
            return [row + tuple(self.states.get(row[0], (True,) * 4)) for row in rows]
        return rows


class PersistenceInterceptionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.UniqueKeyPrerequisiteTests('test_valid_catalog_allows_body_and_commit')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def assert_unsafe_state_rejected(self, field, value=False):
        for database, connection, tables in self.fixture.schemas():
            for table in tables:
                with self.subTest(table=table, field=field, value=value):
                    flags = [True] * 4
                    flags[field] = value
                    probe = InterceptionCatalogConnection(
                        *connection.metadata[:2], copy.deepcopy(connection.catalog), {table: flags})
                    self.fixture.rejected_before_body(database, probe)

    def test_row_security_cannot_hide_state_from_the_body(self):
        self.assert_unsafe_state_rejected(0)

    def test_forced_row_security_cannot_authorize_the_body(self):
        self.assert_unsafe_state_rejected(1)

    def test_user_triggers_cannot_intercept_effect_or_authority_writes(self):
        self.assert_unsafe_state_rejected(2)

    def test_rewrite_rules_cannot_redirect_or_suppress_writes(self):
        self.assert_unsafe_state_rejected(3)

    def test_unknown_or_nonboolean_interception_state_cannot_authorize_body(self):
        for field in range(4):
            for value in (None, 1):
                self.assert_unsafe_state_rejected(field, value)

    def test_plain_tables_retain_body_and_commit(self):
        for database, connection, _ in self.fixture.schemas():
            probe = InterceptionCatalogConnection(*connection.metadata[:2], connection.catalog)
            body = []
            with patch.object(database, '_connect', return_value=probe):
                with database.transaction():
                    body.append('protected-body-entered')
            self.assertEqual(body, ['protected-body-entered'])
            self.assertIn(('commit',), probe.events)

    def test_schema_guard_requests_ddl_conflicting_locks_before_reads(self):
        for database, connection, tables in self.fixture.schemas():
            with self.subTest(schema=tables[0]):
                probe = InterceptionCatalogConnection(*connection.metadata[:2], connection.catalog)
                with patch.object(database, '_connect', return_value=probe):
                    with database.transaction():
                        probe.events.append(('protected-body',))
                commands = [event[1] for event in probe.events if event[0] == 'execute']
                self.assertEqual(commands[:len(tables)], [
                    f'LOCK TABLE ONLY {table} IN SHARE UPDATE EXCLUSIVE MODE' for table in tables])


if __name__ == '__main__':
    unittest.main()
