from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/GodOfAgents/code/VAMS-testnet")
SCRIPTS = ROOT / "scripts/remediation"
FIXTURES = ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1"
AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken")
EXPECTED_POLICY = "9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


public = load("f05_public_mutation_probe", SCRIPTS / "test_f05_2a_authority_bootstrap_public.py")
helper = load("f05_tx_sim_registry_probe", SCRIPTS / "f05_2a_tx_sim_registry.py")
runner = load("f05_tx_sim_runner_probe", SCRIPTS / "f05_2a_tx_sim_runner_r3.py")


def remove_seed(tx):
    body = tx[0]
    inputs = helper.map_get(body, 0)
    assert isinstance(inputs, helper.Tag) and inputs.number == 258
    datum = helper.map_get(helper.map_get(body, 1)[0], 2)
    assert datum[0] == 1 and isinstance(datum[1], helper.Tag) and datum[1].number == 24
    state = helper.roundtrip(datum[1].value)
    seed = [state.value[1], state.value[2]]
    kept = [item for item in inputs.value if item != seed]
    assert len(kept) == len(inputs.value) - 1 and kept
    helper.map_set(body, 0, helper.Tag(258, kept))
    return helper.dumps(tx)


def mutant_transaction(raw: bytes, mutant_id: bytes, mutant_code: bytes, missing_seed: bool) -> bytes:
    tx = helper.roundtrip(raw)
    body = tx[0]
    mint = helper.map_get(body, 9)
    assert len(mint.pairs) == 1 and mint.pairs[0][0].hex() == EXPECTED_POLICY
    base_id, assets = mint.pairs[0]
    helper.map_set(body, 9, helper.Map([(mutant_id, assets)]))
    for output in helper.map_get(body, 1):
        value = helper.map_get(output, 1)
        if isinstance(value, list) and len(value) == 2 and isinstance(value[1], helper.Map):
            if any(key == base_id for key, _ in value[1].pairs):
                value[1] = helper.Map([
                    (mutant_id if key == base_id else key, item)
                    for key, item in value[1].pairs
                ])
    witnesses = helper.map_get(tx[1], 7)
    assert isinstance(witnesses, helper.Tag) and witnesses.number == 258
    assert isinstance(witnesses.value, list) and len(witnesses.value) == 1
    helper.map_set(tx[1], 7, helper.Tag(258, [mutant_code]))
    if missing_seed:
        remove_seed(tx)
    return helper.dumps(tx)


def main() -> None:
    manifest_path = FIXTURES / "CANARY-MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == "91c7bc46476a391c3ea3e3012b2f9174a1b87f6e0253ce6167b4c7b96e47f95d"
    assert hashlib.sha256(AIKEN.read_bytes()).hexdigest() == manifest["runtimes"]["aiken-1.1.21"]["sha256"]
    assert EXPECTED_POLICY == manifest["target"]["applied_policy_id"]
    for name, expected in (
        ("applied-policy.cbor", manifest["target"]["applied_policy_cbor"]["sha256"]),
        ("raw_inputs.cbor", manifest["shared_vectors"]["raw_inputs.cbor"]),
        ("raw_outputs.cbor", manifest["shared_vectors"]["raw_outputs.cbor"]),
        ("valid.tx.cbor", manifest["canaries"][0]["sha256"]),
    ):
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == expected

    valid_path = FIXTURES / "valid.tx.cbor"
    original = valid_path.read_bytes()
    parsed = helper.roundtrip(original)
    body = parsed[0]
    refs = helper.map_get(body, 0)
    assert isinstance(refs, helper.Tag) and refs.number == 258
    state_datum = helper.map_get(helper.map_get(body, 1)[0], 2)
    state = helper.roundtrip(state_datum[1].value)
    seed_hash, seed_index, keys = state.value[1], state.value[2], state.value[4]
    assert refs.value[0] == [seed_hash, seed_index]
    params = {
        "genesis_ref": public._output_reference(seed_hash, seed_index),
        "initial_keys": public.list_data([public.byte_string(key) for key in keys]),
    }

    with tempfile.TemporaryDirectory(prefix="f05-unconditional-r3-mutation-") as temp:
        work = Path(temp)
        base = public._compile(ROOT / "cardano", AIKEN, work / "base", params)
        assert base["policy_id"].hex() == EXPECTED_POLICY
        mutant = public._compile(ROOT / "cardano", AIKEN, work / "mutant", params,
                                 "unconditional_success")
        mutant_id = mutant["policy_id"].hex()
        assert hashlib.blake2b(b"\x03" + mutant["code"], digest_size=28).hexdigest() == mutant_id

        baseline_missing = work / "baseline-seed-missing.tx.cbor"
        baseline_missing.write_bytes(remove_seed(helper.roundtrip(original)))
        mutant_valid = work / "mutant-valid.tx.cbor"
        mutant_valid.write_bytes(mutant_transaction(original, mutant["policy_id"],
                                                     mutant["code"], False))
        mutant_missing = work / "mutant-seed-missing.tx.cbor"
        mutant_missing.write_bytes(mutant_transaction(original, mutant["policy_id"],
                                                       mutant["code"], True))

        cases = []
        for case, tx_path, policy_id, expected_exit, expected_stage in (
            ("baseline_seed_missing", baseline_missing, EXPECTED_POLICY, 1, "compiled_evaluation"),
            ("mutant_valid", mutant_valid, mutant_id, 0, "script_accepted"),
            ("mutant_seed_missing", mutant_missing, mutant_id, 0, "script_accepted"),
        ):
            result = runner.run_snapshot_simulation(
                AIKEN, tx_path, FIXTURES / "raw_inputs.cbor",
                FIXTURES / "raw_outputs.cbor", policy_id,
            )
            assert result["wrapper_exit_code"] == 0, (case, result)
            assert result["simulator_child_exit"] == expected_exit, (case, result)
            assert result["simulator_result"] == {
                "stage": expected_stage, "target_script_invoked": True,
            }, (case, result)
            assert result["cleanup"]["status"] == "clean", (case, result)
            cases.append({
                "case": case,
                "wrapper_exit": result["wrapper_exit_code"],
                "simulator_child_exit": result["simulator_child_exit"],
                "classification": result["simulator_result"],
                "target_mint_binding": result["target_mint_binding"],
                "submitted_sha256": result["submitted_sha256"],
                "cleanup": result["cleanup"],
            })

        print(json.dumps({
            "status": "pass",
            "base_policy_id": EXPECTED_POLICY,
            "mutant_policy_id": mutant_id,
            "mutant_code_sha256": hashlib.sha256(mutant["code"]).hexdigest(),
            "cases": cases,
            "evidence_class": "synthetic_r3_transaction_simulator_mutation_probe",
            "registered_mutation_credit": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
