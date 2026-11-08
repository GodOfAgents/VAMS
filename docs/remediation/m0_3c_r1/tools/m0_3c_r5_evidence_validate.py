#!/usr/bin/env python3
"""Strict closed-schema validator for M0.3c-R5 evidence."""
import argparse,hashlib,json,math,re,sys,unicodedata
from datetime import datetime
from pathlib import Path,PurePosixPath
T=Path(__file__).resolve().parent;sys.path.insert(0,str(T))
import m0_3c_adjudicator as m
import m0_3c_schema as old
import m0_3c_filesystem as filesystem
HEAD="829ab544571f12efe50ecb5740f129c8acb3e16f"
R4="c2f74e04c89184195c962e266f3485ed59070a0515f51514e7a785bac58bb1bc"
REPO="/home/GodOfAgents/code/VAMS-testnet"
PY="/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
GL="/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks"
CHANGED={"docs/CHANGELOG.md","docs/audit/GITLEAKS_ADJUDICATION.md",
"docs/remediation/SESSION_HANDOFF.md","docs/remediation/STATUS.md",
"docs/remediation/m0_3c_r1/R5_REVIEW.md",
"docs/remediation/m0_3c_r1/tools/m0_3c_adjudicator.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_mutations.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_r5_evidence.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_r5_evidence_validate.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_r5_validator_matrix.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_schema.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_semantic_oracle.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_validate.py",
"docs/remediation/m0_3c_r1/tools/test_m0_3c_adjudicator.py",
"docs/remediation/m0_3c_r1/tools/test_m0_3c_semantic_oracle.py",
"docs/remediation/m0_3c_r1/tools/test_m0_3c_validator.py"}
VERIFY={"m0_3c_adjudicator.py","m0_3c_mutations.py","m0_3c_reconcile.py",
"m0_3c_r5_evidence.py","m0_3c_r5_evidence_validate.py","m0_3c_r5_validator_matrix.py",
"m0_3c_schema.py","m0_3c_semantic_oracle.py","m0_3c_validate.py",
"test_m0_3c_adjudicator.py","test_m0_3c_semantic_oracle.py",
"test_m0_3c_validator.py","pre_checksum_short_circuit.py"}
GATE={"decisions.json","excluded-gitlinks.json","findings.json","ledger.json",
"owned-blobs.json","reachability.json","record.json","source-checksums.sha256",
"source-manifest.json","summary.json"}
ROOT={"REVIEW.md","changed-files.json","commands.json","environment.json",
"invariant-matrix.json","mutation-matrix.json","pre-r5-checksum-short-circuit.json",
"pre-r5-reproduction-summary.json","pre-r5-semantic-adversarial.json",
"pre-r5-validator-adversarial.json","reconciliation.json","reviewed-hashes.json",
"semantic-attestation.json","semantic-oracle-result.json","summary.json",
"test-results.json","validator-53-case-results.json"}
ART=ROOT|{"gate/"+x for x in GATE}|{"verification/"+x for x in VERIFY}
NAMES={"r4-manifest-check","focused-m0-3c-r5-tests","validator-53-case-matrix",
"m0-3a-regression-tests","m0-3b-regression-tests","existing-gitleaks-tests",
"negative-fixture-regression","independent-semantic-attestation",
"fresh-independent-reconciliation","fail-closed-mutation-matrix",
"dual-proof-exact-set-gate","gate-inner-checksums",
"preserved-r1-schema-validation","git-diff-check","git-cached-diff-check",
"gitleaks-config-preservation","recursive-submodule-preservation",
"final-schema-validation","final-manifest-check"}
class E(RuntimeError):pass
def f(x):raise E(x)
def d(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ex(v,k,c):
 if not isinstance(v,dict) or set(v)!=set(k):f("schema."+c)
def tx(v,c,n=512):
 if not isinstance(v,str) or not 1<=len(v)<=n or any(ord(x)<32 or ord(x)==127 for x in v):f("schema."+c)
def si(v,c,n=64):
 tx(v,c,n)
 if not re.fullmatch(rf"[0-9a-f]{{{n}}}",v):f("schema."+c)
def it(v,c,a=0,b=10_000_000):
 if type(v)is not int or not a<=v<=b:f("schema."+c)
def bo(v,c):
 if type(v)is not bool:f("schema."+c)
def guard(v,z=0,q=None):
 q=[0] if q is None else q;q[0]+=1
 if z>10 or q[0]>100000:f("bounds.structure")
 if isinstance(v,dict):
  if len(v)>4096:f("bounds.mapping")
  for k,x in v.items():
   tx(k,"key",300)
   if not k.isascii() or unicodedata.normalize("NFKC",k)!=k or "\\" in k:f("schema.key")
   n=re.sub("[^a-z0-9]","",k.lower())
   path_digest_key=("/" in k and isinstance(x,str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}",x) is not None)
   if not path_digest_key and k not in {"raw_removed","potential_credential","credential_loading",
    "private_key_der","fingerprintMetadata","unsafe_echo"} and any(t in n for t in
    ("secret","password","rawmatch","matchvalue","snippet","entropy","fingerprint",
     "credentialvalue","privatekey","tokendigest")):f("schema.sensitive_key")
   guard(x,z+1,q)
 elif isinstance(v,list):
  if len(v)>4096:f("bounds.collection")
  for x in v:guard(x,z+1,q)
 elif isinstance(v,str):tx(v,"string",4096)
 elif v is None:pass
 elif type(v)not in {bool,int,float} or isinstance(v,float)and not math.isfinite(v):f("schema.scalar")
 elif type(v)is int and not -1_000_000_000<=v<=1_000_000_000:f("schema.integer_range")
 elif type(v)is float and not -86_400<=v<=86_400:f("schema.number_range")
 return v
def ld(p):
 p=Path(p)
 if not p.is_file()or p.stat().st_size>2097152:f("bounds.json")
 def pairs(a):
  o={}
  for k,v in a:
   if k in o:f("json.duplicate_key")
   o[k]=v
  return o
 try:return guard(json.loads(p.read_text(),object_pairs_hook=pairs,parse_constant=lambda _:f("json.nonfinite")))
 except (UnicodeError,json.JSONDecodeError):f("json.malformed")
def manifest(e):
 o={}
 for line in (e/"SHA256SUMS").read_text().splitlines():
  if not re.fullmatch(r"[0-9a-f]{64}  [A-Za-z0-9_./-]+",line):f("checksum.outer")
  h,n=line.split("  ");p=(e/n).resolve()
  if n in o or n=="SHA256SUMS"or e not in p.parents or not p.is_file()or d(p)!=h:f("checksum.outer")
  o[n]=h
 try:a=filesystem.inspect_exact_tree(e,ART)
 except filesystem.EvidenceTreeError as x:f(str(x))
 if set(o)!=ART or set(a)-{"SHA256SUMS"}!=ART:f("checksum.artifact_set")
 if any(a[n]!=h for n,h in o.items()):f("checksum.outer")
def matrix(v):
 ex(v,{"schema","case_count","expectation_failure_count","expectation_failures",
 "temporary_copies_removed","results"},"matrix")
 if v["schema"]!="m0_3c_r5_validator_adversarial"or v["case_count"]!=53 or v["expectation_failure_count"]!=0 or v["expectation_failures"]!=[]or v["temporary_copies_removed"]is not True or not isinstance(v["results"],list)or len(v["results"])!=53:f("schema.matrix")
 for x in v["results"]:
  ex(x,{"name","expected_accept","accepted","expectation_met","checksums_passed",
  "schema_code","unsafe_echo","exit","stdout_sha256","stderr_sha256"},"matrix_result")
  if x["expectation_met"]is not True or x["checksums_passed"]is not True or x["unsafe_echo"]is not False:f("schema.matrix_result")
  for k in("expected_accept","accepted","expectation_met","checksums_passed","unsafe_echo"):bo(x[k],k)
  if x["schema_code"]is not None:tx(x["schema_code"],"schema_code",128)
  it(x["exit"],"exit",0,1);si(x["stdout_sha256"],"stdout");si(x["stderr_sha256"],"stderr")
def validate(repo,e):
 repo=Path(repo).resolve();e=Path(e).resolve()
 if str(repo)!=REPO:f("binding.repo")
 manifest(e)
 env=ld(e/"environment.json");ex(env,{"schema","canonical_checkout","evidence_output",
 "origin_fetch","origin_push","branch","head","parent_submodule_commit","submodule_commit",
 "parent_submodule_clean","submodule_clean","recursive_submodules","dirty_status",
 "python_version","python_sha256","gitleaks_version","gitleaks_sha256","openssl_version",
 "cryptography_version","started_utc","finished_utc"},"environment")
 if env["schema"]!="m0_3c_r5_environment"or env["canonical_checkout"]!=REPO or env["evidence_output"]!=str(e)or env["origin_fetch"]!=env["origin_push"]or env["origin_fetch"]!="https://github.com/GodOfAgents/VAMS.git"or env["branch"]!="testnet/remediation-20260907"or env["head"]!=HEAD or env["parent_submodule_commit"]!=m.PARENT_PIN or env["submodule_commit"]!=m.PIN or env["parent_submodule_clean"]is not True or env["submodule_clean"]is not True:f("binding.environment")
 for k in("python_sha256","gitleaks_sha256"):si(env[k],k)
 for k in("recursive_submodules","dirty_status"):
  if not isinstance(env[k],list)or len(env[k])>256:f("schema."+k)
  for x in env[k]:tx(x,k,512)
 for k in("started_utc","finished_utc"):
  tx(env[k],k,64)
  try:
   if datetime.fromisoformat(env[k]).utcoffset().total_seconds()!=0:f("schema."+k)
  except Exception:f("schema."+k)
 c=ld(e/"changed-files.json");ex(c,{"schema","paths"},"changed")
 if c["schema"]!="m0_3c_r5_changed_files"or not isinstance(c["paths"],list)or len(c["paths"])!=len(CHANGED)or len(set(c["paths"]))!=len(CHANGED)or set(c["paths"])!=CHANGED:f("schema.changed")
 r=ld(e/"reviewed-hashes.json");ex(r,{"schema","files","verification","pinned_tools"},"reviewed")
 if r["schema"]!="m0_3c_r5_reviewed_hashes":f("schema.reviewed")
 ex(r["files"],{str(repo/x)for x in CHANGED},"reviewed_files");ex(r["verification"],{"verification/"+x for x in VERIFY},"reviewed_verification");ex(r["pinned_tools"],{PY,GL},"reviewed_tools")
 reviewed_canonical=(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n").encode()
 if hashlib.sha256(reviewed_canonical).hexdigest()!="029bdb354f933630b379edba5ab0c12a0d1bc8a511dc13837362a5aebd1986dc":f("binding.reviewed_hashes")
 for x in VERIFY:
  if r["verification"]["verification/"+x]!=d(e/"verification"/x):f("binding.verification_hash")
 if r["pinned_tools"][PY]!=d(PY)or r["pinned_tools"][GL]!=d(GL):f("binding.tool_hash")
 for q in(r["files"],r["verification"],r["pinned_tools"]):
  for h in q.values():si(h,"reviewed_hash")
 cmds=ld(e/"commands.json")
 if not isinstance(cmds,list)or len(cmds)!=len(NAMES):f("schema.commands")
 seen=set()
 for x in cmds:
  ex(x,{"name","command","cwd","exit","result","stdout_sha256",
  "stdout_size","stderr_sha256","stderr_size"},"command")
  if x["name"]not in NAMES or x["name"]in seen:f("schema.command_name")
  seen.add(x["name"])
  if not isinstance(x["command"],list)or not x["command"]:f("schema.command")
  for a in x["command"]:
   tx(a,"command_arg",512)
   if "<"in a or ">"in a:f("schema.placeholder")
  tx(x["cwd"],"cwd",300);it(x["exit"],"exit",0,0);tx(x["result"],"result",256)
  si(x["stdout_sha256"],"stdout");si(x["stderr_sha256"],"stderr");it(x["stdout_size"],"stdout_size",0,100000000);it(x["stderr_size"],"stderr_size",0,100000000)
 if seen!=NAMES:f("schema.command_set")
 tests=ld(e/"test-results.json");ex(tests,{"schema","results"},"tests")
 wanted={"focused_m0_3c_r5":39,"m0_3a":20,"m0_3b":16,"existing_gitleaks":11}
 ex(tests["results"],wanted,"test_results")
 for k,n in wanted.items():
  ex(tests["results"][k],{"status","tests"},"test_result")
  if tests["results"][k]!={"status":"pass","tests":n}:f("schema.test_result")
 summary=ld(e/"summary.json");ex(summary,{"schema","head","finding_count","path_count",
 "direct_blob_count","excluded_gitlink_count","proof_counts","disposition_totals",
 "scanner_exit","exact_gate_exit","raw_removed","validator_case_count",
 "r4_manifest_sha256","independent_review","promotion_gates","next_slice"},"summary")
 expected={"schema":"m0_3c_r5_summary","head":HEAD,"finding_count":158,"path_count":22,
 "direct_blob_count":821,"excluded_gitlink_count":3,
 "proof_counts":{"ecdsa_public_key_der":75,"expected_custom_error_assertion":83},
 "disposition_totals":{"confirmed_noncredential_fixture":158,"potential_credential":0,"unresolved":0},
 "scanner_exit":1,"exact_gate_exit":0,"raw_removed":True,"validator_case_count":53,
 "r4_manifest_sha256":R4,"independent_review":False,"promotion_gates":"open",
 "next_slice":"independent_m0_3c_r6_review"}
 if summary!=expected:f("schema.summary")
 inv=ld(e/"invariant-matrix.json");ex(inv,{"schema","invariants","mock_mode"},"invariants")
 if inv["schema"]!="m0_3c_r5_invariant_matrix"or inv["mock_mode"]!="no_impact"or inv["invariants"]!=[{"id":f"INV-{i}","impact":"no_impact"}for i in range(1,11)]:f("schema.invariants")
 pre=ld(e/"pre-r5-reproduction-summary.json");ex(pre,{"schema","schema_bypass_count",
 "schema_bypasses","undeclared_disposition","undeclared_exact_gate_passed",
 "undeclared_production_proof","undeclared_reconciler_accepts"},"pre")
 if pre["schema_bypass_count"]!=8 or pre["undeclared_exact_gate_passed"]is not True or pre["undeclared_reconciler_accepts"]is not False:f("schema.pre")
 expected_bypasses=["bool_as_integer_raw_removed","bool_as_integer_scanner_exit","bool_as_integer_disposition_total","null_unvalidated_record_field","unexpected_scalar_environment_branch","sensitive_dynamic_reviewed_files_key","sensitive_dynamic_pinned_binary_key","changed_files_wrong_exact_set"]
 if pre["schema_bypasses"]!=expected_bypasses:f("schema.pre_bypasses")
 pc=ld(e/"pre-r5-checksum-short-circuit.json");ex(pc,{"schema","outer_only_reason","both_layers_reason","temporary_copy_removed"},"pre_checksum")
 pv=ld(e/"pre-r5-validator-adversarial.json");ex(pv,{"schema","case_count","expectation_failure_count","expectation_failures","temporary_copies_removed","results"},"pre_validator")
 if pv["case_count"]!=53 or pv["expectation_failure_count"]!=8 or not isinstance(pv["results"],list)or len(pv["results"])!=53:f("schema.pre_validator")
 for x in pv["results"]:
  ex(x,{"name","expected_accept","accepted","expectation_met","unsafe_echo","exit","stdout_sha256","stderr_sha256"},"pre_validator_result")
  for k in("expected_accept","accepted","expectation_met","unsafe_echo"):bo(x[k],"pre_"+k)
  it(x["exit"],"pre_exit",0,1);si(x["stdout_sha256"],"pre_stdout");si(x["stderr_sha256"],"pre_stderr")
 ps=ld(e/"pre-r5-semantic-adversarial.json");ex(ps,{"schema","javascript","der","cryptography","declaration_extractor","disagreement_gate","independence","temporary_copies_removed"},"pre_semantic")
 nested={"javascript":{"block_comment","extra_argument","line_comment","malformed","multiline_first","string_literal","undeclared","valid_backtick","valid_double","valid_single","wrong_error","wrong_quote","wrong_receiver"},"der":{"malformed_der","non_ec_public","private_key_der","valid_public_ec"},"cryptography":{"distribution_version","module_path","module_sha256","version"},"declaration_extractor":{"commented_declaration_matched","string_declaration_matched"},"disagreement_gate":{"double_quote_disposition","double_quote_exact_gate_passed","double_quote_production_proof","double_quote_reconciler_accepts","undeclared_disposition","undeclared_exact_gate_passed","undeclared_production_proof","undeclared_reconciler_accepts"},"independence":{"production_imports_shared_base","reconciler_calls_production_source_proof","reconciler_imports_adjudicator","reconciler_imports_cryptography","reconciler_uses_openssl"}}
 for k,v in nested.items():ex(ps[k],v,"pre_"+k)
 matrix(ld(e/"validator-53-case-results.json"))
 mu=ld(e/"mutation-matrix.json");ex(mu,{"schema","baseline_count","checks","passed"},"mutation")
 if mu["baseline_count"]!=158 or mu["passed"]is not True or not isinstance(mu["checks"],dict)or set(mu["checks"])!=old.MUTATION_KEYS or set(mu["checks"].values())!={True}:f("schema.mutation")
 rec=ld(e/"reconciliation.json");ex(rec,{"schema","scanner_exit","scanner_command","scanner_cwd","finding_count","path_count","proof_counts","direct_blob_count","excluded_gitlink_count","child_gitlinks_excluded","reachability_reference_counts","raw_removed","head","parent_submodule_commit","submodule_commit","semantic_oracles"},"reconciliation")
 if rec["scanner_exit"]!=1 or rec["finding_count"]!=158 or rec["path_count"]!=22 or rec["direct_blob_count"]!=821 or rec["excluded_gitlink_count"]!=3 or rec["raw_removed"]is not True:f("schema.reconciliation")
 ex(rec["proof_counts"],m.PROOFS,"reconciliation_proofs");ex(rec["reachability_reference_counts"],m.DOMAINS,"reconciliation_reachability");ex(rec["semantic_oracles"],{"javascript","der","der_library_version"},"reconciliation_oracles")
 if rec["proof_counts"]!={"ecdsa_public_key_der":75,"expected_custom_error_assertion":83}or set(rec["reachability_reference_counts"].values())!={0}:f("schema.reconciliation_nested")
 oracle=ld(e/"semantic-oracle-result.json");ex(oracle,{"schema","attestation","attestation_sha256","finding_count","path_count","proof_counts","raw_removed","scanner_command","scanner_cwd","scanner_exit"},"oracle")
 if oracle["finding_count"]!=158 or oracle["path_count"]!=22 or oracle["scanner_exit"]!=1 or oracle["raw_removed"]is not True or oracle["attestation_sha256"]!=d(e/"semantic-attestation.json"):f("schema.oracle")
 ex(oracle["proof_counts"],m.PROOFS,"oracle_proofs")
 if oracle["proof_counts"]!={"ecdsa_public_key_der":75,"expected_custom_error_assertion":83}:f("schema.oracle_proofs")
 if not isinstance(oracle["scanner_command"],list)or len(oracle["scanner_command"])!=13:f("schema.oracle_command")
 for x in oracle["scanner_command"]:tx(x,"oracle_argument",512)
 g=e/"gate";inner={}
 for line in(g/"source-checksums.sha256").read_text().splitlines():
  h,n=line.split("  ")
  if n in inner or n not in GATE-{"source-checksums.sha256"}or d(g/n)!=h:f("checksum.inner")
  inner[n]=h
 if set(inner)!=GATE-{"source-checksums.sha256"}:f("checksum.inner")
 docs=[ld(g/x)for x in("findings.json","decisions.json","ledger.json")]
 for doc,name in zip(docs,("m0_3c_r1_findings","m0_3c_r1_decisions","m0_3c_r1_ledger")):
  ex(doc,{"schema","records"},"gate_records")
  if doc["schema"]!=name or not isinstance(doc["records"],list)or len(doc["records"])!=158:f("schema.gate_records")
  for row in doc["records"]:m.validate_record(row)
 if m.base.encoded(docs[1]["records"])!=m.base.encoded(docs[2]["records"]):f("schema.gate_reconcile")
 gs=ld(g/"summary.json");ex(gs,{"schema","disposition_totals","observed_count","path_count"},"gate_summary")
 if gs!={"schema":"m0_3c_r1_summary","disposition_totals":expected["disposition_totals"],"observed_count":158,"path_count":22}:f("schema.gate_summary")
 reach=ld(g/"reachability.json");ex(reach,{"schema","source_manifest_sha256","domains","reviewed_path_count"},"gate_reachability");ex(reach["domains"],m.DOMAINS,"gate_domains")
 if set(reach["domains"].values())!={"absent"}or reach["reviewed_path_count"]!=22:f("schema.gate_reachability")
 owned=ld(g/"owned-blobs.json");ex(owned,{"schema","blobs"},"gate_owned")
 if not isinstance(owned["blobs"],list)or len(owned["blobs"])!=821:f("schema.gate_owned")
 observed={}
 for x in owned["blobs"]:
  ex(x,{"path","object_id","mode"},"gate_blob");si(x["object_id"],"object_id",40)
  if x["path"]in observed or x["mode"]not in{"100644","100755"}:f("schema.gate_blob")
  observed[x["path"]]={"object_id":x["object_id"],"mode":x["mode"]}
 expected_blobs,expected_links=m.direct_tree(repo,m.PIN)
 if observed!=expected_blobs:f("binding.gate_blobs")
 links=ld(g/"excluded-gitlinks.json");ex(links,{"schema","gitlinks"},"gate_links")
 if not isinstance(links["gitlinks"],list)or len(links["gitlinks"])!=3:f("schema.gate_links")
 got={}
 for x in links["gitlinks"]:
  ex(x,{"path","commit"},"gate_link");si(x["commit"],"gitlink",40)
  if x["path"]in got:f("schema.gate_link_duplicate")
  got[x["path"]]=x["commit"]
 if got!=expected_links:f("binding.gate_links")
 source=ld(g/"source-manifest.json")
 if not isinstance(source,dict)or source!=m.base.source_manifest(repo):f("binding.source_manifest")
 for k,v in source.items():tx(k,"source_path",300);si(v,"source_hash")
 gr=ld(g/"record.json");ex(gr,{"schema","head","parent_submodule","parent_submodule_commit","parent_submodule_head","parent_submodule_clean","submodule","submodule_commit","submodule_head","submodule_clean","started_utc","finished_utc","duration_seconds","command","scanner_version","scanner_sha256","scanner_exit","adjudication_exit","source_manifest_sha256","raw_removed","approved_decisions_sha256","independent_review","input_decisions_sha256","semantic_attestation_sha256","semantic_attestation_valid","unknown_decision_count","promotion_gates","direct_blob_count","excluded_gitlink_count"},"gate_record")
 if gr["adjudication_exit"]!=0 or gr["scanner_exit"]!=1 or gr["semantic_attestation_valid"]is not True or gr["semantic_attestation_sha256"]!=d(e/"semantic-attestation.json"):f("schema.gate_record")
 state=m.provenance(repo);blobs,_=m.direct_tree(repo,state["submodule_commit"]);manifest_sha=m.base.digest(m.base.encoded(m.base.source_manifest(repo)))
 semantic=m.validate_semantic_attestation(repo,GL,g/"decisions.json",d(g/"decisions.json"),manifest_sha,state,blobs,e/"semantic-attestation.json",d(e/"semantic-attestation.json"),legacy=True)
 if len(semantic)!=158:f("schema.semantic_count")
 if(e/"REVIEW.md").stat().st_size>65536:f("bounds.review")
 return{"schema":"m0_3c_r5_evidence_validation","status":"pass","artifact_count":len(ART),"finding_count":158,"validator_cases":53}
def main():
 p=argparse.ArgumentParser();p.add_argument("--repo",required=True);p.add_argument("--evidence",required=True);a=p.parse_args()
 try:o=validate(a.repo,a.evidence)
 except Exception as x:o={"schema":"m0_3c_r5_evidence_validation","status":"failure","type":type(x).__name__,"code":str(x)};print(json.dumps(o,sort_keys=True));return 1
 print(json.dumps(o,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
