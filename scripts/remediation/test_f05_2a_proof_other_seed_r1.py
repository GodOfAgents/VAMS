from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/"docs/remediation/m3_f05_2a_proof_domain_family_r1_20261005/r2_signature_for_other_seed"
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
fam=load("proof_seed_test_builder",ROOT/"scripts/remediation/build_f05_2a_proof_other_seed_r1.py").family()
cb=fam.cb
def verify(pub,sig,msg):
 prefix=bytes.fromhex("302a300506032b6570032100");fds=[]
 try:
  for name,data in (("pub",prefix+pub),("sig",sig),("msg",msg)):
   fd=os.memfd_create("vams-proof-domain-review-"+name,0);fds.append(fd);os.write(fd,data);os.lseek(fd,0,0)
  pubfd,sigfd,msgfd=fds
  r=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pubfd}","-keyform","DER","-in",f"/proc/self/fd/{msgfd}","-sigfile",f"/proc/self/fd/{sigfd}"],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=tuple(fds),check=False)
  assert r.returncode==0
 finally:
  for fd in fds:os.close(fd)
def test_fixture_preserves_case_and_is_pending():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 assert m["case_id"]=="r2_signature_for_other_seed" and m["original_case_id_preserved"]
 assert m["original_assertion"]["id"]==m["case_id"]
 assert m["original_assertion"]["mutation"]=="sign_same_tuple_with_alternate_seed"
 assert m["positive_control"]["status"]=="PENDING" and m["negative"]["status"]=="PENDING"
 assert m["credit"]=={"negative_case":None,"original_policy":False,"ledger_admission":False,"live_network":False}
 assert m["execution"].startswith("not run")
def test_positive_and_negative_bind_same_applied_policy_and_differ_only_in_seed_message():
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 pid=bytes.fromhex(m["applied_policy"]["policy_id"]);keys=[bytes.fromhex(x) for x in m["applied_parameters"]["committee_public_keys_hex"]]
 assert len(keys)==5 and keys==sorted(keys) and len(set(keys))==5
 txs=[]
 for label in ("positive-control","negative"):
  code=(PACKAGE/f"{label}.applied-policy.cbor").read_bytes();tx=cb.roundtrip((PACKAGE/f"{label}.tx.cbor").read_bytes());body,wit=tx[0],tx[1]
  mint=cb.map_get(body,9);assert [k for k,_ in mint.pairs]==[pid]
  scripts=cb.map_get(wit,7);assert isinstance(scripts,cb.Tag) and scripts.number==258 and scripts.value==[code]
  assert hashlib.blake2b(bytes([3])+code,digest_size=28).digest()==pid
  redeemer=cb.map_get(cb.map_get(wit,5),[1,0]);assert isinstance(redeemer,list) and isinstance(redeemer[0],cb.Tag) and redeemer[0].number==121
  proofs=redeemer[0].value[0];assert len(proofs)==5 and all(len(s)==64 for s in proofs)
  msg=(PACKAGE/f"{label}.proof-message.bin").read_bytes();assert len(msg)==279
  for key,sig in zip(keys,proofs):verify(key,sig,msg)
  for suffix in ("tx.cbor","raw_inputs.cbor","raw_outputs.cbor","applied-policy.cbor"):
   ref=m["artifacts"][f"{label}.{suffix}"];data=(PACKAGE/f"{label}.{suffix}").read_bytes()
   assert len(data)==ref["bytes"] and hashlib.sha256(data).hexdigest()==ref["sha256"]
  txs.append((body,msg,proofs))
 assert txs[0][0]==txs[1][0]
 assert txs[0][1][48:80]==bytes.fromhex("ab"*32)
 assert txs[1][1][48:80]==bytes.fromhex("ad"*32)
 assert txs[0][1][:48]==txs[1][1][:48] and txs[0][1][80:]==txs[1][1][80:]
 assert txs[0][2]!=txs[1][2]
def test_package_checksums_and_conservation():
 for directory in (PACKAGE,PACKAGE.parent):
  for line in (directory/"SHA256SUMS").read_text().splitlines():
   digest,name=line.split("  ",1);assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
 m=json.loads((PACKAGE/"FIXTURE-MANIFEST.json").read_text())
 for label in ("positive-control","negative"):
  c=m["artifacts"][label+".validation"]
  assert c["valid_body_bound_ephemeral_signatures"] is True and c["private_keys_persisted"] is False
  assert c["ada_conservation"] and c["native_asset_conservation"]
 assert m["funding_and_conservation"]["inputs_lovelace"]==17000000
 assert m["funding_and_conservation"]["authority_output_lovelace"]+m["funding_and_conservation"]["change_output_lovelace"]+m["funding_and_conservation"]["fee_lovelace"]==17000000
