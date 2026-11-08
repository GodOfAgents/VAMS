#!/usr/bin/env python3
"""Test-only bounded F05.2a simulator runner with immutable byte snapshots."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = "f05-2a-tx-sim-run-result-r3"
MAX_TX_BYTES = 1_048_576
MAX_VECTOR_BYTES = 4_194_304
MAX_TOTAL_BYTES = MAX_TX_BYTES + 2 * MAX_VECTOR_BYTES
MAX_OUTPUT_BYTES = 262_144
DEFAULT_TIMEOUT_SECONDS = 90.0
MIN_TIMEOUT_SECONDS = 0.05
MAX_TIMEOUT_SECONDS = 90.0
TERM_GRACE_SECONDS = 0.25
GROUP_REAP_SECONDS = 0.75


class SnapshotError(Exception):
    """Input could not be snapshotted exactly and safely."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _registry_helpers() -> Any:
    path = ROOT / "scripts/remediation/f05_2a_tx_sim_registry.py"
    spec = importlib.util.spec_from_file_location("f05_2a_tx_sim_registry_r3", path)
    if spec is None or spec.loader is None:
        raise SnapshotError("result_classifier_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _extract_target_mint_binding(helper: Any, tx_cbor: bytes,
                                 expected_policy_id: str) -> dict[str, Any]:
    """Independently bind the transaction mint purpose to its V3 witness hash."""
    if type(expected_policy_id) is not str or re.fullmatch(r"[0-9a-f]{56}", expected_policy_id) is None:
        raise SnapshotError("invalid_expected_policy_id")
    try:
        tx = helper.roundtrip(tx_cbor)
        if type(tx) is not list or len(tx) != 4:
            raise SnapshotError("typed_transaction_shape_invalid")
        if not isinstance(tx[0], helper.Map) or not isinstance(tx[1], helper.Map):
            raise SnapshotError("typed_transaction_body_or_witness_invalid")
        mint = helper.map_get(tx[0], 9)
        if not isinstance(mint, helper.Map) or len(mint.pairs) != 1:
            raise SnapshotError("target_mint_policy_cardinality_invalid")
        policy, assets = mint.pairs[0]
        if type(policy) is not bytes or len(policy) != 28 or not isinstance(assets, helper.Map):
            raise SnapshotError("target_mint_policy_encoding_invalid")
        policy_id = policy.hex()
        if policy_id != expected_policy_id:
            raise SnapshotError("target_policy_binding_mismatch")
        witness_set = helper.map_get(tx[1], 7)
        if (not isinstance(witness_set, helper.Tag) or witness_set.number != 258 or
                type(witness_set.value) is not list or len(witness_set.value) != 1 or
                type(witness_set.value[0]) is not bytes):
            raise SnapshotError("target_v3_witness_shape_invalid")
        script_hash = hashlib.blake2b(b"\x03" + witness_set.value[0], digest_size=28).hexdigest()
        if script_hash != expected_policy_id:
            raise SnapshotError("target_script_hash_mismatch")
        return {"policy_ids": [policy_id], "script_hash": script_hash}
    except SnapshotError:
        raise
    except Exception as exc:
        raise SnapshotError("target_mint_binding_invalid") from exc


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino, left.st_mode, left.st_size,
            left.st_mtime_ns, left.st_ctime_ns) == (
            right.st_dev, right.st_ino, right.st_mode, right.st_size,
            right.st_mtime_ns, right.st_ctime_ns)


def _read_source_once(path: Path, maximum: int) -> bytes:
    """Read one regular file through O_NOFOLLOW and reject identity/content races."""
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None or not hasattr(os, "memfd_create"):
        raise SnapshotError("immutable_snapshot_unavailable")
    flags = (os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | nofollow |
             getattr(os, "O_NONBLOCK", 0))
    try:
        path_before = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(path_before.st_mode):
            raise SnapshotError("source_not_regular")
        if path_before.st_size <= 0 or path_before.st_size > maximum:
            raise SnapshotError("source_size_out_of_bounds")
        fd = os.open(path, flags)
    except SnapshotError:
        raise
    except OSError as exc:
        raise SnapshotError("source_open_failed") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not _same_stat(path_before, before):
            raise SnapshotError("source_identity_changed")
        if before.st_size <= 0 or before.st_size > maximum:
            raise SnapshotError("source_size_out_of_bounds")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                raise SnapshotError("source_changed_during_read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise SnapshotError("source_changed_during_read")
        after = os.fstat(fd)
        try:
            path_after = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            raise SnapshotError("source_path_changed") from exc
        if not _same_stat(before, after) or not _same_stat(after, path_after):
            raise SnapshotError("source_changed_during_read")
        content = b"".join(chunks)
        if len(content) != before.st_size or len(content) > maximum:
            raise SnapshotError("source_size_changed")
        return content
    finally:
        os.close(fd)


def _linux_sealing_constants() -> tuple[int, int, int]:
    """Use Linux UAPI values when Python was built without sealing symbols.

    linux/fcntl.h fixes F_LINUX_SPECIFIC_BASE=1024, ADD/GET=base+9/+10,
    and SEAL_SEAL/SHRINK/GROW/WRITE=1/2/4/8. Runtime kernel enforcement
    and read-back are still mandatory; absent enforcement never passes.
    """
    if sys.platform != "linux":
        raise SnapshotError("immutable_snapshot_unavailable")
    add = getattr(fcntl, "F_ADD_SEALS", 1033)
    get = getattr(fcntl, "F_GET_SEALS", 1034)
    seals = (getattr(fcntl, "F_SEAL_WRITE", 8) |
             getattr(fcntl, "F_SEAL_GROW", 4) |
             getattr(fcntl, "F_SEAL_SHRINK", 2) |
             getattr(fcntl, "F_SEAL_SEAL", 1))
    return add, get, seals


def _sealed_snapshot(name: str, content: bytes) -> int:
    """Create an anonymous private snapshot that the simulator cannot rewrite."""
    allow_sealing = getattr(os, "MFD_ALLOW_SEALING", None)
    if allow_sealing is None:
        raise SnapshotError("immutable_snapshot_unavailable")
    add_seals, get_seals, seals = _linux_sealing_constants()
    fd = os.memfd_create(name, allow_sealing | getattr(os, "MFD_CLOEXEC", 0))
    try:
        view = memoryview(content)
        offset = 0
        while offset < len(view):
            offset += os.write(fd, view[offset:])
        os.fchmod(fd, 0o400)
        fcntl.fcntl(fd, add_seals, seals)
        if fcntl.fcntl(fd, get_seals) & seals != seals:
            raise SnapshotError("snapshot_seal_failed")
        if os.pread(fd, len(content), 0) != content:
            raise SnapshotError("snapshot_verification_failed")
        return fd
    except Exception as exc:
        try:
            os.close(fd)
        except OSError:
            pass
        if isinstance(exc, OSError):
            raise SnapshotError("snapshot_sealing_failed") from exc
        raise


def _snapshot_still_bound(fd: int, content: bytes, digest: str) -> bool:
    try:
        _, get_seals, required = _linux_sealing_constants()
        if fcntl.fcntl(fd, get_seals) & required != required:
            return False
        return (os.fstat(fd).st_size == len(content) and
                hashlib.sha256(os.pread(fd, len(content), 0)).hexdigest() == digest)
    except OSError:
        return False


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _terminate_group(proc: subprocess.Popen[bytes]) -> tuple[bool, bool]:
    """Terminate the isolated process group, reap the direct child, verify empty."""
    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError:
        pass
    try:
        proc.wait(timeout=TERM_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            pass
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            return False, False
    deadline = time.monotonic() + GROUP_REAP_SECONDS
    while _group_exists(pgid) and time.monotonic() < deadline:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            break
        except OSError:
            break
        time.sleep(0.025)
    return proc.poll() is not None, not _group_exists(pgid)


def _capture_bounded(proc: subprocess.Popen[bytes], timeout: float) -> tuple[bytes, bytes, bool, bool]:
    """Drain both streams without unbounded buffering; signal deadline/overflow."""
    selector = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    timed_out = False
    overflow = False
    deadline = time.monotonic() + timeout
    assert proc.stdout is not None and proc.stderr is not None
    for name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    try:
        while selector.get_map() or proc.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            events = selector.select(min(remaining, 0.05))
            for key, _ in events:
                name = key.data
                chunk = os.read(key.fd, min(8192, MAX_OUTPUT_BYTES + 1))
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                target = buffers[name]
                if len(target) + len(chunk) > MAX_OUTPUT_BYTES:
                    overflow = True
                    break
                target.extend(chunk)
            if overflow:
                break
        return bytes(buffers["stdout"]), bytes(buffers["stderr"]), timed_out, overflow
    finally:
        selector.close()


def _close_snapshot_fd(fd: int) -> None:
    """Small cleanup seam used by the public-boundary failure regression."""
    os.close(fd)


def _base_result() -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA,
        "submitted_sha256": {},
        "submitted_size_bytes": {},
        "simulator_child_exit": None,
        "simulator_result": {"stage": "indeterminate", "target_script_invoked": False},
        "wrapper_exit_code": 2,
        "cleanup": {"child_reaped": True, "process_group_empty": True,
                    "snapshot_descriptors_closed": True, "status": "not_started"},
    }


def _build_simulator_command(aiken: Path, descriptors: dict[str, int]) -> list[str]:
    return [str(aiken), "tx", "simulate", "--cbor",
            f"/proc/self/fd/{descriptors['transaction']}",
            f"/proc/self/fd/{descriptors['raw_inputs']}",
            f"/proc/self/fd/{descriptors['raw_outputs']}"]


def _verify_command_binding(command: list[str], descriptors: dict[str, int]) -> None:
    expected = [f"/proc/self/fd/{descriptors[name]}"
                for name in ("transaction", "raw_inputs", "raw_outputs")]
    if command[-3:] != expected:
        raise SnapshotError("snapshot_binding_mismatch")


def run_snapshot_simulation(aiken: Path, tx_path: Path, inputs_path: Path,
                            outputs_path: Path, expected_policy_id: str,
                            timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Submit exact bounded immutable snapshots; expose hashes and separate exit codes only."""
    result = _base_result()
    if (type(timeout_seconds) not in (int, float) or
            not MIN_TIMEOUT_SECONDS <= timeout_seconds <= MAX_TIMEOUT_SECONDS):
        result["error_code"] = "timeout_out_of_bounds"
        result["cleanup"]["status"] = "not_started"
        return result
    paths = (("transaction", tx_path, MAX_TX_BYTES),
             ("raw_inputs", inputs_path, MAX_VECTOR_BYTES),
             ("raw_outputs", outputs_path, MAX_VECTOR_BYTES))
    source: dict[str, bytes] = {}
    descriptors: list[int] = []
    proc: subprocess.Popen[bytes] | None = None
    child_reaped = True
    group_empty = True
    cleanup_errors = False
    stdout = stderr = b""
    timed_out = overflow = False
    classified: dict[str, Any] = result["simulator_result"]
    try:
        total = 0
        for name, path, maximum in paths:
            content = _read_source_once(Path(path), maximum)
            total += len(content)
            if total > MAX_TOTAL_BYTES:
                raise SnapshotError("total_snapshot_size_out_of_bounds")
            source[name] = content
        helper = _registry_helpers()
        binding = _extract_target_mint_binding(helper, source["transaction"], expected_policy_id)
        result["target_mint_binding"] = {
            "expected_policy_id": expected_policy_id,
            "policy_ids": binding["policy_ids"],
            "compiled_script_hash": binding["script_hash"],
        }
        for name, _, _ in paths:
            descriptors.append(_sealed_snapshot("f05-r3-" + name, source[name]))
        digests = {name: hashlib.sha256(source[name]).hexdigest() for name, _, _ in paths}
        result["submitted_sha256"] = digests
        result["submitted_size_bytes"] = {name: len(source[name]) for name, _, _ in paths}
        if any(not _snapshot_still_bound(fd, source[name], digests[name])
               for fd, (name, _, _) in zip(descriptors, paths, strict=True)):
            raise SnapshotError("snapshot_integrity_failure")
        descriptor_by_role = dict(zip((name for name, _, _ in paths), descriptors, strict=True))
        command = _build_simulator_command(aiken, descriptor_by_role)
        _verify_command_binding(command, descriptor_by_role)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, close_fds=True,
                                pass_fds=tuple(descriptors), start_new_session=True,
                                bufsize=0)
        stdout, stderr, timed_out, overflow = _capture_bounded(proc, float(timeout_seconds))
        if timed_out or overflow:
            child_reaped, group_empty = _terminate_group(proc)
        else:
            child_reaped = proc.poll() is not None
            if _group_exists(proc.pid):
                reaped, empty = _terminate_group(proc)
                child_reaped = child_reaped and reaped
                group_empty = empty
        child_exit = proc.returncode
        result["simulator_child_exit"] = child_exit
        if not timed_out and not overflow and all(
                _snapshot_still_bound(fd, source[name], digests[name])
                for fd, (name, _, _) in zip(descriptors, paths, strict=True)):
            classified = helper.classify_tx_sim_result(
                {"exit": child_exit,
                 "stdout": stdout.decode("utf-8", "replace"),
                 "stderr": stderr.decode("utf-8", "replace")},
                source["transaction"], expected_policy_id)
        elif timed_out:
            result["error_code"] = "simulator_deadline"
        elif overflow:
            result["error_code"] = "simulator_output_limit"
        else:
            result["error_code"] = "snapshot_integrity_failure"
        result["simulator_result"] = classified
    except SnapshotError as exc:
        result["error_code"] = exc.code
    except Exception:
        result["error_code"] = "runner_internal_error"
        if proc is not None and proc.poll() is None:
            child_reaped, group_empty = _terminate_group(proc)
    finally:
        if proc is not None and proc.poll() is None:
            reaped, empty = _terminate_group(proc)
            child_reaped = child_reaped and reaped
            group_empty = group_empty and empty
        for fd in reversed(descriptors):
            try:
                _close_snapshot_fd(fd)
            except Exception:
                cleanup_errors = True
                try:
                    os.close(fd)
                except OSError:
                    pass
        if proc is not None:
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        cleanup_errors = True
    cleanup_ok = child_reaped and group_empty and not cleanup_errors
    result["cleanup"] = {
        "child_reaped": child_reaped,
        "process_group_empty": group_empty,
        "snapshot_descriptors_closed": not cleanup_errors,
        "status": "clean" if cleanup_ok else "failed",
    }
    if not cleanup_ok:
        result["error_code"] = "cleanup_failed"
    completed_classification = classified.get("stage") in {
        "script_accepted", "compiled_evaluation"
    } and classified.get("target_script_invoked") is True
    result["wrapper_exit_code"] = 0 if cleanup_ok and completed_classification and not timed_out and not overflow else 2
    if timed_out:
        result["wrapper_exit_code"] = 2
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aiken", type=Path, required=True)
    parser.add_argument("--tx", type=Path, required=True)
    parser.add_argument("--raw-inputs", type=Path, required=True)
    parser.add_argument("--raw-outputs", type=Path, required=True)
    parser.add_argument("--policy-id", required=True)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    result = run_snapshot_simulation(args.aiken, args.tx, args.raw_inputs,
                                    args.raw_outputs, args.policy_id, args.timeout)
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return int(result["wrapper_exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
