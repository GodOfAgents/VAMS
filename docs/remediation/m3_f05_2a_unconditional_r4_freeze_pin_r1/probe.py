#!/usr/bin/env python3
"""Supplemental exact-R4-context probe for unconditional_success."""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
EVID=ROOT/"docs/remediation/m3_f05_2a_unconditional_r3_mutation_r1/probe.py"
FAMILY=ROOT/"docs/remediation/m3_f05_2a_r4_tx_families/seed_reference_and_datum_binding"
FREEZE=ROOT/"docs/remediation/m3_f05_2a_r4_family_freeze_r1/FREEZE.json"
CONTRACT=ROOT/"docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r2.json"
EXPECTED="9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
EXPECTED_FREEZE="df7d882ad8aa26b59692c65457bf888204cfbfdc3586ce2619a99f1749115c6b"

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError("module_load_failed")
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module
    spec.loader.exec_module(module); return module

probe=load("f05_r3_probe_lib",EVID)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    freeze=json.loads(FREEZE.read_text())
    assert sha(FREEZE)==EXPECTED_FREEZE
    family=json.loads((FAMILY/"FAMILY-MANIFEST.json").read_text())
    contract=json.loads(CONTRACT.read_text())
    assert freeze["family_manifest_sha256"]==sha(FAMILY/"FAMILY-MANIFEST.json")
    assert sha(probe.AIKEN)=="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
    entry=next(x for x in contract["compiled_mutations"] if x["id"]=="unconditional_success")
    assert entry["paired_negative_id"]=="seed_missing"
    assert entry["mutant_replacement"]=="BootstrapAuthority { proofs: _ } -> True"
    cases={x["id"]:x for x in family["cases"]}; cases["positive_control"]=family["positive_control"]
    paths={}
    for case_id in ("positive_control","seed_missing"):
        item=cases[case_id]; paths[case_id]={}
        for field,meta in item["files"].items():
            path=FAMILY/meta["path"]
            assert path.stat().st_size==meta["size_bytes"] and sha(path)==meta["sha256"]
            paths[case_id][field]=path
    neg=paths["seed_missing"]
    tx=probe.helper.roundtrip(neg["transaction"].read_bytes())
    datum=probe.helper.map_get(probe.helper.map_get(tx[0],1)[0],2)
    state=probe.helper.roundtrip(datum[1].value)
    params={"genesis_ref":probe.public._output_reference(state.value[1],state.value[2]),
            "initial_keys":probe.public.list_data([probe.public.byte_string(k) for k in state.value[4]])}
    with tempfile.TemporaryDirectory(prefix="f05-r4-unconditional-") as td:
        work=Path(td); aiken=probe.AIKEN
        base=probe.public._compile(ROOT/"cardano",aiken,work/"base",params)
        assert base["policy_id"].hex()==EXPECTED
        mutant=probe.public._compile(ROOT/"cardano",aiken,work/"mutant",params,"unconditional_success")
        mutant_id=mutant["policy_id"].hex()
        assert hashlib.blake2b(b"\x03"+mutant["code"],digest_size=28).hexdigest()==mutant_id
        pos=work/"positive-mutant.tx.cbor"; missing=work/"missing-mutant.tx.cbor"
        pos.write_bytes(probe.mutant_transaction(paths["positive_control"]["transaction"].read_bytes(),mutant["policy_id"],mutant["code"],False))
        missing.write_bytes(probe.mutant_transaction(neg["transaction"].read_bytes(),mutant["policy_id"],mutant["code"],False))
        planned=[
            ("baseline_seed_missing",neg["transaction"],neg["raw_inputs"],neg["raw_outputs"],EXPECTED,1,"compiled_evaluation"),
            ("mutant_positive_control",pos,paths["positive_control"]["raw_inputs"],paths["positive_control"]["raw_outputs"],mutant_id,0,"script_accepted"),
            ("mutant_exact_seed_missing_context",missing,neg["raw_inputs"],neg["raw_outputs"],mutant_id,0,"script_accepted")]
        out=[]
        for name,txp,inp,outputs,pid,child,stage in planned:
            r=probe.runner.run_snapshot_simulation(aiken,txp,inp,outputs,pid)
            assert r["wrapper_exit_code"]==0 and r["simulator_child_exit"]==child
            assert r["simulator_result"]=={"stage":stage,"target_script_invoked":True}
            assert r["cleanup"]["status"]=="clean"
            out.append({"id":name,"wrapper_exit":r["wrapper_exit_code"],"simulator_child_exit":child,
                        "classification":r["simulator_result"],"target_mint_binding":r["target_mint_binding"],
                        "submitted_sha256":r["submitted_sha256"],"cleanup":r["cleanup"]})
        print(json.dumps({"schema_version":"f05-unconditional-r4-exact-context-r2","status":"pass",
          "base_policy_id":EXPECTED,"mutant_policy_id":mutant_id,
          "mutant_code_sha256":hashlib.sha256(mutant["code"]).hexdigest(),
          "family_manifest_sha256":sha(FAMILY/"FAMILY-MANIFEST.json"),
          "fixture_hashes":{cid:{k:v["sha256"] for k,v in cases[cid]["files"].items()} for cid in ("positive_control","seed_missing")},
          "cases":out,"evidence_class":"synthetic_local_transaction_simulator_only",
          "registered_mutation_credit":False,"count_ledger":{"negative_cases":"45/55","compiled_mutations":"18/21"},
          "limitations":["one paired negative only; full unconditional_success mutation suite not run",
          "mutant body and Plutus witness are rebound; key-witness ledger validity is not established",
          "no ledger admission or live-network evidence"]},sort_keys=True))
if __name__=="__main__":main()
