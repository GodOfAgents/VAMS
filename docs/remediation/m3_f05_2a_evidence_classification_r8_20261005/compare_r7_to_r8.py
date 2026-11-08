from pathlib import Path
import copy,hashlib,json
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;D=ROOT/"docs/remediation";CID="r2_signature_for_other_validator_hash"
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=load(D/"m3_f05_2a_evidence_classification_r7_20261005/CASE-STATUS.json");b=load(HERE/"CASE-STATUS.json");L=load(HERE/"EVIDENCE-LINKS.json")
assert a["negative_cases"]["pending"].count(CID)==1 and not any(x.get("id")==CID for x in a["negative_cases"]["pass"])
rows=[x for x in b["negative_cases"]["pass"] if x.get("id")==CID];assert len(rows)==1
r=rows[0];assert CID not in b["negative_cases"]["pending"] and r["classification"]=="transaction_simulator"
assert r["original_assertion"]=={"id":CID,"mutation":"sign_tuple_with_another_state_validator_hash"} and r["evidence_sha256"]==sha(ROOT/r["evidence"])
s=r["evidence_scope"];assert s["decision"]=="R4.1 proof-domain B" and s["evidence_category"]=="synthetic_parameter_bound_tx_sim"
assert all(s[k] is False for k in ["mutation_suite","original_policy","ledger_admission","pre_prod","live_network","deployment_readiness"])
for x in L["files"]:
 p=ROOT/x["path"];assert p.is_file() and sha(p)==x["sha256"],"hash mismatch "+x["path"]
e=L["case_evidence"]
for k in ["positive_run","positive_review","negative_run","negative_review","negative_preexecution_review","mutant_run","mutant_preexecution_review","normal_fixture_family","mutant_fixture_family"]:assert sha(ROOT/e[k]["path"])==e[k]["sha256"]
def rr(k):return load(ROOT/e[k]["path"])["attempt"]["runner_result"]
assert rr("positive_run")["simulator_result"]=={"stage":"script_accepted","target_script_invoked":True}
assert rr("negative_run")["simulator_result"]=={"stage":"compiled_evaluation","target_script_invoked":True}
assert rr("mutant_run")["simulator_result"]=={"stage":"script_accepted","target_script_invoked":True}
assert rr("positive_run")["target_mint_binding"]["expected_policy_id"]==s["normal_applied_policy_id"]
assert rr("negative_run")["target_mint_binding"]["expected_policy_id"]==s["normal_applied_policy_id"]
assert rr("mutant_run")["target_mint_binding"]["expected_policy_id"]==s["one_expression_mutant_policy_id"]
n=copy.deepcopy(b);n["schema_version"]=a["schema_version"];n["negative_cases"]["pass"]=[x for x in n["negative_cases"]["pass"] if x.get("id")!=CID]
n["negative_cases"]["pending"].insert(a["negative_cases"]["pending"].index(CID),CID)
n["negative_cases"]["summary"]["pass"]-=1;n["negative_cases"]["summary"]["pending"]+=1
n["negative_cases"]["classification"]["transaction_simulator"]["pass"]-=1;n["negative_cases"]["classification"]["transaction_simulator"]["pending"]+=1
assert n==a,"unexpected delta beyond target row/counts"
assert b["negative_cases"]["summary"]=={"pass":52,"pending":3,"failed":0}
assert b["negative_cases"]["classification"]["transaction_simulator"]=={"total":51,"pass":48,"pending":3,"failed":0}
assert b["negative_cases"]["classification"]["context_only"]==a["negative_cases"]["classification"]["context_only"] and b["negative_cases"]["classification"]["routing_only"]==a["negative_cases"]["classification"]["routing_only"]
assert b["mutations"]==a["mutations"]
print(json.dumps({"result":"PASS","target":CID,"delta":"PENDING -> PASS","case_counts":{"pass":52,"pending":3,"failed":0},"transaction_simulator":{"total":51,"pass":48,"pending":3,"failed":0},"mutation_rows_unchanged":True,"verified_evidence_hashes":len(L["files"]),"credit_scope":"synthetic alternate-applied-policy only"},indent=2))
