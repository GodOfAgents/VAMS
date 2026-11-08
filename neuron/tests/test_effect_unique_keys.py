"""Controlled catalog replies and body observation; not native SQL/PG evidence."""
import copy
import os
import unittest
from unittest.mock import patch

from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3,MIGRATION_HASH
from neuron.effect_authority_store_v3 import PostgresAuthorityDatabaseV3,AUTH_MIGRATION_HASH
from neuron.effect_authority_store_v4 import PostgresAuthorityDatabaseV4,MIGRATION4
from neuron.effect_protocol_v3 import EffectV3Error
from neuron.runtime_safety import RuntimeConfigurationError
from neuron.tests.effect_unique_catalog_fixture import unique_catalog_rows,additional_catalog_rows

TABLES=(
 ('public.vams_effect_v3_provider_meta','public.vams_effect_v3_provider_fences','public.vams_effect_v3_provider_objects'),
 ('public.vams_effect_v3_authority_meta','public.vams_effect_v3_authority_scopes','public.vams_effect_v3_authority_operations'),
 ('public.vams_effect_v4_authority_meta','public.vams_effect_v4_authority_generations','public.vams_effect_v4_authority_heads','public.vams_effect_v4_authority_operations'),
)

class CatalogConnection:
    def __init__(self,version,migration,catalog):
        self.metadata=(version,migration,b'c'*32);self.catalog=catalog
        self.events=[];self.catalog_error=None;self.lock_error=None
    def set_session(self,**kwargs):self.events.append(('session',kwargs))
    def cursor(self):return self
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=None):
        self.events.append(('execute',sql,params))
        if 'pg_catalog.pg_constraint' in sql or 'tr.tgconstraint::bigint' in sql:
            self.catalog_query=sql;self.catalog_tables=params[0]
        if sql.startswith('LOCK TABLE') and self.lock_error:raise self.lock_error
        if 'pg_catalog.pg_constraint' in sql and self.catalog_error:raise self.catalog_error
    def fetchone(self):return self.metadata
    def fetchall(self):
        additional=additional_catalog_rows(self.catalog_query,self.catalog_tables)
        return additional if additional is not None else self.catalog
    def commit(self):self.events.append(('commit',))
    def rollback(self):self.events.append(('rollback',))
    def close(self):self.events.append(('close',))

class UniqueKeyPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'VAMS_ENV':'test',**{k:os.environ[k] for k in ('SystemRoot','WINDIR') if k in os.environ}},clear=True)
        self.env.start();self.addCleanup(self.env.stop)
    def schemas(self):
        for cls,version,migration,tables in zip(
            (PostgresEffectDatabaseV3,PostgresAuthorityDatabaseV3,PostgresAuthorityDatabaseV4),
            (3,3,4),(MIGRATION_HASH,AUTH_MIGRATION_HASH,MIGRATION4),TABLES):
            yield cls('postgresql://synthetic-unused',b'c'*32),CatalogConnection(version,migration,unique_catalog_rows(tables)),tables
    def rejected_before_body(self,db,connection,error=EffectV3Error):
        body=[]
        with patch.object(db,'_connect',return_value=connection),self.assertRaises(error):
            with db.transaction():body.append('protected-body-entered')
        self.assertEqual(body,[])
        self.assertNotIn(('commit',),connection.events)
        self.assertIn(('rollback',),connection.events)
    def test_matching_migration_marker_cannot_hide_absent_unique_keys(self):
        for db,connection,tables in self.schemas():
            with self.subTest(schema=tables[0]):
                connection.catalog=[];self.rejected_before_body(db,connection)
    def test_required_key_contract_cannot_be_rebound_after_construction(self):
        for db,connection,tables in self.schemas():
            with self.subTest(schema=tables[0]),self.assertRaises(RuntimeConfigurationError):
                db._uniqueness_keys=()
    def test_each_required_key_must_exist_before_body(self):
        for db,connection,tables in self.schemas():
            rows=connection.catalog
            for index in range(len(rows)):
                with self.subTest(schema=tables[0],key=rows[index][:3]):
                    probe=CatalogConnection(*connection.metadata[:2],rows[:index]+rows[index+1:])
                    self.rejected_before_body(db,probe)
    def test_invalid_index_and_constraint_flags_cannot_authorize_body(self):
        # Every flag describes an enforcement prerequisite, not a trusted marker.
        for db,connection,tables in self.schemas():
            for field,wrong in [(3,False),(4,True),(5,True),(6,'p'),(7,'u'),
                (8,False),(9,False),(10,False),(11,False),(12,False),
                (15,False),(16,False),(17,False),(21,False)]:
                with self.subTest(schema=tables[0],field=field):
                    rows=copy.deepcopy(connection.catalog);row=list(rows[-1]);row[field]=wrong;rows[-1]=tuple(row)
                    self.rejected_before_body(db,CatalogConnection(*connection.metadata[:2],rows))
    def test_nullable_or_wrongly_typed_keys_cannot_authorize_body(self):
        for db,connection,tables in self.schemas():
            for field,wrong in [(18,[False]),(19,[25]),(20,['public.lookalike_ops']),
                (13,0),(14,7),(2,['unrelated_column'])]:
                with self.subTest(schema=tables[0],field=field):
                    rows=copy.deepcopy(connection.catalog);row=list(rows[-1]);row[field]=wrong;rows[-1]=tuple(row)
                    self.rejected_before_body(db,CatalogConnection(*connection.metadata[:2],rows))
    def test_duplicate_or_unexpected_constraints_cannot_authorize_body(self):
        for db,connection,tables in self.schemas():
            for extra in [connection.catalog[0],(tables[0],'u',['singleton'],*connection.catalog[0][3:])]:
                with self.subTest(schema=tables[0],extra=extra[:3]):
                    self.rejected_before_body(db,CatalogConnection(*connection.metadata[:2],connection.catalog+[extra]))
    def test_malformed_catalog_and_integer_boolean_substitutes_reject(self):
        for db,connection,tables in self.schemas():
            variants=[None,[None],connection.catalog[:-1]+[connection.catalog[-1][:-1]]]
            row=list(connection.catalog[-1]);row[8]=1;variants.append(connection.catalog[:-1]+[tuple(row)])
            row=list(connection.catalog[-1]);row[13]=True;variants.append(connection.catalog[:-1]+[tuple(row)])
            for index,rows in enumerate(variants):
                with self.subTest(schema=tables[0],variant=index):
                    self.rejected_before_body(db,CatalogConnection(*connection.metadata[:2],rows))
    def test_catalog_error_does_not_fall_back_to_migration_marker(self):
        for db,connection,tables in self.schemas():
            with self.subTest(schema=tables[0]):
                connection.catalog_error=RuntimeError('fixture catalog unavailable')
                self.rejected_before_body(db,connection,RuntimeError)
    def test_schema_lock_failure_does_not_enter_body(self):
        for db,connection,tables in self.schemas():
            with self.subTest(schema=tables[0]):
                connection.lock_error=RuntimeError('fixture DDL lock unavailable')
                self.rejected_before_body(db,connection,RuntimeError)
    def test_valid_catalog_allows_body_and_commit(self):
        for db,connection,tables in self.schemas():
            body=[]
            with patch.object(db,'_connect',return_value=connection):
                with db.transaction():body.append('protected-body-entered')
            self.assertEqual(body,['protected-body-entered']);self.assertIn(('commit',),connection.events)
    def test_lock_order_and_catalog_binding_precede_body(self):
        for db,connection,tables in self.schemas():
            with patch.object(db,'_connect',return_value=connection):
                with db.transaction():connection.events.append(('protected-body',))
            statements=[e for e in connection.events if e[0]=='execute']
            self.assertEqual([e[1] for e in statements[:len(tables)]],
                [f'LOCK TABLE ONLY {t} IN SHARE UPDATE EXCLUSIVE MODE' for t in tables])
            catalog=[e for e in statements if "c.contype IN ('p','u')" in e[1]]
            self.assertEqual(len(catalog),1);self.assertEqual(catalog[0][2],(list(tables),))
            self.assertLess(connection.events.index(catalog[0]),connection.events.index(('protected-body',)))

if __name__=='__main__':unittest.main()
