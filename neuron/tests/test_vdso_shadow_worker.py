from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from neuron.vdso.shadow_worker import (
    AikenShadowEvaluator,
    AppendOnlyJsonlSource,
    BackendUnavailable,
    EVIDENCE_FILENAMES,
    EvidenceRejected,
    ImplementationRoot,
    PythonShadowEvaluator,
    RunState,
    RustShadowEvaluator,
    SHADOW_SCHEMA_VERSION,
    ShadowRunConfig,
    ShadowSourceRecord,
    ShadowWorker,
    SourcePending,
    TransitionAudit,
    TransitionDivergence,
    TransitionRejected,
    ZERO_HASH,
    advance_transcript,
    build_source_transition,
    chain_evidence_records,
    initial_checkpoint_root,
    initial_transcript_root,
    is_report_eligible,
    serialize_evidence_records,
    verify_audit_jsonl,
)
from neuron.vdso.keccak import keccak_256


UTC = timezone.utc


def _implementation(name: str, source: str, marker: str) -> ImplementationRoot:
    return ImplementationRoot(
        source_paths=(source,),
        source_root_sha256=marker * 64,
        artifact_path=EVIDENCE_FILENAMES[name],
        artifact_sha256=marker * 64,
    )


def _config() -> ShadowRunConfig:
    return ShadowRunConfig(
        commit_sha="1" * 40,
        seed=20260713,
        chunk_size=1000,
        configured_max_gap_seconds=60,
        input_source_schema="vdso-shadow-input-v1",
        input_jsonl_path=EVIDENCE_FILENAMES["input"],
        implementation_roots={
            "python": _implementation("python", "neuron/vdso", "a"),
            "rust": _implementation("rust", "vams-vm/crates", "b"),
            "aiken": _implementation("aiken", "cardano/lib/vams/vdso.ak", "c"),
        },
    )


def _source_record(sequence: int, previous: bytes) -> ShadowSourceRecord:
    return ShadowSourceRecord.create(
        sequence,
        keccak_256(b"cursor" + sequence.to_bytes(8, "big")),
        keccak_256(b"input" + sequence.to_bytes(8, "big")),
        previous,
    )


class _MemorySource:
    def __init__(self, records: list[ShadowSourceRecord]) -> None:
        self.records = {record.source_sequence: record for record in records}
        self.next_sequence = 0
        self.previous = ZERO_HASH

    def resume(self, next_sequence: int, previous_hash: bytes) -> None:
        self.next_sequence = next_sequence
        self.previous = previous_hash

    def next_record(self) -> ShadowSourceRecord:
        if self.next_sequence not in self.records:
            raise SourcePending("pending")
        record = self.records[self.next_sequence]
        if record.previous_source_record_sha256 != self.previous:
            raise TransitionRejected("source mismatch")
        self.next_sequence += 1
        self.previous = record.source_record_sha256
        return record


class _MemoryStore:
    def __init__(
        self,
        config: ShadowRunConfig,
        *,
        next_sequence: int = 0,
        checkpoint_root: bytes | None = None,
        source_cursor_hash: bytes = ZERO_HASH,
        source_chain_root: bytes = ZERO_HASH,
    ) -> None:
        started = datetime(2026, 7, 14, tzinfo=UTC)
        transcript = initial_transcript_root(config.commit_sha, config.seed)
        self.state = RunState(
            run_id=config.run_id,
            config=config,
            started_at=started,
            last_transition_at=None,
            next_sequence=next_sequence,
            checkpoint_root=checkpoint_root or initial_checkpoint_root(config.seed),
            source_cursor_hash=source_cursor_hash,
            source_chain_root=source_chain_root,
            transcript_roots={"python": transcript, "rust": transcript, "aiken": transcript},
            backend_eval_count={
                "python": next_sequence,
                "rust": next_sequence,
                "aiken": next_sequence,
            },
            chunk_count=next_sequence // config.chunk_size,
            max_transition_gap_seconds=0,
            restart_count=0,
            replay_verification_count=0,
            stop_conditions=(),
        )
        self.audits: dict[int, TransitionAudit] = {}

    def initialize_run(self, config: ShadowRunConfig) -> RunState:
        assert config == self.state.config
        return self.state

    def load_state(self, run_id: str) -> RunState:
        assert run_id == self.state.run_id
        return self.state

    def load_last_audit(self, run_id: str) -> TransitionAudit | None:
        assert run_id == self.state.run_id
        return self.audits[max(self.audits)] if self.audits else None

    def record_transition(self, run_id: str, audit: TransitionAudit) -> RunState:
        assert run_id == self.state.run_id
        audit.validate()
        assert audit.transition.sequence == self.state.next_sequence
        assert audit.transition.actual_previous_root == self.state.checkpoint_root
        assert (
            audit.source_record.previous_source_record_sha256
            == self.state.source_chain_root
        )
        transcripts = {
            name: advance_transcript(
                self.state.transcript_roots[name],
                audit.transition.sequence,
                getattr(audit, f"{name}_root"),
            )
            for name in ("python", "rust", "aiken")
        }
        next_sequence = self.state.next_sequence + 1
        self.audits[audit.transition.sequence] = audit
        self.state = replace(
            self.state,
            started_at=(
                audit.recorded_at
                if self.state.next_sequence == 0
                else self.state.started_at
            ),
            last_transition_at=audit.recorded_at,
            next_sequence=next_sequence,
            checkpoint_root=audit.python_root,
            source_cursor_hash=audit.source_record.source_cursor_hash,
            source_chain_root=audit.source_record.source_record_sha256,
            transcript_roots=transcripts,
            backend_eval_count={name: next_sequence for name in ("python", "rust", "aiken")},
            chunk_count=next_sequence // self.state.config.chunk_size,
        )
        return self.state

    def record_replay_verified(self, run_id: str) -> RunState:
        assert run_id == self.state.run_id
        self.state = replace(
            self.state,
            restart_count=self.state.restart_count + 1,
            replay_verification_count=self.state.replay_verification_count + 1,
        )
        return self.state

    def record_stop(self, run_id: str, code: str) -> None:
        assert run_id == self.state.run_id
        self.state = replace(
            self.state,
            stop_conditions=tuple(sorted(set((*self.state.stop_conditions, code)))),
        )

    def export_evidence_records(self, run_id: str):
        raise NotImplementedError


class _CountingEvaluator:
    def __init__(self, name: str, *, wrong: bool = False) -> None:
        self.name = name
        self.wrong = wrong
        self.calls: list[int] = []

    def evaluate(self, transition):
        transition.validate()
        self.calls.append(transition.sequence)
        return b"\xff" * 32 if self.wrong else transition.expected_commitment


def _write_source(path: Path, records: list[ShadowSourceRecord]) -> None:
    path.write_bytes(
        b"".join(
            json.dumps(
                record.as_mapping(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            + b"\n"
            for record in records
        )
    )


def test_append_only_source_rejects_gap_duplicate_plaintext_and_partial(tmp_path: Path):
    first = _source_record(0, ZERO_HASH)
    second = _source_record(1, first.source_record_sha256)
    source_path = tmp_path / EVIDENCE_FILENAMES["input"]
    _write_source(source_path, [first, second])
    source = AppendOnlyJsonlSource(source_path)
    source.resume(0, ZERO_HASH)
    assert source.next_record() == first
    assert source.next_record() == second
    with pytest.raises(SourcePending):
        source.next_record()

    duplicate = _source_record(1, second.source_record_sha256)
    _write_source(source_path, [first, second, duplicate])
    source.resume(2, second.source_record_sha256)
    with pytest.raises(TransitionRejected, match="gap, duplicate, or reordering"):
        source.next_record()

    plaintext = first.as_mapping() | {"payload": "forbidden"}
    source_path.write_bytes(
        json.dumps(plaintext, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )
    source.resume(0, ZERO_HASH)
    with pytest.raises(TransitionRejected, match="plaintext-like"):
        source.next_record()

    source_path.write_bytes(json.dumps(first.as_mapping()).encode("utf-8"))
    source.resume(0, ZERO_HASH)
    with pytest.raises(SourcePending, match="newline-terminated"):
        source.next_record()


def test_worker_runs_all_backends_and_replays_on_restart():
    config = _config()
    first = _source_record(0, ZERO_HASH)
    source = _MemorySource([first])
    store = _MemoryStore(config)
    rust = _CountingEvaluator("rust")
    aiken = _CountingEvaluator("aiken")
    worker = ShadowWorker(
        config,
        store,
        [PythonShadowEvaluator(), rust, aiken],
        source,
    )
    recorded_at = store.state.started_at + timedelta(seconds=1)
    state = worker.run_once(recorded_at=recorded_at)
    assert state.next_sequence == 1
    assert rust.calls == [0]
    assert aiken.calls == [0]

    restarted = ShadowWorker(
        config,
        store,
        [PythonShadowEvaluator(), rust, aiken],
        _MemorySource([first]),
    )
    state = restarted.initialize()
    assert state.restart_count == 1
    assert state.replay_verification_count == 1
    assert rust.calls == [0, 0]
    assert aiken.calls == [0, 0]


def test_worker_remains_deterministic_beyond_one_hundred_thousand():
    config = _config()
    sequence = 100_000
    previous_root = keccak_256(b"checkpoint-100000")
    previous_source = keccak_256(b"source-100000")
    previous_cursor = keccak_256(b"cursor-99999")
    record = _source_record(sequence, previous_source)
    store = _MemoryStore(
        config,
        next_sequence=sequence,
        checkpoint_root=previous_root,
        source_cursor_hash=previous_cursor,
        source_chain_root=previous_source,
    )
    evaluators = [
        _CountingEvaluator("python"),
        _CountingEvaluator("rust"),
        _CountingEvaluator("aiken"),
    ]
    worker = ShadowWorker(config, store, evaluators, _MemorySource([record]))
    state = worker.run_once(recorded_at=store.state.started_at + timedelta(seconds=1))
    assert state.next_sequence == 100_001
    assert all(evaluator.calls == [100_000] for evaluator in evaluators)
    assert state.source_chain_root == record.source_record_sha256


def test_worker_fails_closed_on_divergence_and_missing_backend():
    config = _config()
    record = _source_record(0, ZERO_HASH)
    store = _MemoryStore(config)
    worker = ShadowWorker(
        config,
        store,
        [
            _CountingEvaluator("python"),
            _CountingEvaluator("rust", wrong=True),
            _CountingEvaluator("aiken"),
        ],
        _MemorySource([record]),
    )
    with pytest.raises(TransitionDivergence):
        worker.run_once(recorded_at=store.state.started_at + timedelta(seconds=1))
    assert "transition_divergence" in store.state.stop_conditions

    with pytest.raises(BackendUnavailable, match="mandatory"):
        ShadowWorker(
            config,
            _MemoryStore(config),
            [_CountingEvaluator("python"), _CountingEvaluator("rust")],
            _MemorySource([record]),
        )


def test_evidence_jsonl_chain_detects_tampering(tmp_path: Path):
    run_id = "d" * 64
    records = [
        {"record_type": "run", "schema_version": SHADOW_SCHEMA_VERSION, "run_id": run_id},
        {
            "record_type": "chunk",
            "schema_version": SHADOW_SCHEMA_VERSION,
            "run_id": run_id,
            "chunk_index": 0,
        },
        {
            "record_type": "summary",
            "schema_version": SHADOW_SCHEMA_VERSION,
            "run_id": run_id,
            "chunk_count": 1,
        },
    ]
    audit_path = tmp_path / EVIDENCE_FILENAMES["audit"]
    audit_path.write_bytes(serialize_evidence_records(records))
    summary = verify_audit_jsonl(audit_path, run_id)
    assert summary["record_sha256"] == chain_evidence_records(records)[-1]["record_sha256"]

    tampered = audit_path.read_bytes().replace(b'"chunk_index":0', b'"chunk_index":1')
    audit_path.write_bytes(tampered)
    with pytest.raises(EvidenceRejected, match="hash|contiguous"):
        verify_audit_jsonl(audit_path, run_id)


def test_report_eligibility_requires_time_counts_replay_and_equal_roots():
    config = _config()
    base = _MemoryStore(config).state
    final_root = keccak_256(b"final-root")
    transcript = keccak_256(b"final-transcript")
    eligible = replace(
        base,
        last_transition_at=base.started_at + timedelta(days=7),
        next_sequence=100_000,
        checkpoint_root=final_root,
        source_cursor_hash=keccak_256(b"source-cursor"),
        source_chain_root=keccak_256(b"source-chain"),
        transcript_roots={name: transcript for name in ("python", "rust", "aiken")},
        backend_eval_count={name: 100_000 for name in ("python", "rust", "aiken")},
        chunk_count=100,
        max_transition_gap_seconds=6,
        restart_count=1,
        replay_verification_count=1,
    )
    assert is_report_eligible(eligible)
    assert not is_report_eligible(replace(eligible, replay_verification_count=0))
    assert not is_report_eligible(
        replace(
            eligible,
            transcript_roots={
                "python": transcript,
                "rust": transcript,
                "aiken": keccak_256(b"divergent"),
            },
        )
    )
    assert not is_report_eligible(replace(eligible, stop_conditions=("continuity_gap",)))


@pytest.mark.skipif(
    not Path("cardano/build/shadow/vdso-shadow-read.cbor").exists(),
    reason="run prepare-aiken to enable the real UPLC evaluator integration",
)
def test_real_aiken_uplc_evaluator_matches_python():
    source = _source_record(7, ZERO_HASH)
    transition = build_source_transition(20260713, source, b"\x11" * 32)
    python_root = PythonShadowEvaluator().evaluate(transition)
    aiken_root = AikenShadowEvaluator(
        Path("cardano/build/shadow/vdso-shadow-read.cbor")
    ).evaluate(transition)
    assert aiken_root == python_root


@pytest.mark.skipif(
    not Path("vams-vm/target/release/shadow_eval.exe").exists()
    and not Path("vams-vm/target/release/shadow_eval").exists(),
    reason="build the Rust shadow evaluator to enable toolchain integration",
)
def test_real_rust_evaluator_matches_python():
    binary = Path("vams-vm/target/release/shadow_eval.exe")
    if not binary.exists():
        binary = Path("vams-vm/target/release/shadow_eval")
    source = _source_record(7, ZERO_HASH)
    transition = build_source_transition(20260713, source, b"\x11" * 32)
    assert RustShadowEvaluator(binary).evaluate(transition) == PythonShadowEvaluator().evaluate(
        transition
    )
