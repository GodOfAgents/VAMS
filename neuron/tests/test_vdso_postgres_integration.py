"""Opt-in PostgreSQL integration proof for private VDSO shadow state.

This test truncates the two fixed VDSO test tables. It is intentionally gated
to a dedicated disposable database and must never target shared infrastructure.
"""

from __future__ import annotations

import multiprocessing
import os
from datetime import datetime, timezone
from queue import Empty

import pytest

from gateway.vdso_postgres import PostgresNonceStore, PostgresReplayStore
from neuron.vdso.keccak import keccak_256
from neuron.vdso.shadow_postgres import PostgresShadowStore
from neuron.vdso.shadow_worker import (
    DEFAULT_CHUNK_SIZE,
    EVIDENCE_FILENAMES,
    ImplementationRoot,
    PythonShadowEvaluator,
    SHADOW_INPUT_SCHEMA,
    SHADOW_SEED,
    ShadowRunConfig,
    ShadowSourceRecord,
    TransitionAudit,
    ZERO_HASH,
    build_source_transition,
)


_DSN = os.getenv("VDSO_TEST_POSTGRES_DSN", "").strip()
_RESET_ALLOWED = os.getenv("VDSO_TEST_POSTGRES_ALLOW_RESET") == "1"

pytestmark = pytest.mark.skipif(
    not (_DSN and _RESET_ALLOWED),
    reason=(
        "requires a dedicated disposable PostgreSQL database via "
        "VDSO_TEST_POSTGRES_DSN and VDSO_TEST_POSTGRES_ALLOW_RESET=1"
    ),
)


def _nonce_worker(dsn: str, intent_id: bytes, start, output) -> None:
    start.wait(30)
    store = PostgresNonceStore(dsn)
    key = (bytes.fromhex("11" * 32), bytes.fromhex("22" * 32), 7, 9)
    output.put((intent_id, store.check_and_record(key, intent_id)))


def _replay_worker(dsn: str, now: int, start, output) -> None:
    start.wait(30)
    store = PostgresReplayStore(dsn)
    output.put(store.check_and_record("shared-auth-claim", now, now + 1_000))


def _checkpoint_worker(dsn: str, run_id: str, audit: TransitionAudit, start, output) -> None:
    start.wait(30)
    state = PostgresShadowStore(dsn).record_transition(run_id, audit)
    output.put(state.next_sequence == 1)


def _run_processes(context, target, arguments):
    start = context.Event()
    output = context.Queue()
    processes = [
        context.Process(target=target, args=(*args, start, output))
        for args in arguments
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(60)
        assert process.exitcode == 0

    results = []
    for _process in processes:
        try:
            results.append(output.get(timeout=10))
        except Empty as exc:
            raise AssertionError("PostgreSQL worker produced no result") from exc
    output.close()
    output.join_thread()
    return results


def _truncate_tables(dsn: str) -> None:
    import psycopg2

    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE vams_vdso_nonce_claims, vams_vdso_auth_replays,
                    vams_vdso_shadow_transition_audit, vams_vdso_shadow_chunks,
                    vams_vdso_shadow_runs
                """
            )


def _shadow_config() -> ShadowRunConfig:
    implementations = {
        name: ImplementationRoot(
            source_paths=(source,),
            source_root_sha256=marker * 64,
            artifact_path=EVIDENCE_FILENAMES[name],
            artifact_sha256=marker * 64,
        )
        for name, source, marker in (
            ("python", "neuron/vdso", "a"),
            ("rust", "vams-vm/crates", "b"),
            ("aiken", "cardano/lib/vams/vdso.ak", "c"),
        )
    }
    return ShadowRunConfig(
        commit_sha="1" * 40,
        seed=SHADOW_SEED,
        chunk_size=DEFAULT_CHUNK_SIZE,
        configured_max_gap_seconds=60,
        input_source_schema=SHADOW_INPUT_SCHEMA,
        input_jsonl_path=EVIDENCE_FILENAMES["input"],
        implementation_roots=implementations,
    )


def _database_now(dsn: str) -> int:
    import psycopg2

    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT floor(extract(epoch FROM clock_timestamp()))::bigint"
            )
            return cursor.fetchone()[0]


def test_postgres_atomicity_restart_and_six_figure_state():
    """Prove multi-process claims, restart persistence, and bounded pruning."""

    pytest.importorskip("psycopg2")
    nonce_store = PostgresNonceStore(_DSN)
    replay_store = PostgresReplayStore(_DSN)
    shadow_store = PostgresShadowStore(_DSN)
    nonce_store.initialize()
    replay_store.initialize()
    _truncate_tables(_DSN)
    database_now = _database_now(_DSN)

    context = multiprocessing.get_context("spawn")
    try:
        intents = [index.to_bytes(32, "big") for index in range(1, 9)]
        nonce_results = _run_processes(
            context,
            _nonce_worker,
            [(_DSN, intent_id) for intent_id in intents],
        )
        winners = [intent_id for intent_id, claimed in nonce_results if claimed]
        assert len(winners) == 1

        # A new store instance models a process restart: the winning claim is
        # idempotent, while a distinct intent cannot take over the nonce.
        restarted_nonce_store = PostgresNonceStore(_DSN)
        key = (bytes.fromhex("11" * 32), bytes.fromhex("22" * 32), 7, 9)
        assert restarted_nonce_store.check_and_record(key, winners[0]) is True
        losing_intent = next(intent for intent in intents if intent != winners[0])
        assert restarted_nonce_store.check_and_record(key, losing_intent) is False

        replay_results = _run_processes(
            context,
            _replay_worker,
            [(_DSN, database_now) for _index in range(8)],
        )
        assert replay_results.count(True) == 1
        assert PostgresReplayStore(_DSN).check_and_record(
            "shared-auth-claim", database_now, database_now + 1_000
        ) is False

        config = _shadow_config()
        initial = shadow_store.initialize_run(config)
        source = ShadowSourceRecord.create(
            0,
            keccak_256(b"integration-cursor"),
            keccak_256(b"integration-input"),
            ZERO_HASH,
        )
        transition = build_source_transition(
            config.seed, source, initial.checkpoint_root
        )
        root = PythonShadowEvaluator().evaluate(transition)
        audit = TransitionAudit(
            source_record=source,
            transition=transition,
            python_root=root,
            rust_root=root,
            aiken_root=root,
            recorded_at=datetime.now(timezone.utc),
        )
        checkpoint_results = _run_processes(
            context,
            _checkpoint_worker,
            [(_DSN, config.run_id, audit) for _index in range(8)],
        )
        assert checkpoint_results == [True] * 8
        restarted_shadow_store = PostgresShadowStore(_DSN)
        restarted_state = restarted_shadow_store.load_state(config.run_id)
        assert restarted_state.next_sequence == 1
        assert restarted_state.checkpoint_root == root
        assert restarted_shadow_store.load_last_audit(config.run_id) is not None
        replay_state = restarted_shadow_store.record_replay_verified(config.run_id)
        assert replay_state.restart_count == 1
        assert replay_state.replay_verification_count == 1

        import psycopg2

        with psycopg2.connect(_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE vams_vdso_auth_replays")
                cursor.execute(
                    """
                    INSERT INTO vams_vdso_auth_replays (replay_key, expires_at)
                    SELECT 'bulk-' || value::text, %s
                    FROM generate_series(1, 100001) AS value
                    """,
                    (database_now + 1_000,),
                )
                cursor.execute("SELECT count(*) FROM vams_vdso_auth_replays")
                assert cursor.fetchone()[0] == 100_001

        six_figure_store = PostgresReplayStore(_DSN, cleanup_batch_size=10_000)
        assert six_figure_store.check_and_record(
            "bulk-1", database_now, database_now + 1_000
        ) is False

        with psycopg2.connect(_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE vams_vdso_auth_replays SET expires_at = %s",
                    (database_now,),
                )

        # Eleven bounded claims remove 100,001 expired rows without an
        # unbounded delete in any request transaction.
        for index in range(11):
            assert six_figure_store.check_and_record(
                f"fresh-{index}", database_now, database_now + 1_000
            ) is True

        with psycopg2.connect(_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM vams_vdso_auth_replays WHERE expires_at <= %s",
                    (database_now,),
                )
                assert cursor.fetchone()[0] == 0
                cursor.execute("SELECT count(*) FROM vams_vdso_auth_replays")
                assert cursor.fetchone()[0] == 11
    finally:
        _truncate_tables(_DSN)
