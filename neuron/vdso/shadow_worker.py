"""Private, non-authoritative VDSO shadow conformance worker.

The worker produces a deterministic stream of commitment-only READ
transitions.  Every transition is evaluated independently by Python, the Rust
``shadow_eval`` binary, and an Aiken function exported to UPLC.  It records
only commitments, evaluator outputs, checkpoints, and audit metadata in
PostgreSQL.  It has no VDSO mutation, settlement, sidecar, or external-write
interface.

This module does not claim that a seven-day shadow run has occurred.  It emits
report material only after the durable database proves every acceptance bound.
It never signs evidence and writes reports only to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .keccak import keccak_256


SHADOW_SCHEMA_VERSION = "1.0.0"
SHADOW_SEED = 20260713
SHADOW_READ_ACTION = 0
SHADOW_READ_DOMAIN = b"VAMS:VDSO:SHADOW:READ:v1"
SHADOW_INPUT_DOMAIN = b"VAMS:VDSO:SHADOW:INPUT:v1"
SHADOW_INITIAL_DOMAIN = b"VAMS:VDSO:SHADOW:INITIAL:v1"
SHADOW_TRANSCRIPT_DOMAIN = b"VAMS:VDSO:SHADOW:TRANSCRIPT:v1"
SHADOW_INPUT_SCHEMA = "vdso-shadow-input-v1"
HASH_LENGTH = 32
CANONICAL_TRANSITION_LENGTH = len(SHADOW_READ_DOMAIN) + 8 + 32 + 32
DEFAULT_CHUNK_SIZE = 1_000
MINIMUM_TRANSITIONS = 100_000
MINIMUM_SECONDS = 7 * 24 * 60 * 60
ZERO_HASH = b"\x00" * HASH_LENGTH
ZERO_SHA256_HEX = "0" * 64
EVIDENCE_FILENAMES = {
    "input": "vdso-shadow-input.jsonl",
    "audit": "vdso-shadow-audit.jsonl",
    "python": "vdso-shadow-python-evaluator.py",
    "rust": "vdso-shadow-rust-evaluator.bin",
    "aiken": "vdso-shadow-aiken-evaluator.cbor",
}
_HEX_32 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_UPLC_BYTES = re.compile(
    r"\(con\s+bytestring\s+#([0-9a-fA-F]{64})\s*\)\Z",
    re.MULTILINE,
)
_ALLOWED_TRANSITION_FIELDS = {
    "action",
    "sequence",
    "expected_previous_root",
    "actual_previous_root",
    "input_commitment",
    "canonical_transition",
    "expected_commitment",
}
_ALLOWED_SOURCE_FIELDS = {
    "schema_version",
    "source_sequence",
    "source_cursor_hash",
    "input_commitment",
    "previous_source_record_sha256",
    "source_record_sha256",
}
_PLAINTEXT_FIELD_NAMES = {
    "content",
    "data",
    "message",
    "payload",
    "plaintext",
    "prompt",
    "secret",
    "sidecar",
}


class ShadowWorkerError(RuntimeError):
    """Base error for fail-closed shadow execution."""


class BackendUnavailable(ShadowWorkerError):
    """A required semantic evaluator is missing or cannot run."""


class TransitionRejected(ShadowWorkerError):
    """A transition violates the commitment-only READ contract."""


class TransitionDivergence(ShadowWorkerError):
    """The Python, Rust, and Aiken evaluators disagree."""


class EvidenceRejected(ShadowWorkerError):
    """Evidence or implementation-root material is incomplete or mismatched."""


class SourcePending(ShadowWorkerError):
    """The append-only source has not published its next complete record yet."""


def _bytes32(name: str, value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) != HASH_LENGTH:
        raise TransitionRejected(f"{name} must be exactly 32 bytes")
    if value == ZERO_HASH:
        raise TransitionRejected(f"{name} must be nonzero")
    return value


def _uint64(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << 64:
        raise TransitionRejected(f"{name} must be an unsigned 64-bit integer")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_rfc3339(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed.astimezone(timezone.utc)


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative_path(repo_root: Path, path: Path) -> str:
    repo = repo_root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(repo)
    except ValueError as exc:
        raise EvidenceRejected(f"artifact must remain inside repository: {resolved}") from exc
    return relative.as_posix()


def _resolve_executable(command: str, name: str) -> str:
    if not isinstance(command, str) or not command or any(
        character in command for character in ("\x00", "\r", "\n")
    ):
        raise BackendUnavailable(f"{name} executable is invalid")
    resolved = shutil.which(command)
    if resolved is None:
        raise BackendUnavailable(f"{name} executable is unavailable")
    return str(Path(resolved).resolve(strict=True))


def _source_root(repo_root: Path, source_paths: Sequence[str]) -> str:
    digest = hashlib.sha256()
    files: list[tuple[str, Path]] = []
    for source_path in source_paths:
        unresolved = repo_root / source_path
        if unresolved.is_symlink():
            raise EvidenceRejected("implementation source path must not be a symlink")
        candidate = unresolved.resolve(strict=True)
        _safe_relative_path(repo_root, candidate)
        if candidate.is_file():
            files.append((source_path.replace("\\", "/"), candidate))
            continue
        for child in candidate.rglob("*"):
            if child.is_symlink():
                raise EvidenceRejected("implementation source must not contain symlinks")
            if not child.is_file() or child.suffix in {".pyc", ".pyo"}:
                continue
            if "__pycache__" in child.parts:
                continue
            files.append((_safe_relative_path(repo_root, child), child))
    if not files:
        raise EvidenceRejected("implementation source root contains no files")
    for relative, path in sorted(files):
        encoded_path = relative.encode("utf-8")
        content = path.read_bytes()
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _git_output(repo_root: Path, arguments: Sequence[str]) -> str:
    git = _resolve_executable("git", "git")
    try:
        result = subprocess.run(
            [git, *arguments],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise EvidenceRejected("git is required to bind the shadow run") from exc
    if result.stderr.strip():
        raise EvidenceRejected("git emitted unexpected diagnostics")
    return result.stdout.strip()


def _commit_sha(repo_root: Path) -> str:
    value = _git_output(repo_root, ["rev-parse", "HEAD"])
    if not _COMMIT_SHA.fullmatch(value):
        raise EvidenceRejected("HEAD is not a full commit SHA")
    return value


def _require_clean_sources(repo_root: Path, paths: Sequence[str]) -> None:
    status = _git_output(
        repo_root,
        ["status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
    )
    if status:
        raise EvidenceRejected(
            "shadow implementation sources must be clean and commit-bound before a run"
        )


def initial_checkpoint_root(seed: int = SHADOW_SEED) -> bytes:
    _uint64("seed", seed)
    root = keccak_256(SHADOW_INITIAL_DOMAIN + seed.to_bytes(8, "big"))
    return _bytes32("initial checkpoint root", root)


def initial_transcript_root(commit_sha: str, seed: int = SHADOW_SEED) -> bytes:
    if not _COMMIT_SHA.fullmatch(commit_sha):
        raise EvidenceRejected("invalid commit SHA for transcript root")
    root = keccak_256(
        SHADOW_TRANSCRIPT_DOMAIN + bytes.fromhex(commit_sha) + seed.to_bytes(8, "big")
    )
    return _bytes32("initial transcript root", root)


def advance_transcript(previous: bytes, sequence: int, result: bytes) -> bytes:
    return keccak_256(
        _bytes32("previous transcript root", previous)
        + _uint64("sequence", sequence).to_bytes(8, "big")
        + _bytes32("evaluator result", result)
    )


@dataclass(frozen=True)
class ShadowTransition:
    """One strict commitment-only, non-mutating shadow READ."""

    action: int
    sequence: int
    expected_previous_root: bytes
    actual_previous_root: bytes
    input_commitment: bytes
    canonical_transition: bytes
    expected_commitment: bytes

    def validate(self) -> None:
        if self.action != SHADOW_READ_ACTION:
            raise TransitionRejected("private shadow supports READ only")
        _uint64("sequence", self.sequence)
        expected = _bytes32("expected_previous_root", self.expected_previous_root)
        actual = _bytes32("actual_previous_root", self.actual_previous_root)
        if expected != actual:
            raise TransitionRejected("shadow checkpoint root mismatch")
        input_commitment = _bytes32("input_commitment", self.input_commitment)
        expected_commitment = _bytes32(
            "expected_commitment", self.expected_commitment
        )
        if (
            not isinstance(self.canonical_transition, bytes)
            or len(self.canonical_transition) != CANONICAL_TRANSITION_LENGTH
        ):
            raise TransitionRejected("malformed canonical shadow transition")
        expected_preimage = (
            SHADOW_READ_DOMAIN
            + self.sequence.to_bytes(8, "big")
            + actual
            + input_commitment
        )
        if self.canonical_transition != expected_preimage:
            raise TransitionRejected("canonical shadow transition binding mismatch")
        if keccak_256(self.canonical_transition) != expected_commitment:
            raise TransitionRejected("shadow transition commitment mismatch")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ShadowTransition":
        keys = set(value)
        if keys & _PLAINTEXT_FIELD_NAMES:
            raise TransitionRejected("plaintext-like payload field is prohibited")
        if keys != _ALLOWED_TRANSITION_FIELDS:
            raise TransitionRejected("shadow transition has unsupported fields")
        try:
            transition = cls(
                action=value["action"],
                sequence=value["sequence"],
                expected_previous_root=bytes.fromhex(value["expected_previous_root"]),
                actual_previous_root=bytes.fromhex(value["actual_previous_root"]),
                input_commitment=bytes.fromhex(value["input_commitment"]),
                canonical_transition=bytes.fromhex(value["canonical_transition"]),
                expected_commitment=bytes.fromhex(value["expected_commitment"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TransitionRejected("shadow transition must contain hex commitments") from exc
        transition.validate()
        return transition

    def as_mapping(self) -> dict[str, Any]:
        self.validate()
        return {
            "action": self.action,
            "sequence": self.sequence,
            "expected_previous_root": self.expected_previous_root.hex(),
            "actual_previous_root": self.actual_previous_root.hex(),
            "input_commitment": self.input_commitment.hex(),
            "canonical_transition": self.canonical_transition.hex(),
            "expected_commitment": self.expected_commitment.hex(),
        }


def build_transition(seed: int, sequence: int, previous_root: bytes) -> ShadowTransition:
    """Build a deterministic transition for tests; live runs use source records."""

    _uint64("seed", seed)
    _uint64("sequence", sequence)
    previous = _bytes32("previous_root", previous_root)
    input_commitment = keccak_256(
        SHADOW_INPUT_DOMAIN + seed.to_bytes(8, "big") + sequence.to_bytes(8, "big")
    )
    canonical = (
        SHADOW_READ_DOMAIN
        + sequence.to_bytes(8, "big")
        + previous
        + input_commitment
    )
    transition = ShadowTransition(
        action=SHADOW_READ_ACTION,
        sequence=sequence,
        expected_previous_root=previous,
        actual_previous_root=previous,
        input_commitment=input_commitment,
        canonical_transition=canonical,
        expected_commitment=keccak_256(canonical),
    )
    transition.validate()
    return transition


@dataclass(frozen=True)
class ShadowSourceRecord:
    """One hash-chained commitment-only record mirrored from the baseline."""

    source_sequence: int
    source_cursor_hash: bytes
    input_commitment: bytes
    previous_source_record_sha256: bytes
    source_record_sha256: bytes

    def unsigned_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": SHADOW_SCHEMA_VERSION,
            "source_sequence": self.source_sequence,
            "source_cursor_hash": self.source_cursor_hash.hex(),
            "input_commitment": self.input_commitment.hex(),
            "previous_source_record_sha256": self.previous_source_record_sha256.hex(),
        }

    def validate(self) -> None:
        _uint64("source_sequence", self.source_sequence)
        _bytes32("source_cursor_hash", self.source_cursor_hash)
        _bytes32("input_commitment", self.input_commitment)
        if (
            not isinstance(self.previous_source_record_sha256, bytes)
            or len(self.previous_source_record_sha256) != HASH_LENGTH
        ):
            raise TransitionRejected("previous source record hash must be bytes32")
        _bytes32("source_record_sha256", self.source_record_sha256)
        expected = hashlib.sha256(_canonical_json(self.unsigned_mapping())).digest()
        if expected != self.source_record_sha256:
            raise TransitionRejected("source record SHA-256 mismatch")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ShadowSourceRecord":
        keys = set(value)
        if keys & _PLAINTEXT_FIELD_NAMES:
            raise TransitionRejected("plaintext-like source field is prohibited")
        if keys != _ALLOWED_SOURCE_FIELDS:
            raise TransitionRejected("source record has unsupported fields")
        if value.get("schema_version") != SHADOW_SCHEMA_VERSION:
            raise TransitionRejected("unsupported shadow input schema")
        for field in (
            "source_cursor_hash",
            "input_commitment",
            "previous_source_record_sha256",
            "source_record_sha256",
        ):
            if not isinstance(value.get(field), str) or not _HEX_32.fullmatch(
                value[field]
            ):
                raise TransitionRejected(
                    "source commitments must use lowercase 32-byte hex"
                )
        try:
            record = cls(
                source_sequence=value["source_sequence"],
                source_cursor_hash=bytes.fromhex(value["source_cursor_hash"]),
                input_commitment=bytes.fromhex(value["input_commitment"]),
                previous_source_record_sha256=bytes.fromhex(
                    value["previous_source_record_sha256"]
                ),
                source_record_sha256=bytes.fromhex(value["source_record_sha256"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TransitionRejected("source record must contain hex commitments") from exc
        record.validate()
        return record

    @classmethod
    def create(
        cls,
        sequence: int,
        cursor_hash: bytes,
        input_commitment: bytes,
        previous_record_sha256: bytes,
    ) -> "ShadowSourceRecord":
        provisional = cls(
            source_sequence=sequence,
            source_cursor_hash=cursor_hash,
            input_commitment=input_commitment,
            previous_source_record_sha256=previous_record_sha256,
            source_record_sha256=b"\x01" * 32,
        )
        record = cls(
            source_sequence=sequence,
            source_cursor_hash=cursor_hash,
            input_commitment=input_commitment,
            previous_source_record_sha256=previous_record_sha256,
            source_record_sha256=hashlib.sha256(
                _canonical_json(provisional.unsigned_mapping())
            ).digest(),
        )
        record.validate()
        return record

    def as_mapping(self) -> dict[str, Any]:
        self.validate()
        return {
            **self.unsigned_mapping(),
            "source_record_sha256": self.source_record_sha256.hex(),
        }


def build_source_transition(
    seed: int,
    source: ShadowSourceRecord,
    previous_root: bytes,
) -> ShadowTransition:
    """Bind a validated real source commitment to the canonical READ preimage."""

    _uint64("seed", seed)
    source.validate()
    previous = _bytes32("previous_root", previous_root)
    canonical = (
        SHADOW_READ_DOMAIN
        + source.source_sequence.to_bytes(8, "big")
        + previous
        + source.input_commitment
    )
    transition = ShadowTransition(
        action=SHADOW_READ_ACTION,
        sequence=source.source_sequence,
        expected_previous_root=previous,
        actual_previous_root=previous,
        input_commitment=source.input_commitment,
        canonical_transition=canonical,
        expected_commitment=keccak_256(canonical),
    )
    transition.validate()
    return transition


class AppendOnlyJsonlSource:
    """Read and verify a strict hash-chained append-only baseline mirror."""

    def __init__(self, path: Path, *, maximum_line_bytes: int = 4096) -> None:
        if path.is_symlink():
            raise EvidenceRejected("shadow input JSONL must not be a symlink")
        self.path = path.resolve(strict=True)
        if not self.path.is_file():
            raise EvidenceRejected("shadow input JSONL is not a file")
        self.maximum_line_bytes = maximum_line_bytes
        self._stream = None
        self._next_sequence = 0
        self._previous_hash = ZERO_HASH

    def _parse_line(self, raw: bytes) -> ShadowSourceRecord:
        if len(raw) > self.maximum_line_bytes:
            raise TransitionRejected("shadow input record exceeds the size limit")
        if not raw.endswith(b"\n"):
            raise SourcePending("shadow input record is not yet newline-terminated")
        if b"\r" in raw:
            raise TransitionRejected("shadow input must use LF line endings")
        payload = raw[:-1]
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransitionRejected("shadow input record is malformed JSON") from exc
        if not isinstance(value, dict):
            raise TransitionRejected("shadow input record must be a JSON object")
        if payload != _canonical_json(value):
            raise TransitionRejected("shadow input record is not canonical JSON")
        return ShadowSourceRecord.from_mapping(value)

    def resume(self, next_sequence: int, previous_hash: bytes) -> None:
        _uint64("next source sequence", next_sequence)
        if not isinstance(previous_hash, bytes) or len(previous_hash) != 32:
            raise TransitionRejected("source checkpoint hash must be bytes32")
        if self._stream is not None:
            self._stream.close()
        self._stream = self.path.open("rb")
        expected_previous = ZERO_HASH
        for sequence in range(next_sequence):
            raw = self._stream.readline(self.maximum_line_bytes + 1)
            if not raw:
                raise EvidenceRejected("shadow input is shorter than its durable checkpoint")
            record = self._parse_line(raw)
            if (
                record.source_sequence != sequence
                or record.previous_source_record_sha256 != expected_previous
            ):
                raise EvidenceRejected("shadow input history is reordered or hash-chain invalid")
            expected_previous = record.source_record_sha256
        if expected_previous != previous_hash:
            raise EvidenceRejected("shadow input root does not match durable checkpoint")
        self._next_sequence = next_sequence
        self._previous_hash = previous_hash

    def next_record(self) -> ShadowSourceRecord:
        if self._stream is None:
            raise EvidenceRejected("shadow input source has not been resumed")
        offset = self._stream.tell()
        raw = self._stream.readline(self.maximum_line_bytes + 1)
        if not raw:
            raise SourcePending("no new shadow input record")
        try:
            record = self._parse_line(raw)
        except SourcePending:
            self._stream.seek(offset)
            raise
        if record.source_sequence != self._next_sequence:
            raise TransitionRejected("shadow input sequence gap, duplicate, or reordering")
        if record.previous_source_record_sha256 != self._previous_hash:
            raise TransitionRejected("shadow input record-chain mismatch")
        self._next_sequence += 1
        self._previous_hash = record.source_record_sha256
        return record

    def require_exact_eof(self, expected_count: int, expected_root: bytes) -> None:
        """Revalidate the final artifact and require no unconsumed trailing record."""

        self.resume(expected_count, expected_root)
        if self._stream is None:
            raise EvidenceRejected("shadow input source did not resume")
        trailing = self._stream.readline(self.maximum_line_bytes + 1)
        if trailing:
            if not trailing.endswith(b"\n"):
                raise EvidenceRejected("shadow input ends with a partial record")
            raise EvidenceRejected("shadow input contains records not included in the report")


class ShadowEvaluator(Protocol):
    name: str

    def evaluate(self, transition: ShadowTransition) -> bytes: ...


class PythonShadowEvaluator:
    """Local Python implementation of the canonical READ evaluator."""

    name = "python"

    def evaluate(self, transition: ShadowTransition) -> bytes:
        transition.validate()
        return keccak_256(transition.canonical_transition)


class RustShadowEvaluator:
    """Invoke the capability-free Rust evaluator for one transition."""

    name = "rust"

    def __init__(self, binary: Path, *, timeout_seconds: float = 10.0) -> None:
        self.binary = binary.resolve(strict=True)
        self.timeout_seconds = timeout_seconds
        if not self.binary.is_file():
            raise BackendUnavailable("Rust shadow evaluator is not a file")

    def evaluate(self, transition: ShadowTransition) -> bytes:
        transition.validate()
        arguments = [
            str(self.binary),
            str(transition.action),
            str(transition.sequence),
            transition.expected_previous_root.hex(),
            transition.actual_previous_root.hex(),
            transition.input_commitment.hex(),
            transition.canonical_transition.hex(),
            transition.expected_commitment.hex(),
        ]
        try:
            result = subprocess.run(
                arguments,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            raise BackendUnavailable("Rust shadow evaluator unavailable") from exc
        output = result.stdout.strip()
        if result.returncode != 0 or result.stderr.strip() or not _HEX_32.fullmatch(output):
            raise TransitionRejected("Rust shadow evaluator rejected transition")
        return bytes.fromhex(output)


class AikenShadowEvaluator:
    """Evaluate the exported conformance-only Aiken function through UPLC."""

    name = "aiken"

    def __init__(
        self,
        program_cbor: Path,
        *,
        aiken_cli: str = "aiken",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.program_cbor = program_cbor.resolve(strict=True)
        self.aiken_cli = _resolve_executable(aiken_cli, "Aiken")
        self.timeout_seconds = timeout_seconds
        if not self.program_cbor.is_file():
            raise BackendUnavailable("Aiken shadow evaluator artifact is not a file")

    @staticmethod
    def _integer(value: int) -> str:
        # `aiken export` wraps typed parameters in PlutusData decoders.
        return f"(con data (I {value}))"

    @staticmethod
    def _byte_string(value: bytes) -> str:
        return f"(con data (B #{value.hex()}))"

    def evaluate(self, transition: ShadowTransition) -> bytes:
        transition.validate()
        arguments = [
            self.aiken_cli,
            "uplc",
            "eval",
            "--cbor",
            str(self.program_cbor),
            self._integer(transition.action),
            self._integer(transition.sequence),
            self._byte_string(transition.expected_previous_root),
            self._byte_string(transition.actual_previous_root),
            self._byte_string(transition.input_commitment),
            self._byte_string(transition.canonical_transition),
            self._byte_string(transition.expected_commitment),
        ]
        try:
            result = subprocess.run(
                arguments,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            raise BackendUnavailable("Aiken UPLC evaluator unavailable") from exc
        if result.returncode != 0 or result.stderr.strip():
            raise TransitionRejected("Aiken UPLC evaluator rejected transition")
        try:
            parsed = json.loads(result.stdout)
            encoded = parsed["result"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise TransitionRejected("Aiken UPLC evaluator emitted malformed output") from exc
        match = _UPLC_BYTES.fullmatch(encoded)
        if match is None:
            raise TransitionRejected("Aiken UPLC evaluator returned a non-commitment value")
        commitment = bytes.fromhex(match.group(1))
        if commitment == ZERO_HASH:
            raise TransitionRejected("Aiken UPLC evaluator returned the rejection sentinel")
        return commitment


@dataclass(frozen=True)
class ImplementationRoot:
    source_paths: tuple[str, ...]
    source_root_sha256: str
    artifact_path: str
    artifact_sha256: str

    def as_mapping(self) -> dict[str, Any]:
        return {
            "source_paths": list(self.source_paths),
            "source_root_sha256": self.source_root_sha256,
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ImplementationRoot":
        source_paths = tuple(value["source_paths"])
        root = cls(
            source_paths=source_paths,
            source_root_sha256=value["source_root_sha256"],
            artifact_path=value["artifact_path"],
            artifact_sha256=value["artifact_sha256"],
        )
        for field in (root.source_root_sha256, root.artifact_sha256):
            if not isinstance(field, str) or not _HEX_32.fullmatch(field):
                raise EvidenceRejected("invalid implementation SHA-256")
        return root


@dataclass(frozen=True)
class ShadowRunConfig:
    commit_sha: str
    seed: int
    chunk_size: int
    configured_max_gap_seconds: int
    input_source_schema: str
    input_jsonl_path: str
    implementation_roots: Mapping[str, ImplementationRoot]

    def __post_init__(self) -> None:
        if not _COMMIT_SHA.fullmatch(self.commit_sha):
            raise EvidenceRejected("invalid shadow commit SHA")
        _uint64("seed", self.seed)
        if self.seed != SHADOW_SEED:
            raise EvidenceRejected(f"shadow seed must equal {SHADOW_SEED}")
        if self.chunk_size != DEFAULT_CHUNK_SIZE:
            raise EvidenceRejected(f"shadow chunk size must equal {DEFAULT_CHUNK_SIZE}")
        if not isinstance(self.configured_max_gap_seconds, int) or not 1 <= self.configured_max_gap_seconds <= 3600:
            raise EvidenceRejected("configured maximum gap must be between 1 and 3600 seconds")
        if self.input_source_schema != SHADOW_INPUT_SCHEMA:
            raise EvidenceRejected("unsupported shadow input source schema")
        if (
            not isinstance(self.input_jsonl_path, str)
            or not self.input_jsonl_path
            or Path(self.input_jsonl_path).is_absolute()
            or ".." in Path(self.input_jsonl_path).parts
        ):
            raise EvidenceRejected("shadow input path must be a safe repository-relative path")
        if set(self.implementation_roots) != {"python", "rust", "aiken"}:
            raise EvidenceRejected("Python, Rust, and Aiken implementation roots are required")

    @property
    def run_id(self) -> str:
        return hashlib.sha256(b"VAMS:VDSO:SHADOW:RUN:v1" + _canonical_json(self.as_mapping())).hexdigest()

    def as_mapping(self) -> dict[str, Any]:
        return {
            "commit_sha": self.commit_sha,
            "seed": self.seed,
            "chunk_size": self.chunk_size,
            "configured_max_gap_seconds": self.configured_max_gap_seconds,
            "input_source_schema": self.input_source_schema,
            "input_jsonl_path": self.input_jsonl_path,
            "implementation_roots": {
                name: self.implementation_roots[name].as_mapping()
                for name in ("python", "rust", "aiken")
            },
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ShadowRunConfig":
        roots = {
            name: ImplementationRoot.from_mapping(value["implementation_roots"][name])
            for name in ("python", "rust", "aiken")
        }
        return cls(
            commit_sha=value["commit_sha"],
            seed=value["seed"],
            chunk_size=value["chunk_size"],
            configured_max_gap_seconds=value["configured_max_gap_seconds"],
            input_source_schema=value["input_source_schema"],
            input_jsonl_path=value["input_jsonl_path"],
            implementation_roots=roots,
        )

    @classmethod
    def from_repository(
        cls,
        repo_root: Path,
        rust_artifact: Path,
        aiken_artifact: Path,
        input_jsonl: Path,
        *,
        configured_max_gap_seconds: int,
    ) -> "ShadowRunConfig":
        repo = repo_root.resolve(strict=True)
        source_paths = {
            "python": ("neuron/vdso",),
            "rust": ("vams-vm/crates",),
            "aiken": ("cardano/lib/vams/vdso.ak",),
        }
        _require_clean_sources(
            repo,
            [path for values in source_paths.values() for path in values],
        )
        artifacts = {
            "python": Path(__file__).resolve(strict=True),
            "rust": rust_artifact.resolve(strict=True),
            "aiken": aiken_artifact.resolve(strict=True),
        }
        for artifact in artifacts.values():
            if artifact.is_symlink():
                raise EvidenceRejected("shadow evaluator artifact must not be a symlink")
            _safe_relative_path(repo, artifact)
        source_input = input_jsonl.resolve(strict=True)
        if source_input.name != EVIDENCE_FILENAMES["input"]:
            raise EvidenceRejected(
                f"shadow input must be named {EVIDENCE_FILENAMES['input']}"
            )
        roots = {
            name: ImplementationRoot(
                source_paths=source_paths[name],
                source_root_sha256=_source_root(repo, source_paths[name]),
                artifact_path=EVIDENCE_FILENAMES[name],
                artifact_sha256=_sha256_file(artifacts[name]),
            )
            for name in ("python", "rust", "aiken")
        }
        return cls(
            commit_sha=_commit_sha(repo),
            seed=SHADOW_SEED,
            chunk_size=DEFAULT_CHUNK_SIZE,
            configured_max_gap_seconds=configured_max_gap_seconds,
            input_source_schema=SHADOW_INPUT_SCHEMA,
            input_jsonl_path=EVIDENCE_FILENAMES["input"],
            implementation_roots=roots,
        )


@dataclass(frozen=True)
class TransitionAudit:
    source_record: ShadowSourceRecord
    transition: ShadowTransition
    python_root: bytes
    rust_root: bytes
    aiken_root: bytes
    recorded_at: datetime

    def validate(self) -> None:
        self.source_record.validate()
        self.transition.validate()
        if (
            self.source_record.source_sequence != self.transition.sequence
            or self.source_record.input_commitment != self.transition.input_commitment
        ):
            raise TransitionRejected("source record is not bound to transition")
        for name, value in (
            ("python_root", self.python_root),
            ("rust_root", self.rust_root),
            ("aiken_root", self.aiken_root),
        ):
            _bytes32(name, value)
        if not self.python_root == self.rust_root == self.aiken_root:
            raise TransitionDivergence("backend transition roots diverged")
        if self.python_root != self.transition.expected_commitment:
            raise TransitionDivergence("backend root differs from expected commitment")
        if self.recorded_at.tzinfo is None:
            raise TransitionRejected("audit timestamp must be timezone-aware")


@dataclass(frozen=True)
class RunState:
    run_id: str
    config: ShadowRunConfig
    started_at: datetime
    last_transition_at: datetime | None
    next_sequence: int
    checkpoint_root: bytes
    source_cursor_hash: bytes
    source_chain_root: bytes
    transcript_roots: Mapping[str, bytes]
    backend_eval_count: Mapping[str, int]
    chunk_count: int
    max_transition_gap_seconds: float
    restart_count: int
    replay_verification_count: int
    stop_conditions: tuple[str, ...]

    @property
    def transition_count(self) -> int:
        return self.next_sequence

    @property
    def completed_at(self) -> datetime:
        return self.last_transition_at or self.started_at

    @property
    def observed_seconds(self) -> int:
        return max(0, int((self.completed_at - self.started_at).total_seconds()))


class ShadowStore(Protocol):
    def initialize_run(self, config: ShadowRunConfig) -> RunState: ...

    def load_state(self, run_id: str) -> RunState: ...

    def load_last_audit(self, run_id: str) -> TransitionAudit | None: ...

    def record_transition(self, run_id: str, audit: TransitionAudit) -> RunState: ...

    def record_replay_verified(self, run_id: str) -> RunState: ...

    def record_stop(self, run_id: str, code: str) -> None: ...

    def export_evidence_records(self, run_id: str) -> Sequence[Mapping[str, Any]]: ...


class ShadowWorker:
    """Coordinate three independent semantic evaluators and durable storage."""

    def __init__(
        self,
        config: ShadowRunConfig,
        store: ShadowStore,
        evaluators: Sequence[ShadowEvaluator],
        source: AppendOnlyJsonlSource,
    ) -> None:
        self.config = config
        self.store = store
        self.evaluators = {evaluator.name: evaluator for evaluator in evaluators}
        self.source = source
        if set(self.evaluators) != {"python", "rust", "aiken"}:
            raise BackendUnavailable("Python, Rust, and Aiken evaluators are mandatory")
        self._initialized = False

    def _evaluate(self, transition: ShadowTransition) -> dict[str, bytes]:
        transition.validate()
        results: dict[str, bytes] = {}
        for name in ("python", "rust", "aiken"):
            try:
                result = self.evaluators[name].evaluate(transition)
            except BackendUnavailable:
                self.store.record_stop(self.config.run_id, "backend_unavailable")
                raise
            except Exception as exc:
                self.store.record_stop(self.config.run_id, "transition_divergence")
                raise TransitionDivergence(f"{name} evaluator rejected transition") from exc
            results[name] = _bytes32(f"{name} evaluator root", result)
        if len(set(results.values())) != 1 or results["python"] != transition.expected_commitment:
            self.store.record_stop(self.config.run_id, "transition_divergence")
            raise TransitionDivergence("Python, Rust, and Aiken results differ")
        return results

    def initialize(self) -> RunState:
        state = self.store.initialize_run(self.config)
        if state.stop_conditions:
            raise ShadowWorkerError("shadow run is permanently stopped")
        self.source.resume(state.next_sequence, state.source_chain_root)
        last_audit = self.store.load_last_audit(self.config.run_id)
        if last_audit is not None:
            results = self._evaluate(last_audit.transition)
            expected = {
                "python": last_audit.python_root,
                "rust": last_audit.rust_root,
                "aiken": last_audit.aiken_root,
            }
            if results != expected:
                self.store.record_stop(self.config.run_id, "replay_mismatch")
                raise TransitionDivergence("restart replay does not match durable audit")
            state = self.store.record_replay_verified(self.config.run_id)
        self._initialized = True
        return state

    def run_once(self, *, recorded_at: datetime | None = None) -> RunState:
        if not self._initialized:
            self.initialize()
        state = self.store.load_state(self.config.run_id)
        if state.stop_conditions:
            raise ShadowWorkerError("shadow run is permanently stopped")
        try:
            source_record = self.source.next_record()
        except (TransitionRejected, EvidenceRejected) as exc:
            code = (
                "plaintext_payload"
                if "plaintext-like" in str(exc).lower()
                else "source_chain_mismatch"
            )
            self.store.record_stop(self.config.run_id, code)
            raise
        if (
            source_record.source_sequence != state.next_sequence
            or source_record.previous_source_record_sha256 != state.source_chain_root
        ):
            self.store.record_stop(self.config.run_id, "source_chain_mismatch")
            raise TransitionRejected("source record does not match durable checkpoint")
        try:
            transition = build_source_transition(
                self.config.seed, source_record, state.checkpoint_root
            )
        except TransitionRejected:
            self.store.record_stop(self.config.run_id, "transition_divergence")
            raise
        results = self._evaluate(transition)
        audit = TransitionAudit(
            source_record=source_record,
            transition=transition,
            python_root=results["python"],
            rust_root=results["rust"],
            aiken_root=results["aiken"],
            recorded_at=recorded_at or _utc_now(),
        )
        audit.validate()
        try:
            return self.store.record_transition(self.config.run_id, audit)
        except TransitionRejected as exc:
            message = str(exc).lower()
            code = (
                "continuity_gap"
                if "continuity" in message or "timestamp" in message
                else "transition_divergence"
            )
            self.store.record_stop(self.config.run_id, code)
            raise


def is_report_eligible(state: RunState) -> bool:
    return (
        not state.stop_conditions
        and state.transition_count >= MINIMUM_TRANSITIONS
        and state.observed_seconds >= MINIMUM_SECONDS
        and state.chunk_count >= MINIMUM_TRANSITIONS // DEFAULT_CHUNK_SIZE
        and state.transition_count % state.config.chunk_size == 0
        and state.max_transition_gap_seconds
        <= state.config.configured_max_gap_seconds
        and state.restart_count >= 1
        and state.replay_verification_count >= 1
        and all(
            state.backend_eval_count.get(name) == state.transition_count
            for name in ("python", "rust", "aiken")
        )
        and len(set(state.transcript_roots.values())) == 1
        and state.source_cursor_hash != ZERO_HASH
        and state.source_chain_root != ZERO_HASH
    )


def progress_material(state: RunState) -> dict[str, Any]:
    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "record_type": "progress",
        "eligible_for_report": is_report_eligible(state),
        "run_id": state.run_id,
        "commit_sha": state.config.commit_sha,
        "transition_count": state.transition_count,
        "observed_seconds": state.observed_seconds,
        "chunk_count": state.chunk_count,
        "max_transition_gap_seconds": state.max_transition_gap_seconds,
        "restart_count": state.restart_count,
        "replay_verification_count": state.replay_verification_count,
        "backend_eval_count": dict(state.backend_eval_count),
        "source_record_count": state.transition_count,
        "source_final_cursor_hash": state.source_cursor_hash.hex(),
        "source_chain_root_sha256": state.source_chain_root.hex(),
        "stop_conditions": list(state.stop_conditions),
    }


def _record_hash(record: Mapping[str, Any]) -> str:
    without_hash = dict(record)
    without_hash.pop("record_sha256", None)
    return hashlib.sha256(_canonical_json(without_hash)).hexdigest()


def chain_evidence_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    chained: list[dict[str, Any]] = []
    previous = ZERO_SHA256_HEX
    for source in records:
        record = dict(source)
        record["previous_record_sha256"] = previous
        record["record_sha256"] = _record_hash(record)
        previous = record["record_sha256"]
        chained.append(record)
    return chained


def serialize_evidence_records(records: Sequence[Mapping[str, Any]]) -> bytes:
    chained = chain_evidence_records(records)
    return b"".join(_canonical_json(record) + b"\n" for record in chained)


def verify_audit_jsonl(
    path: Path,
    expected_run_id: str,
    *,
    expected_header: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    previous = ZERO_SHA256_HEX
    header_seen = False
    summary: dict[str, Any] | None = None
    expected_chunk = 0
    header: dict[str, Any] | None = None
    with path.open("rb") as stream:
        for raw_line in stream:
            if not raw_line.endswith(b"\n") or not raw_line.strip():
                raise EvidenceRejected("audit JSONL must use non-empty newline-terminated records")
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise EvidenceRejected("audit JSONL contains malformed JSON") from exc
            if not isinstance(record, dict) or record.get("run_id") != expected_run_id:
                raise EvidenceRejected("audit JSONL run binding mismatch")
            if record.get("previous_record_sha256") != previous:
                raise EvidenceRejected("audit JSONL hash chain is broken")
            if record.get("record_sha256") != _record_hash(record):
                raise EvidenceRejected("audit JSONL record hash mismatch")
            previous = record["record_sha256"]
            record_type = record.get("record_type")
            if not header_seen:
                if record_type != "run":
                    raise EvidenceRejected("audit JSONL must start with a run header")
                header_seen = True
                header = record
            elif record_type == "chunk":
                if summary is not None or record.get("chunk_index") != expected_chunk:
                    raise EvidenceRejected("audit JSONL chunks are not contiguous")
                expected_chunk += 1
            elif record_type == "summary":
                if summary is not None:
                    raise EvidenceRejected("audit JSONL contains multiple summaries")
                summary = record
            else:
                raise EvidenceRejected("audit JSONL record ordering is invalid")
    if not header_seen or summary is None or summary.get("chunk_count") != expected_chunk:
        raise EvidenceRejected("audit JSONL is incomplete")
    if expected_header is not None:
        if header is None:
            raise EvidenceRejected("audit JSONL run header is missing")
        for key, expected in expected_header.items():
            if header.get(key) != expected:
                raise EvidenceRejected(f"audit JSONL header mismatch: {key}")
    return summary


def build_report_material(
    state: RunState,
    repo_root: Path,
    audit_jsonl: Path,
) -> dict[str, Any]:
    if not is_report_eligible(state):
        raise EvidenceRejected("durable shadow run has not met every report gate")
    if audit_jsonl.is_symlink():
        raise EvidenceRejected("shadow audit evidence must not be a symlink")
    audit_path = audit_jsonl.resolve(strict=True)
    _safe_relative_path(repo_root, audit_path)
    if audit_path.name != EVIDENCE_FILENAMES["audit"]:
        raise EvidenceRejected(
            f"shadow audit must be named {EVIDENCE_FILENAMES['audit']}"
        )
    evidence_directory = audit_path.parent
    relative_audit_path = EVIDENCE_FILENAMES["audit"]
    input_candidate = evidence_directory / state.config.input_jsonl_path
    if input_candidate.is_symlink():
        raise EvidenceRejected("shadow input evidence must not be a symlink")
    input_path = input_candidate.resolve(strict=True)
    source = AppendOnlyJsonlSource(input_path)
    source.require_exact_eof(state.transition_count, state.source_chain_root)
    summary = verify_audit_jsonl(
        audit_path,
        state.run_id,
        expected_header={
            "commit_sha": state.config.commit_sha,
            "seed": state.config.seed,
            "chunk_size": state.config.chunk_size,
            "configured_max_gap_seconds": state.config.configured_max_gap_seconds,
            "initial_root": initial_checkpoint_root(state.config.seed).hex(),
            "input_source_schema": state.config.input_source_schema,
            "input_jsonl_path": state.config.input_jsonl_path,
            "implementation_roots": {
                name: state.config.implementation_roots[name].as_mapping()
                for name in ("python", "rust", "aiken")
            },
        },
    )
    if summary.get("transition_count") != state.transition_count:
        raise EvidenceRejected("audit summary transition count mismatch")
    if summary.get("final_root") != state.checkpoint_root.hex():
        raise EvidenceRejected("audit summary final root mismatch")
    if (
        summary.get("source_record_count") != state.transition_count
        or summary.get("source_final_cursor_hash") != state.source_cursor_hash.hex()
        or summary.get("source_chain_root_sha256") != state.source_chain_root.hex()
    ):
        raise EvidenceRejected("audit summary source checkpoint mismatch")
    input_sha256 = _sha256_file(input_path)
    implementation_artifacts: list[dict[str, str]] = []
    for name in ("python", "rust", "aiken"):
        implementation = state.config.implementation_roots[name]
        artifact_candidate = evidence_directory / implementation.artifact_path
        if artifact_candidate.is_symlink():
            raise EvidenceRejected(f"{name} evidence artifact must not be a symlink")
        artifact = artifact_candidate.resolve(strict=True)
        if artifact.parent != evidence_directory or _sha256_file(artifact) != implementation.artifact_sha256:
            raise EvidenceRejected(f"{name} evidence artifact hash mismatch")
        implementation_artifacts.append(
            {
                "path": implementation.artifact_path,
                "sha256": implementation.artifact_sha256,
            }
        )
    report = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "commit_sha": state.config.commit_sha,
        "seed": state.config.seed,
        "started_at": _rfc3339(state.started_at),
        "completed_at": _rfc3339(state.completed_at),
        "consecutive_days": state.observed_seconds // (24 * 60 * 60),
        "observed_seconds": state.observed_seconds,
        "transition_count": state.transition_count,
        "chunk_count": state.chunk_count,
        "configured_max_gap_seconds": state.config.configured_max_gap_seconds,
        "max_transition_gap_seconds": state.max_transition_gap_seconds,
        "continuity_passed": True,
        "restart_count": state.restart_count,
        "replay_verification_count": state.replay_verification_count,
        "backend_eval_count": dict(state.backend_eval_count),
        "source_record_count": state.transition_count,
        "source_final_cursor_hash": state.source_cursor_hash.hex(),
        "source_chain_root_sha256": state.source_chain_root.hex(),
        "input_jsonl_path": state.config.input_jsonl_path,
        "input_jsonl_sha256": input_sha256,
        "audit_jsonl_path": relative_audit_path,
        "audit_jsonl_sha256": _sha256_file(audit_path),
        "audit_chain_root_sha256": summary["record_sha256"],
        "public_vdso_mode": "off",
        "worker_mode": "shadow",
        "authoritative_enabled": False,
        "read_only": True,
        "value_bearing_domains_enabled": False,
        "divergence_count": 0,
        "external_write_count": 0,
        "plaintext_payload_count": 0,
        "restart_recovery_passed": True,
        "replay_determinism_passed": True,
        "privacy_result": "pass",
        "stop_conditions_triggered": False,
        "stop_conditions": {
            "transition_divergence": False,
            "external_write": False,
            "plaintext_payload": False,
            "restart_failure": False,
            "replay_mismatch": False,
            "privacy_failure": False,
            "public_mode_enabled": False,
            "authoritative_enabled": False,
            "value_bearing_enabled": False,
            "continuity_gap": False,
            "backend_unavailable": False,
            "source_chain_mismatch": False,
        },
        "implementation_roots": {
            name: state.config.implementation_roots[name].as_mapping()
            for name in ("python", "rust", "aiken")
        },
        "evidence_artifacts": [
            {
                "path": state.config.input_jsonl_path,
                "sha256": input_sha256,
            },
            {
                "path": relative_audit_path,
                "sha256": _sha256_file(audit_path),
            },
            *implementation_artifacts,
        ],
    }
    return report


def prepare_aiken_evaluator(
    cardano_project: Path,
    output_path: Path,
    *,
    aiken_cli: str = "aiken",
    force: bool = False,
) -> dict[str, str]:
    project = cardano_project.resolve(strict=True)
    output = output_path.resolve()
    aiken_executable = _resolve_executable(aiken_cli, "Aiken")
    if output.exists() and not force:
        raise EvidenceRejected("Aiken evaluator artifact already exists; use --force")
    try:
        result = subprocess.run(
            [
                aiken_executable,
                "export",
                "--module",
                "vams/vdso",
                "--name",
                "shadow_read_commitment",
                str(project),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            shell=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        raise BackendUnavailable("Aiken export is unavailable") from exc
    if result.returncode != 0:
        raise BackendUnavailable("Aiken failed to export shadow_read_commitment")
    try:
        exported = json.loads(result.stdout)
        if exported["name"] != "vams/vdso.shadow_read_commitment":
            raise KeyError("name")
        compiled_hex = exported["compiledCode"]
        compiled = bytes.fromhex(compiled_hex)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise EvidenceRejected("Aiken export emitted malformed artifact metadata") from exc
    if not compiled:
        raise EvidenceRejected("Aiken exported an empty evaluator")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    # `aiken uplc eval --cbor` expects the exported CBOR as UTF-8 hex, not
    # the decoded binary bytes.  Preserve a final newline for tool portability.
    temporary.write_text(compiled_hex.lower() + "\n", encoding="ascii", newline="\n")
    os.replace(temporary, output)
    return {
        "path": str(output),
        "sha256": _sha256_file(output),
        "aiken_hash": exported["hash"],
    }


def _require_shadow_environment() -> None:
    required = {
        "VAMS_ENV": "testnet",
        "VAMS_NETWORK": "polygon-amoy",
        "VDSO_MODE": "shadow",
        "VDSO_PUBLIC_MODE": "off",
    }
    mismatches = [
        f"{name}={expected}"
        for name, expected in required.items()
        if os.environ.get(name) != expected
    ]
    if mismatches:
        raise ShadowWorkerError(
            "private shadow environment is fail-closed; require " + ", ".join(mismatches)
        )


def _store(dsn: str):
    from .shadow_postgres import PostgresShadowStore

    return PostgresShadowStore(dsn)


def _run_command(arguments: argparse.Namespace) -> int:
    _require_shadow_environment()
    if arguments.interval_seconds <= 0 or arguments.source_poll_seconds <= 0:
        raise ShadowWorkerError("transition and source-poll intervals must be positive")
    config = ShadowRunConfig.from_repository(
        arguments.repo,
        arguments.rust_evaluator,
        arguments.aiken_program,
        arguments.input_jsonl,
        configured_max_gap_seconds=arguments.max_gap_seconds,
    )
    worker = ShadowWorker(
        config,
        _store(arguments.postgres_dsn),
        [
            PythonShadowEvaluator(),
            RustShadowEvaluator(arguments.rust_evaluator),
            AikenShadowEvaluator(arguments.aiken_program, aiken_cli=arguments.aiken_cli),
        ],
        AppendOnlyJsonlSource(arguments.input_jsonl),
    )
    state = worker.initialize()
    print(json.dumps(progress_material(state), sort_keys=True))
    while not is_report_eligible(state):
        started = time.monotonic()
        try:
            state = worker.run_once()
        except SourcePending:
            time.sleep(arguments.source_poll_seconds)
            continue
        if state.transition_count % state.config.chunk_size == 0:
            print(json.dumps(progress_material(state), sort_keys=True), flush=True)
        elapsed = time.monotonic() - started
        time.sleep(max(0.0, arguments.interval_seconds - elapsed))
    print(json.dumps(progress_material(state), sort_keys=True), flush=True)
    return 0


def _export_command(arguments: argparse.Namespace) -> int:
    records = _store(arguments.postgres_dsn).export_evidence_records(arguments.run_id)
    sys.stdout.buffer.write(serialize_evidence_records(records))
    return 0


def _report_command(arguments: argparse.Namespace) -> int:
    store = _store(arguments.postgres_dsn)
    state = store.load_state(arguments.run_id)
    report = build_report_material(state, arguments.repo, arguments.audit_jsonl)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


def _prepare_command(arguments: argparse.Namespace) -> int:
    result = prepare_aiken_evaluator(
        arguments.cardano_project,
        arguments.output,
        aiken_cli=arguments.aiken_cli,
        force=arguments.force,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-aiken", help="export the Aiken UPLC evaluator")
    prepare.add_argument("--cardano-project", type=Path, default=Path("cardano"))
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--aiken-cli", default="aiken")
    prepare.add_argument("--force", action="store_true")
    prepare.set_defaults(handler=_prepare_command)

    run = subparsers.add_parser("run", help="run until every seven-day shadow gate passes")
    run.add_argument("--repo", type=Path, default=Path("."))
    run.add_argument("--postgres-dsn", default=os.environ.get("VDSO_POSTGRES_DSN"))
    run.add_argument("--rust-evaluator", type=Path, required=True)
    run.add_argument("--aiken-program", type=Path, required=True)
    run.add_argument("--input-jsonl", type=Path, required=True)
    run.add_argument("--aiken-cli", default="aiken")
    run.add_argument("--interval-seconds", type=float, default=6.0)
    run.add_argument("--max-gap-seconds", type=int, default=60)
    run.add_argument("--source-poll-seconds", type=float, default=1.0)
    run.set_defaults(handler=_run_command)

    export = subparsers.add_parser("export-evidence", help="stream chained audit JSONL")
    export.add_argument("--postgres-dsn", default=os.environ.get("VDSO_POSTGRES_DSN"))
    export.add_argument("--run-id", required=True)
    export.set_defaults(handler=_export_command)

    report = subparsers.add_parser("report", help="emit unsigned report JSON to stdout")
    report.add_argument("--repo", type=Path, default=Path("."))
    report.add_argument("--postgres-dsn", default=os.environ.get("VDSO_POSTGRES_DSN"))
    report.add_argument("--run-id", required=True)
    report.add_argument("--audit-jsonl", type=Path, required=True)
    report.set_defaults(handler=_report_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    if hasattr(arguments, "postgres_dsn") and not arguments.postgres_dsn:
        raise ShadowWorkerError("VDSO_POSTGRES_DSN is required")
    return arguments.handler(arguments)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ShadowWorkerError as exc:
        print(f"shadow worker rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
