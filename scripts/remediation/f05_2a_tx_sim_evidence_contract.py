#!/usr/bin/env python3
"""Emit deterministic F05.2a test-only evidence contract rows from the accepted fixture registry."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
POLICY_HASH = "9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
APPLIED_PARAMETER_CASES = frozenset({
    "applied_genesis_parameter", "applied_keys_parameter",
    "applied_keys_bad_count", "applied_keys_bad_length",
    "applied_keys_duplicate", "applied_keys_unsorted",
})
CONTEXT = {
    "seed_duplicate": "duplicate input reference is rejected by ledger input-set rules",
    "authority_output_duplicate_nft": "duplicate NFT-bearing outputs violate single-mint native-asset conservation",
    "authority_output_quantity_two": "output quantity two violates conservation against a mint quantity of one",
}
MUTATION_PAIRS = {
    "unconditional_success": "seed_missing",
    "remove_seed_guard": "seed_missing",
    "remove_exact_mint_guard": "mint_extra_name",
    "remove_target_output_cardinality_guard": "authority_output_extra_target",
    "remove_state_validator_credential_binding": "r2_wrong_state_address",
    "remove_no_stake_credential_guard": "output_stake_credential",
    "remove_singleton_quantity_guard": "authority_output_quantity_two",
    "remove_exact_lovelace_guard": "authority_value_minus_one",
    "remove_no_extra_asset_guard": "authority_extra_native_asset",
    "remove_inline_datum_guard": "datum_missing",
    "remove_schema_version_guard": "datum_schema_version",
    "remove_seed_hash_guard": "seed_datum_hash",
    "remove_seed_index_guard": "seed_datum_index",
    "remove_epoch_guard": "datum_epoch",
    "remove_key_uniqueness_order_guard": "applied_keys_duplicate",
    "remove_key_order_guard": "applied_keys_unsorted",
    "remove_key_binding_guard": "datum_key_binding",
    "remove_threshold_guard": "datum_threshold",
    "remove_status_guard": "datum_status",
    "remove_pending_canonicality_guard": "datum_pending_noncanonical",
    "remove_bootstrap_proof_of_possession_verification": "r2_invalid_proof_0",
}
MUTATION_GUARDS = {
    "unconditional_success": ("""BootstrapAuthority { proofs } -> validate_bootstrap(
        genesis_ref,
        initial_keys,
        proofs,
        policy_id,
        tx,
      )""", "BootstrapAuthority { proofs: _ } -> True"),
    "remove_seed_guard": ("expect count_seed_input(tx.inputs, genesis_ref) == 1", "expect True"),
    "remove_exact_mint_guard": ("expect\n    dict.to_pairs(assets.tokens(tx.mint, policy_id)) == [\n      Pair(authority_asset_name, 1),\n    ]", "expect True"),
    "remove_target_output_cardinality_guard": ("expect count_state_credential_outputs(tx.outputs, state_validator_script_hash) == 1", "expect True"),
    "remove_state_validator_credential_binding": ("expect authority_output.address.payment_credential == Script(state_validator_script_hash)", "expect True"),
    "remove_no_stake_credential_guard": ("expect authority_output.address.stake_credential == None", "expect True"),
    "remove_singleton_quantity_guard": ("expect assets.quantity_of(authority_output.value, policy_id, authority_asset_name) == 1", "expect True"),
    "remove_exact_lovelace_guard": ("expect assets.lovelace_of(authority_output.value) == authority_initial_lovelace", "expect True"),
    "remove_no_extra_asset_guard": ("expect only_authority_nft(authority_output.value, policy_id)", "expect True"),
    "remove_inline_datum_guard": ("expect InlineDatum(raw_datum) = authority_output.datum", "expect InlineDatum(raw_datum) = sponsor_datum(tx.outputs, state_validator_script_hash)"),
    "remove_schema_version_guard": ("state.schema_version == authority_schema_version", "True"),
    "remove_seed_hash_guard": ("state.bootstrap_tx_hash == genesis_ref.transaction_id", "True"),
    "remove_seed_index_guard": ("state.bootstrap_output_index == genesis_ref.output_index", "True"),
    "remove_epoch_guard": ("state.epoch == 0", "True"),
    "remove_key_uniqueness_order_guard": ("bytearray.to_int_big_endian(first) < bytearray.to_int_big_endian(second)", "True"),
    "remove_key_order_guard": ("bytearray.to_int_big_endian(second) < bytearray.to_int_big_endian(third)", "True"),
    "remove_key_binding_guard": ("state.ordered_keys == initial_keys", "True"),
    "remove_threshold_guard": ("state.threshold == authority_threshold", "True"),
    "remove_status_guard": ("state.status == AuthorityActive", "True"),
    "remove_pending_canonicality_guard": ("canonical_none(state.pending)", "True"),
    "remove_bootstrap_proof_of_possession_verification": ("valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message)", "True"),
}
def _cbor_helpers() -> Any:
    helper = ROOT / "scripts/remediation/f05_2a_tx_sim_registry.py"
    spec = importlib.util.spec_from_file_location("f05_evidence_cbor", helper)
    if spec is None or spec.loader is None:
        raise RuntimeError("typed CBOR helper unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def verify_mint_binding(tx_cbor: bytes, expected_policy_id: str) -> dict[str, Any]:
    """Bind simulator evidence to the typed transaction's sole mint policy and V3 script."""
    cb = _cbor_helpers()
    tx = cb.loads(tx_cbor)
    if not isinstance(tx, list) or len(tx) != 4:
        raise ValueError("expected typed Conway transaction tuple")
    mint = cb.map_get(tx[0], 9)
    if not isinstance(mint, cb.Map) or len(mint.pairs) != 1:
        raise ValueError("expected exactly one unique typed mint policy entry")
    if not isinstance(mint.pairs[0][0], bytes):
        raise ValueError("typed mint policy ID must be bytes")
    policy_ids = {policy.hex() for policy, _ in mint.pairs}
    if policy_ids != {expected_policy_id}:
        raise ValueError(f"typed mint policy set mismatch: {sorted(policy_ids)}")
    tagged_scripts = cb.map_get(tx[1], 7)
    if not isinstance(tagged_scripts, cb.Tag) or tagged_scripts.number != 258:
        raise ValueError("expected Plutus V3 script set with tag 258")
    scripts = tagged_scripts.value
    if not isinstance(scripts, list) or len(scripts) != 1 or not isinstance(scripts[0], bytes):
        raise ValueError("expected exactly one Plutus V3 witness script")
    script_hash = hashlib.blake2b(b"\x03" + scripts[0], digest_size=28).hexdigest()
    if script_hash != expected_policy_id:
        raise ValueError(f"witness script hash mismatch: {script_hash}")
    return {"policy_ids": sorted(policy_ids), "script_hash": script_hash, "bound": True}

def run_bound_simulation(aiken: Path, tx_path: Path, inputs_path: Path,
                         outputs_path: Path, expected_policy_id: str) -> dict[str, Any]:
    """Run the pinned simulator only after binding the typed tx to its exact Mint[0] script."""
    tx_bytes = tx_path.read_bytes()
    verify_mint_binding(tx_bytes, expected_policy_id)
    command = [str(aiken), "tx", "simulate", "--cbor", str(tx_path),
               str(inputs_path), str(outputs_path)]
    completed = subprocess.run(command, capture_output=True, text=True,
                               timeout=90, check=False)
    cb = _cbor_helpers()
    classified = cb.classify_tx_sim_result(
        {"exit": completed.returncode, "stdout": completed.stdout,
         "stderr": completed.stderr}, tx_bytes, expected_policy_id,
    )
    if tx_path.read_bytes() != tx_bytes:
        raise ValueError("transaction fixture changed during simulation")
    return {"command": command, "simulator_exit": completed.returncode,
            "transaction_sha256": hashlib.sha256(tx_bytes).hexdigest(), **classified}

def negative_property(case_id: str) -> str | None:
    if case_id in {"seed_missing", "seed_duplicate", "applied_genesis_parameter"}:
        return "count_seed_input(tx.inputs, genesis_ref) == 1"
    if case_id == "applied_keys_parameter":
        return "state.ordered_keys == initial_keys"
    if case_id == "mint_wrong_policy":
        return None
    if case_id.startswith("mint_"):
        return "dict.to_pairs(assets.tokens(tx.mint, policy_id)) == [Pair(authority_asset_name, 1)]"
    if case_id in {"output_wrong_payment_credential", "r2_wrong_state_address"}:
        return "authority_output.address.payment_credential == Script(state_validator_script_hash)"
    if case_id == "output_stake_credential":
        return "authority_output.address.stake_credential == None"
    if case_id in {"datum_missing", "datum_hash_only"}:
        return "InlineDatum(raw_datum) = authority_output.datum"
    if case_id == "datum_unknown_constructor":
        return "expect state: AuthorityStateV3 = raw_datum"
    if case_id == "datum_schema_version":
        return "state.schema_version == authority_schema_version"
    if case_id in {"seed_datum_hash", "datum_seed_hash"}:
        return "state.bootstrap_tx_hash == genesis_ref.transaction_id"
    if case_id in {"seed_datum_index", "datum_seed_index"}:
        return "state.bootstrap_output_index == genesis_ref.output_index"
    if case_id == "datum_epoch":
        return "state.epoch == 0"
    if case_id in {"datum_key_count", "applied_keys_bad_count"}:
        return "valid_ordered_keys requires exactly five keys"
    if case_id in {"datum_key_length", "applied_keys_bad_length"}:
        return "bytearray.length(first) == authority_key_bytes"
    if case_id in {"datum_duplicate_key", "r2_duplicate_datum_key", "applied_keys_duplicate"}:
        return "bytearray.to_int_big_endian(first) < bytearray.to_int_big_endian(second)"
    if case_id in {"datum_key_order", "r2_swapped_datum_keys", "applied_keys_unsorted"}:
        return "ordered_keys are strictly increasing by key bytes"
    if case_id == "datum_key_binding":
        return "state.ordered_keys == initial_keys"
    if case_id == "datum_threshold":
        return "state.threshold == authority_threshold"
    if case_id == "datum_status":
        return "state.status == AuthorityActive"
    if case_id in {"datum_pending_kind", "datum_pending_noncanonical"}:
        return "canonical_none(state.pending)"
    if case_id in {"authority_value_minus_one", "authority_value_plus_one", "fee_diversion"}:
        return "assets.lovelace_of(authority_output.value) == authority_initial_lovelace"
    if case_id == "authority_extra_native_asset":
        return "only_authority_nft(authority_output.value, policy_id)"
    if case_id == "authority_output_duplicate_nft":
        return "list.filter(tx.outputs, NFT predicate) has exactly one authority output"
    if case_id == "authority_output_quantity_two":
        return "assets.quantity_of(authority_output.value, policy_id, authority_asset_name) == 1"
    if case_id in {"authority_output_extra_target", "authority_output_missing"}:
        return "count_state_credential_outputs(tx.outputs, state_validator_script_hash) == 1"
    if case_id.startswith(("r2_proof", "r2_invalid_proof", "r2_wrong_key", "r2_signature")):
        return "valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message)"
    return None

def generate(registry_path: Path = REGISTRY) -> dict[str, Any]:
    source = json.loads(registry_path.read_text(encoding="utf-8"))
    expected_negative = source["expected"]["every_negative_case"]
    expected_mutant = source["expected"]["individual_guard_removal_on_matching_negative"]
    negatives = []
    for case in source["negative_cases"]:
        case_id = case["id"]
        category = ("context_only" if case_id in CONTEXT else
                    "routing_noninvoking" if case_id == "mint_wrong_policy" else "ledger_tx_sim")
        nonexecuting = category == "routing_noninvoking"
        contextual = category == "context_only"
        applied = case_id in APPLIED_PARAMETER_CASES
        status = "PENDING"
        negatives.append({
            "id": case_id,
            "mutation": case["mutation"],
            "original_assertion": {"path": "expected.every_negative_case", "value": expected_negative},
            "verifier_property": negative_property(case_id),
            "category": category,
            "executor": None if nonexecuting else ("compiled_context (unqualified)" if contextual else "pinned Aiken parameterized compile + tx-sim" if case_id.startswith("applied_") else "pinned Aiken tx simulate --cbor"),
            "target_ref": None if nonexecuting else "cardano/validators/f05_authority_policy.ak#f05_authority_policy.mint",
            "target_policy_hash": None if nonexecuting or applied else POLICY_HASH,
            "expected_base_policy_id": POLICY_HASH,
            "compiled_target_policy_id": None if applied or nonexecuting else POLICY_HASH,
            "compiled_target_policy_id_status": "parameter-derived policy pending isolated compile" if applied else "not invoked" if nonexecuting else "confirmed base policy id",
            "target_policy_hash_note": "target applied policy" if contextual else "non-invoking routing category" if nonexecuting else ("parameter-derived hash pending isolated compile" if applied else "accepted applied-policy hash"),
            "expected_result": "not invoked" if nonexecuting else "compiled context rejection; target invocation unqualified" if contextual else "reject at compiled target Mint[0]",
            "status": status,
            "status_reason": "historical #33 execution requires R2 evidence and exit-status reconciliation" if case_id == "authority_value_minus_one" else CONTEXT.get(case_id, "parameter-derived hash and simulation pending isolated compile" if applied else "not yet executed and independently reviewed"),
            "evidence_ref": f"docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json#negative_cases/{case_id}",
            "historical_evidence_ref": "m3-f05-2a-tx-pair-r1-20261001T045757Z-829ab544571f" if case_id == "authority_value_minus_one" else None,
            "preservation_delta": "authority output minus one lovelace; sponsor change plus one lovelace" if case_id == "authority_value_minus_one" else "rebalance 2,000,000 lovelace from sponsor output to preserve ADA conservation" if case_id == "r2_wrong_state_address" else ("authority output minus one lovelace; divert one lovelace to fee" if case_id == "fee_diversion" else None),
        })
    mutations = []
    for mutation in source["compiled_mutations"]:
        pair = MUTATION_PAIRS.get(mutation)
        guard = MUTATION_GUARDS.get(mutation)
        unbound_target = mutation in {
            "remove_key_uniqueness_order_guard", "remove_key_order_guard",
            "remove_singleton_quantity_guard",
        }
        mutations.append({
            "id": mutation,
            "paired_negative_id": pair,
            "original_assertion": {
                "baseline_path": "expected.every_negative_case",
                "baseline_value": expected_negative,
                "mutant_path": "expected.individual_guard_removal_on_matching_negative",
                "mutant_value": expected_mutant,
            },
            "source_guard_before": guard[0] if guard else None,
            "mutant_replacement": guard[1] if guard else None,
            "category": ("composite_mutation" if mutation == "unconditional_success" else
                         "context_only_mutation" if mutation == "remove_singleton_quantity_guard" else
                         "alternate_parameter_mutation" if mutation in {"remove_key_uniqueness_order_guard", "remove_key_order_guard"} else "canonical_guard_mutation"),
            "executor": "compiled_context (unqualified)" if mutation == "remove_singleton_quantity_guard" else "scripts/remediation/test_f05_2a_authority_bootstrap_public.py with pinned Aiken",
            "target_ref": "cardano/validators/f05_authority_policy.ak and cardano/lib/vams/f05_authority.ak",
            "base_policy_id": POLICY_HASH,
            "target_policy_hash": None if unbound_target else POLICY_HASH,
            "target_policy_hash_status": "unbound parameter/context target" if unbound_target else "accepted base-policy reference only",
            "mutant_policy_id": None,
            "mutant_policy_hash": None,
            "mutant_policy_id_status": "pending mutant compile; do not treat base ID as mutant ID",
            "mutant_policy_hash_note": "mutant script hash unavailable until isolated compile",
            "expected_result": {"baseline": "reject", "matching_mutant": "accept"},
            "status": "PENDING",
            "status_reason": "mutation suite not rerun/reviewed in this evidence package",
            "evidence_ref": f"scripts/remediation/test_f05_2a_authority_bootstrap_public.py#mutation_pairs/{mutation}",
        })
    if len(negatives) != 55 or len(mutations) != 21:
        raise ValueError("source registry row count changed")
    if any(row["status"] != "PENDING" for row in negatives + mutations):
        raise ValueError("new contract cannot promote cases without verified R2 evidence")
    return {
        "schema_version": "f05-2a-ledger-negative-evidence-contract-r2",
        "status": "all R2 cases pending; historical #33 execution not promoted",
        "source_registry": str(registry_path.relative_to(ROOT)) if registry_path.is_relative_to(ROOT) else registry_path.name,
        "expected_semantics": source["expected"],
        "base_policy_hash": POLICY_HASH,
        "negative_cases": negatives,
        "compiled_mutations": mutations,
    }

def write_contract(target: Path, registry_path: Path = REGISTRY) -> Path:
    target = target.resolve()
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(generate(registry_path), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target

def main_with_args(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    target = (args.output if args.output.is_absolute() else ROOT / args.output).resolve()
    expected = (ROOT / "docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r2.json").resolve()
    if target != expected:
        raise SystemExit(f"output must be exact authorized contract path: {expected}")
    if target.exists():
        raise SystemExit(f"refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(generate(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    return 0

def main() -> int:
    return main_with_args()

if __name__ == "__main__":
    raise SystemExit(main())
