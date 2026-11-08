#!/usr/bin/env python3
"""Capture one separately classified synthetic F05.2a mutation-suite fixture family."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAMILY = ROOT / "docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_keys_unsorted"
MANIFEST_PATH = FAMILY / "FIXTURE-MANIFEST.json"
RUNNER = ROOT / "scripts/remediation/f05_2a_tx_sim_runner_r3.py"
DEFAULT_PYTHON = Path("/home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12")
DEFAULT_AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken")
OUT = ROOT / "docs/remediation/m3_f05_2a_unsorted_mutation_suite_r1_20261005"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run_case(label: str, prefix: str, policy: str, expected_stage: str, aiken: Path, python: Path) -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text())
    artifacts = manifest["artifacts"]
    for suffix in ("tx.cbor", "raw_inputs.cbor", "raw_outputs.cbor"):
        name = f"{prefix}.{suffix}"
        path = FAMILY / name
        expected = artifacts[name]["sha256"]
        actual = sha(path)
        if actual != expected:
            raise SystemExit(f"{label}: fixture hash mismatch for {name}")
    validation = artifacts[f"{prefix}.validation"]
    required = {
        "valid_body_bound_ephemeral_signatures": True,
        "ada_conservation": True,
        "native_asset_conservation": True,
        "private_keys_persisted": False,
        "funding_signatures": 2,
    }
    for key, expected in required.items():
        if validation.get(key) != expected:
            raise SystemExit(f"{label}: validation metadata {key} mismatch")
    cmd = [
        str(python), str(RUNNER), "--aiken", str(aiken),
        "--tx", str(FAMILY / f"{prefix}.tx.cbor"),
        "--raw-inputs", str(FAMILY / f"{prefix}.raw_inputs.cbor"),
        "--raw-outputs", str(FAMILY / f"{prefix}.raw_outputs.cbor"),
        "--policy-id", policy,
    ]
    completed = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise SystemExit(f"{label}: runner returned no JSON")
    result = json.loads(lines[-1])
    sim = result.get("simulator_result", {})
    binding = result.get("target_mint_binding", {})
    if result.get("wrapper_exit_code") != 0:
        raise SystemExit(f"{label}: wrapper exit {result.get('wrapper_exit_code')}")
    if sim.get("stage") != expected_stage or sim.get("target_script_invoked") is not True:
        raise SystemExit(f"{label}: unexpected simulator result {sim}")
    if result.get("cleanup", {}).get("status") != "clean":
        raise SystemExit(f"{label}: cleanup not clean")
    if binding.get("expected_policy_id") != policy or binding.get("compiled_script_hash") != policy:
        raise SystemExit(f"{label}: policy/script binding mismatch")
    submitted = result["submitted_sha256"]
    expected_hashes = {
        "transaction": artifacts[f"{prefix}.tx.cbor"]["sha256"],
        "raw_inputs": artifacts[f"{prefix}.raw_inputs.cbor"]["sha256"],
        "raw_outputs": artifacts[f"{prefix}.raw_outputs.cbor"]["sha256"],
    }
    if submitted != expected_hashes:
        raise SystemExit(f"{label}: submitted hash mismatch")
    return {"label": label, "command": cmd, "runner_exit": completed.returncode,
            "result": result, "manifest_validation": validation}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aiken", type=Path, default=DEFAULT_AIKEN)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--output", type=Path, default=OUT / "RUN.json")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text())
    policies = {
        "positive_control": manifest["policy_applications"]["positive-control"]["applied_policy_id"],
        "original_negative": manifest["policy_applications"]["negative"]["applied_policy_id"],
        "matching_mutant": manifest["policy_applications"]["one-guard-mutant-control"]["applied_policy_id"],
    }
    runs = [
        run_case("positive_control", "positive-control", policies["positive_control"], "script_accepted", args.aiken, args.python),
        run_case("original_negative", "negative", policies["original_negative"], "compiled_evaluation", args.aiken, args.python),
        run_case("matching_mutant", "one-guard-mutant-control", policies["matching_mutant"], "script_accepted", args.aiken, args.python),
    ]
    payload = {
        "schema_version": "f05-2a-unsorted-mutation-suite-capture-r1",
        "status": "pass",
        "mutation_suite": True,
        "mutation": "remove_key_order_guard",
        "paired_negative_id": "applied_keys_unsorted",
        "entrypoint": "f05_authority_policy.f05_authority_policy.mint / Mint[0]",
        "fixture_family": str(FAMILY.relative_to(ROOT)),
        "decision": "R4.1 applied-parameter C",
        "runs": runs,
        "credit": {
            "mutation_suite": True,
            "negative_case": False,
            "original_policy": False,
            "ledger_admission": False,
            "cardano_pre_prod": False,
            "live_network": False,
            "deployment_readiness": False,
        },
        "evidence_scope": "synthetic alternate-applied-policy transaction-simulator mutation capture only",
        "security": {
            "ephemeral_test_keys_only": True,
            "private_keys_persisted": False,
            "body_bound_funding_signatures": True,
            "ada_and_native_asset_conservation": True,
        },
        "source_unchanged": True,
        "fixture_registry_unchanged": True,
        "classification": "pending independent review and classification overlay",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "status": payload["status"], "mutation_suite": True, "runs": len(runs)}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
