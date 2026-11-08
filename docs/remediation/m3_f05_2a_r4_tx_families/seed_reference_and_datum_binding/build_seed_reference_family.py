#!/usr/bin/env python3
"""Deterministic test-only typed-CBOR builder for the R4 seed/datum family.

This script creates fixture files and manifests only. It never invokes Aiken.
The reproducible synthetic funding-key derivation is not a credential and must
never be used outside local test fixtures.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(os.environ.get("VAMS_R4_REPO_ROOT", Path(__file__).resolve().parents[4])).resolve()
BASE = ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1"
OUTPUT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
REGISTRY_SHA256 = "98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d"
R2_CONTRACT_PATH = ROOT / "docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r2.json"
R2_CONTRACT_SHA256 = "3510e127d369e9eab24a7ebe5a5dea10daaf55fd9589a297d78776bda940f6e9"
BASE_HASHES = {
    "transaction": "765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28",
    "raw_inputs": "4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
    "raw_outputs": "9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a",
}
POLICY_ID = "9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
POLICY_BYTES = bytes.fromhex(POLICY_ID)
CASE_IDS = ("seed_missing", "seed_datum_hash", "seed_datum_index")
GENESIS_REF = (bytes.fromhex("aa" * 32), 7)
ALT_SEED_REF = (bytes.fromhex("dd" * 32), 8)
FAMILY_ID = "seed_reference_and_datum_binding"


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
    positions = [index for index, (candidate, _) in enumerate(value.pairs) if candidate == key]
    if len(positions) != 1:
        raise ValueError(f"CBOR map key {key} is not unique")
    pairs = list(value.pairs)
    pairs[positions[0]] = (key, replacement)
    return codec.M(tuple(pairs))


def set_output_datum(codec: Any, tx: list[Any], mutate) -> None:
    body = tx[0]
    outputs = codec.get(body, 1)
    if type(outputs) is not list or len(outputs) != 2:
        raise ValueError("expected authority plus sponsor output")
    authority = outputs[0]
    envelope = codec.get(authority, 2)
    if (type(envelope) is not list or len(envelope) != 2 or envelope[0] != 1 or
            not isinstance(envelope[1], codec.T) or envelope[1].tag != 24 or
            not isinstance(envelope[1].value, codec.B)):
        raise ValueError("expected inline Plutus datum envelope")
    state = codec.parse(envelope[1].value.value)
    if (not isinstance(state, codec.T) or state.tag != 121 or
            type(state.value) is not list or len(state.value) != 8):
        raise ValueError("unexpected AuthorityStateV3 Plutus Data")
    fields = list(state.value)
    mutate(fields)
    changed_state = codec.T(state.tag, fields)
    changed_authority = replace_map(
        codec, authority, 2, [1, codec.T(24, codec.B(codec.enc(changed_state)))])
    changed_outputs = list(outputs)
    changed_outputs[0] = changed_authority
    tx[0] = replace_map(codec, body, 1, changed_outputs)


def change_seed_reference(codec: Any, tx: list[Any], raw_inputs: list[Any]) -> None:
    body_refs = codec.get(tx[0], 0)
    if not isinstance(body_refs, codec.T) or body_refs.tag != 258 or type(body_refs.value) is not list:
        raise ValueError("expected typed transaction input reference set")
    refs = list(body_refs.value)
    body_matches = [i for i, ref in enumerate(refs)
                    if type(ref) is list and len(ref) == 2 and
                    ref[0] == codec.B(GENESIS_REF[0]) and ref[1] == GENESIS_REF[1]]
    input_matches = [i for i, ref in enumerate(raw_inputs)
                     if type(ref) is list and len(ref) == 2 and
                     ref[0] == codec.B(GENESIS_REF[0]) and ref[1] == GENESIS_REF[1]]
    if len(body_matches) != 1 or len(input_matches) != 1 or body_matches != input_matches:
        raise ValueError("seed reference is not uniquely paired in ordered inputs")
    index = body_matches[0]
    refs[index] = [codec.B(ALT_SEED_REF[0]), ALT_SEED_REF[1]]
    raw_inputs[index] = [codec.B(ALT_SEED_REF[0]), ALT_SEED_REF[1]]
    tx[0] = replace_map(codec, tx[0], 0, codec.T(258, refs))


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


def resign_funding(codec: Any, tx: list[Any], raw_outputs: list[Any], case_id: str) -> tuple[bytes, bytes, str, int]:
    if type(raw_outputs) is not list or len(raw_outputs) != 2:
        raise ValueError("expected two ordered funding UTxOs")
    keys = deterministic_funding_keys(case_id, len(raw_outputs))
    for index, (utxo, (_, public)) in enumerate(zip(raw_outputs, keys, strict=True)):
        address = b"\x60" + hashlib.blake2b(public, digest_size=28).digest()
        utxo_pairs = list(utxo.pairs)
        address_positions = [i for i, (key, _) in enumerate(utxo_pairs) if key == 0]
        if len(address_positions) != 1:
            raise ValueError("resolved funding UTxO has no unique address")
        utxo_pairs[address_positions[0]] = (0, codec.B(address))
        raw_outputs[index] = codec.M(tuple(utxo_pairs))
    body_hash = hashlib.blake2b(codec.enc(tx[0]), digest_size=32).digest()
    vkeys = []
    for private, public in keys:
        signature = private.sign(body_hash)
        Ed25519PublicKey.from_public_bytes(public).verify(signature, body_hash)
        vkeys.append([codec.B(public), codec.B(signature)])
    vkeys.sort(key=lambda pair: pair[0].value)
    witness_set = tx[1]
    old_vkeys = codec.get(witness_set, 0)
    if not isinstance(old_vkeys, codec.T) or old_vkeys.tag != 258:
        raise ValueError("base fixture has no canonical vkey witness set")
    tx[1] = replace_map(codec, witness_set, 0, codec.T(258, vkeys))
    encoded_tx = codec.enc(tx)
    reread = codec.parse(encoded_tx)
    serialized_body_hash = hashlib.blake2b(codec.enc(reread[0]), digest_size=32).digest()
    if serialized_body_hash != body_hash:
        raise ValueError("serialized transaction body hash changed")
    serialized_witnesses = codec.get(reread[1], 0)
    if not isinstance(serialized_witnesses, codec.T) or serialized_witnesses.tag != 258:
        raise ValueError("serialized funding witnesses malformed")
    for public, signature in serialized_witnesses.value:
        Ed25519PublicKey.from_public_bytes(public.value).verify(signature.value, body_hash)
    encoded_outputs = codec.enc(raw_outputs)
    return encoded_tx, encoded_outputs, body_hash.hex(), len(serialized_witnesses.value)


def verify_conservation(codec: Any, tx: list[Any], raw_outputs: list[Any]) -> dict[str, Any]:
    body = tx[0]
    input_lovelace = sum(codec.get(utxo, 1) for utxo in raw_outputs)
    output_list = codec.get(body, 1)
    output_lovelace = sum(
        value if type(value) is int else value[0]
        for value in (codec.get(output, 1) for output in output_list))
    fee = codec.get(body, 2)
    if input_lovelace != output_lovelace + fee:
        raise ValueError("lovelace conservation failed")
    minted = codec.get(body, 9)
    output_assets: dict[tuple[bytes, bytes], int] = {}
    for output in output_list:
        value = codec.get(output, 1)
        if type(value) is not list or len(value) != 2 or not isinstance(value[1], codec.M):
            continue
        for policy, tokens in value[1].pairs:
            if not isinstance(tokens, codec.M):
                raise ValueError("malformed output asset map")
            for name, quantity in tokens.pairs:
                output_assets[(policy.value, name.value)] = output_assets.get((policy.value, name.value), 0) + quantity
    minted_assets: dict[tuple[bytes, bytes], int] = {}
    for policy, tokens in minted.pairs:
        for name, quantity in tokens.pairs:
            minted_assets[(policy.value, name.value)] = quantity
    if output_assets != minted_assets:
        raise ValueError("native asset conservation failed")
    return {
        "input_lovelace": input_lovelace,
        "output_lovelace": output_lovelace,
        "fee_lovelace": fee,
        "lovelace_conserved": True,
        "minted_output_assets_match": True,
    }


def build() -> dict[str, Any]:
    codec = load_codec()
    if digest(REGISTRY_PATH.read_bytes()) != REGISTRY_SHA256:
        raise ValueError("accepted registry digest mismatch")
    if digest(R2_CONTRACT_PATH.read_bytes()) != R2_CONTRACT_SHA256:
        raise ValueError("R2 evidence contract digest mismatch")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    contract = json.loads(R2_CONTRACT_PATH.read_text(encoding="utf-8"))
    source_ids = {row["id"] for row in registry["negative_cases"]}
    negative_rows = {row["id"]: row for row in contract["negative_cases"]}
    if not set(CASE_IDS).issubset(source_ids) or not set(CASE_IDS).issubset(negative_rows):
        raise ValueError("seed family IDs differ from accepted registry or R2 contract")
    source_files = {
        "transaction": BASE / "valid.tx.cbor",
        "raw_inputs": BASE / "raw_inputs.cbor",
        "raw_outputs": BASE / "raw_outputs.cbor",
    }
    source_bytes = {key: path.read_bytes() for key, path in source_files.items()}
    if {key: digest(value) for key, value in source_bytes.items()} != BASE_HASHES:
        raise ValueError("accepted positive fixture digest mismatch")
    for content in source_bytes.values():
        if codec.enc(codec.parse(content)) != content:
            raise ValueError("accepted fixture is not canonical CBOR")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    positive_dir = OUTPUT / "positive_control"
    positive_dir.mkdir(exist_ok=True)
    positive_paths = {
        "transaction": positive_dir / "transaction.cbor",
        "raw_inputs": positive_dir / "raw_inputs.cbor",
        "raw_outputs": positive_dir / "raw_outputs.cbor",
    }
    for role, path in positive_paths.items():
        path.write_bytes(source_bytes[role])
    records: list[dict[str, Any]] = []
    deltas = {
        "seed_missing": "replace the unique applied genesis input reference aa…aa#7 by dd…dd#8 in both transaction inputs and ordered raw-input vector; retain resolved UTxO values, mint, outputs and fee",
        "seed_datum_hash": "change only AuthorityStateV3.bootstrap_tx_hash from aa…aa to bb…bb; retain applied seed, proof message, keys, value, mint and outputs",
        "seed_datum_index": "change only AuthorityStateV3.bootstrap_output_index from 7 to 8; retain applied seed, proof message, keys, value, mint and outputs",
    }
    for case_id in CASE_IDS:
        if case_id not in negative_rows:
            raise ValueError(f"registry missing case {case_id}")
        tx = codec.parse(source_bytes["transaction"])
        raw_inputs = codec.parse(source_bytes["raw_inputs"])
        raw_outputs = codec.parse(source_bytes["raw_outputs"])
        if case_id == "seed_missing":
            change_seed_reference(codec, tx, raw_inputs)
        elif case_id == "seed_datum_hash":
            set_output_datum(codec, tx, lambda fields: fields.__setitem__(1, codec.B(bytes.fromhex("bb" * 32))))
        elif case_id == "seed_datum_index":
            set_output_datum(codec, tx, lambda fields: fields.__setitem__(2, 8))
        else:
            raise AssertionError("unregistered family case")
        encoded_tx, encoded_outputs, body_hash, witness_count = resign_funding(codec, tx, raw_outputs, case_id)
        encoded_inputs = codec.enc(raw_inputs)
        final_tx = codec.parse(encoded_tx)
        if codec.enc(final_tx) != encoded_tx or codec.enc(codec.parse(encoded_inputs)) != encoded_inputs:
            raise ValueError("fixture encoding failed canonical roundtrip")
        conservation = verify_conservation(codec, final_tx, codec.parse(encoded_outputs))
        case_dir = OUTPUT / "cases" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "transaction": case_dir / "transaction.cbor",
            "raw_inputs": case_dir / "raw_inputs.cbor",
            "raw_outputs": case_dir / "raw_outputs.cbor",
        }
        contents = {"transaction": encoded_tx, "raw_inputs": encoded_inputs, "raw_outputs": encoded_outputs}
        for role, path in paths.items():
            path.write_bytes(contents[role])
        row = negative_rows[case_id]
        case_manifest = {
            "schema_version": "f05-2a-r4-family-case-v1",
            "id": case_id,
            "family_id": FAMILY_ID,
            "registry_assertion": row["verifier_property"],
            "original_registry_assertion": row["original_assertion"],
            "expected_result": row["expected_result"],
            "delta": deltas[case_id],
            "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID, "applied_script_hash": POLICY_ID},
            "files": {role: {"path": path.relative_to(OUTPUT).as_posix(), "sha256": digest(contents[role]), "size_bytes": len(contents[role])} for role, path in paths.items()},
            "transaction_body_hash_blake2b_256": body_hash,
            "funding_witnesses": {"count": witness_count, "verified_against_serialized_body": True, "private_material_persisted": False},
            "conservation": conservation,
            "script_invoked": False,
            "simulator_result": "not run pending coordinator freeze and independent review",
            "status": "PENDING",
        }
        (case_dir / "CASE-MANIFEST.json").write_text(json.dumps(case_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        records.append(case_manifest)

    positive_manifest = {
        "schema_version": "f05-2a-r4-family-positive-control-v1",
        "id": "valid_positive_control",
        "family_id": FAMILY_ID,
        "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID, "applied_script_hash": POLICY_ID},
        "files": {role: {"path": path.relative_to(OUTPUT).as_posix(), "sha256": digest(source_bytes[role]), "size_bytes": len(source_bytes[role])} for role, path in positive_paths.items()},
        "source": "accepted typed positive control, copied byte-for-byte",
        "funding_witnesses": "previously accepted base-witness set; byte-identical copy",
        "expected_result": "accept control",
        "status": "control-only; no new simulator execution",
    }
    (positive_dir / "CASE-MANIFEST.json").write_text(json.dumps(positive_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    family_manifest = {
        "schema_version": "f05-2a-r4-transaction-family-manifest-v1",
        "family_id": FAMILY_ID,
        "status": "fixtures prepared; pending independent family review; no simulator execution",
        "accepted_registry": {"path": REGISTRY_PATH.relative_to(ROOT).as_posix(), "sha256": REGISTRY_SHA256},
        "r2_contract": {"path": R2_CONTRACT_PATH.relative_to(ROOT).as_posix(), "sha256": R2_CONTRACT_SHA256},
        "base_positive_hashes": BASE_HASHES,
        "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID, "applied_script_hash": POLICY_ID},
        "funding_signature_method": "canonical transaction body Blake2b-256; deterministic per-case synthetic Ed25519 signers derived in memory for repeatable fixtures; ordered raw-output payment credentials rebound; every serialized witness independently verified; no private bytes or seeds written",
        "conservation_rule": "sum resolved input lovelace equals output lovelace plus fee; minted singleton asset equals the output singleton asset",
        "positive_control": positive_manifest,
        "cases": records,
        "family_fixture_count": len(records),
        "executions": 0,
        "all_cases_pending": all(record["status"] == "PENDING" for record in records),
        "freeze_gate": "coordinator freezes exact family hashes and Agent C independently approves before any Aiken simulator invocation",
    }
    (OUTPUT / "FAMILY-MANIFEST.json").write_text(json.dumps(family_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_rows = []
    for path in sorted((item for item in OUTPUT.rglob("*")
                        if item.is_file() and item.name != "SHA256SUMS"),
                       key=lambda item: item.relative_to(OUTPUT).as_posix()):
        checksum_rows.append(f"{digest(path.read_bytes())}  {path.relative_to(OUTPUT).as_posix()}")
    (OUTPUT / "SHA256SUMS").write_text("\n".join(checksum_rows) + "\n", encoding="utf-8", newline="\n")
    return family_manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", required=True)
    args = parser.parse_args()
    print(json.dumps(build(), sort_keys=True))
