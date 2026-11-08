"""M2.4a fail-closed SQLite schema-integrity regressions."""

from __future__ import annotations

import hashlib
import http.client
import os
import socket
import sqlite3
import stat
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import uvicorn
from fastapi.testclient import TestClient

os.environ.setdefault("VAMS_ENV", "test")
os.environ.setdefault("GATEWAY_ADMIN_PASSWORD", "m2-4a-test-password")

from gateway import server
from gateway.replay_store import (
    ReplayStorageInitializationError,
    RevocationIdentity,
    RevocationOutcome,
    SQLiteDurableReplayStore,
    SQLiteReplayConfiguration,
    signer_identity_digest,
)
from gateway.request_auth import AUTH_VERSION, ReplayNamespace, ReplayOutcome
from neuron.runtime_safety import REGISTERED_MOCK_VARIABLES, load_runtime_policy
from neuron.tests.m2_gateway_helpers import (
    AUDIENCE,
    SIGNER,
    compact_json,
    signed_headers,
)


NOW = 2_000_000_000
SIGNER_DIGEST = signer_identity_digest(SIGNER)
MALFORMED_SCHEMAS = (
    "missing_composite_primary_key",
    "subset_unique_constraint",
    "wrong_composite_key_order",
    "wrong_primary_key_positions",
    "rowid_replay_table",
    "nullable_replay_column",
    "wrong_replay_column_type",
    "replay_column_default",
    "replay_column_collation",
    "altered_replay_check",
    "missing_retention_index",
    "altered_retention_index",
    "unexpected_unique_index",
    "unexpected_partial_index",
    "unexpected_expression_index",
    "insert_ignore_trigger",
    "insert_delete_trigger",
    "insert_rewrite_trigger",
    "unexpected_view",
    "unexpected_table",
    "unexpected_virtual_table",
    "rowid_revocation_table",
    "missing_revocation_primary_key",
    "altered_revocation_check",
)


_METADATA_SQL = """CREATE TABLE replay_metadata (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                schema_version INTEGER NOT NULL CHECK (schema_version = 1),
                backend_identity TEXT NOT NULL,
                clock_high_watermark INTEGER NOT NULL CHECK (clock_high_watermark >= 0)
            )"""
_REPLAY_SQL = """CREATE TABLE replay_reservations (
                auth_version TEXT NOT NULL,
                audience TEXT NOT NULL,
                signer_digest BLOB NOT NULL CHECK (length(signer_digest) = 32),
                nonce BLOB NOT NULL CHECK (length(nonce) = 16),
                expires_at INTEGER NOT NULL,
                retain_until INTEGER NOT NULL,
                reserved_at INTEGER NOT NULL,
                PRIMARY KEY (auth_version, audience, signer_digest, nonce)
            ) WITHOUT ROWID"""
_RETENTION_SQL = """CREATE INDEX replay_reservations_retention
                ON replay_reservations(retain_until)"""
_REVOCATION_SQL = """CREATE TABLE signer_revocations (
                signer_digest BLOB PRIMARY KEY CHECK (length(signer_digest) = 32),
                effective_at INTEGER NOT NULL,
                recorded_at INTEGER NOT NULL
            ) WITHOUT ROWID"""


class _SyntheticInstance:
    blueprint = SimpleNamespace(required_service_blocks=[])
    allocation = SimpleNamespace(total_hourly_cost=1.0)

    @staticmethod
    def to_dict() -> dict[str, str]:
        return {"instance_id": "synthetic-m2-4a"}


class _RecordingComposer:
    def __init__(self) -> None:
        self.calls = 0

    def provision_blueprint(self, _name: str):
        self.calls += 1
        return _SyntheticInstance()

    # Stand-in protected handler; the real Composer simulation is demo-only
    # (covered by test_m2_3_gateway_routes.test_local_mode_composer_simulation_stays_unavailable).
    def assert_simulation_available(self) -> None:
        return None


class _LoopbackServer:
    def __init__(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(32)
        self.port = self.socket.getsockname()[1]
        self.server = uvicorn.Server(
            uvicorn.Config(server.app, log_level="error", lifespan="on")
        )
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.socket]},
            name="m2-4a-loopback-server",
        )

    def start(self) -> None:
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and self.thread.is_alive():
            if time.monotonic() >= deadline:
                pytest.fail("loopback gateway startup exceeded bounded timeout")
            threading.Event().wait(0.01)
        if not self.server.started:
            pytest.fail("loopback gateway failed during startup")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(10)
        self.socket.close()
        if self.thread.is_alive():
            pytest.fail("loopback gateway shutdown exceeded bounded timeout")


@pytest.fixture
def configured_gateway(monkeypatch, tmp_path):
    database = tmp_path / "m2-4a-replay.sqlite3"
    monkeypatch.setenv("VAMS_ENV", "local")
    monkeypatch.setenv("VAMS_MOCK_MODE", "false")
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "m2-4a-test-password")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("GATEWAY_AUTH_REPLAY_DB", str(database))
    monkeypatch.delenv("GATEWAY_ALLOWED_ORIGINS", raising=False)
    for variable in REGISTERED_MOCK_VARIABLES:
        if variable != "VAMS_MOCK_MODE":
            monkeypatch.delenv(variable, raising=False)
    composer = _RecordingComposer()
    monkeypatch.setattr(server, "composer", composer)
    monkeypatch.setattr(server, "COMPOSER_AVAILABLE", True)
    # Startup would otherwise rebind the real (demo-only) Composer over the recorder.
    monkeypatch.setattr(server, "_bind_resource_composer", lambda _policy: None)
    server.nodes.clear()
    yield database, composer
    server.nodes.clear()


def _backend_identity(path: Path) -> str:
    return hashlib.sha256(
        b"VAMS:GATEWAY:REPLAY-SQLITE:v1\x00" + os.fsencode(str(path.resolve()))
    ).hexdigest()


def _replay_sql(case: str | None) -> str:
    if case == "missing_composite_primary_key":
        return """CREATE TABLE replay_reservations (
                auth_version TEXT NOT NULL,
                audience TEXT NOT NULL,
                signer_digest BLOB NOT NULL CHECK (length(signer_digest) = 32),
                nonce BLOB NOT NULL CHECK (length(nonce) = 16),
                expires_at INTEGER NOT NULL,
                retain_until INTEGER NOT NULL,
                reserved_at INTEGER NOT NULL
            )"""
    if case == "subset_unique_constraint":
        return _replay_sql("missing_composite_primary_key").replace(
            "\n            )",
            ",\n                UNIQUE (auth_version, audience, nonce)\n            )",
        )
    if case == "wrong_composite_key_order":
        return _REPLAY_SQL.replace(
            "PRIMARY KEY (auth_version, audience, signer_digest, nonce)",
            "PRIMARY KEY (audience, auth_version, signer_digest, nonce)",
        )
    if case == "wrong_primary_key_positions":
        return _REPLAY_SQL.replace(
            "auth_version TEXT NOT NULL,",
            "auth_version TEXT PRIMARY KEY,",
        ).replace(
            "PRIMARY KEY (auth_version, audience, signer_digest, nonce)",
            "UNIQUE (auth_version, audience, signer_digest, nonce)",
        )
    if case == "rowid_replay_table":
        return _REPLAY_SQL.removesuffix(" WITHOUT ROWID")
    if case == "nullable_replay_column":
        return _REPLAY_SQL.replace("audience TEXT NOT NULL,", "audience TEXT,")
    if case == "wrong_replay_column_type":
        return _REPLAY_SQL.replace(
            "audience TEXT NOT NULL,", "audience BLOB NOT NULL,"
        )
    if case == "replay_column_default":
        return _REPLAY_SQL.replace(
            "audience TEXT NOT NULL,", "audience TEXT NOT NULL DEFAULT 'probe',"
        )
    if case == "replay_column_collation":
        return _REPLAY_SQL.replace(
            "audience TEXT NOT NULL,", "audience TEXT NOT NULL COLLATE NOCASE,"
        )
    if case == "altered_replay_check":
        return _REPLAY_SQL.replace(
            "length(signer_digest) = 32", "length(signer_digest) > 0"
        )
    return _REPLAY_SQL


def _revocation_sql(case: str | None) -> str:
    if case == "rowid_revocation_table":
        return _REVOCATION_SQL.removesuffix(" WITHOUT ROWID")
    if case == "missing_revocation_primary_key":
        return _REVOCATION_SQL.replace(" PRIMARY KEY", "").removesuffix(
            " WITHOUT ROWID"
        )
    if case == "altered_revocation_check":
        return _REVOCATION_SQL.replace(
            "length(signer_digest) = 32", "length(signer_digest) > 0"
        )
    return _REVOCATION_SQL


def _install_extra_schema(connection: sqlite3.Connection, case: str | None) -> None:
    if case == "unexpected_unique_index":
        connection.execute(
            "CREATE UNIQUE INDEX unexpected_unique "
            "ON replay_reservations(audience, nonce)"
        )
    elif case == "unexpected_partial_index":
        connection.execute(
            "CREATE INDEX unexpected_partial ON replay_reservations(expires_at) "
            "WHERE expires_at > 0"
        )
    elif case == "unexpected_expression_index":
        connection.execute(
            "CREATE INDEX unexpected_expression "
            "ON replay_reservations(lower(audience))"
        )
    elif case == "insert_ignore_trigger":
        connection.execute(
            "CREATE TRIGGER unexpected_ignore BEFORE INSERT ON replay_reservations "
            "BEGIN SELECT RAISE(IGNORE); END"
        )
    elif case == "insert_delete_trigger":
        connection.execute(
            "CREATE TRIGGER unexpected_delete AFTER INSERT ON replay_reservations "
            "BEGIN DELETE FROM replay_reservations "
            "WHERE auth_version = NEW.auth_version AND audience = NEW.audience "
            "AND signer_digest = NEW.signer_digest AND nonce = NEW.nonce; END"
        )
    elif case == "insert_rewrite_trigger":
        connection.execute(
            "CREATE TRIGGER unexpected_rewrite AFTER INSERT ON replay_reservations "
            "BEGIN UPDATE replay_reservations SET expires_at = 0 "
            "WHERE auth_version = NEW.auth_version AND audience = NEW.audience "
            "AND signer_digest = NEW.signer_digest AND nonce = NEW.nonce; END"
        )
    elif case == "unexpected_view":
        connection.execute(
            "CREATE VIEW unexpected_view AS SELECT * FROM replay_reservations"
        )
    elif case == "unexpected_table":
        connection.execute("CREATE TABLE unexpected_table (value TEXT)")
    elif case == "unexpected_virtual_table":
        connection.execute(
            "CREATE VIRTUAL TABLE unexpected_virtual USING fts5(value)"
        )


def _create_independent_database(path: Path, case: str | None = None) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(_METADATA_SQL)
        connection.execute(_replay_sql(case))
        if case != "missing_retention_index":
            retention_sql = (
                _RETENTION_SQL.replace("retain_until", "expires_at")
                if case == "altered_retention_index"
                else _RETENTION_SQL
            )
            connection.execute(retention_sql)
        connection.execute(_revocation_sql(case))
        connection.execute(
            "INSERT INTO replay_metadata "
            "(singleton, schema_version, backend_identity, clock_high_watermark) "
            "VALUES (1, 1, ?, 0)",
            (_backend_identity(path),),
        )
        connection.execute("PRAGMA user_version=1")
        _install_extra_schema(connection, case)
        connection.commit()
    finally:
        connection.close()
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _mutate_initialized_database(path: Path, case: str) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        if case in {
            "missing_composite_primary_key",
            "subset_unique_constraint",
            "wrong_composite_key_order",
            "wrong_primary_key_positions",
            "rowid_replay_table",
            "nullable_replay_column",
            "wrong_replay_column_type",
            "replay_column_default",
            "replay_column_collation",
            "altered_replay_check",
        }:
            connection.execute("DROP TABLE replay_reservations")
            connection.execute(_replay_sql(case))
            connection.execute(_RETENTION_SQL)
        elif case in {
            "rowid_revocation_table",
            "missing_revocation_primary_key",
            "altered_revocation_check",
        }:
            connection.execute("DROP TABLE signer_revocations")
            connection.execute(_revocation_sql(case))
        elif case == "missing_retention_index":
            connection.execute("DROP INDEX replay_reservations_retention")
        elif case == "altered_retention_index":
            connection.execute("DROP INDEX replay_reservations_retention")
            connection.execute(_RETENTION_SQL.replace("retain_until", "expires_at"))
        else:
            _install_extra_schema(connection, case)
        connection.commit()
    finally:
        connection.close()


def _namespace(nonce: int = 1) -> ReplayNamespace:
    return ReplayNamespace(
        AUTH_VERSION,
        AUDIENCE,
        SIGNER_DIGEST,
        nonce.to_bytes(16, "big"),
    )


def _loopback_request(port: int, *, nonce: int) -> tuple[int, bytes]:
    body = compact_json({"blueprint_name": "ServiceBlock_OMS_v1"})
    headers = signed_headers("POST", "/compose", body=body, nonce=nonce)
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("POST", "/compose", body=body, headers=headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


@pytest.mark.parametrize("case", MALFORMED_SCHEMAS)
def test_each_malformed_schema_denies_startup_fail_closed(
    monkeypatch, tmp_path: Path, case: str
):
    path = tmp_path / f"{case}.sqlite3"
    _create_independent_database(path, case)
    monkeypatch.setenv("VAMS_ENV", "test")
    for variable in REGISTERED_MOCK_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    with pytest.raises(
        ReplayStorageInitializationError,
        match="gateway replay storage initialization failed",
    ):
        SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(str(path)), load_runtime_policy()
        )


@pytest.mark.parametrize("case", MALFORMED_SCHEMAS)
def test_each_post_startup_schema_mutation_denies_real_http_without_handler(
    configured_gateway, case: str
):
    database, composer = configured_gateway
    running = _LoopbackServer()
    running.start()
    try:
        _mutate_initialized_database(database, case)
        status, payload = _loopback_request(running.port, nonce=1)
    finally:
        running.stop()
    assert status == 503
    assert b"gateway_request_denied:storage_failure" in payload
    assert composer.calls == 0


def test_malformed_database_rejects_gateway_startup_before_owned_activity(
    configured_gateway,
):
    database, composer = configured_gateway
    _create_independent_database(database, "missing_composite_primary_key")
    with pytest.raises(ReplayStorageInitializationError):
        with TestClient(server.app):
            pass
    assert composer.calls == 0
    assert server.cleanup_task is None


def test_rejected_existing_schema_is_not_repaired_replaced_or_overwritten(
    monkeypatch, tmp_path: Path
):
    path = tmp_path / "unchanged-malformed.sqlite3"
    _create_independent_database(path, "missing_composite_primary_key")
    inode_before = path.stat().st_ino
    connection = sqlite3.connect(path)
    try:
        schema_before = tuple(
            connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_schema "
                "ORDER BY type, name"
            )
        )
    finally:
        connection.close()
    monkeypatch.setenv("VAMS_ENV", "test")
    for variable in REGISTERED_MOCK_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    with pytest.raises(ReplayStorageInitializationError):
        SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(str(path)), load_runtime_policy()
        )
    connection = sqlite3.connect(path)
    try:
        schema_after = tuple(
            connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_schema "
                "ORDER BY type, name"
            )
        )
    finally:
        connection.close()
    assert path.stat().st_ino == inode_before
    assert schema_after == schema_before


def test_original_missing_key_replay_exploit_now_denies_both_requests(
    configured_gateway,
):
    database, composer = configured_gateway
    running = _LoopbackServer()
    running.start()
    try:
        _mutate_initialized_database(database, "missing_composite_primary_key")
        first = _loopback_request(running.port, nonce=10)
        second = _loopback_request(running.port, nonce=10)
    finally:
        running.stop()
    assert first[0] == second[0] == 503
    assert b"storage_failure" in first[1]
    assert b"storage_failure" in second[1]
    assert composer.calls == 0


def test_valid_schema_exact_duplicate_executes_once_over_real_http(
    configured_gateway,
):
    _database, composer = configured_gateway
    running = _LoopbackServer()
    running.start()
    try:
        first = _loopback_request(running.port, nonce=11)
        replay = _loopback_request(running.port, nonce=11)
    finally:
        running.stop()
    assert first[0] == 200
    assert replay[0] == 401
    assert b"duplicate_nonce" in replay[1]
    assert composer.calls == 1


def test_post_initialization_mutation_denies_reservation_and_revocation(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("VAMS_ENV", "test")
    for variable in REGISTERED_MOCK_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    path = tmp_path / "post-init.sqlite3"
    store = SQLiteDurableReplayStore(
        SQLiteReplayConfiguration(str(path)), load_runtime_policy()
    )
    _mutate_initialized_database(path, "missing_retention_index")
    assert (
        store.reserve_and_consume(
            _namespace(), expires_at=NOW + 120, now=NOW
        )
        is ReplayOutcome.STORAGE_FAILURE
    )
    assert (
        store.revoke_signer(
            RevocationIdentity(SIGNER_DIGEST), effective_at=NOW, now=NOW
        )
        is RevocationOutcome.STORAGE_FAILURE
    )


def test_valid_fresh_schema_matches_independent_contract_and_is_deterministic(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("VAMS_ENV", "test")
    for variable in REGISTERED_MOCK_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    paths = [tmp_path / "first.sqlite3", tmp_path / "second.sqlite3"]
    for path in paths:
        SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(str(path)), load_runtime_policy()
        )
    schemas = []
    for path in paths:
        connection = sqlite3.connect(path)
        try:
            schemas.append(
                tuple(
                    connection.execute(
                        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
                        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                    )
                )
            )
            replay_xinfo = tuple(
                connection.execute("PRAGMA table_xinfo(replay_reservations)")
            )
            replay_table = next(
                row
                for row in connection.execute("PRAGMA table_list")
                if row[1] == "replay_reservations"
            )
            replay_indexes = tuple(
                connection.execute("PRAGMA index_list(replay_reservations)")
            )
        finally:
            connection.close()
        assert [row[5] for row in replay_xinfo[:4]] == [1, 2, 3, 4]
        assert [row[2] for row in replay_xinfo] == [
            "TEXT",
            "TEXT",
            "BLOB",
            "BLOB",
            "INTEGER",
            "INTEGER",
            "INTEGER",
        ]
        assert replay_table[4:] == (1, 0)
        assert replay_indexes == (
            (0, "replay_reservations_retention", 0, "c", 0),
            (1, "sqlite_autoindex_replay_reservations_1", 1, "pk", 0),
        )
    assert schemas[0] == schemas[1]


def test_valid_populated_database_preserves_replay_and_revocation_state(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("VAMS_ENV", "test")
    for variable in REGISTERED_MOCK_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    path = tmp_path / "populated.sqlite3"
    first = SQLiteDurableReplayStore(
        SQLiteReplayConfiguration(str(path)), load_runtime_policy()
    )
    assert (
        first.reserve_and_consume(
            _namespace(20), expires_at=NOW + 120, now=NOW
        )
        is ReplayOutcome.ACCEPTED
    )
    assert (
        first.revoke_signer(
            RevocationIdentity(hashlib.sha256(b"other-signer").digest()),
            effective_at=NOW,
            now=NOW,
        )
        is RevocationOutcome.APPLIED
    )
    restarted = SQLiteDurableReplayStore(
        SQLiteReplayConfiguration(str(path)), load_runtime_policy()
    )
    assert (
        restarted.reserve_and_consume(
            _namespace(20), expires_at=NOW + 120, now=NOW
        )
        is ReplayOutcome.DUPLICATE
    )
    assert (
        restarted.reserve_and_consume(
            ReplayNamespace(
                AUTH_VERSION,
                AUDIENCE,
                hashlib.sha256(b"other-signer").digest(),
                (21).to_bytes(16, "big"),
            ),
            expires_at=NOW + 120,
            now=NOW,
        )
        is ReplayOutcome.REVOKED
    )


def test_schema_failures_are_sanitized(
    configured_gateway, caplog
):
    database, composer = configured_gateway
    marker = "m2_4a_sensitive_schema_marker"
    running = _LoopbackServer()
    running.start()
    try:
        connection = sqlite3.connect(database)
        try:
            connection.execute(f"CREATE TABLE {marker} (value TEXT)")
            connection.commit()
        finally:
            connection.close()
        status, payload = _loopback_request(running.port, nonce=30)
    finally:
        running.stop()
    assert status == 503
    assert marker.encode() not in payload
    assert marker not in caplog.text
    assert SIGNER.encode() not in payload
    assert SIGNER not in caplog.text
    assert composer.calls == 0
