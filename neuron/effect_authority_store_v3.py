"""Explicit fresh V3 authority schema; no provider/legacy schema adoption."""
import hashlib

from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_protocol_v3 import EffectV3Error, commitment

AUTH_META='public.vams_effect_v3_authority_meta'
SCOPES='public.vams_effect_v3_authority_scopes'
OPERATIONS='public.vams_effect_v3_authority_operations'
AUTH_DDL=(
    f'''CREATE TABLE {AUTH_META} (
        singleton SMALLINT PRIMARY KEY CHECK(singleton=1),version SMALLINT NOT NULL CHECK(version=3),
        migration_hash BYTEA NOT NULL CHECK(octet_length(migration_hash)=32),
        configuration_hash BYTEA NOT NULL CHECK(octet_length(configuration_hash)=32))''',
    f'''CREATE TABLE {SCOPES} (
        scope_id BYTEA PRIMARY KEY CHECK(octet_length(scope_id)=32),scope_bytes BYTEA NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('installing','active','draining','revoked')),
        budget_limit BIGINT NOT NULL CHECK(budget_limit>=0),
        budget_reserved BIGINT NOT NULL CHECK(budget_reserved>=0),
        budget_spent BIGINT NOT NULL CHECK(budget_spent>=0),
        fence_bytes BYTEA NOT NULL,update_bytes BYTEA NOT NULL,ack_bytes BYTEA,
        CHECK(budget_spent<=budget_limit AND budget_reserved<=budget_limit-budget_spent))''',
    f'''CREATE TABLE {OPERATIONS} (
        operation_id BYTEA PRIMARY KEY CHECK(octet_length(operation_id)=32),
        scope_id BYTEA NOT NULL REFERENCES {SCOPES}(scope_id),
        proposal_bytes BYTEA NOT NULL,proposal_digest BYTEA NOT NULL CHECK(octet_length(proposal_digest)=32),
        admission_bytes BYTEA NOT NULL,admission_digest BYTEA UNIQUE NOT NULL CHECK(octet_length(admission_digest)=32),
        nonce BYTEA UNIQUE NOT NULL CHECK(octet_length(nonce)=32),
        cost_units BIGINT NOT NULL CHECK(cost_units>=0),
        status TEXT NOT NULL CHECK(status IN ('reserved','dispatched','indeterminate','committed','rejected')),
        result_bytes BYTEA,
        CHECK((status IN ('committed','rejected'))=(result_bytes IS NOT NULL)))''',
)
AUTH_MIGRATION_HASH=hashlib.sha256(b'VAMS:AUTHORITY-PG-MIGRATION:v3\0'+'\n'.join(AUTH_DDL).encode()).digest()


def authority_configuration(identity):
    return commitment(b'VAMS:AUTHORITY-STORE:v3\0',identity.digest)


class PostgresAuthorityDatabaseV3(PostgresEffectDatabaseV3):
    _foreign_keys = ((OPERATIONS, ('scope_id',), SCOPES, ('scope_id',)),)
    _uniqueness_keys = (
        (AUTH_META, 'p', (('singleton', 21),)),
        (SCOPES, 'p', (('scope_id', 17),)),
        (OPERATIONS, 'p', (('operation_id', 17),)),
        (OPERATIONS, 'u', (('admission_digest', 17),)),
        (OPERATIONS, 'u', (('nonce', 17),)),
    )

    _application_name='vams-effect-authority-v3'
    def _verify_schema(self,cursor):
        self._lock_unique_tables(cursor)
        cursor.execute(f'SELECT version,migration_hash,configuration_hash FROM {AUTH_META} WHERE singleton=1')  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
        row=cursor.fetchone()
        if row is None or row[0]!=3 or bytes(row[1])!=AUTH_MIGRATION_HASH or bytes(row[2])!=self.configuration_hash:
            raise EffectV3Error('authority schema/version/configuration mismatch')
        self._verify_unique_keys(cursor)

    def migrate(self):
        with self._transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(%s)',(0x56414D5341563300,))
                cursor.execute('SELECT to_regclass(%s),to_regclass(%s),to_regclass(%s)',(AUTH_META,SCOPES,OPERATIONS))
                existing=cursor.fetchone()
                if existing is None:raise EffectV3Error('authority schema inspection unavailable')
                if any(v is not None for v in existing):
                    if not all(v is not None for v in existing):raise EffectV3Error('partial/unversioned authority schema')
                    self._verify_schema(cursor)
                    return
                for statement in AUTH_DDL:cursor.execute(statement)
                cursor.execute(f'INSERT INTO {AUTH_META} VALUES(1,3,%s,%s)',(AUTH_MIGRATION_HASH,self.configuration_hash))  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
                self._verify_schema(cursor)
