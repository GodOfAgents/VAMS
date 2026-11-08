"""M2.2 durable replay/revocation tests using real SQLite and processes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import multiprocessing
import os
import queue
import sqlite3
import time
import stat
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Request
from fastapi.testclient import TestClient

from gateway.request_auth import (
    AUTH_ALGORITHM,
    AUTH_VERSION,
    ConfiguredAdminDIDResolver,
    GatewayAuthEnvelope,
    GatewayAuthenticationError,
    GatewayRequestAuthenticator,
    ProcessLocalReplayStore,
    ReplayNamespace,
    ReplayOutcome,
)
from gateway.replay_store import (
    REPLAY_DATABASE_VARIABLE,
    CleanupOutcome,
    ReplayStorageInitializationError,
    RevocationIdentity,
    RevocationOutcome,
    SQLiteDurableReplayStore,
    SQLiteReplayConfiguration,
    build_gateway_replay_store,
    signer_identity_digest,
)
from neuron.runtime_safety import (
    REGISTERED_MOCK_VARIABLES,
    LiveModeSafetyError,
    RuntimeConfigurationError,
    RuntimePolicy,
)
from neuron.secp256k1 import public_key_bytes, sign_message


NOW = 2_000_000_000
AUDIENCE = "vams.gateway.testnet"
PRIVATE_KEY = ec.derive_private_key(1, ec.SECP256K1())
PUBLIC_KEY = public_key_bytes(PRIVATE_KEY)
SIGNER = "did:key:" + PUBLIC_KEY.hex()
SIGNER_DIGEST = signer_identity_digest(SIGNER)


class MutableClock:
    def __init__(self, value: int = NOW):
        self.value = value

    def now(self) -> int:
        return self.value


def _set_process_mode(mode: str) -> None:
    os.environ["VAMS_ENV"] = mode
    for variable in REGISTERED_MOCK_VARIABLES:
        os.environ.pop(variable, None)


def _policy(mode: str) -> RuntimePolicy:
    return RuntimePolicy.from_environment({"VAMS_ENV": mode})


def _namespace(nonce: int = 1, *, version: str = AUTH_VERSION) -> ReplayNamespace:
    return ReplayNamespace(
        version,
        AUDIENCE,
        SIGNER_DIGEST,
        nonce.to_bytes(16, "big"),
    )


def _store(
    path: Path,
    clock: MutableClock,
    *,
    mode: str = "test",
    cleanup_batch_size: int = 256,
) -> SQLiteDurableReplayStore:
    _set_process_mode(mode)
    return SQLiteDurableReplayStore(
        SQLiteReplayConfiguration(
            str(path), cleanup_batch_size=cleanup_batch_size
        ),
        _policy(mode),
        clock=clock,
    )


def _reserve_worker(
    path: str,
    nonce: int,
    barrier,
    output,
    worker_index: int | None = None,
    diagnostics=None,
    *,
    mode: str = "testnet",
    ready=None,
) -> None:
    try:
        _set_process_mode(mode)
        clock = MutableClock()
        store = SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(path), _policy(mode), clock=clock
        )
        if ready is not None:
            ready.set()
        barrier.wait(timeout=10)
        outcome = store.reserve_and_consume(
            _namespace(nonce), expires_at=NOW + 120, now=NOW
        )
        result = ("ok", outcome.value)
        if diagnostics is None:
            output.put(result)
        else:
            output.put((worker_index, result))
            diagnostics.put(
                {
                    "worker_index": worker_index,
                    "outcome_category": outcome.value,
                    "exception_class": None,
                }
            )
    except BaseException as exc:  # only exception class crosses the process boundary
        result = ("error", type(exc).__name__)
        if diagnostics is None:
            output.put(result)
        else:
            output.put((worker_index, result))
            diagnostics.put(
                {
                    "worker_index": worker_index,
                    "outcome_category": "exception",
                    "exception_class": type(exc).__name__,
                }
            )
            raise RuntimeError("sanitized diagnostic worker failure") from None


def _revoke_worker(path: str, barrier, output) -> None:
    try:
        _set_process_mode("testnet")
        store = SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(path),
            _policy("testnet"),
            clock=MutableClock(),
        )
        barrier.wait(timeout=10)
        outcome = store.revoke_signer(
            RevocationIdentity(SIGNER_DIGEST), effective_at=NOW, now=NOW
        )
        output.put(("ok", outcome.value))
    except BaseException as exc:
        output.put(("error", type(exc).__name__))


def _prepared_reserve_worker(path: str, ready, start, output) -> None:
    try:
        _set_process_mode("testnet")
        store = SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(path),
            _policy("testnet"),
            clock=MutableClock(),
        )
        ready.set()
        if not start.wait(10):
            raise TimeoutError("reservation start signal was not received")
        outcome = store.reserve_and_consume(
            _namespace(), expires_at=NOW + 120, now=NOW
        )
        output.put(("ok", outcome.value))
    except BaseException as exc:
        output.put(("error", type(exc).__name__))


def _run_processes(
    target,
    arguments: list[tuple],
    count: int,
    *,
    defer_failures: bool = False,
):
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=target, args=args) for args in arguments]
    for process in processes:
        process.start()
    timed_out_indices = []
    for index, process in enumerate(processes):
        process.join(15)
        if process.is_alive():
            process.terminate()
            process.join(5)
            if not defer_failures:
                pytest.fail("durable replay worker exceeded bounded timeout")
            timed_out_indices.append(index)
            continue
        if not defer_failures:
            assert process.exitcode == 0
    if defer_failures:
        return processes, timed_out_indices
    return processes


@pytest.fixture(autouse=True)
def exact_runtime(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "test")
    monkeypatch.delenv(REPLAY_DATABASE_VARIABLE, raising=False)
    for variable in REGISTERED_MOCK_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_synchronized_same_request_race_has_exactly_one_success(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    _store(path, MutableClock())
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(10)
    output = context.Queue()
    diagnostics = context.Queue()
    args = [
        (str(path), 1, barrier, output, worker_index, diagnostics)
        for worker_index in range(10)
    ]
    processes, timed_out_indices = _run_processes(
        _reserve_worker, args, 10, defer_failures=True
    )

    collected_messages = []
    collector_exception_class = None
    collector_empty_read_count = 0
    for _ in range(10):
        try:
            collected_messages.append(output.get(timeout=3))
        except queue.Empty as exc:
            collector_exception_class = type(exc).__name__
            collector_empty_read_count += 1

    collected_by_worker = {}
    malformed_collector_messages = 0
    results = []
    for message in collected_messages:
        if (
            isinstance(message, tuple)
            and len(message) == 2
            and type(message[0]) is int
            and isinstance(message[1], tuple)
        ):
            worker_index, original_result = message
            results.append(original_result)
            if worker_index in collected_by_worker:
                malformed_collector_messages += 1
            else:
                collected_by_worker[worker_index] = original_result
        else:
            malformed_collector_messages += 1

    diagnostic_messages = []
    diagnostic_deadline = time.monotonic() + 3
    while len(diagnostic_messages) < 10:
        remaining = diagnostic_deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            diagnostic_messages.append(diagnostics.get(timeout=remaining))
        except queue.Empty:
            break

    diagnostics_by_worker = {}
    duplicate_diagnostic_indices = []
    malformed_diagnostic_records = 0
    for record in diagnostic_messages:
        if (
            not isinstance(record, dict)
            or type(record.get("worker_index")) is not int
            or not isinstance(record.get("outcome_category"), str)
            or (
                record.get("exception_class") is not None
                and not isinstance(record.get("exception_class"), str)
            )
        ):
            malformed_diagnostic_records += 1
            continue
        worker_index = record["worker_index"]
        if worker_index in diagnostics_by_worker:
            duplicate_diagnostic_indices.append(worker_index)
        else:
            diagnostics_by_worker[worker_index] = record

    timed_out = set(timed_out_indices)
    worker_records = []
    for worker_index, process in enumerate(processes):
        diagnostic = diagnostics_by_worker.get(worker_index)
        outcome_category = (
            "process_timeout"
            if worker_index in timed_out
            else diagnostic["outcome_category"]
            if diagnostic is not None
            else "missing_worker_record"
        )
        worker_records.append(
            {
                "worker_index": worker_index,
                "terminal_outcome_category": outcome_category,
                "worker_reported_outcome_category": (
                    None if diagnostic is None else diagnostic["outcome_category"]
                ),
                "exception_class": (
                    None if diagnostic is None else diagnostic["exception_class"]
                ),
                "process_exit_code": process.exitcode,
                "original_result_tuple_collected": worker_index
                in collected_by_worker,
            }
        )

    final_reservation_cardinality = None
    cardinality_exception_class = None
    cardinality_query_skipped_for_live_workers = any(
        process.is_alive() for process in processes
    )
    if not cardinality_query_skipped_for_live_workers:
        try:
            read_only_uri = path.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(read_only_uri, uri=True) as connection:
                row = connection.execute(
                    "SELECT COUNT(*) FROM replay_reservations"
                ).fetchone()
                if row is not None:
                    final_reservation_cardinality = int(row[0])
        except (OSError, sqlite3.Error) as exc:
            cardinality_exception_class = type(exc).__name__

    report = {
        "worker_records": worker_records,
        "original_collector_results": results,
        "original_collector_count": len(results),
        "original_collector_exception_class": collector_exception_class,
        "original_collector_empty_read_count": collector_empty_read_count,
        "malformed_collector_message_count": malformed_collector_messages,
        "diagnostic_record_count": len(diagnostic_messages),
        "malformed_diagnostic_record_count": malformed_diagnostic_records,
        "duplicate_diagnostic_worker_indices": duplicate_diagnostic_indices,
        "timed_out_worker_indices": timed_out_indices,
        "final_reservation_cardinality": final_reservation_cardinality,
        "cardinality_exception_class": cardinality_exception_class,
        "cardinality_query_skipped_for_live_workers": (
            cardinality_query_skipped_for_live_workers
        ),
    }
    print("RACE_DIAGNOSTIC_JSON=" + json.dumps(report, sort_keys=True))

    assert collector_exception_class is None
    assert collector_empty_read_count == 0
    assert malformed_collector_messages == 0
    assert len(collected_by_worker) == 10
    assert set(collected_by_worker) == set(range(10))
    assert malformed_diagnostic_records == 0
    assert duplicate_diagnostic_indices == []
    assert len(diagnostics_by_worker) == 10
    assert timed_out_indices == []
    assert all(record["process_exit_code"] == 0 for record in worker_records)
    assert all(record["original_result_tuple_collected"] for record in worker_records)
    assert all(record["exception_class"] is None for record in worker_records)
    assert [record["worker_index"] for record in worker_records] == list(range(10))
    assert [record["terminal_outcome_category"] for record in worker_records].count(
        ReplayOutcome.ACCEPTED.value
    ) == 1
    assert [record["terminal_outcome_category"] for record in worker_records].count(
        ReplayOutcome.DUPLICATE.value
    ) == 9
    assert cardinality_exception_class is None
    assert final_reservation_cardinality == 1
    assert results.count(("ok", ReplayOutcome.ACCEPTED.value)) == 1
    assert results.count(("ok", ReplayOutcome.DUPLICATE.value)) == 9


def test_parallel_distinct_nonces_all_succeed(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    _store(path, MutableClock())
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(8)
    output = context.Queue()
    args = [(str(path), nonce, barrier, output) for nonce in range(1, 9)]
    _run_processes(_reserve_worker, args, 8)
    assert [output.get(timeout=3) for _ in range(8)].count(
        ("ok", ReplayOutcome.ACCEPTED.value)
    ) == 8


def test_replay_rejected_after_backend_and_verifier_restart(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    first = _store(path, MutableClock())
    assert first.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.ACCEPTED
    second = _store(path, MutableClock())
    assert second.backend_identity == first.backend_identity
    assert second.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.DUPLICATE


def test_revocation_persists_and_is_visible_to_parallel_workers(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    identity = RevocationIdentity(SIGNER_DIGEST)
    assert store.revoke_signer(
        identity, effective_at=NOW, now=NOW
    ) is RevocationOutcome.APPLIED
    assert _store(path, MutableClock()).revoke_signer(
        identity, effective_at=NOW + 10, now=NOW
    ) is RevocationOutcome.ALREADY_APPLIED

    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(6)
    output = context.Queue()
    args = [(str(path), nonce, barrier, output) for nonce in range(1, 7)]
    _run_processes(_reserve_worker, args, 6)
    assert [output.get(timeout=3) for _ in range(6)].count(
        ("ok", ReplayOutcome.REVOKED.value)
    ) == 6


def test_committed_revocation_wins_reservation_lock_race(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    _store(path, MutableClock())
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    start = context.Event()
    output = context.Queue()
    process = context.Process(
        target=_prepared_reserve_worker,
        args=(str(path), ready, start, output),
    )
    process.start()
    assert ready.wait(10)

    connection = sqlite3.connect(path, timeout=1, isolation_level=None)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        "INSERT INTO signer_revocations "
        "(signer_digest, effective_at, recorded_at) VALUES (?, ?, ?)",
        (SIGNER_DIGEST, NOW, NOW),
    )
    start.set()
    connection.commit()
    connection.close()
    process.join(15)
    if process.is_alive():
        process.terminate()
        process.join(5)
        pytest.fail("revocation-race worker exceeded bounded timeout")
    assert process.exitcode == 0
    assert output.get(timeout=3) == ("ok", ReplayOutcome.REVOKED.value)


def test_revocation_never_deletes_prior_reservations(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    assert store.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.ACCEPTED
    assert store.revoke_signer(
        RevocationIdentity(SIGNER_DIGEST), effective_at=NOW + 60, now=NOW
    ) is RevocationOutcome.APPLIED
    assert store.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.DUPLICATE
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM replay_reservations"
        ).fetchone()[0] == 1


def _envelope(
    *,
    nonce: int = 1,
    body: bytes = b'{"a":1}',
    audience: str = AUDIENCE,
    issued_at: int = NOW,
    expires_at: int = NOW + 120,
) -> GatewayAuthEnvelope:
    return GatewayAuthEnvelope(
        AUTH_VERSION,
        AUTH_ALGORITHM,
        b"POST",
        b"/v1/jobs",
        b"tag=a&tag=",
        hashlib.sha256(body).digest(),
        audience,
        SIGNER,
        nonce.to_bytes(16, "big"),
        issued_at,
        expires_at,
    )


def _headers(envelope: GatewayAuthEnvelope) -> list[tuple[bytes, bytes]]:
    return [
        (b"x-vams-auth-version", envelope.version.encode()),
        (b"x-vams-auth-algorithm", envelope.algorithm.encode()),
        (b"x-vams-auth-audience", envelope.audience.encode()),
        (b"x-vams-auth-signer", envelope.signer.encode()),
        (b"x-vams-auth-nonce", envelope.nonce.hex().encode()),
        (b"x-vams-auth-issued-at", str(envelope.issued_at).encode()),
        (b"x-vams-auth-expires-at", str(envelope.expires_at).encode()),
        (
            b"x-vams-auth-signature",
            sign_message(PRIVATE_KEY, envelope.canonical_bytes()).hex().encode(),
        ),
    ]


def _request(
    envelope: GatewayAuthEnvelope,
    *,
    body: bytes = b'{"a":1}',
    raw_path: bytes | None = None,
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": envelope.method.decode(),
            "scheme": "https",
            "path": (raw_path or envelope.raw_path).decode("ascii"),
            "raw_path": raw_path or envelope.raw_path,
            "query_string": envelope.raw_query,
            "headers": headers or _headers(envelope),
            "client": ("127.0.0.1", 1),
            "server": ("gateway", 443),
        },
        receive,
    )


@pytest.mark.parametrize(
    "mutation",
    ["signature", "signer", "audience", "expired", "canonicalization"],
)
def test_invalid_request_never_consumes_nonce(tmp_path: Path, mutation: str):
    path = tmp_path / "replay.sqlite3"
    clock = MutableClock()
    store = _store(path, clock)
    authenticator = GatewayRequestAuthenticator(
        expected_audience=AUDIENCE,
        clock=clock,
        key_resolver=ConfiguredAdminDIDResolver({"GATEWAY_ADMIN_DID": SIGNER}),
        replay_store=store,
    )
    valid = _envelope()
    candidate = valid
    request_headers = None
    raw_path = None
    if mutation == "signature":
        request_headers = _headers(valid)
        request_headers[-1] = (request_headers[-1][0], b"00" * 64)
    elif mutation == "signer":
        request_headers = _headers(valid)
        request_headers[3] = (
            request_headers[3][0],
            ("did:key:" + (b"\x01" * 64).hex()).encode(),
        )
    elif mutation == "audience":
        candidate = _envelope(audience="vams.gateway.other")
    elif mutation == "expired":
        candidate = _envelope(issued_at=NOW - 120, expires_at=NOW - 1)
    else:
        raw_path = b"/v1/../jobs"

    with pytest.raises(GatewayAuthenticationError):
        asyncio.run(
            authenticator.authenticate(
                _request(
                    candidate,
                    raw_path=raw_path,
                    headers=request_headers,
                )
            )
        )
    assert asyncio.run(
        authenticator.authenticate(_request(valid))
    ).envelope.nonce == valid.nonce


def test_commit_survives_simulated_response_and_process_failure(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    assert store.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.ACCEPTED
    # No response or completion acknowledgement is written. A fresh process-
    # equivalent object must still reject the request.
    restarted = _store(path, MutableClock())
    assert restarted.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.DUPLICATE


def test_storage_failure_before_commit_leaves_no_partial_reservation(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER synthetic_replay_failure BEFORE INSERT "
            "ON replay_reservations BEGIN SELECT RAISE(ABORT, 'synthetic'); END"
        )
    assert store.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.STORAGE_FAILURE
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM replay_reservations"
        ).fetchone()[0] == 0
        connection.execute("DROP TRIGGER synthetic_replay_failure")
    assert store.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.ACCEPTED


def test_expiry_retention_cleanup_and_clock_rollback_fail_closed(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    clock = MutableClock()
    store = _store(path, clock)
    expires = NOW + 10
    assert store.reserve_and_consume(
        _namespace(), expires_at=expires, now=NOW
    ) is ReplayOutcome.ACCEPTED
    retain_until = expires + 300 + 60
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT expires_at, retain_until FROM replay_reservations"
        ).fetchone() == (expires, retain_until)

    clock.value = retain_until - 1
    assert store.cleanup(now=clock.value).deleted == 0
    clock.value = retain_until
    result = store.cleanup(now=clock.value)
    assert result == type(result)(CleanupOutcome.COMPLETED, 1)
    clock.value = NOW
    assert store.reserve_and_consume(
        _namespace(), expires_at=expires, now=NOW
    ) is ReplayOutcome.STORAGE_FAILURE


def test_cleanup_is_bounded_and_transactional(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    clock = MutableClock()
    store = _store(path, clock, cleanup_batch_size=2)
    for nonce in range(1, 6):
        assert store.reserve_and_consume(
            _namespace(nonce), expires_at=NOW + 1, now=NOW
        ) is ReplayOutcome.ACCEPTED
    clock.value = NOW + 362
    assert store.cleanup(now=clock.value).deleted == 2
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM replay_reservations"
        ).fetchone()[0] == 3


def test_database_lock_timeout_fails_closed(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    blocker = sqlite3.connect(path, timeout=1, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        assert store.reserve_and_consume(
            _namespace(), expires_at=NOW + 120, now=NOW
        ) is ReplayOutcome.STORAGE_FAILURE
    finally:
        blocker.rollback()
        blocker.close()


def test_missing_database_after_initialization_fails_without_recreation(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    path.unlink()
    assert store.reserve_and_consume(
        _namespace(), expires_at=NOW + 120, now=NOW
    ) is ReplayOutcome.STORAGE_FAILURE
    assert not path.exists()


def test_corrupt_and_incompatible_schema_reject_initialization(tmp_path: Path):
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")
    corrupt.chmod(0o600)
    with pytest.raises(ReplayStorageInitializationError) as error:
        _store(corrupt, MutableClock())
    assert str(corrupt) not in str(error.value)
    assert "not a sqlite" not in str(error.value)

    incompatible = tmp_path / "incompatible.sqlite3"
    with sqlite3.connect(incompatible) as connection:
        connection.execute("PRAGMA user_version=999")
    incompatible.chmod(0o600)
    with pytest.raises(ReplayStorageInitializationError):
        _store(incompatible, MutableClock())


def test_storage_exceptions_and_logs_do_not_expose_sensitive_values(
    tmp_path: Path, caplog
):
    sensitive = "m2-2-signature-credential-body-marker"
    corrupt = tmp_path / f"{sensitive}.sqlite3"
    corrupt.write_bytes(b"corrupt")
    corrupt.chmod(0o600)
    with pytest.raises(ReplayStorageInitializationError) as captured:
        _store(corrupt, MutableClock())
    assert sensitive not in str(captured.value)
    assert sensitive not in caplog.text


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission contract")
def test_read_only_database_fails_closed(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    path.chmod(0o400)
    try:
        assert store.reserve_and_consume(
            _namespace(), expires_at=NOW + 120, now=NOW
        ) is ReplayOutcome.STORAGE_FAILURE
    finally:
        path.chmod(0o600)


def test_missing_parent_relative_and_symlink_paths_reject(tmp_path: Path):
    with pytest.raises(ReplayStorageInitializationError):
        SQLiteReplayConfiguration("relative.sqlite3")
        _store(Path("relative.sqlite3"), MutableClock())
    with pytest.raises(ReplayStorageInitializationError):
        _store(tmp_path / "missing" / "replay.sqlite3", MutableClock())

    real = tmp_path / "real.sqlite3"
    _store(real, MutableClock())
    link = tmp_path / "linked.sqlite3"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(ReplayStorageInitializationError):
        _store(link, MutableClock())


def test_live_factory_requires_and_initializes_explicit_durable_store(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    live = _policy("testnet")
    with pytest.raises(ReplayStorageInitializationError, match="required"):
        build_gateway_replay_store(live, clock=MutableClock())
    path = tmp_path / "live.sqlite3"
    monkeypatch.setenv(REPLAY_DATABASE_VARIABLE, str(path))
    store = build_gateway_replay_store(live, clock=MutableClock())
    assert isinstance(store, SQLiteDurableReplayStore)
    assert path.exists()
    assert store.deployment_boundary == "single-host-shared-filesystem"


def test_live_never_falls_back_for_corrupt_store(tmp_path: Path, monkeypatch):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"corrupt")
    path.chmod(0o600)
    monkeypatch.setenv("VAMS_ENV", "production")
    monkeypatch.setenv(REPLAY_DATABASE_VARIABLE, str(path))
    with pytest.raises(ReplayStorageInitializationError):
        build_gateway_replay_store(_policy("production"), clock=MutableClock())


def test_process_local_store_remains_non_live_only(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")
    assert isinstance(build_gateway_replay_store(_policy("local")), ProcessLocalReplayStore)
    monkeypatch.setenv("VAMS_ENV", "staging")
    with pytest.raises(ReplayStorageInitializationError):
        build_gateway_replay_store(_policy("staging"))
    with pytest.raises(LiveModeSafetyError):
        ProcessLocalReplayStore(_policy("staging"))


def test_configuration_and_backend_identity_are_immutable(tmp_path: Path, monkeypatch):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    identity = store.backend_identity
    with pytest.raises(RuntimeConfigurationError):
        store._database_path = tmp_path / "other.sqlite3"
    monkeypatch.setenv(REPLAY_DATABASE_VARIABLE, str(tmp_path / "other.sqlite3"))
    assert store.backend_identity == identity
    assert store.configuration.database_path == str(path)


def test_policy_rebinding_rejects_durable_store(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    with pytest.raises(RuntimeConfigurationError, match="does not match"):
        SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(str(tmp_path / "replay.sqlite3")),
            _policy("test"),
            clock=MutableClock(),
        )


def test_database_contains_no_raw_request_or_signer_material(tmp_path: Path):
    path = tmp_path / "replay.sqlite3"
    store = _store(path, MutableClock())
    clock = MutableClock()
    body = b'{"sensitive":"m2-2-body-marker"}'
    envelope = _envelope(body=body)
    request_headers = _headers(envelope)
    signature = request_headers[-1][1]
    authenticator = GatewayRequestAuthenticator(
        expected_audience=AUDIENCE,
        clock=clock,
        key_resolver=ConfiguredAdminDIDResolver({"GATEWAY_ADMIN_DID": SIGNER}),
        replay_store=store,
    )
    asyncio.run(
        authenticator.authenticate(
            _request(envelope, body=body, headers=request_headers)
        )
    )

    durable_bytes = b"".join(
        candidate.read_bytes()
        for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm"))
        if candidate.exists()
    )
    assert SIGNER.encode() not in durable_bytes
    assert body not in durable_bytes
    assert signature not in durable_bytes


def test_gateway_lifespan_initializes_live_store_before_activity(
    tmp_path: Path, monkeypatch
):
    import gateway.server as gateway_server

    path = tmp_path / "gateway.sqlite3"
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv(REPLAY_DATABASE_VARIABLE, str(path))
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "m2-2-test-password")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "aa" * 32)
    monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    with TestClient(gateway_server.app):
        assert isinstance(
            gateway_server.app.state.auth_replay_store,
            SQLiteDurableReplayStore,
        )
        assert path.exists()
    assert gateway_server.cleanup_task is None
    assert gateway_server.auth_replay_store is None


def test_gateway_live_missing_store_rejects_before_background_activity(
    monkeypatch,
):
    import gateway.server as gateway_server

    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.delenv(REPLAY_DATABASE_VARIABLE, raising=False)
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "m2-2-test-password")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "aa" * 32)
    monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    with pytest.raises(ReplayStorageInitializationError):
        with TestClient(gateway_server.app):
            pass
    assert gateway_server.cleanup_task is None
    assert gateway_server.auth_replay_store is None
