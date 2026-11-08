#!/usr/bin/env python3
"""Create an unexecuted applied-genesis one-guard mutant fixture."""
from __future__ import annotations
import difflib, hashlib, importlib.util, json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE_PATH=ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py"
REG=ROOT/"docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
OUT=ROOT/"docs/remediation/m3_f05_2a_applied_genesis_mutant_r1_20261005"
CASE="applied_genesis_parameter"
MUTATION="remove_seed_guard"
OLD="expect count_seed_input(tx.inputs, genesis_ref) == 1"
NEW="expect True"
POLICY_SOURCE=Path("validators/f05_authority_policy.ak")
A_VERSION="aiken v1.1.21+42babe5"
A_SHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
def sha(x): return hashlib.sha256(x).hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s)
 sys.modules[name]=m; s.loader.exec_module(m); return m
def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--aiken",type=Path,required=True); a=p.parse_args()
 aiken=a.aiken.resolve(strict=True)
 v=subprocess.run([str(aiken),"--version"],capture_output=True,text=True,check=True).stdout.strip()
 if v!=A_VERSION or sha(aiken.read_bytes())!=A_SHA: raise SystemExit("non-pinned Aiken")
 if OUT.exists(): raise SystemExit("preserve existing package; choose a new revision")
 b=load("applied_genesis_base",BASE_PATH); h=b.h
 registry=json.loads(REG.read_text()); assertion=next(x for x in registry["negative_cases"] if x["id"]==CASE)
 signers=h._ephemeral_committee()
 try:
  keys=[s.public_key for s in signers[:5]]
  params,changed,seed=b.params_for(CASE,keys)
  if changed!=keys or len(keys)!=5: raise ValueError("case must retain original five keys")
  with tempfile.TemporaryDirectory(prefix="f05-genesis-mutant-") as td:
   work=Path(td); normal=b.compile_policy(aiken,params,work/"normal")
   mutant=b.compile_policy(aiken,params,work/"mutant",MUTATION)
   if normal["code"]==mutant["code"] or normal["policy_id"]==mutant["policy_id"]: raise ValueError("mutant identity unchanged")
   staged=work/"source"; shutil.copytree(ROOT/"cardano",staged)
   original=(ROOT/"cardano"/POLICY_SOURCE).read_text()
   h._mutant_source(staged,MUTATION); altered=(staged/POLICY_SOURCE).read_text()
   patch="".join(difflib.unified_diff(original.splitlines(True),altered.splitlines(True),fromfile="a/cardano/validators/f05_authority_policy.ak",tofile="b/cardano/validators/f05_authority_policy.ak"))
   changes=[x for x in patch.splitlines() if x.startswith(("+","-")) and not x.startswith(("+++","---"))]
   if original.count(OLD)!=1 or altered.count(OLD)!=0 or changes!=["-  "+OLD,"+  "+NEW]: raise ValueError("not a one-guard-only source mutation")
   msg=h._canonical_pop_message(*seed,normal["state_credential"],keys)
   proofs=[s.sign(msg) for s in h._signers_for_keys(keys,signers)]
   raw,rin,rout=tuple((b.FIX/n).read_bytes() for n in b.HASHES)
   if {n:sha((b.FIX/n).read_bytes()) for n in b.HASHES}!=b.HASHES: raise ValueError("frozen baseline hash mismatch")
   positive=b.build_tx(raw,rin,rout,normal,seed,keys,proofs,True)
   negative=b.build_tx(raw,rin,rout,normal,seed,keys,proofs,False)
   control=b.build_tx(raw,rin,rout,mutant,seed,keys,proofs,False)
   OUT.mkdir(parents=True); files={}; policies={}
   for label,built,pol in (("positive-control",positive,normal),("negative",negative,normal),("one-guard-mutant-control",control,mutant)):
    tx,inputs,outputs,validation=built
    pieces={"tx.cbor":tx,"raw_inputs.cbor":inputs,"raw_outputs.cbor":outputs,"applied-policy.cbor":pol["code"],
      "genesis_ref.cbor":h.cbor(params["genesis_ref"]),"initial_keys.cbor":h.cbor(params["initial_keys"])}
    for suffix,data in pieces.items():
     name=label+"."+suffix;(OUT/name).write_bytes(data);files[name]={"bytes":len(data),"sha256":sha(data)}
    policies[label]={"policy_id":pol["policy_id"].hex(),"program_sha256":sha(pol["code"]),
      "validation":validation,"seed_in_inputs":label=="positive-control"}
   (OUT/"MUTANT-SOURCE.patch").write_text(patch)
   files["MUTANT-SOURCE.patch"]={"bytes":len(patch.encode()),"sha256":sha(patch.encode())}
   manifest={"schema_version":"f05-2a-applied-genesis-mutant-candidate-r1","case_id":CASE,
    "original_case_id_preserved":True,"assertion":assertion,
    "status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; case-and-mutation-PENDING",
    "scope":"synthetic alternate applied policy only; no original-policy, ledger-admission, or live-network evidence",
    "entrypoint":"f05_authority_policy.f05_authority_policy.mint / Mint[0]",
    "source_mutation":{"name":MUTATION,"file":str(POLICY_SOURCE),"changed_lines":changes,
      "original_source_sha256":sha(original.encode()),"mutant_source_sha256":sha(altered.encode())},
    "policy_applications":policies,"negative":{"status":"PENDING","tx_sha256":sha(negative[0]),
      "applied_parameter_seed_ref":{"tx_hash":seed[0].hex(),"output_index":seed[1]},
      "seed_retained_in_applied_parameters":True,"seed_retained_in_datum_and_pop":True,"seed_omitted_from_inputs":True},
    "positive_control":{"status":"not executed","tx_sha256":sha(positive[0])},
    "one_guard_mutant_control":{"mutation":MUTATION,"status":"not executed","tx_sha256":sha(control[0]),
      "mutant_policy_id":mutant["policy_id"].hex()},
    "toolchain":{"python":"3.12.14","aiken":A_VERSION,"aiken_sha256":A_SHA,"mutant_recompiled":True},
    "credit":{"case":False,"mutation":False,"original_policy":False,"ledger_admission":False,"live_network":False},
    "artifacts":files}
   (OUT/"FIXTURE-MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
   sums="".join(f"{sha(x.read_bytes())}  {x.name}\n" for x in sorted(OUT.iterdir()) if x.is_file() and x.name!="SHA256SUMS")
   (OUT/"SHA256SUMS").write_text(sums)
   print(json.dumps({"status":manifest["status"],"case_id":CASE,"negative_tx_sha256":sha(negative[0]),
    "mutant_tx_sha256":sha(control[0]),"normal_policy_id":normal["policy_id"].hex(),
    "mutant_policy_id":mutant["policy_id"].hex(),"output":str(OUT)},sort_keys=True))
 finally:
  for signer in signers: signer.close()
if __name__=="__main__": raise SystemExit(main())

