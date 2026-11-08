from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILDER=ROOT/"scripts/remediation/build_f05_2a_proof_other_validator_hash_r1.py"
PACKAGE=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_r1_20261005/r2_signature_for_other_validator_hash"
REG=ROOT/"docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
R41=ROOT/"docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json"
spec=importlib.util.spec_from_file_location("validator_hash_builder_test",BUILDER)
builder=importlib.util.module_from_spec(spec);sys.modules[spec.name]=builder;spec.loader.exec_module(builder)
fam=builder.load("other_validator_hash_test_fam",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
cb,h=fam.cb,fam.h

def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def verify(public:bytes,signature:bytes,message:bytes)->None:
 prefix=bytes.fromhex("302a300506032b6570032100");fds=[]
 try:
  for label,data in (("pub",prefix+public),("sig",signature),("msg",message)):
   fd=os.memfd_create("vams-validator-hash-test-"+label,0);fds.append(fd)
   if os.write(fd,data)!=len(data):raise AssertionError("short anonymous-memfd write")
   os.lseek(fd,0,0)
  pubfd,sigfd,msgfd=fds
  result=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pubfd}",
   "-keyform","DER","-in",f"/proc/self/fd/{msgfd}","-sigfile",f"/proc/self/fd/{sigfd}"],
   stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=tuple(fds),check=False)
  assert result.returncode==0,result.stderr.decode(errors="replace")
 finally:
  for fd in fds:os.close(fd)

def test_r4_1_case_and_original_assertion_are_preserved():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 reg=json.loads(REG.read_text());original=next(x for x in reg["negative_cases"] if x["id"]==m["case_id"])
 contract=json.loads(R41.read_text());row=next(x for x in contract["case_overrides"] if x["id"]==m["case_id"])
 assert m["case_id"]=="r2_signature_for_other_validator_hash"
 assert m["original_assertion"]==original=={"id":m["case_id"],"mutation":"sign_tuple_with_another_state_validator_hash"}
 assert m["contract_row"]==row
 assert m["preserved_security_assertion"]==row["preserved_security_assertion"]
 assert row["amended_contract"]["decision"]=="B"
 assert row["amended_contract"]["changed_condition"]=="ephemeral committee signs validator hash cd repeated 28 bytes; test policy uses derived hash"
 assert m["positive_control"]["status"]==m["negative"]["status"]=="PENDING"
 assert m["credit"]=={"negative_case":None,"original_policy":False,"ledger_admission":False,"live_network":False}
 assert "NOT RUN" in m["execution"] and "tx simulate" not in BUILDER.read_text()

def test_messages_differ_only_in_exact_alternate_validator_hash_field_and_signatures_verify():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 keys=[bytes.fromhex(x) for x in m["applied_parameters"]["committee_public_keys_hex"]]
 assert len(keys)==5 and keys==sorted(keys) and len(set(keys))==5
 seed=(bytes.fromhex(m["applied_parameters"]["seed_ref"]["tx_hash"]),m["applied_parameters"]["seed_ref"]["output_index"])
 positive=(PACKAGE/"positive-control.proof-message.bin").read_bytes()
 negative=(PACKAGE/"negative.proof-message.bin").read_bytes()
 applied=bytes.fromhex(m["applied_parameters"]["derived_applied_state_validator_hash"])
 alternate=bytes.fromhex(m["applied_parameters"]["alternate_signed_state_validator_hash"])
 assert applied==builder.STATE and alternate==bytes.fromhex("cd"*28) and applied!=alternate
 assert positive==h._canonical_pop_message(*seed,applied,keys)
 assert negative==h._canonical_pop_message(*seed,alternate,keys)
 offset=m["proof_message_relation"]["state_validator_hash_offset"]
 assert offset==82 and m["proof_message_relation"]["field_width"]==28
 assert positive[:offset]==negative[:offset] and positive[offset+28:]==negative[offset+28:]
 assert positive[offset:offset+28]==applied and negative[offset:offset+28]==alternate
 assert m["proof_message_relation"]["all_other_bytes_identical"] is True
 for label,message in (("positive-control",positive),("negative",negative)):
  tx=cb.roundtrip((PACKAGE/(label+".tx.cbor")).read_bytes())
  pair=cb.map_get(cb.map_get(tx[1],5),[1,0])
  proofs=pair[0].value[0]
  assert len(proofs)==5 and all(len(sig)==64 for sig in proofs)
  for key,sig in zip(keys,proofs):verify(key,sig,message)
  ref=m["artifacts"][label+".validation"]["mint0_redeemer"]
  assert ref["proof_signatures_hex"]==[sig.hex() for sig in proofs]

def test_same_body_context_and_funding_witness_with_only_mint_proofs_changed():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 positives=cb.roundtrip((PACKAGE/"positive-control.tx.cbor").read_bytes())
 negatives=cb.roundtrip((PACKAGE/"negative.tx.cbor").read_bytes())
 assert positives[0]==negatives[0]
 for name in ("raw_inputs.cbor","raw_outputs.cbor"):
  assert (PACKAGE/("positive-control."+name)).read_bytes()==(PACKAGE/("negative."+name)).read_bytes()
 assert cb.dumps(cb.map_get(positives[1],0))==cb.dumps(cb.map_get(negatives[1],0))
 p=cb.map_get(cb.map_get(positives[1],5),[1,0]);n=cb.map_get(cb.map_get(negatives[1],5),[1,0])
 assert len(p)==len(n)==2 and p[1]==n[1]
 assert p[0]!=n[0]
 assert m["shared_transaction_context"]=={"body_identical":True,"raw_inputs_identical":True,"raw_outputs_identical":True,
  "funding_witnesses_byte_identical":True,"only_witness_change":"Mint[0] proof list"}
 body=positives[0];bodyhash=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
 for public,sig in cb.map_get(positives[1],0).value:verify(public,sig,bodyhash)
 for public,sig in cb.map_get(negatives[1],0).value:verify(public,sig,bodyhash)

def test_policy_binding_datum_and_value_conservation():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 pid=bytes.fromhex(m["applied_policy"]["policy_id"])
 policy=(PACKAGE/"positive-control.applied-policy.cbor").read_bytes()
 assert policy==(PACKAGE/"negative.applied-policy.cbor").read_bytes()
 assert sha(policy)==m["applied_policy"]["compiled_script_sha256"]
 assert hashlib.blake2b(b"\x03"+policy,digest_size=28).digest()==pid
 seed=(bytes.fromhex(m["applied_parameters"]["seed_ref"]["tx_hash"]),m["applied_parameters"]["seed_ref"]["output_index"])
 keys=[bytes.fromhex(x) for x in m["applied_parameters"]["committee_public_keys_hex"]]
 state=h._authority_state(seed[0],seed[1],keys)
 for label in ("positive-control","negative"):
  tx=cb.roundtrip((PACKAGE/(label+".tx.cbor")).read_bytes())
  body,wit=tx[0],tx[1]
  mint=cb.map_get(body,9);scripts=cb.map_get(wit,7)
  assert [p for p,_ in mint.pairs]==[pid]
  assert isinstance(scripts,cb.Tag) and scripts.number==258 and scripts.value==[policy]
  assert hashlib.blake2b(b"\x03"+scripts.value[0],digest_size=28).digest()==pid
  datum=cb.map_get(cb.map_get(body,1)[0],2)
  assert datum==[1,cb.Tag(24,h.cbor(state))]
  inputs=cb.roundtrip((PACKAGE/(label+".raw_inputs.cbor")).read_bytes())
  resolved=cb.roundtrip((PACKAGE/(label+".raw_outputs.cbor")).read_bytes())
  assert cb.map_get(body,0).value==inputs and len(resolved)==2
  bodyhash=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
  funding=cb.map_get(wit,0)
  assert isinstance(funding,cb.Tag) and funding.number==258 and len(funding.value)==2
  for pub,sig in funding.value:verify(pub,sig,bodyhash)
  assert {hashlib.blake2b(pub,digest_size=28).digest() for pub,_ in funding.value}=={cb.map_get(o,0)[1:] for o in resolved}
  in_coin=sum(cb.map_get(o,1) for o in resolved);out_coin=0;native={}
  for o in cb.map_get(body,1):
   value=cb.map_get(o,1)
   if isinstance(value,int):out_coin+=value
   else:
    out_coin+=value[0]
    for pol,assets in value[1].pairs:
     for name,qty in assets.pairs:native[(pol,name)]=native.get((pol,name),0)+qty
  minted={(pol,name):qty for pol,assets in mint.pairs for name,qty in assets.pairs}
  assert (in_coin,out_coin,cb.map_get(body,2))==(17000000,16000000,1000000)
  assert native==minted=={(pid,b"VAMS-F05-AUTH-V3"):1}
 assert m["applied_parameters"]["private_key_material_persisted"] is False
 assert m["funding_and_conservation"]["collateral"]["present"] is False

def test_case_and_family_manifests_cover_all_candidate_bytes():
 for directory in (PACKAGE,PACKAGE.parent):
  for line in (directory/"SHA256SUMS").read_text().splitlines():
   digest,name=line.split("  ",1)
   assert sha((directory/name).read_bytes())==digest
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 for name,row in m["artifacts"].items():
  if name.endswith(".validation"):continue
  raw=(PACKAGE/name).read_bytes()
  assert len(raw)==row["bytes"] and sha(raw)==row["sha256"]
 fm=json.loads((PACKAGE.parent/"FAMILY-MANIFEST.json").read_text())
 expected={p.relative_to(PACKAGE.parent).as_posix() for p in PACKAGE.parent.rglob("*")
  if p.is_file() and p.relative_to(PACKAGE.parent).as_posix() not in {"FAMILY-MANIFEST.json","SHA256SUMS"}}
 assert set(fm["files"])==expected
 for name,row in fm["files"].items():
  raw=(PACKAGE.parent/name).read_bytes()
  assert len(raw)==row["bytes"] and sha(raw)==row["sha256"]
 assert fm["case_ids_in_scope"]==["r2_signature_for_other_validator_hash"]
 assert fm["no_source_registry_status_or_handoff_changed"] is True

