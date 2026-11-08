#!/usr/bin/env python3
"""Build a synthetic applied_keys_parameter one-guard mutant; never simulates."""
from __future__ import annotations
import argparse,difflib,hashlib,importlib.util,json,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py"
HARNESS=ROOT/"scripts/remediation/test_f05_2a_authority_bootstrap_public.py"
R5=ROOT/"docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_keys_parameter"
MANIFEST=R5/"FIXTURE-MANIFEST.json"
OUT=ROOT/"docs/remediation/m3_f05_2a_applied_keys_parameter_mutant_r1_20261005"
CASE="applied_keys_parameter"; MUTATION="remove_key_binding_guard"
OLD="state.ordered_keys == initial_keys"; NEW="True"
AV="aiken v1.1.21+42babe5"; ASHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
CODE_SHA="76a66d88ecd09ccf78d32835dfaa976e6d0aab1aade7f550dd254c9a26806e39"
PID="efec0d79e496e2df81f8e3e27734c9718655dc577070c7519645fa29"
KEYS_SHA="eff6e11b5799dd63b02706204283cb77fe170dd08d07bfd4df5aca29ea001d3a"
SEED_SHA="5e0115ddb460b0c9eab9bba6499740f9e32cbf5e41fa02eb7f0a99d91473f086"
TX_SHA="f57020cb1d5ac3a7eebf8885472c62e6c0c1c4f8f2c9f85f890beac25194413f"
IN_SHA="4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe"
OUT_SHA="c36f6ae6016bdf289d87758b37b6feab4daf13be58deadff57fdae12bf562645"
def sha(x): return hashlib.sha256(x).hexdigest()
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser();p.add_argument("--aiken",type=Path,required=True);a=p.parse_args()
 aiken=a.aiken.resolve(strict=True)
 if subprocess.run([str(aiken),"--version"],capture_output=True,text=True,check=True).stdout.strip()!=AV or sha(aiken.read_bytes())!=ASHA: raise SystemExit("refusing non-pinned Aiken")
 if OUT.exists(): raise SystemExit("candidate exists; preserve it")
 b=load("akp_base",BASE);harness=load("akp_harness",HARNESS);cb,h=b.cb,b.h
 m=json.loads(MANIFEST.read_text());assert m["case_id"]==CASE and m["assertion"]["id"]==CASE
 app=m["policy_applications"]["negative"];pm=app["parameter_cbor"]
 kp,sp=R5/pm["initial_keys"]["file"],R5/pm["genesis_ref"]["file"]
 tp,ip,op=(R5/x for x in ("negative.tx.cbor","negative.raw_inputs.cbor","negative.raw_outputs.cbor"))
 for path,digest in ((kp,KEYS_SHA),(sp,SEED_SHA),(tp,TX_SHA),(ip,IN_SHA),(op,OUT_SHA)):
  if sha(path.read_bytes())!=digest: raise SystemExit("R5 artifact hash mismatch: "+path.name)
 keys=[bytes.fromhex(x) for x in pm["initial_keys"]["values_hex"]];sv=pm["genesis_ref"]["value"]
 seed=(bytes.fromhex(sv["tx_hash"]),sv["output_index"])
 params={"genesis_ref":h._output_reference(*seed),"initial_keys":h.list_data([h.byte_string(k) for k in keys])}
 if h.cbor(params["genesis_ref"])!=sp.read_bytes() or h.cbor(params["initial_keys"])!=kp.read_bytes(): raise SystemExit("parameter reconstruction differs from R5 CBOR")
 r5code=(R5/"negative.applied-policy.cbor").read_bytes()
 if sha(r5code)!=CODE_SHA or app["applied_policy_id"]!=PID: raise SystemExit("R5 policy identity mismatch")
 with tempfile.TemporaryDirectory(prefix="f05-akp-mutant-r1-") as d:
  work=Path(d);normal=b.compile_policy(aiken,params,work/"normal")
  if normal["code"]!=r5code or sha(normal["code"])!=CODE_SHA or normal["policy_id"].hex()!=PID: raise SystemExit("STOP: normal compile is not exact R5 identity")
  mutant=b.compile_policy(aiken,params,work/"mutant",MUTATION)
  if mutant["code"]==r5code or mutant["policy_id"]==normal["policy_id"]: raise SystemExit("mutant identity did not change")
  staged=work/"cardano";shutil.copytree(ROOT/"cardano",staged);harness._mutant_source(staged,MUTATION)
  orig=(ROOT/"cardano/lib/vams/f05_authority.ak").read_text();alter=(staged/"lib/vams/f05_authority.ak").read_text()
  patch="".join(difflib.unified_diff(orig.splitlines(True),alter.splitlines(True),fromfile="a/cardano/lib/vams/f05_authority.ak",tofile="b/cardano/lib/vams/f05_authority.ak"))
  changed=[x for x in patch.splitlines() if x.startswith(("+","-")) and not x.startswith(("+++","---"))]
  if orig.count(OLD)!=1 or alter.count(OLD)!=0 or changed!=["-    && "+OLD,"+    && True"]: raise SystemExit("mutation is not exactly the named equality guard")
  oldtx=cb.roundtrip(tp.read_bytes());tx=cb.roundtrip(tp.read_bytes());body,wit=tx[0],tx[1]
  red=cb.dumps(cb.map_get(cb.map_get(oldtx[1],5),[1,0]))
  if cb.dumps(cb.map_get(cb.map_get(wit,5),[1,0]))!=red: raise SystemExit("R5 redeemer mismatch")
  oldpid,newpid=bytes.fromhex(PID),mutant["policy_id"]
  tx[0]=b.rename(body,oldpid,newpid);cb.map_set(wit,7,cb.Tag(258,[mutant["code"]]))
  resolved=cb.roundtrip(op.read_bytes());inputs=cb.roundtrip(ip.read_bytes())
  raw,validation=b._fund_and_check(tx,resolved,inputs,mutant)
  final=cb.roundtrip(raw)
  if cb.dumps(cb.map_get(cb.map_get(final[1],5),[1,0]))!=red: raise SystemExit("Mint[0] redeemer not preserved")
  OUT.mkdir(parents=True)
  arts={"one-guard-mutant-control.tx.cbor":raw,"one-guard-mutant-control.raw_inputs.cbor":ip.read_bytes(),"one-guard-mutant-control.raw_outputs.cbor":cb.dumps(resolved),"one-guard-mutant-control.applied-policy.cbor":mutant["code"],"R5-exact-negative-redeemer.cbor":red,"MUTANT-SOURCE.patch":patch.encode()}
  fm={}
  for name,data in arts.items():(OUT/name).write_bytes(data);fm[name]={"bytes":len(data),"sha256":sha(data)}
  record={"schema_version":"f05-2a-applied-keys-parameter-mutant-candidate-r1","case_id":CASE,"original_case_id_preserved":True,"assertion":m["assertion"],"status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; case-and-mutation-PENDING","scope":"synthetic alternate applied policy only; no original-policy, ledger-admission, or live-network credit","entrypoint":"f05_authority_policy.f05_authority_policy.mint / Mint[0]","source_mutation":{"name":MUTATION,"predicate":OLD,"replacement":NEW,"source_path":"cardano/lib/vams/f05_authority.ak","changed_lines":changed,"original_source_sha256":sha(orig.encode()),"mutant_source_sha256":sha(alter.encode()),"patch_sha256":sha(patch.encode())},"normal_policy_recompile":{"code_sha256":sha(normal["code"]),"policy_id":normal["policy_id"].hex(),"exact_R5_code_and_ID_match":True},"exact_r5_binding":{"manifest":"docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_keys_parameter/FIXTURE-MANIFEST.json","manifest_sha256":sha(MANIFEST.read_bytes()),"negative_tx_sha256":TX_SHA,"initial_keys_sha256":KEYS_SHA,"genesis_ref_sha256":SEED_SHA,"raw_inputs_sha256":IN_SHA,"raw_outputs_sha256":OUT_SHA},"mutant":{"mutation":MUTATION,"policy_id":mutant["policy_id"].hex(),"program_sha256":sha(mutant["code"]),"transaction_sha256":sha(raw),"status":"not executed","validation":validation,"R5_negative_redeemer_sha256":sha(red),"PoP_signatures_preserved_from_R5":True},"credit":{"case":False,"mutation":False,"original_policy":False,"ledger_admission":False,"live_network":False},"toolchain":{"python":"3.12.14","aiken":AV,"aiken_sha256":ASHA,"normal_policy_recompiled":True,"mutant_recompiled":True,"simulation":"not run"},"artifacts":fm}
  (OUT/"FIXTURE-MANIFEST.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
  (OUT/"SHA256SUMS").write_text("".join(f"{sha(x.read_bytes())}  {x.name}\n" for x in sorted(OUT.iterdir()) if x.is_file() and x.name!="SHA256SUMS"))
  print(json.dumps({"candidate":record["status"],"normal_policy_id":PID,"mutant_policy_id":mutant["policy_id"].hex(),"tx_sha256":sha(raw),"output":str(OUT)},sort_keys=True))
 return 0
if __name__=="__main__":raise SystemExit(main())
