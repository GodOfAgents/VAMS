"""Durable gateway replay reservation and signer revocation (M2.2).

The SQLite backend is deliberately host-local.  It coordinates independent
gateway worker processes only when they share this exact database on one host.
It is not a distributed-store claim and must not be placed on a network share.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Protocol

from gateway.request_auth import (
    AUTH_MAX_FUTURE_SKEW_SECONDS,
    Clock,
    ProcessLocalReplayStore,
    ReplayNamespace,
    ReplayOutcome,
    ReplayStore,
    SystemClock,
)
from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    RuntimeConfigurationError,
    RuntimePolicy,
    load_runtime_policy,
)


REPLAY_DATABASE_VARIABLE = "GATEWAY_AUTH_REPLAY_DB"
REPLAY_SCHEMA_VERSION = 1
REPLAY_LOCK_TIMEOUT_SECONDS = 0.25
REPLAY_RETENTION_SAFETY_MARGIN_SECONDS = 60
REPLAY_CLOCK_ROLLBACK_TOLERANCE_SECONDS = AUTH_MAX_FUTURE_SKEW_SECONDS
REPLAY_CLEANUP_BATCH_SIZE = 256
_MAX_SQLITE_INTEGER = (1 << 63) - 1

_CREATE_REPLAY_METADATA = """CREATE TABLE replay_metadata (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                schema_version INTEGER NOT NULL CHECK (schema_version = 1),
                backend_identity TEXT NOT NULL,
                clock_high_watermark INTEGER NOT NULL CHECK (clock_high_watermark >= 0)
            )"""
_CREATE_REPLAY_RESERVATIONS = """CREATE TABLE replay_reservations (
                auth_version TEXT NOT NULL,
                audience TEXT NOT NULL,
                signer_digest BLOB NOT NULL CHECK (length(signer_digest) = 32),
                nonce BLOB NOT NULL CHECK (length(nonce) = 16),
                expires_at INTEGER NOT NULL,
                retain_until INTEGER NOT NULL,
                reserved_at INTEGER NOT NULL,
                PRIMARY KEY (auth_version, audience, signer_digest, nonce)
            ) WITHOUT ROWID"""
_CREATE_REPLAY_RETENTION_INDEX = """CREATE INDEX replay_reservations_retention
                ON replay_reservations(retain_until)"""
_CREATE_SIGNER_REVOCATIONS = """CREATE TABLE signer_revocations (
                signer_digest BLOB PRIMARY KEY CHECK (length(signer_digest) = 32),
                effective_at INTEGER NOT NULL,
                recorded_at INTEGER NOT NULL
            ) WITHOUT ROWID"""
_SCHEMA_STATEMENTS = (
    _CREATE_REPLAY_METADATA,
    _CREATE_REPLAY_RESERVATIONS,
    _CREATE_REPLAY_RETENTION_INDEX,
    _CREATE_SIGNER_REVOCATIONS,
)
_EXPECTED_SCHEMA_OBJECTS = (
    (
        "index",
        "replay_reservations_retention",
        "replay_reservations",
        _CREATE_REPLAY_RETENTION_INDEX,
    ),
    ("table", "replay_metadata", "replay_metadata", _CREATE_REPLAY_METADATA),
    (
        "table",
        "replay_reservations",
        "replay_reservations",
        _CREATE_REPLAY_RESERVATIONS,
    ),
    (
        "table",
        "signer_revocations",
        "signer_revocations",
        _CREATE_SIGNER_REVOCATIONS,
    ),
)
_EXPECTED_TABLE_XINFO = {
    "replay_metadata": (
        (0, "singleton", "INTEGER", 0, None, 1, 0),
        (1, "schema_version", "INTEGER", 1, None, 0, 0),
        (2, "backend_identity", "TEXT", 1, None, 0, 0),
        (3, "clock_high_watermark", "INTEGER", 1, None, 0, 0),
    ),
    "replay_reservations": (
        (0, "auth_version", "TEXT", 1, None, 1, 0),
        (1, "audience", "TEXT", 1, None, 2, 0),
        (2, "signer_digest", "BLOB", 1, None, 3, 0),
        (3, "nonce", "BLOB", 1, None, 4, 0),
        (4, "expires_at", "INTEGER", 1, None, 0, 0),
        (5, "retain_until", "INTEGER", 1, None, 0, 0),
        (6, "reserved_at", "INTEGER", 1, None, 0, 0),
    ),
    "signer_revocations": (
        (0, "signer_digest", "BLOB", 1, None, 1, 0),
        (1, "effective_at", "INTEGER", 1, None, 0, 0),
        (2, "recorded_at", "INTEGER", 1, None, 0, 0),
    ),
}
_EXPECTED_TABLE_LIST = {
    "replay_metadata": ("table", 4, 0, 0),
    "replay_reservations": ("table", 7, 1, 0),
    "signer_revocations": ("table", 3, 1, 0),
}
_EXPECTED_INDEX_LIST = {
    "replay_metadata": (),
    "replay_reservations": (
        (0, "replay_reservations_retention", 0, "c", 0),
        (1, "sqlite_autoindex_replay_reservations_1", 1, "pk", 0),
    ),
    "signer_revocations": (
        (0, "sqlite_autoindex_signer_revocations_1", 1, "pk", 0),
    ),
}
_EXPECTED_INDEX_XINFO = {
    "replay_reservations_retention": (
        (0, 5, "retain_until", 0, "BINARY", 1),
        (1, 0, "auth_version", 0, "BINARY", 0),
        (2, 1, "audience", 0, "BINARY", 0),
        (3, 2, "signer_digest", 0, "BINARY", 0),
        (4, 3, "nonce", 0, "BINARY", 0),
    ),
    "sqlite_autoindex_replay_reservations_1": (
        (0, 0, "auth_version", 0, "BINARY", 1),
        (1, 1, "audience", 0, "BINARY", 1),
        (2, 2, "signer_digest", 0, "BINARY", 1),
        (3, 3, "nonce", 0, "BINARY", 1),
        (4, 4, "expires_at", 0, "BINARY", 0),
        (5, 5, "retain_until", 0, "BINARY", 0),
        (6, 6, "reserved_at", 0, "BINARY", 0),
    ),
    "sqlite_autoindex_signer_revocations_1": (
        (0, 0, "signer_digest", 0, "BINARY", 1),
        (1, 1, "effective_at", 0, "BINARY", 0),
        (2, 2, "recorded_at", 0, "BINARY", 0),
    ),
}


class ReplayStorageInitializationError(RuntimeError):
    """Sanitized durable-store initialization/configuration failure."""


class RevocationOutcome(str, Enum):
    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    STORAGE_FAILURE = "storage_failure"


class CleanupOutcome(str, Enum):
    COMPLETED = "completed"
    STORAGE_FAILURE = "storage_failure"


@dataclass(frozen=True)
class CleanupResult:
    outcome: CleanupOutcome
    deleted: int = 0


@dataclass(frozen=True)
class RevocationIdentity:
    """Non-secret digest of the exact canonical signer/key identity."""

    signer_digest: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.signer_digest, bytes) or len(self.signer_digest) != 32:
            raise ValueError("revocation signer digest must be 32 bytes")


class DurableReplayStore(ReplayStore, Protocol):
    def revoke_signer(
        self,
        identity: RevocationIdentity,
        *,
        effective_at: int,
        now: int,
    ) -> RevocationOutcome: ...

    def cleanup(self, *, now: int) -> CleanupResult: ...


@dataclass(frozen=True)
class SQLiteReplayConfiguration:
    database_path: str
    lock_timeout_seconds: float = REPLAY_LOCK_TIMEOUT_SECONDS
    cleanup_batch_size: int = REPLAY_CLEANUP_BATCH_SIZE
    retention_safety_margin_seconds: int = (
        REPLAY_RETENTION_SAFETY_MARGIN_SECONDS
    )
    clock_rollback_tolerance_seconds: int = (
        REPLAY_CLOCK_ROLLBACK_TOLERANCE_SECONDS
    )

    def __post_init__(self) -> None:
        if not isinstance(self.database_path, str) or not self.database_path:
            raise ReplayStorageInitializationError(
                "gateway replay storage configuration is invalid"
            )
        if type(self.lock_timeout_seconds) not in {int, float} or not (
            0.01 <= float(self.lock_timeout_seconds) <= 5.0
        ):
            raise ReplayStorageInitializationError(
                "gateway replay storage lock timeout is invalid"
            )
        if type(self.cleanup_batch_size) is not int or not (
            1 <= self.cleanup_batch_size <= 1_000
        ):
            raise ReplayStorageInitializationError(
                "gateway replay cleanup batch is invalid"
            )
        if type(self.retention_safety_margin_seconds) is not int or not (
            1 <= self.retention_safety_margin_seconds <= 3_600
        ):
            raise ReplayStorageInitializationError(
                "gateway replay retention margin is invalid"
            )
        if type(self.clock_rollback_tolerance_seconds) is not int or not (
            0 <= self.clock_rollback_tolerance_seconds <= 3_600
        ):
            raise ReplayStorageInitializationError(
                "gateway replay clock tolerance is invalid"
            )


class SQLiteDurableReplayStore(ImmutableRuntimeConfiguration):
    """Atomic host-local replay/revocation storage shared by worker processes."""

    _immutable_runtime_fields = frozenset(
        {"_configuration", "_database_path", "_backend_identity", "_policy", "_clock"}
    )

    def __init__(
        self,
        configuration: SQLiteReplayConfiguration,
        policy: RuntimePolicy,
        *,
        clock: Clock | None = None,
    ) -> None:
        observed = load_runtime_policy()
        if policy != observed:
            raise RuntimeConfigurationError(
                "durable gateway replay policy does not match the effective "
                "runtime environment"
            )
        database_path = _validate_configured_path(configuration.database_path)
        backend_identity = hashlib.sha256(
            b"VAMS:GATEWAY:REPLAY-SQLITE:v1\x00"
            + os.fsencode(str(database_path))
        ).hexdigest()
        self._configuration = configuration
        self._database_path = database_path
        self._backend_identity = backend_identity
        self._policy = observed
        self._clock = clock or SystemClock()
        self._initialize()
        self._freeze_runtime_configuration()

    @property
    def configuration(self) -> SQLiteReplayConfiguration:
        return self._configuration

    @property
    def backend_identity(self) -> str:
        return self._backend_identity

    @property
    def deployment_boundary(self) -> str:
        return "single-host-shared-filesystem"

    def reserve_and_consume(
        self,
        namespace: ReplayNamespace,
        *,
        expires_at: int,
        now: int,
    ) -> ReplayOutcome:
        if not _valid_timestamp(expires_at) or not _valid_timestamp(now):
            return ReplayOutcome.STORAGE_FAILURE
        try:
            with closing(self._connect_existing()) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                self._validate_schema(connection)
                transaction_now = self._check_clock(connection, max(now, self._clock_now()))
                if expires_at <= transaction_now:
                    connection.rollback()
                    return ReplayOutcome.STORAGE_FAILURE
                self._cleanup_in_transaction(connection, transaction_now)
                if self._revocation_effective(
                    connection, namespace.signer_digest, transaction_now
                ):
                    self._advance_clock(connection, transaction_now)
                    connection.commit()
                    return ReplayOutcome.REVOKED
                retain_until = min(
                    _MAX_SQLITE_INTEGER,
                    expires_at
                    + AUTH_MAX_FUTURE_SKEW_SECONDS
                    + self._configuration.retention_safety_margin_seconds,
                )
                try:
                    connection.execute(
                        """
                        INSERT INTO replay_reservations (
                            auth_version, audience, signer_digest, nonce,
                            expires_at, retain_until, reserved_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            namespace.auth_version,
                            namespace.audience,
                            namespace.signer_digest,
                            namespace.nonce,
                            expires_at,
                            retain_until,
                            transaction_now,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    if not self._is_exact_duplicate(connection, namespace, exc):
                        raise
                    self._advance_clock(connection, transaction_now)
                    connection.commit()
                    return ReplayOutcome.DUPLICATE

                commit_now = self._check_clock(connection, max(transaction_now, self._clock_now()))
                revoked_at_commit = self._revocation_effective(
                    connection, namespace.signer_digest, commit_now
                )
                if expires_at <= commit_now or revoked_at_commit:
                    connection.rollback()
                    return (
                        ReplayOutcome.REVOKED
                        if revoked_at_commit
                        else ReplayOutcome.STORAGE_FAILURE
                    )
                self._advance_clock(connection, commit_now)
                connection.commit()
                return ReplayOutcome.ACCEPTED
        except (OSError, sqlite3.Error, ValueError):
            return ReplayOutcome.STORAGE_FAILURE

    def revoke_signer(
        self,
        identity: RevocationIdentity,
        *,
        effective_at: int,
        now: int,
    ) -> RevocationOutcome:
        if not _valid_timestamp(effective_at) or not _valid_timestamp(now):
            return RevocationOutcome.STORAGE_FAILURE
        try:
            with closing(self._connect_existing()) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                self._validate_schema(connection)
                transaction_now = self._check_clock(connection, max(now, self._clock_now()))
                row = connection.execute(
                    "SELECT effective_at FROM signer_revocations "
                    "WHERE signer_digest = ?",
                    (identity.signer_digest,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO signer_revocations "
                        "(signer_digest, effective_at, recorded_at) VALUES (?, ?, ?)",
                        (identity.signer_digest, effective_at, transaction_now),
                    )
                    outcome = RevocationOutcome.APPLIED
                elif effective_at < int(row[0]):
                    connection.execute(
                        "UPDATE signer_revocations SET effective_at = ?, recorded_at = ? "
                        "WHERE signer_digest = ?",
                        (effective_at, transaction_now, identity.signer_digest),
                    )
                    outcome = RevocationOutcome.APPLIED
                else:
                    outcome = RevocationOutcome.ALREADY_APPLIED
                commit_now = self._check_clock(connection, max(transaction_now, self._clock_now()))
                self._advance_clock(connection, commit_now)
                connection.commit()
                return outcome
        except (OSError, sqlite3.Error, ValueError):
            return RevocationOutcome.STORAGE_FAILURE

    def cleanup(self, *, now: int) -> CleanupResult:
        if not _valid_timestamp(now):
            return CleanupResult(CleanupOutcome.STORAGE_FAILURE)
        try:
            with closing(self._connect_existing()) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                self._validate_schema(connection)
                transaction_now = self._check_clock(connection, max(now, self._clock_now()))
                deleted = self._cleanup_in_transaction(connection, transaction_now)
                self._advance_clock(connection, transaction_now)
                connection.commit()
                return CleanupResult(CleanupOutcome.COMPLETED, deleted)
        except (OSError, sqlite3.Error, ValueError):
            return CleanupResult(CleanupOutcome.STORAGE_FAILURE)

    def _initialize(self) -> None:
        try:
            _secure_create_or_validate_file(self._database_path)
            with closing(self._connect_existing(initializing=True)) as connection, connection:
                journal = connection.execute("PRAGMA journal_mode=WAL").fetchone()
                if journal is None or str(journal[0]).lower() != "wal":
                    raise sqlite3.OperationalError("WAL mode unavailable")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("BEGIN IMMEDIATE")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
                if version == 0:
                    if tables:
                        raise sqlite3.DatabaseError("ambiguous unversioned schema")
                    self._create_schema(connection)
                elif version != REPLAY_SCHEMA_VERSION:
                    raise sqlite3.DatabaseError("incompatible replay schema")
                self._validate_schema(connection)
                integrity = connection.execute("PRAGMA integrity_check(1)").fetchone()
                if integrity is None or integrity[0] != "ok":
                    raise sqlite3.DatabaseError("replay database integrity failure")
                connection.commit()
        except (OSError, sqlite3.Error, ValueError):
            raise ReplayStorageInitializationError(
                "gateway replay storage initialization failed"
            ) from None

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO replay_metadata "
            "(singleton, schema_version, backend_identity, clock_high_watermark) "
            "VALUES (1, ?, ?, 0)",
            (REPLAY_SCHEMA_VERSION, self._backend_identity),
        )
        connection.execute(f"PRAGMA user_version={REPLAY_SCHEMA_VERSION}")

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != REPLAY_SCHEMA_VERSION:
            raise sqlite3.DatabaseError("incompatible replay schema")

        schema_objects = tuple(
            connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_schema "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            )
        )
        if schema_objects != _EXPECTED_SCHEMA_OBJECTS:
            raise sqlite3.DatabaseError("incompatible replay schema")

        tables = {
            str(row[1]): (str(row[2]), int(row[3]), int(row[4]), int(row[5]))
            for row in connection.execute("PRAGMA table_list")
            if str(row[0]) == "main" and not str(row[1]).startswith("sqlite_")
        }
        if tables != _EXPECTED_TABLE_LIST:
            raise sqlite3.DatabaseError("incompatible replay schema")

        for table, expected in _EXPECTED_TABLE_XINFO.items():
            actual = tuple(connection.execute(f"PRAGMA table_xinfo({table})"))
            if actual != expected:
                raise sqlite3.DatabaseError("incompatible replay schema")
            if tuple(connection.execute(f"PRAGMA foreign_key_list({table})")):
                raise sqlite3.DatabaseError("incompatible replay schema")
            indexes = tuple(connection.execute(f"PRAGMA index_list({table})"))
            if indexes != _EXPECTED_INDEX_LIST[table]:
                raise sqlite3.DatabaseError("incompatible replay schema")

        for index, expected in _EXPECTED_INDEX_XINFO.items():
            actual = tuple(connection.execute(f"PRAGMA index_xinfo({index})"))
            if actual != expected:
                raise sqlite3.DatabaseError("incompatible replay schema")

        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
        if foreign_keys != (1,):
            raise sqlite3.DatabaseError("incompatible replay schema")

        row = connection.execute(
            "SELECT schema_version, backend_identity FROM replay_metadata "
            "WHERE singleton = 1"
        ).fetchone()
        if row != (REPLAY_SCHEMA_VERSION, self._backend_identity):
            raise sqlite3.DatabaseError("replay backend identity mismatch")
        count = connection.execute(
            "SELECT COUNT(*) FROM replay_metadata"
        ).fetchone()
        if count is None or int(count[0]) != 1:
            raise sqlite3.DatabaseError("invalid replay metadata cardinality")
        self._probe_schema_constraints(connection)

    def _probe_schema_constraints(self, connection: sqlite3.Connection) -> None:
        signer = hashlib.sha256(
            b"VAMS:GATEWAY:REPLAY-SCHEMA-PROBE:v1\x00"
            + secrets.token_bytes(32)
        ).digest()
        nonce = secrets.token_bytes(16)
        audience = "vams-schema-probe"
        connection.execute("SAVEPOINT replay_schema_probe")
        try:
            replay_insert = (
                "INSERT INTO replay_reservations "
                "(auth_version, audience, signer_digest, nonce, expires_at, "
                "retain_until, reserved_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
            )
            replay_values = ("v2", audience, signer, nonce, 2, 3, 1)
            connection.execute(replay_insert, replay_values)
            self._expect_constraint(
                connection,
                replay_insert,
                replay_values,
                sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY,
            )
            self._expect_constraint(
                connection,
                replay_insert,
                ("v2", audience, b"x", secrets.token_bytes(16), 2, 3, 1),
                sqlite3.SQLITE_CONSTRAINT_CHECK,
            )
            self._expect_constraint(
                connection,
                replay_insert,
                ("v2", audience, signer, b"x", 2, 3, 1),
                sqlite3.SQLITE_CONSTRAINT_CHECK,
            )
            self._expect_constraint(
                connection,
                replay_insert,
                ("v2", audience, signer, secrets.token_bytes(16), None, 3, 1),
                sqlite3.SQLITE_CONSTRAINT_NOTNULL,
            )

            revocation_insert = (
                "INSERT INTO signer_revocations "
                "(signer_digest, effective_at, recorded_at) VALUES (?, ?, ?)"
            )
            connection.execute(revocation_insert, (signer, 1, 1))
            self._expect_constraint(
                connection,
                revocation_insert,
                (signer, 1, 1),
                sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY,
            )
            self._expect_constraint(
                connection,
                revocation_insert,
                (b"x", 1, 1),
                sqlite3.SQLITE_CONSTRAINT_CHECK,
            )
            self._expect_constraint(
                connection,
                "UPDATE replay_metadata SET schema_version = 2 "
                "WHERE singleton = 1",
                (),
                sqlite3.SQLITE_CONSTRAINT_CHECK,
            )
            self._expect_constraint(
                connection,
                "UPDATE replay_metadata SET clock_high_watermark = -1 "
                "WHERE singleton = 1",
                (),
                sqlite3.SQLITE_CONSTRAINT_CHECK,
            )
            self._expect_constraint(
                connection,
                "INSERT INTO replay_metadata "
                "(singleton, schema_version, backend_identity, "
                "clock_high_watermark) VALUES (2, 1, ?, 0)",
                (self._backend_identity,),
                sqlite3.SQLITE_CONSTRAINT_CHECK,
            )
        finally:
            connection.execute("ROLLBACK TO replay_schema_probe")
            connection.execute("RELEASE replay_schema_probe")

    @staticmethod
    def _expect_constraint(
        connection: sqlite3.Connection,
        statement: str,
        parameters: tuple[object, ...],
        expected_code: int,
    ) -> None:
        try:
            connection.execute(statement, parameters)
        except sqlite3.IntegrityError as exc:
            if getattr(exc, "sqlite_errorcode", None) == expected_code:
                return
            raise sqlite3.DatabaseError("incompatible replay schema") from None
        raise sqlite3.DatabaseError("incompatible replay schema")

    @staticmethod
    def _is_exact_duplicate(
        connection: sqlite3.Connection,
        namespace: ReplayNamespace,
        error: sqlite3.IntegrityError,
    ) -> bool:
        if (
            getattr(error, "sqlite_errorcode", None)
            != sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY
        ):
            return False
        row = connection.execute(
            "SELECT 1 FROM replay_reservations WHERE auth_version = ? "
            "AND audience = ? AND signer_digest = ? AND nonce = ?",
            (
                namespace.auth_version,
                namespace.audience,
                namespace.signer_digest,
                namespace.nonce,
            ),
        ).fetchone()
        return row == (1,)

    def _connect_existing(
        self, *, initializing: bool = False
    ) -> sqlite3.Connection:
        if not initializing:
            _validate_existing_file(self._database_path)
        uri = self._database_path.as_uri() + "?mode=rw"
        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=float(self._configuration.lock_timeout_seconds),
            isolation_level=None,
        )
        try:
            connection.execute(
                f"PRAGMA busy_timeout={int(self._configuration.lock_timeout_seconds * 1000)}"
            )
            connection.execute("PRAGMA foreign_keys=ON")
        except BaseException:
            connection.close()
            raise
        return connection

    def _check_clock(self, connection: sqlite3.Connection, now: int) -> int:
        """Validate rollback tolerance and retain the durable monotonic time.

        Callers hold BEGIN IMMEDIATE through the associated decision/commit.
        Tolerated wall-clock skew must not resurrect a revoked signer or extend
        an expired request. Missing or malformed persisted time fails closed.
        """
        row = connection.execute(
            "SELECT clock_high_watermark FROM replay_metadata WHERE singleton = 1"
        ).fetchone()
        if row is None or len(row) != 1 or not _valid_timestamp(row[0]):
            raise sqlite3.DatabaseError("replay metadata unavailable")
        high = row[0]
        if now + self._configuration.clock_rollback_tolerance_seconds < high:
            raise sqlite3.DatabaseError("clock rollback exceeds tolerance")
        return max(now, high)

    def _advance_clock(self, connection: sqlite3.Connection, now: int) -> None:
        connection.execute(
            "UPDATE replay_metadata SET clock_high_watermark = "
            "MAX(clock_high_watermark, ?) WHERE singleton = 1",
            (now,),
        )

    def _cleanup_in_transaction(
        self, connection: sqlite3.Connection, now: int
    ) -> int:
        cursor = connection.execute(
            """
            DELETE FROM replay_reservations
            WHERE (auth_version, audience, signer_digest, nonce) IN (
                SELECT auth_version, audience, signer_digest, nonce
                FROM replay_reservations
                WHERE retain_until <= ?
                ORDER BY retain_until, auth_version, audience
                LIMIT ?
            )
            """,
            (now, self._configuration.cleanup_batch_size),
        )
        return max(0, int(cursor.rowcount))

    @staticmethod
    def _revocation_effective(
        connection: sqlite3.Connection, signer_digest: bytes, now: int
    ) -> bool:
        row = connection.execute(
            "SELECT effective_at FROM signer_revocations WHERE signer_digest = ?",
            (signer_digest,),
        ).fetchone()
        return row is not None and int(row[0]) <= now

    def _clock_now(self) -> int:
        value = self._clock.now()
        if not _valid_timestamp(value):
            raise ValueError("invalid storage clock")
        return value


def build_gateway_replay_store(
    policy: RuntimePolicy,
    *,
    clock: Clock | None = None,
) -> ReplayStore:
    """Build the one allowed store for the effective runtime environment."""

    observed = load_runtime_policy()
    if policy != observed:
        raise RuntimeConfigurationError(
            "gateway replay policy does not match the effective runtime environment"
        )
    configured_path = os.environ.get(REPLAY_DATABASE_VARIABLE)
    if configured_path is not None and (
        not configured_path or configured_path != configured_path.strip()
    ):
        raise ReplayStorageInitializationError(
            "gateway replay database configuration is malformed"
        )
    if observed.is_live and configured_path is None:
        raise ReplayStorageInitializationError(
            "durable gateway replay database is required in live modes"
        )
    if configured_path is None:
        return ProcessLocalReplayStore(observed)
    configuration = SQLiteReplayConfiguration(database_path=configured_path)
    return SQLiteDurableReplayStore(configuration, observed, clock=clock)


def signer_identity_digest(signer: str) -> bytes:
    """Derive the non-secret durable identity used by M2.1 reservations."""

    if not isinstance(signer, str) or not signer:
        raise ValueError("signer identity is required")
    return hashlib.sha256(signer.encode("ascii", "strict")).digest()


def _valid_timestamp(value: object) -> bool:
    return type(value) is int and 0 <= value <= _MAX_SQLITE_INTEGER


def _validate_configured_path(raw_path: str) -> Path:
    if "\x00" in raw_path or raw_path != raw_path.strip() or raw_path.startswith("file:"):
        raise ReplayStorageInitializationError(
            "gateway replay database path is unsafe"
        )
    path = Path(raw_path)
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ReplayStorageInitializationError(
            "gateway replay database path is unsafe"
        )
    normalized = Path(os.path.abspath(os.fspath(path)))
    if path != normalized or path.suffix != ".sqlite3":
        raise ReplayStorageInitializationError(
            "gateway replay database path is unsafe"
        )
    parent = path.parent
    if not parent.exists() or not parent.is_dir():
        raise ReplayStorageInitializationError(
            "gateway replay database parent is unavailable"
        )
    _reject_symlink_components(parent)
    if os.name == "posix":
        parent_stat = parent.stat()
        if parent_stat.st_uid != os.geteuid() or parent_stat.st_mode & 0o022:
            raise ReplayStorageInitializationError(
                "gateway replay database parent permissions are unsafe"
            )
    return path


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:] if path.anchor else path.parts:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                raise ReplayStorageInitializationError(
                    "gateway replay database path contains a symlink"
                )
        except FileNotFoundError:
            raise ReplayStorageInitializationError(
                "gateway replay database parent is unavailable"
            ) from None


def _secure_create_or_validate_file(path: Path) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except FileExistsError:
        _validate_existing_file(path)
    else:
        os.close(descriptor)
        if os.name == "posix":
            os.chmod(path, 0o600)
        _validate_existing_file(path)


def _validate_existing_file(path: Path) -> None:
    try:
        file_stat = path.lstat()
    except FileNotFoundError:
        raise OSError("replay database is unavailable") from None
    if not stat.S_ISREG(file_stat.st_mode) or stat.S_ISLNK(file_stat.st_mode):
        raise OSError("replay database is unsafe")
    if file_stat.st_nlink != 1:
        raise OSError("replay database has an unsafe alias")
    if os.name == "posix":
        if file_stat.st_uid != os.geteuid() or stat.S_IMODE(file_stat.st_mode) != 0o600:
            raise OSError("replay database permissions are unsafe")
