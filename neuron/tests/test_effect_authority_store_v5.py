"""Controlled catalog/driver doubles, not a PostgreSQL migration or qualification."""
from contextlib import contextmanager
import hashlib
import os
import sys
import types
import unittest
from unittest.mock import patch

from neuron import effect_authority_store_v5 as S
from neuron.effect_protocol_v3 import EffectV3Error
from neuron.effect_postgres_v3 import EffectPersistenceErrorV3
from neuron.runtime_safety import RuntimeConfigurationError


def h(value):return hashlib.sha256(value).digest()


def synthetic_checks():
    # Deliberately synthetic constants, NOT expected PostgreSQL output or approved
    # qualification data. A real source-created schema cannot match these rows.
    definitions=tuple(sorted((table,'CHECK ((0 <= '+str(i)+'))')
        for table,count in S._CHECK_COUNTS5.items() for i in range(count)))
    return S.ExpectedChecksV5(S.MIGRATION5,h(b'SYNTHETIC_NOT_A_POSTGRESQL_BUILD'),
        h(b'SYNTHETIC_NOT_A_QUALIFICATION_REPORT'),180000,definitions)


class CatalogCursor:
    """Explicitly synthetic catalog, with independently mutated denial cases."""
    def __init__(self,defect=None):self.defect=defect;self.queries=[];self.answer=None
    def execute(self,query,params=()):
        self.queries.append((query,params))
        if 'SELECT r.oid' in query:
            self.answer=(101,False,False,False,False,True,True,False) if 'r.rolinherit' in query else (102,False,False,False,False,True)
            if 'r.rolreplication' in query:self.answer+= (False,)
        elif 'WITH RECURSIVE migration_inherited' in query:
            self.answer=(False,)
        elif 'WITH RECURSIVE inherited' in query:
            self.answer=(False,self.defect=='membership')
        elif 'owner.rolname::text' in query:
            self.answer=[(t,'fixture_owner','r','p',True,True,True,True,True) for t in S._TABLES5]
            if self.defect=='owner':self.answer[0]=(S.META5,'fixture_runtime','r','p',True,True,True,True,True)
        elif 'has_table_privilege' in query:
            table=params[1]
            if 'WITH GRANT OPTION' in query:self.answer=(self.defect=='table_grant_option',)
            else:
                self.answer=(True,table!=S.META5,False,False,False,False,False,self.defect!='missing_maintain')
                if self.defect=='immutable_update' and table==S.ATTEMPTS5:
                    self.answer=(True,True,True,False,False,False,False,True)
        elif 'a.atttypid::int' in query:
            allowed={S.GENERATIONS5:set(S._GENERATION_UPDATES),S.HEADS5:set(S._HEAD_UPDATES)}
            self.answer=[(table,col,oid,notnull,True,True,True,col in allowed.get(table,set()),False)
                for (table,col),(oid,notnull) in S._COLUMNS5.items()]
            if self.defect=='missing_column':self.answer.pop()
            if self.defect=='extra_column':self.answer.append((S.WORK5,'unreviewed',17,True,True,True,True,False,False))
            if self.defect in ('wrong_type','default','column_grant_option'):
                row=list(self.answer[0]);row[2 if self.defect=='wrong_type' else 4 if self.defect=='default' else 8]=25 if self.defect=='wrong_type' else False if self.defect=='default' else True
                self.answer[0]=tuple(row)
        else:raise AssertionError('unexpected catalog fixture query')
    def fetchone(self):return self.answer
    def fetchall(self):return self.answer


class SimpleCursor:
    def __init__(self,session=('fixture_runtime','fixture_runtime'),existing=None):
        self.session=session;self.existing=existing;self.queries=[];self.answer=None
    def execute(self,query,params=()):
        self.queries.append((query,params))
        if 'SELECT session_user::text,current_user::text' in query:self.answer=self.session
        elif "current_setting('server_version_num')" in query:self.answer=(180000,)
        elif 'SELECT version,migration_hash' in query:self.answer=(5,S.MIGRATION5,h(b'config'))
        elif 'pg_catalog.to_regclass' in query:
            self.answer=(711,)+tuple(self.existing) if query.startswith('SELECT pg_catalog.pg_backend_pid(),') else self.existing
        elif 'SELECT pg_catalog.pg_advisory_lock(' in query:self.answer=(None,711)
        elif query=='SELECT pg_catalog.pg_backend_pid()':self.answer=(711,)
        else:self.answer=None
    def fetchone(self):return self.answer
    def __enter__(self):return self
    def __exit__(self,*args):return False


class DriverError(Exception):pass


class ConnectionFixture:
    def __init__(self,cursor,fail=None):self.c=cursor;self.fail=fail;self.commits=0;self.rollbacks=0;self.closes=0
    def set_session(self,**settings):self.settings=settings;self.autocommit=settings['autocommit']
    def cursor(self):return self.c
    def commit(self):
        self.commits+=1
        if self.fail=='COMMIT':raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')
    def rollback(self):self.rollbacks+=1
    def close(self):
        self.closes+=1
        if self.fail=='CLOSE':raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')


class AuthorityStoreV5Test(unittest.TestCase):
    def setUp(self):
        self.environment=patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True);self.environment.start();self.addCleanup(self.environment.stop)
    def database(self):return S.PostgresAuthorityDatabaseV5('postgresql://fixture.invalid/fixture',h(b'config'),runtime_role='fixture_runtime',migration_role='fixture_owner',check_manifest=synthetic_checks())

    def test_constructor_has_no_connection_and_requires_distinct_roles(self):
        with patch.object(S.PostgresEffectDatabaseV3,'_connect',side_effect=AssertionError('no connection')):
            db=self.database();self.assertEqual(db.runtime_role,'fixture_runtime')
        with self.assertRaises(EffectV3Error):S.PostgresAuthorityDatabaseV5('postgresql://fixture.invalid',h(b'config'),runtime_role='same',migration_role='same',check_manifest=synthetic_checks())

    def test_live_and_invalid_role_names_reject_before_connection(self):
        for name in ('PG_owner','pg_owner','not a role','bad;sql','x'*64):
            with self.subTest(name=name),self.assertRaises(EffectV3Error):
                S.PostgresAuthorityDatabaseV5('postgresql://fixture.invalid',h(b'config'),runtime_role=name,migration_role='fixture_owner',check_manifest=synthetic_checks())
        with patch.dict(os.environ,{'VAMS_ENV':'staging'},clear=True),self.assertRaises(RuntimeConfigurationError):self.database()

    def test_configuration_binds_roles_native_identity_and_migration_profile(self):
        identity=types.SimpleNamespace(digest=h(b'identity'))
        a=S.authority_configuration_v5(identity,h(b'native'),'fixture_runtime','fixture_owner',synthetic_checks())
        b=S.authority_configuration_v5(identity,h(b'other-native'),'fixture_runtime','fixture_owner',synthetic_checks())
        c=S.authority_configuration_v5(identity,h(b'native'),'different_runtime','fixture_owner',synthetic_checks())
        self.assertNotEqual(a,b);self.assertNotEqual(a,c)
        self.assertNotIn('settlement_bytes',S.DDL5[6])
        self.assertIn(S.SETTLEMENTS5,S.DDL5[7])

    def test_owner_session_cannot_masquerade_as_runtime(self):
        db=self.database();cursor=SimpleCursor(('fixture_owner','fixture_owner'))
        with self.assertRaisesRegex(EffectV3Error,'session role'):db._verify_schema(cursor)
        self.assertEqual(len(cursor.queries),9)
        self.assertTrue(all(query.startswith('LOCK TABLE ONLY ') for query,_ in cursor.queries[:8]))
        self.assertEqual(cursor.queries[8][0],'SELECT session_user::text,current_user::text')

    def test_runtime_and_explicit_owner_modes_use_exact_principals(self):
        db=self.database()
        for migration,role in ((False,'fixture_runtime'),(True,'fixture_owner')):
            cursor=SimpleCursor((role,role))
            with patch.object(db,'_verify_unique_keys'),patch.object(db,'_verify_check_constraints'),patch.object(db,'_verify_owners_and_privileges'):
                db._verify_schema(cursor,migration=migration)
            locks=[q for q,_ in cursor.queries if q.startswith('LOCK TABLE ONLY')]
            self.assertEqual(len(locks),8);self.assertTrue(all('SHARE UPDATE EXCLUSIVE MODE' in q for q in locks))

    def test_guard_locks_all_tables_before_first_select_even_role_only(self):
        # An ordinary SELECT without FROM still establishes a SERIALIZABLE
        # snapshot. Counting locks alone did not prove the guard's contract.
        db=self.database()
        for migration,role in ((False,'fixture_runtime'),(True,'fixture_owner')):
            cursor=SimpleCursor((role,role))
            with patch.object(db,'_verify_unique_keys'),patch.object(db,'_verify_check_constraints'),patch.object(db,'_verify_owners_and_privileges'):
                db._verify_schema(cursor,migration=migration)
            first_select=next(i for i,(query,_) in enumerate(cursor.queries) if query.lstrip().startswith('SELECT'))
            locked=cursor.queries[:first_select]
            self.assertEqual(len(locked),8)
            self.assertTrue(all(query.startswith('LOCK TABLE ONLY ') and
                'SHARE UPDATE EXCLUSIVE MODE' in query for query,_ in locked))

    def test_selected_catalog_allowlist_passes_synthetic_guard(self):
        self.database()._verify_owners_and_privileges(CatalogCursor())

    def test_generation_access_index_is_required_by_the_catalog_guard(self):
        db=self.database()
        # This redundant uniqueness key provides the exact scope/generation
        # prefix and closure ordering; a global attempt PK cannot replace it.
        required=(S.ATTEMPTS5,'u',('scope_id','generation_id','operation_id','attempt_id'))
        ops={17:'pg_catalog.bytea_ops',20:'pg_catalog.int8_ops',21:'pg_catalog.int2_ops'}
        rows=[]
        for table,kind,columns in db._uniqueness_keys:
            names=[c[0] for c in columns];types_=[c[1] for c in columns];n=len(columns)
            if (table,kind,tuple(names))==required:continue
            rows.append((table,kind,names,True,False,False,'r','p',True,True,True,True,True,
                n,n,True,True,True,[True]*n,types_,[ops[t] for t in types_],True,True,True,True,True))
        cursor=types.SimpleNamespace(execute=lambda *args:None,fetchall=lambda:rows)
        with patch.object(db,'_verify_foreign_keys_and_triggers'),self.assertRaises(EffectV3Error):
            db._verify_unique_keys(cursor)

    def test_missing_or_changed_expected_check_manifest_rejects_before_connection(self):
        with self.assertRaises(EffectV3Error):
            S.PostgresAuthorityDatabaseV5('postgresql://fixture.invalid',h(b'config'),
                runtime_role='fixture_runtime',migration_role='fixture_owner',check_manifest=None)
        manifest=synthetic_checks()
        from dataclasses import replace
        for change in ({'definitions':()},{'migration_hash':h(b'wrong source')},
                {'compiler_identity':b'\0'*32},{'server_version_num':170000}):
            with self.subTest(change=change),self.assertRaises(EffectV3Error):replace(manifest,**change).validate()

    def test_check_catalog_requires_exact_definitions_and_enforcement(self):
        db=self.database()
        rows=[(table,definition,True,True,False,False,True,0,False,0)
            for table,definition in db.check_manifest.definitions]
        cursor=types.SimpleNamespace(execute=lambda *args:None,fetchall=lambda:rows)
        db._verify_check_constraints(cursor)
        for defect in ('missing','changed','extra','duplicate','not_enforced','not_validated','deferred','inherited'):
            bad=list(rows)
            if defect=='missing':bad.pop()
            elif defect=='extra':bad.append((S.HEADS5,'CHECK (TRUE)',True,True,False,False,True,0,False,0))
            elif defect=='duplicate':bad[-1]=bad[0]
            else:
                item=list(bad[0])
                if defect=='changed':item[1]='CHECK (TRUE)'
                elif defect=='not_enforced':item[3]=False
                elif defect=='not_validated':item[2]=False
                elif defect=='deferred':item[5]=True
                elif defect=='inherited':item[7]=1
                bad[0]=tuple(item)
            cursor=types.SimpleNamespace(execute=lambda *args:None,fetchall=lambda:bad)
            with self.subTest(defect=defect),self.assertRaises(EffectV3Error):db._verify_check_constraints(cursor)

    def test_schema_entrypoint_refuses_dropped_checks_before_accepting_role_profile(self):
        class DroppedChecksCursor(SimpleCursor):
            def execute(self,query,params=()):
                super().execute(query,params)
                if 'pg_get_constraintdef' in query:self.answer=[]
            def fetchall(self):return self.answer
        db=self.database();cursor=DroppedChecksCursor()
        with patch.object(db,'_verify_unique_keys'),patch.object(db,'_verify_owners_and_privileges') as owners,\
                self.assertRaisesRegex(EffectV3Error,'CHECK constraints'):
            db._verify_schema(cursor)
        owners.assert_not_called()

    def test_bad_membership_owner_mutation_or_missing_lock_privilege_reject(self):
        for defect in ('membership','owner','immutable_update','missing_maintain'):
            with self.subTest(defect=defect),self.assertRaises(EffectV3Error):
                self.database()._verify_owners_and_privileges(CatalogCursor(defect))

    def test_extra_missing_changed_column_or_delegation_reject(self):
        for defect in ('missing_column','extra_column','wrong_type','default','table_grant_option','column_grant_option'):
            with self.subTest(defect=defect),self.assertRaises(EffectV3Error):
                self.database()._verify_owners_and_privileges(CatalogCursor(defect))

    def test_migration_connection_pins_tcp_tls_timeouts_and_search_path(self):
        calls=[]
        driver=types.ModuleType('psycopg2');driver.Error=DriverError
        driver.connect=lambda *args,**kwargs:calls.append((args,kwargs)) or object()
        with patch.dict(sys.modules,{'psycopg2':driver}):
            self.database()._connect();S.PostgresAuthorityDatabaseV5._connect_migration('postgresql://fixture.invalid/db?sslmode=disable')
        self.assertEqual(len(calls),2)
        for _,settings in calls:
            self.assertEqual(settings['sslmode'],'verify-full');self.assertEqual(settings['gssencmode'],'disable')
            self.assertEqual(settings['host'],'fixture.invalid');self.assertEqual(settings['connect_timeout'],5)
            self.assertIn('search_path=pg_catalog',settings['options'])

    def test_connect_error_has_bounded_public_message_and_no_driver_context(self):
        driver=types.ModuleType('psycopg2');driver.Error=DriverError
        def fail(*args,**kwargs):raise DriverError('SYNTHETIC_PRIVATE_DRIVER_DIAGNOSTIC')
        driver.connect=fail
        with patch.dict(sys.modules,{'psycopg2':driver}),self.assertRaises(EffectPersistenceErrorV3) as caught:
            self.database()._connect()
        self.assertEqual(caught.exception.stage,'CONNECT');self.assertIsNone(caught.exception.__context__)
        self.assertNotIn('SYNTHETIC_PRIVATE',str(caught.exception))

    def test_partial_schema_never_executes_ddl_or_grants(self):
        db=self.database();cursor=SimpleCursor(existing=(1,None,None,None,None,None,None,None));conn=ConnectionFixture(cursor)
        with patch.object(db,'_connect_migration',return_value=conn),patch.object(db,'_check_roles_and_migration_session'),self.assertRaises(EffectV3Error):
            db.migrate('postgresql://fixture.invalid/migration')
        self.assertFalse(any('CREATE TABLE' in q or q.startswith('GRANT') for q,_ in cursor.queries))
        self.assertEqual(conn.commits,0);self.assertEqual(conn.rollbacks,1)

    def test_uncertain_commit_and_close_never_retry_or_expose_driver_details(self):
        for stage in ('COMMIT','CLOSE'):
            db=self.database();cursor=SimpleCursor(existing=(1,)*8);conn=ConnectionFixture(cursor,stage)
            driver=types.ModuleType('psycopg2');driver.Error=DriverError
            with self.subTest(stage=stage),patch.dict(sys.modules,{'psycopg2':driver}),\
                    patch.object(db,'_connect_migration',return_value=conn) as connect,\
                    patch.object(db,'_check_roles_and_migration_session'),patch.object(db,'_verify_schema'),\
                    self.assertRaises(EffectPersistenceErrorV3) as caught:
                db.migrate('postgresql://fixture.invalid/migration')
            self.assertEqual(connect.call_count,1);self.assertEqual(conn.commits,1)
            self.assertEqual(caught.exception.stage,stage);self.assertEqual(caught.exception.outcome,'UNKNOWN')
            self.assertNotIn('SYNTHETIC_PRIVATE',str(caught.exception))


if __name__=='__main__':unittest.main()
