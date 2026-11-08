#!/usr/bin/env python3
"""Independent compiled public-entrypoint regressions for F04.

The accepted 49-row fixture is read-only input.  This module keeps a separate,
versioned mutation matrix and derives its expected outcomes from that matrix,
never from the production validator or its evaluator.  A disposable applied
blueprint is evaluated when the pinned Aiken binary is available.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "docs/remediation/m3_f04_fixtures_r1/FIXTURES.json"
MATRIX = Path(__file__).with_name("supplemental_cases.json")
BLUEPRINT = ROOT / "cardano/plutus.json"
REGISTRY = ROOT / "cardano/validators/agent_registry.ak"
AIKEN = Path(os.environ.get("AIKEN_BIN", "/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken"))
DOMAIN = b"VAMS/agent/v1\0"
MAX_U64 = (1 << 64) - 1


def cbor_head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([(major << 5) | n])
    if n < 256:
        return bytes([(major << 5) | 24, n])
    if n < 65536:
        return bytes([(major << 5) | 25]) + n.to_bytes(2, "big")
    if n < 2**32:
        return bytes([(major << 5) | 26]) + n.to_bytes(4, "big")
    return bytes([(major << 5) | 27]) + n.to_bytes(8, "big")


def cbor(value: dict) -> bytes:
    if "int" in value:
        n = value["int"]
        return cbor_head(0, n) if n >= 0 else cbor_head(1, -1 - n)
    if "bytes" in value:
        raw = bytes.fromhex(value["bytes"])
        return cbor_head(2, len(raw)) + raw
    if "list" in value:
        return b"\x9f" + b"".join(cbor(x) for x in value["list"]) + b"\xff"
    if "map" in value:
        pairs = sorted((cbor(p["k"]), cbor(p["v"])) for p in value["map"])
        return b"\xbf" + b"".join(k + v for k, v in pairs) + b"\xff"
    fields = b"\x9f" + b"".join(cbor(x) for x in value["fields"]) + b"\xff"
    return cbor_head(6, 121 + value["constructor"] if value["constructor"] < 7 else 1280 + value["constructor"] - 7) + fields


def uplc(value: dict) -> str:
    if "int" in value:
        return f"I {value['int']}"
    if "bytes" in value:
        return f"B #{value['bytes']}"
    if "list" in value:
        return "List [" + ", ".join(uplc(x) for x in value["list"]) + "]"
    if "map" in value:
        return "Map [" + ", ".join(f"({uplc(p['k'])}, {uplc(p['v'])})" for p in value["map"]) + "]"
    return f"Constr {value['constructor']} [" + ", ".join(uplc(x) for x in value["fields"]) + "]"


def walk_replace(value: object, old: str, new: str) -> None:
    if isinstance(value, dict):
        if value.get("bytes") == old:
            value["bytes"] = new
        for child in value.values():
            walk_replace(child, old, new)
    elif isinstance(value, list):
        for child in value:
            walk_replace(child, old, new)


def datum_fields(ctx: dict) -> list[dict]:
    output = ctx["fields"][0]["fields"][2]["list"][0]
    return output["fields"][2]["fields"][0]["fields"]


def tx(ctx: dict) -> dict:
    return ctx["fields"][0]


def value_map(output: dict) -> dict:
    return output["fields"][1]


def set_lovelace(output: dict, amount: int) -> None:
    for policy in value_map(output)["map"]:
        if policy["k"].get("bytes") == "":
            policy["v"]["map"][0]["v"] = {"int": amount}
            return
    raise AssertionError("fixture output has no lovelace entry")


def set_token(output: dict, policy_id: str, asset_name: str, quantity: int) -> None:
    for policy in value_map(output)["map"]:
        if policy["k"].get("bytes") == policy_id:
            if policy["v"]["map"]:
                policy["v"]["map"][0]["k"] = {"bytes": asset_name}
                policy["v"]["map"][0]["v"] = {"int": quantity}
            else:
                policy["v"]["map"].append({"k": {"bytes": asset_name}, "v": {"int": quantity}})
            return
    value_map(output)["map"].append({"k": {"bytes": policy_id}, "v": {"map": [{"k": {"bytes": asset_name}, "v": {"int": quantity}}]}})


def identity_name(did: bytes, owner: bytes) -> str:
    # The applied bootstrap parameter is the frozen 1111...:7 reference.
    seed_tx = bytes.fromhex("11" * 32)
    seed_index = (7).to_bytes(4, "big")
    return hashlib.blake2b(DOMAIN + len(did).to_bytes(2, "big") + did + owner + seed_tx + seed_index, digest_size=32).hexdigest()


def register_mint_context(rows: dict) -> dict:
    return copy.deepcopy(next(e for e in rows["register_valid"]["evaluations"] if e["entrypoint"].endswith(".mint"))["script_context"]["data"])


def burn_mint_context(rows: dict) -> dict:
    return copy.deepcopy(next(e for e in rows["deregister_valid"]["evaluations"] if e["entrypoint"].endswith(".mint"))["script_context"]["data"])


def mutate_context(case_id: str, rows: dict) -> dict:
    if case_id.startswith("mint_"):
        ctx = register_mint_context(rows)
        fields = datum_fields(ctx)
        output = tx(ctx)["fields"][2]["list"][0]
        old_did = fields[4]["bytes"]
        owner = bytes.fromhex(fields[5]["bytes"])
        old_token = fields[2]["bytes"]
        if case_id in {"mint_did_31", "mint_did_32", "mint_did_256", "mint_did_257"}:
            size = {"mint_did_31": 31, "mint_did_32": 32, "mint_did_256": 256, "mint_did_257": 257}[case_id]
            did = bytes([0x61]) * size
            token = identity_name(did, owner)
            walk_replace(ctx, old_did, did.hex())
            walk_replace(ctx, old_token, token)
        elif case_id == "mint_malformed_utf8":
            did = bytes([0xFF]) * 32
            walk_replace(ctx, old_did, did.hex())
            walk_replace(ctx, old_token, identity_name(did, owner))
        elif case_id == "mint_incomplete_datum":
            fields.pop()
        elif case_id == "mint_bootstrap_parameter_mismatch":
            tx(ctx)["fields"][0]["list"][1]["fields"][0]["fields"][0]["bytes"] = "aa" * 32
        elif case_id == "mint_transformed_did_token":
            transformed = bytes.fromhex(old_did).hex().encode()
            fields[4]["bytes"] = transformed.hex()
            ctx["fields"][1]["fields"][0]["bytes"] = transformed.hex()
        elif case_id == "mint_redeemer_did_mismatch":
            ctx["fields"][1]["fields"][0]["bytes"] = "62" * 32
        elif case_id == "mint_redeemer_owner_mismatch":
            ctx["fields"][1]["fields"][1]["bytes"] = "aa" * 28
        elif case_id.startswith("mint_metadata_"):
            amount = int(case_id.rsplit("_", 1)[1])
            fields[9]["bytes"] = ("bb" * amount)
        elif case_id.startswith("mint_nonce_"):
            fields[3]["int"] = MAX_U64 if case_id.endswith("max") else MAX_U64 + 1
        elif case_id.startswith("mint_stake_"):
            amount = MAX_U64 if case_id.endswith("max") else MAX_U64 + 1
            fields[7]["int"] = amount
            set_lovelace(output, amount)
        elif case_id.startswith("mint_epoch_"):
            fields[11]["int"] = MAX_U64 if case_id.endswith("max") else MAX_U64 + 1
        elif case_id.startswith("mint_registered_at_"):
            fields[12]["int"] = MAX_U64 if case_id.endswith("max") else MAX_U64 + 1
        return ctx

    ctx = burn_mint_context(rows)
    inputs = tx(ctx)["fields"][0]["list"]
    linked = inputs[0]
    input_output = linked["fields"][1]
    input_datum = input_output["fields"][2]["fields"][0]["fields"]
    policy = input_datum[1]["bytes"]
    token = input_datum[2]["bytes"]
    if case_id == "burn_malformed_datum":
        input_datum.pop()
    elif case_id == "burn_wrong_registry_credential":
        input_output["fields"][0]["fields"][0]["fields"][0]["bytes"] = "aa" * 28
    elif case_id == "burn_token_not_rederived":
        walk_replace(ctx, token, "00" * 32)
    elif case_id == "burn_bootstrap_token_mismatch":
        walk_replace(ctx, token, "01" * 32)
    elif case_id == "burn_policy_mismatch":
        ctx["fields"][2]["fields"][0]["bytes"] = "aa" * 28
    elif case_id == "burn_unlinked_input":
        extra = copy.deepcopy(linked)
        extra["fields"][0]["fields"][0]["bytes"] = "aa" * 32
        inputs.append(extra)
    elif case_id == "burn_resurrection_output":
        output = copy.deepcopy(tx(ctx)["fields"][2]["list"][0])
        set_token(output, policy, token, 1)
        tx(ctx)["fields"][2]["list"].append(output)
    return ctx


def apply_parameters(aiken: Path, folder: Path) -> tuple[dict[str, bytes], str]:
    blueprint = json.loads(BLUEPRINT.read_text())
    params = json.loads(FIXTURE.read_text())["rows"][0]["parameters"]["data"]["fields"]
    previous = folder / "0.json"
    shutil.copyfile(BLUEPRINT, previous)
    for index, value in enumerate(params, 1):
        target = folder / f"{index}.json"
        run = subprocess.run([str(aiken), "blueprint", "apply", "-i", str(previous), "-o", str(target), "-m", "agent_registry", "-v", "agent_registry", cbor(value).hex()], capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError("pinned blueprint parameter application failed")
        previous = target
    applied = json.loads(previous.read_text())
    entries = {entry["title"]: entry for entry in applied["validators"]}
    policy = subprocess.run(
        [str(aiken), "blueprint", "policy", "-i", str(previous), "-m", "agent_registry", "-v", "agent_registry", str(ROOT / "cardano")],
        capture_output=True, text=True, check=True,
    )
    matches = re.findall(r"\b[0-9a-f]{56}\b", policy.stdout + policy.stderr)
    if not matches:
        raise AssertionError("current applied policy hash missing")
    return ({name: bytes.fromhex(entries[name]["compiledCode"]) for name in ("agent_registry.agent_registry.mint", "agent_registry.agent_registry.spend")}, matches[-1])


def evaluate(aiken: Path, code: bytes, context: dict, folder: Path, label: str) -> bool:
    code_path = folder / f"{label}.cbor"
    code_path.write_bytes(code)
    decoded = subprocess.run([str(aiken), "uplc", "decode", "-c", str(code_path)], capture_output=True, text=True, check=True).stdout
    prefix = "(program\n  1.1.0\n"
    if not decoded.startswith(prefix):
        raise RuntimeError("unexpected UPLC prefix")
    term = decoded[len(prefix):-2]
    source = folder / f"{label}.uplc"
    source.write_text(prefix + f"[ {term} (con data ({uplc(context)})) ]\n)\n")
    run = subprocess.run([str(aiken), "uplc", "eval", "-d", str(source)], capture_output=True, text=True)
    return run.returncode == 0 and "(con unit ())" in run.stdout


class SupplementalMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads(MATRIX.read_text())
        cls.fixture = json.loads(FIXTURE.read_text())
        cls.rows = {row["id"]: row for row in cls.fixture["rows"]}

    def test_matrix_is_independent_and_complete(self):
        self.assertEqual(self.matrix["source_fixture_contract"], "49 rows / 67 evaluations; immutable for this matrix")
        cases = self.matrix["cases"]
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        self.assertEqual({case["id"] for case in cases}, {
            "mint_did_31", "mint_did_32", "mint_did_256", "mint_did_257", "mint_malformed_utf8",
            "mint_incomplete_datum", "mint_bootstrap_parameter_mismatch", "mint_transformed_did_token",
            "mint_redeemer_did_mismatch", "mint_redeemer_owner_mismatch", "mint_metadata_31", "mint_metadata_32",
            "mint_metadata_33", "mint_nonce_max", "mint_nonce_max_plus_one", "mint_stake_max", "mint_stake_max_plus_one",
            "mint_epoch_max", "mint_epoch_max_plus_one", "mint_registered_at_max", "mint_registered_at_max_plus_one",
            "burn_malformed_datum", "burn_wrong_registry_credential", "burn_token_not_rederived", "burn_bootstrap_token_mismatch",
            "burn_policy_mismatch", "burn_unlinked_input", "burn_resurrection_output",
        })
        self.assertEqual(len(self.fixture["rows"]), 49)
        self.assertEqual(sum(len(row["evaluations"]) for row in self.fixture["rows"]), 67)
        self.assertEqual(
            hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "18e2252e38d474c13ffece96b78bc0ee18d50b7327636f57be289063312fa224",
        )

    def test_mutations_are_independently_constructible(self):
        for case in self.matrix["cases"]:
            context = mutate_context(case["id"], self.rows)
            self.assertIsInstance(context, dict, case["id"])
            self.assertEqual(case["expected"], "accept" if case["id"] in {"mint_did_32", "mint_did_256", "mint_metadata_32", "mint_nonce_max", "mint_stake_max", "mint_epoch_max", "mint_registered_at_max"} else "reject")

    def test_each_new_case_has_an_explicit_contract_guard(self):
        source = REGISTRY.read_text()
        markers = {
            "did_length_lower_bound": "size >= min_did_length",
            "did_length_lower_bound_control": "size >= min_did_length",
            "did_length_upper_bound_control": "size <= max_did_length",
            "did_length_upper_bound": "size <= max_did_length",
            "did_utf8_validity": "bytearray.from_string(bytearray.to_string(did)) == did",
            "complete_datum": "valid_datum(datum)",
            "burn_complete_datum": "valid_datum(datum)",
            "bootstrap_parameter_binding": "list.length(list.filter(tx.inputs, fn(input) { input.output_reference == bootstrap_ref })) == 1",
            "raw_did_identity_binding": "derive_identity_name(datum.did, datum.owner, bootstrap_ref) == asset_name",
            "burn_deterministic_identity": "derive_identity_name(datum.did, datum.owner, bootstrap_ref) == asset_name",
            "burn_bootstrap_binding": "derive_identity_name(datum.did, datum.owner, bootstrap_ref) == asset_name",
            "redeemer_output_did_binding": "datum.did == did",
            "redeemer_output_owner_binding": "datum.owner == owner_vkh",
            "metadata_hash_lower_bound": "bytearray.length(datum.metadata_hash) == digest_bytes",
            "metadata_hash_exact_length_control": "bytearray.length(datum.metadata_hash) == digest_bytes",
            "metadata_hash_upper_bound": "bytearray.length(datum.metadata_hash) == digest_bytes",
            "nonce_u64_max_control": "datum.nonce <= max_u64",
            "nonce_u64_upper_bound": "datum.nonce <= max_u64",
            "stake_u64_max_control": "datum.stake_lovelace <= max_u64",
            "stake_u64_upper_bound": "datum.stake_lovelace <= max_u64",
            "epoch_u64_max_control": "datum.action_epoch <= max_u64",
            "epoch_u64_upper_bound": "datum.action_epoch <= max_u64",
            "registered_at_u64_max_control": "datum.registered_at_ms <= max_u64",
            "registered_at_u64_upper_bound": "datum.registered_at_ms <= max_u64",
            "burn_registry_credential": "script_hash == policy_id",
            "burn_policy_binding": "identity_asset_name == asset_name",
            "burn_linked_input": "list.length(list.filter(tx.inputs, fn(input) {",
            "burn_no_resurrection": "list.length(list.filter(tx.outputs, fn(output) {",
        }
        for case in self.matrix["cases"]:
            self.assertIn(case["guard"], markers)
            self.assertIn(markers[case["guard"]], source, case["id"])

    @unittest.skipUnless(AIKEN.exists(), "pinned Aiken 1.1.21 is not available")
    def test_every_supplemental_case_against_applied_public_entrypoint(self):
        folder = Path(tempfile.mkdtemp(prefix="m3-f04-supplemental-"))
        try:
            codes, applied_policy = apply_parameters(AIKEN, folder)
            self.assertRegex(applied_policy, r"^[0-9a-f]{56}$")
            actual = {}
            for case in self.matrix["cases"]:
                context = mutate_context(case["id"], self.rows)
                accepted = evaluate(AIKEN, codes["agent_registry.agent_registry.mint"], context, folder, case["id"])
                actual[case["id"]] = "accept" if accepted else "reject"
            expected = {case["id"]: case["expected"] for case in self.matrix["cases"]}
            self.assertEqual(actual, expected)
        finally:
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
