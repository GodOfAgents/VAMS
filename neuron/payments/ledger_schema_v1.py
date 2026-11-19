"""Payment add-on for V5 retained operations; no reinterpretation of V5 rows.

Money is uint256 atomic units, separate from the V5 BIGINT execution-cost budget.
An explicit PG18 compiled-constraint manifest is required by the consumer. This
DDL is neither a live migration nor evidence of a qualified database/operator.
"""
from dataclasses import dataclass
import hashlib
import json

UINT256_MAX = (1 << 256) - 1
TABLES = ('public.vams_payment_meta_v1', 'public.vams_payment_budgets_v1',
          'public.vams_payment_intents_v1', 'public.vams_payment_events_v1')
DDL = (
    '''CREATE TABLE public.vams_payment_meta_v1 (
        singleton SMALLINT PRIMARY KEY CHECK (singleton=1),
        version SMALLINT NOT NULL CHECK (version=1),
        migration_hash BYTEA NOT NULL CHECK (octet_length(migration_hash)=32),
        configuration_hash BYTEA NOT NULL CHECK (octet_length(configuration_hash)=32))''',
    f'''CREATE TABLE public.vams_payment_budgets_v1 (
        budget_id BYTEA PRIMARY KEY CHECK (octet_length(budget_id)=32),
        denomination BYTEA NOT NULL CHECK (octet_length(denomination)=32),
        reserved NUMERIC(78,0) NOT NULL CHECK (reserved>=0 AND reserved<={UINT256_MAX}),
        revision BIGINT NOT NULL CHECK (revision>=0))''',
    f'''CREATE TABLE public.vams_payment_intents_v1 (
        key_digest BYTEA PRIMARY KEY CHECK (octet_length(key_digest)=32),
        operation_id BYTEA NOT NULL UNIQUE REFERENCES public.vams_effect_v5_authority_work(operation_id),
        attempt_id BYTEA NOT NULL UNIQUE,
        intent_id BYTEA NOT NULL UNIQUE CHECK (octet_length(intent_id)=32),
        budget_id BYTEA NOT NULL REFERENCES public.vams_payment_budgets_v1(budget_id),
        nonce_key BYTEA NOT NULL UNIQUE CHECK (octet_length(nonce_key)=32),
        amount NUMERIC(78,0) NOT NULL CHECK (amount>0 AND amount<={UINT256_MAX}),
        intent_bytes BYTEA NOT NULL CHECK (octet_length(intent_bytes) BETWEEN 1 AND 8192),
        approval_bytes BYTEA NOT NULL CHECK (octet_length(approval_bytes) BETWEEN 1 AND 8192),
        state TEXT NOT NULL CHECK (state IN ('reserved','exposed','unknown')),
        credential_digest BYTEA CHECK (credential_digest IS NULL OR octet_length(credential_digest)=32),
        revision BIGINT NOT NULL CHECK (revision>=1 AND revision<=32),
        CHECK ((state='reserved' AND credential_digest IS NULL) OR
               (state='exposed' AND credential_digest IS NOT NULL) OR state='unknown'),
        FOREIGN KEY (operation_id,attempt_id)
          REFERENCES public.vams_effect_v5_authority_attempts(operation_id,attempt_id))''',
    '''CREATE INDEX vams_payment_budget_lookup_v1 ON public.vams_payment_intents_v1(budget_id)''',
    '''CREATE TABLE public.vams_payment_events_v1 (
        intent_id BYTEA NOT NULL REFERENCES public.vams_payment_intents_v1(intent_id),
        event_seq BIGINT NOT NULL CHECK (event_seq BETWEEN 1 AND 32),
        state TEXT NOT NULL CHECK (state IN ('reserved','exposed','unknown')),
        evidence_digest BYTEA NOT NULL CHECK (octet_length(evidence_digest)=32),
        event_digest BYTEA NOT NULL UNIQUE CHECK (octet_length(event_digest)=32),
        PRIMARY KEY (intent_id,event_seq))''',
)

MIGRATION_HASH = hashlib.sha256(b'VAMS:PAYMENT-MIGRATION:v1\0' + '\n'.join(DDL).encode()).digest()
# Constraint counts include every CHECK, key and foreign key; no manifest can
# omit one kind and replace it with an equal number of another kind.
CONSTRAINT_COUNTS = {
    TABLES[0]: {'c': 4, 'p': 1},
    TABLES[1]: {'c': 4, 'p': 1},
    TABLES[2]: {'c': 10, 'p': 1, 'u': 4, 'f': 3},
    TABLES[3]: {'c': 4, 'p': 1, 'u': 1, 'f': 1},
}
COLUMNS = {
    TABLES[0]: 'singleton:int2 version:int2 migration_hash:bytea configuration_hash:bytea',
    TABLES[1]: 'budget_id:bytea denomination:bytea reserved:numeric(78,0) revision:int8',
    TABLES[2]: 'key_digest:bytea operation_id:bytea attempt_id:bytea intent_id:bytea budget_id:bytea '
               'nonce_key:bytea amount:numeric(78,0) intent_bytes:bytea approval_bytes:bytea '
               'state:text credential_digest:bytea? revision:int8',
    TABLES[3]: 'intent_id:bytea event_seq:int8 state:text evidence_digest:bytea event_digest:bytea',
}


@dataclass(frozen=True)
class PaymentSchemaManifestV1:
    """Reviewed exact PG18 compilation identities, never inferred from a live DB."""
    migration_hash: bytes
    compiler_identity: bytes
    provenance_identity: bytes
    server_version_num: int
    constraints: tuple

    def validate(self):
        for value in (self.migration_hash, self.compiler_identity, self.provenance_identity):
            if type(value) is not bytes or len(value) != 32 or value == bytes(32):
                raise ValueError('explicit schema/compiler/provenance identities required')
        if self.migration_hash != MIGRATION_HASH:
            raise ValueError('payment migration version/hash mismatch')
        if type(self.server_version_num) is not int or not 180000 <= self.server_version_num < 190000:
            raise ValueError('explicit PostgreSQL18 compiler binding required')
        if type(self.constraints) is not tuple or tuple(sorted(self.constraints)) != self.constraints:
            raise ValueError('canonical compiled constraint manifest required')
        observed = {table: {} for table in TABLES}
        definitions = set()
        for row in self.constraints:
            if (type(row) is not tuple or len(row) != 3 or row[0] not in TABLES or
                    row[1] not in ('c', 'p', 'u', 'f') or type(row[2]) is not str or
                    not 1 <= len(row[2]) <= 8192 or row in definitions):
                raise ValueError('invalid compiled payment constraint')
            definitions.add(row)
            counts = observed[row[0]]
            counts[row[1]] = counts.get(row[1], 0) + 1
        if observed != CONSTRAINT_COUNTS:
            raise ValueError('payment manifest omits or adds constraints')

    @property
    def digest(self):
        self.validate()
        raw = json.dumps(self.constraints, ensure_ascii=True, separators=(',', ':')).encode()
        return hashlib.sha256(b'VAMS:PAYMENT-SCHEMA:v1\0' + self.migration_hash +
            self.compiler_identity + self.provenance_identity + self.server_version_num.to_bytes(32, 'big') + raw).digest()
