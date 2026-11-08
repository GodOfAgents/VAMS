from pathlib import Path
import json,hashlib,copy
R=Path("/home/GodOfAgents/code/VAMS-testnet");D=R/"docs/remediation"
A=D/"m3_f05_2a_evidence_classification_r8_20261005";B=D/"m3_f05_2a_evidence_classification_r9_20261005"
sha=lambda b:hashlib.sha256(b).hexdigest()
a=json.loads((A/"CASE-STATUS.json").read_text());b=json.loads((B/"CASE-STATUS.json").read_text())
cid="r2_signature_for_other_epoch"
assert cid in a["negative_cases"]["pending"] and cid not in b["negative_cases"]["pending"]
row=next(x for x in b["negative_cases"]["pass"] if x["id"]==cid)
norm=copy.deepcopy(b);norm["schema_version"]=a["schema_version"]
norm["negative_cases"]["pass"]=[x for x in norm["negative_cases"]["pass"] if x["id"]!=cid]
norm["negative_cases"]["pending"]=a["negative_cases"]["pending"]
for name in ["summary","classification"]:
 norm["negative_cases"][name]=a["negative_cases"][name]
assert norm==a
assert b["mutations"]==a["mutations"]
nc=b["negative_cases"];assert len(nc["pass"])==53 and len(nc["pending"])==2 and len(nc["failed"])==0 and nc["total"]==55
assert nc["pending"]==["applied_keys_bad_count","applied_keys_bad_length"]
assert nc["summary"]=={"pass":53,"pending":2,"failed":0}
assert nc["classification"]["transaction_simulator"]=={"total":51,"pass":49,"pending":2,"failed":0}
assert len(set(x["id"] for x in nc["pass"]))==53
assert row["classification"]=="transaction_simulator"
for k in ["mutation_suite","original_policy","ledger_admission","pre_prod","live_network","deployment_readiness"]:assert row["evidence_scope"][k] is False
assert row["original_assertion"]=={"id":cid,"mutation":"sign_tuple_with_nonzero_epoch"}
reg=json.loads((D/"m3_f05_2a/authority_bootstrap_public_fixtures.json").read_text())
assert row["original_assertion"]==next(x for x in reg["negative_cases"] if x["id"]==cid)
al=json.loads((A/"EVIDENCE-LINKS.json").read_text());bl=json.loads((B/"EVIDENCE-LINKS.json").read_text())
assert bl["case_evidence"]==al["case_evidence"]
by={x["path"]:x for x in bl["files"]};assert len(by)==len(bl["files"])
for x in al["files"]:assert by[x["path"]]==x
checked=0;manifests=0
def checkrec(x):
 global checked
 if isinstance(x,dict):
  if "path" in x and "sha256" in x:
   q=R/x["path"] if not Path(x["path"]).is_absolute() else Path(x["path"])
   assert q.resolve().is_relative_to(R);assert sha(q.read_bytes())==x["sha256"],q;checked+=1
  for v in x.values():checkrec(v)
 elif isinstance(x,list):
  for v in x:checkrec(v)
checkrec(bl);checkrec(row)
assert sha((R/row["evidence"]).read_bytes())==row["evidence_sha256"]
for line in (B/"SHA256SUMS").read_text().splitlines():
 digest,name=line.split("  ",1);q=B/name if (B/name).exists() else R/name;assert sha(q.read_bytes())==digest
for rec in bl["files"]:
 p=R/rec["path"]
 if p.name=="SHA256SUMS":
  for line in p.read_text().splitlines():
   digest,name=line.split("  ",1);q=p.parent/name if (p.parent/name).exists() else R/name
   assert q.resolve().is_relative_to(R);assert sha(q.read_bytes())==digest,q;manifests+=1
comparison=json.loads((B/"COMPARISON.json").read_text())
assert comparison["case_counts"]==nc["summary"] and comparison["transaction_simulator"]==nc["classification"]["transaction_simulator"]
assert comparison["verified_evidence_hashes"]==len(bl["files"])
assert "No mutation-suite" in (B/"AMENDMENT.md").read_text()
print(json.dumps({"result":"PASS","only_case_changed":cid,"total_pass":53,"pending":2,"simulator_pass":49,"mutations_unchanged":True,"top_level_evidence_links":len(bl["files"]),"checked_link_hashes":checked,"manifest_entries_checked":manifests,"CASE_STATUS_SHA256":sha((B/"CASE-STATUS.json").read_bytes()),"package_SHA256SUMS_SHA256":sha((B/"SHA256SUMS").read_bytes())},indent=2))
