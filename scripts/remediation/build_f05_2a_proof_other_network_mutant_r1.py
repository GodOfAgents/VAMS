#!/usr/bin/env python3
"""Build an unexecuted one-guard network-magic mutant candidate."""
from __future__ import annotations
import difflib, hashlib, importlib.util, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CID="r2_signature_for_other_network"
R21=ROOT/"docs/remediation/m3_f05_2a_proof_other_network_negative_attempt_r1_20261005/RUN.json"
SOURCE=ROOT/"cardano/lib/vams/f05_authority.ak"
R2=ROOT/"docs/remediation/m3_f05_2a_proof_domain_family_r2_20261005"/CID
BASE=ROOT/"docs/remediation/m3_f05_2a/tx_sim_r1"
OUT=ROOT/"docs/remediation/m3_f05_2a_proof_other_network_mutant_r1_20261005"
AIKEN_SHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
R21_TX_SHA="2627b7ca1d85a06adac1e957eb186f3e5fd8e69a8f0fdd7b9d81b6753c7a3065"
R21_MSG_SHA="87b2d24f30ca078e33b98f6d34616d91be975e32643655f7a34466afd0731c7f"
R21_POLICY="13a2712cbc7b1c6f7cf48f7c3decd50b9c13e7837bd4cfc8865f496a"
R21_SCRIPT_SHA="bd3bbef9e5ce973e4c20ec1f4c898730a3ec9ba4503c1d6d196f02e71b4ab9c1"
OLD="bytearray.from_int_big_endian(1, 4)"
NEW="bytearray.from_int_big_endian(0, 4)"
STATE=bytes.fromhex("b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66")
def sha(b): return hashlib.sha256(b).hexdigest()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 if spec is None or spec.loader is None: raise RuntimeError("cannot load local fixture helper")
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
def sums(directory,recursive=False):
 files=sorted(directory.rglob("*") if recursive else directory.iterdir())
 return "".join(f"{sha(p.read_bytes())}  {p.relative_to(directory).as_posix()}\n" for p in files if p.is_file() and p.relative_to(directory).as_posix()!="SHA256SUMS")
def build(aiken):
 fam=load("f05_network_mutant_family",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
 h,cb=fam.h,fam.cb
 if OUT.exists(): raise FileExistsError("preserve existing mutant evidence package")
 run=json.loads(R21.read_text())
 attempt=run["attempt"]["runner_result"]; identity=run["fixture"]
 if run["case_id"]!=CID or identity["transaction_sha256"]!=R21_TX_SHA or identity["proof_message_sha256"]!=R21_MSG_SHA:
  raise ValueError("R21 case, transaction, or proof-message identity mismatch")
 if attempt["submitted_sha256"]["transaction"]!=R21_TX_SHA or attempt["submitted_sha256"]["raw_inputs"]!="5e935c48cc9d4e82e6dbedce94b2fbd3fb427f5e187bbe67ed376671ba5e4fec" or attempt["submitted_sha256"]["raw_outputs"]!="14f8b6399c77d55fa3cf016a48b1ff47d97efa293d5e043b7d699f66d847e6c0":
  raise ValueError("R21 runner-submitted byte identities mismatch")
 files={name:(R2/name).read_bytes() for name in ("negative.tx.cbor","negative.raw_inputs.cbor","negative.raw_outputs.cbor","negative.proof-message.bin","negative.applied-policy.cbor","negative.genesis_ref.cbor","negative.initial_keys.cbor")}
 if sha(files["negative.tx.cbor"])!=R21_TX_SHA or sha(files["negative.proof-message.bin"])!=R21_MSG_SHA or sha(files["negative.applied-policy.cbor"])!=R21_SCRIPT_SHA:
  raise ValueError("R2 artifacts do not match the exact R21 transaction/message/script")
 if sha(files["negative.raw_inputs.cbor"])!=attempt["submitted_sha256"]["raw_inputs"] or sha(files["negative.raw_outputs.cbor"])!=attempt["submitted_sha256"]["raw_outputs"]:
  raise ValueError("R21 raw-input/output identity mismatch")
 oldsource=SOURCE.read_text(encoding="utf-8")
 if oldsource.count(OLD)!=1: raise ValueError("network magic source literal is not unique")
 newsource=oldsource.replace(OLD,NEW,1)
 if newsource==oldsource or newsource.count(NEW)!=1: raise ValueError("network magic mutation failed exact-one guard")
 r2manifest=json.loads((R2/"FIXTURE-MANIFEST.json").read_text())
 applied=r2manifest["applied_parameters"]
 seed=(bytes.fromhex(applied["seed_ref"]["tx_hash"]),applied["seed_ref"]["output_index"])
 keys=[bytes.fromhex(x) for x in applied["committee_public_keys_hex"]]
 params={"genesis_ref":h._output_reference(*seed),"initial_keys":h.list_data([h.byte_string(k) for k in keys])}
 if h.cbor(params["genesis_ref"])!=files["negative.genesis_ref.cbor"] or h.cbor(params["initial_keys"])!=files["negative.initial_keys.cbor"]:
  raise ValueError("R21 applied parameters do not reproduce exactly from public values")
 if applied["parameter_cbor_sha256"]!="f679803627e6ea1abcb7649b10c6bbd6e0827e080f32c8814663510547711cae":
  raise ValueError("R21 parameter identity mismatch")
 rawtx=cb.roundtrip(files["negative.tx.cbor"])
 redpair=cb.map_get(cb.map_get(rawtx[1],5),[1,0])
 if not isinstance(redpair,list) or len(redpair)!=2 or not isinstance(redpair[0],cb.Tag) or redpair[0].number!=121:
  raise ValueError("R21 direct Plutus redeemer/ex-unit pair missing")
 proofs=redpair[0].value[0]
 if len(proofs)!=5 or [p.hex() for p in proofs]!=r2manifest["negative"]["validation"]["mint0_redeemer"]["proof_signatures_hex"]:
  raise ValueError("R21 negative PoP signature bytes mismatch")
 message=files["negative.proof-message.bin"]
 if len(message)!=279 or sha(message)!=R21_MSG_SHA or message[43:47]!=(0).to_bytes(4,"big"):
  raise ValueError("R21 proof-message bytes are not exact magic-0 message")
 if h._canonical_pop_message(*seed,STATE,keys,network_magic=0)!=message:
  raise ValueError("R21 message does not bind the recorded public parameters")
 with tempfile.TemporaryDirectory(prefix="f05-network-guard-mutant-") as td:
  temp=Path(td);staged=temp/"mutant-source";shutil.copytree(ROOT/"cardano",staged)
  staged_source=staged/"lib/vams/f05_authority.ak"
  staged_before=staged_source.read_text(encoding="utf-8")
  if staged_before!=oldsource: raise ValueError("temporary compile source differs from current canonical source")
  staged_source.write_text(newsource,encoding="utf-8")
  diff="".join(difflib.unified_diff(oldsource.splitlines(True),newsource.splitlines(True),fromfile="a/cardano/lib/vams/f05_authority.ak",tofile="b/cardano/lib/vams/f05_authority.ak"))
  policy_raw=h._compile(staged,aiken,temp/"compiled",params)
  mutant={"code":policy_raw["code"],"policy_id":policy_raw["policy_id"],"state_credential":policy_raw["state_credential"]}
  if mutant["state_credential"]!=STATE: raise ValueError("one-guard mutation changed state validator identity")
  if mutant["code"]==files["negative.applied-policy.cbor"]: raise ValueError("mutant compiled bytes equal normative R21 policy")
  if hashlib.blake2b(b"\x03"+mutant["code"],digest_size=28).digest()!=mutant["policy_id"]:
   raise ValueError("mutant policy ID does not derive from compiled script bytes")
  baselines={name:(BASE/name).read_bytes() for name in ("valid.tx.cbor","raw_inputs.cbor","raw_outputs.cbor")}
  expected={"valid.tx.cbor":"765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28",
    "raw_inputs.cbor":"4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
    "raw_outputs.cbor":"9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a"}
  if {n:sha(b) for n,b in baselines.items()}!=expected: raise ValueError("frozen source transaction identity changed")
  rebuilt=fam.build_tx(baselines["valid.tx.cbor"],baselines["raw_inputs.cbor"],baselines["raw_outputs.cbor"],mutant,seed,keys,proofs,True)
  mutant_tx,mutant_inputs,mutant_outputs,validation=rebuilt
  final=cb.roundtrip(mutant_tx);body,wit=final[0],final[1]
  mint=cb.map_get(body,9);scripts=cb.map_get(wit,7)
  if [pid for pid,_ in mint.pairs]!=[mutant["policy_id"]]: raise ValueError("mint map does not bind mutant policy")
  if not isinstance(scripts,cb.Tag) or scripts.number!=258 or scripts.value!=[mutant["code"]]:
   raise ValueError("Plutus V3 witness does not bind mutant bytes")
  changed=list(difflib.unified_diff(oldsource.splitlines(True),newsource.splitlines(True)))
  if len([line for line in changed if line.startswith("+") and not line.startswith("++")])!=1 or len([line for line in changed if line.startswith("-") and not line.startswith("---")])!=1:
   raise ValueError("source diff is not one exact line replacement")
  out=OUT/CID;out.mkdir(parents=True)
  artifacts={"r21-negative.tx.cbor":files["negative.tx.cbor"],"r21-negative.raw_inputs.cbor":files["negative.raw_inputs.cbor"],
   "r21-negative.raw_outputs.cbor":files["negative.raw_outputs.cbor"],"r21-negative.applied-policy.cbor":files["negative.applied-policy.cbor"],
   "r21-negative.proof-message.bin":message,"r21-negative.genesis_ref.cbor":files["negative.genesis_ref.cbor"],
   "r21-negative.initial_keys.cbor":files["negative.initial_keys.cbor"],
   "mutant.tx.cbor":mutant_tx,"mutant.raw_inputs.cbor":mutant_inputs,"mutant.raw_outputs.cbor":mutant_outputs,
   "mutant.applied-policy.cbor":mutant["code"],"mutant.proof-message.bin":message,
   "mutant.genesis_ref.cbor":files["negative.genesis_ref.cbor"],"mutant.initial_keys.cbor":files["negative.initial_keys.cbor"],
   "SOURCE-MUTATION.patch":diff.encode()}
  hashes={}
  for name,data in artifacts.items():(out/name).write_bytes(data);hashes[name]={"sha256":sha(data),"bytes":len(data)}
  import re
  lineno=next(i for i,line in enumerate(oldsource.splitlines(),1) if OLD in line)
  pyversion=subprocess.run([sys.executable,"--version"],capture_output=True,text=True,check=True).stdout.strip()
  openssl=subprocess.run(["openssl","version"],capture_output=True,text=True,check=True).stdout.strip()
  case={"schema_version":"f05-2a-proof-domain-network-magic-mutant-r1","status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit",
   "case_id":CID,"decision":"R4.1 proof-domain B","original_case_id_preserved":True,"original_assertion":"sign_tuple_with_another_network_magic",
   "scope":"synthetic one-guard alternate applied-policy candidate only; no original-policy, full-ledger-admission, Pre-Prod, or live-network credit",
   "execution":"NOT RUN; builder and structural tests do not invoke simulator","entrypoint":"f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]",
   "source_mutation":{"file":"cardano/lib/vams/f05_authority.ak","function":"authority_genesis_pop_preimage","line":lineno,
    "guard":"expected network_magic in bootstrap PoP preimage","before":OLD,"after":NEW,"replacement_count":1,
    "old_source_sha256":sha(oldsource.encode()),"mutant_source_sha256":sha(newsource.encode()),"patch_artifact":"SOURCE-MUTATION.patch",
    "all_other_guards_and_ed25519_verification_retained":True,"state_validator_identity_retained":mutant["state_credential"].hex()},
   "R21_basis":{"run_record":"docs/remediation/m3_f05_2a_proof_other_network_negative_attempt_r1_20261005/RUN.json",
    "run_record_sha256":sha(R21.read_bytes()),"original_policy_id":R21_POLICY,"original_script_sha256":R21_SCRIPT_SHA,
    "exact_original_negative_transaction_sha256":R21_TX_SHA,"exact_proof_message_sha256":R21_MSG_SHA,
    "exact_proof_message_bytes_reused":True,"exact_proof_signatures_reused":True,
    "runner_credit":"negative remains PENDING; prior simulator result has no named-condition credit"},
   "toolchain":{"aiken_version":"aiken v1.1.21+42babe5","aiken_binary_sha256":AIKEN_SHA,"python_version":pyversion,"openssl_version":openssl},
   "applied_parameters":{"seed_ref":{"tx_hash":seed[0].hex(),"output_index":seed[1]},
    "committee_public_keys_hex":[k.hex() for k in keys],"parameter_cbor_sha256":applied["parameter_cbor_sha256"],
    "network_tuple":{"chain_code":2,"chain_id":0,"network_magic":1,"address_network_id":0},"private_key_material_persisted":False},
   "mutant_policy":{"policy_id":mutant["policy_id"].hex(),"compiled_script_sha256":sha(mutant["code"]),
    "state_validator_hash":mutant["state_credential"].hex(),"mint_applied_v3_witness_identity_verified":True},
   "mutant_control":{"status":"PENDING","transaction_sha256":sha(mutant_tx),"raw_inputs_sha256":sha(mutant_inputs),
    "raw_outputs_sha256":sha(mutant_outputs),"same_R21_proof_message_sha256":sha(message),
    "same_R21_proof_signatures_hex":[p.hex() for p in proofs],"only_fixture_semantic_change_is_policy_rebinding_and_rebound_state":True,
    "validation":validation,"named_condition_attribution":"await independent exact-byte review; simulator execution not performed"},
   "funding_and_conservation":{"inputs_lovelace":17000000,"outputs_lovelace":16000000,"fee_lovelace":1000000,
    "value_equation":"17000000 = 16000000 + 1000000","collateral_present":False,"ada_conservation":True,
    "native_asset_conservation":True,"funding_signatures_body_bound":True,"funding_private_keys_ephemeral":True},
   "credit":{"negative_case":None,"mutation_suite":None,"original_policy":False,"ledger_admission":False,"live_network":False},"artifacts":hashes}
  (out/"FIXTURE-MANIFEST.json").write_text(json.dumps(case,indent=2,sort_keys=True)+"\n")
  (out/"SHA256SUMS").write_text(sums(out))
  (OUT/"SUMMARY.md").write_text("""# F05.2a network-magic one-guard mutant candidate r1

Status: **candidate; independent byte review required; tx-sim not run; no credit**.

This package preserves case r2_signature_for_other_network and the reviewed R21 negative proof-message and five proof signatures. A disposable source copy changes only the expected four-byte network_magic constant in authority_genesis_pop_preimage from 1 to 0. The validator source in the canonical checkout is unchanged. The mutant is recompiled and its new policy ID, mint entry, and Plutus V3 witness are rebound into a synthetic transaction; funding keys are ephemeral, and their signatures bind the final transaction body.

All five message-bound proof signatures are the exact R21 negative signatures. This candidate is pending independent review. It has not been executed. It grants no original-policy, full-ledger-admission, Pre-Prod, or live-network credit; F05/M3 remains open and deployment and gated activations remain disabled.
""")
  fm={"schema_version":"f05-2a-proof-domain-mutant-family-r1","status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit",
   "case_ids_in_scope":[CID],"case_package":str(out.relative_to(ROOT)),"R21_run_sha256":sha(R21.read_bytes()),
   "source_mutation":{"file":"cardano/lib/vams/f05_authority.ak","line":lineno,"replacement_count":1},
   "scope":case["scope"],"no_source_registry_status_or_handoff_changes":True,"files":{}}
  for p in sorted(OUT.rglob("*")):
   if p.is_file() and p.relative_to(OUT).as_posix() not in {"FAMILY-MANIFEST.json","SHA256SUMS"}:
    raw=p.read_bytes();fm["files"][p.relative_to(OUT).as_posix()]={"sha256":sha(raw),"bytes":len(raw)}
  (OUT/"FAMILY-MANIFEST.json").write_text(json.dumps(fm,indent=2,sort_keys=True)+"\n")
  (OUT/"SHA256SUMS").write_text(sums(OUT,recursive=True))
  return case
def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--aiken",type=Path,required=True);a=p.parse_args()
 binary=a.aiken.resolve(strict=True)
 version=subprocess.run([str(binary),"--version"],capture_output=True,text=True,timeout=20)
 if version.returncode or version.stdout.strip()!="aiken v1.1.21+42babe5" or sha(binary.read_bytes())!=AIKEN_SHA: raise SystemExit("refusing non-pinned Aiken")
 result=build(binary)
 print(json.dumps({"case_id":CID,"status":result["status"],"mutant_policy_id":result["mutant_policy"]["policy_id"],
  "mutant_tx_sha256":result["mutant_control"]["transaction_sha256"],"artifact_dir":str(OUT/CID)},sort_keys=True))
 return 0
if __name__=="__main__": raise SystemExit(main())

