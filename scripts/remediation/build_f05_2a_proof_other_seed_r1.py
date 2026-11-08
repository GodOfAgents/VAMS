#!/usr/bin/env python3
"""Build the R4.1 proof-domain wrong-seed fixture; never simulates."""
from __future__ import annotations
import hashlib, importlib.util, json, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
R41=ROOT/"docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json"
REG=ROOT/"docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
BASE=ROOT/"docs/remediation/m3_f05_2a/tx_sim_r1"
OUT=ROOT/"docs/remediation/m3_f05_2a_proof_domain_family_r1_20261005"
CID="r2_signature_for_other_seed"
ORIGINAL="9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
PINS={"valid.tx.cbor":"765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28","raw_inputs.cbor":"4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe","raw_outputs.cbor":"9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a"}
AIKEN_SHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
STATE_HASH=bytes.fromhex("b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66")
def sha(b): return hashlib.sha256(b).hexdigest()
def family():
 spec=importlib.util.spec_from_file_location("f05_applied_family_shared",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
 mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod
def build(aiken):
 fam=family();h,cb=fam.h,fam.cb
 contract=json.loads(R41.read_text());registry=json.loads(REG.read_text())
 if contract["owner_decisions"]["proof_domain"]["choice"]!="B" or CID not in contract["owner_decisions"]["proof_domain"]["case_ids"]:raise ValueError("R4.1 B decision/case missing")
 assertion=next((c for c in registry["negative_cases"] if c["id"]==CID),None)
 if assertion is None or assertion["mutation"]!="sign_same_tuple_with_alternate_seed":raise ValueError("original assertion changed/missing")
 if OUT.exists():raise FileExistsError("preserve existing package")
 source={n:(BASE/n).read_bytes() for n in PINS}
 if {n:sha(v) for n,v in source.items()}!=PINS:raise ValueError("baseline CBOR hash mismatch")
 for n,b in source.items():
  if cb.dumps(cb.roundtrip(b))!=b:raise ValueError(f"{n} is not canonical CBOR")
 applied=(bytes.fromhex("ab"*32),7);other=(bytes.fromhex("ad"*32),7)
 signers=h._ephemeral_committee();work=ROOT/".codex/scratch/proof-other-seed-build"
 try:
  keys=[x.public_key for x in signers]
  params={"genesis_ref":h._output_reference(*applied),"initial_keys":h.list_data([h.byte_string(k) for k in keys])}
  work.mkdir(parents=True,exist_ok=False)
  try:
   policy=fam.compile_policy(aiken,params,work)
   if policy["state_credential"]!=STATE_HASH:raise ValueError("state-validator hash mismatch")
   pid,psha=policy["policy_id"].hex(),sha(policy["code"])
   pmsg=h._canonical_pop_message(*applied,policy["state_credential"],keys)
   nmsg=h._canonical_pop_message(*other,policy["state_credential"],keys)
   pp=[s.sign(pmsg) for s in signers];np=[s.sign(nmsg) for s in signers]
   args=[source["valid.tx.cbor"],source["raw_inputs.cbor"],source["raw_outputs.cbor"]]
   positive=fam.build_tx(*args,policy,applied,keys,pp,True)
   negative=fam.build_tx(*args,policy,applied,keys,np,True)
   case=OUT/CID;case.mkdir(parents=True);refs={}
   for label,fixture,message in (("positive-control",positive,pmsg),("negative",negative,nmsg)):
    tx,ins,outs,validation=fixture
    for name,data in {f"{label}.tx.cbor":tx,f"{label}.raw_inputs.cbor":ins,f"{label}.raw_outputs.cbor":outs,f"{label}.applied-policy.cbor":policy["code"],f"{label}.genesis_ref.cbor":h.cbor(params["genesis_ref"]),f"{label}.initial_keys.cbor":h.cbor(params["initial_keys"]),f"{label}.proof-message.bin":message}.items():
     (case/name).write_bytes(data);refs[name]={"sha256":sha(data),"bytes":len(data)}
    refs[label+".validation"]=validation
   manifest={"schema_version":"f05-2a-proof-domain-case-r1","status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit","decision":"R4.1 proof-domain B","fixture_family":"proof_domain","case_id":CID,"original_case_id_preserved":True,"original_assertion":assertion,"preserved_security_assertion":{"verifier_property":"valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message)","expected_result":"reject at compiled target Mint[0]","target_ref":"cardano/validators/f05_authority_policy.ak#f05_authority_policy.mint"},"scope":"synthetic test-only alternate applied policy; no original-policy, full-ledger-admission, Pre-Prod, or live-network credit","execution":"not run; awaits independent byte review","toolchain":{"aiken_version":"aiken v1.1.21+42babe5","aiken_binary_sha256":AIKEN_SHA,"python_version":subprocess.run([sys.executable,"--version"],capture_output=True,text=True).stdout.strip()},"entrypoint":"f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]","original_policy_id":ORIGINAL,"applied_parameters":{"seed_ref":{"tx_hash":applied[0].hex(),"output_index":applied[1]},"committee_public_keys_hex":[k.hex() for k in keys],"parameter_cbor_sha256":sha(h.cbor(params["genesis_ref"])+h.cbor(params["initial_keys"])),"private_key_material_persisted":False},"applied_policy":{"policy_id":pid,"compiled_script_sha256":psha,"state_validator_hash":policy["state_credential"].hex()},"positive_control":{"status":"PENDING","signed_seed_ref":{"tx_hash":applied[0].hex(),"output_index":applied[1]},"proof_message_sha256":sha(pmsg),"applied_policy_id":pid,"compiled_script_sha256":psha,"mint_applied_v3_witness_identity_verified":True,"transaction_sha256":sha(positive[0]),"raw_inputs_sha256":sha(positive[1]),"raw_outputs_sha256":sha(positive[2]),"validation":positive[3]},"negative":{"status":"PENDING","changed_condition":"ephemeral committee signs the exact R2 tuple with alternate seed tx hash ad repeated 32 bytes; policy parameters, datum and transaction retain seed tx hash ab repeated 32 bytes","signed_seed_ref":{"tx_hash":other[0].hex(),"output_index":other[1]},"applied_seed_ref_retained":{"tx_hash":applied[0].hex(),"output_index":applied[1]},"proof_message_sha256":sha(nmsg),"applied_policy_id":pid,"compiled_script_sha256":psha,"mint_applied_v3_witness_identity_verified":True,"transaction_sha256":sha(negative[0]),"raw_inputs_sha256":sha(negative[1]),"raw_outputs_sha256":sha(negative[2]),"validation":negative[3],"named_condition_attribution":"pending simulator execution and independent compiled Mint[0] review; none inferred from construction"},"funding_and_conservation":{"inputs_lovelace":17000000,"authority_output_lovelace":10000000,"change_output_lovelace":6000000,"fee_lovelace":1000000,"collateral":{"present":False,"lovelace":0},"value_equation":"17000000 = 10000000 + 6000000 + 1000000","native_asset_equation":"exactly one authority NFT under this applied policy is minted and preserved in the authority output"},"credit":{"negative_case":None,"original_policy":False,"ledger_admission":False,"live_network":False},"artifacts":refs}
   (case/"FIXTURE-MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
   def sums(d):return "".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(d.iterdir()) if p.is_file() and p.name!="SHA256SUMS")
   (case/"SHA256SUMS").write_text(sums(case))
   fm={"schema_version":"f05-2a-proof-domain-family-r1","status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit","decision":"R4.1 proof-domain B","case_ids_in_scope":[CID],"next_cases_untouched":["r2_signature_for_other_network","r2_signature_for_other_validator_hash","r2_signature_for_other_epoch"],"case_package":str(case.relative_to(ROOT)),"R4_1_sha256":sha(R41.read_bytes()),"registry_sha256":sha(REG.read_bytes()),"no_shared_status_or_registry_changed":True,"scope":manifest["scope"]}
   (OUT/"FAMILY-MANIFEST.json").write_text(json.dumps(fm,indent=2,sort_keys=True)+"\n")
   (OUT/"SHA256SUMS").write_text(sums(OUT));return manifest
  finally:shutil.rmtree(work)
 finally:
  for s in signers:s.close()
def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--aiken",type=Path,required=True);a=p.parse_args();aiken=a.aiken.resolve(strict=True)
 v=subprocess.run([str(aiken),"--version"],capture_output=True,text=True,timeout=20)
 if v.returncode or v.stdout.strip()!="aiken v1.1.21+42babe5" or sha(aiken.read_bytes())!=AIKEN_SHA:raise SystemExit("refusing non-pinned Aiken 1.1.21")
 result=build(aiken);print(json.dumps({"case_id":CID,"status":result["status"],"artifact_dir":str(OUT/CID)},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
