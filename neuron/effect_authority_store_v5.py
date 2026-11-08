"""Unintegrated PG5 authority-store preparation.

This module is a source artifact only. It is not imported by VAMS, does not
connect at construction, does not validate native funded admission, and has not
been run against PostgreSQL 18. No V3/V4 adoption is performed.
"""
import hashlib
from dataclasses import dataclass
from collections import Counter
import ipaddress
import json
import re
from urllib.parse import urlsplit

from neuron.effect_postgres_v3 import (
    EffectPersistenceErrorV3,
    PostgresEffectDatabaseV3,
    _is_postgres_driver_error,
)
from neuron.effect_protocol_v3 import EffectV3Error, commitment, hash32
from neuron.runtime_safety import RuntimeConfigurationError, load_runtime_policy


META5 = 'public.vams_effect_v5_authority_meta'
GENERATIONS5 = 'public.vams_effect_v5_authority_generations'
HEADS5 = 'public.vams_effect_v5_authority_heads'
WORK5 = 'public.vams_effect_v5_authority_work'
ATTEMPTS5 = 'public.vams_effect_v5_authority_attempts'
EVENTS5 = 'public.vams_effect_v5_authority_events'
COMPLETIONS5 = 'public.vams_effect_v5_authority_completions'
SETTLEMENTS5 = 'public.vams_effect_v5_authority_settlements'

# Bound a generation's cryptographic closure audit even for zero-cost work.
# Renewal preserves cumulative spend and old history; this is not a cap on the
# lifetime of a logical operation or an exclusion from either readiness gate.
MAX_GENERATION_ATTEMPTS5 = 256
AUTHORITY_LIMITS5 = {'max_generation_attempts':MAX_GENERATION_ATTEMPTS5}
MIGRATION_PROTOCOL5 = {
    'version':1,
    'serialization':'dedicated-session-advisory-lock-in-autocommit',
    'existing':'serializable-relation-locks-before-first-select',
    'fresh':'serializable-atomic-create-without-adoption',
    'session_affinity':'same-backend-pid-through-commit',
    'lock_release':'dedicated-connection-close-only',
}

DDL5 = (
    f'''CREATE TABLE {META5} (
        singleton SMALLINT PRIMARY KEY CHECK (singleton=1),
        version SMALLINT NOT NULL CHECK (version=5),
        migration_hash BYTEA NOT NULL CHECK (octet_length(migration_hash)=32),
        configuration_hash BYTEA NOT NULL CHECK (octet_length(configuration_hash)=32))''',
    f'''CREATE TABLE {GENERATIONS5} (
        generation_id BYTEA PRIMARY KEY CHECK (octet_length(generation_id)=32),
        scope_id BYTEA NOT NULL CHECK (octet_length(scope_id)=32),
        ordinal BIGINT NOT NULL CHECK (ordinal>=1),
        previous_generation BYTEA,
        scope_bytes BYTEA NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('installing','active','draining','revoked')),
        fence_bytes BYTEA NOT NULL, update_bytes BYTEA NOT NULL, ack_bytes BYTEA,
        closed_reserved BIGINT, closed_spent BIGINT,
        UNIQUE (scope_id,generation_id), UNIQUE (scope_id,ordinal),
        FOREIGN KEY (scope_id,previous_generation)
          REFERENCES {GENERATIONS5}(scope_id,generation_id),
        CHECK ((ordinal=1)=(previous_generation IS NULL)),
        CHECK (previous_generation IS NULL OR previous_generation<>generation_id),
        CHECK ((status='revoked' AND closed_reserved IS NOT NULL AND closed_spent IS NOT NULL
                  AND closed_reserved=0 AND closed_spent>=0)
            OR (status<>'revoked' AND closed_reserved IS NULL AND closed_spent IS NULL)))''',
    f'''CREATE TABLE {HEADS5} (
        scope_id BYTEA PRIMARY KEY CHECK (octet_length(scope_id)=32),
        current_generation BYTEA NOT NULL CHECK (octet_length(current_generation)=32),
        budget_unit BYTEA NOT NULL CHECK (octet_length(budget_unit)=32),
        budget_limit BIGINT NOT NULL CHECK (budget_limit>0),
        budget_reserved BIGINT NOT NULL CHECK (budget_reserved>=0),
        budget_spent BIGINT NOT NULL CHECK (budget_spent>=0),
        FOREIGN KEY (scope_id,current_generation)
          REFERENCES {GENERATIONS5}(scope_id,generation_id),
        CHECK (budget_spent<=budget_limit AND budget_reserved<=budget_limit-budget_spent))''',
    f'''CREATE TABLE {WORK5} (
        operation_id BYTEA PRIMARY KEY CHECK (octet_length(operation_id)=32),
        logical_work BYTEA NOT NULL CHECK (octet_length(logical_work)=32),
        initial_proposal_bytes BYTEA NOT NULL CHECK (octet_length(initial_proposal_bytes)<=65536),
        initial_proposal_digest BYTEA NOT NULL CHECK (octet_length(initial_proposal_digest)=32),
        postcondition BYTEA NOT NULL CHECK (octet_length(postcondition)=32),
        budget_unit BYTEA NOT NULL CHECK (octet_length(budget_unit)=32),
        cost_units BIGINT NOT NULL CHECK (cost_units>=0),
        UNIQUE (operation_id,logical_work))''',
    f'''CREATE TABLE {ATTEMPTS5} (
        attempt_id BYTEA PRIMARY KEY CHECK (octet_length(attempt_id)=32),
        operation_id BYTEA NOT NULL CHECK (octet_length(operation_id)=32),
        attempt_no BIGINT NOT NULL CHECK (attempt_no>=1),
        logical_work BYTEA NOT NULL CHECK (octet_length(logical_work)=32),
        predecessor_attempt_id BYTEA,
        scope_id BYTEA NOT NULL CHECK (octet_length(scope_id)=32),
        generation_id BYTEA NOT NULL CHECK (octet_length(generation_id)=32),
        native_chain_id BIGINT NOT NULL CHECK (native_chain_id>0),
        native_contract BYTEA NOT NULL CHECK (octet_length(native_contract)=32),
        allocation_id BYTEA NOT NULL CHECK (octet_length(allocation_id)=32),
        allocation_index BIGINT NOT NULL CHECK (allocation_index>=0 AND allocation_index<20),
        row_bytes BYTEA NOT NULL CHECK (octet_length(row_bytes)=128),
        row_digest BYTEA NOT NULL CHECK (octet_length(row_digest)=32),
        proposal_bytes BYTEA NOT NULL CHECK (octet_length(proposal_bytes)<=65536),
        proposal_digest BYTEA NOT NULL CHECK (octet_length(proposal_digest)=32),
        admission_bytes BYTEA NOT NULL CHECK (octet_length(admission_bytes)<=4096),
        admission_digest BYTEA NOT NULL UNIQUE CHECK (octet_length(admission_digest)=32),
        nonce BYTEA NOT NULL UNIQUE CHECK (octet_length(nonce)=32),
        budget_unit BYTEA NOT NULL CHECK (octet_length(budget_unit)=32),
        cost_units BIGINT NOT NULL CHECK (cost_units>=0),
        UNIQUE (operation_id,attempt_no),
        UNIQUE (operation_id,attempt_id),
        UNIQUE (operation_id,attempt_no,attempt_id),
        UNIQUE (native_chain_id,native_contract,allocation_id,allocation_index),
        UNIQUE (scope_id,generation_id,operation_id,attempt_id),
        FOREIGN KEY (operation_id,logical_work)
          REFERENCES {WORK5}(operation_id,logical_work),
        FOREIGN KEY (scope_id) REFERENCES {HEADS5}(scope_id),
        FOREIGN KEY (scope_id,generation_id)
          REFERENCES {GENERATIONS5}(scope_id,generation_id),
        FOREIGN KEY (operation_id,predecessor_attempt_id)
          REFERENCES {ATTEMPTS5}(operation_id,attempt_id),
        CHECK ((attempt_no=1)=(predecessor_attempt_id IS NULL)),
        CHECK (predecessor_attempt_id IS NULL OR predecessor_attempt_id<>attempt_id))''',
    f'''CREATE TABLE {EVENTS5} (
        operation_id BYTEA NOT NULL CHECK (octet_length(operation_id)=32),
        attempt_no BIGINT NOT NULL CHECK (attempt_no>=1),
        attempt_id BYTEA NOT NULL CHECK (octet_length(attempt_id)=32),
        event_seq SMALLINT NOT NULL CHECK (event_seq BETWEEN 1 AND 8),
        predecessor_event_seq SMALLINT,
        kind TEXT NOT NULL CHECK (kind IN
          ('reserved','funding_unknown','funded','dispatched','indeterminate','completed','absent')),
        payload_bytes BYTEA NOT NULL CHECK (octet_length(payload_bytes) BETWEEN 1 AND 65536),
        payload_digest BYTEA NOT NULL CHECK (octet_length(payload_digest)=32),
        event_digest BYTEA NOT NULL UNIQUE CHECK (octet_length(event_digest)=32),
        PRIMARY KEY (attempt_id,event_seq),
        UNIQUE (operation_id,attempt_no,attempt_id,event_seq),
        FOREIGN KEY (operation_id,attempt_no,attempt_id)
          REFERENCES {ATTEMPTS5}(operation_id,attempt_no,attempt_id),
        FOREIGN KEY (attempt_id,predecessor_event_seq)
          REFERENCES {EVENTS5}(attempt_id,event_seq),
        CHECK ((event_seq=1)=(predecessor_event_seq IS NULL)),
        CHECK (predecessor_event_seq IS NULL OR predecessor_event_seq=event_seq-1))''',
    f'''CREATE TABLE {COMPLETIONS5} (
        operation_id BYTEA PRIMARY KEY CHECK (octet_length(operation_id)=32),
        attempt_no BIGINT NOT NULL CHECK (attempt_no>=1),
        attempt_id BYTEA NOT NULL CHECK (octet_length(attempt_id)=32),
        completion_event_seq SMALLINT NOT NULL CHECK (completion_event_seq BETWEEN 1 AND 8),
        receipt_bytes BYTEA NOT NULL CHECK (octet_length(receipt_bytes)<=4096),
        receipt_digest BYTEA NOT NULL CHECK (octet_length(receipt_digest)=32),
        UNIQUE (attempt_id,completion_event_seq),
        FOREIGN KEY (operation_id,attempt_no,attempt_id)
          REFERENCES {ATTEMPTS5}(operation_id,attempt_no,attempt_id),
        FOREIGN KEY (operation_id,attempt_no,attempt_id,completion_event_seq)
          REFERENCES {EVENTS5}(operation_id,attempt_no,attempt_id,event_seq))''',
    f'''CREATE TABLE {SETTLEMENTS5} (
        observation_id BYTEA PRIMARY KEY CHECK (octet_length(observation_id)=32),
        attempt_id BYTEA NOT NULL REFERENCES {ATTEMPTS5}(attempt_id),
        observation_no SMALLINT NOT NULL CHECK (observation_no BETWEEN 1 AND 4),
        previous_observation BYTEA,
        kind TEXT NOT NULL CHECK (kind IN ('earned','paid','absent','refunded')),
        evidence_bytes BYTEA NOT NULL CHECK (octet_length(evidence_bytes) BETWEEN 1 AND 65536),
        evidence_digest BYTEA NOT NULL CHECK (octet_length(evidence_digest)=32),
        UNIQUE (attempt_id,observation_no), UNIQUE (attempt_id,observation_id),
        FOREIGN KEY (attempt_id,previous_observation)
          REFERENCES {SETTLEMENTS5}(attempt_id,observation_id),
        CHECK ((observation_no=1)=(previous_observation IS NULL)),
        CHECK (previous_observation IS NULL OR previous_observation<>observation_id))''',
)

_ROLE_RE = re.compile(r'[a-z_][a-z0-9_]{0,62}\Z', re.ASCII)
_TABLES5 = (META5, GENERATIONS5, HEADS5, WORK5, ATTEMPTS5, EVENTS5, COMPLETIONS5, SETTLEMENTS5)
_GENERATION_UPDATES = (
    'status', 'fence_bytes', 'update_bytes', 'ack_bytes', 'closed_reserved', 'closed_spent',
)
_HEAD_UPDATES = ('current_generation', 'budget_limit', 'budget_reserved', 'budget_spent')
# Exact non-generated column identities. CHECK/DDL normalization still requires
# independent PG18 qualification; the inherited guard covers keys and RI hooks.
_COLUMN_TYPES5 = {
    META5: 'singleton:21 version:21 migration_hash:17 configuration_hash:17',
    GENERATIONS5: 'generation_id:17 scope_id:17 ordinal:20 previous_generation:17? scope_bytes:17 status:25 '
        'fence_bytes:17 update_bytes:17 ack_bytes:17? closed_reserved:20? closed_spent:20?',
    HEADS5: 'scope_id:17 current_generation:17 budget_unit:17 budget_limit:20 budget_reserved:20 budget_spent:20',
    WORK5: 'operation_id:17 logical_work:17 initial_proposal_bytes:17 initial_proposal_digest:17 '
        'postcondition:17 budget_unit:17 cost_units:20',
    ATTEMPTS5: 'attempt_id:17 operation_id:17 attempt_no:20 logical_work:17 predecessor_attempt_id:17? '
        'scope_id:17 generation_id:17 native_chain_id:20 native_contract:17 allocation_id:17 allocation_index:20 '
        'row_bytes:17 row_digest:17 proposal_bytes:17 proposal_digest:17 admission_bytes:17 admission_digest:17 '
        'nonce:17 budget_unit:17 cost_units:20',
    EVENTS5: 'operation_id:17 attempt_no:20 attempt_id:17 event_seq:21 predecessor_event_seq:21? '
        'kind:25 payload_bytes:17 payload_digest:17 event_digest:17',
    COMPLETIONS5: 'operation_id:17 attempt_no:20 attempt_id:17 completion_event_seq:21 receipt_bytes:17 receipt_digest:17',
    SETTLEMENTS5: 'observation_id:17 attempt_id:17 observation_no:21 previous_observation:17? kind:25 '
        'evidence_bytes:17 evidence_digest:17',
}
_COLUMNS5 = {(table,item.split(':')[0]):(int(item.split(':')[1].rstrip('?')),not item.endswith('?'))
    for table,items in _COLUMN_TYPES5.items() for item in items.split()}
PRIVILEGE_PROFILE5 = {
    'meta': ['SELECT','MAINTAIN'],
    'facts': ['SELECT','INSERT','MAINTAIN'],
    'generation_updates': list(_GENERATION_UPDATES),
    'head_updates': list(_HEAD_UPDATES),
    'grant_options': False,
    'runtime_memberships': False,
    'forbidden_role_attributes': ['SUPERUSER','CREATEROLE','CREATEDB','BYPASSRLS','REPLICATION'],
    'migration_replication_memberships': False,
    'table_lock': 'SHARE UPDATE EXCLUSIVE',
}
MIGRATION5 = hashlib.sha256(b'VAMS:AUTHORITY-PG-MIGRATION:v5\0'+
    '\n'.join(DDL5).encode('ascii')+b'\0'+
    json.dumps(PRIVILEGE_PROFILE5,sort_keys=True,separators=(',',':')).encode('ascii')+b'\0'+
    json.dumps(AUTHORITY_LIMITS5,sort_keys=True,separators=(',',':')).encode('ascii')+b'\0'+
    json.dumps(MIGRATION_PROTOCOL5,sort_keys=True,separators=(',',':')).encode('ascii')).digest()
_CHECK_COUNTS5={table:len(re.findall(r'\bCHECK\s*\(',ddl)) for table,ddl in zip(_TABLES5,DDL5)}


@dataclass(frozen=True)
class ExpectedChecksV5:
    """Expected canonical catalog from an independently reviewed PG18 build.

    This object binds data, not approval. Never obtain its expected definitions
    from the live database being checked. Actual compiler/provenance records are
    required qualification inputs; no default or source-string approximation.
    """
    migration_hash:bytes
    compiler_identity:bytes
    provenance_identity:bytes
    server_version_num:int
    definitions:tuple[tuple[str,str],...]

    def validate(self):
        hash32(self.migration_hash)
        if self.migration_hash!=MIGRATION5:
            raise EffectV3Error('CHECK manifest belongs to another source/privilege schema')
        hash32(self.compiler_identity);hash32(self.provenance_identity)
        if type(self.server_version_num) is not int or not 180000<=self.server_version_num<190000:
            raise EffectV3Error('explicit qualified PostgreSQL18 version required')
        if type(self.definitions) is not tuple or len(self.definitions)!=sum(_CHECK_COUNTS5.values()):
            raise EffectV3Error('complete frozen CHECK manifest required')
        counts=Counter()
        for item in self.definitions:
            if type(item) is not tuple or len(item)!=2:
                raise EffectV3Error('invalid CHECK manifest entry')
            table,definition=item
            if (type(table) is not str or table not in _TABLES5 or type(definition) is not str or
                    not definition.startswith('CHECK (') or not definition.isascii() or
                    '\0' in definition or len(definition)>8192):
                raise EffectV3Error('invalid bounded canonical CHECK definition')
            counts[table]+=1
        if counts!=Counter(_CHECK_COUNTS5) or tuple(sorted(set(self.definitions)))!=self.definitions:
            raise EffectV3Error('CHECK manifest table/count/order mismatch')

    @property
    def digest(self):
        self.validate()
        body=json.dumps(self.definitions,separators=(',',':'),ensure_ascii=True).encode('ascii')
        return commitment(b'VAMS:PG-CHECK-MANIFEST:v5\0',MIGRATION5,self.compiler_identity,
            self.provenance_identity,self.server_version_num.to_bytes(32,'big'),hashlib.sha256(body).digest())


def _role_name(value, label):
    if type(value) is not str or not _ROLE_RE.fullmatch(value) or value.startswith('pg_'):
        raise EffectV3Error('explicit validated ' + label + ' role name required')
    return value


def authority_configuration_v5(identity, native_config_hash, runtime_role, migration_role, check_manifest):
    """Bind store identity to the explicitly selected issuer/native/role config."""
    digest = getattr(identity, 'digest', None)
    if type(digest) is not bytes or len(digest) != 32:
        raise EffectV3Error('typed authority/provider identity digest required')
    native_config_hash = hash32(native_config_hash, 'native configuration hash')
    runtime_role = _role_name(runtime_role, 'runtime')
    migration_role = _role_name(migration_role, 'migration')
    if runtime_role == migration_role:
        raise EffectV3Error('runtime and migration roles must be distinct')
    role_binding = runtime_role.encode('ascii') + b'\0' + migration_role.encode('ascii')
    if type(check_manifest) is not ExpectedChecksV5:
        raise EffectV3Error('explicit frozen CHECK manifest required')
    return commitment(b'VAMS:AUTHORITY-STORE:v5\0', digest, native_config_hash, role_binding,
        MIGRATION5,check_manifest.digest)


class PostgresAuthorityDatabaseV5(PostgresEffectDatabaseV3):
    """Fresh V5 store candidate; no V3/V4 adoption and no live qualification."""

    _foreign_keys = (
        (GENERATIONS5, ('scope_id', 'previous_generation'), GENERATIONS5, ('scope_id', 'generation_id')),
        (HEADS5, ('scope_id', 'current_generation'), GENERATIONS5, ('scope_id', 'generation_id')),
        (ATTEMPTS5, ('operation_id', 'logical_work'), WORK5, ('operation_id', 'logical_work')),
        (ATTEMPTS5, ('scope_id',), HEADS5, ('scope_id',)),
        (ATTEMPTS5, ('scope_id', 'generation_id'), GENERATIONS5, ('scope_id', 'generation_id')),
        (ATTEMPTS5, ('operation_id', 'predecessor_attempt_id'), ATTEMPTS5, ('operation_id', 'attempt_id')),
        (EVENTS5, ('operation_id', 'attempt_no', 'attempt_id'), ATTEMPTS5,
            ('operation_id', 'attempt_no', 'attempt_id')),
        (EVENTS5, ('attempt_id', 'predecessor_event_seq'), EVENTS5, ('attempt_id', 'event_seq')),
        (COMPLETIONS5, ('operation_id', 'attempt_no', 'attempt_id'), ATTEMPTS5,
            ('operation_id', 'attempt_no', 'attempt_id')),
        (COMPLETIONS5, ('operation_id', 'attempt_no', 'attempt_id', 'completion_event_seq'), EVENTS5,
            ('operation_id', 'attempt_no', 'attempt_id', 'event_seq')),
        (SETTLEMENTS5, ('attempt_id',), ATTEMPTS5, ('attempt_id',)),
        (SETTLEMENTS5, ('attempt_id','previous_observation'), SETTLEMENTS5, ('attempt_id','observation_id')),
    )
    _uniqueness_keys = (
        (META5, 'p', (('singleton', 21),)),
        (GENERATIONS5, 'p', (('generation_id', 17),)),
        (GENERATIONS5, 'u', (('scope_id', 17), ('generation_id', 17))),
        (GENERATIONS5, 'u', (('scope_id', 17), ('ordinal', 20))),
        (HEADS5, 'p', (('scope_id', 17),)),
        (WORK5, 'p', (('operation_id', 17),)),
        (WORK5, 'u', (('operation_id', 17), ('logical_work', 17))),
        (ATTEMPTS5, 'p', (('attempt_id', 17),)),
        (ATTEMPTS5, 'u', (('operation_id', 17), ('attempt_no', 20))),
        (ATTEMPTS5, 'u', (('operation_id', 17), ('attempt_id', 17))),
        (ATTEMPTS5, 'u', (('operation_id', 17), ('attempt_no', 20), ('attempt_id', 17))),
        (ATTEMPTS5, 'u', (('native_chain_id', 20), ('native_contract', 17), ('allocation_id', 17), ('allocation_index', 20))),
        (ATTEMPTS5, 'u', (('scope_id',17),('generation_id',17),('operation_id',17),('attempt_id',17))),
        (ATTEMPTS5, 'u', (('admission_digest', 17),)),
        (ATTEMPTS5, 'u', (('nonce', 17),)),
        (EVENTS5, 'p', (('attempt_id', 17), ('event_seq', 21))),
        (EVENTS5, 'u', (('event_digest', 17),)),
        (EVENTS5, 'u', (('operation_id', 17), ('attempt_no', 20), ('attempt_id', 17), ('event_seq', 21))),
        (COMPLETIONS5, 'p', (('operation_id', 17),)),
        (COMPLETIONS5, 'u', (('attempt_id', 17), ('completion_event_seq', 21))),
        (SETTLEMENTS5, 'p', (('observation_id',17),)),
        (SETTLEMENTS5, 'u', (('attempt_id',17),('observation_no',21))),
        (SETTLEMENTS5, 'u', (('attempt_id',17),('observation_id',17))),
    )

    _application_name = 'vams-effect-authority-v5'
    _immutable_runtime_fields = frozenset({
        'runtime_policy', 'configuration_hash', 'dsn', '_uniqueness_keys', '_foreign_keys',
        'runtime_role', 'migration_role', 'check_manifest',
    })

    def __init__(self, dsn, configuration_hash, *, runtime_role, migration_role, check_manifest):
        self.runtime_policy = load_runtime_policy()
        if self.runtime_policy.is_live:
            raise RuntimeConfigurationError('Unqualified authority storage5 cannot run in live mode')
        runtime_role = _role_name(runtime_role, 'runtime')
        migration_role = _role_name(migration_role, 'migration')
        if runtime_role == migration_role:
            raise EffectV3Error('runtime and migration roles must be distinct')
        if type(check_manifest) is not ExpectedChecksV5:
            raise EffectV3Error('explicit frozen CHECK manifest required before database use')
        check_manifest.validate()
        self.runtime_role = runtime_role
        self.migration_role = migration_role
        self.check_manifest = check_manifest
        super().__init__(dsn, configuration_hash)

    def _require_runtime(self):
        super()._require_runtime()
        if load_runtime_policy().is_live:
            raise RuntimeConfigurationError('Unqualified authority storage5 cannot run in live mode')

    def _lock_unique_tables(self, cursor):
        # The base catalog guard deliberately rejects arbitrary table names.
        # Keep its exact lock discipline while admitting only the fixed V5 set.
        for table in dict.fromkeys(key[0] for key in self._uniqueness_keys):
            if table not in _TABLES5:
                raise EffectV3Error('unsupported storage5 catalog table')
            cursor.execute(f'LOCK TABLE ONLY {table} IN SHARE UPDATE EXCLUSIVE MODE')

    def _verify_schema(self, cursor, *, migration=False):
        expected_role=self.migration_role if migration else self.runtime_role
        # Even SELECT session_user,current_user takes a transaction snapshot.
        # Acquire all fixed relation locks before that first ordinary SELECT.
        self._lock_unique_tables(cursor)
        cursor.execute('SELECT session_user::text,current_user::text')
        session=cursor.fetchone()
        if session is None or tuple(session)!=(expected_role,expected_role):
            raise EffectV3Error('selected V5 database session role required')
        cursor.execute("SELECT pg_catalog.current_setting('server_version_num')::int")
        version=cursor.fetchone()
        if version is None or tuple(version)!=(self.check_manifest.server_version_num,):
            raise EffectV3Error('V5 PostgreSQL compiler/version manifest mismatch')
        cursor.execute(
            f'SELECT version,migration_hash,configuration_hash FROM {META5} WHERE singleton=1'
        )
        row = cursor.fetchone()
        if (row is None or row[0] != 5 or bytes(row[1]) != MIGRATION5 or
                bytes(row[2]) != self.configuration_hash):
            raise EffectV3Error('authority storage5 version/configuration mismatch')
        self._verify_unique_keys(cursor)
        self._verify_check_constraints(cursor)
        self._verify_owners_and_privileges(cursor)

    def _verify_check_constraints(self,cursor):
        self.check_manifest.validate()
        cursor.execute('''SELECT n.nspname::text||'.'||t.relname::text,
            pg_catalog.pg_get_constraintdef(c.oid,false),
            c.convalidated,c.conenforced,c.condeferrable,c.condeferred,
            c.conislocal,c.coninhcount::int,c.connoinherit,c.conparentid::bigint
            FROM pg_catalog.pg_constraint c
            JOIN pg_catalog.pg_class t ON t.oid=c.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
            WHERE c.contype='c' AND n.nspname::text||'.'||t.relname::text=ANY(%s)''',
            (list(_TABLES5),))
        rows=cursor.fetchall();expected=set(self.check_manifest.definitions);seen=set()
        if type(rows) is not list or len(rows)!=len(expected):
            raise EffectV3Error('live CHECK constraints absent or unexpected')
        for row in rows:
            if type(row) not in (tuple,list) or len(row)!=10:
                raise EffectV3Error('malformed live CHECK catalog')
            if type(row[0]) is not str or type(row[1]) is not str:
                raise EffectV3Error('malformed live CHECK identity')
            key=(row[0],row[1])
            if (key not in expected or key in seen or any(row[i] is not True for i in (2,3,6)) or
                    any(row[i] is not False for i in (4,5,8)) or
                    any(type(row[i]) is not int or row[i]!=0 for i in (7,9))):
                raise EffectV3Error('live CHECK definition/enforcement drift')
            seen.add(key)
        if seen!=expected:raise EffectV3Error('required live CHECK missing')

    def _verify_owners_and_privileges(self, cursor):
        cursor.execute('''SELECT r.oid::bigint,r.rolsuper,r.rolcreaterole,r.rolcreatedb,
            r.rolbypassrls,r.rolinherit,pg_catalog.has_schema_privilege(r.oid,'public','USAGE'),
            pg_catalog.has_schema_privilege(r.oid,'public','CREATE'),r.rolreplication
            FROM pg_catalog.pg_roles r WHERE r.rolname=%s''', (self.runtime_role,))
        runtime = cursor.fetchone()
        if (type(runtime) not in (tuple,list) or len(runtime)!=9 or runtime[8] is not False or
                runtime[1] is not False or runtime[2] is not False or
                runtime[3] is not False or runtime[4] is not False or type(runtime[5]) is not bool or
                runtime[6] is not True or runtime[7] is not False):
            raise EffectV3Error('V5 runtime role attributes/schema grants are unsafe or unavailable')
        cursor.execute('''SELECT r.oid::bigint,r.rolsuper,r.rolcreaterole,r.rolcreatedb,r.rolbypassrls,
            pg_catalog.has_schema_privilege(r.oid,'public','CREATE'),r.rolreplication
            FROM pg_catalog.pg_roles r WHERE r.rolname=%s''', (self.migration_role,))
        migration = cursor.fetchone()
        if (type(migration) not in (tuple,list) or len(migration)!=7 or migration[6] is not False or
                migration[1] is not False or migration[2] is not False or
                migration[3] is not False or migration[4] is not False or migration[5] is not True):
            raise EffectV3Error('V5 selected migration owner role is unsafe or unavailable')
        if runtime[0] == migration[0]:
            raise EffectV3Error('V5 runtime and migration roles must differ')

        self._verify_role_memberships(cursor)

        cursor.execute('''SELECT n.nspname::text || '.' || c.relname::text,
                owner.rolname::text,c.relkind::text,c.relpersistence::text,
                NOT c.relrowsecurity,NOT c.relforcerowsecurity,
                NOT EXISTS(SELECT 1 FROM pg_catalog.pg_inherits i
                  WHERE i.inhparent=c.oid OR i.inhrelid=c.oid),
                NOT EXISTS(SELECT 1 FROM pg_catalog.pg_trigger t
                  WHERE t.tgrelid=c.oid AND NOT t.tgisinternal),
                NOT EXISTS(SELECT 1 FROM pg_catalog.pg_rewrite w WHERE w.ev_class=c.oid)
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_catalog.pg_roles owner ON owner.oid=c.relowner
            WHERE n.nspname='public' AND c.relname=ANY(%s)''',
            ([table.split('.', 1)[1] for table in _TABLES5],))
        objects = cursor.fetchall()
        if type(objects) is not list or len(objects) != len(_TABLES5):
            raise EffectV3Error('V5 relations missing or unexpected')
        expected = set(_TABLES5)
        seen = set()
        for row in objects:
            if (type(row) not in (tuple, list) or len(row) != 9 or
                    row[0] not in expected or row[0] in seen or row[1] != self.migration_role or
                    row[2] != 'r' or row[3] != 'p' or any(value is not True for value in row[4:])):
                raise EffectV3Error('V5 relation owner/catalog interception mismatch')
            seen.add(row[0])
        if seen != expected:
            raise EffectV3Error('V5 relation catalog set mismatch')

        expected_table_privileges = {
            META5: (True, False, False, False, False, False, False, True),
            GENERATIONS5: (True, True, False, False, False, False, False, True),
            HEADS5: (True, True, False, False, False, False, False, True),
            WORK5: (True, True, False, False, False, False, False, True),
            ATTEMPTS5: (True, True, False, False, False, False, False, True),
            EVENTS5: (True, True, False, False, False, False, False, True),
            COMPLETIONS5: (True, True, False, False, False, False, False, True),
            SETTLEMENTS5: (True, True, False, False, False, False, False, True),
        }
        for table, expected_privileges in expected_table_privileges.items():
            cursor.execute('''SELECT pg_catalog.has_table_privilege(%s,%s,'SELECT'),
                pg_catalog.has_table_privilege(%s,%s,'INSERT'),
                pg_catalog.has_table_privilege(%s,%s,'UPDATE'),
                pg_catalog.has_table_privilege(%s,%s,'DELETE'),
                pg_catalog.has_table_privilege(%s,%s,'TRUNCATE'),
                pg_catalog.has_table_privilege(%s,%s,'REFERENCES'),
                pg_catalog.has_table_privilege(%s,%s,'TRIGGER'),
                pg_catalog.has_table_privilege(%s,%s,'MAINTAIN')''',
                (self.runtime_role, table) * 8)
            privileges = cursor.fetchone()
            if privileges is None or tuple(privileges) != expected_privileges:
                raise EffectV3Error('V5 runtime table privileges differ from the allowlist')
            cursor.execute('''SELECT pg_catalog.has_table_privilege(%s,%s,
                'SELECT WITH GRANT OPTION,INSERT WITH GRANT OPTION,UPDATE WITH GRANT OPTION,
                DELETE WITH GRANT OPTION,TRUNCATE WITH GRANT OPTION,REFERENCES WITH GRANT OPTION,
                TRIGGER WITH GRANT OPTION,MAINTAIN WITH GRANT OPTION')''',(self.runtime_role,table))
            delegated=cursor.fetchone()
            if delegated is None or tuple(delegated)!=(False,):
                raise EffectV3Error('V5 runtime table privilege delegation forbidden')

        allowed_column_updates = {
            GENERATIONS5: set(_GENERATION_UPDATES),
            HEADS5: set(_HEAD_UPDATES),
        }
        cursor.execute('''SELECT n.nspname::text || '.' || c.relname::text,
                a.attname::text,a.atttypid::int,a.attnotnull,NOT a.atthasdef,
                a.attgenerated='',a.attidentity='',
                pg_catalog.has_column_privilege(%s,c.oid,a.attnum,'UPDATE'),
                pg_catalog.has_column_privilege(%s,c.oid,a.attnum,
                  'SELECT WITH GRANT OPTION,INSERT WITH GRANT OPTION,UPDATE WITH GRANT OPTION,REFERENCES WITH GRANT OPTION')
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
            WHERE n.nspname='public' AND c.relname=ANY(%s)
              AND a.attnum>0 AND NOT a.attisdropped''',
            (self.runtime_role,self.runtime_role,[table.split('.', 1)[1] for table in _TABLES5]))
        columns = cursor.fetchall()
        if type(columns) is not list:
            raise EffectV3Error('V5 column privilege inspection unavailable')
        seen_columns = set()
        for row in columns:
            if type(row) not in (tuple,list) or len(row)!=9:
                raise EffectV3Error('malformed V5 column identity response')
            table,column,oid,not_null,no_default,no_generated,no_identity,can_update,grant_option=row
            key = (table, column)
            if key in seen_columns or key not in _COLUMNS5 or type(can_update) is not bool:
                raise EffectV3Error('malformed V5 column privilege response')
            expected_type,expected_not_null=_COLUMNS5[key]
            if (type(oid) is not int or oid!=expected_type or not_null is not expected_not_null or
                    any(value is not True for value in (no_default,no_generated,no_identity)) or grant_option is not False):
                raise EffectV3Error('V5 column type/default/generation/grant mismatch')
            seen_columns.add(key)
            allowed = column in allowed_column_updates.get(table, set())
            if can_update is not allowed:
                raise EffectV3Error('V5 runtime column update privilege differs from the allowlist')
        if seen_columns!=set(_COLUMNS5):
            raise EffectV3Error('V5 required column identity/privilege missing')

    def _check_roles_and_migration_session(self, cursor):
        cursor.execute('''SELECT session_user::text,current_user::text,
            pg_catalog.has_schema_privilege(current_user,'public','CREATE')''')
        session = cursor.fetchone()
        if (session is None or session[0] != self.migration_role or
                session[1] != self.migration_role or session[2] is not True):
            raise EffectV3Error('explicit V5 migration-owner connection required')
        cursor.execute('''SELECT rolname::text,rolsuper,rolcreaterole,rolcreatedb,rolbypassrls,rolreplication
            FROM pg_catalog.pg_roles WHERE rolname=ANY(%s)''',
            ([self.runtime_role, self.migration_role],))
        roles = cursor.fetchall()
        if type(roles) is not list or len(roles) != 2:
            raise EffectV3Error('selected V5 runtime/migration roles must already exist')
        by_name = {row[0]: row for row in roles if type(row) in (tuple, list) and len(row) == 6}
        if set(by_name) != {self.runtime_role, self.migration_role}:
            raise EffectV3Error('selected V5 roles unavailable')
        if any(value is not False for row in by_name.values() for value in row[1:]):
            raise EffectV3Error('selected V5 roles have forbidden privileged attributes')
        self._verify_role_memberships(cursor)

    def _verify_role_memberships(self,cursor):
        # Conservatively reject every runtime membership, as before. Traverse
        # all edges regardless of INHERIT/SET options; never infer safe role
        # switching from rolinherit alone. No membership privilege is granted.
        cursor.execute('''WITH RECURSIVE inherited(role_oid) AS (
              SELECT oid FROM pg_catalog.pg_roles WHERE rolname=%s
              UNION
              SELECT m.roleid FROM pg_catalog.pg_auth_members m
                JOIN inherited i ON m.member=i.role_oid)
            SELECT EXISTS(SELECT 1 FROM inherited i JOIN pg_catalog.pg_roles r ON r.oid=i.role_oid
              WHERE r.rolname=%s OR r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR r.rolbypassrls OR r.rolreplication),
              EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
                JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
                JOIN pg_catalog.pg_roles u ON u.oid=m.member
                WHERE u.rolname=%s)''', (self.runtime_role, self.migration_role, self.runtime_role))
        membership = cursor.fetchone()
        if (type(membership) not in (tuple,list) or len(membership)!=2 or
                membership[0] is not False or membership[1] is not False):
            raise EffectV3Error('V5 runtime role has unsafe membership')
        # Migration ownership does not require replication or access to a role
        # with that capability. Preserve its existing other membership rules.
        cursor.execute('''WITH RECURSIVE migration_inherited(role_oid) AS (
              SELECT oid FROM pg_catalog.pg_roles WHERE rolname=%s
              UNION
              SELECT m.roleid FROM pg_catalog.pg_auth_members m
                JOIN migration_inherited i ON m.member=i.role_oid)
            SELECT EXISTS(SELECT 1 FROM migration_inherited i
              JOIN pg_catalog.pg_roles r ON r.oid=i.role_oid WHERE r.rolreplication)''',
            (self.migration_role,))
        migration_membership=cursor.fetchone()
        if (type(migration_membership) not in (tuple,list) or len(migration_membership)!=1 or
                migration_membership[0] is not False):
            raise EffectV3Error('V5 migration role has unsafe replication membership')

    @staticmethod
    def _grant_runtime_privileges(cursor, runtime_role):
        try:
            from psycopg2 import sql
        except ImportError:
            raise EffectV3Error('PostgreSQL driver unavailable; no fallback') from None
        role = sql.Identifier(runtime_role)
        cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(role))
        for table in _TABLES5:
            ident = sql.Identifier('public', table.split('.', 1)[1])
            cursor.execute(sql.SQL('REVOKE ALL PRIVILEGES ON TABLE {} FROM PUBLIC').format(ident))
            # PG18 requires MAINTAIN or a mutating table privilege for this lock.
            # Keep the DDL-race guard without granting UPDATE to immutable facts.
            cursor.execute(sql.SQL('GRANT MAINTAIN ON TABLE {} TO {}').format(ident,role))
        for table in (GENERATIONS5, HEADS5, WORK5, ATTEMPTS5, EVENTS5, COMPLETIONS5,SETTLEMENTS5):
            ident = sql.Identifier('public', table.split('.', 1)[1])
            cursor.execute(sql.SQL('GRANT SELECT, INSERT ON TABLE {} TO {}').format(ident, role))
        meta = sql.Identifier('public', META5.split('.', 1)[1])
        cursor.execute(sql.SQL('GRANT SELECT ON TABLE {} TO {}').format(meta, role))
        for table, columns in ((GENERATIONS5, _GENERATION_UPDATES), (HEADS5, _HEAD_UPDATES)):
            ident = sql.Identifier('public', table.split('.', 1)[1])
            column_list = sql.SQL(',').join(sql.Identifier(column) for column in columns)
            cursor.execute(sql.SQL('GRANT UPDATE ({}) ON TABLE {} TO {}').format(column_list, ident, role))

    @staticmethod
    def _connect_selected_dsn(migration_dsn, application_name):
        if application_name not in ('vams-effect-authority-v5','vams-effect-authority-v5-migrate'):
            raise EffectV3Error('unsupported storage5 connection purpose')
        if type(migration_dsn) is not str or not migration_dsn.startswith(('postgresql://', 'postgres://')):
            raise EffectV3Error('explicit PostgreSQL migration-owner DSN required')
        try:
            address = urlsplit(migration_dsn)
            host, port = address.hostname, address.port
            if not host or not host.isascii():
                raise ValueError
            try:
                host = str(ipaddress.ip_address(host))
            except ValueError:
                labels = host.removesuffix('.').split('.')
                if len(host) > 254 or not all(re.fullmatch(
                        r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                        for label in labels):
                    raise ValueError
            if port is not None and not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            raise EffectV3Error('migration requires one explicit TCP hostname/address and valid port') from None
        try:
            import psycopg2
        except ImportError:
            raise EffectV3Error('PostgreSQL driver unavailable; no fallback') from None
        try:
            return psycopg2.connect(
                migration_dsn,
                connect_timeout=5,
                application_name=application_name,
                options='-c search_path=pg_catalog -c statement_timeout=10000 -c lock_timeout=5000',
                host=host,
                port=port or 5432,
                sslmode='verify-full',
                gssencmode='disable',
            )
        except psycopg2.Error:
            pass
        raise EffectPersistenceErrorV3('CONNECT') from None

    def _connect(self):
        self._require_runtime()
        return self._connect_selected_dsn(self.dsn,'vams-effect-authority-v5')

    @staticmethod
    def _connect_migration(migration_dsn):
        return PostgresAuthorityDatabaseV5._connect_selected_dsn(migration_dsn,'vams-effect-authority-v5-migrate')

    @staticmethod
    def _migration_pid(value):
        if type(value) is not int or not 0<value<(1<<31):
            raise EffectV3Error('migration backend identity unavailable')
        return value

    def _assert_migration_backend(self,cursor,expected_pid):
        cursor.execute('SELECT pg_catalog.pg_backend_pid()')
        row=cursor.fetchone()
        if type(row) not in (tuple,list) or len(row)!=1 or self._migration_pid(row[0])!=expected_pid:
            raise EffectV3Error('migration requires one dedicated backend session')

    def migrate(self, migration_dsn):
        """Explicit fresh-only DDL using a separately supplied owner connection.

        This method is not called by construction or by runtime operations. It
        never creates roles/memberships and performs no V3/V4 migration.
        """
        self._require_runtime()
        connection = self._connect_migration(migration_dsn)
        failure = None
        stage = 'SESSION'
        try:
            # The blocking advisory SELECT must finish its own transaction and
            # release its pre-wait snapshot before the protected transaction.
            # This dedicated direct connection must never be transaction-pooled.
            connection.set_session(isolation_level='SERIALIZABLE', readonly=False, autocommit=True)
            if connection.autocommit is not True:
                raise EffectV3Error('migration preflight requires statement transactions')
            stage = 'BODY'
            with connection.cursor() as cursor:
                self._check_roles_and_migration_session(cursor)
                cursor.execute('SELECT pg_catalog.pg_advisory_lock(%s),pg_catalog.pg_backend_pid()',
                    (0x56414D5341563500,))
                lock_row=cursor.fetchone()
                if type(lock_row) not in (tuple,list) or len(lock_row)!=2:
                    raise EffectV3Error('migration session serialization unavailable')
                backend_pid=self._migration_pid(lock_row[1])
                # A new autocommit statement sees state after the lock wait.
                # The SELECT's void-return representation is not authority.
                cursor.execute('SELECT pg_catalog.pg_backend_pid(),'+
                    ','.join('pg_catalog.to_regclass(%s)' for _ in _TABLES5),_TABLES5)
                observed=cursor.fetchone()
                if (type(observed) not in (tuple,list) or len(observed)!=len(_TABLES5)+1 or
                        self._migration_pid(observed[0])!=backend_pid):
                    raise EffectV3Error('storage5 schema inspection unavailable')
                existing=tuple(observed[1:])
                if any(value is not None for value in existing) and not all(value is not None for value in existing):
                    raise EffectV3Error('partial/unversioned V5 schema; no adoption')
            # No transaction snapshot from preflight survives into this phase.
            connection.set_session(isolation_level='SERIALIZABLE', readonly=False, autocommit=False)
            if connection.autocommit is not False:
                raise EffectV3Error('protected migration requires explicit SERIALIZABLE transaction')
            with connection.cursor() as cursor:
                if any(value is not None for value in existing):
                    # Even PID/role-only queries must follow the relation locks.
                    self._lock_unique_tables(cursor)
                    self._assert_migration_backend(cursor,backend_pid)
                    self._check_roles_and_migration_session(cursor)
                    self._verify_schema(cursor,migration=True)
                else:
                    # Nothing exists to lock. Validate this fresh transaction's
                    # principal/backend, then create without IF NOT EXISTS. Own
                    # DDL is visible; any competing creation aborts, never adopts.
                    self._assert_migration_backend(cursor,backend_pid)
                    self._check_roles_and_migration_session(cursor)
                    for statement in DDL5:
                        cursor.execute(statement)
                    self._grant_runtime_privileges(cursor, self.runtime_role)
                    cursor.execute(f'INSERT INTO {META5} VALUES (1,5,%s,%s)',
                        (MIGRATION5, self.configuration_hash))
                    self._verify_schema(cursor,migration=True)
                self._assert_migration_backend(cursor,backend_pid)
            stage = 'COMMIT'
            connection.commit()
        except BaseException as error:
            try:
                connection.rollback()
            except BaseException:
                pass
            try:
                connection.close()
            except BaseException:
                pass
            if not _is_postgres_driver_error(error):
                raise
            failure = EffectPersistenceErrorV3(stage)
        else:
            try:
                # Session serialization spans commit. Only closing this dedicated
                # connection releases it; an uncertain close is UNKNOWN/no retry.
                connection.close()
            except Exception as error:
                if not _is_postgres_driver_error(error):
                    raise
                failure = EffectPersistenceErrorV3('CLOSE')
        if failure is not None:
            raise failure from None
