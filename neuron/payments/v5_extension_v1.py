"""Sealed opt-in payment catalog contract, never inferred from a runtime DB.

No connection, migration, compiler or approval producer. The base V3 validator
is reused unchanged with one fixed complete FK graph, not a permissive cursor.
"""
from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_protocol_v3 import EffectV3Error
from neuron.payments.ledger_schema_v1 import TABLES, PaymentSchemaManifestV1

WORK = 'public.vams_effect_v5_authority_work'
ATTEMPTS = 'public.vams_effect_v5_authority_attempts'
PAYMENT_KEYS = (
    (TABLES[2], ('operation_id',), WORK, ('operation_id',)),
    (TABLES[2], ('operation_id', 'attempt_id'), ATTEMPTS, ('operation_id', 'attempt_id')),
    (TABLES[2], ('budget_id',), TABLES[1], ('budget_id',)),
    (TABLES[3], ('intent_id',), TABLES[2], ('intent_id',)),
)


def require(value, message):
    if not value:
        raise EffectV3Error(message)


def validate_profile(manifest, stage, version):
    if manifest is None:
        require(stage is None, 'payment stage without selected manifest')
        return
    require(type(manifest) is PaymentSchemaManifestV1 and type(stage) is str
            and stage in ('absent', 'present'), 'explicit sealed payment manifest/stage required')
    manifest.validate()
    require(manifest.server_version_num == version, 'payment/V5 compiler version mismatch')


def verify_absent(cursor):
    cursor.execute('SELECT pg_catalog.to_regclass(%s),pg_catalog.to_regclass(%s),'
                   'pg_catalog.to_regclass(%s),pg_catalog.to_regclass(%s)', TABLES)
    require(cursor.fetchone() == (None, None, None, None), 'selected payment-absent stage has existing relations')


def lock_payment_tables(cursor):
    for table in TABLES:
        # Names originate exclusively in this source version's fixed DDL tuple.
        cursor.execute('LOCK TABLE ONLY ' + table + ' IN SHARE UPDATE EXCLUSIVE MODE')


def verify_present(cursor, manifest, migration_role, v5_tables, v5_keys):
    """Caller holds all V5 then payment locks before its first ordinary SELECT."""
    require(type(manifest) is PaymentSchemaManifestV1, 'sealed payment schema required')
    manifest.validate()
    cursor.execute('''SELECT n.nspname::text||'.'||t.relname::text,t.relowner::regrole::text,
        t.relkind::text,t.relpersistence::text,t.relrowsecurity,t.relforcerowsecurity,t.relispartition,
        NOT EXISTS(SELECT 1 FROM pg_catalog.pg_inherits h WHERE h.inhparent=t.oid OR h.inhrelid=t.oid),
        NOT EXISTS(SELECT 1 FROM pg_catalog.pg_rewrite r WHERE r.ev_class=t.oid)
        FROM pg_catalog.pg_class t JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname::text||'.'||t.relname::text=ANY(%s)''', (list(TABLES),))
    rows = cursor.fetchall()
    expected = {(table, migration_role, 'r', 'p', False, False, False, True, True) for table in TABLES}
    require(type(rows) is list and len(rows) == len(expected) and
            all(type(row) in (tuple, list) and len(row) == 9 and
                all(type(row[i]) is str for i in range(4)) and
                all(type(row[i]) is bool for i in range(4, 9)) for row in rows) and
            {tuple(row) for row in rows} == expected, 'payment extension relation identity/interception mismatch')
    cursor.execute('''SELECT n.nspname::text||'.'||t.relname::text,c.contype::text,
        pg_catalog.pg_get_constraintdef(c.oid,true),c.convalidated,c.conenforced,c.condeferrable,c.condeferred,
        c.conislocal,c.coninhcount::int,c.conparentid::bigint
        FROM pg_catalog.pg_constraint c JOIN pg_catalog.pg_class t ON t.oid=c.conrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname::text||'.'||t.relname::text=ANY(%s) AND c.contype IN ('c','p','u','f')''', (list(TABLES),))
    rows = cursor.fetchall()
    require(type(rows) is list and len(rows) == len(manifest.constraints), 'complete payment compiled constraints required')
    seen = set()
    for row in rows:
        require(type(row) in (tuple, list) and len(row) == 10, 'malformed payment constraint row')
        require(all(type(row[i]) is str for i in (0, 1, 2)) and
                all(row[i] is True for i in (3, 4, 7)) and
                all(row[i] is False for i in (5, 6)) and
                type(row[8]) is int and row[8] == 0 and type(row[9]) is int and row[9] == 0,
                'payment compiled constraint enforcement drift')
        key = tuple(row[:3])
        require(key not in seen, 'duplicate payment compiled constraint')
        seen.add(key)
    require(tuple(sorted(seen)) == manifest.constraints, 'payment compiled constraint identity drift')

    # Sealed instance-local FK contract: no alteration of shared V3/V5 classes,
    # no discovered allow-list and no cursor filtering. Base validator sees all
    # rows, including unexpected incoming FKs and all internal/noninternal triggers.
    class Contract:
        _foreign_keys = tuple(v5_keys) + PAYMENT_KEYS
    PostgresEffectDatabaseV3._verify_foreign_keys_and_triggers(
        Contract(), cursor, list(v5_tables) + list(TABLES))
