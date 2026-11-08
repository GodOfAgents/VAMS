"""Structural checks for the R1 candidate; this test never invokes a simulator."""
from __future__ import annotations
import hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BUILDER=ROOT/"scripts/remediation/build_f05_2a_applied_keys_parameter_mutant_r1.py"
SPEC=importlib.util.spec_from_file_location("akp_mutant_r1_builder",BUILDER)
b=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=b;SPEC.loader.exec_module(b)
base=importlib.util.module_from_spec(importlib.util.spec_from_file_location("akp_base_test",b.BASE))
sys.modules["akp_base_test"]=base;sys.modules["akp_base_test"].__spec__=importlib.util.spec_from_file_location("akp_base_test",b.BASE);sys.modules["akp_base_test"].__spec__.loader.exec_module(base)
cb,h=base.cb,base.h
OUT=b.OUT;R5=b.R5
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify(pub,sig,msg):
 prefix=bytes.fromhex("302a300506032b6570032100");fds=[]
 try:
  for label,data in (("pub",prefix+pub),("sig",sig),("msg",msg)):
   fd=os.memfd_create("akp-r1-"+label,0);fds.append(fd);assert os.write(fd,data)==len(data);os.lseek(fd,0,0)
  p,s,m=fds
  result=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{p}","-keyform","DER","-in",f"/proc/self/fd/{m}","-sigfile",f"/proc/self/fd/{s}"],pass_fds=tuple(fds),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
  assert result.returncode==0
 finally:
  for fd in fds:os.close(fd)

def test_r1_candidate_exact_r5_binding_and_no_simulation():
 m=json.loads((OUT/"FIXTURE-MANIFEST.json").read_text());r5=json.loads((b.MANIFEST).read_text())
 assert m["case_id"]=="applied_keys_parameter" and m["assertion"]==r5["assertion"] and m["original_case_id_preserved"]
 assert m["status"]=="candidate-awaiting-independent-byte-review; tx-sim-not-run; case-and-mutation-PENDING"
 assert m["credit"]=={"case":False,"mutation":False,"original_policy":False,"ledger_admission":False,"live_network":False}
 assert m["mutant"]["status"]=="not executed" and m["toolchain"]["simulation"]=="not run"
 assert not any("run" in x.lower() and "sim" in x.lower() for x in sys.argv)
 # Candidate normal compilation reproduces the exact R5 applied code/identity.
 normal=(R5/"negative.applied-policy.cbor").read_bytes()
 assert sha(normal)==b.CODE_SHA==m["normal_policy_recompile"]["code_sha256"]
 assert hashlib.blake2b(b"\x03"+normal,digest_size=28).hexdigest()==b.PID==m["normal_policy_recompile"]["policy_id"]
 assert m["normal_policy_recompile"]["exact_R5_code_and_ID_match"]
 # Exact one-line source mutation and source hash provenance.
 patch=(OUT/"MUTANT-SOURCE.patch").read_text()
 changes=[x for x in patch.splitlines() if x.startswith(("+","-")) and not x.startswith(("+++","---"))]
 assert changes==["-    && "+b.OLD,"+    && True"]==m["source_mutation"]["changed_lines"]
 assert m["source_mutation"]["replacement"]=="True" and m["source_mutation"]["predicate"]==b.OLD
 # R5 transaction, datum, input set and PoP redeemer stay fixed; policy is rebound.
 old=cb.roundtrip((R5/"negative.tx.cbor").read_bytes())
 tx=cb.roundtrip((OUT/"one-guard-mutant-control.tx.cbor").read_bytes());body,wit=tx[0],tx[1]
 old_red=cb.map_get(cb.map_get(old[1],5),[1,0]);red=cb.map_get(cb.map_get(wit,5),[1,0])
 assert cb.dumps(red)==(OUT/"R5-exact-negative-redeemer.cbor").read_bytes()==cb.dumps(old_red)
 assert cb.map_get(body,0)==cb.map_get(old[0],0)
 assert cb.map_get(cb.map_get(body,1)[0],2)==cb.map_get(cb.map_get(old[0],1)[0],2)
 assert (OUT/"one-guard-mutant-control.raw_inputs.cbor").read_bytes()==(R5/"negative.raw_inputs.cbor").read_bytes()
 # Five PoPs verify against the applied parameter keys (not the datum's differing keys).
 app=r5["policy_applications"]["negative"]["parameter_cbor"]
 keys=[bytes.fromhex(x) for x in app["initial_keys"]["values_hex"]]
 seed=app["genesis_ref"]["value"];genesis=(bytes.fromhex(seed["tx_hash"]),seed["output_index"])
 proof_list=red[0].value[0];msg=h._canonical_pop_message(genesis[0],genesis[1],base.STATE,keys)
 assert len(keys)==len(proof_list)==5
 assert [x.hex() for x in proof_list]==r5["artifacts"]["negative.validation"]["mint0_redeemer"]["proof_signatures_hex"]
 for pub,sig in zip(keys,proof_list):verify(pub,sig,msg)
 # Mutant identity matches mint and V3 script witness at the intended Mint[0] entrypoint.
 code=(OUT/"one-guard-mutant-control.applied-policy.cbor").read_bytes()
 mid=hashlib.blake2b(b"\x03"+code,digest_size=28).digest()
 assert mid.hex()==m["mutant"]["policy_id"] and mid.hex()!=b.PID
 assert [pid for pid,_ in cb.map_get(body,9).pairs]==[mid]
 scripts=cb.map_get(wit,7);assert scripts.number==258 and scripts.value==[code]
 assert m["entrypoint"].endswith("mint / Mint[0]")
 # Body-bound ephemeral funding witnesses, resolved addresses, ADA and native asset conservation.
 resolved=cb.roundtrip((OUT/"one-guard-mutant-control.raw_outputs.cbor").read_bytes())
 body_hash=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
 witnesses=cb.map_get(wit,0);assert witnesses.number==258 and len(witnesses.value)==2
 for pub,sig in witnesses.value:verify(pub,sig,body_hash)
 assert {hashlib.blake2b(pub,digest_size=28).digest() for pub,_ in witnesses.value}=={cb.map_get(o,0)[1:] for o in resolved}
 input_coin=sum(cb.map_get(o,1) for o in resolved);output_coin=0;native={}
 for o in cb.map_get(body,1):
  value=cb.map_get(o,1)
  if isinstance(value,int):output_coin+=value
  else:
   output_coin+=value[0]
   for pid,assets in value[1].pairs:
    for name,q in assets.pairs:native[(pid,name)]=native.get((pid,name),0)+q
 minted={(pid,name):q for pid,assets in cb.map_get(body,9).pairs for name,q in assets.pairs}
 assert (input_coin,output_coin,cb.map_get(body,2))==(17_000_000,16_000_000,1_000_000)
 assert native==minted=={(mid,b"VAMS-F05-AUTH-V3"):1}
 assert m["mutant"]["validation"]=={"body_hash":body_hash.hex(),"funding_signatures":2,"valid_body_bound_ephemeral_signatures":True,"private_keys_persisted":False,"ada_conservation":True,"native_asset_conservation":True}
 # Every package byte is checksummed; private key material is absent.
 entries={}
 for line in (OUT/"SHA256SUMS").read_text().splitlines():
  digest,name=line.split("  ",1);entries[name]=digest
 files={p.name for p in OUT.iterdir() if p.is_file() and p.name!="SHA256SUMS"}
 assert set(entries)==files
 for name,digest in entries.items():assert sha((OUT/name).read_bytes())==digest
 assert "private" not in "".join(entries).lower()
