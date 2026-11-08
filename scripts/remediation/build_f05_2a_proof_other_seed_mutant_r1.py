#!/usr/bin/env python3
"""Build an unexecuted, R18-bound one-guard seed-domain mutant candidate."""
from __future__ import annotations
import difflib, hashlib, importlib.util, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
R18=ROOT/"docs/remediation/m3_f05_2a_proof_other_seed_negative_attempt_r1_20261005/RUN.json"
R18_REVIEW=ROOT/"docs/remediation/m3_f05_2a_proof_other_seed_negative_review_r1_20261005/INDEPENDENT-REVIEW.md"
R18_CHECKS=ROOT/"docs/remediation/m3_f05_2a_proof_domain_family_r1_20261005/r2_signature_for_other_seed"
OUT=ROOT/"docs/remediation/m3_f05_2a_proof_other_seed_mutant_r1_20261005"
CID="r2_signature_for_other_seed"
R18_RUN_SHA="2f3d042cd4350d821b0ce91dafa4cddfdb36dc23258eefb6115b947fd764b0be"
R18_REVIEW_SHA="a2d5d636cf1489341cc61ba30e0c7b638da223958a785219dfb6c016d1a61460"
AIKEN_SHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
OLD="let bootstrap_message = authority_genesis_pop_preimage(\n    genesis_ref,\n    state_validator_script_hash,\n    initial_keys,\n  )"
NEW='let bootstrap_message = authority_genesis_pop_preimage(\n    OutputReference {\n      transaction_id: #"adadadadadadadadadadadadadadadadadadadadadadadadadadadadadadadad",\n      output_index: genesis_ref.output_index,\n    },\n    state_validator_script_hash,\n    initial_keys,\n  )'
def sha(b):return hashlib.sha256(b).hexdigest()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def patch_seed_argument(path):
 source=path.read_text(encoding="utf-8")
 if source.count(OLD)!=1:raise ValueError("exact bootstrap preimage call not unique; refusing mutant")
 changed=source.replace(OLD,NEW,1)
 if changed==source or changed.count(NEW)!=1:raise ValueError("seed-domain patch did not apply exactly once")
 path.write_text(changed,encoding="utf-8")
 return source,changed
def sums(directory):
 return "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(directory.iterdir()) if p.is_file() and p.name!="SHA256SUMS")
def build(aiken):
 fam=load("f05_applied_family_mutant",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
 h,cb=fam.h,fam.cb
 if OUT.exists():raise FileExistsError("preserve existing mutant package")
 if sha(R18.read_bytes())!=R18_RUN_SHA or sha(R18_REVIEW.read_bytes())!=R18_REVIEW_SHA:raise ValueError("R18 execution/review identity mismatch")
 run=json.loads(R18.read_text()); review=R18_REVIEW.read_text()
 if "PASS for execution integrity" not in review or "FAIL/PENDING for named-condition attribution" not in review:raise ValueError("R18 independent assessment is not the expected accepted-pending review")
 manifest=json.loads((R18_CHECKS/"FIXTURE-MANIFEST.json").read_text())
 if manifest["case_id"]!=CID or manifest["negative"]["transaction_sha256"]!=run["attempt"]["runner_result"]["submitted_sha256"]["transaction"]:raise ValueError("R18 case identity mismatch")
 for line in (R18_CHECKS/"SHA256SUMS").read_text().splitlines():
  digest,name=line.split("  ",1)
  if sha((R18_CHECKS/name).read_bytes())!=digest:raise ValueError("R18 package checksum mismatch")
 tx_raw=(R18_CHECKS/"negative.tx.cbor").read_bytes()
 ins_raw=(R18_CHECKS/"negative.raw_inputs.cbor").read_bytes()
 outs_raw=(R18_CHECKS/"negative.raw_outputs.cbor").read_bytes()
 msg_raw=(R18_CHECKS/"negative.proof-message.bin").read_bytes()
 applied_code=(R18_CHECKS/"negative.applied-policy.cbor").read_bytes()
 seed_raw=(R18_CHECKS/"negative.genesis_ref.cbor").read_bytes()
 keys_raw=(R18_CHECKS/"negative.initial_keys.cbor").read_bytes()
 if tuple(map(sha,(tx_raw,ins_raw,outs_raw,msg_raw)))!=(run["attempt"]["runner_result"]["submitted_sha256"]["transaction"],run["attempt"]["runner_result"]["submitted_sha256"]["raw_inputs"],run["attempt"]["runner_result"]["submitted_sha256"]["raw_outputs"],manifest["negative"]["proof_message_sha256"]):raise ValueError("R18 fixture bytes do not match reviewed/run record")
 keys=[bytes.fromhex(x) for x in manifest["applied_parameters"]["committee_public_keys_hex"]]
 seedmeta=manifest["applied_parameters"]["seed_ref"]
 seed=(bytes.fromhex(seedmeta["tx_hash"]),seedmeta["output_index"])
 if h.cbor(h._output_reference(*seed))!=seed_raw or h.cbor(h.list_data([h.byte_string(k) for k in keys]))!=keys_raw:raise ValueError("R18 applied parameters differ from public manifest")
 source_tx=cb.roundtrip(tx_raw)
 redeemer=cb.map_get(cb.map_get(source_tx[1],5),[1,0])
 if not isinstance(redeemer,list) or redeemer[0].number!=121:raise ValueError("R18 Mint[0] bootstrap redeemer not found")
 proofs=redeemer[0].value[0]
 if len(proofs)!=5 or [p.hex() for p in proofs]!=manifest["negative"]["validation"]["mint0_redeemer"]["proof_signatures_hex"]:raise ValueError("R18 negative PoP bytes changed")
 if len(msg_raw)!=279 or sha(msg_raw)!="5fa13e0c6240b7b75d154f152de2bf376f93d2af3dd8642c7d25f4757e2a8542":raise ValueError("R18 wrong-seed proof message changed")
 wrong_seed=(bytes.fromhex("ad"*32),7)
 if msg_raw[48:80]!=wrong_seed[0]:raise ValueError("R18 proof message seed bytes mismatch")
 params={"genesis_ref":h._output_reference(*seed),"initial_keys":h.list_data([h.byte_string(k) for k in keys])}
 with tempfile.TemporaryDirectory(prefix="f05-proof-domain-mutant-") as td:
  temp=Path(td)
  normal=fam.compile_policy(aiken,params,temp/"normal")
  if normal["code"]!=applied_code or normal["policy_id"].hex()!=manifest["applied_policy"]["policy_id"]:raise ValueError("normal rebuild does not reproduce exact R18 applied script/policy")
  staged=temp/"mutant-source";shutil.copytree(ROOT/"cardano",staged)
  policy_source=staged/"validators/f05_authority_policy.ak"
  before,after=patch_seed_argument(policy_source)
  changed_lines=list(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile="a/f05_authority_policy.ak",tofile="b/f05_authority_policy.ak"))
  mutant=fam.h._compile(staged,aiken,temp/"mutant-build",params)
  if mutant["state_credential"]!=normal["state_credential"]:raise ValueError("mutant changed state validator identity")
  if mutant["code"]==normal["code"]:raise ValueError("mutant did not change compiled script")
  policy={"code":mutant["code"],"policy_id":mutant["policy_id"],"state_credential":mutant["state_credential"]}
  original_policy_hex=fam.ORIGINAL
  fam.ORIGINAL=manifest["applied_policy"]["policy_id"]
  try:
   rebuilt=fam.build_tx(tx_raw,ins_raw,outs_raw,policy,seed,keys,proofs,True)
  finally:fam.ORIGINAL=original_policy_hex
  mutant_tx,mutant_ins,mutant_outs,validation=rebuilt
  # Transactional identity is independently re-derived from the compiled mutant bytes.
  if hashlib.blake2b(bytes([3])+policy["code"],digest_size=28).digest()!=policy["policy_id"]:raise ValueError("mutant policy ID does not derive from compiled V3 bytes")
  out=OUT/CID;out.mkdir(parents=True)
  artifacts={
   "r18-negative.tx.cbor":tx_raw,"r18-negative.raw_inputs.cbor":ins_raw,"r18-negative.raw_outputs.cbor":outs_raw,
   "r18-negative.applied-policy.cbor":applied_code,"r18-negative.proof-message.bin":msg_raw,
   "r18-negative.genesis_ref.cbor":seed_raw,"r18-negative.initial_keys.cbor":keys_raw,
   "mutant.tx.cbor":mutant_tx,"mutant.raw_inputs.cbor":mutant_ins,"mutant.raw_outputs.cbor":mutant_outs,
   "mutant.applied-policy.cbor":policy["code"],"mutant.genesis_ref.cbor":seed_raw,"mutant.initial_keys.cbor":keys_raw,
   "mutant.proof-message.bin":msg_raw,"mutant-policy-source.ak":policy_source.read_bytes(),
   "SOURCE-DIFF.patch":"".join(changed_lines).encode()}
  hashes={}
  for name,data in artifacts.items():(out/name).write_bytes(data);hashes[name]={"sha256":sha(data),"bytes":len(data)}
  result=cb.roundtrip(mutant_tx);body,wit=result[0],result[1]
  mint=cb.map_get(body,9);scripts=cb.map_get(wit,7)
  if [k for k,_ in mint.pairs]!=[policy["policy_id"]]:raise ValueError("mutant transaction mint map does not bind only mutant policy")
  if scripts.number!=258 or scripts.value!=[policy["code"]]:raise ValueError("mutant transaction V3 witness does not bind mutant bytes")
  if mutant_ins!=ins_raw:raise ValueError("raw input snapshots changed from R18")
  case={"schema_version":"f05-2a-proof-domain-one-guard-mutant-r1","status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit","case_id":CID,"decision":"R4.1 proof-domain B","source_attempt":"R18","source_attempt_sha256":R18_RUN_SHA,"source_independent_review":"docs/remediation/m3_f05_2a_proof_other_seed_negative_review_r1_20261005/INDEPENDENT-REVIEW.md","source_independent_review_sha256":R18_REVIEW_SHA,"original_case_id_preserved":True,"assertion":"sign_same_tuple_with_alternate_seed","scope":"synthetic alternate applied policy only; no original-policy, full-ledger-admission, Pre-Prod, or live-network credit","execution":"NOT RUN; no simulator invocation in builder","entrypoint":"f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]","normal_rebuild":{"policy_id":normal["policy_id"].hex(),"script_sha256":sha(normal["code"]),"matches_R18_policy_and_code":True},"mutant":{"guard":"only authority_genesis_pop_preimage seed argument changes from genesis_ref to alternate ad...ad#7","policy_id":policy["policy_id"].hex(),"script_sha256":sha(policy["code"]),"state_validator_hash":policy["state_credential"].hex(),"source_change_count":1,"ed25519_verification_retained":True,"key_count_order_and_state_guards_retained":True},"preserved_R18_inputs":{"applied_policy_id":manifest["applied_policy"]["policy_id"],"parameter_cbor_sha256":manifest["applied_parameters"]["parameter_cbor_sha256"],"public_keys_hex":manifest["applied_parameters"]["committee_public_keys_hex"],"poP_signatures_hex":[p.hex() for p in proofs],"proof_message_sha256":sha(msg_raw),"exact_R18_negative_message_bytes_retained":True,"exact_R18_negative_pop_bytes_retained":True},"mutant_control":{"status":"PENDING","transaction_sha256":sha(mutant_tx),"raw_inputs_sha256":sha(mutant_ins),"raw_outputs_sha256":sha(mutant_outs),"policy_id":policy["policy_id"].hex(),"compiled_script_sha256":sha(policy["code"]),"mint_applied_v3_witness_identity_verified":True,"validation":validation},"funding_and_conservation":{"inputs_lovelace":17000000,"authority_output_lovelace":10000000,"change_output_lovelace":6000000,"fee_lovelace":1000000,"collateral":{"present":False,"lovelace":0},"validation":validation,"no_private_key_material_persisted":True},"credit":{"case_negative":None,"mutation_suite":None,"original_policy":False,"ledger_admission":False,"live_network":False},"artifacts":hashes}
  (out/"FIXTURE-MANIFEST.json").write_text(json.dumps(case,indent=2,sort_keys=True)+"\n")
  (out/"SHA256SUMS").write_text(sums(out))
  fm={"schema_version":"f05-2a-proof-domain-mutant-family-r1","status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit","case_ids_in_scope":[CID],"case_package":str(out.relative_to(ROOT)),"source_R18_sha256":R18_RUN_SHA,"source_R18_review_sha256":R18_REVIEW_SHA,"scope":case["scope"],"no_source_registry_status_or_handoff_changes":True}
  (OUT/"FAMILY-MANIFEST.json").write_text(json.dumps(fm,indent=2,sort_keys=True)+"\n")
  (OUT/"SHA256SUMS").write_text(sums(OUT))
  return case
def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--aiken",type=Path,required=True);a=p.parse_args();binary=a.aiken.resolve(strict=True)
 v=subprocess.run([str(binary),"--version"],capture_output=True,text=True,timeout=20)
 if v.returncode or v.stdout.strip()!="aiken v1.1.21+42babe5" or sha(binary.read_bytes())!=AIKEN_SHA:raise SystemExit("refusing non-pinned Aiken")
 print(json.dumps({"case_id":CID,"status":build(binary)["status"],"artifact_dir":str(OUT/CID)},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
