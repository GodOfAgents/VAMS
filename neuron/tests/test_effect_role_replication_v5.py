"""Controlled role catalog tests; no actual roles, database or replication use."""
import hashlib,json,os,unittest
from unittest.mock import patch
from neuron.tests import test_effect_authority_store_v5 as B
S=B.S

class RoleCursor(B.CatalogCursor):
    def __init__(self,role=None,value=False,*,missing=False,reachable=None):
        super().__init__();self.role=role;self.value=value;self.missing=missing;self.reachable=reachable
    def execute(self,query,params=()):
        if 'pg_advisory_lock' in query:
            self.queries.append((query,params));self.answer=(None,7412)
        elif 'to_regclass' in query:
            self.queries.append((query,params));self.answer=(7412,)+(101,)*8
        elif query=='SELECT pg_catalog.pg_backend_pid()':
            self.queries.append((query,params));self.answer=(7412,)
        elif query.startswith('LOCK TABLE ONLY '):
            self.queries.append((query,params));self.answer=None
        elif 'SELECT r.oid' in query:
            super().execute(query,params)
            # Model what the actual projection exposes. An omitted attribute
            # cannot be magically supplied by a fixture to make old code fail.
            if params==(self.role,) and 'r.rolreplication' in query:
                self.answer=self.answer[:-1] if self.missing else (*self.answer[:-1],self.value)
        elif 'FROM pg_catalog.pg_roles WHERE rolname=ANY' in query:
            self.queries.append((query,params));rows=[]
            for name in ('fixture_runtime','fixture_owner'):
                row=(name,False,False,False,False)
                if 'rolreplication' in query:
                    if not (self.missing and name==self.role):row+=(self.value if name==self.role else False,)
                rows.append(row)
            self.answer=rows
        elif 'SELECT session_user::text,current_user::text,' in query:
            self.queries.append((query,params));self.answer=('fixture_owner','fixture_owner',True)
        elif 'WITH RECURSIVE migration_inherited' in query:
            self.queries.append((query,params));self.answer=(self.reachable=='fixture_owner' and 'r.rolreplication' in query,)
        elif 'WITH RECURSIVE inherited' in query:
            self.queries.append((query,params));self.answer=(self.reachable=='fixture_runtime' and 'r.rolreplication' in query,False)
        else:super().execute(query,params)
    def __enter__(self):return self
    def __exit__(self,*args):return False

class RoleReplicationV5Test(unittest.TestCase):
    def setUp(self):
        env=patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True);env.start();self.addCleanup(env.stop)
        self.db=B.AuthorityStoreV5Test().database()
    def test_clean_direct_roles_and_memberships_pass_both_guards(self):
        for method in (self.db._check_roles_and_migration_session,self.db._verify_owners_and_privileges):method(RoleCursor())
    def test_runtime_replication_attribute_rejects_in_full_guard(self):
        for value in (True,None,0,'false'):
            with self.subTest(value=value),self.assertRaisesRegex(B.EffectV3Error,'runtime role attributes'):
                self.db._verify_owners_and_privileges(RoleCursor('fixture_runtime',value))
    def test_migration_replication_attribute_rejects_in_full_guard(self):
        for value in (True,None,0,'false'):
            with self.subTest(value=value),self.assertRaisesRegex(B.EffectV3Error,'migration owner role'):
                self.db._verify_owners_and_privileges(RoleCursor('fixture_owner',value))
    def test_missing_attribute_projection_rejects_full_guard(self):
        for name in ('fixture_runtime','fixture_owner'):
            with self.subTest(role=name),self.assertRaises(B.EffectV3Error):
                self.db._verify_owners_and_privileges(RoleCursor(name,missing=True))
    def test_migration_preflight_rejects_both_roles_bad_or_missing_attribute(self):
        for name in ('fixture_runtime','fixture_owner'):
            for value,missing in ((True,False),(None,False),(0,False),('false',False),(False,True)):
                with self.subTest(role=name,value=value,missing=missing),self.assertRaises(B.EffectV3Error):
                    self.db._check_roles_and_migration_session(RoleCursor(name,value,missing=missing))
    def test_runtime_reachable_replication_role_rejects_both_guards(self):
        for method in (self.db._check_roles_and_migration_session,self.db._verify_owners_and_privileges):
            with self.subTest(method=method.__name__),self.assertRaisesRegex(B.EffectV3Error,'membership'):
                method(RoleCursor(reachable='fixture_runtime'))
    def test_migration_reachable_replication_role_rejects_both_guards(self):
        for method in (self.db._check_roles_and_migration_session,self.db._verify_owners_and_privileges):
            with self.subTest(method=method.__name__),self.assertRaisesRegex(B.EffectV3Error,'replication.*membership'):
                method(RoleCursor(reachable='fixture_owner'))
    def test_every_role_projection_and_both_graphs_query_replication(self):
        for method in (self.db._check_roles_and_migration_session,self.db._verify_owners_and_privileges):
            c=RoleCursor();method(c)
            direct=[q for q,p in c.queries if 'SELECT r.oid' in q or 'FROM pg_catalog.pg_roles WHERE rolname=ANY' in q]
            self.assertTrue(direct);self.assertTrue(all('rolreplication' in q for q in direct))
            graphs=[(q,p) for q,p in c.queries if 'WITH RECURSIVE' in q]
            self.assertEqual(len(graphs),2);self.assertTrue(all('r.rolreplication' in q for q,p in graphs))
            self.assertTrue(any(p==('fixture_owner',) for q,p in graphs))
    def test_runtime_membership_result_must_be_exact_false_booleans(self):
        class BadGraph(RoleCursor):
            def execute(self,q,params=()):
                super().execute(q,params)
                if 'WITH RECURSIVE inherited' in q:self.answer=value
        for value in (None,(),(False,),(0,False),(False,None),(False,False,False)):
            for method in (self.db._check_roles_and_migration_session,self.db._verify_owners_and_privileges):
                with self.subTest(value=value,method=method.__name__),self.assertRaisesRegex(B.EffectV3Error,'membership'):
                    method(BadGraph())
    def test_migration_membership_result_must_be_exact_false_boolean(self):
        class BadGraph(RoleCursor):
            def execute(self,q,params=()):
                super().execute(q,params)
                if 'WITH RECURSIVE migration_inherited' in q:self.answer=value
        for value in (None,(),(None,),(0,),(True,),(False,False)):
            for method in (self.db._check_roles_and_migration_session,self.db._verify_owners_and_privileges):
                with self.subTest(value=value,method=method.__name__),self.assertRaisesRegex(B.EffectV3Error,'replication.*membership'):
                    method(BadGraph())
    def test_role_policy_is_explicit_and_changes_migration_fingerprint(self):
        self.assertIn('forbidden_role_attributes',S.PRIVILEGE_PROFILE5)
        self.assertIn('REPLICATION',S.PRIVILEGE_PROFILE5['forbidden_role_attributes'])
        old=dict(S.PRIVILEGE_PROFILE5);old.pop('forbidden_role_attributes',None);old.pop('migration_replication_memberships',None)
        legacy=hashlib.sha256(b'VAMS:AUTHORITY-PG-MIGRATION:v5\0'+'\n'.join(S.DDL5).encode('ascii')+b'\0'+
            json.dumps(old,sort_keys=True,separators=(',',':')).encode('ascii')+b'\0'+
            json.dumps(S.AUTHORITY_LIMITS5,sort_keys=True,separators=(',',':')).encode('ascii')+b'\0'+
            json.dumps(S.MIGRATION_PROTOCOL5,sort_keys=True,separators=(',',':')).encode('ascii')).digest()
        self.assertNotEqual(legacy,S.MIGRATION5)
        class OldMeta(B.SimpleCursor):
            def execute(self,q,params=()):
                super().execute(q,params)
                if 'SELECT version,migration_hash' in q:self.answer=(5,legacy,B.h(b'config'))
        with self.assertRaisesRegex(B.EffectV3Error,'version/configuration'):
            self.db._verify_schema(OldMeta())
    def test_real_migration_entrypoint_denies_before_lock_ddl_grants(self):
        for name in ('fixture_runtime','fixture_owner'):
            c=RoleCursor(name,True);conn=B.ConnectionFixture(c)
            with patch.object(self.db,'_connect_migration',return_value=conn) as connect,\
                    patch.object(self.db,'_verify_schema'),patch.object(self.db,'_grant_runtime_privileges'),\
                    self.assertRaisesRegex(B.EffectV3Error,'selected V5 roles'):self.db.migrate('postgresql://fixture.invalid/owner')
            self.assertEqual(connect.call_count,1);self.assertEqual(conn.commits,0)
            self.assertEqual(conn.rollbacks,1);self.assertEqual(conn.closes,1)
            self.assertFalse(any('pg_advisory_lock' in q or q.startswith(('CREATE TABLE','GRANT','REVOKE')) for q,p in c.queries))

if __name__=='__main__':unittest.main()
