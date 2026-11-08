"""Focused structural exact-byte review checks for R2; no simulation."""
from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BUILDER=ROOT/"scripts/remediation/build_f05_2a_applied_genesis_mutant_r2.py"
SPEC=importlib.util.spec_from_file_location("f05_genesis_mutant_r2",BUILDER)
b=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=b;SPEC.loader.exec_module(b)
BASE_SPEC=importlib.util.spec_from_file_location("f05_r2_base",b.BASE_PATH)
base=importlib.util.module_from_spec(BASE_SPEC);sys.modules[BASE_SPEC.name]=base;BASE_SPEC.loader.exec_module(base)
h=base.h;cb=base.cb;OUT=b.OUT;R5=b.R5
def sha(raw): return hashlib.sha256(raw).hexdigest()
def verify(public,signature,message):
 prefix=bytes.fromhex("302a300506032b6570032100");fds=[]
 try:
  for name,data in (("pub",prefix+public),("sig",signature),("msg",message)):
   fd=os.memfd_create("vams-r2-verify-"+name,0);fds.append(fd);assert os.write(fd,data)==len(data);os.lseek(fd,0,0)
  pub,sig,msg=fds
  proc=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pub}","-keyform","DER","-in",f"/proc/self/fd/{msg}","-sigfile",f"/proc/self/fd/{sig}"],pass_fds=tuple(fds),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
  assert proc.returncode==0
 finally:
  for fd in fds: os.close(fd)

def test_r2_exact_r5_bound_mutant_candidate():
 m=json.loads((OUT/"FIXTURE-MANIFEST.json").read_text())
 r5m=json.loads(b.R5_MANIFEST.read_text())
 assert m["schema_version"]=="f05-2a-applied-genesis-mutant-candidate-r2"
 assert m["case_id"]=="applied_genesis_parameter" and m["original_case_id_preserved"]
 assert m["assertion"]==r5m["assertion"]
 assert m["status"].startswith("candidate-awaiting-independent-byte-review")
 assert m["scope"]=="synthetic alternate applied policy only; no original-policy, ledger-admission, or live-network credit"
 assert m["credit"]=={"case":False,"mutation":False,"original_policy":False,"ledger_admission":False,"live_network":False}
 assert m["mutant"]["status"]=="not executed"
 # Parameter bytes are exact R5 inputs; do not regenerate keys or PoPs.
 keys_meta=r5m["policy_applications"]["negative"]["parameter_cbor"]["initial_keys"]
 seed_meta=r5m["policy_applications"]["negative"]["parameter_cbor"]["genesis_ref"]
 keys_path=R5/keys_meta["file"];seed_path=R5/seed_meta["file"]
 assert sha(keys_path.read_bytes())==b.EXPECTED_R5_KEYS_SHA
 assert sha(seed_path.read_bytes())==b.EXPECTED_R5_SEED_SHA
 keys=[bytes.fromhex(k) for k in keys_meta["values_hex"]]
 seed_value=seed_meta["value"];seed=(bytes.fromhex(seed_value["tx_hash"]),seed_value["output_index"])
 assert (OUT/"R5-exact-negative-redeemer.cbor").read_bytes()==base.cb.dumps(base.cb.map_get(base.cb.map_get(cb.roundtrip((R5/"negative.tx.cbor").read_bytes())[1],5),[1,0]))
 # Exact R5 normal compiled code and policy identity are mandatory.
 r5_code=(R5/"negative.applied-policy.cbor").read_bytes()
 assert sha(r5_code)==b.EXPECTED_R5_CODE_SHA
 r5pid=hashlib.blake2b(b"\x03"+r5_code,digest_size=28).hexdigest()
 assert r5pid==b.EXPECTED_R5_POLICY_ID
 assert m["normal_policy_recompile"]=={"code_sha256":b.EXPECTED_R5_CODE_SHA,"policy_id":b.EXPECTED_R5_POLICY_ID,"exact_R5_code_and_ID_match":True}
 # R6 accepted positive and R7 named negative remain the paired normal-run references.
 for name,path,digest,stage in (
  ("R6_positive_control",b.R6_RUN,"457cb0ec423477df1d232501506e713f3ce7800210635b35535abff0b2417c8e","script_accepted"),
  ("R7_negative_control",b.R7_RUN,"651fc64426b0968828a597564b48ae4a6dbba68b0f5d516d37f28b8bc5924d7e","compiled_evaluation")):
  record=json.loads(path.read_text());entry=m["exact_r5_binding"][name]
  assert sha(path.read_bytes())==digest==entry["sha256"]
  assert record["attempt"]["runner_result"]["simulator_result"]["stage"]==stage
  assert record["attempt"]["runner_result"]["simulator_result"]["target_script_invoked"] is True
 # Candidate uses the exact R5 transaction inputs, datum, and proof redeemer.
 old=cb.roundtrip((R5/"negative.tx.cbor").read_bytes())
 raw=(OUT/"one-guard-mutant-control.tx.cbor").read_bytes();tx=cb.roundtrip(raw);body,wit=tx[0],tx[1]
 assert sha((R5/"negative.tx.cbor").read_bytes())==b.EXPECTED_R5_TX_SHA
 assert cb.map_get(body,0)==cb.map_get(old[0],0)
 assert (OUT/"one-guard-mutant-control.raw_inputs.cbor").read_bytes()==(R5/"negative.raw_inputs.cbor").read_bytes()
 assert cb.map_get(cb.map_get(body,1)[0],2)==cb.map_get(cb.map_get(old[0],1)[0],2)
 old_red=cb.map_get(cb.map_get(old[1],5),[1,0]);new_red=cb.map_get(cb.map_get(wit,5),[1,0])
 assert cb.dumps(new_red)==cb.dumps(old_red)
 assert isinstance(new_red,list) and len(new_red)==2
 assert isinstance(new_red[0],cb.Tag) and new_red[0].number==121
 assert new_red[1]==cb.map_get(cb.map_get(cb.roundtrip((base.FIX/"valid.tx.cbor").read_bytes())[1],5),[1,0])[1]
 proof_hex=r5m["artifacts"]["negative.validation"]["mint0_redeemer"]["proof_signatures_hex"]
 proofs=new_red[0].value[0]
 assert [sig.hex() for sig in proofs]==proof_hex and len(proofs)==5
 assert hashlib.sha256(cb.dumps(new_red[0])).hexdigest()==r5m["artifacts"]["negative.validation"]["mint0_redeemer"]["cbor_sha256"]
 pop=h._canonical_pop_message(seed[0],seed[1],base.STATE,keys)
 for pub,sig in zip(keys,proofs): verify(pub,sig,pop)
 # Exact one-guard source change.
 patch=(OUT/"MUTANT-SOURCE.patch").read_text()
 changed=[line for line in patch.splitlines() if line.startswith(("+","-")) and not line.startswith(("+++","---"))]
 assert changed==["-  expect count_seed_input(tx.inputs, genesis_ref) == 1","+  expect True"]
 assert m["source_mutation"]["changed_lines"]==changed
 # Rebound script/policy, Mint[0], and output NFT all match.
 code=(OUT/"one-guard-mutant-control.applied-policy.cbor").read_bytes()
 mutant_id=hashlib.blake2b(b"\x03"+code,digest_size=28).digest()
 assert mutant_id.hex()==m["mutant"]["policy_id"]
 assert mutant_id.hex()!=r5pid
 assert cb.map_get(body,9).pairs and [pid for pid,_ in cb.map_get(body,9).pairs]==[mutant_id]
 v3=cb.map_get(wit,7);assert isinstance(v3,cb.Tag) and v3.number==258 and v3.value==[code]
 assert m["entrypoint"].endswith("mint / Mint[0]")
 # Seed stays in applied parameters/datum/PoPs, and remains omitted from the tx input set.
 assert (R5/seed_meta["file"]).read_bytes()==seed_path.read_bytes()
 assert [seed[0],seed[1]] not in cb.map_get(body,0).value
 assert cb.map_get(cb.map_get(body,1)[0],2)==cb.map_get(cb.map_get(old[0],1)[0],2)
 # Funding signatures bind the final body and resolved input output addresses.
 resolved=cb.roundtrip((OUT/"one-guard-mutant-control.raw_outputs.cbor").read_bytes())
 body_hash=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
 ws=cb.map_get(wit,0);assert isinstance(ws,cb.Tag) and ws.number==258
 for pub,sig in ws.value: verify(pub,sig,body_hash)
 assert {hashlib.blake2b(pub,digest_size=28).digest() for pub,_ in ws.value}=={cb.map_get(out,0)[1:] for out in resolved}
 # Funding/output values and minted native asset are conserved.
 input_coin=sum(cb.map_get(out,1) for out in resolved)
 output_coin=0;native={}
 for out in cb.map_get(body,1):
  val=cb.map_get(out,1)
  if isinstance(val,int): output_coin+=val
  else:
   output_coin+=val[0]
   for pid,assets in val[1].pairs:
    for asset,q in assets.pairs:native[(pid,asset)]=native.get((pid,asset),0)+q
 minted={(pid,asset):q for pid,assets in cb.map_get(body,9).pairs for asset,q in assets.pairs}
 assert (input_coin,output_coin,cb.map_get(body,2))==(17_000_000,16_000_000,1_000_000)
 assert native==minted=={(mutant_id,b"VAMS-F05-AUTH-V3"):1}
 assert m["mutant"]["validation"]["ada_conservation"] is True
 assert m["mutant"]["validation"]["native_asset_conservation"] is True
 assert m["mutant"]["validation"]["valid_body_bound_ephemeral_signatures"] is True
 assert m["mutant"]["validation"]["private_keys_persisted"] is False
 sums={}
 for line in (OUT/"SHA256SUMS").read_text().splitlines():
  digest,name=line.split("  ",1);sums[name]=digest
 files={p.name for p in OUT.iterdir() if p.is_file() and p.name!="SHA256SUMS"}
 assert set(sums)==files
 for name,digest in sums.items(): assert sha((OUT/name).read_bytes())==digest

