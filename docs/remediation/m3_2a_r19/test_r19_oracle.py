from __future__ import annotations
import base64
import importlib.util
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[3]
ORACLE_PATH = HERE / "docs/remediation/m3_2a_r9/address_value_oracle.py"
DATUM_PATH = HERE / "docs/remediation/m3_2a_r7/DATUM_VECTORS.json"
TOPOLOGY_PATH = HERE / "docs/remediation/m3_2a_r7/TRANSITION_TOPOLOGY.json"
sys.path.insert(0, str(ORACLE_PATH.parent))
import address_value_oracle as oracle


def _record_fixture():
    document = json.loads(DATUM_PATH.read_text())
    vector = next(item for item in document["vectors"] if item["accepted"] and item["kind"] == "record")
    datum = {
        "kind": "VoteLockRecordV1",
        "constructor_index": 0,
        "fields": [[key, value] for key, value in vector["value"].items()],
        "cbor_hex": vector["cbor_hex"],
    }
    return vector, datum


def _child_code():
    return r'''
import json, sys
from pathlib import Path
import importlib.util
module_path, vector_path, vector_id, vector_json = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("r19_child", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
vector = json.loads(vector_json)
datum = {
    "kind": "VoteLockRecordV1",
    "constructor_index": 0,
    "fields": [[key, value] for key, value in vector["value"].items()],
    "cbor_hex": vector["cbor_hex"],
}
try:
    module.validate_inline_datum(datum, vector_id)
except module.OracleError:
    print(json.dumps({"error": "oracle rejected", "ok": False}, sort_keys=True))
    raise SystemExit(1)
except Exception:
    print(json.dumps({"error": "oracle rejected", "ok": False}, sort_keys=True))
    raise SystemExit(2)
print(json.dumps({"ok": True}, sort_keys=True))
'''


def _copy_tree(source_text=None, ancestor_symlink=False):
    td = tempfile.TemporaryDirectory(prefix="m32a-r19-")
    root = Path(td.name)
    if ancestor_symlink:
        real = root / "real"
        module_dir = real / "m3_2a_r9"
        artifact_dir = real / "m3_2a_r7"
        module_dir.mkdir(parents=True)
        artifact_dir.mkdir(parents=True)
        docs = root / "docs"
        docs.mkdir()
        (docs / "remediation").symlink_to(real, target_is_directory=True)
        module_path = root / "docs/remediation/m3_2a_r9/address_value_oracle.py"
        vector_path = root / "docs/remediation/m3_2a_r7/DATUM_VECTORS.json"
    else:
        module_dir = root / "docs/remediation/m3_2a_r9"
        artifact_dir = root / "docs/remediation/m3_2a_r7"
        module_dir.mkdir(parents=True)
        artifact_dir.mkdir(parents=True)
        module_path = module_dir / "address_value_oracle.py"
        vector_path = artifact_dir / "DATUM_VECTORS.json"
    module_path_real = module_dir / "address_value_oracle.py"
    module_path_real.write_text(ORACLE_PATH.read_text() if source_text is None else source_text)
    vector_path_real = artifact_dir / "DATUM_VECTORS.json"
    shutil.copy2(DATUM_PATH, vector_path_real)
    shutil.copy2(TOPOLOGY_PATH, artifact_dir / "TRANSITION_TOPOLOGY.json")
    return td, root, module_path, vector_path


def _run_child(module_path, vector_path, timeout=2):
    vector, _datum = _record_fixture()
    vector_id = vector["id"]
    return subprocess.run(
        [sys.executable, "-c", _child_code(), str(module_path), str(vector_path), vector_id, json.dumps(vector)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _fifo_probe_child_code():
    # Independent child used for every FIFO probe.
    return r'''
import base64, importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path

base_dir, source_b64, vector_b64, vector_id, vector_json, mode = sys.argv[1:]
base = Path(base_dir)
probe_dir = Path(tempfile.mkdtemp(prefix="m32a-r21-child-", dir=base))
module_dir = probe_dir / "docs/remediation/m3_2a_r9"
artifact_dir = probe_dir / "docs/remediation/m3_2a_r7"
module_dir.mkdir(parents=True)
artifact_dir.mkdir(parents=True)
module_path = module_dir / "address_value_oracle.py"
registry = artifact_dir / "DATUM_VECTORS.json"
module_path.write_bytes(base64.b64decode(source_b64))
registry.write_bytes(base64.b64decode(vector_b64))
reader_fd = None
writer_fd = None
status = "exception"
exit_code = 2
if mode in {"no_writer", "writer"}:
    registry.unlink()
    os.mkfifo(registry)
if mode == "writer":
    reader_fd = os.open(registry, os.O_RDONLY | os.O_NONBLOCK)
    writer_fd = os.open(registry, os.O_WRONLY | os.O_NONBLOCK)
    os.write(writer_fd, b"r21-probe")
try:
    spec = importlib.util.spec_from_file_location("r21_probe", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    vector = json.loads(vector_json)
    datum = {
        "kind": "VoteLockRecordV1",
        "constructor_index": 0,
        "fields": [[key, value] for key, value in vector["value"].items()],
        "cbor_hex": vector["cbor_hex"],
    }
    try:
        module.validate_inline_datum(datum, vector_id)
    except module.OracleError:
        status = "oracle_error"
        exit_code = 1
    except Exception:
        status = "exception"
        exit_code = 2
    else:
        status = "success"
        exit_code = 0
finally:
    if writer_fd is not None:
        os.close(writer_fd)
    remaining = None
    if reader_fd is not None:
        remaining = os.read(reader_fd, 4096) == b"r21-probe"
        os.close(reader_fd)
    shutil.rmtree(probe_dir, ignore_errors=True)
    print(json.dumps({
        "status": status,
        "writer_bytes_remaining": remaining,
        "probe_removed": not probe_dir.exists(),
    }, sort_keys=True), flush=True)
    raise SystemExit(exit_code)
'''


def _fd_count():
    return len(os.listdir("/proc/self/fd"))


def _remaining_processes(process_group):
    # Return process IDs remaining in the isolated process group/session.
    completed = subprocess.run(
        ["ps", "-eo", "pid=,pgid=,sid="],
        check=True,
        capture_output=True,
        text=True,
    )
    remaining = []
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        pid, pgid, sid = (int(value) for value in fields)
        if pgid == process_group or sid == process_group:
            remaining.append(pid)
    return sorted(remaining)


def _terminate_process_group(process):
    # Terminate, reap, and prove the isolated child process group is gone.
    process_group = process.pid
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=0.5)
    if process.poll() is None:
        process.kill()
        process.wait(timeout=0.5)
    return _remaining_processes(process_group)


def _run_fifo_probe(source_text, mode, timeout=1.0):
    # Run one fresh bounded FIFO/regular-file probe in an isolated child.
    vector, _datum = _record_fixture()
    vector_bytes = DATUM_PATH.read_bytes()
    base = Path(tempfile.mkdtemp(prefix="m32a-r21-parent-"))
    before = _fd_count()
    process = None
    timed_out = False
    remaining_processes = []
    stdout = ""
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _fifo_probe_child_code(),
                str(base),
                base64.b64encode(source_text.encode()).decode(),
                base64.b64encode(vector_bytes).decode(),
                vector["id"],
                json.dumps(vector),
                mode,
            ],
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, _stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            remaining_processes = _terminate_process_group(process)
            stdout, _stderr = process.communicate(timeout=0.5)
        else:
            process.wait(timeout=0.5)
            remaining_processes = _remaining_processes(process.pid)
    finally:
        if process is not None and process.poll() is None:
            remaining_processes = _terminate_process_group(process)
        shutil.rmtree(base, ignore_errors=True)
    after = _fd_count()
    if timed_out:
        status = "timeout"
        child_result = None
    else:
        try:
            child_result = json.loads(stdout)
            status = child_result.get("status", "malformed")
        except (TypeError, json.JSONDecodeError):
            child_result = None
            status = "malformed"
    return {
        "status": status,
        "child_result": child_result,
        "returncode": None if process is None else process.returncode,
        "child_reaped": process is not None and process.poll() is not None,
        "remaining_processes": remaining_processes,
        "temp_removed": not base.exists(),
        "descriptor_before": before,
        "descriptor_after": after,
    }


def _load_copy(module_path):
    spec = importlib.util.spec_from_file_location("r19_copy_" + str(id(module_path)), module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class R19OracleTests(unittest.TestCase):
    def _assert_probe_cleanup(self, probe):
        self.assertTrue(probe["child_reaped"])
        self.assertEqual(probe["remaining_processes"], [])
        self.assertTrue(probe["temp_removed"])
        self.assertEqual(probe["descriptor_before"], probe["descriptor_after"])

    def test_fifo_without_writer_rejects_promptly_and_closes(self):
        source = ORACLE_PATH.read_text()
        for _ in range(3):
            probe = _run_fifo_probe(source, "no_writer")
            self.assertEqual(probe["status"], "oracle_error")
            self.assertNotEqual(probe["returncode"], 0)
            self.assertIsNotNone(probe["child_result"])
            self.assertTrue(probe["child_result"]["probe_removed"])
            self.assertFalse(probe["child_result"]["writer_bytes_remaining"] is True)
            self._assert_probe_cleanup(probe)

    def test_fifo_with_writer_rejects_before_read(self):
        source = ORACLE_PATH.read_text()
        for _ in range(3):
            probe = _run_fifo_probe(source, "writer")
            self.assertEqual(probe["status"], "oracle_error")
            self.assertNotEqual(probe["returncode"], 0)
            self.assertEqual(probe["child_result"]["writer_bytes_remaining"], True)
            self.assertTrue(probe["child_result"]["probe_removed"])
            self._assert_probe_cleanup(probe)

    def test_fixed_regular_file_control_completes_before_deadline(self):
        source = ORACLE_PATH.read_text()
        for _ in range(3):
            probe = _run_fifo_probe(source, "regular")
            self.assertEqual(probe["status"], "success")
            self.assertEqual(probe["returncode"], 0)
            self.assertTrue(probe["child_result"]["probe_removed"])
            self._assert_probe_cleanup(probe)

    def test_removing_nonblocking_flag_is_detected_without_hanging_suite(self):
        source = ORACLE_PATH.read_text()
        mutated = source.replace("|os.O_NONBLOCK", "", 1)
        self.assertNotEqual(mutated, source)
        for _ in range(3):
            probe = _run_fifo_probe(mutated, "no_writer")
            self.assertEqual(probe["status"], "timeout")
            self.assertTrue(probe["child_reaped"])
            self.assertEqual(probe["remaining_processes"], [])
            self.assertTrue(probe["temp_removed"])
            self.assertEqual(probe["descriptor_before"], probe["descriptor_after"])

    def test_pathname_reopen_mutation_is_detected_without_hanging_suite(self):
        source = ORACLE_PATH.read_text()
        replacement = '(Path(os.path.abspath(__file__)).parents[3] / "docs/remediation/m3_2a_r7/DATUM_VECTORS.json").read_bytes()'
        mutated = source.replace("raw=_open_fixed_registry()", "raw=" + replacement, 1)
        self.assertNotEqual(mutated, source)
        for _ in range(3):
            probe = _run_fifo_probe(mutated, "no_writer")
            self.assertEqual(probe["status"], "timeout")
            self.assertTrue(probe["child_reaped"])
            self.assertEqual(probe["remaining_processes"], [])
            self.assertTrue(probe["temp_removed"])
            self.assertEqual(probe["descriptor_before"], probe["descriptor_after"])

    def test_other_nonregular_objects_reject_promptly(self):
        vector, datum = _record_fixture()
        for mode in ("directory", "socket", "symlink", "ancestor"):
            td, root, module_path, vector_path = _copy_tree(ancestor_symlink=(mode == "ancestor"))
            sock = None
            try:
                if mode != "ancestor":
                    raw = vector_path.read_bytes()
                    vector_path.unlink()
                    if mode == "directory":
                        vector_path.mkdir()
                    elif mode == "socket":
                        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        sock.bind(str(vector_path))
                    else:
                        target = vector_path.with_name("target.json")
                        target.write_bytes(raw)
                        vector_path.symlink_to(target)
                result = _run_child(module_path, vector_path)
                self.assertNotEqual(result.returncode, 0, mode)
                self.assertEqual(result.stderr, "", mode)
            finally:
                if sock is not None:
                    sock.close()
                td.cleanup()

    def test_independent_address_formula_accepts_public_validator(self):
        network = 0
        verification_key_hash = "11" * 28
        address = bytes([0x60 | network]) + bytes.fromhex(verification_key_hash)
        output = {
            "address_hex": address.hex(),
            "credential_kind": "key",
            "network_id": network,
            "lovelace": 10,
            "assets": {"locked_vams": 100},
            "datum_form": "none",
            "transition_role": "voter_refund:" + verification_key_hash,
        }
        self.assertEqual(oracle.validate_output_record(output).address_hex, address.hex())

    def test_independent_fixed_record_is_accepted(self):
        vector, datum = _record_fixture()
        self.assertTrue(oracle.validate_inline_datum(datum, vector["id"]))

    def test_independent_address_mutation_is_rejected(self):
        source = ORACLE_PATH.read_text()
        mutated = source.replace('0x60 if credential_kind=="key" else 0x70', '0x70 if credential_kind=="key" else 0x60', 1)
        td, root, module_path, vector_path = _copy_tree(mutated)
        try:
            spec = importlib.util.spec_from_file_location("r19_address_mutation", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            vkh = "11" * 28
            output = {
                "address_hex": (bytes([0x60]) + bytes.fromhex(vkh)).hex(),
                "credential_kind": "key",
                "network_id": 0,
                "lovelace": 10,
                "assets": {"locked_vams": 100},
                "datum_form": "none",
                "transition_role": "voter_refund:" + vkh,
            }
            with self.assertRaises(module.OracleError):
                module.validate_output_record(output)
        finally:
            td.cleanup()

    def test_independent_integer_encoding_mutation_is_rejected(self):
        source = ORACLE_PATH.read_text()
        old = "    return _cbor_head(head,n)\n\ndef _cbor_head"
        mutated = source.replace(old, "    return _cbor_head(head,n+1)\n\ndef _cbor_head", 1)
        self.assertNotEqual(mutated, source)
        td, root, module_path, vector_path = _copy_tree(mutated)
        try:
            result = _run_child(module_path, vector_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), {"error": "oracle rejected", "ok": False})
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
