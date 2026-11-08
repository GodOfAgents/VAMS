from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILDER_PATH=ROOT/"scripts/remediation/build_f05_2a_proof_other_network_r1.py"
PACKAGE=ROOT/"docs/remediation/m3_f05_2a_proof_domain_family_r2_20261005/r2_signature_for_other_network"
SPEC=importlib.util.spec_from_file_location("proof_network_test_builder",BUILDER_PATH)
builder=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=builder;SPEC.loader.exec_module(builder)
fam=builder.family();cb=fam.cb;h=fam.h

def verify(public:bytes,signature:bytes,message:bytes)->None:
 prefix=bytes.fromhex("302a300506032b6570032100");fds=[]
 try:
  for label,data in (("pub",prefix+public),("sig",signature),("msg",message)):
   fd=os.memfd_create("vams-proof-network-test-"+label,0);fds.append(fd)
   if os.write(fd,data)!=len(data):raise AssertionError("short anonymous-memfd write")
   os.lseek(fd,0,0)
  pubfd,sigfd,msgfd=fds
  result=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pubfd}",
   "-keyform","DER","-in",f"/proc/self/fd/{msgfd}","-sigfile",f"/proc/self/fd/{sigfd}"],
   stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=tuple(fds),check=False)
  assert result.returncode==0
 finally:
  for fd in fds:os.close(fd)

def test_original_case_decision_and_no_execution_are_preserved():
 manifest=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 contract=json.loads(builder.R41.read_text())
 registry=json.loads(builder.REG.read_text())
 original=next(row for row in registry["negative_cases"] if row["id"]==manifest["case_id"])
 assert contract["owner_decisions"]["proof_domain"]["choice"]=="B"
 assert "r2_signature_for_other_network" in contract["owner_decisions"]["proof_domain"]["case_ids"]
 assert manifest["case_id"]=="r2_signature_for_other_network"
 assert manifest["original_case_id_preserved"] is True
 assert manifest["original_assertion"]==original
 assert original["mutation"]=="sign_tuple_with_another_network_magic"
 assert manifest["positive_control"]["status"]=="PENDING"
 assert manifest["negative"]["status"]=="PENDING"
 assert manifest["credit"]=={"negative_case":None,"original_policy":False,"ledger_admission":False,"live_network":False}
 assert manifest["execution"].startswith("not run")
 assert "run_typed_tx_case(" not in BUILDER_PATH.read_text()
 assert "tx simulate" not in BUILDER_PATH.read_text()

def test_only_network_magic_changes_and_both_messages_match_current_r2_oracle():
 manifest=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 applied=manifest["applied_parameters"]["seed_ref"]
 seed=(bytes.fromhex(applied["tx_hash"]),applied["output_index"])
 keys=[bytes.fromhex(value) for value in manifest["applied_parameters"]["committee_public_keys_hex"]]
 assert len(keys)==5 and keys==sorted(keys) and len(set(keys))==5
 positive=(PACKAGE/"positive-control.proof-message.bin").read_bytes()
 negative=(PACKAGE/"negative.proof-message.bin").read_bytes()
 assert len(positive)==len(negative)==279
 assert positive==h._canonical_pop_message(*seed,bytes.fromhex(manifest["applied_policy"]["state_validator_hash"]),keys,network_magic=1)
 assert negative==h._canonical_pop_message(*seed,bytes.fromhex(manifest["applied_policy"]["state_validator_hash"]),keys,network_magic=0)
 offset=manifest["proof_message_relation"]["network_magic_field_offset"]
 assert offset==43 and manifest["proof_message_relation"]["network_magic_field_width"]==4
 assert positive[offset:offset+4]==(1).to_bytes(4,"big")
 assert negative[offset:offset+4]==(0).to_bytes(4,"big")
 assert positive[:offset]==negative[:offset]
 assert positive[offset+4:]==negative[offset+4:]
 assert manifest["proof_message_relation"]["all_other_bytes_identical"] is True

def test_pair_has_exact_policy_binding_valid_pops_funding_and_conservation():
 manifest=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 keys=[bytes.fromhex(value) for value in manifest["applied_parameters"]["committee_public_keys_hex"]]
 pid=bytes.fromhex(manifest["applied_policy"]["policy_id"])
 params=manifest["applied_parameters"]
 seed=h._output_reference(bytes.fromhex(params["seed_ref"]["tx_hash"]),params["seed_ref"]["output_index"])
 initial_keys=h.list_data([h.byte_string(key) for key in keys])
 assert h.cbor(seed)==(PACKAGE/"positive-control.genesis_ref.cbor").read_bytes()
 assert h.cbor(initial_keys)==(PACKAGE/"positive-control.initial_keys.cbor").read_bytes()
 txs=[]
 for label,magic in (("positive-control",1),("negative",0)):
  txraw=(PACKAGE/(label+".tx.cbor")).read_bytes()
  raw_inputs=(PACKAGE/(label+".raw_inputs.cbor")).read_bytes()
  raw_outputs=(PACKAGE/(label+".raw_outputs.cbor")).read_bytes()
  policy=(PACKAGE/(label+".applied-policy.cbor")).read_bytes()
  assert hashlib.sha256(policy).hexdigest()==manifest["applied_policy"]["compiled_script_sha256"]
  tx=cb.roundtrip(txraw);body,wits=tx[0],tx[1]
  assert cb.map_get(body,0).value==cb.roundtrip(raw_inputs)
  mint=cb.map_get(body,9)
  assert [key for key,_ in mint.pairs]==[pid]
  scripts=cb.map_get(wits,7)
  assert isinstance(scripts,cb.Tag) and scripts.number==258 and scripts.value==[policy]
  assert hashlib.blake2b(b"\x03"+policy,digest_size=28).digest()==pid
  redeemer=cb.map_get(cb.map_get(wits,5),[1,0])
  assert isinstance(redeemer,list) and len(redeemer)==2
  assert isinstance(redeemer[0],cb.Tag) and redeemer[0].number==121
  proofs=redeemer[0].value[0]
  assert len(proofs)==5 and all(isinstance(sig,bytes) and len(sig)==64 for sig in proofs)
  message=(PACKAGE/(label+".proof-message.bin")).read_bytes()
  assert message[43:47]==magic.to_bytes(4,"big")
  for key,signature in zip(keys,proofs):verify(key,signature,message)
  validation=manifest["artifacts"][label+".validation"]
  assert validation["mint0_redeemer"]["proof_signatures_hex"]==[signature.hex() for signature in proofs]
  assert validation["mint0_redeemer"]["constructor_tag"]==121 and validation["mint0_redeemer"]["proof_count"]==5
  assert hashlib.sha256(cb.dumps(redeemer[0])).hexdigest()==validation["mint0_redeemer"]["cbor_sha256"]
  body_hash=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
  funding=cb.map_get(wits,0)
  assert isinstance(funding,cb.Tag) and funding.number==258 and len(funding.value)==2
  resolved_refs=cb.roundtrip(raw_inputs)
  resolved_outputs=cb.roundtrip(raw_outputs)
  assert len(resolved_refs)==2 and len(resolved_outputs)==2
  assert cb.map_get(body,0).value==resolved_refs
  for public,signature in funding.value:verify(public,signature,body_hash)
  funding_key_hashes={hashlib.blake2b(public,digest_size=28).digest() for public,_ in funding.value}
  resolved_key_hashes={cb.map_get(output,0)[1:] for output in resolved_outputs}
  assert funding_key_hashes==resolved_key_hashes
  assert validation["valid_body_bound_ephemeral_signatures"] is True
  assert validation["private_keys_persisted"] is False
  control=manifest["positive_control"] if label=="positive-control" else manifest["negative"]
  assert control["mint_applied_v3_witness_identity_verified"] is True
  input_coin=sum(cb.map_get(output,1) for output in resolved_outputs)
  output_coin=0;native={}
  for output in cb.map_get(body,1):
   value=cb.map_get(output,1)
   if isinstance(value,int):output_coin+=value
   else:
    output_coin+=value[0]
    for policy_id,assets in value[1].pairs:
     for name,quantity in assets.pairs:native[(policy_id,name)]=native.get((policy_id,name),0)+quantity
  minted={(policy_id,name):quantity for policy_id,assets in mint.pairs for name,quantity in assets.pairs}
  fee=cb.map_get(body,2)
  assert (input_coin,output_coin,fee)==(17000000,16000000,1000000)
  assert native==minted=={(pid,b"VAMS-F05-AUTH-V3"):1}
  txs.append((body,raw_inputs,raw_outputs,proofs,cb.dumps(funding)))
 assert txs[0][0]==txs[1][0]
 assert txs[0][1]==txs[1][1] and txs[0][2]==txs[1][2]
 assert txs[0][4]==txs[1][4]  # byte-identical body-bound funding witness set
 assert txs[0][3]!=txs[1][3]

def test_case_and_family_checksums_cover_only_the_new_case():
 for directory in (PACKAGE,PACKAGE.parent):
  for line in (directory/"SHA256SUMS").read_text().splitlines():
   digest,name=line.split("  ",1)
   assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
 manifest=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 for name,entry in manifest["artifacts"].items():
  if name.endswith(".validation"):continue
  raw=(PACKAGE/name).read_bytes()
  assert len(raw)==entry["bytes"] and hashlib.sha256(raw).hexdigest()==entry["sha256"]
 family_manifest=json.loads((PACKAGE.parent/"FAMILY-MANIFEST.json").read_text())
 expected={path.relative_to(PACKAGE.parent).as_posix() for path in PACKAGE.parent.rglob("*")
  if path.is_file() and path.relative_to(PACKAGE.parent).as_posix() not in {"FAMILY-MANIFEST.json","SHA256SUMS"}}
 assert set(family_manifest["files"])==expected
 for relative,entry in family_manifest["files"].items():
  raw=(PACKAGE.parent/relative).read_bytes()
  assert len(raw)==entry["bytes"] and hashlib.sha256(raw).hexdigest()==entry["sha256"]
 assert family_manifest["case_ids_in_scope"]==["r2_signature_for_other_network"]
 assert family_manifest["next_cases_untouched"]==["r2_signature_for_other_validator_hash","r2_signature_for_other_epoch"]
 assert family_manifest["no_shared_status_or_registry_changed"] is True

