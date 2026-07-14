"""PostgreSQL-backed atomic stores for the private VDSO shadow gateway."""

from __future__ import annotations

from typing import Callable

from neuron.vdso.service import NonceKey


_CREATE_NONCE_TABLE = """
CREATE TABLE IF NOT EXISTS vams_vdso_nonce_claims (
    actor_root BYTEA NOT NULL,
    state_domain BYTEA NOT NULL,
    authority_epoch NUMERIC(20, 0) NOT NULL,
    intent_nonce NUMERIC(20, 0) NOT NULL,
    intent_id BYTEA NOT NULL,
    PRIMARY KEY (actor_root, state_domain, authority_epoch, intent_nonce)
)
"""

_CLAIM_NONCE = """
INSERT INTO vams_vdso_nonce_claims (
    actor_root, state_domain, authority_epoch, intent_nonce, intent_id
) VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (actor_root, state_domain, authority_epoch, intent_nonce)
DO UPDATE SET intent_id = vams_vdso_nonce_claims.intent_id
WHERE vams_vdso_nonce_claims.intent_id = EXCLUDED.intent_id
RETURNING intent_id
"""

_CREATE_REPLAY_TABLE = """
CREATE TABLE IF NOT EXISTS vams_vdso_auth_replays (
    replay_key TEXT PRIMARY KEY,
    expires_at BIGINT NOT NULL
)
"""

_CREATE_REPLAY_EXPIRY_INDEX = """
CREATE INDEX IF NOT EXISTS vams_vdso_auth_replays_expiry_idx
ON vams_vdso_auth_replays (expires_at, replay_key)
"""

_CLAIM_REPLAY = """
WITH database_clock AS MATERIALIZED (
    SELECT floor(extract(epoch FROM clock_timestamp()))::bigint AS now
), incoming AS MATERIALIZED (
    SELECT %s::text AS replay_key, %s::bigint AS expires_at
), expired AS (
    SELECT replay.replay_key
    FROM vams_vdso_auth_replays AS replay, database_clock, incoming
    WHERE replay.expires_at <= database_clock.now
      AND replay.replay_key <> incoming.replay_key
    ORDER BY replay.expires_at, replay.replay_key
    LIMIT %s
    FOR UPDATE SKIP LOCKED
), pruned AS (
    DELETE FROM vams_vdso_auth_replays AS replay
    USING expired
    WHERE replay.replay_key = expired.replay_key
    RETURNING replay.replay_key
)
INSERT INTO vams_vdso_auth_replays (replay_key, expires_at)
SELECT incoming.replay_key, incoming.expires_at
FROM incoming, database_clock
WHERE incoming.expires_at > database_clock.now
ON CONFLICT (replay_key)
DO UPDATE SET expires_at = EXCLUDED.expires_at
WHERE vams_vdso_auth_replays.expires_at <= (SELECT now FROM database_clock)
RETURNING replay_key
"""


def _connect(dsn: str):
    import psycopg2

    return psycopg2.connect(dsn)


def validate_live_postgres_dsn(dsn: str) -> None:
    """Require loopback/Unix transport or authenticated remote PostgreSQL TLS."""

    try:
        from psycopg2.extensions import parse_dsn

        parsed = parse_dsn(dsn)
    except Exception as exc:
        raise RuntimeError("VDSO_POSTGRES_DSN is not a valid PostgreSQL DSN") from exc
    host = parsed.get("host", "")
    if host in {"", "localhost", "127.0.0.1", "::1"} or host.startswith("/"):
        return
    if parsed.get("sslmode") != "verify-full" or not parsed.get("sslrootcert"):
        raise RuntimeError(
            "remote VDSO PostgreSQL requires sslmode=verify-full and sslrootcert"
        )


class _PostgresStore:
    def __init__(self, dsn: str, *, connect: Callable = _connect) -> None:
        if not isinstance(dsn, str) or not dsn.strip():
            raise RuntimeError("VDSO_POSTGRES_DSN is required for durable shadow state")
        self._dsn = dsn
        self._connect = connect

    @property
    def dsn(self) -> str:
        return self._dsn

    def _execute(self, statement: str, parameters=(), *, fetch_one: bool = False):
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
                    return cursor.fetchone() if fetch_one else None
        finally:
            connection.close()


class PostgresNonceStore(_PostgresStore):
    """Durable multi-process nonce claims with idempotent identical retries."""

    durable = True

    def initialize(self) -> None:
        self._execute(_CREATE_NONCE_TABLE)

    def check_and_record(self, key: NonceKey, intent_id: bytes) -> bool:
        actor_root, state_domain, authority_epoch, intent_nonce = key
        if len(actor_root) != 32 or len(state_domain) != 32 or len(intent_id) != 32:
            raise ValueError("VDSO nonce claims require bytes32 identities")
        if not 0 <= authority_epoch <= (1 << 64) - 1:
            raise ValueError("authority_epoch must be a uint64")
        if not 0 <= intent_nonce <= (1 << 64) - 1:
            raise ValueError("intent_nonce must be a uint64")
        claimed = self._execute(
            _CLAIM_NONCE,
            (
                actor_root,
                state_domain,
                authority_epoch,
                intent_nonce,
                intent_id,
            ),
            fetch_one=True,
        )
        return claimed is not None


class PostgresReplayStore(_PostgresStore):
    """Shared request-auth replay claims safe across processes and restarts."""

    shared = True

    def __init__(
        self,
        dsn: str,
        *,
        connect: Callable = _connect,
        cleanup_batch_size: int = 256,
    ) -> None:
        super().__init__(dsn, connect=connect)
        if not isinstance(cleanup_batch_size, int) or isinstance(
            cleanup_batch_size, bool
        ) or not 1 <= cleanup_batch_size <= 10_000:
            raise ValueError("cleanup_batch_size must be between 1 and 10000")
        self._cleanup_batch_size = cleanup_batch_size

    def initialize(self) -> None:
        self._execute(_CREATE_REPLAY_TABLE)
        self._execute(_CREATE_REPLAY_EXPIRY_INDEX)

    def check_and_record(self, key: str, now: int, expires_at: int) -> bool:
        if not key:
            raise ValueError("replay key must not be empty")
        if not isinstance(now, int) or not isinstance(expires_at, int):
            raise ValueError("replay timestamps must be integers")
        if now < 0 or expires_at <= now:
            raise ValueError("replay expiry must be later than the current time")
        claimed = self._execute(
            _CLAIM_REPLAY,
            (
                key,
                expires_at,
                self._cleanup_batch_size,
            ),
            fetch_one=True,
        )
        return claimed is not None
