#!/usr/bin/env python3
"""Build deterministic, test-only transaction fixtures for mint-map exactness.

Writes a positive control and three single-assertion mutations. Does not invoke
the simulator and does not persist any test signing key material.
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
WRONG_NAME = b"VAMS-F05-AUTH-V4"
EXTRA_NAME = b"VAMS-F05-EXTRA"
CASE_IDS = ("mint_wrong_name", "mint_quantity_two", "mint_extra_name")
FAMILY_ID = "mint_map_exactness"
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


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_map(codec: Any, value: Any, key: Any, replacement: Any) -> Any:
    positions = [i for i, (candidate, _) in enumerate(value.pairs) if candidate == key]
    if len(positions) != 1:
        raise ValueError(f"map key {key!r} is not unique")
    pairs = list(value.pairs)
    pairs[positions[0]] = (key, replacement)
    return codec.M(tuple(pairs))


def set_asset_map(codec: Any, multiasset: Any, asset_map: Any) -> Any:
    if not isinstance(multiasset, codec.M):
        raise ValueError("expected multiasset map")
    return replace_map(codec, multiasset, codec.B(POLICY_ID), asset_map)


def set_tx_mint(codec: Any, tx: list[Any], case_id: str) -> None:
    mint = codec.get(tx[0], 9)
    if not isinstance(mint, codec.M) or len(mint.pairs) != 1:
        raise ValueError("expected singleton policy mint map")
    token_map = mint.pairs[0][1]
    if not isinstance(token_map, codec.M) or token_map.pairs != ((codec.B(TOKEN_NAME), 1),):
        raise ValueError("base mint does not contain exactly authority NFT quantity one")
    if case_id == "mint_wrong_name":
        changed_tokens = codec.M(((codec.B(WRONG_NAME), 1),))
    elif case_id == "mint_quantity_two":
        changed_tokens = codec.M(((codec.B(TOKEN_NAME), 2),))
    elif case_id == "mint_extra_name":
        changed_tokens = codec.M(tuple(sorted(((codec.B(TOKEN_NAME), 1), (codec.B(EXTRA_NAME), 1)), key=lambda pair: pair[0].value)))
    else:
        raise ValueError(f"unknown case {case_id}")
    tx[0] = replace_map(codec, tx[0], 9, set_asset_map(codec, mint, changed_tokens))


def set_authority_output_assets(codec: Any, tx: list[Any], case_id: str) -> None:
    body = tx[0]
    outputs = codec.get(body, 1)
    if type(outputs) is not list or len(outputs) != 2:
        raise ValueError("expected authority plus sponsor output")
    authority = outputs[0]
    value = codec.get(authority, 1)
    if type(value) is not list or len(value) != 2 or not isinstance(value[1], codec.M):
        raise ValueError("expected lovelace plus multiasset authority value")
    assets = value[1]
    token_map = codec.get(assets, codec.B(POLICY_ID))
    if not isinstance(token_map, codec.M) or token_map.pairs != ((codec.B(TOKEN_NAME), 1),):
        raise ValueError("base authority output does not contain exactly the authority NFT")
    if case_id == "mint_wrong_name":
        changed_tokens = codec.M(((codec.B(WRONG_NAME), 1),))
    elif case_id == "mint_quantity_two":
        changed_tokens = codec.M(((codec.B(TOKEN_NAME), 2),))
    elif case_id == "mint_extra_name":
        changed_tokens = codec.M(tuple(sorted(((codec.B(TOKEN_NAME), 1), (codec.B(EXTRA_NAME), 1)), key=lambda pair: pair[0].value)))
    else:
        raise ValueError(f"unknown case {case_id}")
    changed_value = [value[0], set_asset_map(codec, assets, changed_tokens)]
    changed_authority = replace_map(codec, authority, 1, changed_value)
    new_outputs = list(outputs)
    new_outputs[0] = changed_authority
    tx[0] = replace_map(codec, body, 1, new_outputs)


def mutate(codec: Any, tx: list[Any], case_id: str) -> None:
    set_tx_mint(codec, tx, case_id)
    set_authority_output_assets(codec, tx, case_id)


def funding_keys(case_id: str, count: int):
    result = []
    for index in range(count):
        seed = hashlib.sha256(b"VAMS-F05-2A-R4-LOCAL-FIXTURE-ONLY\0" + case_id.encode("ascii") + b"\0" + index.to_bytes(2, "big")).digest()
        private = Ed25519PrivateKey.from_private_bytes(seed)
        public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        result.append((private, public))
    return result


def resign(codec: Any, tx: list[Any], raw_outputs: list[Any], case_id: str):
    if type(raw_outputs) is not list or len(raw_outputs) != 2:
        raise ValueError("expected two ordered resolved funding inputs")
    keys = funding_keys(case_id, len(raw_outputs))
    for index, (utxo, (_, public)) in enumerate(zip(raw_outputs, keys, strict=True)):
        pairs = list(utxo.pairs)
        positions = [i for i, (key, _) in enumerate(pairs) if key == 0]
        if len(positions) != 1:
            raise ValueError("resolved funding UTxO lacks unique payment address")
        address = b"\x60" + hashlib.blake2b(public, digest_size=28).digest()
        pairs[positions[0]] = (0, codec.B(address))
        raw_outputs[index] = codec.M(tuple(pairs))
    body_hash = hashlib.blake2b(codec.enc(tx[0]), digest_size=32).digest()
    witnesses = []
    for private, public in keys:
        sig = private.sign(body_hash)
        Ed25519PublicKey.from_public_bytes(public).verify(sig, body_hash)
        witnesses.append([codec.B(public), codec.B(sig)])
    witnesses.sort(key=lambda row: row[0].value)
    old = codec.get(tx[1], 0)
    if not isinstance(old, codec.T) or old.tag != 258:
        raise ValueError("base fixture lacks vkey witness set")
    tx[1] = replace_map(codec, tx[1], 0, codec.T(258, witnesses))
    encoded = codec.enc(tx)
    reread = codec.parse(encoded)
    actual_body = hashlib.blake2b(codec.enc(reread[0]), digest_size=32).digest()
    if actual_body != body_hash:
        raise ValueError("serialized transaction body hash changed")
    serialized = codec.get(reread[1], 0)
    if not isinstance(serialized, codec.T) or serialized.tag != 258:
        raise ValueError("serialized witnesses malformed")
    for pub, sig in serialized.value:
        Ed25519PublicKey.from_public_bytes(pub.value).verify(sig.value, body_hash)
    return encoded, codec.enc(raw_outputs), body_hash.hex(), len(serialized.value)


def conservation(codec: Any, tx: list[Any], raw_outputs: list[Any]) -> dict[str, Any]:
    inputs_lovelace = sum(codec.get(utxo, 1) for utxo in raw_outputs)
    outputs = codec.get(tx[0], 1)
    outputs_lovelace = sum(value if type(value) is int else value[0] for value in (codec.get(out, 1) for out in outputs))
    fee = codec.get(tx[0], 2)
    if inputs_lovelace != outputs_lovelace + fee:
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
        raise ValueError("minted/output native asset conservation failed")
    return {"input_lovelace": inputs_lovelace, "output_lovelace": outputs_lovelace, "fee_lovelace": fee,
            "lovelace_conserved": True, "minted_output_assets_match": True,
            "minted_assets": {f"{pid.hex()}.{name.hex()}": qty for (pid, name), qty in minted_assets.items()},
            "output_assets": {f"{pid.hex()}.{name.hex()}": qty for (pid, name), qty in output_assets.items()}}


def build() -> dict[str, Any]:
    codec = load_codec()
    if sha(REGISTRY_PATH.read_bytes()) != REGISTRY_SHA256 or sha(CONTRACT_PATH.read_bytes()) != CONTRACT_SHA256:
        raise ValueError("accepted registry or R2 contract digest mismatch")
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    accepted = {row["id"]: row for row in registry["negative_cases"]}
    contracted = {row["id"]: row for row in contract["negative_cases"]}
    if any(case not in accepted or case not in contracted for case in CASE_IDS):
        raise ValueError("mint family IDs absent from accepted registry or evidence contract")
    paths = {"transaction": BASE / "valid.tx.cbor", "raw_inputs": BASE / "raw_inputs.cbor", "raw_outputs": BASE / "raw_outputs.cbor"}
    base = {role: path.read_bytes() for role, path in paths.items()}
    if {role: sha(raw) for role, raw in base.items()} != BASE_HASHES:
        raise ValueError("accepted positive fixture hashes do not match")
    if any(codec.enc(codec.parse(raw)) != raw for raw in base.values()):
        raise ValueError("accepted positive CBOR is not canonical")

    positive_dir = OUTPUT / "positive_control"
    positive_dir.mkdir(parents=True, exist_ok=True)
    positive_files = {}
    for role, raw in base.items():
        filename = "transaction.cbor" if role == "transaction" else role + ".cbor"
        target = positive_dir / filename
        target.write_bytes(raw)
        positive_files[role] = {"path": target.relative_to(OUTPUT).as_posix(), "sha256": sha(raw), "size_bytes": len(raw)}
    positive = {"schema_version": "f05-2a-r4-family-positive-control-v1", "id": "valid_positive_control", "family_id": FAMILY_ID,
                "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID.hex(), "applied_script_hash": POLICY_ID.hex()},
                "files": positive_files, "source": "accepted typed positive control copied byte-for-byte",
                "funding_witnesses": "accepted base-witness set; byte-identical copy", "expected_result": "accept control",
                "status": "control-only; no new simulator execution"}
    (positive_dir / "CASE-MANIFEST.json").write_text(json.dumps(positive, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    deltas = {
        "mint_wrong_name": "rename the minted authority token and matching authority-output asset to VAMS-F05-AUTH-V4; all minted/output quantities remain equal",
        "mint_quantity_two": "change only the authority NFT quantity from one to two in both mint and authority output; ledger asset conservation remains exact",
        "mint_extra_name": "add one extra policy asset name to both mint and authority output; singleton amount and every other field remain unchanged",
    }
    cases = []
    for case_id in CASE_IDS:
        tx = codec.parse(base["transaction"])
        raw_inputs = codec.parse(base["raw_inputs"])
        raw_outputs = codec.parse(base["raw_outputs"])
        mutate(codec, tx, case_id)
        tx_bytes, output_bytes, body_hash, witness_count = resign(codec, tx, raw_outputs, case_id)
        inputs_bytes = codec.enc(raw_inputs)
        final_tx, final_inputs, final_outputs = codec.parse(tx_bytes), codec.parse(inputs_bytes), codec.parse(output_bytes)
        if codec.enc(final_tx) != tx_bytes or codec.enc(final_inputs) != inputs_bytes or codec.enc(final_outputs) != output_bytes:
            raise ValueError("fixture failed canonical CBOR roundtrip")
        conservation_result = conservation(codec, final_tx, final_outputs)
        folder = OUTPUT / "cases" / case_id
        folder.mkdir(parents=True, exist_ok=True)
        contents = {"transaction": tx_bytes, "raw_inputs": inputs_bytes, "raw_outputs": output_bytes}
        file_manifest = {}
        for role, raw in contents.items():
            filename = "transaction.cbor" if role == "transaction" else role + ".cbor"
            path = folder / filename
            path.write_bytes(raw)
            file_manifest[role] = {"path": path.relative_to(OUTPUT).as_posix(), "sha256": sha(raw), "size_bytes": len(raw)}
        contract_row = contracted[case_id]
        record = {"schema_version": "f05-2a-r4-family-case-v1", "id": case_id, "family_id": FAMILY_ID,
                  "registry_assertion": contract_row["verifier_property"], "original_registry_assertion": contract_row["original_assertion"],
                  "expected_result": contract_row["expected_result"], "delta": deltas[case_id],
                  "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID.hex(), "applied_script_hash": POLICY_ID.hex()},
                  "files": file_manifest, "transaction_body_hash_blake2b_256": body_hash,
                  "funding_witnesses": {"count": witness_count, "verified_against_serialized_body": True, "private_material_persisted": False},
                  "conservation": conservation_result, "script_invoked": False,
                  "simulator_result": "not run pending independent family review and coordinator freeze", "status": "PENDING"}
        (folder / "CASE-MANIFEST.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        cases.append(record)

    manifest = {"schema_version": "f05-2a-r4-transaction-family-manifest-v1", "family_id": FAMILY_ID,
                "status": "fixtures prepared; pending independent review; no simulator execution",
                "accepted_registry": {"path": REGISTRY_PATH.relative_to(ROOT).as_posix(), "sha256": REGISTRY_SHA256},
                "r2_contract": {"path": CONTRACT_PATH.relative_to(ROOT).as_posix(), "sha256": CONTRACT_SHA256},
                "base_positive_hashes": BASE_HASHES, "target": {"purpose": "Mint[0]", "policy_id": POLICY_ID.hex(), "applied_script_hash": POLICY_ID.hex()},
                "funding_signature_method": "Blake2b-256 of exact serialized body; deterministic synthetic test-only Ed25519 signers derived in memory per case; resolved funding payment credentials rebound; serialized witnesses reverified; no private material persisted",
                "conservation_rule": "resolved inputs equal outputs plus fee, and every minted asset name/quantity equals aggregate output assets",
                "positive_control": positive, "cases": cases, "family_fixture_count": len(cases), "executions": 0,
                "all_cases_pending": all(row["status"] == "PENDING" for row in cases),
                "freeze_gate": "coordinator freezes exact family hashes and Agent C independently approves before simulator invocation"}
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
