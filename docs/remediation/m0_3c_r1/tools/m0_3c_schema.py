"""Closed, bounded schemas for every durable M0.3c-R1 evidence artifact."""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import unicodedata

import m0_3c_filesystem as filesystem

MAX_BYTES=1_048_576
MAX_DEPTH=8
MAX_ITEMS=2048
MAX_NODES=50_000
MAX_STRING=256
CANONICAL_REPO="/home/GodOfAgents/code/VAMS-testnet"
PINNED_PYTHON="/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
PINNED_SCANNER="/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks"
ORIGIN="https://github.com/GodOfAgents/VAMS.git"
BRANCH="testnet/remediation-20260907"
VERIFY={
"verification/m0_3c_adjudicator.py","verification/m0_3c_evidence.py",
"verification/m0_3c_mutations.py","verification/m0_3c_prepare.py",
"verification/m0_3c_reconcile.py","verification/m0_3c_validate.py",
"verification/test_m0_3c_adjudicator.py"}
CORE={"decisions.json","excluded-gitlinks.json","findings.json","ledger.json",
"owned-blobs.json","reachability.json","record.json","source-manifest.json","summary.json"}
ARTIFACTS=CORE|VERIFY|{"REVIEW.md","changed-files.json","commands.json","environment.json",
"reviewed-hashes.json","source-checksums.sha256"}
ROOT_KEYS={
"findings.json":{"schema","records"},"decisions.json":{"schema","records"},
"ledger.json":{"schema","records"},
"summary.json":{"schema","disposition_totals","observed_count","path_count"},
"record.json":{"schema","head","parent_submodule","parent_submodule_commit","parent_submodule_head",
"parent_submodule_clean","submodule","submodule_commit","submodule_head","submodule_clean",
"started_utc","finished_utc","duration_seconds","command","scanner_version","scanner_sha256",
"scanner_exit","adjudication_exit","source_manifest_sha256","raw_removed",
"approved_decisions_sha256","independent_review","input_decisions_sha256",
"unknown_decision_count","promotion_gates","direct_blob_count","excluded_gitlink_count"},
"reachability.json":{"schema","source_manifest_sha256","domains","reviewed_path_count"},
"owned-blobs.json":{"schema","blobs"},"excluded-gitlinks.json":{"schema","gitlinks"},
"environment.json":{"schema","canonical_checkout","evidence_output","origin_fetch","origin_push",
"branch","head","dirty_status","recursive_submodules","parent_submodule_clean",
"target_submodule_clean","python_version","gitleaks_version","openssl_version",
"gitleaks_sha256","python_sha256"},
"changed-files.json":{"schema","paths"},
"reviewed-hashes.json":{"schema","files","evidence_verification_scripts","pinned_binaries"}}
SCHEMAS={"findings.json":"m0_3c_r1_findings","decisions.json":"m0_3c_r1_decisions",
"ledger.json":"m0_3c_r1_ledger","summary.json":"m0_3c_r1_summary",
"record.json":"m0_3c_r1_run","reachability.json":"m0_3c_r1_reachability",
"owned-blobs.json":"m0_3c_r1_owned_blobs","excluded-gitlinks.json":"m0_3c_r1_excluded_gitlinks",
"environment.json":"m0_3c_r1_environment","changed-files.json":"m0_3c_r1_changed_files",
"reviewed-hashes.json":"m0_3c_r1_reviewed_hashes"}
COMMAND_REQUIRED={"name","command","cwd","exit","result"}
COMMAND_OPTIONAL={"duration_seconds","stdout_sha256","stdout_size","stderr_sha256","stderr_size","environment_overrides"}
TEST_NAMES={"focused-m0-3c-tests","m0-3a-regression-tests","m0-3b-regression-tests","existing-gitleaks-tests"}
SCAN_NAMES={"fresh-unsuppressed-gitleaks-8-30-1","exact-gate-unsuppressed-gitleaks-8-30-1"}
SIMPLE_NAMES={"negative-fixture-regression","git-diff-check","git-cached-diff-check",
"gitleaks-config-preservation","recursive-submodule-preservation","inner-source-checksums",
"outer-evidence-checksums"}
ALL_NAMES=TEST_NAMES|SCAN_NAMES|SIMPLE_NAMES|{"schema-and-checksum-validation",
"separate-exact-set-gate","fail-closed-mutation-matrix","independent-fresh-scanner-reconciliation"}
DOMAINS={"production_compilation","deployment","runtime","gateway","frontend","credential_loading","ci_execution"}
MUTATION_KEYS={"child_gitlink_excluded","cross_tranche_decision","dirty_parent","dirty_submodule",
"finding_added","finding_duplicated","finding_omitted","nested_sensitive_field",
"parent_clean_pin_enforced","pending_review","potential_disposition","rebound_line_end",
"rebound_line_start","rebound_path","rebound_rule","stale_file_hash","stale_head",
"stale_manifest","stale_parent_commit","stale_parent_head","stale_submodule_head",
"stale_target_commit","target_clean_pin_enforced","unknown_decision",
"unresolved_disposition","vendor_test_path_not_sufficient"}
EVIDENCE_CHANGED_FILES={
"docs/remediation/m0_3c_r1/REVIEW.md","docs/remediation/m0_3c_r1/findings.json",
"docs/remediation/m0_3c_r1/decisions.json","docs/remediation/m0_3c_r1/tools/m0_3c_adjudicator.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_prepare.py","docs/remediation/m0_3c_r1/tools/m0_3c_reconcile.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_mutations.py","docs/remediation/m0_3c_r1/tools/m0_3c_validate.py",
"docs/remediation/m0_3c_r1/tools/m0_3c_evidence.py","docs/remediation/m0_3c_r1/tools/test_m0_3c_adjudicator.py",
"docs/audit/GITLEAKS_ADJUDICATION.md","docs/CHANGELOG.md","docs/remediation/STATUS.md",
"docs/remediation/SESSION_HANDOFF.md"}
REVIEWED_FILES={
"/home/GodOfAgents/code/VAMS-testnet/.gitleaks.toml",
"/home/GodOfAgents/code/VAMS-testnet/docs/CHANGELOG.md",
"/home/GodOfAgents/code/VAMS-testnet/docs/audit/GITLEAKS_ADJUDICATION.md",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/SESSION_HANDOFF.md",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/STATUS.md",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3a_r1/decisions.json",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3a_r1/findings.json",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3b_r1/decisions.json",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3b_r1/findings.json",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3b_r1/tools/m0_3b_adjudicator.py",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3b_r1/tools/test_m0_3b_adjudicator.py",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/REVIEW.md",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/decisions.json",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/findings.json",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/tools/m0_3c_adjudicator.py",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/tools/m0_3c_evidence.py",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/tools/m0_3c_mutations.py",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/tools/m0_3c_prepare.py",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/tools/m0_3c_reconcile.py",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/tools/m0_3c_validate.py",
"/home/GodOfAgents/code/VAMS-testnet/docs/remediation/m0_3c_r1/tools/test_m0_3c_adjudicator.py",
"/home/GodOfAgents/code/VAMS-testnet/scripts/security/m0_3a_adjudicator.py",
"/home/GodOfAgents/code/VAMS-testnet/scripts/security/test_m0_3a_adjudicator.py"}
PINNED_BINARIES={PINNED_SCANNER,PINNED_PYTHON}
SENSITIVE_ALLOWED={"raw_removed","credential_loading","potential_credential"}
SENSITIVE_TOKENS={"secret","password","privatekey","rawmatch","credentialmaterial","tokendigest",
"fingerprintmetadata","entropy","snippet","sourceline","matchvalue","secretvalue","apisecretmaterial"}
R1_DIRTY_STATUS=[' M .github/workflows/security-gates.yml',' M AGENTS.md',' M docs/CHANGELOG.md',
' M docs/audit/GITLEAKS_ADJUDICATION.md',' M gateway/server.py',' M neuron/economics/keeper.py',
' M neuron/tests/test_workflows.py',' M scripts/audit/test_workflow_security.py',
' M scripts/audit/validate_workflow_security.py','?? .codex/','?? docs/remediation/',
'?? neuron/tests/test_gateway_shutdown.py','?? neuron/tests/test_workflows_isolation.py',
'?? scripts/remediation/','?? scripts/security/gitleaks_working_tree_inventory.py',
'?? scripts/security/m0_3a_adjudicator.py','?? scripts/security/test_gitleaks_working_tree_inventory.py',
'?? scripts/security/test_m0_3a_adjudicator.py']

def fail(m,code): raise m.AdjudicationError(code)
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def exact(m,v,k,code):
 if not isinstance(v,dict) or set(v)!=set(k): fail(m,"schema."+code)
def sensitive_key(m,k,allowed_path_keys=frozenset()):
 if not isinstance(k,str) or len(k)>MAX_STRING or not k.isascii() or unicodedata.normalize("NFKC",k)!=k or "\\" in k or any(ord(c)<32 or ord(c)==127 for c in k): fail(m,"schema.key")
 if k in SENSITIVE_ALLOWED or k in allowed_path_keys:return
 n=re.sub(r"[^a-z0-9]","",k.lower())
 if any(t in n for t in SENSITIVE_TOKENS): fail(m,"schema.sensitive_key")
def safe_text(m,v,code,maxlen=MAX_STRING):
 if not isinstance(v,str) or not 1<=len(v)<=maxlen or any(ord(c)<32 or ord(c)==127 for c in v): fail(m,"schema."+code)
def sha(m,v,code,n=64):
 safe_text(m,v,code,n)
 if re.fullmatch(rf"[0-9a-f]{{{n}}}",v) is None: fail(m,"schema."+code)
def boolean(m,v,code):
 if type(v) is not bool: fail(m,"schema."+code)
def integer(m,v,code,low=0,high=10_000_000):
 if type(v) is not int or not low<=v<=high: fail(m,"schema."+code)
def number(m,v,code,low=0,high=86_400):
 # Historical R1 used a finite fractional duration. New R7 artifacts use
 # integer milliseconds, but the immutable R1 package remains valid.
 if type(v) not in {int,float} or not math.isfinite(v) or not low<=v<=high: fail(m,"schema."+code)
def safe_path(m,v,code,absolute=False):
 safe_text(m,v,code,240);p=PurePosixPath(v)
 if p.is_absolute()!=absolute or any(x in {"",".",".."} for x in v.lstrip("/").split("/")) or re.fullmatch(r"/?[A-Za-z0-9_./-]+",v) is None: fail(m,"schema."+code)
def timestamp(m,v,code):
 safe_text(m,v,code,64)
 try:d=datetime.fromisoformat(v)
 except ValueError:fail(m,"schema."+code)
 if d.tzinfo is None or d.utcoffset().total_seconds()!=0:fail(m,"schema."+code)
def command(m,v):
 if not isinstance(v,list) or not 1<=len(v)<=32:fail(m,"schema.command")
 for x in v:
  safe_text(m,x,"command_argument",240)
  if "<" in x or ">" in x:fail(m,"schema.command_placeholder")

def guard(m,v,d=0,s=None,allowed_path_keys=frozenset()):
 s={"n":0} if s is None else s;s["n"]+=1
 if d>MAX_DEPTH or s["n"]>MAX_NODES:fail(m,"bounds.structure")
 if isinstance(v,dict):
  if len(v)>MAX_ITEMS:fail(m,"bounds.mapping")
  for k,x in v.items():sensitive_key(m,k,allowed_path_keys);guard(m,x,d+1,s,allowed_path_keys)
 elif isinstance(v,list):
  if len(v)>MAX_ITEMS:fail(m,"bounds.collection")
  for x in v:guard(m,x,d+1,s,allowed_path_keys)
 elif isinstance(v,str):safe_text(m,v,"string")
 elif v is None:pass
 elif type(v) not in {bool,int,float}:fail(m,"schema.scalar")
 elif isinstance(v,float) and not math.isfinite(v):fail(m,"schema.number")
 return v

def load(m,p,allowed_path_keys=frozenset()):
 p=Path(p)
 if not p.is_file() or p.stat().st_size>MAX_BYTES:fail(m,"bounds.json_bytes")
 def pairs(items):
  out={}
  for k,v in items:
   if k in out:fail(m,"json.duplicate_key")
   out[k]=v
  return out
 def constant(_):fail(m,"json.nonfinite")
 try:v=json.loads(p.read_text(encoding="utf-8"),object_pairs_hook=pairs,parse_constant=constant)
 except (UnicodeError,json.JSONDecodeError):fail(m,"json.malformed")
 return guard(m,v,allowed_path_keys=allowed_path_keys)

def manifest(m,e):
 entries={}
 try:lines=(e/"SHA256SUMS").read_text(encoding="utf-8").splitlines()
 except (OSError,UnicodeError):fail(m,"checksum.outer")
 for line in lines:
  if re.fullmatch(r"[0-9a-f]{64}  [A-Za-z0-9_./-]+",line) is None:fail(m,"checksum.outer")
  h,n=line.split("  ");t=(e/n).resolve()
  if n in entries or n=="SHA256SUMS" or e not in t.parents or not t.is_file() or digest(t)!=h:fail(m,"checksum.outer")
  entries[n]=h
 try: observed=filesystem.inspect_exact_tree(e,ARTIFACTS)
 except filesystem.EvidenceTreeError as exc:fail(m,str(exc))
 if set(entries)!=ARTIFACTS or set(observed)-{"SHA256SUMS"}!=ARTIFACTS:fail(m,"checksum.artifact_set")
 if any(observed[n]!=h for n,h in entries.items()):fail(m,"checksum.outer")
 if any((e/n).stat().st_size>131072 for n in VERIFY) or (e/"REVIEW.md").stat().st_size>65536:fail(m,"bounds.artifact")

def inner(m,e):
 seen={}
 try:lines=(e/"source-checksums.sha256").read_text(encoding="utf-8").splitlines()
 except (OSError,UnicodeError):fail(m,"checksum.inner")
 for line in lines:
  if re.fullmatch(r"[0-9a-f]{64}  [A-Za-z0-9_.-]+",line) is None:fail(m,"checksum.inner")
  h,n=line.split("  ")
  if n in seen or n not in CORE or digest(e/n)!=h:fail(m,"checksum.inner")
  seen[n]=h
 if set(seen)!=CORE:fail(m,"checksum.inner")

def totals(m,v,code):
 exact(m,v,m.ALLOWED,code)
 for k in m.ALLOWED:integer(m,v[k],code+"."+k,0,158)

def validate_result(m,name,v):
 if name in TEST_NAMES:
  exact(m,v,{"status","tests"},"command.test_result");safe_text(m,v["status"],"test_status",16)
  if v["status"]!="pass":fail(m,"schema.test_status")
  integer(m,v["tests"],"test_count",1,1000)
 elif name in SCAN_NAMES:
  exact(m,v,{"finding_count","path_count","raw_removed"},"command.scan_result")
  integer(m,v["finding_count"],"scan_finding_count",0,1000);integer(m,v["path_count"],"scan_path_count",0,1000);boolean(m,v["raw_removed"],"scan_raw_removed")
  if v!={"finding_count":158,"path_count":22,"raw_removed":True}:fail(m,"schema.scan_result")
 elif name in SIMPLE_NAMES:
  safe_text(m,v,"command_result",200)
 elif name=="schema-and-checksum-validation":
  exact(m,v,{"status","finding_count","decision_count","ledger_count"},"command.validation_result")
  if v["status"]!="pass":fail(m,"schema.validation_status")
  for f in ("finding_count","decision_count","ledger_count"):integer(m,v[f],f,158,158)
 elif name=="separate-exact-set-gate":
  exact(m,v,{"scanner_exit","adjudication_exit","raw_removed","unknown_decision_count","disposition_totals","observed_count","path_count"},"command.gate_result")
  for f,x in (("scanner_exit",1),("adjudication_exit",0),("unknown_decision_count",0),("observed_count",158),("path_count",22)):
   integer(m,v[f],f,x,x)
  boolean(m,v["raw_removed"],"gate_raw_removed");totals(m,v["disposition_totals"],"gate_totals")
  if v["raw_removed"] is not True or v["disposition_totals"]!={"confirmed_noncredential_fixture":158,"potential_credential":0,"unresolved":0}:fail(m,"schema.gate_result")
 elif name=="fail-closed-mutation-matrix":
  exact(m,v,{"schema","baseline_count","checks","passed"},"command.mutation_result")
  if v["schema"]!="m0_3c_r1_mutation_matrix":fail(m,"schema.mutation_schema")
  integer(m,v["baseline_count"],"baseline_count",158,158);boolean(m,v["passed"],"mutation_passed")
  exact(m,v["checks"],MUTATION_KEYS,"mutation_checks")
  for key in MUTATION_KEYS:
   boolean(m,v["checks"][key],"mutation_check")
   if v["checks"][key] is not True:fail(m,"schema.mutation_check")
 elif name=="independent-fresh-scanner-reconciliation":
  base={"schema","scanner_exit","scanner_command","scanner_cwd","finding_count","path_count","proof_counts","direct_blob_count","excluded_gitlink_count","child_gitlinks_excluded","reachability_reference_counts","raw_removed","head","parent_submodule_commit","submodule_commit"}
  allowed=(base,base|{"semantic_oracles"})
  if not isinstance(v,dict) or set(v) not in allowed:fail(m,"schema.reconciliation_result")
  if v["schema"] not in {"m0_3c_r1_independent_reconciliation","m0_3c_r3_independent_reconciliation"}:fail(m,"schema.reconciliation_schema")
  command(m,v["scanner_command"]);safe_path(m,v["scanner_cwd"],"scanner_cwd",True)
  for f,x in (("scanner_exit",1),("finding_count",158),("path_count",22),("direct_blob_count",821),("excluded_gitlink_count",3)):integer(m,v[f],f,x,x)
  boolean(m,v["child_gitlinks_excluded"],"child_gitlinks_excluded");boolean(m,v["raw_removed"],"reconcile_raw_removed")
  exact(m,v["proof_counts"],m.PROOFS,"proof_counts")
  for f,x in (("ecdsa_public_key_der",75),("expected_custom_error_assertion",83)):integer(m,v["proof_counts"][f],f,x,x)
  exact(m,v["reachability_reference_counts"],DOMAINS,"reachability_counts")
  for f in DOMAINS:integer(m,v["reachability_reference_counts"][f],f,0,0)
  for f in ("head","parent_submodule_commit","submodule_commit"):sha(m,v[f],f,40)
  if v["child_gitlinks_excluded"] is not True or v["raw_removed"] is not True:fail(m,"schema.reconciliation_result")
  if "semantic_oracles" in v:
   exact(m,v["semantic_oracles"],{"javascript","der","der_library_version"},"semantic_oracles")
   if v["semantic_oracles"]["javascript"]!="bounded_token_parser_v1" or v["semantic_oracles"]["der"]!="cryptography_load_der_public_key":fail(m,"schema.semantic_oracle")
   safe_text(m,v["semantic_oracles"]["der_library_version"],"der_library_version",32)
 else:fail(m,"schema.command_name")

def commands(m,v):
 if not isinstance(v,list) or len(v)!=len(ALL_NAMES):fail(m,"schema.commands")
 seen=set()
 for x in v:
  if not isinstance(x,dict) or not COMMAND_REQUIRED.issubset(x) or set(x)-COMMAND_REQUIRED-COMMAND_OPTIONAL:fail(m,"schema.command_entry")
  name=x["name"];safe_text(m,name,"command_name",96)
  if name not in ALL_NAMES or name in seen:fail(m,"schema.command_name")
  seen.add(name);command(m,x["command"]);safe_path(m,x["cwd"],"command_cwd",True);integer(m,x["exit"],"command_exit",0,255);validate_result(m,name,x["result"])
  if "duration_seconds" in x:number(m,x["duration_seconds"],"duration")
  for f in ("stdout_sha256","stderr_sha256"):
   if f in x:sha(m,x[f],f)
  for f in ("stdout_size","stderr_size"):
   if f in x:integer(m,x[f],f,0,100_000_000)
  if "environment_overrides" in x:
   exact(m,x["environment_overrides"],{"GITLEAKS_BIN"},"environment_overrides")
   safe_path(m,x["environment_overrides"]["GITLEAKS_BIN"],"gitleaks_path",True)
 if seen!=ALL_NAMES:fail(m,"schema.command_set")

def validate(repo,evidence,m):
 repo=Path(repo).resolve();e=Path(evidence).resolve();manifest(m,e);inner(m,e)
 docs={n:load(m,e/n) for n in ROOT_KEYS}
 for n,k in ROOT_KEYS.items():exact(m,docs[n],k,n)
 for n,schema_name in SCHEMAS.items():
  if docs[n]["schema"]!=schema_name:fail(m,"schema.identifier")
 rows=[]
 for n in ("findings.json","decisions.json","ledger.json"):
  records=docs[n]["records"]
  if not isinstance(records,list) or len(records)!=158:fail(m,"schema.record_count")
  for row in records:m.validate_record(row)
  rows.append(records)
 ids=[{r["finding_id"] for r in records} for records in rows]
 if any(len(x)!=158 for x in ids) or not ids[0]==ids[1]==ids[2] or m.base.encoded(rows[1])!=m.base.encoded(rows[2]):fail(m,"schema.record_reconciliation")
 summary=docs["summary.json"];totals(m,summary["disposition_totals"],"summary_totals")
 integer(m,summary["observed_count"],"observed_count",158,158);integer(m,summary["path_count"],"path_count",22,22)
 if summary["disposition_totals"]!={"confirmed_noncredential_fixture":158,"potential_credential":0,"unresolved":0}:fail(m,"schema.summary")
 record=docs["record.json"]
 for f in ("head","parent_submodule_commit","parent_submodule_head","submodule_commit","submodule_head"):sha(m,record[f],f,40)
 for f in ("scanner_sha256","source_manifest_sha256","approved_decisions_sha256","input_decisions_sha256"):sha(m,record[f],f)
 for f in ("parent_submodule_clean","submodule_clean","raw_removed","independent_review"):boolean(m,record[f],f)
 for f,x in (("scanner_exit",1),("adjudication_exit",0),("unknown_decision_count",0),("direct_blob_count",821),("excluded_gitlink_count",3)):integer(m,record[f],f,x,x)
 timestamp(m,record["started_utc"],"started_utc");timestamp(m,record["finished_utc"],"finished_utc");number(m,record["duration_seconds"],"duration_seconds")
 command(m,record["command"])
 expected_command=[PINNED_SCANNER,"dir",".","--config",CANONICAL_REPO+"/.gitleaks.toml","--redact=100","--report-format","json","--report-path",record["command"][9],"--exit-code","1","--no-banner"]
 if record["command"]!=expected_command or re.fullmatch(r"/tmp/m03c-raw-[A-Za-z0-9_-]+/report[.]json",record["command"][9]) is None:fail(m,"schema.run_command")
 if record["parent_submodule"]!=m.PARENT_PREFIX or record["submodule"]!=m.PREFIX:fail(m,"schema.submodule")
 if record["parent_submodule_clean"] is not True or record["submodule_clean"] is not True or record["raw_removed"] is not True or record["independent_review"] is not False:fail(m,"schema.run_flags")
 if record["scanner_version"]!="8.30.1" or record["scanner_sha256"]!=m.SCANNER_SHA256 or record["promotion_gates"]!="open":fail(m,"schema.run_metadata")
 if record["approved_decisions_sha256"]!=digest(e/"decisions.json") or record["input_decisions_sha256"]!=digest(e/"decisions.json"):fail(m,"schema.decision_digest")
 reach=docs["reachability.json"];exact(m,reach["domains"],DOMAINS,"reachability_domains");sha(m,reach["source_manifest_sha256"],"reachability_manifest")
 integer(m,reach["reviewed_path_count"],"reviewed_path_count",22,22)
 if set(reach["domains"].values())!={"absent"} or reach["source_manifest_sha256"]!=record["source_manifest_sha256"]:fail(m,"schema.reachability")
 owned=docs["owned-blobs.json"]["blobs"]
 if not isinstance(owned,list) or len(owned)!=821:fail(m,"schema.owned_blobs")
 observed={}
 for x in owned:
  exact(m,x,{"path","object_id","mode"},"owned_blob");safe_path(m,x["path"],"owned_path");sha(m,x["object_id"],"object_id",40)
  if x["mode"] not in {"100644","100755"} or x["path"] in observed:fail(m,"schema.owned_blob")
  observed[x["path"]]={"object_id":x["object_id"],"mode":x["mode"]}
 expected,_=m.direct_tree(repo,m.PIN)
 if observed!=expected:fail(m,"schema.owned_provenance")
 links=docs["excluded-gitlinks.json"]["gitlinks"]
 if not isinstance(links,list) or len(links)!=3:fail(m,"schema.gitlinks")
 seen={}
 for x in links:
  exact(m,x,{"path","commit"},"gitlink");safe_path(m,x["path"],"gitlink_path");sha(m,x["commit"],"gitlink_commit",40)
  if x["path"] in seen:fail(m,"schema.gitlink_duplicate")
  seen[x["path"]]=x["commit"]
 if seen!=m.CHILD_GITLINKS:fail(m,"schema.gitlink_provenance")
 commands(m,load(m,e/"commands.json"))
 env=docs["environment.json"]
 for f in ("canonical_checkout","evidence_output"):safe_path(m,env[f],f,True)
 for f in ("origin_fetch","origin_push","branch","python_version","gitleaks_version","openssl_version"):safe_text(m,env[f],f,128)
 sha(m,env["head"],"environment_head",40);sha(m,env["gitleaks_sha256"],"gitleaks_hash");sha(m,env["python_sha256"],"python_hash")
 for f in ("parent_submodule_clean","target_submodule_clean"):boolean(m,env[f],f)
 for f in ("dirty_status","recursive_submodules"):
  if not isinstance(env[f],list) or not 1<=len(env[f])<=128:fail(m,"schema."+f)
  for x in env[f]:safe_text(m,x,f,240)
 expected_submodules=[line.strip() for line in m.base.git(repo,"submodule","status","--recursive").decode().splitlines() if line.strip()]
 if env["canonical_checkout"]!=CANONICAL_REPO or env["evidence_output"]!=str(e) or env["origin_fetch"]!=ORIGIN or env["origin_push"]!=ORIGIN or env["branch"]!=BRANCH or env["head"]!=record["head"]:fail(m,"schema.environment_binding")
 if env["parent_submodule_clean"] is not True or env["target_submodule_clean"] is not True or env["recursive_submodules"]!=expected_submodules:fail(m,"schema.environment_state")
 if env["dirty_status"]!=R1_DIRTY_STATUS:fail(m,"binding.dirty_status")
 if env["python_version"]!="Python 3.12.14" or env["gitleaks_version"]!="8.30.1":fail(m,"schema.tool_version")
 changed=docs["changed-files.json"]["paths"]
 if not isinstance(changed,list) or len(changed)!=len(EVIDENCE_CHANGED_FILES) or len(set(changed))!=len(changed):fail(m,"schema.changed_files")
 for x in changed:safe_path(m,x,"changed_path")
 if set(changed)!=EVIDENCE_CHANGED_FILES:fail(m,"schema.changed_files")
 reviewed=docs["reviewed-hashes.json"]
 exact(m,reviewed["files"],REVIEWED_FILES,"reviewed_files")
 exact(m,reviewed["evidence_verification_scripts"],VERIFY,"verification_script_hashes")
 exact(m,reviewed["pinned_binaries"],PINNED_BINARIES,"pinned_binaries")
 for field in ("files","evidence_verification_scripts","pinned_binaries"):
  for k,v in reviewed[field].items():
   safe_text(m,k,"reviewed_hash_key",240);sha(m,v,"reviewed_hash")
 # The R1 package is immutable. Bind the complete reviewed map so a
 # checksum-valid replacement value cannot silently redefine its evidence.
 reviewed_canonical=(json.dumps(reviewed,sort_keys=True,separators=(",",":"))+"\n").encode()
 if hashlib.sha256(reviewed_canonical).hexdigest()!="f587c85c263881d2302514d490f4002a549a7529bd95b1618a12e6bbb305925c":fail(m,"binding.reviewed_hashes")
 expected_source=m.base.source_manifest(repo)
 source=load(m,e/"source-manifest.json",frozenset(expected_source))
 if not isinstance(source,dict) or source!=expected_source:fail(m,"schema.source_manifest")
 for k,v in source.items():safe_path(m,k,"source_path");sha(m,v,"source_hash")
 return {"schema":"m0_3c_r5_validation","checksums":len(ARTIFACTS),"finding_count":158,"decision_count":158,"ledger_count":158,"status":"pass"}
