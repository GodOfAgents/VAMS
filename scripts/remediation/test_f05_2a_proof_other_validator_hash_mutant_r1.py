from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILDER=ROOT/"scripts/remediation/build_f05_2a_proof_other_validator_hash_mutant_r1.py"
PACKAGE=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_mutant_r1_20261005/r2_signature_for_other_validator_hash"
BASE=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_r1_20261005/r2_signature_for_other_validator_hash"
CANONICAL=ROOT/"cardano/validators/f05_authority_policy.ak"
spec=importlib.util.spec_from_file_location("validator_hash_mutant_builder_test",BUILDER)
builder=importlib.util.module_from_spec(spec);sys.modules[spec.name]=builder;spec.loader.exec_module(builder)
fam=builder.load("hash_mutant_test_fam",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
cb,h=fam.cb,fam.h

def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def verify(public:bytes,signature:bytes,message:bytes)->None:
 prefix=bytes.fromhex("302a300506032b6570032100")
 fds=[]
 try:
  for label,data in (("pub",prefix+public),("sig",signature),("msg",message)):
   fd=os.memfd_create("vams-validator-hash-mutant-test-"+label,0);fds.append(fd)
   if os.write(fd,data)!=len(data):raise AssertionError("short anonymous-memfd write")
   os.lseek(fd,0,0)
  pubfd,sigfd,msgfd=fds
  result=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pubfd}",
   "-keyform","DER","-in",f"/proc/self/fd/{msgfd}","-sigfile",f"/proc/self/fd/{sigfd}"],
   stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=tuple(fds),check=False)
  assert result.returncode==0,result.stderr.decode(errors="replace")
 finally:
  for fd in fds:os.close(fd)

def test_exact_single_source_call_mutation_and_recompiled_identity():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 before=CANONICAL.read_text(encoding="utf-8")
 assert sha(before.encode())==m["source_mutation"]["source_before_sha256"]
 assert before.count(builder.OLD_CALL)==1
 after=before.replace(builder.OLD_CALL,builder.NEW_CALL,1)
 assert sha(after.encode())==m["source_mutation"]["source_mutant_sha256"]
 patch=(PACKAGE/"SOURCE-DIFF.patch").read_text()
 removed=[line[1:] for line in patch.splitlines() if line.startswith("-") and not line.startswith("---")]
 added=[line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
 assert len(removed)==len(added)==1
 assert "state_validator_script_hash," in removed[0]
 assert '#"cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd"' in added[0]
 assert m["source_mutation"]["replacement_count"]==1
 assert m["source_mutation"]["canonical_state_validator_hash_constant_unchanged"] is True
 assert builder.OLD_CALL not in after and builder.NEW_CALL in after
 script=(PACKAGE/"mutant.applied-policy.cbor").read_bytes()
 pid=bytes.fromhex(m["mutant_policy"]["policy_id"])
 assert sha(script)==m["mutant_policy"]["compiled_script_sha256"]
 assert hashlib.blake2b(b"\x03"+script,digest_size=28).digest()==pid
 assert m["mutant_policy"]["state_validator_hash"]=="b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66"

def test_reuses_exact_reviewed_negative_proof_parameters_and_inputs():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 for name in ("tx.cbor","raw_inputs.cbor","raw_outputs.cbor","proof-message.bin","applied-policy.cbor","genesis_ref.cbor","initial_keys.cbor"):
  assert (PACKAGE/("reviewed-negative."+name)).read_bytes()==(BASE/("negative."+name)).read_bytes()
 msg=(PACKAGE/"mutant.proof-message.bin").read_bytes()
 assert msg==(BASE/"negative.proof-message.bin").read_bytes()
 assert sha(msg)==m["prior_negative"]["proof_message_sha256"]
 assert msg[82:110]==bytes.fromhex("cd"*28)
 original=cb.roundtrip((BASE/"negative.tx.cbor").read_bytes())
 mutant=cb.roundtrip((PACKAGE/"mutant.tx.cbor").read_bytes())
 oldpair=cb.map_get(cb.map_get(original[1],5),[1,0])
 newpair=cb.map_get(cb.map_get(mutant[1],5),[1,0])
 assert len(oldpair)==len(newpair)==2 and oldpair[1]==newpair[1]
 proofs=oldpair[0].value[0]
 assert newpair[0].value[0]==proofs
 assert [p.hex() for p in proofs]==m["mutant_control"]["proof_signatures_hex"]
 keys=[bytes.fromhex(k) for k in m["applied_parameters"]["committee_public_keys_hex"]]
 assert len(keys)==5 and keys==sorted(keys) and len(set(keys))==5
 for key,sig in zip(keys,proofs):verify(key,sig,msg)
 assert (PACKAGE/"mutant.raw_inputs.cbor").read_bytes()==(BASE/"negative.raw_inputs.cbor").read_bytes()
 assert m["mutant_control"]["same_reviewed_negative_proofs_parameters_and_input_refs"] is True

def test_mutant_rebinds_policy_mint_v3_and_preserves_canonical_output_context():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 script=(PACKAGE/"mutant.applied-policy.cbor").read_bytes()
 pid=bytes.fromhex(m["mutant_policy"]["policy_id"])
 txraw=(PACKAGE/"mutant.tx.cbor").read_bytes()
 assert sha(txraw)==m["mutant_control"]["transaction_sha256"]
 tx=cb.roundtrip(txraw);body,wit=tx[0],tx[1]
 mint=cb.map_get(body,9);v3=cb.map_get(wit,7)
 assert [policy for policy,_ in mint.pairs]==[pid]
 assert isinstance(v3,cb.Tag) and v3.number==258 and v3.value==[script]
 assert hashlib.blake2b(b"\x03"+v3.value[0],digest_size=28).digest()==pid
 canonical=cb.map_get(cb.map_get(body,1)[0],0)
 assert canonical[1:]==bytes.fromhex("b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66")
 params=m["applied_parameters"]
 keys=[bytes.fromhex(k) for k in params["committee_public_keys_hex"]]
 seed=(bytes.fromhex(params["seed_ref"]["tx_hash"]),params["seed_ref"]["output_index"])
 expected=h._authority_state(seed[0],seed[1],keys)
 assert cb.map_get(cb.map_get(body,1)[0],2)==[1,cb.Tag(24,h.cbor(expected))]
 prior_body=cb.roundtrip((BASE/"negative.tx.cbor").read_bytes())[0]
 assert cb.map_get(body,0)==cb.map_get(prior_body,0)
 assert cb.map_get(body,2)==cb.map_get(prior_body,2)
 mutant_outputs=cb.map_get(body,1);prior_outputs=cb.map_get(prior_body,1)
 assert len(mutant_outputs)==len(prior_outputs)
 for current,prior in zip(mutant_outputs,prior_outputs):
  cv=cb.map_get(current,1);pv=cb.map_get(prior,1)
  current_coin=cv if isinstance(cv,int) else cv[0]
  prior_coin=pv if isinstance(pv,int) else pv[0]
  assert current_coin==prior_coin
 assert m["mutant_control"]["canonical_authority_output_address_retained"] is True

def test_body_bound_funding_signatures_conservation_and_positive_control():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 mutant=cb.roundtrip((PACKAGE/"mutant.tx.cbor").read_bytes())
 body,wit=mutant[0],mutant[1]
 bodyhash=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
 funds=cb.map_get(wit,0)
 assert isinstance(funds,cb.Tag) and funds.number==258 and len(funds.value)==2
 for pub,sig in funds.value:verify(pub,sig,bodyhash)
 refs=cb.roundtrip((PACKAGE/"mutant.raw_inputs.cbor").read_bytes())
 resolved=cb.roundtrip((PACKAGE/"mutant.raw_outputs.cbor").read_bytes())
 assert cb.map_get(body,0).value==refs
 assert {hashlib.blake2b(pub,digest_size=28).digest() for pub,_ in funds.value}=={cb.map_get(out,0)[1:] for out in resolved}
 in_coin=sum(cb.map_get(out,1) for out in resolved);out_coin=0;native={}
 mint=cb.map_get(body,9)
 for out in cb.map_get(body,1):
  value=cb.map_get(out,1)
  if isinstance(value,int):out_coin+=value
  else:
   out_coin+=value[0]
   for policy,assets in value[1].pairs:
    for name,qty in assets.pairs:native[(policy,name)]=native.get((policy,name),0)+qty
 minted={(policy,name):qty for policy,assets in mint.pairs for name,qty in assets.pairs}
 assert (in_coin,out_coin,cb.map_get(body,2))==(17000000,16000000,1000000)
 assert native==minted=={(bytes.fromhex(m["mutant_policy"]["policy_id"]),b"VAMS-F05-AUTH-V3"):1}
 assert m["funding_and_conservation"]["private_keys_ephemeral"] is True
 assert m["applied_parameters"]["private_key_material_persisted"] is False
 prior_pos=PACKAGE/"positive-control.tx.cbor"
 base_pos=BASE/"positive-control.tx.cbor"
 assert prior_pos.read_bytes()==base_pos.read_bytes()
 posrun=json.loads((PACKAGE/"prior-positive-run.json").read_text())
 observed=posrun["attempt"]["runner_result"]
 assert observed["simulator_child_exit"]==0
 assert observed["simulator_result"]["stage"]=="script_accepted"
 assert m["positive_control"]["accepted_control_credit_scope"]=="synthetic positive only"

def test_case_and_family_hash_inventories():
 for directory in (PACKAGE,PACKAGE.parent):
  for line in (directory/"SHA256SUMS").read_text().splitlines():
   digest,name=line.split("  ",1)
   assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 for name,entry in m["artifacts"].items():
  raw=(PACKAGE/name).read_bytes()
  assert len(raw)==entry["bytes"] and hashlib.sha256(raw).hexdigest()==entry["sha256"]
 fm=json.loads((PACKAGE.parent/"FAMILY-MANIFEST.json").read_text())
 expected={p.relative_to(PACKAGE.parent).as_posix() for p in PACKAGE.parent.rglob("*")
  if p.is_file() and p.relative_to(PACKAGE.parent).as_posix() not in {"FAMILY-MANIFEST.json","SHA256SUMS"}}
 assert set(fm["files"])==expected
 for rel,entry in fm["files"].items():
  raw=(PACKAGE.parent/rel).read_bytes()
  assert len(raw)==entry["bytes"] and hashlib.sha256(raw).hexdigest()==entry["sha256"]
 assert fm["case_ids_in_scope"]==["r2_signature_for_other_validator_hash"]
 assert fm["source_registry_status_handoff_unchanged"] is True
 assert m["status"].startswith("candidate-awaiting-independent-byte-review")
 assert m["mutant_control"]["status"]=="PENDING"
 assert m["credit"]["negative_case"] is None and m["credit"]["mutant_acceptance"] is None

