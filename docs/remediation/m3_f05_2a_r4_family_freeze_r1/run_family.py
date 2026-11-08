from __future__ import annotations
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path("/home/GodOfAgents/code/VAMS-testnet")
FAMILY=ROOT/"docs/remediation/m3_f05_2a_r4_tx_families/seed_reference_and_datum_binding"
EVIDENCE=ROOT/"docs/remediation/m3_f05_2a_r4_family_freeze_r1"
AIKEN=Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken")
EXPECTED_AIKEN="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
EXPECTED_POLICY="9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

freeze=json.loads((EVIDENCE/"FREEZE.json").read_text())
freeze_sha=sha((EVIDENCE/"FREEZE.json").read_bytes())
review=json.loads((EVIDENCE/"RUN.json").read_text())["independent_review"]
assert freeze["status"]=="coordinator_frozen_pending_independent_family_approval"
assert review["result"]=="PASS" and review["reviewed_freeze_sha256"]==freeze_sha
assert review["simulator_invoked_by_reviewer"] is False
family_manifest=json.loads((FAMILY/"FAMILY-MANIFEST.json").read_text())
assert family_manifest["family_id"]==freeze["family_id"]
assert family_manifest["executions"]==0 and family_manifest["all_cases_pending"]
assert family_manifest["target"]["policy_id"]==EXPECTED_POLICY
assert sha(AIKEN.read_bytes())==EXPECTED_AIKEN
version=subprocess.run([str(AIKEN),"--version"],capture_output=True,text=True,check=True).stdout.strip()
assert version.startswith("aiken v1.1.21+42babe5"),version
for rel,entry in freeze["files"].items():
    actual=(FAMILY/rel).read_bytes()
    assert sha(actual)==entry["sha256"],rel

runner_path=ROOT/"scripts/remediation/f05_2a_tx_sim_runner_r3.py"
spec=importlib.util.spec_from_file_location("r4_frozen_r3_runner",runner_path)
runner=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=runner
assert spec.loader is not None
spec.loader.exec_module(runner)
results=[]
for case in family_manifest["cases"]:
    assert case["status"]=="PENDING" and case["script_invoked"] is False
    assert case["simulator_result"]=="not run pending coordinator freeze and independent review"
    tx=FAMILY/case["files"]["transaction"]["path"]
    raw_inputs=FAMILY/case["files"]["raw_inputs"]["path"]
    raw_outputs=FAMILY/case["files"]["raw_outputs"]["path"]
    result=runner.run_snapshot_simulation(AIKEN,tx,raw_inputs,raw_outputs,EXPECTED_POLICY)
    assert result["wrapper_exit_code"]==0,(case["id"],result)
    assert result["simulator_child_exit"]==1,(case["id"],result)
    assert result["simulator_result"]=={"stage":"compiled_evaluation","target_script_invoked":True},(case["id"],result)
    assert result["target_mint_binding"]["expected_policy_id"]==EXPECTED_POLICY
    assert result["target_mint_binding"]["policy_ids"]==[EXPECTED_POLICY]
    assert result["cleanup"]["status"]=="clean",(case["id"],result)
    for role,path in (("transaction",tx),("raw_inputs",raw_inputs),("raw_outputs",raw_outputs)):
        assert result["submitted_sha256"][role]==sha(path.read_bytes()),(case["id"],role)
    results.append({
      "id":case["id"],
      "expected":"reject at compiled target Mint[0]",
      "wrapper_exit":result["wrapper_exit_code"],
      "simulator_child_exit":result["simulator_child_exit"],
      "classification":result["simulator_result"],
      "target_mint_binding":result["target_mint_binding"],
      "submitted_sha256":result["submitted_sha256"],
      "cleanup":result["cleanup"]
    })
print(json.dumps({
 "status":"pass_pending_independent_result_review",
 "evidence_class":"synthetic_local_snapshot_bound_transaction_simulator",
 "family_id":family_manifest["family_id"],
 "freeze_sha256":freeze_sha,
 "applied_policy_id":EXPECTED_POLICY,
 "aiken_version":version,
 "aiken_sha256":EXPECTED_AIKEN,
 "runner_sha256":sha(runner_path.read_bytes()),
 "cases":results,
 "family_manifest_admission_status":"PENDING",
 "ledger_admission":False,
 "live_network_evidence":False
},sort_keys=True))
