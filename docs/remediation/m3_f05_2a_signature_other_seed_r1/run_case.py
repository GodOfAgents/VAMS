#!/usr/bin/env python3
"""Run one registered F05 proof-domain negative using the existing public harness."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/remediation/test_f05_2a_authority_bootstrap_public.py"
CASE_ID = "r2_signature_for_other_seed"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aiken", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("_f05_public_harness", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load existing F05 public harness")
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    fixture, contract = harness._validate_inputs()
    signers = harness._ephemeral_committee()
    workroot = Path(tempfile.mkdtemp(prefix="f05-other-seed-r1-"))
    try:
        keys = [item.public_key for item in signers]
        fixture_only = fixture["synthetic_fixture_only"]
        seed_hash = bytes.fromhex(fixture_only["genesis_tx_hash"])
        seed_index = fixture_only["genesis_output_index"]
        parameters = {
            "genesis_ref": harness._output_reference(seed_hash, seed_index),
            "initial_keys": harness.list_data([harness.byte_string(key) for key in keys]),
        }
        base = harness._compile(harness.CARDANO, args.aiken.resolve(),
                                workroot / "base", parameters)
        parameters.update({
            "policy_id": base["policy_id"].hex(),
            "state_credential": base["state_credential"].hex(),
            "state_validator_hash": base["expected_credential"].hex(),
        })
        message = harness._canonical_pop_message(
            seed_hash, seed_index, base["state_credential"], keys)
        valid_proofs = [item.sign(message) for item in signers]
        valid_context = harness._base_context(
            base["policy_id"], base["state_credential"], seed_hash, seed_index,
            keys, valid_proofs)
        positive = harness._evaluate(args.aiken.resolve(), base["code"],
                                     valid_context, workroot, "positive-control")
        if not positive["accepted"]:
            raise RuntimeError(f"positive control did not accept: {positive}")
        negative_context, _ = harness._mutate(
            CASE_ID, valid_context, parameters, signers)
        negative = harness._evaluate(args.aiken.resolve(), base["code"],
                                     negative_context, workroot, CASE_ID)
        if negative["accepted"]:
            raise RuntimeError("wrong-seed proof was accepted")
        alt_message = harness._canonical_pop_message(
            bytes.fromhex("ad" * 32), seed_index, base["state_credential"], keys)
        source_paths = [
            ROOT / "cardano/aiken.toml",
            ROOT / "cardano/aiken.lock",
            ROOT / "cardano/aiken-dependency-manifest.json",
            ROOT / "cardano/lib/vams/f05_authority.ak",
            ROOT / "cardano/validators/f05_authority_policy.ak",
            ROOT / "cardano/validators/f05_authority_state.ak",
            ROOT / "docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json",
            ROOT / "docs/remediation/m3_f05_design_r2/CONTRACT.json",
            ROOT / "scripts/remediation/test_f05_2a_authority_bootstrap_public.py",
            Path(__file__),
        ]
        version = subprocess.run([str(args.aiken.resolve()), "--version"],
                                 text=True, capture_output=True, check=True)
        result = {
            "case_id": CASE_ID,
            "expected": "reject",
            "actual": "reject",
            "evidence_scope": "synthetic compiled UPLC ScriptContext evaluation; not ledger admission or live-network evidence",
            "entrypoint": harness.POLICY_TITLE,
            "toolchain": version.stdout.strip(),
            "aiken_sha256": sha(args.aiken.resolve()),
            "harness_sha256": sha(RUNNER),
            "case_runner_sha256": sha(Path(__file__)),
            "contract_id": contract["specification_id"],
            "committee_signer_count": len(signers),
            "keys_or_signatures_persisted": False,
            "base_policy_id": base["policy_id"].hex(),
            "compiled_program_sha256": hashlib.sha256(base["code"]).hexdigest(),
            "state_validator_hash": base["state_credential"].hex(),
            "canonical_seed_hash": seed_hash.hex(),
            "alternate_signed_seed_hash": "ad" * 32,
            "canonical_pop_message_bytes": len(message),
            "alternate_pop_message_bytes": len(alt_message),
            "alternate_pop_message_sha256": hashlib.sha256(alt_message).hexdigest(),
            "positive_control": positive,
            "negative_result": negative,
            "inputs": {str(path.relative_to(ROOT)): sha(path) for path in source_paths},
        }
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(workroot, ignore_errors=True)
        for signer in signers:
            signer.close()

if __name__ == "__main__":
    raise SystemExit(main())
