"""Explicit new PostgreSQL provider schema and transaction ownership for V3.

No connection occurs at construction. No SQLite/driver fallback, automatic legacy
adoption or implicit migration. Real PostgreSQL qualification is still required.
"""
from contextlib import contextmanager
import hashlib
import ipaddress
import re
import sys
from urllib.parse import urlsplit

from neuron.effect_protocol_v3 import EffectV3Error, hash32, MAX_CONTENT_BYTES
from neuron.runtime_safety import ImmutableRuntimeConfiguration, RuntimeConfigurationError, load_runtime_policy

META = 'public.vams_effect_v3_provider_meta'
FENCES = 'public.vams_effect_v3_provider_fences'
OBJECTS = 'public.vams_effect_v3_provider_objects'
DDL = (
    f'''CREATE TABLE {META} (
        singleton SMALLINT PRIMARY KEY CHECK(singleton=1), version SMALLINT NOT NULL CHECK(version=3),
        migration_hash BYTEA NOT NULL CHECK(octet_length(migration_hash)=32),
        configuration_hash BYTEA NOT NULL CHECK(octet_length(configuration_hash)=32))''',
    f'''CREATE TABLE {FENCES} (
        scope_id BYTEA PRIMARY KEY CHECK(octet_length(scope_id)=32),
        fence_bytes BYTEA NOT NULL, update_bytes BYTEA NOT NULL, ack_bytes BYTEA NOT NULL)''',
    f'''CREATE TABLE {OBJECTS} (
        operation_id BYTEA PRIMARY KEY CHECK(octet_length(operation_id)=32),
        scope_id BYTEA NOT NULL REFERENCES {FENCES}(scope_id),
        resource_id BYTEA NOT NULL CHECK(octet_length(resource_id)=32),
        proposal_bytes BYTEA NOT NULL, admission_bytes BYTEA NOT NULL,
        admission_digest BYTEA UNIQUE NOT NULL CHECK(octet_length(admission_digest)=32),
        nonce BYTEA UNIQUE NOT NULL CHECK(octet_length(nonce)=32),
        content BYTEA NOT NULL CHECK(octet_length(content)<={MAX_CONTENT_BYTES}),
        record_bytes BYTEA NOT NULL, UNIQUE(scope_id,resource_id))''',
)
MIGRATION_HASH = hashlib.sha256(b'VAMS:PROVIDER-PG-MIGRATION:v3\0' + '\n'.join(DDL).encode()).digest()


class EffectPersistenceErrorV3(EffectV3Error):
    """Bounded public diagnostic; UNKNOWN never authorizes retry or refund.

    Backend text, SQLSTATE, cursor, query and diagnostic objects are deliberately
    omitted. This protects ordinary exception/log rendering, not a process that
    can inspect traceback locals, native driver state or database/server logs.
    """
    def __init__(self, stage):
        if stage not in ('CONNECT','SESSION','BODY','COMMIT','CLOSE'):
            raise EffectV3Error('unsupported persistence failure stage')
        self.stage = stage
        self.outcome = 'UNKNOWN'
        super().__init__('Effect persistence failure during ' + stage + '; outcome UNKNOWN; reconciliation required')


def _is_postgres_driver_error(error):
    # _connect loads the selected driver. Do not import/initialize another
    # backend while handling an error, and never inspect the exception payload.
    driver = sys.modules.get('psycopg2')
    kind = getattr(driver, 'Error', None)
    return isinstance(kind, type) and issubclass(kind, Exception) and isinstance(error, kind)


class PostgresEffectDatabaseV3(ImmutableRuntimeConfiguration):
    _uniqueness_keys = (
        (META, 'p', (('singleton', 21),)),
        (FENCES, 'p', (('scope_id', 17),)),
        (OBJECTS, 'p', (('operation_id', 17),)),
        (OBJECTS, 'u', (('admission_digest', 17),)),
        (OBJECTS, 'u', (('nonce', 17),)),
        (OBJECTS, 'u', (('scope_id', 17), ('resource_id', 17))),
    )
    _foreign_keys = ((OBJECTS, ('scope_id',), FENCES, ('scope_id',)),)

    _immutable_runtime_fields = frozenset({'runtime_policy', 'configuration_hash', 'dsn', '_uniqueness_keys', '_foreign_keys'})
    _application_name = 'vams-effect-provider-v3'

    def __init__(self, dsn, configuration_hash):
        self.runtime_policy = load_runtime_policy()
        if type(dsn) is not str or not dsn.startswith(('postgresql://', 'postgres://')):
            raise EffectV3Error('explicit PostgreSQL DSN required')
        self.configuration_hash = hash32(configuration_hash, 'provider database identity')
        self.dsn = dsn
        self._freeze_runtime_configuration()

    def _require_runtime(self):
        if load_runtime_policy() != self.runtime_policy:
            raise RuntimeConfigurationError('provider database runtime configuration changed')

    def _connect(self):
        self._require_runtime()
        parameters = dict(connect_timeout=5, application_name=self._application_name,
            options='-c search_path=pg_catalog -c statement_timeout=10000 -c lock_timeout=5000')
        # Keyword arguments override DSN/environment downgrades. Missing CA,
        # hostname mismatch or unavailable TLS rejects; qualification must still
        # establish the reviewed server/CA/client/role identities.
        if self.runtime_policy.is_live:
            # libpq ignores sslmode for Unix sockets and may prefer GSS. Pin a
            # single explicit TCP host/port and exclude those unselected routes.
            try:
                address = urlsplit(self.dsn)
                host, port = address.hostname, address.port
                if not host or not host.isascii():
                    raise ValueError
                try:
                    host = str(ipaddress.ip_address(host))
                except ValueError:
                    labels = host.removesuffix('.').split('.')
                    if len(host) > 254 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels):
                        raise ValueError
                if port is not None and not 1 <= port <= 65535:
                    raise ValueError
            except ValueError:
                raise EffectV3Error('live PostgreSQL requires one explicit TCP hostname/address and valid port') from None
            parameters.update(host=host, port=port or 5432, sslmode='verify-full', gssencmode='disable')
        try:
            import psycopg2
        except ImportError as exc:
            raise EffectV3Error('PostgreSQL driver unavailable; no fallback') from exc
        try:
            return psycopg2.connect(self.dsn, **parameters)
        except psycopg2.Error:
            # Leave the handler before raising the public error. Do not attach
            # native driver diagnostics/cursor or its exception chain.
            pass
        raise EffectPersistenceErrorV3('CONNECT') from None

    @contextmanager
    def _transaction(self):
        self._require_runtime()
        connection = self._connect()
        failure = None
        stage = 'SESSION'
        try:
            connection.set_session(isolation_level='SERIALIZABLE', readonly=False, autocommit=False)
            stage = 'BODY'
            yield connection
            stage = 'COMMIT'
            connection.commit()
        except BaseException as error:
            # No retry or receipt escapes a failed/uncertain transaction. Keep
            # domain failures and process interrupts; bound native diagnostics.
            try: connection.rollback()
            except BaseException: pass
            try: connection.close()
            except BaseException: pass
            if not _is_postgres_driver_error(error):
                raise
            failure = EffectPersistenceErrorV3(stage)
        else:
            try:
                connection.close()
            except Exception as error:
                if not _is_postgres_driver_error(error):
                    raise
                # Commit returned, but no successful result escapes a close
                # failure. Reconcile the original operation; never retry here.
                failure = EffectPersistenceErrorV3('CLOSE')
        if failure is not None:
            raise failure from None

    def _lock_unique_tables(self, cursor):
        # Lock before the first SELECT freezes this SERIALIZABLE snapshot.
        # Literal schema names only; no external identifier enters this SQL.
        # CREATE TRIGGER's SHARE ROW EXCLUSIVE lock is compatible with ROW
        # SHARE. This stronger lock holds the inspected table behavior stable.
        # It serializes guarded transactions sharing a table; native contention
        # and migration/DDL-race qualification remain mandatory.
        for table in dict.fromkeys(key[0] for key in self._uniqueness_keys):
            if not re.fullmatch(r'public\.vams_effect_v[34]_[a-z_]+', table):
                raise EffectV3Error('unsupported persistence table')
            cursor.execute(f'LOCK TABLE ONLY {table} IN SHARE UPDATE EXCLUSIVE MODE')

    def _verify_unique_keys(self, cursor):
        # Check uniqueness and reject unselected write/read interception. This
        # is not whole-schema, privilege or server attestation. Internal foreign
        # key triggers receive an exact relationship/function check below.
        # Native SQL/DDL-race/role/TLS/concurrency qualification remains required.
        tables = list(dict.fromkeys(key[0] for key in self._uniqueness_keys))
        cursor.execute('''SELECT n.nspname::text || '.' || t.relname::text, c.contype::text,
            ARRAY(SELECT a.attname::text FROM pg_catalog.unnest(c.conkey) WITH ORDINALITY k(num,pos)
              JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.num AND NOT a.attisdropped ORDER BY k.pos),
            c.convalidated,c.condeferrable,c.condeferred,t.relkind::text,t.relpersistence::text,
            i.indisunique,i.indisvalid,i.indisready,i.indislive,i.indimmediate,i.indnkeyatts,i.indnatts,
            i.indexprs IS NULL,i.indpred IS NULL,
            NOT EXISTS(SELECT 1 FROM pg_catalog.pg_inherits h WHERE h.inhparent=t.oid OR h.inhrelid=t.oid),
            ARRAY(SELECT a.attnotnull FROM pg_catalog.unnest(c.conkey) WITH ORDINALITY k(num,pos)
              JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.num ORDER BY k.pos),
            ARRAY(SELECT a.atttypid::int FROM pg_catalog.unnest(c.conkey) WITH ORDINALITY k(num,pos)
              JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.num ORDER BY k.pos),
            ARRAY(SELECT ns.nspname::text || '.' || op.opcname::text
              FROM pg_catalog.unnest(i.indclass) WITH ORDINALITY k(opid,pos)
              JOIN pg_catalog.pg_opclass op ON op.oid=k.opid
              JOIN pg_catalog.pg_namespace ns ON ns.oid=op.opcnamespace ORDER BY k.pos),
            am.amname='btree', NOT t.relrowsecurity, NOT t.relforcerowsecurity,
            NOT EXISTS(SELECT 1 FROM pg_catalog.pg_trigger tr
              WHERE tr.tgrelid=t.oid AND NOT tr.tgisinternal),
            NOT EXISTS(SELECT 1 FROM pg_catalog.pg_rewrite rw WHERE rw.ev_class=t.oid)
            FROM pg_catalog.pg_constraint c
            JOIN pg_catalog.pg_class t ON t.oid=c.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace AND c.connamespace=n.oid
            JOIN pg_catalog.pg_index i ON i.indexrelid=c.conindid AND i.indrelid=t.oid
            JOIN pg_catalog.pg_class ix ON ix.oid=i.indexrelid
            JOIN pg_catalog.pg_am am ON am.oid=ix.relam
            WHERE n.nspname::text || '.' || t.relname::text = ANY(%s) AND c.contype IN ('p','u')''', (tables,))
        rows = cursor.fetchall()
        expected = {(table, kind, tuple(c[0] for c in columns)): tuple(c[1] for c in columns)
            for table, kind, columns in self._uniqueness_keys}
        if type(rows) is not list or len(rows) != len(expected):
            raise EffectV3Error('required persistence uniqueness is absent or unexpected')
        seen = set()
        ops = {17:'pg_catalog.bytea_ops',20:'pg_catalog.int8_ops',21:'pg_catalog.int2_ops'}
        true_flags = (3,8,9,10,11,12,15,16,17,21,22,23,24,25)
        for row in rows:
            if type(row) not in (tuple,list) or len(row) != 26:
                raise EffectV3Error('malformed uniqueness catalog response')
            if type(row[0]) is not str or type(row[1]) is not str or type(row[2]) is not list or not all(type(c) is str for c in row[2]):
                raise EffectV3Error('malformed uniqueness key identity')
            key = (row[0],row[1],tuple(row[2]))
            if key not in expected or key in seen:
                raise EffectV3Error('unexpected or duplicate uniqueness key')
            types = expected[key]; count = len(types)
            if (any(row[i] is not True for i in true_flags) or row[4] is not False or row[5] is not False or
                    row[6] != 'r' or row[7] != 'p' or
                    any(type(row[i]) is not int or row[i] != count for i in (13,14)) or
                    type(row[18]) is not list or len(row[18]) != count or any(v is not True for v in row[18]) or
                    type(row[19]) is not list or any(type(v) is not int for v in row[19]) or tuple(row[19]) != types or
                    row[20] != [ops[t] for t in types]):
                raise EffectV3Error('persistence uniqueness enforcement mismatch')
            seen.add(key)
        if seen != set(expected):
            raise EffectV3Error('required persistence uniqueness missing')
        self._verify_foreign_keys_and_triggers(cursor, tables)

    def _verify_foreign_keys_and_triggers(self, cursor, tables):
        expected = set(self._foreign_keys)
        if not expected or any(child not in tables or parent not in tables
                for child, _, parent, _ in expected):
            raise EffectV3Error('unsupported persistence foreign-key contract')
        # Include incoming FKs, including external referencing tables. Their
        # internal action triggers also run on our tables. No arbitrary internal
        # trigger is trusted merely because tgisinternal is true.
        cursor.execute('''SELECT c.oid::bigint,
            n.nspname::text || '.' || t.relname::text,
            ARRAY(SELECT a.attname::text FROM pg_catalog.unnest(c.conkey) WITH ORDINALITY k(num,pos)
              JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.num AND NOT a.attisdropped ORDER BY k.pos),
            rn.nspname::text || '.' || rt.relname::text,
            ARRAY(SELECT a.attname::text FROM pg_catalog.unnest(c.confkey) WITH ORDINALITY k(num,pos)
              JOIN pg_catalog.pg_attribute a ON a.attrelid=rt.oid AND a.attnum=k.num AND NOT a.attisdropped ORDER BY k.pos),
            c.convalidated,c.conenforced,c.condeferrable,c.condeferred,
            c.confupdtype::text,c.confdeltype::text,c.confmatchtype::text,
            pg_catalog.current_setting('session_replication_role') IN ('origin','local')
            FROM pg_catalog.pg_constraint c
            JOIN pg_catalog.pg_class t ON t.oid=c.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace AND c.connamespace=n.oid
            JOIN pg_catalog.pg_class rt ON rt.oid=c.confrelid
            JOIN pg_catalog.pg_namespace rn ON rn.oid=rt.relnamespace
            WHERE c.contype='f' AND (n.nspname::text || '.' || t.relname::text = ANY(%s)
              OR rn.nspname::text || '.' || rt.relname::text = ANY(%s))''', (tables, tables))
        rows = cursor.fetchall()
        if type(rows) is not list or len(rows) != len(expected):
            raise EffectV3Error('required persistence foreign keys absent or unexpected')
        approved = {}; seen = set()
        for row in rows:
            if (type(row) not in (tuple,list) or len(row) != 13 or
                    type(row[0]) is not int or not 0 < row[0] <= 4_294_967_295 or
                    type(row[1]) is not str or type(row[3]) is not str or
                    any(type(row[i]) is not list or not all(type(c) is str for c in row[i]) for i in (2,4))):
                raise EffectV3Error('malformed persistence foreign-key response')
            key = (row[1],tuple(row[2]),row[3],tuple(row[4]))
            if (key not in expected or key in seen or row[0] in approved or
                    any(row[i] is not True for i in (5,6,12)) or
                    row[7] is not False or row[8] is not False or
                    row[9:12] not in (('a','a','s'), ['a','a','s'])):
                raise EffectV3Error('persistence foreign-key enforcement mismatch')
            seen.add(key); approved[row[0]] = (row[1],row[3])
        if seen != expected:
            raise EffectV3Error('required persistence foreign key missing')
        cursor.execute('''SELECT n.nspname::text || '.' || t.relname::text,
            tr.tgconstraint::bigint,tr.tgisinternal,tr.tgenabled::text,
            pn.nspname::text || '.' || p.proname::text,tr.tgtype::int,
            tr.tgdeferrable,tr.tginitdeferred,tr.tgnargs::int,
            tr.tgargs=''::pg_catalog.bytea,tr.tgqual IS NULL,tr.tgattr=''::pg_catalog.int2vector
            FROM pg_catalog.pg_trigger tr
            JOIN pg_catalog.pg_class t ON t.oid=tr.tgrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
            JOIN pg_catalog.pg_proc p ON p.oid=tr.tgfoid
            JOIN pg_catalog.pg_namespace pn ON pn.oid=p.pronamespace
            WHERE n.nspname::text || '.' || t.relname::text = ANY(%s)''', (tables,))
        triggers = cursor.fetchall()
        expected_triggers = set()
        for oid, (child,parent) in approved.items():
            expected_triggers.update((
                (child,oid,'pg_catalog.RI_FKey_check_ins',5),
                (child,oid,'pg_catalog.RI_FKey_check_upd',17),
                (parent,oid,'pg_catalog.RI_FKey_noaction_del',9),
                (parent,oid,'pg_catalog.RI_FKey_noaction_upd',17),
            ))
        if type(triggers) is not list or len(triggers) != len(expected_triggers):
            raise EffectV3Error('required persistence triggers absent or unexpected')
        seen_triggers = set()
        for row in triggers:
            if (type(row) not in (tuple,list) or len(row) != 12 or
                    type(row[0]) is not str or type(row[1]) is not int or
                    type(row[4]) is not str or type(row[5]) is not int):
                raise EffectV3Error('malformed persistence trigger response')
            key = (row[0],row[1],row[4],row[5])
            if (key not in expected_triggers or key in seen_triggers or
                    any(row[i] is not True for i in (2,9,10,11)) or row[3] != 'O' or
                    row[6] is not False or row[7] is not False or
                    type(row[8]) is not int or row[8] != 0):
                raise EffectV3Error('persistence trigger enforcement mismatch')
            seen_triggers.add(key)
        if seen_triggers != expected_triggers:
            raise EffectV3Error('required persistence trigger missing')

    def _verify_schema(self, cursor):
        self._lock_unique_tables(cursor)
        cursor.execute(f'SELECT version,migration_hash,configuration_hash FROM {META} WHERE singleton=1')
        row = cursor.fetchone()
        if row is None or row[0] != 3 or bytes(row[1]) != MIGRATION_HASH or bytes(row[2]) != self.configuration_hash:
            raise EffectV3Error('provider schema/version/configuration mismatch')
        self._verify_unique_keys(cursor)

    def migrate(self):
        """Explicit fresh-schema migration; never called by effect or constructor."""
        with self._transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(%s)', (0x56414D5350563300,))
                cursor.execute('SELECT to_regclass(%s),to_regclass(%s),to_regclass(%s)', (META, FENCES, OBJECTS))
                existing = cursor.fetchone()
                if existing is None:
                    raise EffectV3Error('schema inspection unavailable')
                if any(v is not None for v in existing):
                    if not all(v is not None for v in existing):
                        raise EffectV3Error('partial or unversioned provider schema')
                    self._verify_schema(cursor)
                    return
                for statement in DDL: cursor.execute(statement)
                cursor.execute(f'INSERT INTO {META} VALUES(1,3,%s,%s)', (MIGRATION_HASH, self.configuration_hash))
                self._verify_schema(cursor)

    @contextmanager
    def transaction(self):
        with self._transaction() as connection:
            with connection.cursor() as cursor:
                self._verify_schema(cursor)
                yield cursor
