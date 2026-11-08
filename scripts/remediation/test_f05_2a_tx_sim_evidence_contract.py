from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("f05_2a_tx_sim_evidence_contract.py")
SPEC = importlib.util.spec_from_file_location("f05_2a_tx_sim_evidence_contract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_binding_runner_rejects_wrong_policy_and_unbound_false_positive(tmp_path: Path, monkeypatch) -> None:
    cb = MODULE._cbor_helpers()
    script = bytes.fromhex("aabbcc")
    with pytest.raises(ValueError):
        cb.classify_tx_sim_result(
            {"exit": 1, "stdout": "Evaluating Mint[0] failed script execution", "stderr": ""},
            cb.dumps([cb.Map([(9, cb.Map([(b"\\xff" * 28, cb.Map([]))]))]),
                      cb.Map([(7, cb.Tag(258, [b"bad"]))]), True, None]), MODULE.POLICY_HASH,
        )
    false_positive = cb.classify_tx_sim_result(
        {"exit": 1, "stdout": "Parsing script context failed script execution", "stderr": ""},
        cb.dumps(cb.loads((MODULE.ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1/valid.tx.cbor").read_bytes())),
        MODULE.POLICY_HASH,
    )
    assert false_positive["target_script_invoked"] is False
    policy_id = __import__("hashlib").blake2b(b"\x03" + script, digest_size=28).digest()
    tx = [cb.Map([(9, cb.Map([(policy_id, cb.Map([]))]))]),
          cb.Map([(7, cb.Tag(258, [script]))]), True, None]
    assert MODULE.verify_mint_binding(cb.dumps(tx), policy_id.hex())["bound"]
    duplicate_mint = [cb.Map([(9, cb.Map([(policy_id, cb.Map([])), (policy_id, cb.Map([]))]))]),
                      cb.Map([(7, cb.Tag(258, [script]))]), True, None]
    with pytest.raises(ValueError):
        MODULE.verify_mint_binding(cb.dumps(duplicate_mint), policy_id.hex())
    accepted_tx = MODULE.ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1/valid.tx.cbor"
    accepted_bytes = accepted_tx.read_bytes()
    assert MODULE.verify_mint_binding(accepted_bytes, MODULE.POLICY_HASH)["bound"]
    with pytest.raises(ValueError):
        MODULE.verify_mint_binding(cb.dumps(tx), "ff" * 28)
    wrong_witness = [cb.Map([(9, cb.Map([(bytes.fromhex(MODULE.POLICY_HASH), cb.Map([]))]))]),
                     cb.Map([(7, cb.Tag(258, [b"not-the-bound-policy-script"]))]), True, None]
    with pytest.raises(ValueError, match="witness script hash mismatch"):
        MODULE.verify_mint_binding(cb.dumps(wrong_witness), MODULE.POLICY_HASH)

    calls = []
    monkeypatch.setattr(MODULE.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    bad_tx = tmp_path / "unbound.tx.cbor"
    bad_tx.write_bytes(cb.dumps(tx))
    with pytest.raises(ValueError):
        MODULE.run_bound_simulation(Path("aiken"), bad_tx, Path("inputs.cbor"),
                                   Path("outputs.cbor"), "ff" * 28)
    assert calls == [], "unbound tx must not reach simulator, regardless of claimed/logged failure"

    from types import SimpleNamespace
    monkeypatch.setattr(
        MODULE.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="Parsing script context Evaluating Mint[0] failed script execution",
            stderr="",
        ),
    )
    result = MODULE.run_bound_simulation(
        Path("pinned-aiken"), accepted_tx,
        MODULE.ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1/raw_inputs.cbor",
        MODULE.ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1/raw_outputs.cbor",
        MODULE.POLICY_HASH,
    )
    assert result["stage"] == "indeterminate"
    assert result["target_script_invoked"] is False
    assert result["simulator_exit"] == 1


def test_static_contract_generation_is_deterministic_and_preserves_registry_identity(tmp_path: Path) -> None:
    registry = MODULE.REGISTRY
    original = registry.read_bytes()
    output = tmp_path / "contract.json"
    MODULE.write_contract(output, registry)
    output_bytes = output.read_bytes()
    contract = MODULE.generate(registry)
    assert output_bytes == (json.dumps(contract, indent=2, sort_keys=True) + "\n").encode()
    assert registry.read_bytes() == original
    source = json.loads(original)
    negatives, mutations = contract["negative_cases"], contract["compiled_mutations"]
    assert len(negatives) == 55 and len(mutations) == 21
    assert [r["id"] for r in negatives] == [r["id"] for r in source["negative_cases"]]
    assert [r["mutation"] for r in negatives] == [r["mutation"] for r in source["negative_cases"]]
    assert all(r["original_assertion"]["value"] == source["expected"]["every_negative_case"] for r in negatives)
    assert [r["id"] for r in mutations] == source["compiled_mutations"]
    assert all(r["paired_negative_id"] and r["source_guard_before"] and r["mutant_replacement"] for r in mutations)
    assert set(MODULE.MUTATION_PAIRS) == set(source["compiled_mutations"])
    assert set(MODULE.MUTATION_GUARDS) == set(source["compiled_mutations"])
    assert all(r["expected_result"] == {"baseline": "reject", "matching_mutant": "accept"} for r in mutations)
    assert all(r["status"] == "PENDING" for r in negatives)
    historical_33 = next(r for r in negatives if r["id"] == "authority_value_minus_one")
    assert historical_33["historical_evidence_ref"] and "reconciliation" in historical_33["status_reason"]
    assert all(r["status"] == "PENDING" for r in mutations)
    required = {"executor", "expected_result", "evidence_ref", "status", "target_policy_hash"}
    assert all(required <= set(r) for r in negatives + mutations)
    assert all(r["verifier_property"] is not None for r in negatives if r["category"] != "routing_noninvoking")
    assert all(r["executor"] and r["evidence_ref"] and r["expected_result"] for r in mutations)
    assert next(r for r in negatives if r["id"] == "mint_wrong_policy")["target_policy_hash"] is None
    assert "non-invoking" in next(r for r in negatives if r["id"] == "mint_wrong_policy")["target_policy_hash_note"]
    unbound_mutations = {"remove_key_uniqueness_order_guard", "remove_key_order_guard",
                         "remove_singleton_quantity_guard"}
    assert all(r["target_policy_hash"] is None for r in mutations if r["id"] in unbound_mutations)
    assert all(r["target_policy_hash"] == MODULE.POLICY_HASH for r in mutations if r["id"] not in unbound_mutations)
    assert all(r["mutant_policy_hash"] is None for r in mutations)
    assert all(r["original_assertion"]["baseline_value"] == source["expected"]["every_negative_case"] for r in mutations)
    assert all(r["expected_result"] == {"baseline": "reject", "matching_mutant": "accept"} for r in mutations)
    existing = tmp_path / "existing.json"
    existing.write_text("keep")
    with pytest.raises(FileExistsError):
        MODULE.write_contract(existing, registry)
    assert existing.read_text() == "keep"
    with pytest.raises(SystemExit, match="exact authorized contract path"):
        MODULE.main_with_args(["--output", str(tmp_path / "outside.json")])
    assert not (tmp_path / "outside.json").exists()
    assert sum(r["category"] == "ledger_tx_sim" for r in negatives) == 51
    assert {r["id"] for r in negatives if r["category"] == "context_only"} == {
        "seed_duplicate", "authority_output_duplicate_nft", "authority_output_quantity_two"
    }
    assert all(r["target_ref"] and r["target_policy_hash"] for r in negatives if r["category"] == "context_only")
    assert {r["id"] for r in negatives if r["category"] == "routing_noninvoking"} == {"mint_wrong_policy"}
    assert {r["id"] for r in mutations if r["category"] == "alternate_parameter_mutation"} == {
        "remove_key_uniqueness_order_guard", "remove_key_order_guard"
    }
    assert next(r for r in negatives if r["id"] == "r2_wrong_state_address")["preservation_delta"]
    assert {r["id"] for r in negatives if r["id"] in MODULE.APPLIED_PARAMETER_CASES} == MODULE.APPLIED_PARAMETER_CASES
    for applied in (r for r in negatives if r["id"] in MODULE.APPLIED_PARAMETER_CASES):
        assert applied["compiled_target_policy_id"] is None and applied["target_policy_hash"] is None
        assert applied["status"] == "PENDING"
        assert "parameter-derived" in applied["target_policy_hash_note"]
    assert all(r["mutant_policy_id"] is None for r in mutations)
    assert sum(r["category"] == "canonical_guard_mutation" for r in mutations) == 17
    assert sum(r["category"] == "alternate_parameter_mutation" for r in mutations) == 2
    assert sum(r["category"] == "context_only_mutation" for r in mutations) == 1
    assert sum(r["category"] == "composite_mutation" for r in mutations) == 1
