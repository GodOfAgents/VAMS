#!/usr/bin/env python3
"""Strict R7 evidence, schema, filesystem, and checksum validator."""
from __future__ import annotations
import argparse,hashlib,json,re,sys,unicodedata
from pathlib import Path
T=Path(__file__).resolve().parent;sys.path.insert(0,str(T))
import m0_3c_adjudicator as A
import m0_3c_filesystem as F

REPO=Path("/home/GodOfAgents/code/VAMS-testnet")
SCANNER=Path("/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks")
VERIFY={"m0_3c_adjudicator.py","m0_3c_context.py","m0_3c_filesystem.py","m0_3c_mutations.py","m0_3c_prepare.py","m0_3c_reconcile.py","m0_3c_r5_evidence_validate.py","m0_3c_schema.py","m0_3c_semantic_oracle.py","m0_3c_validate.py","test_m0_3c_adjudicator.py","test_m0_3c_r7.py","test_m0_3c_semantic_oracle.py","test_m0_3c_validator.py","r6_validator_matrix.py","r6_semantic_probes.py","pre_fix_reproduce.py","m0_3c_r7_evidence.py","m0_3c_r7_validate.py"}
GATE={"decisions.json","excluded-gitlinks.json","findings.json","ledger.json","owned-blobs.json","reachability.json","record.json","source-checksums.sha256","source-manifest.json","summary.json"}
ROOT={"REVIEW.md","changed-files.json","commands.json","environment.json","invariant-matrix.json","mutation-matrix.json","pre-fix-record.json","pre-fix-semantic-probes.json","pre-fix-validator-matrix.json","reconciliation.json","reviewed-hashes.json","semantic-attestation.json","semantic-oracle-result.json","summary.json","test-results.json","validator-matrix.json"}
ART=ROOT|{"gate/"+x for x in GATE}|{"verification/"+x for x in VERIFY}
CHANGED={"docs/CHANGELOG.md","docs/audit/GITLEAKS_ADJUDICATION.md","docs/remediation/SESSION_HANDOFF.md","docs/remediation/STATUS.md","docs/remediation/m0_3c_r1/R7_REVIEW.md",*["docs/remediation/m0_3c_r1/tools/"+n for n in {"m0_3c_adjudicator.py","m0_3c_context.py","m0_3c_filesystem.py","m0_3c_mutations.py","m0_3c_prepare.py","m0_3c_r5_evidence_validate.py","m0_3c_r7_evidence.py","m0_3c_r7_validate.py","m0_3c_schema.py","m0_3c_semantic_oracle.py","pre_fix_reproduce.py","test_m0_3c_adjudicator.py","test_m0_3c_r7.py"}]}
COMMAND_NAMES={"r6-manifest-check","pre-fix-bypass-reproduction","focused-r7-tests","complete-m0-3c-tests","m0-3a-regression-tests","m0-3b-regression-tests","existing-gitleaks-tests","negative-fixture-regression","expanded-r4-r6-validator-matrix","independent-semantic-attestation","fresh-unsuppressed-scan-and-reconciliation","fail-closed-and-context-mutation-matrix","separate-exact-set-gate","gate-inner-checksums","preserved-r1-validation","preserved-r5-validation","git-diff-check","git-cached-diff-check","gitleaks-config-preservation","recursive-submodule-preservation","final-r7-schema-filesystem-validation"}
BASE_MUTATIONS={"child_gitlink_excluded","cross_tranche_decision","dirty_parent","dirty_submodule","finding_added","finding_duplicated","finding_omitted","nested_sensitive_field","parent_clean_pin_enforced","pending_review","potential_disposition","rebound_line_end","rebound_line_start","rebound_path","rebound_rule","stale_file_hash","stale_head","stale_manifest","stale_parent_commit","stale_parent_head","stale_submodule_head","stale_target_commit","target_clean_pin_enforced","unknown_decision","unresolved_disposition","vendor_test_path_not_sufficient"}
CONTEXT_MUTATIONS={"context_missing","context_target_rebound","context_signature_rebound","context_selector_rebound","context_owner_rebound","context_owner_blob_rebound","context_chain_rebound","context_caller_blob_rebound"}
ALLOWED_SENSITIVE={"raw_removed","potential_credential","credential_loading"}
SENSITIVE=("secret","password","privatekey","rawmatch","matchvalue","snippet","entropy","fingerprint","credentialvalue","tokendigest")
class Error(RuntimeError):pass
def fail(code):raise Error(code)
def path_digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def exact(v,keys,code):
 if not isinstance(v,dict)or set(v)!=set(keys):fail("schema."+code)
def integer(v,code,lo=0,hi=1_000_000_000):
 if type(v)is not int or not lo<=v<=hi:fail("schema."+code)
def text(v,code,limit=2048):
 if not isinstance(v,str)or not 1<=len(v)<=limit or any(ord(c)<32 or ord(c)==127 for c in v):fail("schema."+code)
def hexdigest(v,code,n=64):
 if not isinstance(v,str)or re.fullmatch(rf"[0-9a-f]{{{n}}}",v)is None:fail("schema."+code)
def guard(v,depth=0,nodes=None):
 nodes=[0] if nodes is None else nodes;nodes[0]+=1
 if depth>12 or nodes[0]>100_000:fail("bounds.structure")
 if isinstance(v,dict):
  if len(v)>4096:fail("bounds.mapping")
  for key,value in v.items():
   if not isinstance(key,str)or not key.isascii()or unicodedata.normalize("NFKC",key)!=key or "\\" in key or any(ord(c)<32 or ord(c)==127 for c in key):fail("schema.key")
   normalized=re.sub("[^a-z0-9]","",key.lower())
   path_digest=("/" in key and isinstance(value,str)and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}",value)is not None)
   if not path_digest and key not in ALLOWED_SENSITIVE and any(token in normalized for token in SENSITIVE):fail("schema.sensitive_key")
   guard(value,depth+1,nodes)
 elif isinstance(v,list):
  if len(v)>4096:fail("bounds.collection")
  for item in v:guard(item,depth+1,nodes)
 elif isinstance(v,str):text(v,"string")
 elif v is None:fail("schema.null")
 elif type(v)is bool:pass
 elif type(v)is int:integer(v,"integer",-1_000_000_000,1_000_000_000)
 else:fail("schema.scalar")
 return v
def load(snapshot,name):
 raw=snapshot.get_bytes(name)
 if len(raw)>2_097_152:fail("bounds.json")
 def pairs(items):
  out={}
  for k,v in items:
   if k in out:fail("json.duplicate_key")
   out[k]=v
  return out
 try:value=json.loads(raw.decode("utf-8"),object_pairs_hook=pairs,parse_constant=lambda _:fail("json.nonfinite"))
 except (UnicodeError,json.JSONDecodeError):fail("json.malformed")
 return guard(value)
def checksums(snapshot):
 entries={}
 try:lines=snapshot.get_bytes("SHA256SUMS").decode("ascii").splitlines()
 except UnicodeError:fail("checksum.outer")
 for line in lines:
  if re.fullmatch(r"[0-9a-f]{64}  [A-Za-z0-9_./-]+",line)is None:fail("checksum.outer")
  h,n=line.split("  ")
  if n in entries or n not in ART or snapshot.digest(n)!=h:fail("checksum.outer")
  entries[n]=h
 if set(entries)!=ART:fail("checksum.outer_set")
def _validate_snapshot(repo,e,snapshot):
 repo=Path(repo).resolve();e=Path(e).resolve()
 if repo!=REPO:fail("binding.repo")
 checksums(snapshot)
 summary=load(snapshot,"summary.json");exact(summary,{"schema","head","finding_count","path_count","direct_blob_count","excluded_gitlink_count","proof_counts","disposition_totals","scanner_exit","exact_gate_exit","raw_removed","r6_manifest_sha256","independent_review","promotion_gates","next_slice"},"summary")
 expected={"schema":"m0_3c_r7_summary","head":"829ab544571f12efe50ecb5740f129c8acb3e16f","finding_count":158,"path_count":22,"direct_blob_count":821,"excluded_gitlink_count":3,"proof_counts":{"ecdsa_public_key_der":75,"expected_custom_error_assertion":83},"disposition_totals":{"confirmed_noncredential_fixture":158,"potential_credential":0,"unresolved":0},"scanner_exit":1,"exact_gate_exit":0,"raw_removed":True,"r6_manifest_sha256":"21d7481c6b0288cab7010fdc9a4cde3e52db2f6349945f23b0854e153369ddd5","independent_review":False,"promotion_gates":"open","next_slice":"independent_m0_3c_r8_review"}
 if summary!=expected:fail("binding.summary")
 env=load(snapshot,"environment.json");exact(env,{"schema","canonical_checkout","evidence_output","origin_fetch","origin_push","branch","head","parent_submodule_commit","submodule_commit","parent_submodule_clean","submodule_clean","recursive_submodules","dirty_status","python_version","python_sha256","gitleaks_version","gitleaks_sha256","openssl_version","cryptography_version","started_utc","finished_utc"},"environment")
 if env["schema"]!="m0_3c_r7_environment"or env["canonical_checkout"]!=str(REPO)or env["evidence_output"]!=str(e)or env["origin_fetch"]!="https://github.com/GodOfAgents/VAMS.git"or env["origin_push"]!="https://github.com/GodOfAgents/VAMS.git"or env["branch"]!="testnet/remediation-20260907"or env["head"]!=expected["head"]or env["parent_submodule_commit"]!=A.PARENT_PIN or env["submodule_commit"]!=A.PIN or env["parent_submodule_clean"]is not True or env["submodule_clean"]is not True:fail("binding.environment")
 for k in ("python_sha256","gitleaks_sha256"):hexdigest(env[k],k)
 cmds=load(snapshot,"commands.json")
 if not isinstance(cmds,list)or len(cmds)!=len(COMMAND_NAMES):fail("schema.commands")
 names=set()
 for row in cmds:
  exact(row,{"name","command","cwd","exit","result","stdout_sha256","stdout_size","stderr_sha256","stderr_size"},"command")
  if row["name"]in names or not isinstance(row["command"],list)or not row["command"]:fail("schema.command")
  names.add(row["name"]);integer(row["exit"],"exit",0,2);integer(row["stdout_size"],"stdout_size");integer(row["stderr_size"],"stderr_size");hexdigest(row["stdout_sha256"],"stdout");hexdigest(row["stderr_sha256"],"stderr")
  if row["name"]not in COMMAND_NAMES or row["exit"]!=0 or row["result"]!="pass":fail("binding.command")
  for arg in row["command"]:
   text(arg,"command_arg",512)
   if "<"in arg or ">"in arg:fail("schema.placeholder")
 if names!=COMMAND_NAMES:fail("binding.command_set")
 tests=load(snapshot,"test-results.json");exact(tests,{"schema","results"},"tests")
 if tests["schema"]!="m0_3c_r7_test_results":fail("schema.tests")
 wanted={"focused_r7":8,"m0_3c_complete":47,"m0_3a":20,"m0_3b":16,"existing_gitleaks":11}
 if set(tests["results"])!=set(wanted):fail("schema.tests")
 for k,n in wanted.items():
  if tests["results"][k]!={"status":"pass","tests":n}:fail("schema.tests")
 for name in ("validator-matrix.json","pre-fix-validator-matrix.json"):
  matrix=load(snapshot,name)
  exact(matrix,{"schema","r1_case_count","r1_failures","r1_results","r5_case_count","r5_failures","r5_results","temporary_copies_removed"},"validator_matrix")
  expected_schema="m0_3c_r6_independent_validator_matrix"
  if matrix["schema"]!=expected_schema or matrix["r1_case_count"]!=62 or matrix["r5_case_count"]!=7 or len(matrix["r1_results"])!=62 or len(matrix["r5_results"])!=7 or matrix["temporary_copies_removed"]is not True:fail("binding.validator_matrix_shape")
  for group in ("r1_results","r5_results"):
   for row in matrix[group]:
    exact(row,{"name","expected_accept","accepted","checksums_passed","schema_rejection","code","expectation_met"},"validator_case")
    if type(row["expected_accept"])is not bool or type(row["accepted"])is not bool or type(row["checksums_passed"])is not bool or type(row["schema_rejection"])is not bool or type(row["expectation_met"])is not bool:fail("schema.validator_case")
  if name.startswith("validator"):
   if matrix["r1_failures"]!=[]or matrix["r5_failures"]!=[]:fail("binding.validator_matrix")
  else:
   if sorted(matrix["r1_failures"]+matrix["r5_failures"])!=sorted(["open_map_wrong_value","suspicious_long_value","excessive_number","symlink_artifact","unexpected_empty_directory","suspicious_long_value_open_list","sensitive_slash_key","sensitive_unicode_homoglyph_key","symlink_artifact","unexpected_empty_directory"]):fail("binding.pre_validator")
 pre=load(snapshot,"pre-fix-record.json")
 exact(pre,{"schema","snapshot_file_count","snapshot_manifest_sha256","r6_manifest_sha256","historical_repo_hash_binding_adapted","results","validator_failures","semantic_context_failures","temporary_snapshot_removed"},"pre_record")
 exact(pre["results"],{"validator_matrix","semantic_probes"},"pre_results")
 for row in pre["results"].values():exact(row,{"exit","result_sha256"},"pre_result")
 if pre["schema"]!="m0_3c_r7_pre_fix_snapshot"or pre["snapshot_file_count"]!=16 or pre["r6_manifest_sha256"]!=expected["r6_manifest_sha256"]or pre["temporary_snapshot_removed"]is not True or pre["historical_repo_hash_binding_adapted"]is not True or pre["semantic_context_failures"]!=["unrelated_contract_same_standard","wrong_library_same_standard"]:fail("binding.pre")
 semantic_pre=load(snapshot,"pre-fix-semantic-probes.json")
 exact(semantic_pre,{"schema","context_cases","context_failures","attestation_case_count","attestation_failures","attestation_results","empty_attestation_confirmed_count","empty_attestation_gate_passed","wrong_context_gate_passed","wrong_context_disposition"},"pre_semantic")
 if semantic_pre["schema"]!="m0_3c_r6_semantic_and_attestation_probes"or semantic_pre["context_failures"]!=["unrelated_contract_same_standard","wrong_library_same_standard"]or semantic_pre["attestation_case_count"]!=31 or semantic_pre["attestation_failures"]!=[]or semantic_pre["empty_attestation_confirmed_count"]!=0 or semantic_pre["empty_attestation_gate_passed"]is not False or semantic_pre["wrong_context_gate_passed"]is not True or semantic_pre["wrong_context_disposition"]!="confirmed_noncredential_fixture":fail("binding.pre_semantic")
 for row in semantic_pre["context_cases"]:exact(row,{"name","expected_accept","production_accept","r5_oracle_accept","expectation_met"},"pre_context_case")
 for row in semantic_pre["attestation_results"]:exact(row,{"name","attestation_validation","accepted","expectation_met"},"pre_attestation_case")
 mutation=load(snapshot,"mutation-matrix.json")
 exact(mutation,{"schema","baseline_count","checks","passed"},"mutation")
 if mutation["schema"]!="m0_3c_r7_mutation_matrix"or mutation["baseline_count"]!=158 or mutation["passed"]is not True or set(mutation["checks"])!=BASE_MUTATIONS|CONTEXT_MUTATIONS or set(mutation["checks"].values())!={True}:fail("binding.mutation")
 reconciliation=load(snapshot,"reconciliation.json")
 exact(reconciliation,{"schema","scanner_exit","scanner_command","scanner_cwd","finding_count","path_count","proof_counts","direct_blob_count","excluded_gitlink_count","child_gitlinks_excluded","reachability_reference_counts","raw_removed","head","parent_submodule_commit","submodule_commit","semantic_oracles"},"reconciliation")
 if reconciliation["finding_count"]!=158 or reconciliation["path_count"]!=22 or reconciliation["direct_blob_count"]!=821 or reconciliation["excluded_gitlink_count"]!=3 or reconciliation["raw_removed"]is not True or reconciliation["scanner_exit"]!=1 or reconciliation["child_gitlinks_excluded"]is not True or reconciliation["proof_counts"]!={"ecdsa_public_key_der":75,"expected_custom_error_assertion":83}or set(reconciliation["reachability_reference_counts"])!=A.DOMAINS or set(reconciliation["reachability_reference_counts"].values())!={0}:fail("binding.reconciliation")
 oracle=load(snapshot,"semantic-oracle-result.json");exact(oracle,{"schema","attestation","attestation_sha256","finding_count","path_count","proof_counts","raw_removed","scanner_exit","scanner_command","scanner_cwd"},"oracle")
 if oracle["schema"]!="m0_3c_r9_semantic_attestation_result"or oracle["attestation"]!=str(e/"semantic-attestation.json")or oracle["attestation_sha256"]!=snapshot.digest("semantic-attestation.json")or oracle["finding_count"]!=158 or oracle["path_count"]!=22 or oracle["proof_counts"]!={"ecdsa_public_key_der":75,"expected_custom_error_assertion":83}or oracle["raw_removed"]is not True or oracle["scanner_exit"]!=1:fail("binding.oracle")
 changed=load(snapshot,"changed-files.json");exact(changed,{"schema","paths"},"changed")
 if changed["schema"]!="m0_3c_r7_changed_files"or not isinstance(changed["paths"],list)or len(changed["paths"])!=len(CHANGED)or set(changed["paths"])!=CHANGED or len(set(changed["paths"]))!=len(CHANGED):fail("binding.changed")
 reviewed=load(snapshot,"reviewed-hashes.json");exact(reviewed,{"schema","files","verification","pinned_tools"},"reviewed")
 if reviewed["schema"]!="m0_3c_r7_reviewed_hashes"or set(reviewed["verification"])!={"verification/"+n for n in VERIFY}or set(reviewed["files"])!={str(repo/p)for p in CHANGED}:fail("binding.reviewed")
 for n in VERIFY:
  if reviewed["verification"]["verification/"+n]!=snapshot.digest("verification/"+n):fail("binding.verification_hash")
 for path,h in reviewed["files"].items():
  p=Path(path)
  if not p.is_file()or path_digest(p)!=h:fail("binding.repository_hash")
 if reviewed["pinned_tools"]!={str(SCANNER):path_digest(SCANNER),"/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python":path_digest("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python")}:fail("binding.tools")
 inv=load(snapshot,"invariant-matrix.json")
 if inv!={"schema":"m0_3c_r7_invariant_matrix","invariants":[{"id":f"INV-{i}","impact":"no_impact"}for i in range(1,11)],"mock_mode":"no_impact"}:fail("binding.invariants")
 gate=e/"gate";inner={}
 for line in snapshot.get_bytes("gate/source-checksums.sha256").decode("ascii").splitlines():
  h,n=line.split("  ")
  if n in inner or n not in GATE-{"source-checksums.sha256"}or snapshot.digest("gate/"+n)!=h:fail("checksum.inner")
  inner[n]=h
 if set(inner)!=GATE-{"source-checksums.sha256"}:fail("checksum.inner")
 docs=[load(snapshot,"gate/"+n)for n in ("findings.json","decisions.json","ledger.json")]
 for doc in docs:
  exact(doc,{"schema","records"},"gate_records")
  if len(doc["records"])!=158:fail("binding.gate_count")
  for row in doc["records"]:A.validate_record(row)
 if A.base.encoded(docs[1]["records"])!=A.base.encoded(docs[2]["records"]):fail("binding.gate_ledger")
 gate_summary=load(snapshot,"gate/summary.json");exact(gate_summary,{"schema","disposition_totals","observed_count","path_count"},"gate_summary")
 if gate_summary!={"schema":"m0_3c_r1_summary","disposition_totals":expected["disposition_totals"],"observed_count":158,"path_count":22}:fail("binding.gate_summary")
 reach=load(snapshot,"gate/reachability.json");exact(reach,{"schema","source_manifest_sha256","domains","reviewed_path_count"},"gate_reachability")
 if set(reach["domains"])!=A.DOMAINS or set(reach["domains"].values())!={"absent"}or reach["reviewed_path_count"]!=22:fail("binding.gate_reachability")
 owned=load(snapshot,"gate/owned-blobs.json");exact(owned,{"schema","blobs"},"owned")
 if not isinstance(owned["blobs"],list)or len(owned["blobs"])!=821:fail("binding.owned")
 observed={}
 for row in owned["blobs"]:
  exact(row,{"path","object_id","mode"},"blob");hexdigest(row["object_id"],"object_id",40)
  if row["path"]in observed or row["mode"]not in {"100644","100755"}:fail("binding.blob")
  observed[row["path"]]={"object_id":row["object_id"],"mode":row["mode"]}
 expected_blobs,expected_links=A.direct_tree(repo)
 if observed!=expected_blobs:fail("binding.owned")
 links=load(snapshot,"gate/excluded-gitlinks.json");exact(links,{"schema","gitlinks"},"links");got={}
 for row in links["gitlinks"]:
  exact(row,{"path","commit"},"link");hexdigest(row["commit"],"commit",40)
  if row["path"]in got:fail("binding.link")
  got[row["path"]]=row["commit"]
 if got!=expected_links:fail("binding.links")
 source=load(snapshot,"gate/source-manifest.json")
 if source!=A.base.source_manifest(repo):fail("binding.source_manifest")
 record=load(snapshot,"gate/record.json")
 expected_record={"schema","head","parent_submodule","parent_submodule_commit","parent_submodule_head","parent_submodule_clean","submodule","submodule_commit","submodule_head","submodule_clean","started_utc","finished_utc","duration_milliseconds","command","scanner_version","scanner_sha256","scanner_exit","adjudication_exit","source_manifest_sha256","raw_removed","approved_decisions_sha256","independent_review","input_decisions_sha256","semantic_attestation_sha256","semantic_attestation_valid","unknown_decision_count","promotion_gates","direct_blob_count","excluded_gitlink_count"}
 exact(record,expected_record,"gate_record");integer(record["duration_milliseconds"],"duration",0,3_600_000)
 if record["schema"]!="m0_3c_r7_run"or record["adjudication_exit"]!=0 or record["scanner_exit"]!=1 or record["semantic_attestation_valid"]is not True or record["raw_removed"]is not True:fail("binding.gate_record")
 state=A.provenance(repo);blobs,_=A.direct_tree(repo);manifest=A.base.digest(A.base.encoded(A.base.source_manifest(repo)));att=e/"semantic-attestation.json"
 semantic=A.validate_semantic_attestation(repo,SCANNER,gate/"decisions.json",snapshot.digest("gate/decisions.json"),manifest,state,blobs,att,snapshot.digest("semantic-attestation.json"),attestation_bytes=snapshot.get_bytes("semantic-attestation.json"),decisions_bytes=snapshot.get_bytes("gate/decisions.json"))
 if len(semantic)!=158:fail("binding.semantic")
 return {"schema":"m0_3c_r7_evidence_validation","status":"pass","artifact_count":len(ART),"finding_count":158}
def validate(repo,e):
 repo=Path(repo).resolve();e=Path(e).resolve()
 if repo!=REPO:fail("binding.repo")
 try:
  with F.capture_exact_tree(e,ART) as snapshot:
   result=_validate_snapshot(repo,e,snapshot)
   snapshot.verify_stable()
   return result
 except F.EvidenceTreeError as exc:fail(str(exc))

def main():
 p=argparse.ArgumentParser();p.add_argument("--repo",required=True);p.add_argument("--evidence",required=True);x=p.parse_args()
 try:result=validate(x.repo,x.evidence)
 except Exception as exc:print(json.dumps({"schema":"m0_3c_r7_evidence_validation","status":"failure","type":type(exc).__name__,"code":str(exc)},sort_keys=True));return 1
 print(json.dumps(result,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
