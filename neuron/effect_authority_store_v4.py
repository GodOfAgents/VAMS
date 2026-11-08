"""Fresh authority storage4 with retained generations; V3 receipts stay V3.

No automatic V3/V2/DBOS adoption or live migration. Native PG qualification and
an explicit reviewed legacy migration remain required before any real adoption.
"""
import hashlib
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_protocol_v3 import EffectV3Error,commitment

META4='public.vams_effect_v4_authority_meta'
GENERATIONS4='public.vams_effect_v4_authority_generations'
HEADS4='public.vams_effect_v4_authority_heads'
OPERATIONS4='public.vams_effect_v4_authority_operations'
DDL4=(
 f'''CREATE TABLE {META4} (singleton SMALLINT PRIMARY KEY CHECK(singleton=1),
 version SMALLINT NOT NULL CHECK(version=4),migration_hash BYTEA NOT NULL CHECK(octet_length(migration_hash)=32),
 configuration_hash BYTEA NOT NULL CHECK(octet_length(configuration_hash)=32))''',
 f'''CREATE TABLE {GENERATIONS4} (
 generation_id BYTEA PRIMARY KEY CHECK(octet_length(generation_id)=32),
 scope_id BYTEA NOT NULL CHECK(octet_length(scope_id)=32),ordinal BIGINT NOT NULL CHECK(ordinal>=1),
 previous_generation BYTEA,scope_bytes BYTEA NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('installing','active','draining','revoked')),
 fence_bytes BYTEA NOT NULL,update_bytes BYTEA NOT NULL,ack_bytes BYTEA,
 closed_reserved BIGINT,closed_spent BIGINT,
 UNIQUE(scope_id,generation_id),UNIQUE(scope_id,ordinal),
 FOREIGN KEY(scope_id,previous_generation) REFERENCES {GENERATIONS4}(scope_id,generation_id),
 CHECK((ordinal=1)=(previous_generation IS NULL)),
 CHECK(previous_generation IS NULL OR previous_generation<>generation_id),
 CHECK((status='revoked' AND closed_reserved IS NOT NULL AND closed_spent IS NOT NULL AND closed_reserved=0 AND closed_spent>=0) OR
       (status<>'revoked' AND closed_reserved IS NULL AND closed_spent IS NULL)))''',
 f'''CREATE TABLE {HEADS4} (
 scope_id BYTEA PRIMARY KEY CHECK(octet_length(scope_id)=32),
 current_generation BYTEA NOT NULL CHECK(octet_length(current_generation)=32),
 budget_limit BIGINT NOT NULL CHECK(budget_limit>0),budget_reserved BIGINT NOT NULL CHECK(budget_reserved>=0),
 budget_spent BIGINT NOT NULL CHECK(budget_spent>=0),
 FOREIGN KEY(scope_id,current_generation) REFERENCES {GENERATIONS4}(scope_id,generation_id),
 CHECK(budget_spent<=budget_limit AND budget_reserved<=budget_limit-budget_spent))''',
 f'''CREATE TABLE {OPERATIONS4} (
 operation_id BYTEA PRIMARY KEY CHECK(octet_length(operation_id)=32),
 scope_id BYTEA NOT NULL REFERENCES {HEADS4}(scope_id),generation_id BYTEA NOT NULL,
 proposal_bytes BYTEA NOT NULL,proposal_digest BYTEA NOT NULL CHECK(octet_length(proposal_digest)=32),
 admission_bytes BYTEA NOT NULL,admission_digest BYTEA UNIQUE NOT NULL CHECK(octet_length(admission_digest)=32),
 nonce BYTEA UNIQUE NOT NULL CHECK(octet_length(nonce)=32),cost_units BIGINT NOT NULL CHECK(cost_units>=0),
 status TEXT NOT NULL CHECK(status IN ('reserved','dispatched','indeterminate','committed','rejected')),result_bytes BYTEA,
 FOREIGN KEY(scope_id,generation_id) REFERENCES {GENERATIONS4}(scope_id,generation_id),
 CHECK((status IN ('committed','rejected'))=(result_bytes IS NOT NULL)))''',
)
MIGRATION4=hashlib.sha256(b'VAMS:AUTHORITY-PG-MIGRATION:v4\0'+'\n'.join(DDL4).encode()).digest()

def authority_configuration_v4(identity):return commitment(b'VAMS:AUTHORITY-STORE:v4\0',identity.digest)

class PostgresAuthorityDatabaseV4(PostgresEffectDatabaseV3):
 _foreign_keys = (
     (GENERATIONS4, ('scope_id','previous_generation'), GENERATIONS4, ('scope_id','generation_id')),
     (HEADS4, ('scope_id','current_generation'), GENERATIONS4, ('scope_id','generation_id')),
     (OPERATIONS4, ('scope_id',), HEADS4, ('scope_id',)),
     (OPERATIONS4, ('scope_id','generation_id'), GENERATIONS4, ('scope_id','generation_id')),
 )
 _uniqueness_keys = (
     (META4, 'p', (('singleton', 21),)),
     (GENERATIONS4, 'p', (('generation_id', 17),)),
     (GENERATIONS4, 'u', (('scope_id', 17), ('generation_id', 17))),
     (GENERATIONS4, 'u', (('scope_id', 17), ('ordinal', 20))),
     (HEADS4, 'p', (('scope_id', 17),)),
     (OPERATIONS4, 'p', (('operation_id', 17),)),
     (OPERATIONS4, 'u', (('admission_digest', 17),)),
     (OPERATIONS4, 'u', (('nonce', 17),)),
 )

 _application_name='vams-effect-authority-v4'
 def _verify_schema(self,cursor):
  self._lock_unique_tables(cursor)
  cursor.execute(f'SELECT version,migration_hash,configuration_hash FROM {META4} WHERE singleton=1')  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
  row=cursor.fetchone()
  if row is None or row[0]!=4 or bytes(row[1])!=MIGRATION4 or bytes(row[2])!=self.configuration_hash:
   raise EffectV3Error('authority storage4 version/configuration mismatch')
  self._verify_unique_keys(cursor)
 def migrate(self):
  with self._transaction() as connection:
   with connection.cursor() as cursor:
    cursor.execute('SELECT pg_advisory_xact_lock(%s)',(0x56414D5341563400,))
    cursor.execute('SELECT to_regclass(%s),to_regclass(%s),to_regclass(%s),to_regclass(%s)',(META4,GENERATIONS4,HEADS4,OPERATIONS4))
    row=cursor.fetchone()
    if row is None:raise EffectV3Error('storage4 inspection unavailable')
    if any(v is not None for v in row):
     if not all(v is not None for v in row):raise EffectV3Error('partial/unversioned storage4 schema')
     self._verify_schema(cursor);return
    for statement in DDL4:cursor.execute(statement)
    cursor.execute(f'INSERT INTO {META4} VALUES(1,4,%s,%s)',(MIGRATION4,self.configuration_hash))  # nosec B608 # fixed SQL identifier; enforced by test_effect_sql_identifier_guard
    self._verify_schema(cursor)
