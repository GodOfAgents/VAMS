#!/usr/bin/env python3
"""Build deterministic test-only authority lovelace transaction fixtures.

This builder writes a canonical positive control and the two registry-defined
one-lovelace mutations. It never invokes a simulator or persists signing keys.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(os.environ["VAMS_R4_REPO_ROOT"]).resolve()
BASE = ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1"
REGISTRY_PATH = ROOT / "docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
REGISTRY_SHA256 = "98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d"
CONTRACT_PATH = ROOT / "docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r2.json"
CONTRACT_SHA256 = "3510e127d369e9eab24a7ebe5a5dea10daaf55fd9589a297d78776bda940f6e9"
BASE_HASHES = {
    "transaction": "765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28",
    "raw_inputs": "4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
    "raw_outputs": "9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a",
}
POLICY_ID = bytes.fromhex("9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731")
TOKEN_NAME = b"VAMS-F05-AUTH-V3"
CASE_IDS = ("authority_value_plus_one", "fee_diversion")
FAMILY_ID = "authority_lovelace"
OUTPUT = Path(__file__).resolve().parent


def load_codec():
    path = ROOT / "scripts/remediation/build_f05_2a_typed_tx_pair.py"
    spec = importlib.util.spec_from_file_location("f05_r4_typed_cbor_codec", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("accepted typed-CBOR codec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_map(codec: Any, value: Any, key: Any, replacement: Any) -> Any:
    positions = [i for i, (candidate, _) in enumerate(value.pairs) if candidate == key]
    if len(positions) != 1:
        raise ValueError(f"map key {key!r} is not unique")
    pairs = list(value.pairs)
    pairs[positions[0]] = (key, replacement)
    return codec.M(tuple(pairs))


def mutate(codec: Any, tx: list[Any], case_id: str) -> None:
    body = tx[0]
    outputs = codec.get(body, 1)
    if type(outputs) is not list or len(outputs) != 2:
        raise ValueError("expected exactly authority and sponsor outputs")
    authority, sponsor = outputs
    authority_value = codec.get(authority, 1)
    if type(authority_value) is not list or len(authority_value) != 2:
        raise ValueError("authority output does not have canonical multiasset value")
    sponsor_value = codec.get(sponsor, 1)
    if type(sponsor_value) is not int:
        raise ValueError("expected lovelace-only sponsor output")
    fee = codec.get(body, 2)
    if type(fee) is not int or type(authority_value[0]) is not int:
        raise ValueError("fee and authority lovelace must be integers")
    if case_id == "authority_value_plus_one":
        changed_authority_lovelace = authority_value[0] + 1
        changed_sponsor_lovelace = sponsor_value - 1
        changed_fee = fee
        delta = "authority output lovelace +1; sponsor/change output lovelace -1; fee, assets, inputs, datum, mint unchanged"
    elif case_id == "fee_diversion":
        changed_authority_lovelace = authority_value[0] - 1
        changed_sponsor_lovelace = sponsor_value
        changed_fee = fee + 1
        delta = "authority output lovelace -1; fee +1; sponsor/change output, assets, inputs, datum, mint unchanged"
    else:
        raise ValueError(f"unregistered authority lovelace case {case_id}")
    if changed_authority_lovelace <= 0 or changed_sponsor_lovelace <= 0:
        raise ValueError("mutation produced nonpositive output value")
    changed_authority = replace_map(codec, authority, 1, [changed_authority_lovelace, authority_value[1]])
    changed_sponsor = replace_map(codec, sponsor, 1, changed_sponsor_lovelace)
    changed_outputs = list(outputs)
    changed_outputs[0], changed_outputs[1] = changed_authority, changed_sponsor
    tx[0] = replace_map(codec, body, 1, changed_outputs)
    tx[0] = replace_map(codec, tx[0], 2, changed_fee)
    return delta


def funding_keys(case_id: str, count: int):
    keys = []
    for index in range(count):
        seed = hashlib.sha256(b"VAMS-F05-2A-R4-LOCAL-FIXTURE-ONLY\0" + case_id.encode("ascii") + b"\0" + index.to_bytes(2, "big")).digest()
        private = Ed25519PrivateKey.from_private_bytes(seed)
        public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        keys.append((private, public))
    return keys


def resign(codec: Any, tx: list[Any], raw_outputs: list[Any], case_id: str):
    if type(raw_outputs) is not list or len(raw_outputs) != 2:
        raise ValueError("expected ordered resolved funding UTxOs")
    keys = funding_keys(case_id, len(raw_outputs))
    for index, (utxo, (_, public)) in enumerate(zip(raw_outputs, keys, strict=True)):
        pairs = list(utxo.pairs)
        positions = [i for i, (key, _) in enumerate(pairs) if key == 0]
        if len(positions) != 1:
            raise ValueError("funding UTxO has no unique address")
        address = b"\x60" + hashlib.blake2b(public, digest_size=28).digest()
        pairs[positions[0]] = (0, codec.B(address))
        raw_outputs[index] = codec.M(tuple(pairs))
    body_hash = hashlib.blake2b(codec.enc(tx[0]), digest_size=32).digest()
    witnesses = []
    for private, public in keys:
        signature = private.sign(body_hash)
        Ed25519PublicKey.from_public_bytes(public).verify(signature, body_hash)
        witnesses.append([codec.B(public), codec.B(signature)])
    witnesses.sort(key=lambda pair: pair[0].value)
    old = codec.get(tx[1], 0)
    if not isinstance(old, codec.T) or old.tag != 258:
        raise ValueError("base fixture lacks canonical vkey witness set")
    tx[1] = replace_map(codec, tx[1], 0, codec.T(258, witnesses))
    encoded_tx = codec.enc(tx)
    reread = codec.parse(encoded_tx)
    observed_hash = hashlib.blake2b(codec.enc(reread[0]), digest_size=32).digest()
    if observed_hash != body_hash:
        raise ValueError("serialized body hash changed")
    serialized = codec.get(reread[1], 0)
    if not isinstance(serialized, codec.T) or serialized.tag != 258:
        raise ValueError("serialized witnesses malformed")
    for public, signature in serialized.value:
        Ed25519PublicKey.from_public_bytes(public.value).verify(signature.value, body_hash)
    return encoded_tx, codec.enc(raw_outputs), body_hash.hex(), len(serialized.value)


def check_conservation(codec: Any, tx: list[Any], raw_outputs: list[Any]) -> dict[str, Any]:
    input_lovelace = sum(codec.get(utxo, 1) for utxo in raw_outputs)
    outputs = codec.get(tx[0], 1)
    output_lovelace = sum(v if type(v) is int else v[0] for v in (codec.get(out, 1) for out in outputs))
    fee = codec.get(tx[0], 2)
    if input_lovelace != output_lovelace + fee:
        raise ValueError("lovelace conservation failed")
    minted = codec.get(tx[0], 9)
    minted_assets = {(pid.value, name.value): qty for pid, names in minted.pairs for name, qty in names.pairs}
    output_assets: dict[tuple[bytes, bytes], int] = {}
    for out in outputs:
        value = codec.get(out, 1)
        if type(value) is list and len(value) == 2 and isinstance(value[1], codec.M):
            for pid, names in value[1].pairs:
                for name, qty in names.pairs:
                    key = (pid.value, name.value)
                    output_assets[key] = output_assets.get(key, 0) + qty
    if minted_assets != output_assets:
        raise ValueError("mint/output asset conservation failed")
    return {"input_lovelace": input_lovelace, "output_lovelace": output_lovelace, "fee_lovelace": fee,
            "lovelace_conserved": True, "minted_output_assets_match": True,
            "minted_assets": {f"{pid.hex()}.{name.hex()}": qty for (pid, name), qty in minted_assets.items()},
            "output_assets": {f"{pid.hex()}.{name.hex()}": qty for (pid, name), qty in output_assets.items()}}


def build() -> dict[str, Any]:
    codec = load_codec()
    if sha(REGISTRY_PATH.read_bytes()) != REGISTRY_SHA256 or sha(CONTRACT_PATH.read_bytes()) != CONTRACT_SHA256:
        raise ValueError("accepted registry or R2 contract digest mismatch")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    reg_rows = {row["id"]: row for row in registry["negative_cases"]}
    contract_rows = {row["id"]: row for row in contract["negative_cases"]}
    if any(case not in reg_rows or case not in contract_rows for case in CASE_IDS):
        raise ValueError("authority value case IDs absent from accepted registry/contract")
    source_paths = {"transaction": BASE / "valid.tx.cbor", "raw_inputs": BASE / "raw_inputs.cbor", "raw_outputs": BASE / "raw_outputs.cbor"}
    base = {role: path.read_bytes() for role, path in source_paths.items()}
    if {role: sha(raw) for role, raw in base.items()} != BASE_HASHES:
        raise ValueError("accepted base positive fixture digest mismatch")
    if any(codec.enc(codec.parse(raw)) != raw for raw in base.values()):
        raise ValueError("accepted base fixture failed canonical CBOR roundtrip")

    positive_dir = OUTPUT / "positive_control"
    positive_dir.mkdir(parents=True, exist_ok=True)
    pos_files = {}
    for role, raw in base.items():
        filename = "transaction.cbor" if role == "transaction" else role + ".cbor"
        path = positive_dir / filename
        path.write_bytes(raw)
        pos_files[role] = {"path": path.relative_to(OUTPUT).as_posix(), "sha256": sha(raw), "size_bytes": len(raw)}
    positive = {"schema_version": "f05-2a-r4-family-positive-control-v1", "id": "valid_positive_control",
                "family_id": FAMILY_ID, "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID.hex(), "applied_script_hash": POLICY_ID.hex()},
                "files": pos_files, "source": "accepted typed positive control copied byte-for-byte",
                "funding_witnesses": "accepted base witnesses; byte-identical copy", "expected_result": "accept control",
                "status": "control-only; no new simulator execution"}
    (positive_dir / "CASE-MANIFEST.json").write_text(json.dumps(positive, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cases = []
    for case_id in CASE_IDS:
        tx = codec.parse(base["transaction"])
        raw_inputs = codec.parse(base["raw_inputs"])
        raw_outputs = codec.parse(base["raw_outputs"])
        delta = mutate(codec, tx, case_id)
        tx_bytes, outputs_bytes, body_hash, witness_count = resign(codec, tx, raw_outputs, case_id)
        inputs_bytes = codec.enc(raw_inputs)
        final_tx, final_inputs, final_outputs = codec.parse(tx_bytes), codec.parse(inputs_bytes), codec.parse(outputs_bytes)
        if codec.enc(final_tx) != tx_bytes or codec.enc(final_inputs) != inputs_bytes or codec.enc(final_outputs) != outputs_bytes:
            raise ValueError("fixture failed canonical CBOR roundtrip")
        conserved = check_conservation(codec, final_tx, final_outputs)
        case_dir = OUTPUT / "cases" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        content = {"transaction": tx_bytes, "raw_inputs": inputs_bytes, "raw_outputs": outputs_bytes}
        files = {}
        for role, raw in content.items():
            filename = "transaction.cbor" if role == "transaction" else role + ".cbor"
            path = case_dir / filename
            path.write_bytes(raw)
            files[role] = {"path": path.relative_to(OUTPUT).as_posix(), "sha256": sha(raw), "size_bytes": len(raw)}
        row = contract_rows[case_id]
        record = {"schema_version": "f05-2a-r4-family-case-v1", "id": case_id, "family_id": FAMILY_ID,
                  "registry_assertion": row["verifier_property"], "original_registry_assertion": row["original_assertion"],
                  "expected_result": row["expected_result"], "delta": delta,
                  "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID.hex(), "applied_script_hash": POLICY_ID.hex()},
                  "files": files, "transaction_body_hash_blake2b_256": body_hash,
                  "funding_witnesses": {"count": witness_count, "verified_against_serialized_body": True, "private_material_persisted": False},
                  "conservation": conserved, "script_invoked": False,
                  "simulator_result": "not run pending independent family review and coordinator freeze", "status": "PENDING"}
        (case_dir / "CASE-MANIFEST.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        cases.append(record)

    manifest = {"schema_version": "f05-2a-r4-transaction-family-manifest-v1", "family_id": FAMILY_ID,
                "status": "fixtures prepared; pending independent review; no simulator execution",
                "accepted_registry": {"path": REGISTRY_PATH.relative_to(ROOT).as_posix(), "sha256": REGISTRY_SHA256},
                "r2_contract": {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "sha256": CONTRACT_SHA256},
                "base_positive_hashes": BASE_HASHES,
                "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID.hex(), "applied_script_hash": POLICY_ID.hex()},
                "funding_signature_method": "Blake2b-256 of exact serialized body; deterministic synthetic test-only Ed25519 signers derived in memory per case; resolved payment credentials rebound; witnesses independently verified; no private material persisted",
                "conservation_rule": "resolved inputs equal outputs plus fee and aggregate output assets equal every minted policy/name/quantity",
                "positive_control": positive, "cases": cases, "family_fixture_count": len(cases), "executions": 0,
                "all_cases_pending": all(row["status"] == "PENDING" for row in cases),
                "freeze_gate": "coordinator freezes exact hashes and Agent C independently approves before simulator invocation"}
    (OUTPUT / "FAMILY-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksums = []
    for path in sorted((p for p in OUTPUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS"), key=lambda p: p.relative_to(OUTPUT).as_posix()):
        checksums.append(f"{sha(path.read_bytes())}  {path.relative_to(OUTPUT).as_posix()}")
    (OUTPUT / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps({"family_id": result["family_id"], "cases": len(result["cases"]), "executions": result["executions"],
                      "all_cases_pending": result["all_cases_pending"]}, sort_keys=True))
