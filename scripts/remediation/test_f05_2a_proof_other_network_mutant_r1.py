from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILDER=ROOT/"scripts/remediation/build_f05_2a_proof_other_network_mutant_r1.py"
PACKAGE=ROOT/"docs/remediation/m3_f05_2a_proof_other_network_mutant_r1_20261005/r2_signature_for_other_network"
R2=ROOT/"docs/remediation/m3_f05_2a_proof_domain_family_r2_20261005/r2_signature_for_other_network"
R21=ROOT/"docs/remediation/m3_f05_2a_proof_other_network_negative_attempt_r1_20261005/RUN.json"
SOURCE=ROOT/"cardano/lib/vams/f05_authority.ak"
spec=importlib.util.spec_from_file_location("network_magic_mutant_builder_for_test",BUILDER)
builder=importlib.util.module_from_spec(spec);sys.modules[spec.name]=builder;spec.loader.exec_module(builder)
fam=builder.load("network_mutant_test_fam",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
cb,h=fam.cb,fam.h

def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def verify(public:bytes,signature:bytes,message:bytes)->None:
 prefix=bytes.fromhex("302a300506032b6570032100");fds=[]
 try:
  for label,data in (("pub",prefix+public),("sig",signature),("msg",message)):
   fd=os.memfd_create("vams-network-mutant-test-"+label,0);fds.append(fd)
   if os.write(fd,data)!=len(data):raise AssertionError("short anonymous-memfd write")
   os.lseek(fd,0,0)
  pubfd,sigfd,msgfd=fds
  checked=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pubfd}",
   "-keyform","DER","-in",f"/proc/self/fd/{msgfd}","-sigfile",f"/proc/self/fd/{sigfd}"],
   stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=tuple(fds),check=False)
  assert checked.returncode==0,checked.stderr.decode(errors="replace")
 finally:
  for fd in fds:os.close(fd)

def test_manifest_preserves_r21_case_parameters_and_pending_scope():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 r21=json.loads(R21.read_text())
 assert m["case_id"]=="r2_signature_for_other_network"
 assert m["original_assertion"]=="sign_tuple_with_another_network_magic"
 assert m["R21_basis"]["exact_original_negative_transaction_sha256"]==r21["fixture"]["transaction_sha256"]
 assert m["R21_basis"]["exact_proof_message_sha256"]==r21["fixture"]["proof_message_sha256"]
 assert m["status"].startswith("candidate-awaiting-independent-byte-review")
 assert m["mutant_control"]["status"]=="PENDING"
 assert m["credit"]=={"negative_case":None,"mutation_suite":None,"original_policy":False,"ledger_admission":False,"live_network":False}
 assert "NOT RUN" in m["execution"]
 assert "tx simulate" not in BUILDER.read_text()
 assert "run_typed_tx_case(" not in BUILDER.read_text()

def test_source_patch_changes_only_expected_magic_and_compiled_policy_rebinds():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 mutation=m["source_mutation"]
 current=SOURCE.read_bytes()
 patch=(PACKAGE/"SOURCE-MUTATION.patch").read_text()
 old=builder.OLD;new=builder.NEW
 current_text=current.decode()
 assert current_text.count(old)==1
 assert sha(current)==mutation["old_source_sha256"]
 mutant_text=current_text.replace(old,new,1)
 assert sha(mutant_text.encode())==mutation["mutant_source_sha256"]
 assert mutation["replacement_count"]==1
 assert mutation["function"]=="authority_genesis_pop_preimage"
 assert mutation["line"]==109
 minus=[line[1:] for line in patch.splitlines() if line.startswith("-") and not line.startswith("---")]
 plus=[line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
 assert len(minus)==len(plus)==1 and old in minus[0] and new in plus[0]
 mutant_policy=(PACKAGE/"mutant.applied-policy.cbor").read_bytes()
 policy=m["mutant_policy"];pid=bytes.fromhex(policy["policy_id"])
 assert sha(mutant_policy)==policy["compiled_script_sha256"]
 assert hashlib.blake2b(b"\x03"+mutant_policy,digest_size=28).digest()==pid
 assert policy["state_validator_hash"]==builder.STATE.hex()
 assert mutation["all_other_guards_and_ed25519_verification_retained"] is True

def test_exact_r21_message_and_signatures_are_retained_and_valid():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 exact=(R2/"negative.proof-message.bin").read_bytes()
 message=(PACKAGE/"mutant.proof-message.bin").read_bytes()
 tx=cb.roundtrip((PACKAGE/"mutant.tx.cbor").read_bytes())
 assert message==exact and sha(message)==builder.R21_MSG_SHA
 assert message[43:47]==bytes(4)
 params=m["applied_parameters"]
 keys=[bytes.fromhex(k) for k in params["committee_public_keys_hex"]]
 seed=(bytes.fromhex(params["seed_ref"]["tx_hash"]),params["seed_ref"]["output_index"])
 assert h._canonical_pop_message(*seed,builder.STATE,keys,network_magic=0)==message
 original_tx=cb.roundtrip((R2/"negative.tx.cbor").read_bytes())
 exact_proofs=cb.map_get(cb.map_get(original_tx[1],5),[1,0])[0].value[0]
 redeemer=cb.map_get(cb.map_get(tx[1],5),[1,0])
 assert isinstance(redeemer,list) and len(redeemer)==2
 proofs=redeemer[0].value[0]
 assert proofs==exact_proofs
 assert [p.hex() for p in proofs]==m["mutant_control"]["same_R21_proof_signatures_hex"]
 for key,sig in zip(keys,proofs):verify(key,sig,message)

def test_mutant_transaction_binding_funding_datum_and_conservation():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 txraw=(PACKAGE/"mutant.tx.cbor").read_bytes()
 assert sha(txraw)==m["mutant_control"]["transaction_sha256"]
 tx=cb.roundtrip(txraw);body,wit=tx[0],tx[1]
 raw_inputs=cb.roundtrip((PACKAGE/"mutant.raw_inputs.cbor").read_bytes())
 resolved=cb.roundtrip((PACKAGE/"mutant.raw_outputs.cbor").read_bytes())
 assert cb.map_get(body,0).value==raw_inputs
 pid=bytes.fromhex(m["mutant_policy"]["policy_id"])
 mint=cb.map_get(body,9)
 assert [p for p,_ in mint.pairs]==[pid]
 scripts=cb.map_get(wit,7)
 assert isinstance(scripts,cb.Tag) and scripts.number==258
 assert scripts.value==[(PACKAGE/"mutant.applied-policy.cbor").read_bytes()]
 assert hashlib.blake2b(b"\x03"+scripts.value[0],digest_size=28).digest()==pid
 redeemer_pair=cb.map_get(cb.map_get(wit,5),[1,0])
 assert isinstance(redeemer_pair,list) and len(redeemer_pair)==2
 assert isinstance(redeemer_pair[0],cb.Tag) and redeemer_pair[0].number==121
 params=m["applied_parameters"]
 keys=[bytes.fromhex(k) for k in params["committee_public_keys_hex"]]
 seed=(bytes.fromhex(params["seed_ref"]["tx_hash"]),params["seed_ref"]["output_index"])
 state=h._authority_state(seed[0],seed[1],keys)
 datum=cb.map_get(cb.map_get(body,1)[0],2)
 assert isinstance(datum,list) and len(datum)==2 and datum[0]==1
 assert isinstance(datum[1],cb.Tag) and datum[1].number==24 and datum[1].value==h.cbor(state)
 assert h.cbor(state)==cb.map_get(cb.map_get(cb.roundtrip((R2/"negative.tx.cbor").read_bytes())[0],1)[0],2)[1].value
 body_hash=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
 funding=cb.map_get(wit,0)
 assert isinstance(funding,cb.Tag) and funding.number==258 and len(funding.value)==2
 for public,signature in funding.value:verify(public,signature,body_hash)
 resolved_hashes={cb.map_get(out,0)[1:] for out in resolved}
 assert {hashlib.blake2b(pub,digest_size=28).digest() for pub,_ in funding.value}==resolved_hashes
 input_coin=sum(cb.map_get(out,1) for out in resolved);output_coin=0;native={}
 for out in cb.map_get(body,1):
  value=cb.map_get(out,1)
  if isinstance(value,int):output_coin+=value
  else:
   output_coin+=value[0]
   for policy,assets in value[1].pairs:
    for name,qty in assets.pairs:native[(policy,name)]=native.get((policy,name),0)+qty
 minted={(policy,name):qty for policy,assets in mint.pairs for name,qty in assets.pairs}
 assert (input_coin,output_coin,cb.map_get(body,2))==(17000000,16000000,1000000)
 assert native==minted=={(pid,b"VAMS-F05-AUTH-V3"):1}
 assert m["funding_and_conservation"]["funding_signatures_body_bound"] is True
 assert m["funding_and_conservation"]["funding_private_keys_ephemeral"] is True
 assert m["applied_parameters"]["private_key_material_persisted"] is False
 for path in PACKAGE.iterdir():
  if path.is_file():
   raw=path.read_bytes()
   assert b"-----BEGIN PRIVATE KEY-----" not in raw and b"PRIVATE KEY" not in raw

def test_case_and_family_checksums_cover_all_artifacts():
 for directory in (PACKAGE,PACKAGE.parent):
  sums=(directory/"SHA256SUMS").read_text().splitlines()
  for line in sums:
   digest,name=line.split("  ",1)
   assert sha((directory/name).read_bytes())==digest
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 for name,row in m["artifacts"].items():
  raw=(PACKAGE/name).read_bytes()
  assert len(raw)==row["bytes"] and sha(raw)==row["sha256"]
 family=json.loads((PACKAGE.parent/"FAMILY-MANIFEST.json").read_text())
 expected={p.relative_to(PACKAGE.parent).as_posix() for p in PACKAGE.parent.rglob("*")
  if p.is_file() and p.relative_to(PACKAGE.parent).as_posix() not in {"FAMILY-MANIFEST.json","SHA256SUMS"}}
 assert set(family["files"])==expected
 for name,row in family["files"].items():
  raw=(PACKAGE.parent/name).read_bytes()
  assert len(raw)==row["bytes"] and sha(raw)==row["sha256"]
 assert family["case_ids_in_scope"]==["r2_signature_for_other_network"]
 assert family["no_source_registry_status_or_handoff_changes"] is True

