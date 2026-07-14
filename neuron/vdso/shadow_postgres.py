"""Atomic PostgreSQL checkpoints and audits for the private VDSO shadow worker."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from .shadow_worker import (
    DEFAULT_CHUNK_SIZE,
    SHADOW_INPUT_SCHEMA,
    SHADOW_SCHEMA_VERSION,
    ZERO_HASH,
    EvidenceRejected,
    RunState,
    ShadowRunConfig,
    ShadowWorkerError,
    TransitionAudit,
    TransitionRejected,
    advance_transcript,
    initial_checkpoint_root,
    initial_transcript_root,
    is_report_eligible,
)


_CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS vams_vdso_shadow_runs (
    run_id CHAR(64) PRIMARY KEY,
    config_json JSONB NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    last_transition_at TIMESTAMPTZ,
    next_sequence NUMERIC(20, 0) NOT NULL DEFAULT 0,
    checkpoint_root BYTEA NOT NULL,
    source_cursor_hash BYTEA NOT NULL,
    source_chain_root BYTEA NOT NULL,
    python_transcript_root BYTEA NOT NULL,
    rust_transcript_root BYTEA NOT NULL,
    aiken_transcript_root BYTEA NOT NULL,
    python_eval_count BIGINT NOT NULL DEFAULT 0,
    rust_eval_count BIGINT NOT NULL DEFAULT 0,
    aiken_eval_count BIGINT NOT NULL DEFAULT 0,
    chunk_count BIGINT NOT NULL DEFAULT 0,
    max_transition_gap_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    restart_count BIGINT NOT NULL DEFAULT 0,
    replay_verification_count BIGINT NOT NULL DEFAULT 0,
    stop_conditions TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    CHECK (octet_length(checkpoint_root) = 32),
    CHECK (octet_length(source_cursor_hash) = 32),
    CHECK (octet_length(source_chain_root) = 32),
    CHECK (octet_length(python_transcript_root) = 32),
    CHECK (octet_length(rust_transcript_root) = 32),
    CHECK (octet_length(aiken_transcript_root) = 32),
    CHECK (next_sequence >= 0 AND next_sequence <= 18446744073709551615),
    CHECK (python_eval_count >= 0 AND rust_eval_count >= 0 AND aiken_eval_count >= 0),
    CHECK (chunk_count >= 0 AND restart_count >= 0 AND replay_verification_count >= 0),
    CHECK (max_transition_gap_seconds >= 0)
)
"""

_CREATE_AUDIT = """
CREATE TABLE IF NOT EXISTS vams_vdso_shadow_transition_audit (
    run_id CHAR(64) NOT NULL REFERENCES vams_vdso_shadow_runs(run_id),
    source_sequence NUMERIC(20, 0) NOT NULL,
    action SMALLINT NOT NULL CHECK (action = 0),
    source_cursor_hash BYTEA NOT NULL CHECK (octet_length(source_cursor_hash) = 32),
    input_commitment BYTEA NOT NULL CHECK (octet_length(input_commitment) = 32),
    previous_source_record_sha256 BYTEA NOT NULL CHECK (octet_length(previous_source_record_sha256) = 32),
    source_record_sha256 BYTEA NOT NULL CHECK (octet_length(source_record_sha256) = 32),
    previous_root BYTEA NOT NULL CHECK (octet_length(previous_root) = 32),
    canonical_transition BYTEA NOT NULL CHECK (octet_length(canonical_transition) = 96),
    python_root BYTEA NOT NULL CHECK (octet_length(python_root) = 32),
    rust_root BYTEA NOT NULL CHECK (octet_length(rust_root) = 32),
    aiken_root BYTEA NOT NULL CHECK (octet_length(aiken_root) = 32),
    transition_gap_seconds DOUBLE PRECISION NOT NULL CHECK (transition_gap_seconds >= 0),
    recorded_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, source_sequence),
    UNIQUE (run_id, source_cursor_hash),
    UNIQUE (run_id, source_record_sha256)
)
"""

_CREATE_CHUNKS = """
CREATE TABLE IF NOT EXISTS vams_vdso_shadow_chunks (
    run_id CHAR(64) NOT NULL REFERENCES vams_vdso_shadow_runs(run_id),
    chunk_index BIGINT NOT NULL,
    start_sequence NUMERIC(20, 0) NOT NULL,
    end_sequence NUMERIC(20, 0) NOT NULL,
    transition_count BIGINT NOT NULL CHECK (transition_count = 1000),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    max_gap_seconds DOUBLE PRECISION NOT NULL CHECK (max_gap_seconds >= 0),
    starting_root BYTEA NOT NULL CHECK (octet_length(starting_root) = 32),
    ending_root BYTEA NOT NULL CHECK (octet_length(ending_root) = 32),
    source_start_cursor_hash BYTEA NOT NULL CHECK (octet_length(source_start_cursor_hash) = 32),
    source_end_cursor_hash BYTEA NOT NULL CHECK (octet_length(source_end_cursor_hash) = 32),
    source_chain_root_sha256 BYTEA NOT NULL CHECK (octet_length(source_chain_root_sha256) = 32),
    python_transcript_root BYTEA NOT NULL CHECK (octet_length(python_transcript_root) = 32),
    rust_transcript_root BYTEA NOT NULL CHECK (octet_length(rust_transcript_root) = 32),
    aiken_transcript_root BYTEA NOT NULL CHECK (octet_length(aiken_transcript_root) = 32),
    PRIMARY KEY (run_id, chunk_index),
    UNIQUE (run_id, start_sequence),
    UNIQUE (run_id, end_sequence)
)
"""

_SELECT_RUN = """
SELECT run_id, config_json, started_at, last_transition_at, next_sequence,
       checkpoint_root, source_cursor_hash, source_chain_root,
       python_transcript_root, rust_transcript_root, aiken_transcript_root,
       python_eval_count, rust_eval_count, aiken_eval_count, chunk_count,
       max_transition_gap_seconds, restart_count, replay_verification_count,
       stop_conditions
FROM vams_vdso_shadow_runs
WHERE run_id = %s
"""

_SELECT_RUN_FOR_UPDATE = """
SELECT run_id, config_json, started_at, last_transition_at, next_sequence,
       checkpoint_root, source_cursor_hash, source_chain_root,
       python_transcript_root, rust_transcript_root, aiken_transcript_root,
       python_eval_count, rust_eval_count, aiken_eval_count, chunk_count,
       max_transition_gap_seconds, restart_count, replay_verification_count,
       stop_conditions
FROM vams_vdso_shadow_runs
WHERE run_id = %s
FOR UPDATE
"""


def _connect(dsn: str):
    import psycopg2

    return psycopg2.connect(dsn, application_name="vams-vdso-shadow-worker")


def _validate_dsn(dsn: str) -> None:
    if not isinstance(dsn, str) or not dsn.strip():
        raise ShadowWorkerError("VDSO_POSTGRES_DSN is required")
    try:
        from psycopg2.extensions import parse_dsn

        parsed = parse_dsn(dsn)
    except Exception as exc:
        raise ShadowWorkerError("VDSO_POSTGRES_DSN is invalid") from exc
    host = parsed.get("host", "")
    hostaddr = parsed.get("hostaddr", "")
    if parsed.get("service") and not (host or hostaddr):
        raise ShadowWorkerError("PostgreSQL service DSNs must declare an explicit host")
    endpoints = [value for value in (host, hostaddr) if value]
    if not endpoints or all(
        value in {"localhost", "127.0.0.1", "::1"} or value.startswith("/")
        for value in endpoints
    ):
        return
    if parsed.get("sslmode") != "verify-full" or not parsed.get("sslrootcert"):
        raise ShadowWorkerError(
            "remote shadow PostgreSQL requires sslmode=verify-full and sslrootcert"
        )


def _int(value: int | Decimal) -> int:
    return int(value)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PostgresShadowStore:
    """Serialize checkpoints and transition audits under a per-run row lock."""

    durable = True
    shared = True

    def __init__(self, dsn: str, *, connect: Callable = _connect) -> None:
        _validate_dsn(dsn)
        self._dsn = dsn
        self._connect = connect
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(_CREATE_RUNS)
                    cursor.execute(_CREATE_AUDIT)
                    cursor.execute(_CREATE_CHUNKS)
        finally:
            connection.close()

    @staticmethod
    def _state(row: Sequence[Any]) -> RunState:
        if row is None:
            raise EvidenceRejected("shadow run does not exist")
        config_value = row[1]
        if isinstance(config_value, str):
            config_value = json.loads(config_value)
        config = ShadowRunConfig.from_mapping(config_value)
        return RunState(
            run_id=row[0].strip(),
            config=config,
            started_at=_aware(row[2]),
            last_transition_at=_aware(row[3]) if row[3] is not None else None,
            next_sequence=_int(row[4]),
            checkpoint_root=bytes(row[5]),
            source_cursor_hash=bytes(row[6]),
            source_chain_root=bytes(row[7]),
            transcript_roots={
                "python": bytes(row[8]),
                "rust": bytes(row[9]),
                "aiken": bytes(row[10]),
            },
            backend_eval_count={
                "python": _int(row[11]),
                "rust": _int(row[12]),
                "aiken": _int(row[13]),
            },
            chunk_count=_int(row[14]),
            max_transition_gap_seconds=float(row[15]),
            restart_count=_int(row[16]),
            replay_verification_count=_int(row[17]),
            stop_conditions=tuple(sorted(row[18] or ())),
        )

    def initialize_run(self, config: ShadowRunConfig) -> RunState:
        checkpoint = initial_checkpoint_root(config.seed)
        transcript = initial_transcript_root(config.commit_sha, config.seed)
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO vams_vdso_shadow_runs (
                            run_id, config_json, checkpoint_root, source_cursor_hash,
                            source_chain_root, python_transcript_root,
                            rust_transcript_root, aiken_transcript_root
                        ) VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (run_id) DO NOTHING
                        """,
                        (
                            config.run_id,
                            json.dumps(config.as_mapping(), sort_keys=True),
                            checkpoint,
                            ZERO_HASH,
                            ZERO_HASH,
                            transcript,
                            transcript,
                            transcript,
                        ),
                    )
                    cursor.execute(_SELECT_RUN_FOR_UPDATE, (config.run_id,))
                    state = self._state(cursor.fetchone())
                    if state.config.as_mapping() != config.as_mapping():
                        raise EvidenceRejected("shadow run configuration mismatch")
                    return state
        finally:
            connection.close()

    def load_state(self, run_id: str) -> RunState:
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(_SELECT_RUN, (run_id,))
                    return self._state(cursor.fetchone())
        finally:
            connection.close()

    @staticmethod
    def _audit_from_row(row: Sequence[Any]) -> TransitionAudit:
        from .shadow_worker import ShadowSourceRecord, ShadowTransition

        source = ShadowSourceRecord(
            source_sequence=_int(row[0]),
            source_cursor_hash=bytes(row[2]),
            input_commitment=bytes(row[3]),
            previous_source_record_sha256=bytes(row[4]),
            source_record_sha256=bytes(row[5]),
        )
        transition = ShadowTransition(
            action=_int(row[1]),
            sequence=_int(row[0]),
            expected_previous_root=bytes(row[6]),
            actual_previous_root=bytes(row[6]),
            input_commitment=bytes(row[3]),
            canonical_transition=bytes(row[7]),
            expected_commitment=bytes(row[8]),
        )
        audit = TransitionAudit(
            source_record=source,
            transition=transition,
            python_root=bytes(row[8]),
            rust_root=bytes(row[9]),
            aiken_root=bytes(row[10]),
            recorded_at=_aware(row[11]),
        )
        audit.validate()
        return audit

    def load_last_audit(self, run_id: str) -> TransitionAudit | None:
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT source_sequence, action, source_cursor_hash,
                               input_commitment, previous_source_record_sha256,
                               source_record_sha256, previous_root,
                               canonical_transition, python_root, rust_root,
                               aiken_root, recorded_at
                        FROM vams_vdso_shadow_transition_audit
                        WHERE run_id = %s
                        ORDER BY source_sequence DESC
                        LIMIT 1
                        """,
                        (run_id,),
                    )
                    row = cursor.fetchone()
                    return None if row is None else self._audit_from_row(row)
        finally:
            connection.close()

    @staticmethod
    def _same_audit(row: Sequence[Any], audit: TransitionAudit) -> bool:
        stored = PostgresShadowStore._audit_from_row(row)
        return (
            stored.source_record == audit.source_record
            and stored.transition == audit.transition
            and stored.python_root == audit.python_root
            and stored.rust_root == audit.rust_root
            and stored.aiken_root == audit.aiken_root
        )

    def record_transition(self, run_id: str, audit: TransitionAudit) -> RunState:
        audit.validate()
        sequence = audit.transition.sequence
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(_SELECT_RUN_FOR_UPDATE, (run_id,))
                    state = self._state(cursor.fetchone())
                    cursor.execute("SELECT clock_timestamp()")
                    recorded_at = _aware(cursor.fetchone()[0])
                    if state.stop_conditions:
                        raise ShadowWorkerError("shadow run is permanently stopped")
                    if sequence < state.next_sequence:
                        cursor.execute(
                            """
                            SELECT source_sequence, action, source_cursor_hash,
                                   input_commitment, previous_source_record_sha256,
                                   source_record_sha256, previous_root,
                                   canonical_transition, python_root, rust_root,
                                   aiken_root, recorded_at
                            FROM vams_vdso_shadow_transition_audit
                            WHERE run_id = %s AND source_sequence = %s
                            """,
                            (run_id, sequence),
                        )
                        row = cursor.fetchone()
                        if row is None or not self._same_audit(row, audit):
                            raise TransitionRejected("non-deterministic transition replay")
                        return state
                    if sequence != state.next_sequence:
                        raise TransitionRejected("transition sequence gap")
                    if audit.transition.actual_previous_root != state.checkpoint_root:
                        raise TransitionRejected("transition checkpoint root mismatch")
                    if (
                        audit.source_record.previous_source_record_sha256
                        != state.source_chain_root
                    ):
                        raise TransitionRejected("source record checkpoint mismatch")
                    if audit.source_record.source_cursor_hash == state.source_cursor_hash:
                        raise TransitionRejected("source cursor duplicate")

                    if state.last_transition_at is None:
                        gap = 0.0
                    else:
                        gap = (
                            recorded_at - state.last_transition_at
                        ).total_seconds()
                        if gap <= 0:
                            raise TransitionRejected("transition timestamp is not increasing")
                        if gap > state.config.configured_max_gap_seconds:
                            raise TransitionRejected("transition continuity gap exceeded")

                    next_transcripts = {
                        name: advance_transcript(
                            state.transcript_roots[name], sequence, root
                        )
                        for name, root in (
                            ("python", audit.python_root),
                            ("rust", audit.rust_root),
                            ("aiken", audit.aiken_root),
                        )
                    }
                    cursor.execute(
                        """
                        INSERT INTO vams_vdso_shadow_transition_audit (
                            run_id, source_sequence, action, source_cursor_hash,
                            input_commitment, previous_source_record_sha256,
                            source_record_sha256, previous_root,
                            canonical_transition, python_root, rust_root,
                            aiken_root, transition_gap_seconds, recorded_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            run_id,
                            sequence,
                            audit.transition.action,
                            audit.source_record.source_cursor_hash,
                            audit.source_record.input_commitment,
                            audit.source_record.previous_source_record_sha256,
                            audit.source_record.source_record_sha256,
                            audit.transition.actual_previous_root,
                            audit.transition.canonical_transition,
                            audit.python_root,
                            audit.rust_root,
                            audit.aiken_root,
                            gap,
                            recorded_at,
                        ),
                    )
                    next_sequence = sequence + 1
                    cursor.execute(
                        """
                        UPDATE vams_vdso_shadow_runs
                        SET started_at = CASE WHEN next_sequence = 0 THEN %s ELSE started_at END,
                            last_transition_at = %s,
                            next_sequence = %s,
                            checkpoint_root = %s,
                            source_cursor_hash = %s,
                            source_chain_root = %s,
                            python_transcript_root = %s,
                            rust_transcript_root = %s,
                            aiken_transcript_root = %s,
                            python_eval_count = python_eval_count + 1,
                            rust_eval_count = rust_eval_count + 1,
                            aiken_eval_count = aiken_eval_count + 1,
                            max_transition_gap_seconds = GREATEST(max_transition_gap_seconds, %s)
                        WHERE run_id = %s
                        """,
                        (
                            recorded_at,
                            recorded_at,
                            next_sequence,
                            audit.python_root,
                            audit.source_record.source_cursor_hash,
                            audit.source_record.source_record_sha256,
                            next_transcripts["python"],
                            next_transcripts["rust"],
                            next_transcripts["aiken"],
                            gap,
                            run_id,
                        ),
                    )

                    if next_sequence % state.config.chunk_size == 0:
                        chunk_index = sequence // state.config.chunk_size
                        start_sequence = next_sequence - state.config.chunk_size
                        cursor.execute(
                            """
                            SELECT MIN(recorded_at), MAX(recorded_at),
                                   MAX(transition_gap_seconds)
                            FROM vams_vdso_shadow_transition_audit
                            WHERE run_id = %s
                              AND source_sequence BETWEEN %s AND %s
                            """,
                            (run_id, start_sequence, sequence),
                        )
                        started_at, completed_at, max_gap = cursor.fetchone()
                        cursor.execute(
                            """
                            SELECT previous_root, source_cursor_hash
                            FROM vams_vdso_shadow_transition_audit
                            WHERE run_id = %s AND source_sequence = %s
                            """,
                            (run_id, start_sequence),
                        )
                        starting_root, source_start_cursor = cursor.fetchone()
                        cursor.execute(
                            """
                            INSERT INTO vams_vdso_shadow_chunks (
                                run_id, chunk_index, start_sequence, end_sequence,
                                transition_count, started_at, completed_at,
                                max_gap_seconds, starting_root, ending_root,
                                source_start_cursor_hash, source_end_cursor_hash,
                                source_chain_root_sha256, python_transcript_root,
                                rust_transcript_root, aiken_transcript_root
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                run_id,
                                chunk_index,
                                start_sequence,
                                sequence,
                                state.config.chunk_size,
                                started_at,
                                completed_at,
                                max_gap,
                                starting_root,
                                audit.python_root,
                                source_start_cursor,
                                audit.source_record.source_cursor_hash,
                                audit.source_record.source_record_sha256,
                                next_transcripts["python"],
                                next_transcripts["rust"],
                                next_transcripts["aiken"],
                            ),
                        )
                        cursor.execute(
                            """
                            UPDATE vams_vdso_shadow_runs
                            SET chunk_count = chunk_count + 1
                            WHERE run_id = %s
                            """,
                            (run_id,),
                        )

                    cursor.execute(_SELECT_RUN, (run_id,))
                    return self._state(cursor.fetchone())
        finally:
            connection.close()

    def record_replay_verified(self, run_id: str) -> RunState:
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(_SELECT_RUN_FOR_UPDATE, (run_id,))
                    state = self._state(cursor.fetchone())
                    if state.next_sequence == 0:
                        raise EvidenceRejected("cannot verify replay before a transition exists")
                    cursor.execute(
                        """
                        UPDATE vams_vdso_shadow_runs
                        SET restart_count = restart_count + 1,
                            replay_verification_count = replay_verification_count + 1
                        WHERE run_id = %s
                        """,
                        (run_id,),
                    )
                    cursor.execute(_SELECT_RUN, (run_id,))
                    return self._state(cursor.fetchone())
        finally:
            connection.close()

    def record_stop(self, run_id: str, code: str) -> None:
        allowed = {
            "backend_unavailable",
            "continuity_gap",
            "external_write",
            "plaintext_payload",
            "privacy_failure",
            "replay_mismatch",
            "source_chain_mismatch",
            "transition_divergence",
        }
        if code not in allowed:
            raise ValueError("unknown shadow stop condition")
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE vams_vdso_shadow_runs
                        SET stop_conditions = CASE
                            WHEN %s = ANY(stop_conditions) THEN stop_conditions
                            ELSE array_append(stop_conditions, %s)
                        END
                        WHERE run_id = %s
                        """,
                        (code, code, run_id),
                    )
                    if cursor.rowcount != 1:
                        raise EvidenceRejected("shadow run does not exist")
        finally:
            connection.close()

    def export_evidence_records(self, run_id: str) -> Sequence[Mapping[str, Any]]:
        state = self.load_state(run_id)
        if not is_report_eligible(state):
            raise EvidenceRejected("shadow run is not eligible for evidence export")
        implementation_roots = {
            name: state.config.implementation_roots[name].as_mapping()
            for name in ("python", "rust", "aiken")
        }
        records: list[Mapping[str, Any]] = [
            {
                "record_type": "run",
                "schema_version": SHADOW_SCHEMA_VERSION,
                "run_id": state.run_id,
                "commit_sha": state.config.commit_sha,
                "seed": state.config.seed,
                "started_at": state.started_at.isoformat().replace("+00:00", "Z"),
                "chunk_size": state.config.chunk_size,
                "configured_max_gap_seconds": state.config.configured_max_gap_seconds,
                "initial_root": initial_checkpoint_root(state.config.seed).hex(),
                "input_source_schema": SHADOW_INPUT_SCHEMA,
                "input_jsonl_path": state.config.input_jsonl_path,
                "implementation_roots": implementation_roots,
            }
        ]
        connection = self._connect(self._dsn)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT chunk_index, start_sequence, end_sequence,
                               transition_count, started_at, completed_at,
                               max_gap_seconds, starting_root, ending_root,
                               source_start_cursor_hash, source_end_cursor_hash,
                               source_chain_root_sha256, python_transcript_root,
                               rust_transcript_root, aiken_transcript_root
                        FROM vams_vdso_shadow_chunks
                        WHERE run_id = %s
                        ORDER BY chunk_index
                        """,
                        (run_id,),
                    )
                    rows = cursor.fetchall()
        finally:
            connection.close()
        if len(rows) != state.chunk_count:
            raise EvidenceRejected("shadow chunk count mismatch")
        for row in rows:
            count = _int(row[3])
            records.append(
                {
                    "record_type": "chunk",
                    "schema_version": SHADOW_SCHEMA_VERSION,
                    "run_id": state.run_id,
                    "chunk_index": _int(row[0]),
                    "start_sequence": _int(row[1]),
                    "end_sequence": _int(row[2]),
                    "transition_count": count,
                    "started_at": _aware(row[4]).isoformat().replace("+00:00", "Z"),
                    "completed_at": _aware(row[5]).isoformat().replace("+00:00", "Z"),
                    "max_gap_seconds": float(row[6]),
                    "starting_root": bytes(row[7]).hex(),
                    "ending_root": bytes(row[8]).hex(),
                    "source_start_cursor_hash": bytes(row[9]).hex(),
                    "source_end_cursor_hash": bytes(row[10]).hex(),
                    "source_chain_root_sha256": bytes(row[11]).hex(),
                    "backend_eval_count": {
                        "python": count,
                        "rust": count,
                        "aiken": count,
                    },
                    "transcript_roots": {
                        "python": bytes(row[12]).hex(),
                        "rust": bytes(row[13]).hex(),
                        "aiken": bytes(row[14]).hex(),
                    },
                }
            )
        records.append(
            {
                "record_type": "summary",
                "schema_version": SHADOW_SCHEMA_VERSION,
                "run_id": state.run_id,
                "completed_at": state.completed_at.isoformat().replace("+00:00", "Z"),
                "observed_seconds": state.observed_seconds,
                "transition_count": state.transition_count,
                "chunk_count": state.chunk_count,
                "max_transition_gap_seconds": state.max_transition_gap_seconds,
                "configured_max_gap_seconds": state.config.configured_max_gap_seconds,
                "restart_count": state.restart_count,
                "replay_verification_count": state.replay_verification_count,
                "backend_eval_count": dict(state.backend_eval_count),
                "source_record_count": state.transition_count,
                "source_final_cursor_hash": state.source_cursor_hash.hex(),
                "source_chain_root_sha256": state.source_chain_root.hex(),
                "final_root": state.checkpoint_root.hex(),
                "final_transcript_roots": {
                    name: state.transcript_roots[name].hex()
                    for name in ("python", "rust", "aiken")
                },
                "divergence_count": 0,
                "external_write_count": 0,
                "plaintext_payload_count": 0,
                "privacy_result": "pass",
                "stop_conditions_triggered": False,
            }
        )
        return records
