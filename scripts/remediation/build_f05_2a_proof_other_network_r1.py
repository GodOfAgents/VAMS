#!/usr/bin/env python3
"""Build the R4.1 proof-domain network-magic positive/negative pair; never simulates."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
R41=ROOT/"docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json"
REG=ROOT/"docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
BASE=ROOT/"docs/remediation/m3_f05_2a/tx_sim_r1"
OUT=ROOT/"docs/remediation/m3_f05_2a_proof_domain_family_r2_20261005"
CID="r2_signature_for_other_network"
ORIGINAL="9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
PINS={"valid.tx.cbor":"765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28",
      "raw_inputs.cbor":"4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
      "raw_outputs.cbor":"9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a"}
AIKEN_SHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
STATE_HASH=bytes.fromhex("b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66")

def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()

def family():
 path=ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py"
 spec=importlib.util.spec_from_file_location("f05_network_family_shared",path)
 if spec is None or spec.loader is None:raise RuntimeError("cannot load shared applied-policy builder")
 mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
 return mod

def build(aiken:Path):
 fam=family();h,cb=fam.h,fam.cb
 contract=json.loads(R41.read_text());registry=json.loads(REG.read_text())
 decision=contract["owner_decisions"]["proof_domain"]
 if decision["choice"]!="B" or CID not in decision["case_ids"]:
  raise ValueError("R4.1 proof-domain B decision/case missing")
 assertion=next((c for c in registry["negative_cases"] if c["id"]==CID),None)
 if assertion is None or assertion.get("mutation")!="sign_tuple_with_another_network_magic":
  raise ValueError("original network-magic assertion changed/missing")
 if OUT.exists():raise FileExistsError("preserve existing proof-domain package")
 sources={name:(BASE/name).read_bytes() for name in PINS}
 if {name:sha(data) for name,data in sources.items()}!=PINS:raise ValueError("frozen baseline CBOR hash mismatch")
 for name,data in sources.items():
  if cb.dumps(cb.roundtrip(data))!=data:raise ValueError(f"baseline {name} is noncanonical")
 applied=(bytes.fromhex("ab"*32),7)
 signers=h._ephemeral_committee()
 try:
  keys=[signer.public_key for signer in signers]
  params={"genesis_ref":h._output_reference(*applied),"initial_keys":h.list_data([h.byte_string(key) for key in keys])}
  with tempfile.TemporaryDirectory(prefix="f05-proof-other-network-") as tmp:
   policy=fam.compile_policy(aiken,params,Path(tmp)/"policy")
   if policy["state_credential"]!=STATE_HASH:raise ValueError("state-validator hash mismatch")
   pid=policy["policy_id"].hex();program_hash=sha(policy["code"])
   positive_message=h._canonical_pop_message(*applied,policy["state_credential"],keys,network_magic=1)
   negative_message=h._canonical_pop_message(*applied,policy["state_credential"],keys,network_magic=0)
   if len(positive_message)!=279 or len(negative_message)!=279:raise ValueError("R2 proof messages must be 279 bytes")
   if positive_message[:43]!=negative_message[:43] or positive_message[47:]!=negative_message[47:]:
    raise ValueError("proof messages differ outside the network_magic field")
   if positive_message[43:47]!=(1).to_bytes(4,"big") or negative_message[43:47]!=(0).to_bytes(4,"big"):
    raise ValueError("proof messages do not bind expected network magic")
   positive_proofs=[s.sign(positive_message) for s in signers]
   negative_proofs=[s.sign(negative_message) for s in signers]
   args=[sources["valid.tx.cbor"],sources["raw_inputs.cbor"],sources["raw_outputs.cbor"]]
   positive=fam.build_tx(*args,policy,applied,keys,positive_proofs,True)
   # Clone the fully funded positive transaction, replacing only the proof
   # redeemer. This preserves identical inputs/outputs/body/funding witnesses.
   ntx=cb.roundtrip(positive[0]);redmap=cb.map_get(ntx[1],5)
   prior=cb.map_get(redmap,[1,0])
   if not isinstance(prior,list) or len(prior)!=2:raise ValueError("baseline Mint[0] redeemer pair missing")
   negative_redeemer=cb.Tag(121,[[proof for proof in negative_proofs]])
   cb.map_set(redmap,[1,0],[negative_redeemer,prior[1]])
   negative_raw=cb.dumps(ntx)
   negative_validation=dict(positive[3])
   negative_validation["mint0_redeemer"]={"constructor_tag":121,"proof_count":len(negative_proofs),
    "proof_signatures_hex":[proof.hex() for proof in negative_proofs],"cbor_sha256":sha(cb.dumps(negative_redeemer))}
   negative=(negative_raw,positive[1],positive[2],negative_validation)
   ptx=cb.roundtrip(positive[0]);ntx=cb.roundtrip(negative[0])
   if ptx[0]!=ntx[0] or positive[1]!=negative[1] or positive[2]!=negative[2]:
    raise ValueError("positive and negative differ outside the named proof witness")
   case=OUT/CID;case.mkdir(parents=True,exist_ok=False);artifacts={}
   for label,fixture,message in (("positive-control",positive,positive_message),("negative",negative,negative_message)):
    tx,raw_inputs,raw_outputs,validation=fixture
    files={f"{label}.tx.cbor":tx,f"{label}.raw_inputs.cbor":raw_inputs,
           f"{label}.raw_outputs.cbor":raw_outputs,f"{label}.applied-policy.cbor":policy["code"],
           f"{label}.genesis_ref.cbor":h.cbor(params["genesis_ref"]),
           f"{label}.initial_keys.cbor":h.cbor(params["initial_keys"]),
           f"{label}.proof-message.bin":message}
    for name,data in files.items():
     (case/name).write_bytes(data);artifacts[name]={"sha256":sha(data),"bytes":len(data)}
    artifacts[label+".validation"]=validation
   pyversion=subprocess.run([sys.executable,"--version"],capture_output=True,text=True,check=True).stdout.strip()
   openssl=subprocess.run(["openssl","version"],capture_output=True,text=True,check=True).stdout.strip()
   manifest={"schema_version":"f05-2a-proof-domain-case-r2",
    "status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit",
    "decision":"R4.1 proof-domain B","fixture_family":"proof_domain","case_id":CID,
    "original_case_id_preserved":True,"original_assertion":assertion,
    "preserved_security_assertion":{"verifier_property":"valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message)",
     "expected_result":"reject at compiled target Mint[0]","target_ref":"cardano/validators/f05_authority_policy.ak#f05_authority_policy.mint"},
    "scope":"synthetic test-only alternate applied policy; no original-policy, full-ledger-admission, Pre-Prod, or live-network credit",
    "execution":"not run; awaits independent byte review","generator_invocation":{"argv":list(sys.argv),"exit_code":0},
    "toolchain":{"aiken_version":"aiken v1.1.21+42babe5","aiken_binary_sha256":AIKEN_SHA,"python_version":pyversion,"openssl_version":openssl},
    "entrypoint":"f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]","original_policy_id":ORIGINAL,
    "applied_parameters":{"seed_ref":{"tx_hash":applied[0].hex(),"output_index":applied[1]},
     "committee_public_keys_hex":[key.hex() for key in keys],
     "network_tuple":{"chain_code":2,"chain_id":0,"network_magic":1,"address_network_id":0},
     "parameter_cbor_sha256":sha(h.cbor(params["genesis_ref"])+h.cbor(params["initial_keys"])),"private_key_material_persisted":False},
    "applied_policy":{"policy_id":pid,"compiled_script_sha256":program_hash,"state_validator_hash":policy["state_credential"].hex()},
    "positive_control":{"status":"PENDING","signed_network_magic":1,"proof_message_sha256":sha(positive_message),
     "applied_policy_id":pid,"compiled_script_sha256":program_hash,"mint_applied_v3_witness_identity_verified":True,
     "transaction_sha256":sha(positive[0]),"raw_inputs_sha256":sha(positive[1]),"raw_outputs_sha256":sha(positive[2]),"validation":positive[3]},
    "negative":{"status":"PENDING","changed_condition":"ephemeral committee signs the exact R2 tuple with network_magic 0; policy parameters, datum and transaction retain network_magic 1",
     "signed_network_magic":0,"applied_network_magic_retained":1,"proof_message_sha256":sha(negative_message),
     "applied_policy_id":pid,"compiled_script_sha256":program_hash,"mint_applied_v3_witness_identity_verified":True,
     "transaction_sha256":sha(negative[0]),"raw_inputs_sha256":sha(negative[1]),"raw_outputs_sha256":sha(negative[2]),
     "validation":negative[3],"named_condition_attribution":"pending simulator execution and independent compiled Mint[0] review; none inferred from construction"},
    "proof_message_relation":{"bytes":279,"network_magic_field_offset":43,"network_magic_field_width":4,
     "positive_value_hex":positive_message[43:47].hex(),"negative_value_hex":negative_message[43:47].hex(),
     "all_other_bytes_identical":positive_message[:43]==negative_message[:43] and positive_message[47:]==negative_message[47:]},
    "funding_and_conservation":{"inputs_lovelace":17000000,"authority_output_lovelace":10000000,
     "change_output_lovelace":6000000,"fee_lovelace":1000000,"collateral":{"present":False,"lovelace":0},
     "value_equation":"17000000 = 10000000 + 6000000 + 1000000",
     "native_asset_equation":"exactly one authority NFT under this applied policy is minted and preserved in the authority output"},
    "credit":{"negative_case":None,"original_policy":False,"ledger_admission":False,"live_network":False},"artifacts":artifacts}
   (case/"FIXTURE-MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
   (case/"SHA256SUMS").write_text("".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(case.iterdir()) if p.is_file() and p.name!="SHA256SUMS"))
   summary="""# F05.2a proof-domain other-network candidate pair r2

Status: **candidate bytes generated; independent byte review required; tx-sim not run; no case credit**.

This package preserves the original case ID r2_signature_for_other_network, its assertion sign_tuple_with_another_network_magic, and R4.1 proof-domain decision B. Both fixtures use the same test-only alternate applied policy, seed reference, ordered five-key committee, datum, body, and outputs. The positive proofs sign the exact R2 279-byte message with network magic 1. The negative proofs sign the same message with only the four-byte network-magic field changed to 0. Both transactions retain network magic 1 in their applied message domain and transaction semantics.

The package contains public parameter CBOR, exact positive/negative proof-message bytes, compiled applied policy, transaction CBOR, resolved inputs/outputs, and validation evidence. Policy ID, mint entry, and Plutus V3 script witness bind exactly. Five valid Ed25519 proofs bind each message; funding witnesses sign each final body. ADA conservation is 17,000,000 = 10,000,000 + 6,000,000 + 1,000,000, and exactly one authority NFT is minted and preserved. Private keys were generated ephemerally in process memory/anonymous memfds and were not persisted.

No tx-sim or applied-case suite ran. Both controls remain PENDING. This is synthetic alternate-applied-policy evidence only; it grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. The validator, registry, status, and handoff records were not changed. Independent exact-byte review is required before any simulator run.
"""
   (OUT/"SUMMARY.md").write_text(summary)
   family_manifest={"schema_version":"f05-2a-proof-domain-family-r2",
    "status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit",
    "decision":"R4.1 proof-domain B","case_ids_in_scope":[CID],
    "case_package":str(case.relative_to(ROOT)),
    "R4_1_sha256":sha(R41.read_bytes()),"registry_sha256":sha(REG.read_bytes()),
    "source_sha256":{"cardano/validators/f05_authority_policy.ak":sha((ROOT/"cardano/validators/f05_authority_policy.ak").read_bytes()),
     "cardano/lib/vams/f05_authority.ak":sha((ROOT/"cardano/lib/vams/f05_authority.ak").read_bytes())},
    "applied_policy_id":pid,"positive_tx_sha256":sha(positive[0]),"negative_tx_sha256":sha(negative[0]),
    "generator_invocation":{"argv":list(sys.argv),"exit_code":0},
    "next_cases_untouched":["r2_signature_for_other_validator_hash","r2_signature_for_other_epoch"],
    "no_shared_status_or_registry_changed":True,"scope":manifest["scope"],"files":{}}
   for item in sorted(OUT.rglob("*")):
    relative=item.relative_to(OUT).as_posix()
    if item.is_file() and relative not in {"FAMILY-MANIFEST.json","SHA256SUMS"}:
     data=item.read_bytes();family_manifest["files"][relative]={"sha256":sha(data),"bytes":len(data)}
   (OUT/"FAMILY-MANIFEST.json").write_text(json.dumps(family_manifest,indent=2,sort_keys=True)+"\n")
   (OUT/"SHA256SUMS").write_text("".join(f"{sha(item.read_bytes())}  {item.relative_to(OUT).as_posix()}\n" for item in sorted(OUT.rglob("*")) if item.is_file() and item.relative_to(OUT).as_posix()!="SHA256SUMS"))
   return manifest
 finally:
  for signer in signers:signer.close()

def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--aiken",type=Path,required=True)
 args=parser.parse_args();aiken=args.aiken.resolve(strict=True)
 version=subprocess.run([str(aiken),"--version"],capture_output=True,text=True,timeout=20)
 if version.returncode or version.stdout.strip()!="aiken v1.1.21+42babe5" or sha(aiken.read_bytes())!=AIKEN_SHA:
  raise SystemExit("refusing non-pinned Aiken 1.1.21")
 result=build(aiken)
 print(json.dumps({"case_id":CID,"status":result["status"],"applied_policy_id":result["applied_policy"]["policy_id"],
  "artifact_dir":str(OUT/CID)},sort_keys=True))
 return 0

if __name__=="__main__":raise SystemExit(main())

