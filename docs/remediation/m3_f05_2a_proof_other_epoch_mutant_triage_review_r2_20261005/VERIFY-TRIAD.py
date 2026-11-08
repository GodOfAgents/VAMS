from pathlib import Path
import hashlib,json,importlib.util,sys
R=Path("/home/GodOfAgents/code/VAMS-testnet");P=R/"docs/remediation/m3_f05_2a_proof_other_epoch_mutant_r1_20261005/r2_signature_for_other_epoch"
sha=lambda b:hashlib.sha256(b).hexdigest()
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
f=load("triad_fam",R/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py");cb=f.cb
normal=bytes.fromhex("704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad");mut=bytes.fromhex("6f2cfb8a849311c6e6076b466daafe77ae5a95de9b50c62caecfafa4")
n=cb.roundtrip((P/"reviewed-negative.tx.cbor").read_bytes());m=cb.roundtrip((P/"mutant.tx.cbor").read_bytes());p=cb.roundtrip((P/"positive-control.tx.cbor").read_bytes())
assert cb.dumps(f.rename(n[0],normal,mut))==cb.dumps(m[0])
for key,v in n[1].pairs:
 if key not in (0,7):assert cb.dumps(v)==cb.dumps(cb.map_get(m[1],key))
nr=cb.roundtrip((P/"reviewed-negative.raw_outputs.cbor").read_bytes());mr=cb.roundtrip((P/"mutant.raw_outputs.cbor").read_bytes())
assert len(nr)==len(mr)
for a,b in zip(nr,mr):
 assert [k for k,v in a.pairs]==[k for k,v in b.pairs]
 for k,v in a.pairs:
  if k!=0:assert cb.dumps(v)==cb.dumps(cb.map_get(b,k))
assert cb.dumps(n[0])==cb.dumps(p[0])
results={}
for label,filelabel,child,stage,pid in [("positive","positive-control",0,"script_accepted",normal),("negative","reviewed-negative",1,"compiled_evaluation",normal),("mutant","mutant",0,"script_accepted",mut)]:
 d=R/("docs/remediation/m3_f05_2a_proof_other_epoch_"+label+"_attempt_r1_20261005")
 for line in (d/"SHA256SUMS").read_text().splitlines():
  digest,name=line.split("  ",1);q=d/name if (d/name).exists() else R/name;assert q.resolve().is_relative_to(R);assert sha(q.read_bytes())==digest
 run=json.loads((d/"RUN.json").read_text());a=run["attempt"];rr=a["runner_result"];binding=rr["target_mint_binding"]
 assert run["case_id"]=="r2_signature_for_other_epoch"
 assert a["wrapper_exit_code"]==rr["wrapper_exit_code"]==0
 assert rr["simulator_child_exit"]==child and rr["simulator_result"]=={"stage":stage,"target_script_invoked":True}
 assert binding=={"compiled_script_hash":pid.hex(),"expected_policy_id":pid.hex(),"policy_ids":[pid.hex()]}
 assert rr["cleanup"]=={"child_reaped":True,"process_group_empty":True,"snapshot_descriptors_closed":True,"status":"clean"}
 for prop,suffix in [("transaction","tx.cbor"),("raw_inputs","raw_inputs.cbor"),("raw_outputs","raw_outputs.cbor")]:
  b=(P/(filelabel+"."+suffix)).read_bytes()
  assert sha(b)==rr["submitted_sha256"][prop] and len(b)==rr["submitted_size_bytes"][prop]
 assert sha((R/"scripts/remediation/f05_2a_tx_sim_runner_r3.py").read_bytes())==a["runner_sha256"]=="3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c"
 assert sha(Path(a["argv"][a["argv"].index("--aiken")+1]).read_bytes())==a["aiken_sha256"]
 fx=run["fixture"]
 assert fx["transaction_sha256"]==rr["submitted_sha256"]["transaction"]
 assert fx["applied_policy_id"]==pid.hex()
 results[label]={"run_sha256":sha((d/"RUN.json").read_bytes()),"child_exit":child,"stage":stage,"policy_id":pid.hex()}
md=R/"docs/remediation/m3_f05_2a_proof_other_epoch_mutant_attempt_r1_20261005/RUN.json"
mr=json.loads(md.read_text());fx=mr["fixture"]
for field,path in [("preexecution_review_sha256","m3_f05_2a_proof_other_epoch_mutant_preexecution_review_r1_20261005/INDEPENDENT-REVIEW.md"),("prior_negative_run_sha256","m3_f05_2a_proof_other_epoch_negative_attempt_r1_20261005/RUN.json"),("prior_positive_review_sha256","m3_f05_2a_proof_other_epoch_positive_review_r1_20261005/INDEPENDENT-REVIEW.md")]:
 assert fx[field]==sha((R/"docs/remediation"/path).read_bytes())
for dname in ["m3_f05_2a_proof_other_epoch_mutant_preexecution_review_r1_20261005","m3_f05_2a_proof_other_epoch_mutant_preexecution_review_r2_20261005","m3_f05_2a_proof_other_epoch_positive_review_r1_20261005","m3_f05_2a_proof_other_epoch_negative_review_r1_20261005"]:
 d=R/"docs/remediation"/dname
 for line in (d/"SHA256SUMS").read_text().splitlines():
  digest,name=line.split("  ",1);q=d/name if (d/name).exists() else R/name;assert q.resolve().is_relative_to(R);assert sha(q.read_bytes())==digest
row=next(x for x in json.loads((R/"docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json").read_text())["case_overrides"] if x["id"]=="r2_signature_for_other_epoch")
assert row["amended_contract"]["decision"]=="B" and row["amended_contract"]["changed_condition"]=="ephemeral committee signs epoch 1; applied message binds epoch 0"
print(json.dumps({"outcome":"PASS synthetic transaction_simulator epoch attribution","results":results,"normal_mutant_body_delta":"policy id substitution only","normal_mutant_other_witnesses":"identical except funding and V3","resolved_input_delta":"funding public-key addresses only"},indent=2))
