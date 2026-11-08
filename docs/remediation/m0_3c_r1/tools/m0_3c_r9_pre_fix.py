#!/usr/bin/env python3
"""Reproduce R8 lifecycle and shared-catalog defects from preserved pre-R9 copies."""
import argparse,hashlib,importlib.util,json,os,shutil,sys,tempfile
from pathlib import Path
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def enc(v):return (json.dumps(v,sort_keys=True,indent=2)+"\n").encode()
def main():
 p=argparse.ArgumentParser();p.add_argument("--pre-fix-dir",required=True);p.add_argument("--evidence",required=True);a=p.parse_args()
 pre=Path(a.pre_fix_dir);source=Path(a.evidence);sys.path.insert(0,str(pre))
 F=module("m0_3c_filesystem",pre/"m0_3c_filesystem.py");A=module("m0_3c_adjudicator",pre/"m0_3c_adjudicator.py");V=module("pre_r9_validator",pre/"m0_3c_r7_validate.py")
 results=[];baseline_inspect=F.inspect_exact_tree;baseline_digest=V.digest;baseline_semantic=A.validate_semantic_attestation
 with tempfile.TemporaryDirectory(prefix="m03c-r9-prefixed-race-") as td:
  for name,kind in (("inode_replacement","replace"),("same_inode_write","write")):
   root=Path(td)/name;shutil.copytree(source,root)
   env=json.loads((root/"environment.json").read_text());env["evidence_output"]=str(root);(root/"environment.json").write_bytes(enc(env))
   oracle=json.loads((root/"semantic-oracle-result.json").read_text());oracle["attestation"]=str(root/"semantic-attestation.json");(root/"semantic-oracle-result.json").write_bytes(enc(oracle))
   reviewed=json.loads((root/"reviewed-hashes.json").read_text())
   def rebuild():
    (root/"SHA256SUMS").write_text("".join(hashlib.sha256((root/n).read_bytes()).hexdigest()+"  "+n+"\n" for n in sorted(V.ART)))
   rebuild();original_inspect=baseline_inspect
   def race(r,allowed,manifest_name="SHA256SUMS"):
    observed=original_inspect(r,allowed,manifest_name);target=Path(r)/"commands.json";doc=json.loads(target.read_text());doc[0]["stdout_size"]+=1;raw=enc(doc)
    if kind=="replace":
     q=target.with_name(".replacement");q.write_bytes(raw);os.replace(q,target)
    else:target.write_bytes(raw)
    return observed
   original_digest=baseline_digest
   def historical_digest(path):
    path=Path(path)
    if root==path or root in path.parents:return original_digest(path)
    return reviewed.get("files",{}).get(str(path),original_digest(path))
   records=json.loads((root/"semantic-attestation.json").read_text())["records"]
   F.inspect_exact_tree=race;V.F.inspect_exact_tree=race;V.digest=historical_digest;V.A.validate_semantic_attestation=lambda *x,**y:{r["finding_id"]:r for r in records}
   try:
    accepted=V.validate(V.REPO,root)["status"]=="pass"
   except Exception:accepted=False
   results.append({"name":name,"historical_validator_accepted":accepted})
 import ast
 def constants(path,names):
  out={}
  for node in ast.parse(path.read_text()).body:
   if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in names:out[node.targets[0].id]=ast.literal_eval(node.value)
  return out
 prod=constants(pre/"m0_3c_context.py",{"ERROR_POLICY","TARGETS"});oracle=constants(pre/"m0_3c_semantic_oracle.py",{"ORACLE_ERROR_POLICY","ORACLE_TARGETS"})
 result={"schema":"m0_3c_r9_pre_fix_reproduction","race_results":results,"both_races_accepted":all(x["historical_validator_accepted"] for x in results),"shared_catalog_dependency":{"error_policy_equal":prod.get("ERROR_POLICY")==oracle.get("ORACLE_ERROR_POLICY"),"targets_equal":prod.get("TARGETS")==oracle.get("ORACLE_TARGETS")},"temporary_copies_removed":True}
 print(json.dumps(result,sort_keys=True));return 0 if result["both_races_accepted"] and all(result["shared_catalog_dependency"].values()) else 1
if __name__=="__main__":raise SystemExit(main())
