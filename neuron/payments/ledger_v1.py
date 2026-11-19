"""Local-only payment reservations over retained V5 operations and attempts.

This add-on neither signs a token authorization, pays, dispatches, proves funds,
nor releases reservations. Unknown/expired/absent effects never erase a possible
payment obligation. A future authentic chain-resolution consumer is required.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import time

from neuron.effect_attempt_journal_v5 import PostgresAttemptJournalV5
from neuron.effect_authority_store_v5 import PostgresAuthorityDatabaseV5
from neuron.effect_postgres_v3 import EffectPersistenceErrorV3, _is_postgres_driver_error
from neuron.effect_protocol_v3 import hash32, integer
from neuron.runtime_safety import ImmutableRuntimeConfiguration, load_runtime_policy, RuntimeConfigurationError
from neuron.payments.intent_v1 import (
    PaymentIntentV1, PaymentApprovalV1, PaymentPolicyBindingV1, PaymentPolicyError,
)
from neuron.payments.ledger_schema_v1 import (
    TABLES, DDL, MIGRATION_HASH, COLUMNS, PaymentSchemaManifestV1, UINT256_MAX,
)

MAX_BUDGET_INTENTS = 256
KEY_DOMAIN = b'VAMS:PAYMENT-IDEMPOTENCY:v1\0'
NONCE_DOMAIN = b'VAMS:PAYMENT-TOKEN-NONCE:v1\0'
EVENT_DOMAIN = b'VAMS:PAYMENT-LEDGER-EVENT:v1\0'


class PaymentLedgerError(ValueError):
    pass


class PaymentConflict(PaymentLedgerError):
    pass


def require(ok, message):
    if not ok:
        raise PaymentLedgerError(message)


def _bytes(value, size=None):
    if type(value) is memoryview:
        value = value.tobytes()
    require(type(value) is bytes and (size is None or len(value) == size), 'invalid retained bytes')
    return value


def _money(value):
    if type(value) is Decimal:
        require(value.is_finite() and value == value.to_integral_value(), 'invalid retained money')
        value = int(value)
    require(type(value) is int and 0 <= value <= UINT256_MAX, 'invalid uint256 money')
    return value


@dataclass(frozen=True)
class PaymentIdempotencyKeyV1:
    actor_root: bytes
    host_domain: bytes
    operation_type: bytes
    client_key: bytes = field(repr=False)

    @property
    def digest(self):
        for value in (self.actor_root, self.host_domain, self.operation_type):
            hash32(value)
        require(type(self.client_key) is bytes and 1 <= len(self.client_key) <= 128,
                'bounded caller idempotency key required')
        return hashlib.sha256(KEY_DOMAIN + self.actor_root + self.host_domain +
            self.operation_type + len(self.client_key).to_bytes(2, 'big') + self.client_key).digest()


@dataclass(frozen=True)
class PaymentLedgerRecordV1:
    intent: PaymentIntentV1
    state: str
    credential_digest: bytes | None
    revision: int

    @property
    def signing_authorized(self):
        # A returned ledger record is never a credential-release capability.
        return False

    @property
    def native_payment_verified(self):
        return False


class PaymentLedgerV1(ImmutableRuntimeConfiguration):
    _immutable_runtime_fields = frozenset({'database', 'journal', 'policy', 'schema_manifest',
        'configuration_hash', 'runtime_policy', '_clock'})

    def __init__(self, database, journal, policy, schema_manifest, *,
                 clock=lambda: time.time_ns() // 1_000_000_000):
        self.runtime_policy = load_runtime_policy()
        if self.runtime_policy.is_live:
            raise RuntimeConfigurationError('unqualified payment ledger cannot run live')
        require(type(database) is PostgresAuthorityDatabaseV5 and type(journal) is PostgresAttemptJournalV5,
                'exact configured V5 database and attempt journal required')
        require(journal.database is database, 'payment/effect transaction database differs')
        require(type(policy) is PaymentPolicyBindingV1 and type(schema_manifest) is PaymentSchemaManifestV1,
                'explicit payment policy and compiled schema manifest required')
        schema_manifest.validate()
        require(schema_manifest.server_version_num == database.check_manifest.server_version_num,
                'payment and V5 PostgreSQL compiler versions differ')
        require(policy.authority == journal.identity.authority,
                'payment and effect admission authority differ')
        require(policy.approval_verifier.public_key_bytes != journal.identity.provider.public_key_bytes,
                'provider verification key cannot issue payment authority')
        require(callable(clock), 'explicit payment clock required')
        self.database, self.journal, self.policy = database, journal, policy
        self.schema_manifest, self._clock = schema_manifest, clock
        self.configuration_hash = hashlib.sha256(b'VAMS:PAYMENT-LEDGER-CONFIG:v1\0' +
            database.configuration_hash + schema_manifest.digest + policy.authority.public_key_bytes +
            policy.approval_verifier.public_key_bytes).digest()
        self._freeze_runtime_configuration()

    def _now(self):
        if load_runtime_policy() != self.runtime_policy or self.runtime_policy.is_live:
            raise RuntimeConfigurationError('payment runtime configuration changed or became live')
        return integer(self._clock())

    def _verify_schema(self, cursor):
        # Fixed relation names only; relation locks precede catalog inspection.
        cursor.execute('''LOCK TABLE public.vams_payment_meta_v1, public.vams_payment_budgets_v1,
            public.vams_payment_intents_v1, public.vams_payment_events_v1 IN SHARE UPDATE EXCLUSIVE MODE''')
        cursor.execute("SELECT pg_catalog.current_setting('server_version_num')::int")
        require(cursor.fetchone() == (self.schema_manifest.server_version_num,), 'payment PostgreSQL version drift')
        cursor.execute('''SELECT singleton,version,migration_hash,configuration_hash
            FROM public.vams_payment_meta_v1''')
        rows = cursor.fetchall()
        require(len(rows) == 1 and tuple(rows[0][:2]) == (1, 1) and
                _bytes(rows[0][2], 32) == MIGRATION_HASH and
                _bytes(rows[0][3], 32) == self.configuration_hash, 'payment schema/configuration mismatch')
        cursor.execute('''SELECT n.nspname||'.'||c.relname, a.attname,
            CASE WHEN a.atttypid=1700 THEN pg_catalog.format_type(a.atttypid,a.atttypmod)
                 ELSE t.typname::text END, a.attnotnull,a.attgenerated,a.attidentity
            FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_catalog.pg_type t ON t.oid=a.atttypid
            WHERE a.attrelid=ANY(%s::regclass[]) AND a.attnum>0 AND NOT a.attisdropped''', (list(TABLES),))
        actual = set()
        for table, name, type_, notnull, generated, identity in cursor.fetchall():
            require(generated == identity == '', 'generated payment columns are unsupported')
            actual.add((table, name, type_, notnull))
        expected = set()
        for table, columns in COLUMNS.items():
            for item in columns.split():
                name, type_ = item.split(':')
                expected.add((table, name, type_.rstrip('?'), not type_.endswith('?')))
        require(actual == expected, 'payment column identity mismatch')
        cursor.execute('''SELECT n.nspname||'.'||c.relname,k.contype::text,
            pg_catalog.pg_get_constraintdef(k.oid,true),k.condeferrable,k.condeferred,k.convalidated
            FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE k.conrelid=ANY(%s::regclass[]) AND k.contype IN ('c','p','u','f')''', (list(TABLES),))
        constraints = []
        for table, type_, definition, deferred, initially, validated in cursor.fetchall():
            require(deferred is False and initially is False and validated is True,
                    'payment constraints must enforce immediately')
            constraints.append((table, type_, definition))
        require(tuple(sorted(constraints)) == self.schema_manifest.constraints, 'payment constraint identity mismatch')
        cursor.execute('''SELECT c.relowner::regrole::text,c.relkind::text,c.relpersistence::text,
            c.relrowsecurity,c.relforcerowsecurity,c.relispartition
            FROM pg_catalog.pg_class c WHERE c.oid=ANY(%s::regclass[])''', (list(TABLES),))
        properties = cursor.fetchall()
        require(len(properties) == 4 and all(tuple(row) == (self.database.migration_role, 'r', 'p', False, False, False)
                for row in properties), 'payment owner/relation configuration mismatch')
        cursor.execute('''SELECT 1 FROM pg_catalog.pg_trigger WHERE tgrelid=ANY(%s::regclass[])
            AND (NOT tgisinternal OR tgenabled<>'O') LIMIT 1''', (list(TABLES),))
        require(cursor.fetchone() is None, 'payment enforcement triggers differ')
        cursor.execute('''SELECT 1 FROM pg_catalog.pg_inherits
            WHERE inhrelid=ANY(%s::regclass[]) OR inhparent=ANY(%s::regclass[]) LIMIT 1''', (list(TABLES), list(TABLES)))
        require(cursor.fetchone() is None, 'payment inheritance is unsupported')
        cursor.execute('''SELECT n.nspname||'.'||c.relname,x.grantee::regrole::text,
            x.privilege_type,x.is_grantable FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,
              pg_catalog.acldefault('r',c.relowner))) x WHERE c.oid=ANY(%s::regclass[])''', (list(TABLES),))
        runtime_grants = set()
        for table, role, privilege, grantable in cursor.fetchall():
            if role == self.database.migration_role:
                continue
            require(role == self.database.runtime_role and grantable is False, 'unreviewed payment table grantee/grant option')
            runtime_grants.add((table, privilege))
        expected_grants = {(table, privilege) for table in TABLES for privilege in
                           (('SELECT', 'MAINTAIN') if table == TABLES[0] else ('SELECT', 'INSERT', 'MAINTAIN'))}
        require(runtime_grants == expected_grants, 'payment runtime table privileges differ')
        cursor.execute('''SELECT n.nspname||'.'||c.relname,a.attname,x.grantee::regrole::text,
            x.privilege_type,x.is_grantable FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(a.attacl) x
            WHERE a.attrelid=ANY(%s::regclass[]) AND a.attnum>0 AND NOT a.attisdropped''', (list(TABLES),))
        column_grants = set()
        for table, column, role, privilege, grantable in cursor.fetchall():
            if role == self.database.migration_role:
                continue
            require(role == self.database.runtime_role and privilege == 'UPDATE' and grantable is False,
                    'unreviewed payment column grant')
            column_grants.add((table, column))
        require(column_grants == {(TABLES[1], 'reserved'), (TABLES[1], 'revision'),
                (TABLES[2], 'state'), (TABLES[2], 'credential_digest'), (TABLES[2], 'revision')},
                'payment runtime update columns differ')

    def migrate(self, migration_dsn):
        """Explicit dedicated owner connection, no adoption of an existing schema.

        Any existing/partial/uncertain submission stops; no automatic retry. Role
        provisioning and a reviewed compiled PG18 manifest are prior inputs.
        """
        self._now()
        connection = self.database._connect_migration(migration_dsn)
        failure = None
        stage = 'SESSION'
        try:
            connection.set_session(isolation_level='SERIALIZABLE', readonly=False, autocommit=False)
            require(connection.autocommit is False, 'explicit transactional payment migration required')
            with connection.cursor() as cursor:
                self.database._lock_unique_tables(cursor)
                self.database._check_roles_and_migration_session(cursor)
                self.database._verify_schema(cursor, migration=True)
                cursor.execute('SELECT pg_catalog.pg_advisory_xact_lock(%s)', (0x56414D5350415931,))
                cursor.execute('SELECT pg_catalog.to_regclass(%s)', (TABLES[0],))
                require(cursor.fetchone() == (None,), 'existing payment schema; inspect, do not adopt/retry')
                for statement in DDL:
                    cursor.execute(statement)
                cursor.execute('''INSERT INTO public.vams_payment_meta_v1
                    VALUES (1,1,%s,%s)''', (MIGRATION_HASH, self.configuration_hash))
                from psycopg2 import sql
                runtime = sql.Identifier(self.database.runtime_role)
                cursor.execute(sql.SQL('GRANT SELECT,MAINTAIN ON public.vams_payment_meta_v1 TO {}').format(runtime))
                cursor.execute(sql.SQL('GRANT SELECT,INSERT,MAINTAIN ON public.vams_payment_budgets_v1, '
                    'public.vams_payment_intents_v1,public.vams_payment_events_v1 TO {}').format(runtime))
                cursor.execute(sql.SQL('GRANT UPDATE (reserved,revision) ON public.vams_payment_budgets_v1 TO {}').format(runtime))
                cursor.execute(sql.SQL('GRANT UPDATE (state,credential_digest,revision) ON public.vams_payment_intents_v1 TO {}').format(runtime))
                self._verify_schema(cursor)
            stage = 'COMMIT'
            connection.commit()
            stage = 'CLOSE'
            connection.close()
        except BaseException as error:
            try: connection.rollback()
            except BaseException: pass
            try: connection.close()
            except BaseException: pass
            if not _is_postgres_driver_error(error):
                raise
            failure = EffectPersistenceErrorV3(stage)
        if failure is not None:
            raise failure from None

    @staticmethod
    def _lock_budget(cursor, budget_id):
        hash32(budget_id)
        key = int.from_bytes(hashlib.sha256(b'VAMS:PAYMENT-BUDGET-LOCK:v1\0' + budget_id).digest()[:8], 'big', signed=True)
        cursor.execute('SELECT pg_catalog.pg_advisory_xact_lock(%s)', (key,))

    def _retained(self, cursor, intent, attempt, now):
        self.journal._lock_operation(cursor, intent.operation_id)
        operation, scope = self.journal._locate_attempt(cursor, intent.attempt_id)
        require(operation == intent.operation_id, 'payment operation differs from retained attempt')
        self.journal._lock_scope(cursor, scope)
        read, facts, head = self.journal._history(cursor, intent.attempt_id, now)
        self.journal._load_head(cursor, scope, for_update=True)
        require(read.attempt == attempt and facts.attempt == attempt, 'payment attempt differs from retained signed facts')
        require(facts.generation.status == 'active' and head[0] == facts.generation_id and
                read.events[-1].kind == 'reserved', 'new payment requires a current reserved V5 obligation')
        intent.validate_for(attempt)

    @staticmethod
    def _nonce_key(intent):
        return hashlib.sha256(NONCE_DOMAIN + intent.chain_id.to_bytes(32, 'big') + intent.asset + intent.payer + intent.nonce).digest()

    def _record(self, row):
        if row is None:
            return None
        require(type(row) in (tuple, list) and len(row) == 8, 'malformed retained payment row')
        intent = PaymentIntentV1.from_bytes(_bytes(row[0]))
        approval = PaymentApprovalV1.from_bytes(_bytes(row[1]))
        self.policy.approval_verifier.verify(intent, approval, approval.issued_at)
        require(_bytes(row[2], 32) == intent.digest and _money(row[3]) == intent.amount and
                _bytes(row[4], 32) == intent.budget_identity, 'retained intent commitment mismatch')
        require(row[5] in ('reserved', 'exposed', 'unknown') and type(row[7]) is int and 1 <= row[7] <= 32,
                'invalid retained payment state/revision')
        credential = None if row[6] is None else hash32(_bytes(row[6], 32))
        require((row[5] != 'reserved' or credential is None) and (row[5] != 'exposed' or credential is not None),
                'payment exposure state differs from credential commitment')
        return PaymentLedgerRecordV1(intent, row[5], credential, row[7])

    def _lookup(self, cursor, key_digest):
        cursor.execute('''SELECT intent_bytes,approval_bytes,intent_id,amount,budget_id,state,credential_digest,revision
            FROM public.vams_payment_intents_v1 WHERE key_digest=%s''', (key_digest,))
        record = self._record(cursor.fetchone())
        if record is not None:
            self._events(cursor, record)
        return record

    @staticmethod
    def _event_digest(intent_id, sequence, state, evidence, previous):
        return hashlib.sha256(EVENT_DOMAIN + intent_id + sequence.to_bytes(32, 'big') +
            len(state).to_bytes(1, 'big') + state.encode('ascii') + evidence + previous).digest()

    def _events(self, cursor, record):
        cursor.execute('''SELECT event_seq,state,evidence_digest,event_digest FROM public.vams_payment_events_v1
            WHERE intent_id=%s ORDER BY event_seq LIMIT 33''', (record.intent.digest,))
        rows = cursor.fetchall()
        require(len(rows) == record.revision, 'payment history is truncated/overbound')
        previous = bytes(32)
        allowed = None
        exposed_credential = None
        for expected, row in enumerate(rows, 1):
            sequence, state, evidence, digest = row
            evidence, digest = hash32(_bytes(evidence, 32)), hash32(_bytes(digest, 32))
            require(type(sequence) is int and sequence == expected and state in ('reserved', 'exposed', 'unknown'),
                    'payment event sequence/state is invalid')
            require((expected == 1 and state == 'reserved') or
                    (allowed == 'reserved' and state in ('exposed', 'unknown')) or
                    (allowed == 'exposed' and state == 'unknown'), 'payment history has an invalid transition')
            require(digest == self._event_digest(record.intent.digest, sequence, state, evidence, previous),
                    'payment event commitment mismatch')
            if state == 'exposed':
                exposed_credential = evidence
            previous, allowed = digest, state
        require(allowed == record.state, 'payment row differs from retained history')
        require(record.credential_digest == exposed_credential,
                'retained credential differs from complete exposure history')
        return previous

    def _append(self, cursor, record, state, evidence):
        hash32(evidence)
        previous = self._events(cursor, record) if record.revision else bytes(32)
        sequence = record.revision + 1
        require(sequence <= 32, 'payment event bound exceeded')
        digest = self._event_digest(record.intent.digest, sequence, state, evidence, previous)
        cursor.execute('''INSERT INTO public.vams_payment_events_v1
            (intent_id,event_seq,state,evidence_digest,event_digest) VALUES (%s,%s,%s,%s,%s)''',
            (record.intent.digest, sequence, state, evidence, digest))
        return sequence

    def lookup(self, key):
        """Read retained status only; no policy denial can erase obligations."""
        self._now()
        require(type(key) is PaymentIdempotencyKeyV1, 'typed authenticated key scope required')
        with self.database.transaction() as cursor:
            self._verify_schema(cursor)
            result = self._lookup(cursor, key.digest)
        return result

    def reserve(self, key, intent, attempt, approval):
        now = self._now()
        require(type(key) is PaymentIdempotencyKeyV1 and type(intent) is PaymentIntentV1,
                'typed payment intent and key scope required')
        require((key.actor_root, key.host_domain) == (intent.actor_root, intent.host_domain), 'key principal/host mismatch')
        intent.validate_for(attempt)
        with self.database.transaction() as cursor:
            self._verify_schema(cursor)
            self.journal._lock_operation(cursor, intent.operation_id)
            existing = self._lookup(cursor, key.digest)
            if existing is not None:
                if existing.intent != intent:
                    raise PaymentConflict('scoped idempotency key already binds different commercial terms')
                # Lookup-only retry, not authorization. Signing preparation is separate.
                result = existing
            else:
                self._retained(cursor, intent, attempt, now)
                self.policy.validate_new(intent, attempt, approval, now)
                cursor.execute('''SELECT key_digest FROM public.vams_payment_intents_v1
                    WHERE operation_id=%s OR attempt_id=%s OR nonce_key=%s LIMIT 1''',
                    (intent.operation_id, intent.attempt_id, self._nonce_key(intent)))
                if cursor.fetchone() is not None:
                    raise PaymentConflict('operation/attempt/token authorization already has a payment obligation')
                self._lock_budget(cursor, intent.budget_identity)
                cursor.execute('''SELECT denomination,reserved,revision FROM public.vams_payment_budgets_v1
                    WHERE budget_id=%s FOR UPDATE''', (intent.budget_identity,))
                head = cursor.fetchone()
                if head is None:
                    cursor.execute('''INSERT INTO public.vams_payment_budgets_v1 VALUES (%s,%s,0,0)''',
                                   (intent.budget_identity, intent.budget_fingerprint))
                    reserved, revision = 0, 0
                else:
                    require(_bytes(head[0], 32) == intent.budget_fingerprint, 'budget denomination/principal changed')
                    reserved, revision = _money(head[1]), integer(head[2])
                cursor.execute('''SELECT amount FROM public.vams_payment_intents_v1
                    WHERE budget_id=%s LIMIT 257''', (intent.budget_identity,))
                rows = cursor.fetchall()
                require(len(rows) < MAX_BUDGET_INTENTS and sum(_money(row[0]) for row in rows) == reserved,
                        'budget history exceeds bound or differs from retained liabilities')
                require(intent.amount <= self.policy.capability.max_aggregate - reserved, 'shared monetary budget exhausted')
                cursor.execute('''UPDATE public.vams_payment_budgets_v1 SET reserved=%s,revision=%s
                    WHERE budget_id=%s AND revision=%s''',
                    (reserved + intent.amount, revision + 1, intent.budget_identity, revision))
                require(cursor.rowcount == 1, 'monetary reservation compare-and-set failed')
                cursor.execute('''INSERT INTO public.vams_payment_intents_v1
                    (key_digest,operation_id,attempt_id,intent_id,budget_id,nonce_key,amount,intent_bytes,
                     approval_bytes,state,credential_digest,revision)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'reserved',NULL,1)''',
                    (key.digest, intent.operation_id, intent.attempt_id, intent.digest, intent.budget_identity,
                     self._nonce_key(intent), intent.amount, intent.canonical_bytes(), approval.canonical_bytes()))
                empty = PaymentLedgerRecordV1(intent, 'reserved', None, 0)
                self._append(cursor, empty, 'reserved', approval.digest)
                later = self._now()
                require(later >= now, 'payment clock moved backwards during reservation')
                self.policy.validate_new(intent, attempt, approval, later)
                result = PaymentLedgerRecordV1(intent, 'reserved', None, 1)
        # Commit/close failures propagate as uncertainty; no result escapes early.
        return result

    def mark_potentially_released(self, key, intent, attempt, approval, credential_digest):
        now = self._now()
        hash32(credential_digest)
        require(type(key) is PaymentIdempotencyKeyV1, 'typed payment key required')
        with self.database.transaction() as cursor:
            self._verify_schema(cursor)
            self._retained(cursor, intent, attempt, now)
            record = self._lookup(cursor, key.digest)
            require(record is not None and record.intent == intent, 'original payment reservation required')
            self.policy.validate_new(intent, attempt, approval, now)
            if record.state == 'exposed' and record.credential_digest == credential_digest:
                result = record
            else:
                require(record.state == 'reserved', 'unresolved exposure cannot authorize another credential')
                sequence = self._append(cursor, record, 'exposed', credential_digest)
                cursor.execute('''UPDATE public.vams_payment_intents_v1 SET state='exposed',credential_digest=%s,revision=%s
                    WHERE key_digest=%s AND revision=%s''', (credential_digest, sequence, key.digest, record.revision))
                require(cursor.rowcount == 1, 'payment exposure compare-and-set failed')
                later = self._now()
                require(later >= now, 'payment clock moved backwards during exposure')
                self.policy.validate_new(intent, attempt, approval, later)
                result = PaymentLedgerRecordV1(intent, 'exposed', credential_digest, sequence)
        return result

    def record_unknown(self, key, reason_digest):
        self._now()
        hash32(reason_digest)
        require(type(key) is PaymentIdempotencyKeyV1, 'typed payment key required')
        with self.database.transaction() as cursor:
            self._verify_schema(cursor)
            record = self._lookup(cursor, key.digest)
            require(record is not None, 'original reservation required for uncertainty')
            self.journal._lock_operation(cursor, record.intent.operation_id)
            record = self._lookup(cursor, key.digest)
            if record.state == 'unknown':
                result = record
            else:
                sequence = self._append(cursor, record, 'unknown', reason_digest)
                cursor.execute('''UPDATE public.vams_payment_intents_v1 SET state='unknown',revision=%s
                    WHERE key_digest=%s AND revision=%s''', (sequence, key.digest, record.revision))
                require(cursor.rowcount == 1, 'payment uncertainty compare-and-set failed')
                result = PaymentLedgerRecordV1(record.intent, 'unknown', record.credential_digest, sequence)
        return result
