#!/usr/bin/env python3
"""Compile sanitized source mutations and prove the public harness detects them."""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken")
HARNESS = ROOT / "scripts/remediation/test_m3_1b_public_validator.py"
SOURCE = ROOT / "cardano/validators/insurance_fund.ak"

def mutate(source: str, name: str) -> tuple[str, str]:
    if name == "deposit":
        old = "Deposit { amount: _, bridge_proof: _, payload_hash: _ } -> False"
        return source.replace(old, "Deposit { amount: _, bridge_proof: _, payload_hash: _ } -> True", 1), "deposit_unconditionally_rejected"
    if name == "signer_cap":
        return source.replace("fn bounded_extra_signatories(tx: Transaction) -> Bool {\n  list.length(tx.extra_signatories) <= max_extra_signatories && list.length(\n    list.unique(tx.extra_signatories),\n  ) == list.length(tx.extra_signatories)\n}", "fn bounded_extra_signatories(_tx: Transaction) -> Bool { True }", 1), "signer_count_above_bound_rejected"
    if name == "schema":
        source = source.replace("datum.schema_version == fund_schema_version", "True")
        source = source.replace("before.schema_version == after.schema_version", "True")
        return source, "schema_version_mutation"
    if name == "claimant":
        source = source.replace("bytearray.length(claimant_vkh) == verification_key_hash_bytes", "True")
        source = source.replace("bytearray.length(claim.claimant_vkh) == verification_key_hash_bytes", "True")
        return source, "claimant_hash_length_mutation"
    if name == "evidence":
        source = source.replace("bytearray.length(evidence_hash) == digest_bytes", "True")
        source = source.replace("bytearray.length(claim.evidence_hash) == digest_bytes", "True")
        return source, "evidence_hash_length_mutation"
    if name == "state_asset":
        return source.replace("bytearray.length(state_asset_name) > 0 && bytearray.length(state_asset_name) <= max_asset_name_bytes", "True", 1), "state_asset_name_bound_mutation"
    if name == "guardian":
        return source.replace("before.guardians == after.guardians,", "True,", 1), "guardian_mutation"
    if name == "threshold":
        return source.replace("before.approval_threshold == after.approval_threshold,", "True,", 1), "threshold_mutation"
    if name == "payout_cap":
        return source.replace("before.max_payout_bps == after.max_payout_bps,", "True,", 1), "payout_cap_mutation"
    if name == "epoch":
        return source.replace("before.policy_epoch == after.policy_epoch,", "True,", 1), "policy_epoch_mutation"
    if name == "payout_removal":
        return source.replace("next.pending_claims == remove_claim(datum.pending_claims, claim_id)", "True", 1), "payout_retains_claim"
    if name == "duplicate_approver":
        source = source.replace("expect !list.has(claim.approvers, guardian)", "expect True", 1)
        source = source.replace("list.length(list.unique(claim.approvers)) == list.length(claim.approvers),", "True,", 1)
        return source, "approve_duplicate_actual_state"
    if name in {"approve_interval", "payout_interval", "cancel_interval", "expire_interval"}:
        fn = name.split("_")[0]
        start = source.index(f"fn validate_{fn}(")
        end = source.find("\nfn ", start + 4)
        if end == -1:
            end = len(source)
        block = source[start:end]
        marker = "  expect finite_interval(tx, max_submission_interval_ms)\n"
        if marker not in block:
            raise AssertionError(f"interval mutation did not match {name}")
        block = block.replace(marker, "", 1)
        return source[:start] + block + source[end:], f"{fn}_interval_above"
    raise AssertionError(name)

def main() -> int:
    names = ["deposit", "signer_cap", "schema", "claimant", "evidence", "state_asset", "guardian", "threshold", "payout_cap", "epoch", "payout_removal", "duplicate_approver", "approve_interval", "payout_interval", "cancel_interval", "expire_interval"]
    failures = []
    results = {}
    for name in names:
        with tempfile.TemporaryDirectory(prefix=f"m3-r5-{name}-", dir="/home/GodOfAgents/vams-evidence") as folder:
            root = Path(folder)
            cardano = root / "cardano"
            shutil.copytree(ROOT / "cardano", cardano)
            target = cardano / "validators/insurance_fund.ak"
            mutated, case = mutate(target.read_text(), name)
            if mutated == target.read_text():
                raise AssertionError(f"mutation did not change source: {name}")
            target.write_text(mutated)
            run = subprocess.run([str(AIKEN), "build"], cwd=cardano, text=True, capture_output=True)
            if run.returncode:
                results[name] = {"compile": False, "case": case}
                failures.append(name)
                continue
            blueprint = cardano / "plutus.json"
            doc = json.loads(blueprint.read_text())
            compiled = next(v["compiledCode"] for v in doc["validators"] if v["title"] == "insurance_fund.insurance_fund.mint")
            digest = hashlib.sha256(bytes.fromhex(compiled)).hexdigest()
            harness = root / "harness.py"
            harness.write_text(HARNESS.read_text().replace("EXPECTED_COMPILED_SHA256 = \"4bdefcf0731c54e39b1cf97d29c06d465cd7e503a6f524f4d486dcd5309f0e38\"", f"EXPECTED_COMPILED_SHA256 = \"{digest}\""))
            out = subprocess.run([str(AIKEN), "uplc", "eval", "-h"], cwd=cardano, capture_output=True)
            result = subprocess.run([str(__import__('sys').executable), str(harness), "--aiken", str(AIKEN), "--blueprint", str(blueprint), "--only", case], text=True, capture_output=True)
            payload = json.loads(result.stdout)
            rejected = case in payload["failed"]
            results[name] = {"compile": True, "case": case, "detected": rejected}
            if not rejected:
                failures.append(name)
    print(json.dumps({"mutations": results, "failed": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
