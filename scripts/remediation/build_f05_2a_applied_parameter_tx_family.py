#!/usr/bin/env python3
"""Build one alternate-applied-policy F05.2a CBOR candidate; never simulates."""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
HARNESS=ROOT/"scripts/remediation/test_f05_2a_authority_bootstrap_public.py"
REG=ROOT/"docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
R41=ROOT/"docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json"
FIX=ROOT/"docs/remediation/m3_f05_2a/tx_sim_r1"
OUT=ROOT/"docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005"
CASES=("applied_genesis_parameter","applied_keys_parameter","applied_keys_bad_count","applied_keys_bad_length","applied_keys_duplicate","applied_keys_unsorted")
ORIGINAL="9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"
HASHES={"valid.tx.cbor":"765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28","raw_inputs.cbor":"4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe","raw_outputs.cbor":"9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a"}
STATE=bytes.fromhex("b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66")
SEED=(bytes.fromhex("aa"*32),7)
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); sys.modules[n]=m; s.loader.exec_module(m); return m
h=load("f05family_harness",HARNESS); cb=load("f05family_cbor",ROOT/"scripts/remediation/f05_2a_tx_sim_registry.py")
def sha(b): return hashlib.sha256(b).hexdigest()
def params_for(cid,keys,alternate_key=None):
 ks=list(keys); seed=SEED
 if cid=="applied_genesis_parameter": seed=(bytes.fromhex("ab"*32),7)
 elif cid=="applied_keys_parameter": ks=sorted([*ks[:-1], alternate_key if alternate_key is not None else bytes(32)])
 elif cid=="applied_keys_bad_count": ks.append(bytes.fromhex("ff"*32))
 elif cid=="applied_keys_bad_length": ks[0]=bytes(31)
 elif cid=="applied_keys_duplicate": ks[1]=ks[0]
 elif cid=="applied_keys_unsorted": ks[1],ks[2]=ks[2],ks[1]
 else: raise ValueError("unknown case")
 return {"genesis_ref":h._output_reference(*seed),"initial_keys":h.list_data([h.byte_string(k) for k in ks])},ks,seed
def compile_policy(aiken,params,work,mutation=None):
 p=h._compile(ROOT/"cardano",aiken,work,params,mutation)
 if hashlib.blake2b(b"\x03"+p["code"],digest_size=28).digest()!=p["policy_id"] or p["state_credential"]!=STATE: raise ValueError("policy/script or state hash mismatch")
 return p
def rename(x,old,new):
 if isinstance(x,cb.Map):
  pairs=[(new if k==old else k,rename(v,old,new)) for k,v in x.pairs]; pairs.sort(key=lambda p:cb.dumps(p[0])); return cb.Map(pairs)
 if isinstance(x,list): return [rename(v,old,new) for v in x]
 if isinstance(x,cb.Tag): return cb.Tag(x.number,rename(x.value,old,new))
 return x
class EphemeralFundingKey:
    """An Ed25519 signing key stored in a Linux anonymous memfd only."""
    DER_PREFIX = bytes.fromhex("302a300506032b6570032100")
    def __init__(self):
        import os
        self.os = os
        self.fd = os.memfd_create("vams-f05-funding-key", flags=0)
        made = subprocess.run(["openssl","genpkey","-algorithm","ED25519","-outform","DER","-out",f"/proc/self/fd/{self.fd}"],
                              stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,pass_fds=(self.fd,),check=False)
        if made.returncode:
            os.close(self.fd); self.fd=-1
            raise RuntimeError("ephemeral funding-key generation failed")
        os.lseek(self.fd,0,os.SEEK_SET)
        result=subprocess.run(["openssl","pkey","-inform","DER","-pubout","-outform","DER","-in",f"/proc/self/fd/{self.fd}"],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=(self.fd,),check=False)
        if result.returncode or len(result.stdout)!=44 or result.stdout[:12]!=self.DER_PREFIX:
            self.close(); raise RuntimeError("ephemeral funding public-key extraction failed")
        self.public_key=result.stdout[12:]
    @staticmethod
    def _message_fd(message):
        import os
        fd=os.memfd_create("vams-f05-funding-message",flags=0)
        if os.write(fd,message)!=len(message): os.close(fd); raise RuntimeError("short signing-message write")
        os.lseek(fd,0,os.SEEK_SET); return fd
    def sign(self,message):
        message_fd=self._message_fd(message)
        try:
            self.os.lseek(self.fd,0,self.os.SEEK_SET)
            signed=subprocess.run(["openssl","pkeyutl","-sign","-rawin","-inkey",f"/proc/self/fd/{self.fd}","-keyform","DER","-in",f"/proc/self/fd/{message_fd}"],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=(self.fd,message_fd),check=False)
            if signed.returncode or len(signed.stdout)!=64: raise RuntimeError("ephemeral funding signing failed")
            return signed.stdout
        finally: self.os.close(message_fd)
    def verify(self,message,signature):
        msgfd=self._message_fd(message); sigfd=self._message_fd(signature)
        pubfd=self.os.memfd_create("vams-f05-funding-public",flags=0)
        try:
            self.os.write(pubfd,self.DER_PREFIX+self.public_key); self.os.lseek(pubfd,0,self.os.SEEK_SET)
            checked=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pubfd}","-keyform","DER","-in",f"/proc/self/fd/{msgfd}","-sigfile",f"/proc/self/fd/{sigfd}"],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=(pubfd,msgfd,sigfd),check=False)
            if checked.returncode: raise ValueError("body-bound funding signature verification failed")
        finally:
            self.os.close(msgfd); self.os.close(sigfd); self.os.close(pubfd)
    def close(self):
        if getattr(self,"fd",-1)>=0: self.os.close(self.fd); self.fd=-1

def _fund_and_check(tx, resolved, inputs, policy):
    body,witnesses=tx[0],tx[1]; ephemeral=[]
    try:
        for output in resolved:
            key=EphemeralFundingKey()
            cb.map_set(output,0,b"\x60"+hashlib.blake2b(key.public_key,digest_size=28).digest())
            ephemeral.append(key)
        digest=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
        pairs=sorted(((key.public_key,key.sign(digest)) for key in ephemeral),key=lambda pair:pair[0])
        cb.map_set(witnesses,0,cb.Tag(258,[[pub,sig] for pub,sig in pairs]))
        raw_tx=cb.dumps(tx); check=cb.roundtrip(raw_tx)
        final=cb.map_get(check[1],0)
        if hashlib.blake2b(cb.dumps(check[0]),digest_size=32).digest()!=digest or len(final.value)!=len(ephemeral):
            raise ValueError("funding body hash or witness count mismatch")
        for pub,sig in final.value:
            signer=next((key for key in ephemeral if key.public_key==pub),None)
            if signer is None: raise ValueError("unrecognized funding witness")
            signer.verify(digest,sig)
        if cb.map_get(check[0],0).value!=inputs: raise ValueError("resolved input vector mismatch")
        mint,scripts=cb.map_get(check[0],9),cb.map_get(check[1],7)
        if [key for key,_ in mint.pairs]!=[policy["policy_id"]]: raise ValueError("mint does not use applied policy")
        if not isinstance(scripts,cb.Tag) or scripts.number!=258 or scripts.value!=[policy["code"]]: raise ValueError("V3 witness differs from applied program")
        if hashlib.blake2b(b"\x03"+scripts.value[0],digest_size=28).digest()!=policy["policy_id"]: raise ValueError("Mint/applied/V3 identity mismatch")
        input_coin=sum(cb.map_get(output,1) for output in resolved); output_coin=0; native={}
        for output in cb.map_get(check[0],1):
            value=cb.map_get(output,1)
            if isinstance(value,int): output_coin+=value; continue
            if not isinstance(value,list) or len(value)!=2: raise ValueError("unsupported output Value")
            output_coin+=value[0]
            for pid,assets in value[1].pairs:
                for name,quantity in assets.pairs: native[(pid,name)]=native.get((pid,name),0)+quantity
        minted={(pid,name):quantity for pid,assets in mint.pairs for name,quantity in assets.pairs}
        fee=cb.map_get(check[0],2)
        if input_coin!=output_coin+fee or (input_coin,output_coin,fee)!=(17_000_000,16_000_000,1_000_000): raise ValueError("ADA value conservation mismatch")
        if native!=minted or native!={(policy["policy_id"],h.AUTHORITY_NFT_NAME):1}: raise ValueError("native asset conservation mismatch")
        return raw_tx,{"body_hash":digest.hex(),"funding_signatures":len(pairs),"valid_body_bound_ephemeral_signatures":True,
            "private_keys_persisted":False,"ada_conservation":True,"native_asset_conservation":True}
    finally:
        for key in ephemeral: key.close()

def build_tx(src,rin,rout,policy,seed,keys,proofs,include_seed):
 tx=copy.deepcopy(cb.roundtrip(src)); ins=copy.deepcopy(cb.roundtrip(rin)); outs=copy.deepcopy(cb.roundtrip(rout))
 body,wit=tx[0],tx[1]; refs=cb.map_get(body,0)
 if not isinstance(refs,cb.Tag) or refs.number!=258: raise ValueError("expected input set")
 if include_seed: refs.value[0]=[seed[0],seed[1]]; ins[0]=[seed[0],seed[1]]
 if refs.value!=ins: raise ValueError("resolved inputs differ")
 outputs=cb.map_get(body,1)
 for output in outputs:
  cb.map_set(output,1,rename(cb.map_get(output,1),bytes.fromhex(ORIGINAL),policy["policy_id"]))
 state=h._authority_state(seed[0],seed[1],keys)
 cb.map_set(outputs[0],2,[1,cb.Tag(24,h.cbor(state))])
 redmap=cb.map_get(wit,5)
 if not isinstance(redmap,cb.Map) or len(redmap.pairs)!=1: raise ValueError("expected Mint[0] redeemer")
 red=cb.Tag(121,[[proof for proof in proofs]])
 prior_redeemer=cb.map_get(redmap,[1,0])
 if not isinstance(prior_redeemer,list) or len(prior_redeemer)!=2:
  raise ValueError("expected baseline Mint[0] redeemer plus execution units")
 cb.map_set(redmap,[1,0],[red,prior_redeemer[1]])
 mint=rename(cb.map_get(body,9),bytes.fromhex(ORIGINAL),policy["policy_id"]); cb.map_set(body,9,mint)
 scripts=cb.map_get(wit,7)
 if not isinstance(scripts,cb.Tag) or scripts.number!=258: raise ValueError("expected V3 witness set")
 cb.map_set(wit,7,cb.Tag(258,[policy["code"]]))
 raw,meta=_fund_and_check(tx,outs,ins,policy)
 meta["mint0_redeemer"]={"constructor_tag":121,"proof_count":len(proofs),
  "proof_signatures_hex":[proof.hex() for proof in proofs],
  "cbor_sha256":sha(cb.dumps(red))}
 return raw,cb.dumps(ins),cb.dumps(outs),meta

def make(cid,aiken):
 raw,rin,rout=tuple((FIX/n).read_bytes() for n in HASHES)
 if {n:sha((FIX/n).read_bytes()) for n in HASHES}!=HASHES: raise ValueError("frozen source CBOR hash mismatch")
 contract=json.loads(R41.read_text()); reg=json.loads(REG.read_text())
 if contract["owner_decisions"]["applied_parameter"]["choice"]!="C" or tuple(contract["owner_decisions"]["applied_parameter"]["case_ids"])!=CASES: raise ValueError("R4.1 choice/case IDs mismatch")
 if cid not in {c["id"] for c in reg["negative_cases"]}: raise ValueError("case not in original registry")
 signers=h._ephemeral_committee()
 if cid=="applied_keys_parameter": signers.append(h._EphemeralEd25519Key())
 try:
  keys=[s.public_key for s in signers[:5]]; params,changed,alt_seed=params_for(cid,keys,signers[5].public_key if len(signers)>5 else None)
  with tempfile.TemporaryDirectory(prefix="f05-applied-family-") as temp:
   root=Path(temp); negative_policy=compile_policy(aiken,params,root/"negative")
   if cid=="applied_genesis_parameter": positive_params,positive_keys,positive_seed=params,keys,alt_seed
   elif cid=="applied_keys_parameter": positive_params,positive_keys,positive_seed=params,changed,SEED
   else: positive_params,positive_keys,positive_seed={"genesis_ref":h._output_reference(*SEED),"initial_keys":h.list_data([h.byte_string(k) for k in keys])},keys,SEED
   positive_policy=compile_policy(aiken,positive_params,root/"positive")
   msg=h._canonical_pop_message(*positive_seed,positive_policy["state_credential"],positive_keys)
   pp=[s.sign(msg) for s in h._signers_for_keys(positive_keys,signers)]
   pos=build_tx(raw,rin,rout,positive_policy,positive_seed,positive_keys,pp,True)
   bad=cid in {"applied_keys_bad_count","applied_keys_bad_length","applied_keys_duplicate","applied_keys_unsorted"}
   datum_keys=changed if bad else keys
   nseed=alt_seed if cid=="applied_genesis_parameter" else SEED
   if cid in {"applied_keys_duplicate","applied_keys_unsorted"}:
    msg=h._canonical_pop_message(*nseed,negative_policy["state_credential"],datum_keys,require_canonical_keys=False)
    by={s.public_key:s for s in signers}; np=[by[k].sign(msg) for k in datum_keys]
   elif cid=="applied_keys_parameter":
    # Datum intentionally retains base keys, but PoPs bind to the alternate
    # policy keys so the named state-key binding is the sole feasible mismatch.
    msg=h._canonical_pop_message(*nseed,negative_policy["state_credential"],changed)
    np=[s.sign(msg) for s in h._signers_for_keys(changed,signers)]
   elif cid in {"applied_keys_bad_count","applied_keys_bad_length"}:
    # Matching keys and proofs are impossible for malformed parameters: the
    # policy's PoP verifier requires exactly five 32-byte Ed25519 public keys.
    msg=h._canonical_pop_message(*nseed,negative_policy["state_credential"],keys)
    np=[s.sign(msg) for s in signers[:5]]
   else:
    msg=h._canonical_pop_message(*nseed,negative_policy["state_credential"],keys)
    np=[s.sign(msg) for s in h._signers_for_keys(keys,signers)]
   neg=build_tx(raw,rin,rout,negative_policy,nseed,datum_keys,np,cid!="applied_genesis_parameter")
   variants={"negative":(neg,negative_policy,params),"positive-control":(pos,positive_policy,positive_params)}; mutant_info=None
   if cid in {"applied_keys_duplicate","applied_keys_unsorted"}:
    mutation="remove_key_uniqueness_order_guard" if cid=="applied_keys_duplicate" else "remove_key_order_guard"
    mp=compile_policy(aiken,params,root/"mutant",mutation); mutant=build_tx(raw,rin,rout,mp,nseed,datum_keys,np,True)
    variants["one-guard-mutant-control"]=(mutant,mp,params)
    mutant_info={"guard":mutation,"applied_policy_id":mp["policy_id"].hex(),"tx_sha256":sha(mutant[0]),"status":"not executed"}
   dest=OUT/cid; dest.mkdir(parents=True,exist_ok=False); files={}
   policy_applications={}
   for label,(fixture,policy,policy_params) in variants.items():
    tx,inputs,outputs,meta=fixture
    for suffix,data in (("tx.cbor",tx),("raw_inputs.cbor",inputs),("raw_outputs.cbor",outputs),("applied-policy.cbor",policy["code"])):
     name=label+"."+suffix;(dest/name).write_bytes(data);files[name]={"sha256":sha(data),"bytes":len(data)}
    seed_data=h.cbor(policy_params["genesis_ref"])
    keys_data=h.cbor(policy_params["initial_keys"])
    seed_name=label+".genesis_ref.cbor"; keys_name=label+".initial_keys.cbor"
    for name,data in ((seed_name,seed_data),(keys_name,keys_data)):
     (dest/name).write_bytes(data);files[name]={"sha256":sha(data),"bytes":len(data)}
    seed_fields=policy_params["genesis_ref"]["fields"]
    seed_hash=seed_fields[0]["bytes"];seed_index=seed_fields[1]["int"]
    key_values=[item["bytes"] for item in policy_params["initial_keys"]["list"]]
    key_bytes=[bytes.fromhex(value) for value in key_values]
    policy_applications[label]={"applied_policy_id":policy["policy_id"].hex(),"program_sha256":sha(policy["code"]),
     "parameter_cbor":{"genesis_ref":{"file":seed_name,"sha256":sha(seed_data),"bytes":len(seed_data),"value":{"tx_hash":seed_hash,"output_index":seed_index}},
      "initial_keys":{"file":keys_name,"sha256":sha(keys_data),"bytes":len(keys_data),"count":len(key_values),"values_hex":key_values,
       "key_byte_lengths":[len(k) for k in key_bytes],"strictly_increasing":all(key_bytes[i]<key_bytes[i+1] for i in range(len(key_bytes)-1)),
       "unique":len(set(key_bytes))==len(key_bytes)}}}
    files[label+".validation"]=meta
   summary={"schema_version":"f05-2a-applied-parameter-family-r5","status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit",
    "generator_invocation":{"argv":list(sys.argv),"exit_code":0},
    "decision":"R4.1 applied-parameter C","case_id":cid,"original_case_id_preserved":True,
    "scope":"synthetic alternate applied policy; no original-policy, ledger-admission, or live-network credit",
    "entrypoint":"f05_authority_policy.f05_authority_policy.mint / Mint[0]","original_policy_id":ORIGINAL,
    "alternate_applied_policy_id":negative_policy["policy_id"].hex(),"program_sha256":sha(negative_policy["code"]),
    "parameter_sha256":sha(h.cbor(params["genesis_ref"])+h.cbor(params["initial_keys"])),
    "policy_applications":policy_applications,
    "negative":{"tx_sha256":sha(neg[0]),"inputs_sha256":sha(neg[1]),"outputs_sha256":sha(neg[2]),"status":"PENDING",
     "datum_seed_ref":{"tx_hash":nseed[0].hex(),"output_index":nseed[1]},
     "datum_state":{"schema_version":3,"epoch":0,"threshold":3,"status":0,"pending_kind":0,
      "keys_hex":[key.hex() for key in datum_keys],
      "plutus_data_sha256":sha(h.cbor(h._authority_state(nseed[0],nseed[1],datum_keys)))},
     "alternate_policy_seed_ref":{"tx_hash":alt_seed[0].hex(),"output_index":alt_seed[1]},
     "alternate_policy_seed_present_in_body":cid!="applied_genesis_parameter",
     "datum_ordered_keys_sha256":sha(h.cbor(h.list_data([h.byte_string(k) for k in datum_keys]))),
     "applied_parameter_keys_sha256":sha(h.cbor(params["initial_keys"])),
     "proof_of_possession":{"status":"infeasible-for-malformed-parameter" if cid in {"applied_keys_bad_count","applied_keys_bad_length"} else "valid-signatures-bound-to-applied-parameter",
      "reason":"policy requires exactly five 32-byte keys/proofs; six-key or 31-byte-key parameter cannot have verifier-accepted PoPs" if cid in {"applied_keys_bad_count","applied_keys_bad_length"} else None}},
    "positive_control":{"tx_sha256":sha(pos[0]),"inputs_sha256":sha(pos[1]),"outputs_sha256":sha(pos[2]),
      "applied_policy_id":positive_policy["policy_id"].hex(),"status":"not executed"},
    "one_guard_mutant_control":mutant_info,
    "assertion":next(c for c in reg["negative_cases"] if c["id"]==cid),
    "first_failure_attribution":"not established; PoPs cannot be verifier-valid for this malformed parameter shape, so do not claim isolated guard attribution; remains PENDING" if cid in {"applied_keys_bad_count","applied_keys_bad_length"} else "execution/reviewer attribution pending",
    "conservation":{"inputs_lovelace":17000000,"authority_output_lovelace":10000000,"sponsor_change_output_lovelace":6000000,"fee_lovelace":1000000,"collateral":{"present":False,"lovelace":0},"native_asset":"one authority singleton minted and output under this case applied policy"},
    "credit":{"negative_case":None,"original_policy":False,"ledger_admission":False,"live_network":False},"artifacts":files}
   (dest/"FIXTURE-MANIFEST.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
   (dest/"SHA256SUMS").write_text("".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(dest.iterdir()) if p.is_file() and p.name!="SHA256SUMS"))
   return summary
 finally:
  for s in signers:s.close()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--case-id",choices=CASES,required=True);p.add_argument("--aiken",type=Path,required=True);a=p.parse_args()
 aiken=a.aiken.resolve(strict=True);v=subprocess.run([str(aiken),"--version"],capture_output=True,text=True,timeout=20)
 if v.returncode or v.stdout.strip()!="aiken v1.1.21+42babe5" or sha(aiken.read_bytes())!="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79": raise SystemExit("refusing non-pinned Aiken 1.1.21")
 if (OUT/a.case_id).exists():raise SystemExit("fixture directory exists; preserve and create a new revision")
 m=make(a.case_id,aiken);print(json.dumps({"case_id":a.case_id,"status":m["status"],"alternate_policy_id":m["alternate_applied_policy_id"],"artifact_dir":str(OUT/a.case_id)},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
