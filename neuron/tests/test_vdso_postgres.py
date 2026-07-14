import heapq
import threading
from concurrent.futures import ThreadPoolExecutor

from gateway.vdso_postgres import (
    PostgresNonceStore,
    PostgresReplayStore,
    validate_live_postgres_dsn,
)


class _FakeDatabase:
    def __init__(self):
        self.nonce_claims = {}
        self.replay_claims = {}
        self.replay_expirations = []
        self.now = 1_000
        self.lock = threading.Lock()

    def connect(self, _dsn):
        return _FakeConnection(self)


class _FakeConnection:
    def __init__(self, database):
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return _FakeCursor(self.database)

    def close(self):
        pass


class _FakeCursor:
    def __init__(self, database):
        self.database = database
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=()):
        normalized = " ".join(statement.split()).lower()
        if normalized.startswith("create table") or normalized.startswith(
            "create index"
        ):
            self.row = None
            return
        with self.database.lock:
            if "vams_vdso_nonce_claims" in normalized:
                key = parameters[:4]
                intent_id = parameters[4]
                existing = self.database.nonce_claims.get(key)
                if existing is None:
                    self.database.nonce_claims[key] = intent_id
                    self.row = (intent_id,)
                elif existing == intent_id:
                    self.row = (existing,)
                else:
                    self.row = None
                return
            if "vams_vdso_auth_replays" in normalized:
                replay_key, expires_at, cleanup_batch_size = parameters
                now = self.database.now
                expired = []
                skipped_current = []
                while (
                    self.database.replay_expirations
                    and len(expired) < cleanup_batch_size
                ):
                    expiry, key = self.database.replay_expirations[0]
                    if expiry > now:
                        break
                    heapq.heappop(self.database.replay_expirations)
                    if self.database.replay_claims.get(key) != expiry:
                        continue
                    if key == replay_key:
                        skipped_current.append((expiry, key))
                        continue
                    del self.database.replay_claims[key]
                    expired.append(key)
                for item in skipped_current:
                    heapq.heappush(self.database.replay_expirations, item)
                existing_expiry = self.database.replay_claims.get(replay_key)
                if expires_at > now and (
                    existing_expiry is None or existing_expiry <= now
                ):
                    self.database.replay_claims[replay_key] = expires_at
                    heapq.heappush(
                        self.database.replay_expirations, (expires_at, replay_key)
                    )
                    self.row = (replay_key,)
                else:
                    self.row = None
                return
        raise AssertionError(f"unexpected SQL: {normalized}")

    def fetchone(self):
        return self.row


def _bytes32(value):
    return value.to_bytes(32, "big")


def test_postgres_nonce_claim_survives_store_restart_and_rejects_alias():
    database = _FakeDatabase()
    first_process = PostgresNonceStore("postgresql://unit-test", connect=database.connect)
    restarted_process = PostgresNonceStore(
        "postgresql://unit-test", connect=database.connect
    )
    first_process.initialize()
    key = (_bytes32(1), _bytes32(2), 3, 4)

    assert first_process.check_and_record(key, _bytes32(5)) is True
    assert restarted_process.check_and_record(key, _bytes32(5)) is True
    assert restarted_process.check_and_record(key, _bytes32(6)) is False


def test_postgres_replay_claim_is_atomic_across_processes_and_expires():
    database = _FakeDatabase()
    stores = tuple(
        PostgresReplayStore("postgresql://unit-test", connect=database.connect)
        for _index in range(8)
    )
    stores[0].initialize()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(
                lambda store: store.check_and_record("same-request", 1_000, 1_301),
                stores,
            )
        )
    assert sum(results) == 1
    database.now = 1_301
    assert stores[-1].check_and_record("same-request", 1_301, 1_602) is True

    database.now = 2_000
    assert stores[-1].check_and_record("skewed-request", 1_000, 1_500) is False


def test_postgres_replay_store_does_not_evict_past_one_hundred_thousand_claims():
    database = _FakeDatabase()
    store = PostgresReplayStore("postgresql://unit-test", connect=database.connect)
    for index in range(100_001):
        assert store.check_and_record(f"request-{index}", 1_000, 2_000) is True
    assert store.check_and_record("request-0", 1_000, 2_000) is False
    assert len(database.replay_claims) == 100_001


def test_postgres_replay_store_prunes_expired_rows_in_bounded_batches():
    database = _FakeDatabase()
    store = PostgresReplayStore(
        "postgresql://unit-test",
        connect=database.connect,
        cleanup_batch_size=64,
    )
    for index in range(300):
        assert store.check_and_record(f"expired-{index:03d}", 1_000, 1_100) is True

    database.now = 1_100
    assert store.check_and_record("fresh-0", 1_100, 1_400) is True
    assert len(database.replay_claims) == 237
    for index in range(1, 6):
        assert store.check_and_record(f"fresh-{index}", 1_100, 1_400) is True

    assert set(database.replay_claims) == {f"fresh-{index}" for index in range(6)}


def test_postgres_replay_store_rejects_unbounded_cleanup_configuration():
    for batch_size in (0, 10_001, True):
        try:
            PostgresReplayStore(
                "postgresql://unit-test",
                connect=_FakeDatabase().connect,
                cleanup_batch_size=batch_size,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe cleanup batch size was accepted")


def test_live_postgres_dsn_requires_loopback_or_verified_tls():
    validate_live_postgres_dsn("postgresql://localhost/vams")
    validate_live_postgres_dsn(
        "postgresql://localhost/vams?sslmode=verify-full&sslrootcert=C%3A%5Cca.pem"
    )
    for dsn in (
        "postgresql://localhost/vams",
        "postgresql://localhost/vams?sslmode=require",
        "postgresql://localhost/vams?sslmode=verify-full",
    ):
        try:
            validate_live_postgres_dsn(dsn)
        except RuntimeError:
            pass
        else:
            raise AssertionError("insecure remote PostgreSQL DSN was accepted")
