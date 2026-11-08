from __future__ import annotations
import hashlib, json, os, runpy, subprocess, sys
from pathlib import Path

root=Path("/home/GodOfAgents/code/VAMS-testnet")
outdir=root/"docs/remediation/m7_mock_mode_promotion_current_r1"
scanner=root/"scripts/security/mock_mode_promotion_scan.py"
def inventory():
    guard_map=runpy.run_path(str(scanner))["REQUIRED_GUARDS"]
    rows=[]
    for rel in sorted(guard_map):
        p=root/rel
        raw=p.read_bytes()
        rows.append((rel,hashlib.sha256(raw).hexdigest()))
    packed="".join(f"{path}\0{digest}\n" for path,digest in rows).encode()
    return {"count":len(rows),"sha256":hashlib.sha256(packed).hexdigest(),"files":rows}
before=inventory()
env={"PATH":"/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1"}
argv=["/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python","-B","scripts/security/mock_mode_promotion_scan.py"]
p=subprocess.run(argv,cwd=root,env=env,text=True,capture_output=True,check=False)
after=inventory()
git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
branch=subprocess.check_output(["git","branch","--show-current"],cwd=root,text=True).strip()
result={
 "schema":"m7-mock-mode-promotion-current-v1",
 "command":argv,
 "exit_code":p.returncode,
 "stdout":p.stdout,
 "stderr":p.stderr,
 "source_inventory_before":before,
 "source_inventory_after":after,
 "source_inventory_unchanged":before==after,
 "scanner_sha256":hashlib.sha256(scanner.read_bytes()).hexdigest(),
 "runner_python":sys.version.split()[0],
 "git_head":git_head,
 "branch":branch
}
(outdir/"RESULT.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
