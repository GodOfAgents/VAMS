#!/usr/bin/env python3
"""Deterministic test-only typed-CBOR builder for datum envelope/schema cases.

Creates a positive-control copy, four declarative one-field negative fixtures,
and manifests. It never invokes Aiken or persists fixture signing secrets.
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
POLICY_ID = "9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
CASE_IDS = ("datum_missing", "datum_hash_only", "datum_unknown_constructor", "datum_schema_version")
FAMILY_ID = "datum_envelope_schema"
OUTPUT = Path(__file__).resolve().parent


def load_codec():
    path = ROOT / "scripts/remediation/build_f05_2a_typed_tx_pair.py"
    spec = importlib.util.spec_from_file_location("f05_r4_typed_cbor_codec", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("accepted typed CBOR codec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_map(codec: Any, value: Any, key: int, replacement: Any) -> Any:
    positions = [i for i, (candidate, _) in enumerate(value.pairs) if candidate == key]
    if len(positions) != 1:
        raise ValueError(f"CBOR map key {key} is not unique")
    pairs = list(value.pairs)
    pairs[positions[0]] = (key, replacement)
    return codec.M(tuple(pairs))


def remove_map(codec: Any, value: Any, key: int) -> Any:
    positions = [i for i, (candidate, _) in enumerate(value.pairs) if candidate == key]
    if len(positions) != 1:
        raise ValueError(f"CBOR map key {key} is not unique")
    return codec.M(tuple(pair for pair in value.pairs if pair[0] != key))


def mutate_authority_datum(codec: Any, tx: list[Any], case_id: str) -> None:
    body = tx[0]
    outputs = codec.get(body, 1)
    if type(outputs) is not list or len(outputs) != 2:
        raise ValueError("expected authority plus sponsor output")
    authority = outputs[0]
    envelope = codec.get(authority, 2)
    if (type(envelope) is not list or len(envelope) != 2 or envelope[0] != 1 or
            not isinstance(envelope[1], codec.T) or envelope[1].tag != 24 or
            not isinstance(envelope[1].value, codec.B)):
        raise ValueError("expected inline datum envelope")
    state = codec.parse(envelope[1].value.value)
    if not isinstance(state, codec.T) or state.tag != 121 or type(state.value) is not list or len(state.value) != 8:
        raise ValueError("unexpected canonical AuthorityStateV3 Plutus Data")
    if case_id == "datum_missing":
        changed_authority = remove_map(codec, authority, 2)
    elif case_id == "datum_hash_only":
        datum_hash = hashlib.blake2b(codec.enc(state), digest_size=32).digest()
        changed_authority = replace_map(codec, authority, 2, [0, codec.B(datum_hash)])
    else:
        fields = list(state.value)
        if case_id == "datum_unknown_constructor":
            changed_state = codec.T(123, fields)
        elif case_id == "datum_schema_version":
            fields[0] = 2
            changed_state = codec.T(state.tag, fields)
        else:
            raise ValueError(f"unknown case {case_id}")
        changed_authority = replace_map(
            codec, authority, 2, [1, codec.T(24, codec.B(codec.enc(changed_state)))])
    changed_outputs = list(outputs)
    changed_outputs[0] = changed_authority
    tx[0] = replace_map(codec, body, 1, changed_outputs)


def deterministic_funding_keys(case_id: str, count: int):
    keys = []
    for index in range(count):
        material = hashlib.sha256(
            b"VAMS-F05-2A-R4-LOCAL-FIXTURE-ONLY\0" + case_id.encode("ascii") +
            b"\0" + index.to_bytes(2, "big")).digest()
        private = Ed25519PrivateKey.from_private_bytes(material)
        public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        keys.append((private, public))
    return keys


def resign_funding(codec: Any, tx: list[Any], raw_outputs: list[Any], case_id: str):
    if type(raw_outputs) is not list or len(raw_outputs) != 2:
        raise ValueError("expected two ordered funding UTxOs")
    keys = deterministic_funding_keys(case_id, len(raw_outputs))
    for index, (utxo, (_, public)) in enumerate(zip(raw_outputs, keys, strict=True)):
        address = b"\x60" + hashlib.blake2b(public, digest_size=28).digest()
        pairs = list(utxo.pairs)
        positions = [i for i, (key, _) in enumerate(pairs) if key == 0]
        if len(positions) != 1:
            raise ValueError("funding UTxO address is not unique")
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


def verify_conservation(codec: Any, tx: list[Any], raw_outputs: list[Any]) -> dict[str, Any]:
    input_lovelace = sum(codec.get(utxo, 1) for utxo in raw_outputs)
    outputs = codec.get(tx[0], 1)
    output_lovelace = sum(v if type(v) is int else v[0] for v in (codec.get(o, 1) for o in outputs))
    fee = codec.get(tx[0], 2)
    if input_lovelace != output_lovelace + fee:
        raise ValueError("lovelace conservation failed")
    minted = codec.get(tx[0], 9)
    assets: dict[tuple[bytes, bytes], int] = {}
    for output in outputs:
        value = codec.get(output, 1)
        if type(value) is list and len(value) == 2 and isinstance(value[1], codec.M):
            for policy, tokens in value[1].pairs:
                for name, quantity in tokens.pairs:
                    assets[(policy.value, name.value)] = assets.get((policy.value, name.value), 0) + quantity
    minted_assets = {(p.value, n.value): q for p, tokens in minted.pairs for n, q in tokens.pairs}
    if assets != minted_assets:
        raise ValueError("native asset conservation failed")
    return {"input_lovelace": input_lovelace, "output_lovelace": output_lovelace,
            "fee_lovelace": fee, "lovelace_conserved": True, "minted_output_assets_match": True}


def build() -> dict[str, Any]:
    codec = load_codec()
    if digest(REGISTRY_PATH.read_bytes()) != REGISTRY_SHA256 or digest(CONTRACT_PATH.read_bytes()) != CONTRACT_SHA256:
        raise ValueError("accepted registry or R2 contract digest mismatch")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    registry_rows = {row["id"]: row for row in registry["negative_cases"]}
    contract_rows = {row["id"]: row for row in contract["negative_cases"]}
    if any(case not in registry_rows or case not in contract_rows for case in CASE_IDS):
        raise ValueError("family case IDs absent from accepted registry/contract")
    source_paths = {"transaction": BASE / "valid.tx.cbor", "raw_inputs": BASE / "raw_inputs.cbor",
                    "raw_outputs": BASE / "raw_outputs.cbor"}
    source = {name: path.read_bytes() for name, path in source_paths.items()}
    if {name: digest(raw) for name, raw in source.items()} != BASE_HASHES:
        raise ValueError("accepted positive fixture hash mismatch")
    if any(codec.enc(codec.parse(raw)) != raw for raw in source.values()):
        raise ValueError("accepted fixture failed canonical CBOR roundtrip")
    positive_dir = OUTPUT / "positive_control"
    positive_dir.mkdir(parents=True, exist_ok=True)
    positive_paths = {}
    for role, raw in source.items():
        target = positive_dir / ("transaction.cbor" if role == "transaction" else role + ".cbor")
        target.write_bytes(raw)
        positive_paths[role] = target
    positive_files = {role: {"path": path.relative_to(OUTPUT).as_posix(), "sha256": digest(source[role]),
                             "size_bytes": len(source[role])} for role, path in positive_paths.items()}
    positive_manifest = {"schema_version": "f05-2a-r4-family-positive-control-v1", "id": "valid_positive_control",
                         "family_id": FAMILY_ID, "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID,
                         "applied_script_hash": POLICY_ID}, "files": positive_files,
                         "source": "accepted typed positive control copied byte-for-byte",
                         "funding_witnesses": "accepted base witnesses; byte-identical copy",
                         "expected_result": "accept control", "status": "control-only; no new simulator execution"}
    (positive_dir / "CASE-MANIFEST.json").write_text(json.dumps(positive_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = []
    deltas = {
        "datum_missing": "remove only the authority output inline-datum option; preserve output value, mint, other outputs, fee and ordered inputs",
        "datum_hash_only": "replace only the inline-datum option with a datum-hash option containing Blake2b-256 of the same original datum bytes",
        "datum_unknown_constructor": "replace only AuthorityStateV3 constructor alternative 0 with Plutus Data constructor alternative 2",
        "datum_schema_version": "change only the AuthorityStateV3 schema_version field from 1 to 2",
    }
    for case_id in CASE_IDS:
        tx = codec.parse(source["transaction"])
        raw_inputs = codec.parse(source["raw_inputs"])
        raw_outputs = codec.parse(source["raw_outputs"])
        mutate_authority_datum(codec, tx, case_id)
        encoded_tx, encoded_outputs, body_hash, witness_count = resign_funding(codec, tx, raw_outputs, case_id)
        encoded_inputs = codec.enc(raw_inputs)
        final_tx = codec.parse(encoded_tx)
        final_inputs = codec.parse(encoded_inputs)
        final_outputs = codec.parse(encoded_outputs)
        if codec.enc(final_tx) != encoded_tx or codec.enc(final_inputs) != encoded_inputs or codec.enc(final_outputs) != encoded_outputs:
            raise ValueError("fixture failed canonical CBOR roundtrip")
        conservation = verify_conservation(codec, final_tx, final_outputs)
        case_dir = OUTPUT / "cases" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        contents = {"transaction": encoded_tx, "raw_inputs": encoded_inputs, "raw_outputs": encoded_outputs}
        file_rows = {}
        for role, raw in contents.items():
            name = "transaction.cbor" if role == "transaction" else role + ".cbor"
            path = case_dir / name
            path.write_bytes(raw)
            file_rows[role] = {"path": path.relative_to(OUTPUT).as_posix(), "sha256": digest(raw), "size_bytes": len(raw)}
        row = contract_rows[case_id]
        record = {"schema_version": "f05-2a-r4-family-case-v1", "id": case_id, "family_id": FAMILY_ID,
                  "registry_assertion": row["verifier_property"], "original_registry_assertion": row["original_assertion"],
                  "expected_result": row["expected_result"], "delta": deltas[case_id],
                  "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID, "applied_script_hash": POLICY_ID},
                  "files": file_rows, "transaction_body_hash_blake2b_256": body_hash,
                  "funding_witnesses": {"count": witness_count, "verified_against_serialized_body": True,
                                        "private_material_persisted": False},
                  "conservation": conservation, "script_invoked": False,
                  "simulator_result": "not run pending independent family review and coordinator freeze", "status": "PENDING"}
        (case_dir / "CASE-MANIFEST.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows.append(record)
    manifest = {"schema_version": "f05-2a-r4-transaction-family-manifest-v1", "family_id": FAMILY_ID,
                "status": "fixtures prepared; pending independent review; no simulator execution",
                "accepted_registry": {"path": REGISTRY_PATH.relative_to(ROOT).as_posix(), "sha256": REGISTRY_SHA256},
                "r2_contract": {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "sha256": CONTRACT_SHA256},
                "base_positive_hashes": BASE_HASHES, "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID,
                "applied_script_hash": POLICY_ID}, "funding_signature_method": "Blake2b-256 of serialized body; deterministic synthetic test-only Ed25519 keys derived in memory per case; funding UTxO payment credentials rebound; every witness verified against the serialized body; no private material persisted",
                "conservation_rule": "sum resolved input lovelace equals outputs plus fee; minted singleton equals output singleton",
                "positive_control": positive_manifest, "cases": rows, "family_fixture_count": len(rows), "executions": 0,
                "all_cases_pending": all(row["status"] == "PENDING" for row in rows),
                "freeze_gate": "coordinator freezes exact hashes and Agent C independently approves before simulator invocation"}
    (OUTPUT / "FAMILY-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checks = []
    for path in sorted((p for p in OUTPUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS"),
                       key=lambda p: p.relative_to(OUTPUT).as_posix()):
        checks.append(f"{digest(path.read_bytes())}  {path.relative_to(OUTPUT).as_posix()}")
    (OUTPUT / "SHA256SUMS").write_text("\n".join(checks) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps({"family_id": result["family_id"], "cases": len(result["cases"]),
                      "executions": result["executions"], "all_cases_pending": result["all_cases_pending"]}, sort_keys=True))
