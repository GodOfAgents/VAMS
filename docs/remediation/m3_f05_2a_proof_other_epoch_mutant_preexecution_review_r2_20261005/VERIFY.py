import pathlib,hashlib,json,subprocess,tempfile,shutil,importlib.util,sys
R=pathlib.Path("/home/GodOfAgents/code/VAMS-testnet")
P=R/"docs/remediation/m3_f05_2a_proof_other_epoch_mutant_r1_20261005/r2_signature_for_other_epoch"
O=R/"docs/remediation/m3_f05_2a_proof_other_epoch_mutant_preexecution_review_r2_20261005"
A=pathlib.Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken")
sha=lambda b:hashlib.sha256(b).hexdigest()
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
f=load("ind_epoch_fam",R/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
h,cb=f.h,f.cb
M=json.loads((P/"FIXTURE-MANIFEST.json").read_text())
assert M["source_mutation"]["line"]==122
for d in [P,P.parent]:
 for line in (d/"SHA256SUMS").read_text().splitlines():
  digest,name=line.split("  ",1);assert sha((d/name).read_bytes())==digest,(d,name)
for name,rec in M["artifacts"].items():
 b=(P/name).read_bytes();assert sha(b)==rec["sha256"] and len(b)==rec["bytes"],name
FM=json.loads((P.parent/"FAMILY-MANIFEST.json").read_text())
for name,rec in FM["files"].items():
 b=(P.parent/name).read_bytes();assert sha(b)==rec["sha256"] and len(b)==rec["bytes"],name
keys=[bytes.fromhex(k) for k in M["applied_parameters"]["committee_public_keys_hex"]]
seed=M["applied_parameters"]["seed_ref"];seed=(bytes.fromhex(seed["tx_hash"]),seed["output_index"])
params={"genesis_ref":h._output_reference(*seed),"initial_keys":h.list_data([h.byte_string(k) for k in keys])}
assert h.cbor(params["genesis_ref"])==(P/"mutant.genesis_ref.cbor").read_bytes()
assert h.cbor(params["initial_keys"])==(P/"mutant.initial_keys.cbor").read_bytes()
assert sha(h.cbor(params["genesis_ref"])+h.cbor(params["initial_keys"]))==M["applied_parameters"]["parameter_cbor_sha256"]
before=(R/"cardano/lib/vams/f05_authority.ak").read_bytes()
assert sha(before)==M["source_mutation"]["source_before_sha256"]
old=b"                        bytearray.from_int_big_endian(0, 8),"
new=b"                        bytearray.from_int_big_endian(1, 8),"
assert before.count(old)==1
after=before.replace(old,new,1);assert sha(after)==M["source_mutation"]["source_mutant_sha256"]
assert before.decode().splitlines()[121].strip()=="bytearray.from_int_big_endian(0, 8),"
assert sha(A.read_bytes())==M["toolchain"]["aiken_binary_sha256"]
normal_id=bytes.fromhex("704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad")
mut_id=bytes.fromhex("6f2cfb8a849311c6e6076b466daafe77ae5a95de9b50c62caecfafa4")
results={}
with tempfile.TemporaryDirectory(prefix="epoch-independent-r2-") as td:
 T=pathlib.Path(td)
 normal=h._compile(R/"cardano",A,T/"normal",params)
 assert normal["code"]==(P/"reviewed-negative.applied-policy.cbor").read_bytes()
 assert normal["policy_id"]==normal_id
 staged=T/"source";shutil.copytree(R/"cardano",staged)
 patch=subprocess.run(["patch","-p2","--input",str(P/"SOURCE-DIFF.patch")],cwd=staged,capture_output=True)
 assert patch.returncode==0,patch.stderr
 assert (staged/"lib/vams/f05_authority.ak").read_bytes()==after
 mutant=h._compile(staged,A,T/"mutant",params)
 assert mutant["code"]==(P/"mutant.applied-policy.cbor").read_bytes()
 assert mutant["policy_id"]==mut_id
 assert mutant["state_credential"]==normal["state_credential"]==bytes.fromhex(M["applied_parameters"]["actual_state_validator_hash"])
 pm=(P/"positive-control.proof-message.bin").read_bytes()
 nm=(P/"reviewed-negative.proof-message.bin").read_bytes()
 assert len(pm)==len(nm)==279 and pm[:271]==nm[:271] and pm[271:]==bytes(8) and nm[271:]==(1).to_bytes(8,"big")
 assert nm==(P/"mutant.proof-message.bin").read_bytes()
 assert pm==h._canonical_pop_message(*seed,normal["state_credential"],keys)
 verified_proofs=verified_funding=0
 def verify(pub,sig,msg):
  (T/"pub.der").write_bytes(bytes.fromhex("302a300506032b6570032100")+pub)
  (T/"sig.bin").write_bytes(sig);(T/"msg.bin").write_bytes(msg)
  v=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",str(T/"pub.der"),"-keyform","DER","-in",str(T/"msg.bin"),"-sigfile",str(T/"sig.bin")],capture_output=True)
  assert v.returncode==0,v.stderr
 for label,pid,message in [("positive-control",normal_id,pm),("reviewed-negative",normal_id,nm),("mutant",mut_id,nm)]:
  tx=cb.roundtrip((P/(label+".tx.cbor")).read_bytes());body,wit=tx[0],tx[1]
  inputs=cb.roundtrip((P/(label+".raw_inputs.cbor")).read_bytes())
  resolved=cb.roundtrip((P/(label+".raw_outputs.cbor")).read_bytes())
  assert cb.map_get(body,0).value==inputs
  mint=cb.map_get(body,9);script=cb.map_get(wit,7)
  assert [k for k,v in mint.pairs]==[pid] and script.number==258 and len(script.value)==1
  assert script.value[0]==(P/(label+".applied-policy.cbor")).read_bytes()
  assert hashlib.blake2b(b"\x03"+script.value[0],digest_size=28).digest()==pid
  red=cb.map_get(cb.map_get(wit,5),[1,0])[0]
  assert red.number==121 and len(red.value[0])==5
  for pub,sig in zip(keys,red.value[0]):verify(pub,sig,message);verified_proofs+=1
  digest=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
  fund=cb.map_get(wit,0);assert fund.number==258 and len(fund.value)==2
  pubhashes=set()
  for pub,sig in fund.value:verify(pub,sig,digest);verified_funding+=1;pubhashes.add(hashlib.blake2b(pub,digest_size=28).digest())
  assert all(cb.map_get(o,0)[0]==96 and cb.map_get(o,0)[1:] in pubhashes for o in resolved)
  inp=sum(cb.map_get(o,1) for o in resolved);outcoin=0;assets={}
  for o in cb.map_get(body,1):
   v=cb.map_get(o,1)
   if isinstance(v,int):outcoin+=v
   else:
    outcoin+=v[0]
    for p,aa in v[1].pairs:
     for name,q in aa.pairs:assets[(p,name)]=assets.get((p,name),0)+q
  assert (inp,outcoin,cb.map_get(body,2))==(17000000,16000000,1000000)
  assert assets=={(p,name):q for p,aa in mint.pairs for name,q in aa.pairs}=={(pid,h.AUTHORITY_NFT_NAME):1}
  assert all(k not in (13,16,17) for k,v in body.pairs)
  assert cb.map_get(cb.map_get(body,1)[0],0)[1:]==normal["state_credential"]
  results[label]={"tx_sha256":sha((P/(label+".tx.cbor")).read_bytes()),"policy_id":pid.hex(),"body_hash":digest.hex(),"proofs":5,"funding":2}
 assert cb.dumps(cb.map_get(cb.map_get(cb.roundtrip((P/"mutant.tx.cbor").read_bytes())[1],5),[1,0])[0])==cb.dumps(cb.map_get(cb.map_get(cb.roundtrip((P/"reviewed-negative.tx.cbor").read_bytes())[1],5),[1,0])[0])
 assert (P/"mutant.raw_inputs.cbor").read_bytes()==(P/"reviewed-negative.raw_inputs.cbor").read_bytes()
 for name,p in [("prior-negative-run.json",R/"docs/remediation/m3_f05_2a_proof_other_epoch_negative_attempt_r1_20261005/RUN.json"),("prior-positive-run.json",R/"docs/remediation/m3_f05_2a_proof_other_epoch_positive_attempt_r1_20261005/RUN.json"),("prior-negative-review.md",R/"docs/remediation/m3_f05_2a_proof_other_epoch_negative_review_r1_20261005/INDEPENDENT-REVIEW.md"),("prior-positive-review.md",R/"docs/remediation/m3_f05_2a_proof_other_epoch_positive_review_r1_20261005/INDEPENDENT-REVIEW.md"),("prior-preexecution-review.md",R/"docs/remediation/m3_f05_2a_proof_domain_family_r3_independent_review_r1_20261005/INDEPENDENT-REVIEW.md")]:
  assert (P/name).read_bytes()==p.read_bytes()
assert M["case_id"]=="r2_signature_for_other_epoch" and M["assertion"]=="sign_tuple_with_nonzero_epoch"
assert all(p.suffix in [".md",".json",".cbor",".bin",".patch"] or p.name=="SHA256SUMS" for p in P.iterdir())
assert not any(b"PRIVATE KEY" in p.read_bytes() for p in P.iterdir())
print(json.dumps({"outcome":"PASS","proof_signatures_verified":verified_proofs,"body_bound_funding_verified":verified_funding,"results":results,"package_checksums_sha256":sha((P.parent/"SHA256SUMS").read_bytes())},indent=2))
