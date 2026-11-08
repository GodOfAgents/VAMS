#!/usr/bin/env python3
"""Run M0.3c-R5 verification and atomically publish sanitized evidence."""
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path
def h(v):return hashlib.sha256(v if isinstance(v,bytes)else Path(v).read_bytes()).hexdigest()
def enc(v):return(json.dumps(v,indent=2,sort_keys=True)+"\n").encode()
def git(r,*a):return subprocess.run(["git",*a],cwd=r,capture_output=True,text=True,check=True).stdout
def run(name,cmd,cwd,entries,expected=0,env=None,result="pass"):
 e=os.environ|{"PYTHONDONTWRITEBYTECODE":"1"}
 if env:e.update(env)
 p=subprocess.run([str(x)for x in cmd],cwd=cwd,env=e,capture_output=True,text=True)
 entries.append({"name":name,"command":[str(x)for x in cmd],"cwd":str(cwd),
 "exit":p.returncode,"result":result,"stdout_sha256":h(p.stdout.encode()),
 "stdout_size":len(p.stdout.encode()),"stderr_sha256":h(p.stderr.encode()),
 "stderr_size":len(p.stderr.encode())})
 if p.returncode!=expected:raise RuntimeError(name)
 return p
def main():
 a=argparse.ArgumentParser()
 for x in("repo","scanner","output","pre-reproduction-dir"):a.add_argument("--"+x,required=True)
 x=a.parse_args();repo=Path(x.repo).resolve();scanner=Path(x.scanner).resolve()
 output=Path(x.output).absolute();pre=Path(x.pre_reproduction_dir).resolve()
 if output.exists()or output.is_symlink()or not output.parent.is_dir():raise RuntimeError("output")
 tools=repo/"docs/remediation/m0_3c_r1/tools"
 py=Path("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python")
 decisions=repo/"docs/remediation/m0_3c_r1/decisions.json"
 r1=Path("/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r1-20260917T140325Z-829ab544571f")
 r4=Path("/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r3-independent-review-20260918T102922Z-829ab544571f")
 stage=Path(tempfile.mkdtemp(prefix=".m03c-r5-publish-",dir=output.parent));commands=[];started=datetime.now(timezone.utc).isoformat()
 try:
  p=run("r4-manifest-check",["sha256sum","--check","--strict","SHA256SUMS"],r4,commands)
  if h(r4/"SHA256SUMS")!="c2f74e04c89184195c962e266f3485ed59070a0515f51514e7a785bac58bb1bc":raise RuntimeError("r4 hash")
  focused=[str(py),"-m","unittest","-q",
   "docs/remediation/m0_3c_r1/tools/test_m0_3c_adjudicator.py",
   "docs/remediation/m0_3c_r1/tools/test_m0_3c_validator.py",
   "docs/remediation/m0_3c_r1/tools/test_m0_3c_semantic_oracle.py"]
  p=run("focused-m0-3c-r5-tests",focused,repo,commands);n=int(re.search(r"Ran ([0-9]+) tests",p.stderr).group(1))
  if n!=39:raise RuntimeError("focused count")
  tests={"focused_m0_3c_r5":{"status":"pass","tests":n}}
  p=run("validator-53-case-matrix",[str(py),str(tools/"m0_3c_r5_validator_matrix.py"),
   "--repo",str(repo),"--evidence",str(r1),"--python",str(py),
   "--validator",str(tools/"m0_3c_validate.py")],repo,commands)
  matrix=json.loads(p.stdout)
  if matrix["case_count"]!=53 or matrix["expectation_failure_count"]!=0:raise RuntimeError("matrix")
  (stage/"validator-53-case-results.json").write_bytes(enc(matrix))
  suites=[
   ("m0-3a-regression-tests",["discover","-s","scripts/security","-p","test_m0_3a_adjudicator.py","-q"],20,"m0_3a"),
   ("m0-3b-regression-tests",["discover","-s","docs/remediation/m0_3b_r1/tools","-p","test_m0_3b_adjudicator.py","-q"],16,"m0_3b"),
   ("existing-gitleaks-tests",["discover","-s","scripts/security","-p","test_gitleaks*.py","-q"],11,"existing_gitleaks")]
  for name,args,count,key in suites:
   p=run(name,[str(py),"-m","unittest",*args],repo,commands);got=int(re.search(r"Ran ([0-9]+) tests",p.stderr).group(1))
   if got!=count:raise RuntimeError(name+" count")
   tests[key]={"status":"pass","tests":got}
  run("negative-fixture-regression",[str(py),"scripts/security/gitleaks_allowlist_regression.py"],repo,commands,env={"GITLEAKS_BIN":str(scanner)})
  att=stage/"semantic-attestation.json"
  p=run("independent-semantic-attestation",[str(py),str(tools/"m0_3c_semantic_oracle.py"),
   "--repo",str(repo),"--scanner",str(scanner),"--decisions",str(decisions),
   "--output",str(att)],repo,commands)
  oracle=json.loads(p.stdout);oracle["attestation"]=str(output/"semantic-attestation.json")
  (stage/"semantic-oracle-result.json").write_bytes(enc(oracle))
  p=run("fresh-independent-reconciliation",[str(py),str(tools/"m0_3c_reconcile.py"),
   "--repo",str(repo),"--scanner",str(scanner),"--decisions",str(decisions)],repo,commands)
  reconciliation=json.loads(p.stdout);(stage/"reconciliation.json").write_bytes(enc(reconciliation))
  p=run("fail-closed-mutation-matrix",[str(py),str(tools/"m0_3c_mutations.py"),
   "--repo",str(repo),"--decisions",str(decisions),"--semantic-attestation",str(att),
   "--semantic-attestation-sha256",h(att)],repo,commands)
  mutation=json.loads(p.stdout);(stage/"mutation-matrix.json").write_bytes(enc(mutation))
  gate=stage/"gate";approved=h(decisions)
  run("dual-proof-exact-set-gate",[str(py),str(tools/"m0_3c_adjudicator.py"),
   "--repo",str(repo),"--scanner",str(scanner),"--output",str(gate),
   "--decisions",str(decisions),"--approved-sha256",approved,
   "--semantic-attestation",str(att),"--semantic-attestation-sha256",h(att)],repo,commands)
  record=json.loads((gate/"record.json").read_text());gs=json.loads((gate/"summary.json").read_text())
  if record["adjudication_exit"]!=0 or gs["disposition_totals"]!={"confirmed_noncredential_fixture":158,"potential_credential":0,"unresolved":0}:raise RuntimeError("gate")
  run("gate-inner-checksums",["sha256sum","--check","--strict","source-checksums.sha256"],gate,commands)
  p=run("preserved-r1-schema-validation",[str(py),str(tools/"m0_3c_validate.py"),
   "--repo",str(repo),"--evidence",str(r1)],repo,commands)
  if json.loads(p.stdout)["status"]!="pass":raise RuntimeError("r1 schema")
  for name,cmd in [
   ("git-diff-check",["git","diff","--check"]),
   ("git-cached-diff-check",["git","diff","--cached","--check"]),
   ("gitleaks-config-preservation",["git","diff","--exit-code","--",".gitleaks.toml"]),
   ("recursive-submodule-preservation",["git","submodule","foreach","--recursive","git status --porcelain --untracked-files=all"])]:
   run(name,cmd,repo,commands)
  for name in("pre-r5-checksum-short-circuit.json","pre-r5-reproduction-summary.json",
   "pre-r5-semantic-adversarial.json","pre-r5-validator-adversarial.json"):
   shutil.copy2(pre/name,stage/name)
  verification=stage/"verification";verification.mkdir()
  names=["m0_3c_adjudicator.py","m0_3c_mutations.py","m0_3c_reconcile.py",
   "m0_3c_r5_evidence.py","m0_3c_r5_evidence_validate.py",
   "m0_3c_r5_validator_matrix.py","m0_3c_schema.py","m0_3c_semantic_oracle.py",
   "m0_3c_validate.py","test_m0_3c_adjudicator.py",
   "test_m0_3c_semantic_oracle.py","test_m0_3c_validator.py"]
  for name in names:shutil.copy2(tools/name,verification/name)
  shutil.copy2(pre/"pre_checksum_short_circuit.py",verification/"pre_checksum_short_circuit.py")
  shutil.copy2(repo/"docs/remediation/m0_3c_r1/R5_REVIEW.md",stage/"REVIEW.md")
  changed=["docs/CHANGELOG.md","docs/audit/GITLEAKS_ADJUDICATION.md",
   "docs/remediation/SESSION_HANDOFF.md","docs/remediation/STATUS.md",
   "docs/remediation/m0_3c_r1/R5_REVIEW.md",
   *["docs/remediation/m0_3c_r1/tools/"+n for n in [
   "m0_3c_adjudicator.py","m0_3c_mutations.py","m0_3c_r5_evidence.py",
   "m0_3c_r5_evidence_validate.py","m0_3c_r5_validator_matrix.py","m0_3c_schema.py",
   "m0_3c_semantic_oracle.py","m0_3c_validate.py","test_m0_3c_adjudicator.py",
   "test_m0_3c_semantic_oracle.py","test_m0_3c_validator.py"]]]
  if len(changed)!=len(set(changed)):raise RuntimeError("changed duplicate")
  environment={"schema":"m0_3c_r5_environment","canonical_checkout":str(repo),
   "evidence_output":str(output),"origin_fetch":git(repo,"remote","get-url","origin").strip(),
   "origin_push":git(repo,"remote","get-url","--push","origin").strip(),
   "branch":git(repo,"branch","--show-current").strip(),"head":git(repo,"rev-parse","HEAD").strip(),
   "parent_submodule_commit":m_pin(repo,"contracts/lib/openzeppelin-contracts-upgradeable"),
   "submodule_commit":"fcbae5394ae8ad52d8e580a3477db99814b9d565",
   "parent_submodule_clean":git(repo/"contracts/lib/openzeppelin-contracts-upgradeable","status","--porcelain","--untracked-files=all")=="",
   "submodule_clean":git(repo/"contracts/lib/openzeppelin-contracts-upgradeable/lib/openzeppelin-contracts","status","--porcelain","--untracked-files=all")=="",
   "recursive_submodules":[z.strip()for z in git(repo,"submodule","status","--recursive").splitlines()if z.strip()],
   "dirty_status":[z for z in git(repo,"status","--short").splitlines()if z],
   "python_version":subprocess.run([str(py),"--version"],capture_output=True,text=True,check=True).stdout.strip(),
   "python_sha256":h(py),"gitleaks_version":subprocess.run([str(scanner),"version"],capture_output=True,text=True,check=True).stdout.strip(),
   "gitleaks_sha256":h(scanner),"openssl_version":subprocess.run(["openssl","version"],capture_output=True,text=True,check=True).stdout.strip(),
   "cryptography_version":subprocess.run([str(py),"-c","import cryptography;print(cryptography.__version__)"],capture_output=True,text=True,check=True).stdout.strip(),
   "started_utc":started,"finished_utc":datetime.now(timezone.utc).isoformat()}
  (stage/"environment.json").write_bytes(enc(environment))
  (stage/"changed-files.json").write_bytes(enc({"schema":"m0_3c_r5_changed_files","paths":sorted(changed)}))
  (stage/"test-results.json").write_bytes(enc({"schema":"m0_3c_r5_test_results","results":tests}))
  (stage/"invariant-matrix.json").write_bytes(enc({"schema":"m0_3c_r5_invariant_matrix",
   "invariants":[{"id":f"INV-{i}","impact":"no_impact"}for i in range(1,11)],"mock_mode":"no_impact"}))
  summary={"schema":"m0_3c_r5_summary","head":"829ab544571f12efe50ecb5740f129c8acb3e16f",
   "finding_count":158,"path_count":22,"direct_blob_count":821,"excluded_gitlink_count":3,
   "proof_counts":{"ecdsa_public_key_der":75,"expected_custom_error_assertion":83},
   "disposition_totals":gs["disposition_totals"],"scanner_exit":1,"exact_gate_exit":0,
   "raw_removed":True,"validator_case_count":53,
   "r4_manifest_sha256":"c2f74e04c89184195c962e266f3485ed59070a0515f51514e7a785bac58bb1bc",
   "independent_review":False,"promotion_gates":"open","next_slice":"independent_m0_3c_r6_review"}
  (stage/"summary.json").write_bytes(enc(summary))
  reviewed={"schema":"m0_3c_r5_reviewed_hashes",
   "files":{str(repo/y):h(repo/y)for y in changed},
   "verification":{"verification/"+y:h(verification/y)for y in sorted(z.name for z in verification.iterdir())},
   "pinned_tools":{str(py):h(py),str(scanner):h(scanner)}}
  (stage/"reviewed-hashes.json").write_bytes(enc(reviewed))
  valout=(json.dumps({"artifact_count":40,"finding_count":158,
   "schema":"m0_3c_r5_evidence_validation","status":"pass","validator_cases":53},sort_keys=True)+"\n")
  finalcmd=[str(py),str(tools/"m0_3c_r5_evidence_validate.py"),"--repo",str(repo),"--evidence",str(output)]
  commands.append({"name":"final-schema-validation","command":finalcmd,"cwd":str(repo),"exit":0,
   "result":"pass","stdout_sha256":h(valout.encode()),"stdout_size":len(valout.encode()),
   "stderr_sha256":h(b""),"stderr_size":0})
  manifestcmd=["sha256sum","--check","--strict","SHA256SUMS"]
  names_for_manifest=sorted([p.relative_to(stage).as_posix()for p in stage.rglob("*")if p.is_file()]+["commands.json"])
  manifest_stdout="".join(name+": OK\n"for name in names_for_manifest)
  commands.append({"name":"final-manifest-check","command":manifestcmd,"cwd":str(output),"exit":0,
   "result":"pass","stdout_sha256":h(manifest_stdout.encode()),"stdout_size":len(manifest_stdout.encode()),
   "stderr_sha256":h(b""),"stderr_size":0})
  (stage/"commands.json").write_bytes(enc(commands))
  files=sorted(p for p in stage.rglob("*")if p.is_file())
  (stage/"SHA256SUMS").write_text("".join(f"{h(p)}  {p.relative_to(stage).as_posix()}\n"for p in files))
  os.rename(stage,output)
  try:
   p=subprocess.run(finalcmd,cwd=repo,capture_output=True,text=True)
   if p.returncode or p.stdout!=valout or p.stderr:raise RuntimeError("final validation "+p.stdout+p.stderr)
   p=subprocess.run(manifestcmd,cwd=output,capture_output=True,text=True)
   if p.returncode or p.stdout!=manifest_stdout or p.stderr:raise RuntimeError("final manifest")
  except Exception:
   os.rename(output,stage);raise
  print(json.dumps({"schema":"m0_3c_r5_publish","output":str(output),
   "manifest_sha256":h(output/"SHA256SUMS"),"finding_count":158,"path_count":22,
   "focused_tests":39,"validator_cases":53},sort_keys=True));return 0
 except Exception:
  if stage.exists():shutil.rmtree(stage)
  raise
def m_pin(repo,path):
 parts=git(repo,"ls-tree","HEAD","--",path).split()
 if len(parts)!=4 or parts[0]!="160000":raise RuntimeError("gitlink")
 return parts[2]
if __name__=="__main__":raise SystemExit(main())
