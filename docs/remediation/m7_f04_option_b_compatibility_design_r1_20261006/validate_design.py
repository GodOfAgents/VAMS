#!/usr/bin/env python3
"""Structural-only F04 Option B artifact validation; no execution credit."""
from pathlib import Path
import hashlib,json,re
D=Path(__file__).resolve().parent
ROOT=D.parents[2]
def j(n): return json.loads((D/n).read_text(encoding="utf-8"))
def check(v,m):
 if not v: raise SystemExit("FAIL: "+m)
a=j("ANCHOR-CONTRACT.json"); ac=j("ANCHOR-CASES.json"); c=j("CONSUMER-CONTRACT.json"); gc=j("GENESIS-CASES.json"); m=j("ACCEPTANCE-MATRIX.json"); q=j("QUALIFICATION-CONTRACT.json")
check(a["owner_option"]=="B_PER_BOOTSTRAP_MULTIPLE_CANDIDATE_ANCHORS","Option B")
check(a["global_did_uniqueness"] is False and a["guarantees"]["different_bootstrap_same_did_allowed"] is True,"no global uniqueness")
check(a["guarantees"]["multiple_anchor_seeds_per_bootstrap_allowed"] is True,"multiple anchors")
check("reviewed/pinned VAMS" in a["guarantees"]["one_ledger_admitted_registration_per_bootstrap"],"route-scoped guarantee")
check(a["registration"]["matching_anchor_references"]==1 and a["registration"]["bootstrap_consumed_exactly_once"],"single bootstrap registration binding")
check([x["role"] for x in a["script_graph"]]==["S0","P0","R","N"],"acyclic graph order")
roles={x["role"]:x for x in a["script_graph"]}
edges={role:[dep for dep in spec["parameters"] if dep in roles] for role,spec in roles.items()}
check(set(roles)=={"S0","P0","R","N"},"script graph nodes")
done=set()
def visit(x,path):
 check(x not in path,"cycle")
 if x in done:return
 for y in edges[x]:visit(y,path|{x})
 done.add(x)
for x in edges:visit(x,set())
check(edges=={"S0":[],"P0":["S0"],"R":["S0","P0"],"N":["R","S0","P0"]},"required applied dependency graph")
f=a["datum"]["fields"]
check([x["index"] for x in f]==list(range(17)),"anchor datum arity/index")
check(a["bounds"]["max_selected_authorization_signers"]==8 and "unrelated funding signatories" in a["bounds"]["selected_authorization_signer_scope"],"selected signer bound")
check(a["issuance"]["guardian_quorum"]==3 and a["issuance"]["mint_quantity"]==1 and a["issuance"]["all_burns_reject"],"issuance bounds")
check(a["registration"]["registry_mint_rejects"] and "not global uniqueness" in a["registration"]["matching_reference_rule_scope"],"registration boundary")
for cid in ("A11","A12","A19"):
 x=next(x for x in ac["cases"] if x["id"]==cid)
 check(not x["positive_control_required"] and x["related_positive_control_required"],"reject-only control exception "+cid)
x=next(x for x in ac["cases"] if x["id"]=="A19")
check("V2" in x["condition"] and "V1" in x["condition"],"new R only; V1 preserved")
for cid,want in (("A05",{"compiled_v3","pure_helper","invalid_context"}),("A06",{"compiled_v3","invalid_context","ledger_admission"})):
 x=next(x for x in ac["cases"] if x["id"]==cid)
 check({s["evidence_scope"] for s in x["subcases"]}==want,"evidence split "+cid)
check(c["constructor_tags"]=={"AgentDatumV1":0,"AgentDatumV2":1,"PreGenesisV2":2},"explicit schema tags")
check(c["v1_handling"]["v2_register"]=="REJECT" and "separate owner-reviewed" in c["v1_handling"]["migration"],"V1 explicit no migration")
check(c["agent_v2"]["genesis"]["status"]==0 and "reject2" in c["agent_v2"]["integer_bounds"],"V2 status")
check(c["possession"]["registration"].startswith("founding owner, initial controller and all5"),"five-guardian PoP")
check("DENY" in c["freshness"]["resolution"] and "current ledger state" in c["freshness"]["resolution"],"fresh authority failclosed")
check("failclosed" in c["cross_chain_binding"]["until_gate_passes"],"consumer activation gate")
av=ac["cases"]; check(len(av)==26 and len(gc["cases"])==39,"source case counts")
check(len(m["cases"])==113 and m["case_count"]==113,"matrix case count")
ids=[x["id"] for x in m["cases"]]; check(len(ids)==len(set(ids)),"unique case IDs")
check(all(x.get("execution")=="PENDING" for x in m["cases"]),"matrix pending")
check(set(f"F04-R{i:02d}" for i in range(1,32))<=set(ids),"31 recovery IDs retained")
old=ROOT/"docs/remediation/m7_f04_owner_recovery_design_r1_20261004/TEST-MATRIX.md"; txt=old.read_text(encoding="utf-8")
check(m["historical_matrix_sha256"]==hashlib.sha256(old.read_bytes()).hexdigest(),"historical matrix binding")
source_matches=list(re.finditer(r"(?ms)^(\d+)\. (.*?)(?=^\d+\. |\Z)",txt))
check(len(source_matches)==31,"historical case count")
source_assertions={int(x[1]):x[2].rstrip() for x in source_matches}
for x in m["cases"]:
 if x["id"].startswith("F04-R"):
  n=x["original_case_number"]
  check(x["original_assertion"]==source_assertions[n],"original assertion preserved "+x["id"])
  check(x["original_assertion_sha256"]==hashlib.sha256(source_assertions[n].encode()).hexdigest(),"source-bound assertion hash "+x["id"])
for rel,digest in c["source_sha256"].items():
 check(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest,"current source binding "+rel)
vec=a["golden_vector"]
check(hashlib.blake2b(bytes.fromhex(vec["identity_preimage_hex"]),digest_size=32).hexdigest()==vec["identity_asset_name"],"identity vector")
check(hashlib.blake2b(bytes.fromhex(vec["anchor_preimage_hex"]),digest_size=32).hexdigest()==vec["anchor_asset_name"],"anchor vector")
check(q["budget_acceptance"]["status"]=="PENDING_NO_NUMERIC_BUDGET_OR_COMPILED_CREDIT","budget pending")
check(q["execution"]=="PENDING" and q["readiness"]=="NOT READY","execution/readiness")
check({"deployment","Deposit","Slash","ExecuteIntent"}<=set(q["disabled"]),"activation gates")
check(all(x["execution_status"]=="PENDING_NOT_RUN" for x in gc["cases"]),"genesis cases pending")
print(json.dumps({"result":"PASS_STRUCTURAL_ONLY","anchor_top_level":26,"anchor_subcases":7,"genesis_consumer":39,"preserved_recovery":31,"integration":10,"matrix":113,"compiled":0,"ledger":0,"live":0},sort_keys=True))
