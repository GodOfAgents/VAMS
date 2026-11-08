#!/usr/bin/env python3
"""Build proof-domain validator-hash controls; never invokes tx-sim."""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CID="r2_signature_for_other_validator_hash"
OUT=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_r1_20261005"
R41=ROOT/"docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json"
REG=ROOT/"docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
BASE=ROOT/"docs/remediation/m3_f05_2a/tx_sim_r1"
AIKEN_SHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
STATE=bytes.fromhex("b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66")
ALT_HASH=bytes.fromhex("cd"*28)
SEED=(bytes.fromhex("ab"*32),7)
ORIGINAL="9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
PINS={"valid.tx.cbor":"765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28",
 "raw_inputs.cbor":"4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
 "raw_outputs.cbor":"9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a"}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 if spec is None or spec.loader is None:raise RuntimeError("cannot load shared local builder")
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
def sums(directory,recursive=False):
 files=sorted(directory.rglob("*") if recursive else directory.iterdir())
 return "".join(f"{sha(p.read_bytes())}  {p.relative_to(directory).as_posix()}\n"
  for p in files if p.is_file() and p.relative_to(directory).as_posix()!="SHA256SUMS")
def build(aiken):
 fam=load("f05_other_validator_hash_family",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
 h,cb=fam.h,fam.cb
 if OUT.exists():raise FileExistsError("preserve existing evidence package")
 contract=json.loads(R41.read_text());registry=json.loads(REG.read_text())
 decision=contract["owner_decisions"]["proof_domain"]
 if decision["choice"]!="B" or CID not in decision["case_ids"]:raise ValueError("R4.1 proof-domain B decision missing")
 row=next((x for x in contract["case_overrides"] if x.get("id")==CID),None)
 if row is None:raise ValueError("exact R4.1 case contract missing")
 amended=row.get("amended_contract",{})
 if amended.get("changed_condition")!="ephemeral committee signs validator hash cd repeated 28 bytes; test policy uses derived hash":
  raise ValueError("R4.1 alternate validator-hash condition changed")
 assertion=next((x for x in registry["negative_cases"] if x["id"]==CID),None)
 if assertion!={"id":CID,"mutation":"sign_tuple_with_another_state_validator_hash"}:
  raise ValueError("original registry assertion changed")
 baselines={n:(BASE/n).read_bytes() for n in PINS}
 if {n:sha(b) for n,b in baselines.items()}!=PINS:raise ValueError("frozen source CBOR identity mismatch")
 for n,b in baselines.items():
  if cb.dumps(cb.roundtrip(b))!=b:raise ValueError(f"noncanonical frozen {n}")
 signers=h._ephemeral_committee()
 try:
  keys=[s.public_key for s in signers]
  params={"genesis_ref":h._output_reference(*SEED),"initial_keys":h.list_data([h.byte_string(k) for k in keys])}
  with tempfile.TemporaryDirectory(prefix="f05-other-validator-hash-") as td:
   policy=fam.compile_policy(aiken,params,Path(td)/"policy")
   if policy["state_credential"]!=STATE:raise ValueError("derived applied validator hash differs from pinned expected hash")
   actual_hash=policy["state_credential"]
   if actual_hash==ALT_HASH:raise ValueError("alternate validator hash unexpectedly equals applied hash")
   positive_message=h._canonical_pop_message(*SEED,actual_hash,keys)
   negative_message=h._canonical_pop_message(*SEED,ALT_HASH,keys)
   if len(positive_message)!=279 or len(negative_message)!=279:raise ValueError("proof message must be 279 bytes")
   differing=[i for i,(x,y) in enumerate(zip(positive_message,negative_message)) if x!=y]
   if differing!=list(range(82,110)):raise ValueError("messages differ outside state-validator-hash field")
   proof_signers=h._signers_for_keys(keys,signers)
   positive_proofs=[s.sign(positive_message) for s in proof_signers]
   negative_proofs=[s.sign(negative_message) for s in proof_signers]
   source=(baselines["valid.tx.cbor"],baselines["raw_inputs.cbor"],baselines["raw_outputs.cbor"])
   positive=fam.build_tx(*source,policy,SEED,keys,positive_proofs,True)
   # Both transactions share exactly the same body, resolved input/output data,
   # and body-bound funding witness set; only Mint[0] proof data changes.
   tx=cb.roundtrip(positive[0]);redeemers=cb.map_get(tx[1],5);entry=cb.map_get(redeemers,[1,0])
   if not isinstance(entry,list) or len(entry)!=2:raise ValueError("Mint[0] redeemer/ex-units pair missing")
   cb.map_set(redeemers,[1,0],[cb.Tag(121,[[p for p in negative_proofs]]),entry[1]])
   negative_raw=cb.dumps(tx)
   negative_meta=dict(positive[3])
   negative_meta["mint0_redeemer"]={"constructor_tag":121,"proof_count":5,
    "proof_signatures_hex":[p.hex() for p in negative_proofs],"cbor_sha256":sha(cb.dumps(cb.Tag(121,[[p for p in negative_proofs]])))}
   negative=(negative_raw,positive[1],positive[2],negative_meta)
   ptx=cb.roundtrip(positive[0]);ntx=cb.roundtrip(negative[0])
   if ptx[0]!=ntx[0] or positive[1]!=negative[1] or positive[2]!=negative[2]:
    raise ValueError("positive and negative contexts/body differ")
   pfund=cb.map_get(ptx[1],0);nfund=cb.map_get(ntx[1],0)
   if cb.dumps(pfund)!=cb.dumps(nfund):raise ValueError("funding witness sets differ")
   out=OUT/CID;out.mkdir(parents=True)
   labels=(("positive-control",positive,positive_message),("negative",negative,negative_message))
   artifacts={}
   for label,fixture,message in labels:
    txraw,rin,rout,validation=fixture
    payload={f"{label}.tx.cbor":txraw,f"{label}.raw_inputs.cbor":rin,f"{label}.raw_outputs.cbor":rout,
     f"{label}.applied-policy.cbor":policy["code"],f"{label}.genesis_ref.cbor":h.cbor(params["genesis_ref"]),
     f"{label}.initial_keys.cbor":h.cbor(params["initial_keys"]),f"{label}.proof-message.bin":message}
    for name,data in payload.items():
     (out/name).write_bytes(data);artifacts[name]={"sha256":sha(data),"bytes":len(data)}
    artifacts[label+".validation"]=validation
   posdiff=[i for i,(x,y) in enumerate(zip(positive_message,negative_message)) if x!=y]
   manifest={"schema_version":"f05-2a-proof-domain-validator-hash-r1",
    "status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit",
    "decision":"R4.1 proof-domain B","case_id":CID,"original_assertion":assertion,"original_case_id_preserved":True,
    "contract_row":row,"preserved_security_assertion":row["preserved_security_assertion"],
    "scope":"synthetic test-only alternate applied policy; no original-policy, full-ledger-admission, Pre-Prod, or live-network credit",
    "execution":"NOT RUN; candidate fixtures await independent exact-byte review",
    "entrypoint":"f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]",
    "toolchain":{"aiken_version":"aiken v1.1.21+42babe5","aiken_binary_sha256":AIKEN_SHA,
     "python_version":subprocess.run([sys.executable,"--version"],capture_output=True,text=True,check=True).stdout.strip()},
    "applied_parameters":{"seed_ref":{"tx_hash":SEED[0].hex(),"output_index":SEED[1]},
     "committee_public_keys_hex":[k.hex() for k in keys],
     "parameter_cbor_sha256":sha(h.cbor(params["genesis_ref"])+h.cbor(params["initial_keys"])),
     "derived_applied_state_validator_hash":actual_hash.hex(),"alternate_signed_state_validator_hash":ALT_HASH.hex(),
     "private_key_material_persisted":False},
    "applied_policy":{"policy_id":policy["policy_id"].hex(),"compiled_script_sha256":sha(policy["code"]),
     "state_validator_hash":actual_hash.hex()},
    "positive_control":{"status":"PENDING","signed_validator_hash":actual_hash.hex(),
     "proof_message_sha256":sha(positive_message),"applied_policy_id":policy["policy_id"].hex(),
     "compiled_script_sha256":sha(policy["code"]),"mint_applied_v3_witness_identity_verified":True,
     "transaction_sha256":sha(positive[0]),"raw_inputs_sha256":sha(positive[1]),"raw_outputs_sha256":sha(positive[2]),
     "validation":positive[3]},
    "negative":{"status":"PENDING","changed_condition":"committee signs the same tuple with alternate state-validator hash cd repeated 28 bytes",
     "signed_validator_hash":ALT_HASH.hex(),"applied_validator_hash_retained":actual_hash.hex(),
     "proof_message_sha256":sha(negative_message),"applied_policy_id":policy["policy_id"].hex(),
     "compiled_script_sha256":sha(policy["code"]),"mint_applied_v3_witness_identity_verified":True,
     "transaction_sha256":sha(negative[0]),"raw_inputs_sha256":sha(negative[1]),"raw_outputs_sha256":sha(negative[2]),
     "validation":negative[3],"named_condition_attribution":"pending; no simulator or first-failure evidence inferred"},
    "proof_message_relation":{"bytes":279,"state_validator_hash_offset":82,"field_width":28,
     "positive_value_hex":positive_message[82:110].hex(),"negative_value_hex":negative_message[82:110].hex(),
     "differing_offsets":posdiff,"all_other_bytes_identical":len(posdiff)==28},
    "shared_transaction_context":{"body_identical":True,"raw_inputs_identical":True,"raw_outputs_identical":True,
     "funding_witnesses_byte_identical":True,"only_witness_change":"Mint[0] proof list"},
    "funding_and_conservation":{"inputs_lovelace":17000000,"authority_output_lovelace":10000000,
     "change_output_lovelace":6000000,"fee_lovelace":1000000,"collateral":{"present":False,"lovelace":0},
     "value_equation":"17000000 = 10000000 + 6000000 + 1000000",
     "native_asset_equation":"exactly one authority NFT under this applied policy is minted and preserved in authority output"},
    "credit":{"negative_case":None,"original_policy":False,"ledger_admission":False,"live_network":False},
    "artifacts":artifacts}
   (out/"FIXTURE-MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
   (out/"SHA256SUMS").write_text(sums(out))
   (OUT/"SUMMARY.md").write_text("""# F05.2a other-validator-hash proof-domain candidate r1

Status: **candidate; independent byte review required; tx-sim not run; no credit**.

The original case ID and assertion are preserved. Positive proofs bind the derived applied state-validator hash; negative proofs bind the R4.1 alternate hash cd repeated 28 bytes. All remaining message bytes, applied parameters, datum, body, inputs, outputs, policy, and funding witness set are identical. Only the Mint[0] proof list changes between the two fixtures.

Funding and committee signing keys are ephemeral; no private key material is persisted. The fixtures are synthetic alternate-applied-policy evidence only. They grant no original-policy, full-ledger-admission, Pre-Prod, or live-network credit. F05/M3 remains open; independent exact-byte review is required before any simulator execution.
""")
   fm={"schema_version":"f05-2a-proof-domain-validator-hash-family-r1",
    "status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit","decision":"R4.1 proof-domain B",
    "case_ids_in_scope":[CID],"case_package":str(out.relative_to(ROOT)),
    "R4_1_sha256":sha(R41.read_bytes()),"registry_sha256":sha(REG.read_bytes()),
    "source_sha256":{"cardano/lib/vams/f05_authority.ak":sha((ROOT/"cardano/lib/vams/f05_authority.ak").read_bytes()),
     "cardano/validators/f05_authority_policy.ak":sha((ROOT/"cardano/validators/f05_authority_policy.ak").read_bytes())},
    "no_source_registry_status_or_handoff_changed":True,"scope":manifest["scope"],"files":{}}
   for p in sorted(OUT.rglob("*")):
    if p.is_file() and p.relative_to(OUT).as_posix() not in {"FAMILY-MANIFEST.json","SHA256SUMS"}:
     raw=p.read_bytes();fm["files"][p.relative_to(OUT).as_posix()]={"sha256":sha(raw),"bytes":len(raw)}
   (OUT/"FAMILY-MANIFEST.json").write_text(json.dumps(fm,indent=2,sort_keys=True)+"\n")
   (OUT/"SHA256SUMS").write_text(sums(OUT,recursive=True))
   return manifest
 finally:
  for signer in signers:signer.close()
def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--aiken",type=Path,required=True)
 a=p.parse_args();binary=a.aiken.resolve(strict=True)
 v=subprocess.run([str(binary),"--version"],capture_output=True,text=True,timeout=20)
 if v.returncode or v.stdout.strip()!="aiken v1.1.21+42babe5" or sha(binary.read_bytes())!=AIKEN_SHA:
  raise SystemExit("refusing non-pinned Aiken")
 result=build(binary)
 print(json.dumps({"case_id":CID,"status":result["status"],"applied_policy_id":result["applied_policy"]["policy_id"],
  "positive_tx_sha256":result["positive_control"]["transaction_sha256"],"negative_tx_sha256":result["negative"]["transaction_sha256"],
  "artifact_dir":str(OUT/CID)},sort_keys=True))
 return 0
if __name__=="__main__":raise SystemExit(main())

