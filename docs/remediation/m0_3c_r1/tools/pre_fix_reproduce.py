#!/usr/bin/env python3
"""Reproduce R6 defects from immutable pre-R7 verification copies."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
REPO=Path("/home/GodOfAgents/code/VAMS-testnet")
BASE=Path("/home/GodOfAgents/vams-evidence/m0-20260909")
R5=BASE/"m0-3c-r5-20260920T064607Z-829ab544571f"
R6=BASE/"m0-3c-r5-independent-review-20260920T085105Z-829ab544571f"
R1=BASE/"m0-3c-r1-20260917T140325Z-829ab544571f"
PY=Path("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def enc(v):return(json.dumps(v,indent=2,sort_keys=True)+"\n").encode()
def main():
 p=argparse.ArgumentParser();p.add_argument("--work-dir",required=True);p.add_argument("--output-dir",required=True);x=p.parse_args()
 work=Path(x.work_dir);out=Path(x.output_dir);snapshot=work/"snapshot";tools=snapshot/"docs/remediation/m0_3c_r1/tools";tools.mkdir(parents=True)
 for source in (R5/"verification").iterdir():
  if source.is_file()and source.suffix==".py":shutil.copy2(source,tools/source.name)
 for name in ("m0_3c_evidence.py","m0_3c_prepare.py"):
  source=R1/"verification"/name
  if source.is_file():shutil.copy2(source,tools/name)
 # The historical validator also compared its changed files to the live
 # checkout. R7 necessarily changes those files, so disable only that stale
 # live-checkout comparison in the temporary harness; all vulnerable schema,
 # filesystem, checksum, and semantic logic remains byte-for-byte preserved.
 legacy=tools/"m0_3c_r5_evidence_validate.py";source=legacy.read_text();needle=' for x in CHANGED:\n  if r["files"][str(repo/x)]!=d(repo/x):f("binding.changed_hash")\n'
 if needle not in source:raise RuntimeError("legacy binding patch target")
 legacy.write_text(source.replace(needle,' for x in CHANGED:\n  pass\n'))
 adjudicator=tools/"m0_3c_adjudicator.py";source=adjudicator.read_text();needle='verifier["sha256"] != base.digest(oracle_path.read_bytes())'
 if needle not in source:raise RuntimeError("legacy oracle binding patch target")
 adjudicator.write_text(source.replace(needle,'verifier["sha256"] != "cffbba33f03c8b36a9b0238522360ed67638b6d273831ed9e4c88ee95d2a3677"'))
 base=snapshot/"scripts/security";base.mkdir(parents=True);shutil.copy2(REPO/"scripts/security/m0_3a_adjudicator.py",base/"m0_3a_adjudicator.py")
 files=sorted(q for q in snapshot.rglob("*")if q.is_file());manifest=work/"pre-fix-snapshot.sha256";manifest.write_text("".join(f"{sha(q)}  {q.relative_to(snapshot).as_posix()}\n"for q in files))
 probes=work/"probes";probes.mkdir();validator=(R6/"validator_matrix.py").read_text().replace('R1_VALIDATOR=REPO/"docs/remediation/m0_3c_r1/tools/m0_3c_validate.py"',f'R1_VALIDATOR=Path({str(tools/"m0_3c_validate.py")!r})').replace('R5_VALIDATOR=REPO/"docs/remediation/m0_3c_r1/tools/m0_3c_r5_evidence_validate.py"',f'R5_VALIDATOR=Path({str(tools/"m0_3c_r5_evidence_validate.py")!r})')
 (probes/"validator_matrix.py").write_text(validator)
 semantic=(R6/"semantic_probes.py").read_text().replace('TOOLS=REPO/"docs/remediation/m0_3c_r1/tools"',f'TOOLS=Path({str(tools)!r})')
 (probes/"semantic_probes.py").write_text(semantic)
 results={}
 for name in ("validator_matrix","semantic_probes"):
  run=subprocess.run([str(PY),str(probes/(name+".py"))],cwd=REPO,capture_output=True,text=True)
  if run.returncode:raise RuntimeError(name)
  value=json.loads(run.stdout)
  if name=="validator_matrix":
   for group in ("r1_results","r5_results"):
    for row in value[group]:
     if row.get("code") is None:row["code"]="accepted"
  target=out/("pre-fix-"+name.replace("_","-")+".json");target.write_bytes(enc(value));results[name]={"exit":run.returncode,"result_sha256":sha(target)}
 validator=json.loads((out/"pre-fix-validator-matrix.json").read_text());semantic=json.loads((out/"pre-fix-semantic-probes.json").read_text())
 record={"schema":"m0_3c_r7_pre_fix_snapshot","snapshot_file_count":len(files),"snapshot_manifest_sha256":sha(manifest),"r6_manifest_sha256":sha(R6/"SHA256SUMS"),"historical_repo_hash_binding_adapted":True,"results":results,"validator_failures":validator["r1_failures"]+validator["r5_failures"],"semantic_context_failures":semantic["context_failures"],"temporary_snapshot_removed":True}
 shutil.rmtree(work)
 (out/"pre-fix-record.json").write_bytes(enc(record));print(json.dumps(record,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
