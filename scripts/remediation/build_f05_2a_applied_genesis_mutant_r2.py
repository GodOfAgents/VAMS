#!/usr/bin/env python3
"""Build an R2 mutant bound byte-for-byte to the retained R5 applied parameters."""
from __future__ import annotations
import difflib, hashlib, importlib.util, json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE_PATH=ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py"
R5=ROOT/"docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_genesis_parameter"
R5_MANIFEST=R5/"FIXTURE-MANIFEST.json"
R6_RUN=ROOT/"docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r6_20261005/RUN.json"
R7_RUN=ROOT/"docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r7_20261005/RUN.json"
OUT=ROOT/"docs/remediation/m3_f05_2a_applied_genesis_mutant_r2_20261005"
CASE="applied_genesis_parameter"
MUTATION="remove_seed_guard"
OLD="expect count_seed_input(tx.inputs, genesis_ref) == 1"
NEW="expect True"
A_VERSION="aiken v1.1.21+42babe5"
A_SHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
EXPECTED_R5_CODE_SHA="66d372129d322008e8b095f87b0b7726d3020868954361578a774f4afe8e6c5d"
EXPECTED_R5_POLICY_ID="fc305fd82585607dc1998425cbe3bce8f43667e1ac161c448098c058"
EXPECTED_R5_KEYS_SHA="9b604d528d46f510b808d00ad985e498522a7d60595823ce016adb647ff9556f"
EXPECTED_R5_SEED_SHA="51f08c55f440a2116b42e5283fc76d8be4d707788d3bc765023620199af45c75"
EXPECTED_R5_TX_SHA="67a3a40a149c5972720b23c18d37bb65f4ead04f0eaae421c3f3aa6440cb1e6b"
def sha(raw): return hashlib.sha256(raw).hexdigest()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec)
 sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
def main():
 import argparse
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--aiken",type=Path,required=True);args=ap.parse_args()
 aiken=args.aiken.resolve(strict=True)
 ver=subprocess.run([str(aiken),"--version"],capture_output=True,text=True,check=True).stdout.strip()
 if ver!=A_VERSION or sha(aiken.read_bytes())!=A_SHA: raise SystemExit("refusing non-pinned Aiken")
 if OUT.exists(): raise SystemExit("R2 package already exists; preserve it and choose a new revision")
 if not R6_RUN.is_file() or not R7_RUN.is_file(): raise SystemExit("paired R6/R7 normal-control run records are required")
 b=load("r2_applied_family_builder",BASE_PATH);h=b.h;cb=b.cb
 manifest=json.loads(R5_MANIFEST.read_text())
 if manifest["case_id"]!=CASE: raise SystemExit("R5 case ID mismatch")
 app=manifest["policy_applications"]["negative"];params_meta=app["parameter_cbor"]
 key_path=R5/params_meta["initial_keys"]["file"];seed_path=R5/params_meta["genesis_ref"]["file"]
 if sha(key_path.read_bytes())!=EXPECTED_R5_KEYS_SHA or sha(seed_path.read_bytes())!=EXPECTED_R5_SEED_SHA: raise SystemExit("R5 exact applied-parameter artifact hash mismatch")
 keys=[bytes.fromhex(k) for k in params_meta["initial_keys"]["values_hex"]]
 seed_value=params_meta["genesis_ref"]["value"];seed=(bytes.fromhex(seed_value["tx_hash"]),seed_value["output_index"])
 params={"genesis_ref":h._output_reference(*seed),"initial_keys":h.list_data([h.byte_string(k) for k in keys])}
 if h.cbor(params["initial_keys"])!=key_path.read_bytes() or h.cbor(params["genesis_ref"])!=seed_path.read_bytes(): raise SystemExit("reconstructed applied parameters differ from exact R5 CBOR")
 r5_code=(R5/"negative.applied-policy.cbor").read_bytes()
 if sha(r5_code)!=EXPECTED_R5_CODE_SHA or app["applied_policy_id"]!=EXPECTED_R5_POLICY_ID: raise SystemExit("R5 negative policy evidence identity mismatch")
 r5_tx_raw=(R5/"negative.tx.cbor").read_bytes()
 if sha(r5_tx_raw)!=EXPECTED_R5_TX_SHA: raise SystemExit("R5 negative transaction identity mismatch")
 signers=h._ephemeral_committee()
 try:
  with tempfile.TemporaryDirectory(prefix="f05-genesis-mutant-r2-") as td:
   work=Path(td)
   normal=b.compile_policy(aiken,params,work/"normal")
   # Mandatory deterministic identity gate: stop before building anything if R5 normal differs.
   if normal["code"]!=r5_code or sha(normal["code"])!=EXPECTED_R5_CODE_SHA or normal["policy_id"].hex()!=EXPECTED_R5_POLICY_ID:
    raise SystemExit("STOP: deterministic normal compile differs from exact R5 policy bytes or ID")
   mutant=b.compile_policy(aiken,params,work/"mutant",MUTATION)
   if mutant["code"]==r5_code or mutant["policy_id"]==normal["policy_id"]: raise SystemExit("mutant did not change compiled script identity")
   source_rel=Path("validators/f05_authority_policy.ak")
   original=(ROOT/"cardano"/source_rel).read_text(encoding="utf-8")
   staged=work/"source";shutil.copytree(ROOT/"cardano",staged);h._mutant_source(staged,MUTATION)
   altered=(staged/source_rel).read_text(encoding="utf-8")
   patch="".join(difflib.unified_diff(original.splitlines(True),altered.splitlines(True),
      fromfile="a/cardano/validators/f05_authority_policy.ak",tofile="b/cardano/validators/f05_authority_policy.ak"))
   changed=[line for line in patch.splitlines() if line.startswith(("+","-")) and not line.startswith(("+++","---"))]
   if original.count(OLD)!=1 or altered.count(OLD)!=0 or changed!=["-  "+OLD,"+  "+NEW]:
    raise SystemExit("staged source diff is not exactly the remove_seed_guard one-line mutation")
   old_tx=cb.roundtrip(r5_tx_raw);tx=cb.roundtrip(r5_tx_raw)
   old_body,old_wit=old_tx[0],old_tx[1];body,wit=tx[0],tx[1]
   old_pid=bytes.fromhex(EXPECTED_R5_POLICY_ID);new_pid=mutant["policy_id"]
   tx[0]=b.rename(body,old_pid,new_pid)
   body=tx[0]
   cb.map_set(wit,7,cb.Tag(258,[mutant["code"]]))
   raw_inputs=(R5/"negative.raw_inputs.cbor").read_bytes()
   resolved=cb.roundtrip((R5/"negative.raw_outputs.cbor").read_bytes())
   inputs=cb.roundtrip(raw_inputs)
   # The original proof redeemer/exunits remain byte-equivalent; only mint, output NFT,
   # V3 code, and body-bound funding witnesses are rebound to the mutant policy.
   old_redeemer=cb.dumps(cb.map_get(cb.map_get(old_wit,5),[1,0]))
   if cb.dumps(cb.map_get(cb.map_get(wit,5),[1,0]))!=old_redeemer: raise SystemExit("R5 negative PoP redeemer changed")
   tx_raw,validation=b._fund_and_check(tx,resolved,inputs,mutant)
   final=cb.roundtrip(tx_raw)
   if cb.dumps(cb.map_get(cb.map_get(final[1],5),[1,0]))!=old_redeemer: raise SystemExit("final mutant PoP redeemer differs from R5")
   OUT.mkdir(parents=True)
   files={}
   artifacts={"one-guard-mutant-control.tx.cbor":tx_raw,
     "one-guard-mutant-control.raw_inputs.cbor":raw_inputs,
     "one-guard-mutant-control.raw_outputs.cbor":cb.dumps(resolved),
     "one-guard-mutant-control.applied-policy.cbor":mutant["code"],
     "R5-exact-negative-redeemer.cbor":old_redeemer}
   patch_path=OUT/"MUTANT-SOURCE.patch";patch_path.write_text(patch,encoding="utf-8")
   artifacts[patch_path.name]=patch.encode()
   for name,data in artifacts.items():
    (OUT/name).write_bytes(data);files[name]={"bytes":len(data),"sha256":sha(data)}
   r6=json.loads(R6_RUN.read_text());r7=json.loads(R7_RUN.read_text())
   record={"schema_version":"f05-2a-applied-genesis-mutant-candidate-r2","case_id":CASE,
    "original_case_id_preserved":True,"assertion":manifest["assertion"],
    "status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; case-and-mutation-PENDING",
    "scope":"synthetic alternate applied policy only; no original-policy, ledger-admission, or live-network credit",
    "entrypoint":"f05_authority_policy.f05_authority_policy.mint / Mint[0]",
    "source_mutation":{"name":MUTATION,"changed_lines":changed,"original_source_sha256":sha(original.encode()),
      "mutant_source_sha256":sha(altered.encode()),"patch_sha256":sha(patch.encode())},
    "exact_r5_binding":{"case_manifest":"docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_genesis_parameter/FIXTURE-MANIFEST.json",
      "case_manifest_sha256":sha(R5_MANIFEST.read_bytes()),"negative_transaction_sha256":EXPECTED_R5_TX_SHA,
      "initial_keys_file":"docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_genesis_parameter/negative.initial_keys.cbor",
      "initial_keys_sha256":EXPECTED_R5_KEYS_SHA,"genesis_ref_file":"docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_genesis_parameter/negative.genesis_ref.cbor",
      "genesis_ref_sha256":EXPECTED_R5_SEED_SHA,"normal_policy_file":"docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_genesis_parameter/negative.applied-policy.cbor",
      "normal_policy_sha256":EXPECTED_R5_CODE_SHA,"normal_policy_id":EXPECTED_R5_POLICY_ID,
      "R6_positive_control":{"path":"docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r6_20261005/RUN.json","sha256":sha(R6_RUN.read_bytes()),
        "stage":r6["attempt"]["runner_result"]["simulator_result"]["stage"]},
      "R7_negative_control":{"path":"docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r7_20261005/RUN.json","sha256":sha(R7_RUN.read_bytes()),
        "stage":r7["attempt"]["runner_result"]["simulator_result"]["stage"]}},
    "mutant":{"mutation":MUTATION,"policy_id":mutant["policy_id"].hex(),"program_sha256":sha(mutant["code"]),
      "transaction_sha256":sha(tx_raw),"status":"not executed","validation":validation,
      "R5_negative_redeemer_sha256":sha(old_redeemer),"PoP_signatures_preserved_from_R5":True},
    "normal_policy_recompile":{"code_sha256":sha(normal["code"]),"policy_id":normal["policy_id"].hex(),
      "exact_R5_code_and_ID_match":True},
    "credit":{"case":False,"mutation":False,"original_policy":False,"ledger_admission":False,"live_network":False},
    "toolchain":{"python":"3.12.14","aiken":A_VERSION,"aiken_sha256":A_SHA,"mutant_recompiled":True,"simulation":"not run"},
    "artifacts":files}
   (OUT/"FIXTURE-MANIFEST.json").write_text(json.dumps(record,indent=2,sort_keys=True)+chr(10))
   sums="".join(f"{sha(p.read_bytes())}  {p.name}"+chr(10) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="SHA256SUMS")
   (OUT/"SHA256SUMS").write_text(sums)
   print(json.dumps({"status":record["status"],"normal_policy_id":normal["policy_id"].hex(),
    "mutant_policy_id":mutant["policy_id"].hex(),"mutant_tx_sha256":sha(tx_raw),
    "output":str(OUT)},sort_keys=True))
   return 0
 finally:
  for signer in signers: signer.close()
if __name__=="__main__": raise SystemExit(main())

