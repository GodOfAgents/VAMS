#!/usr/bin/env python3
"""Strict descriptor-snapshot validator for M0.3c-R9 evidence."""
import argparse,hashlib,json,re,sys
from pathlib import Path
T=Path(__file__).resolve().parent;sys.path.insert(0,str(T))
import m0_3c_adjudicator as A
import m0_3c_filesystem as F
import m0_3c_r7_validate as R
REPO=Path("/home/GodOfAgents/code/VAMS-testnet")
SCANNER=Path("/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks")
ROOT={"REVIEW.md","commands.json","environment.json","invariant-matrix.json","mutation-matrix.json","pre-fix-record.json","race-matrix.json","reconciliation.json","reviewed-hashes.json","semantic-attestation.json","semantic-dependency.json","summary.json","test-results.json","run_verification.py"}
GATE={"excluded-gitlinks.json","ledger.json","owned-blobs.json","summary.json","decisions.json","record.json","source-manifest.json","reachability.json","source-checksums.sha256","findings.json"}
PRE={"PRE_FIX_SHA256SUMS","m0_3a_adjudicator.py","m0_3c_adjudicator.py","m0_3c_context.py","m0_3c_filesystem.py","m0_3c_r7_validate.py","m0_3c_schema.py","m0_3c_semantic_oracle.py","test_m0_3c_r7.py"}
VERIFY={"m0_3c_adjudicator.py","m0_3c_context.py","m0_3c_filesystem.py","m0_3c_mutations.py","m0_3c_reconcile.py","m0_3c_schema.py","m0_3c_semantic_oracle.py","m0_3c_r7_validate.py","m0_3c_r9_pre_fix.py","m0_3c_r9_validate.py","test_m0_3c_r7.py","test_m0_3c_r9.py"}
NAMES={"focused-r9","complete-m0-3c","m0-3a","m0-3b","gitleaks-tests","negative-fixture","expanded-r4-r6-matrix","pre-fix-r8-reproduction","fresh-independent-semantic-oracle","mutation-matrix","fresh-reconciliation","separate-exact-set-gate","git-diff-check","git-cached-diff-check","gitleaks-config-preservation"}
LOGS={f"logs/{n}.{ext}" for n in NAMES for ext in ("stdout","stderr")}
ART=ROOT|{"gate/"+x for x in GATE}|{"pre-fix/"+x for x in PRE}|{"verification/"+x for x in VERIFY}|LOGS
class Error(RuntimeError):pass
def fail(x):raise Error(x)
def load(s,n):
 try:return json.loads(s.get_bytes(n).decode(),object_pairs_hook=A.base._pairs,parse_constant=lambda _:fail("json.nonfinite"))
 except (UnicodeError,json.JSONDecodeError):fail("json.malformed")
def exact(v,keys,code):
 if not isinstance(v,dict) or set(v)!=set(keys):fail("schema."+code)
def validate(repo,e):
 repo=Path(repo).resolve();e=Path(e).resolve()
 if repo!=REPO:fail("binding.repo")
 try:
  with F.capture_exact_tree(e,ART,per_file_limit=2_097_152,total_limit=50_331_648) as s:
   entries={}
   for line in s.get_bytes("SHA256SUMS").decode("ascii").splitlines():
    if re.fullmatch(r"[0-9a-f]{64}  [A-Za-z0-9_./-]+",line)is None:fail("checksum.outer")
    h,n=line.split("  ")
    if n in entries or n not in ART or s.digest(n)!=h:fail("checksum.outer")
    entries[n]=h
   if set(entries)!=ART:fail("checksum.outer_set")
   summary=load(s,"summary.json")
   expected={"schema":"m0_3c_r9_summary","head":"829ab544571f12efe50ecb5740f129c8acb3e16f","finding_count":158,"path_count":22,"direct_blob_count":821,"excluded_gitlink_count":3,"proof_counts":{"expected_custom_error_assertion":83,"ecdsa_public_key_der":75},"disposition_totals":{"confirmed_noncredential_fixture":158,"potential_credential":0,"unresolved":0},"scanner_exit":1,"exact_gate_exit":0,"raw_removed":True,"independent_review":False,"promotion_gates":"open","next_slice":"independent_m0_3c_r10_review"}
   if summary!=expected:fail("binding.summary")
   tests=load(s,"test-results.json")
   if tests!={"schema":"m0_3c_r9_tests","results":{"focused_r9":13,"complete_m0_3c":60,"m0_3a":20,"m0_3b":16,"gitleaks":11}}:fail("binding.tests")
   commands=load(s,"commands.json");exact(commands,{"schema","records"},"commands")
   if commands["schema"]!="m0_3c_r9_commands" or len(commands["records"])!=15 or {x["name"] for x in commands["records"]}!=NAMES or any(x["result"]!="pass" or x["exit"]!=x["expected_exit"] for x in commands["records"]):fail("binding.commands")
   race=load(s,"race-matrix.json")
   if race["schema"]!="m0_3c_r9_race_matrix" or race["unchanged_control"] is not True or set(race["attacks"].values())!={False} or len(race["attacks"])!=7 or race["path_reopen_blocked"] is not True:fail("binding.races")
   dep=load(s,"semantic-dependency.json")
   if dep["schema"]!="m0_3c_r9_semantic_dependency" or dep["oracle_semantic_catalogs"]!=[] or dep["production_oracle_shared_semantic_dependencies"]!=[] or dep["source_derived_context_count"]!=83:fail("binding.semantic_dependency")
   pre=load(s,"pre-fix-record.json")
   if pre["both_races_accepted"] is not True or not all(pre["shared_catalog_dependency"].values()):fail("binding.pre_fix")
   mut=load(s,"mutation-matrix.json")
   if mut["passed"] is not True or mut["baseline_count"]!=158 or not all(mut["checks"].values()):fail("binding.mutations")
   rec=load(s,"reconciliation.json")
   if rec["scanner_exit"]!=1 or rec["finding_count"]!=158 or rec["path_count"]!=22 or rec["direct_blob_count"]!=821 or rec["excluded_gitlink_count"]!=3 or rec["raw_removed"] is not True or rec["proof_counts"]!={"expected_custom_error_assertion":83,"ecdsa_public_key_der":75}:fail("binding.reconciliation")
   inner={}
   for line in s.get_bytes("gate/source-checksums.sha256").decode("ascii").splitlines():
    h,n=line.split("  ")
    if n in inner or n not in GATE-{"source-checksums.sha256"} or s.digest("gate/"+n)!=h:fail("checksum.inner")
    inner[n]=h
   if set(inner)!=GATE-{"source-checksums.sha256"}:fail("checksum.inner_set")
   docs=[load(s,"gate/"+n) for n in ("findings.json","decisions.json","ledger.json")]
   if any(len(x["records"])!=158 for x in docs):fail("binding.gate_count")
   for d in docs:
    for row in d["records"]:A.validate_record(row)
   if A.base.encoded(docs[1]["records"])!=A.base.encoded(docs[2]["records"]):fail("binding.ledger")
   if load(s,"gate/summary.json")["disposition_totals"]!=expected["disposition_totals"]:fail("binding.gate_summary")
   reviewed=load(s,"reviewed-hashes.json")
   for n,h in reviewed["verification"].items():
    if s.digest(n)!=h:fail("binding.verification_hash")
   for name,h in reviewed["repository"].items():
    if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=h:fail("binding.repository_hash")
   state=A.provenance(repo);blobs,_=A.direct_tree(repo);manifest=A.base.digest(A.base.encoded(A.base.source_manifest(repo)))
   semantic=A.validate_semantic_attestation(repo,SCANNER,e/"gate/decisions.json",s.digest("gate/decisions.json"),manifest,state,blobs,e/"semantic-attestation.json",s.digest("semantic-attestation.json"),attestation_bytes=s.get_bytes("semantic-attestation.json"),decisions_bytes=s.get_bytes("gate/decisions.json"))
   if len(semantic)!=158:fail("binding.semantic")
   s.verify_stable()
   return {"schema":"m0_3c_r9_evidence_validation","status":"pass","artifact_count":len(ART),"finding_count":158}
 except F.EvidenceTreeError as exc:fail(str(exc))
def main():
 p=argparse.ArgumentParser();p.add_argument("--repo",required=True);p.add_argument("--evidence",required=True);a=p.parse_args()
 try:r=validate(a.repo,a.evidence)
 except Exception as exc:print(json.dumps({"schema":"m0_3c_r9_evidence_validation","status":"failure","type":type(exc).__name__,"code":str(exc)},sort_keys=True));return 1
 print(json.dumps(r,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
