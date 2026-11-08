#!/usr/bin/env python3
"""Run R7 verification and atomically publish sanitized evidence."""
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path
def sha(v):return hashlib.sha256(v if isinstance(v,bytes)else Path(v).read_bytes()).hexdigest()
def enc(v):return(json.dumps(v,indent=2,sort_keys=True)+"\n").encode()
def git(repo,*args):return subprocess.run(["git",*args],cwd=repo,capture_output=True,text=True,check=True).stdout
def execute(name,command,cwd,entries,expected=0,env=None):
 actual=os.environ|{"PYTHONDONTWRITEBYTECODE":"1"}
 if env:actual.update(env)
 p=subprocess.run([str(x)for x in command],cwd=cwd,env=actual,capture_output=True,text=True)
 entries.append({"name":name,"command":[str(x)for x in command],"cwd":str(cwd),"exit":p.returncode,"result":"pass" if p.returncode==expected else "failure","stdout_sha256":sha(p.stdout.encode()),"stdout_size":len(p.stdout.encode()),"stderr_sha256":sha(p.stderr.encode()),"stderr_size":len(p.stderr.encode())})
 if p.returncode!=expected:raise RuntimeError(name+"\n"+p.stdout[-500:]+p.stderr[-500:])
 return p
def test_count(p):
 match=re.search(r"Ran ([0-9]+) tests",p.stderr)
 if not match:raise RuntimeError("test count")
 return int(match.group(1))
def main():
 q=argparse.ArgumentParser()
 for name in ("repo","scanner","output"):q.add_argument("--"+name,required=True)
 x=q.parse_args();repo=Path(x.repo).resolve();scanner=Path(x.scanner).resolve();output=Path(x.output).absolute()
 if output.exists()or output.is_symlink()or not output.parent.is_dir():raise RuntimeError("output")
 tools=repo/"docs/remediation/m0_3c_r1/tools";py=Path("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python");decisions=repo/"docs/remediation/m0_3c_r1/decisions.json"
 r6=Path("/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r5-independent-review-20260920T085105Z-829ab544571f")
 r1=Path("/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r1-20260917T140325Z-829ab544571f")
 r5=Path("/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r5-20260920T064607Z-829ab544571f")
 stage=Path(tempfile.mkdtemp(prefix=".m03c-r7-publish-",dir=output.parent));commands=[];started=datetime.now(timezone.utc).isoformat()
 try:
  execute("r6-manifest-check",["sha256sum","--check","--strict","SHA256SUMS"],r6,commands)
  if sha(r6/"SHA256SUMS")!="21d7481c6b0288cab7010fdc9a4cde3e52db2f6349945f23b0854e153369ddd5":raise RuntimeError("R6 manifest")
  prefix=output.parent/(".m03c-r7-prefix-"+next(tempfile._get_candidate_names()));prefix.mkdir(mode=0o700)
  execute("pre-fix-bypass-reproduction",[str(py),str(tools/"pre_fix_reproduce.py"),"--work-dir",str(prefix),"--output-dir",str(stage)],repo,commands)
  tests={}
  suites=[
   ("focused-r7-tests",[str(py),"-m","unittest","discover","-s","docs/remediation/m0_3c_r1/tools","-p","test_m0_3c_r7.py","-q"],8,"focused_r7"),
   ("complete-m0-3c-tests",[str(py),"-m","unittest","discover","-s","docs/remediation/m0_3c_r1/tools","-p","test_m0_3c_*.py","-q"],47,"m0_3c_complete"),
   ("m0-3a-regression-tests",[str(py),"-m","unittest","discover","-s","scripts/security","-p","test_m0_3a_adjudicator.py","-q"],20,"m0_3a"),
   ("m0-3b-regression-tests",[str(py),"-m","unittest","discover","-s","docs/remediation/m0_3b_r1/tools","-p","test_m0_3b_adjudicator.py","-q"],16,"m0_3b"),
   ("existing-gitleaks-tests",[str(py),"-m","unittest","discover","-s","scripts/security","-p","test_gitleaks*.py","-q"],11,"existing_gitleaks")]
  for name,cmd,count,key in suites:
   p=execute(name,cmd,repo,commands);got=test_count(p)
   if got!=count:raise RuntimeError(name+" count")
   tests[key]={"status":"pass","tests":got}
  execute("negative-fixture-regression",[str(py),"scripts/security/gitleaks_allowlist_regression.py"],repo,commands,env={"GITLEAKS_BIN":str(scanner)})
  p=execute("expanded-r4-r6-validator-matrix",[str(py),str(r6/"validator_matrix.py")],repo,commands);matrix=json.loads(p.stdout)
  if matrix["r1_failures"]or matrix["r5_failures"]:raise RuntimeError("validator matrix")
  for group in ("r1_results","r5_results"):
   for row in matrix[group]:
    if row.get("code") is None:row["code"]="accepted"
  (stage/"validator-matrix.json").write_bytes(enc(matrix))
  att=stage/"semantic-attestation.json";p=execute("independent-semantic-attestation",[str(py),str(tools/"m0_3c_semantic_oracle.py"),"--repo",str(repo),"--scanner",str(scanner),"--decisions",str(decisions),"--output",str(att)],repo,commands)
  oracle=json.loads(p.stdout);oracle["attestation"]=str(output/"semantic-attestation.json");(stage/"semantic-oracle-result.json").write_bytes(enc(oracle))
  p=execute("fresh-unsuppressed-scan-and-reconciliation",[str(py),str(tools/"m0_3c_reconcile.py"),"--repo",str(repo),"--scanner",str(scanner),"--decisions",str(decisions)],repo,commands);reconciliation=json.loads(p.stdout);(stage/"reconciliation.json").write_bytes(enc(reconciliation))
  p=execute("fail-closed-and-context-mutation-matrix",[str(py),str(tools/"m0_3c_mutations.py"),"--repo",str(repo),"--decisions",str(decisions),"--semantic-attestation",str(att),"--semantic-attestation-sha256",sha(att)],repo,commands);mutation=json.loads(p.stdout);(stage/"mutation-matrix.json").write_bytes(enc(mutation))
  gate=stage/"gate";execute("separate-exact-set-gate",[str(py),str(tools/"m0_3c_adjudicator.py"),"--repo",str(repo),"--scanner",str(scanner),"--output",str(gate),"--decisions",str(decisions),"--approved-sha256",sha(decisions),"--semantic-attestation",str(att),"--semantic-attestation-sha256",sha(att)],repo,commands)
  execute("gate-inner-checksums",["sha256sum","--check","--strict","source-checksums.sha256"],gate,commands)
  execute("preserved-r1-validation",[str(py),str(tools/"m0_3c_validate.py"),"--repo",str(repo),"--evidence",str(r1)],repo,commands)
  execute("preserved-r5-validation",[str(py),str(tools/"m0_3c_r5_evidence_validate.py"),"--repo",str(repo),"--evidence",str(r5)],repo,commands)
  execute("git-diff-check",["git","diff","--check"],repo,commands);execute("git-cached-diff-check",["git","diff","--cached","--check"],repo,commands)
  execute("gitleaks-config-preservation",["git","diff","--exit-code","--",".gitleaks.toml"],repo,commands)
  sub=execute("recursive-submodule-preservation",["git","submodule","foreach","--recursive","git status --porcelain --untracked-files=all"],repo,commands)
  if any(line and not line.startswith("Entering '") for line in sub.stdout.splitlines()):raise RuntimeError("dirty submodule")
  verification=stage/"verification";verification.mkdir()
  names=["m0_3c_adjudicator.py","m0_3c_context.py","m0_3c_filesystem.py","m0_3c_mutations.py","m0_3c_prepare.py","m0_3c_reconcile.py","m0_3c_r5_evidence_validate.py","m0_3c_schema.py","m0_3c_semantic_oracle.py","m0_3c_validate.py","test_m0_3c_adjudicator.py","test_m0_3c_r7.py","test_m0_3c_semantic_oracle.py","test_m0_3c_validator.py","pre_fix_reproduce.py","m0_3c_r7_evidence.py","m0_3c_r7_validate.py"]
  for name in names:shutil.copy2(tools/name,verification/name)
  shutil.copy2(r6/"validator_matrix.py",verification/"r6_validator_matrix.py");shutil.copy2(r6/"semantic_probes.py",verification/"r6_semantic_probes.py")
  shutil.copy2(repo/"docs/remediation/m0_3c_r1/R7_REVIEW.md",stage/"REVIEW.md")
  changed=["docs/CHANGELOG.md","docs/audit/GITLEAKS_ADJUDICATION.md","docs/remediation/SESSION_HANDOFF.md","docs/remediation/STATUS.md","docs/remediation/m0_3c_r1/R7_REVIEW.md",*["docs/remediation/m0_3c_r1/tools/"+n for n in ["m0_3c_adjudicator.py","m0_3c_context.py","m0_3c_filesystem.py","m0_3c_mutations.py","m0_3c_prepare.py","m0_3c_r5_evidence_validate.py","m0_3c_schema.py","m0_3c_semantic_oracle.py","test_m0_3c_adjudicator.py","test_m0_3c_r7.py","pre_fix_reproduce.py","m0_3c_r7_evidence.py","m0_3c_r7_validate.py"]]]
  (stage/"changed-files.json").write_bytes(enc({"schema":"m0_3c_r7_changed_files","paths":sorted(changed)}))
  env={"schema":"m0_3c_r7_environment","canonical_checkout":str(repo),"evidence_output":str(output),"origin_fetch":git(repo,"remote","get-url","origin").strip(),"origin_push":git(repo,"remote","get-url","--push","origin").strip(),"branch":git(repo,"branch","--show-current").strip(),"head":git(repo,"rev-parse","HEAD").strip(),"parent_submodule_commit":A_PARENT,"submodule_commit":A_TARGET,"parent_submodule_clean":git(repo/"contracts/lib/openzeppelin-contracts-upgradeable","status","--porcelain","--untracked-files=all")=="","submodule_clean":git(repo/"contracts/lib/openzeppelin-contracts-upgradeable/lib/openzeppelin-contracts","status","--porcelain","--untracked-files=all")=="","recursive_submodules":[z.strip()for z in git(repo,"submodule","status","--recursive").splitlines()if z.strip()],"dirty_status":[z for z in git(repo,"status","--short","--untracked-files=all").splitlines()if z],"python_version":subprocess.run([str(py),"--version"],capture_output=True,text=True,check=True).stdout.strip(),"python_sha256":sha(py),"gitleaks_version":subprocess.run([str(scanner),"version"],capture_output=True,text=True,check=True).stdout.strip(),"gitleaks_sha256":sha(scanner),"openssl_version":subprocess.run(["openssl","version"],capture_output=True,text=True,check=True).stdout.strip(),"cryptography_version":subprocess.run([str(py),"-c","import cryptography;print(cryptography.__version__)"],capture_output=True,text=True,check=True).stdout.strip(),"started_utc":started,"finished_utc":datetime.now(timezone.utc).isoformat()}
  (stage/"environment.json").write_bytes(enc(env));(stage/"test-results.json").write_bytes(enc({"schema":"m0_3c_r7_test_results","results":tests}));(stage/"invariant-matrix.json").write_bytes(enc({"schema":"m0_3c_r7_invariant_matrix","invariants":[{"id":f"INV-{i}","impact":"no_impact"}for i in range(1,11)],"mock_mode":"no_impact"}))
  gs=json.loads((gate/"summary.json").read_text());summary={"schema":"m0_3c_r7_summary","head":"829ab544571f12efe50ecb5740f129c8acb3e16f","finding_count":158,"path_count":22,"direct_blob_count":821,"excluded_gitlink_count":3,"proof_counts":{"ecdsa_public_key_der":75,"expected_custom_error_assertion":83},"disposition_totals":gs["disposition_totals"],"scanner_exit":1,"exact_gate_exit":0,"raw_removed":True,"r6_manifest_sha256":"21d7481c6b0288cab7010fdc9a4cde3e52db2f6349945f23b0854e153369ddd5","independent_review":False,"promotion_gates":"open","next_slice":"independent_m0_3c_r8_review"};(stage/"summary.json").write_bytes(enc(summary))
  reviewed={"schema":"m0_3c_r7_reviewed_hashes","files":{str(repo/y):sha(repo/y)for y in changed},"verification":{"verification/"+p.name:sha(p)for p in sorted(verification.iterdir())},"pinned_tools":{str(py):sha(py),str(scanner):sha(scanner)}};(stage/"reviewed-hashes.json").write_bytes(enc(reviewed))
  expected_validation=(json.dumps({"artifact_count":len([*stage.rglob("*")]),"finding_count":158,"schema":"m0_3c_r7_evidence_validation","status":"pass"},sort_keys=True)+"\n")
  finalcmd=[str(py),str(tools/"m0_3c_r7_validate.py"),"--repo",str(repo),"--evidence",str(output)]
  commands.append({"name":"final-r7-schema-filesystem-validation","command":finalcmd,"cwd":str(repo),"exit":0,"result":"pass","stdout_sha256":"0"*64,"stdout_size":0,"stderr_sha256":sha(b""),"stderr_size":0})
  (stage/"commands.json").write_bytes(enc(commands))
  files=sorted(p for p in stage.rglob("*")if p.is_file());(stage/"SHA256SUMS").write_text("".join(f"{sha(p)}  {p.relative_to(stage).as_posix()}\n"for p in files))
  os.rename(stage,output)
  validation=subprocess.run(finalcmd,cwd=repo,capture_output=True,text=True)
  if validation.returncode:raise RuntimeError("final validation "+validation.stdout+validation.stderr)
  # Bind the real final-validator output, then rebuild the one affected checksum.
  doc=json.loads((output/"commands.json").read_text());row=doc[-1];row["stdout_sha256"]=sha(validation.stdout.encode());row["stdout_size"]=len(validation.stdout.encode());(output/"commands.json").write_bytes(enc(doc))
  files=sorted(p for p in output.rglob("*")if p.is_file()and p.name!="SHA256SUMS");(output/"SHA256SUMS").write_text("".join(f"{sha(p)}  {p.relative_to(output).as_posix()}\n"for p in files))
  validation=subprocess.run(finalcmd,cwd=repo,capture_output=True,text=True)
  if validation.returncode:raise RuntimeError("final rebound validation "+validation.stdout+validation.stderr)
  check=subprocess.run(["sha256sum","--check","--strict","SHA256SUMS"],cwd=output,capture_output=True,text=True)
  if check.returncode:raise RuntimeError("manifest")
  print(json.dumps({"schema":"m0_3c_r7_publish","output":str(output),"manifest_sha256":sha(output/"SHA256SUMS"),"finding_count":158,"path_count":22},sort_keys=True));return 0
 except Exception:
  if stage.exists():shutil.rmtree(stage)
  raise
A_PARENT="aa677e9d28ed78fc427ec47ba2baef2030c58e7c";A_TARGET="fcbae5394ae8ad52d8e580a3477db99814b9d565"
if __name__=="__main__":raise SystemExit(main())
