"""Test-only CBOR helpers for typed F05.2a transaction-simulator fixtures.

This supports only the definite-length CBOR subset present in the reviewed
Conway canary. It is not a ledger validator or general-purpose CBOR package.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import subprocess
from typing import Any


@dataclass(frozen=True)
class Tag:
    number: int
    value: Any


@dataclass
class Map:
    pairs: list[tuple[Any, Any]]


class CBORError(ValueError):
    pass


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate simulator result key")
        result[key] = value
    return result


def _head(data: bytes, pos: int) -> tuple[int, int, int]:
    if pos >= len(data):
        raise CBORError("truncated CBOR item")
    initial = data[pos]
    major, add = initial >> 5, initial & 31
    if add < 24:
        return major, add, pos + 1
    widths = {24: 1, 25: 2, 26: 4, 27: 8}
    if add not in widths:
        raise CBORError("indefinite or reserved CBOR outside fixture subset")
    width = widths[add]
    end = pos + 1 + width
    if end > len(data):
        raise CBORError("truncated CBOR argument")
    value = int.from_bytes(data[pos + 1:end], "big")
    minimum = {24: 24, 25: 256, 26: 65536, 27: 4294967296}[add]
    if value < minimum:
        raise CBORError("non-minimal CBOR argument")
    return major, value, end


def _decode(data: bytes, pos: int = 0) -> tuple[Any, int]:
    major, value, pos = _head(data, pos)
    if major == 0:
        return value, pos
    if major == 1:
        return -1 - value, pos
    if major in (2, 3):
        end = pos + value
        if end > len(data):
            raise CBORError("truncated CBOR string")
        raw = data[pos:end]
        return (raw if major == 2 else raw.decode("utf-8")), end
    if major == 4:
        result = []
        for _ in range(value):
            item, pos = _decode(data, pos)
            result.append(item)
        return result, pos
    if major == 5:
        result = []
        for _ in range(value):
            key, pos = _decode(data, pos)
            item, pos = _decode(data, pos)
            result.append((key, item))
        return Map(result), pos
    if major == 6:
        item, pos = _decode(data, pos)
        return Tag(value, item), pos
    if major == 7:
        if value == 20:
            return False, pos
        if value == 21:
            return True, pos
        if value == 22:
            return None, pos
    raise CBORError("unsupported simple value, float, or CBOR type")


def loads(data: bytes) -> Any:
    value, end = _decode(data)
    if end != len(data):
        raise CBORError("trailing CBOR bytes")
    return value


def _emit_head(major: int, value: int) -> bytes:
    if value < 24:
        return bytes([(major << 5) | value])
    for add, width, limit in ((24, 1, 256), (25, 2, 65536),
                              (26, 4, 4294967296), (27, 8, 2**64)):
        if value < limit:
            return bytes([(major << 5) | add]) + value.to_bytes(width, "big")
    raise CBORError("CBOR integer exceeds uint64")


def dumps(value: Any) -> bytes:
    if value is False:
        return b"\xf4"
    if value is True:
        return b"\xf5"
    if value is None:
        return b"\xf6"
    if isinstance(value, int):
        return _emit_head(0, value) if value >= 0 else _emit_head(1, -1 - value)
    if isinstance(value, bytes):
        return _emit_head(2, len(value)) + value
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _emit_head(3, len(raw)) + raw
    if isinstance(value, list):
        return _emit_head(4, len(value)) + b"".join(map(dumps, value))
    if isinstance(value, Map):
        return _emit_head(5, len(value.pairs)) + b"".join(
            dumps(k) + dumps(v) for k, v in value.pairs)
    if isinstance(value, Tag):
        return _emit_head(6, value.number) + dumps(value.value)
    raise CBORError("unsupported fixture value")


def map_get(value: Map, key: Any) -> Any:
    found = [v for k, v in value.pairs if k == key]
    if len(found) != 1:
        raise CBORError(f"expected one occurrence of CBOR map key {key!r}")
    return found[0]


def map_set(value: Map, key: Any, replacement: Any) -> None:
    found = [i for i, (k, _) in enumerate(value.pairs) if k == key]
    if len(found) != 1:
        raise CBORError(f"expected one occurrence of CBOR map key {key!r}")
    value.pairs[found[0]] = (key, replacement)


def roundtrip(data: bytes) -> Any:
    value = loads(data)
    if dumps(value) != data:
        raise CBORError("CBOR fixture is not canonical byte-for-byte")
    return value


def run_typed_tx_case(aiken: Path, tx_path: Path, inputs_path: Path,
                      outputs_path: Path, timeout: int = 90) -> dict[str, Any]:
    result = subprocess.run(
        [str(aiken), "tx", "simulate", "--cbor", str(tx_path),
         str(inputs_path), str(outputs_path)],
        capture_output=True, text=True, timeout=timeout, check=False)
    return {"exit": result.returncode, "stdout": result.stdout,
            "stderr": result.stderr}


def classify_tx_sim_result(result: dict[str, Any], tx_cbor: bytes,
                           expected_policy_id: str) -> dict[str, Any]:
    """Recognize only the reviewed Aiken 1.1.21/1.1.23 Mint[0] transcript."""
    tx = roundtrip(tx_cbor)
    if not isinstance(tx, list) or len(tx) != 4:
        raise CBORError("expected typed Conway transaction tuple")
    mint = map_get(tx[0], 9)
    if not isinstance(mint, Map) or len(mint.pairs) != 1:
        raise CBORError("expected exactly one unique typed mint policy entry")
    if not isinstance(mint.pairs[0][0], bytes):
        raise CBORError("typed mint policy ID must be bytes")
    policy_ids = {policy.hex() for policy, _ in mint.pairs}
    if policy_ids != {expected_policy_id}:
        raise CBORError(f"typed mint policy set mismatch: {sorted(policy_ids)}")
    scripts = map_get(tx[1], 7)
    if not isinstance(scripts, Tag) or scripts.number != 258:
        raise CBORError("expected Plutus V3 witness set tag 258")
    if not isinstance(scripts.value, list) or len(scripts.value) != 1 or not isinstance(scripts.value[0], bytes):
        raise CBORError("expected one Plutus V3 witness script")
    script_hash = hashlib.blake2b(b"\x03" + scripts.value[0], digest_size=28).hexdigest()
    if script_hash != expected_policy_id:
        raise CBORError(f"witness script hash mismatch: {script_hash}")
    indeterminate = {"stage": "indeterminate", "target_script_invoked": False}
    if (type(result) is not dict or type(result.get("exit")) is not int or
            type(result.get("stdout")) is not str or
            type(result.get("stderr")) is not str):
        return indeterminate
    stderr = result["stderr"]
    # The qualified runtimes emit progress and script errors on stderr. Do not
    # concatenate streams: doing so can manufacture an invocation marker.
    stderr = stderr.replace("\x1b[31m", "").replace("\x1b[39m", "")
    lines = [line.strip() for line in stderr.splitlines()]
    expected_tx_id = hashlib.blake2b(dumps(tx[0]), digest_size=32).hexdigest()
    if (len(lines) < 3 or lines[0] != "Parsing script context" or
            lines[1] != f"Simulating {expected_tx_id}" or
            lines[2] != "Evaluating Mint[0]"):
        return indeterminate
    if result["exit"] == 1 and result["stdout"] == "" and lines[3:] == [
        "Error failed script execution",
        "Mint[0] the validator crashed / exited prematurely",
    ]:
        return {"stage": "compiled_evaluation", "target_script_invoked": True}
    if result["exit"] == 0 and len(lines) == 3:
        try:
            resource = json.loads(result["stdout"], object_pairs_hook=_unique_json_object)
        except (ValueError, TypeError):
            return indeterminate
        if (type(resource) is list and len(resource) == 1 and
                type(resource[0]) is dict and
                set(resource[0]) == {"cpu", "mem", "traces"} and
                type(resource[0]["cpu"]) is int and resource[0]["cpu"] > 0 and
                type(resource[0]["mem"]) is int and resource[0]["mem"] > 0 and
                resource[0]["traces"] == []):
            return {"stage": "script_accepted", "target_script_invoked": True}
    return indeterminate


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
