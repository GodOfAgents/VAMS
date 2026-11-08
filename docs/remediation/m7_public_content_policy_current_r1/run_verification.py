from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path("/home/GodOfAgents/code/VAMS-testnet")
outdir=root/"docs/remediation/m7_public_content_policy_current_r1"
excluded=outdir.relative_to(root).as_posix()+"/"
python="/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
env={"PATH":"/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1"}
def path_inventory():
    listing=subprocess.check_output(["git","ls-files","-z","--cached","--others","--exclude-standard"],cwd=root)
    names=sorted(raw.decode("utf-8","ignore").replace("\\","/") for raw in listing.split(b"\0") if raw)
    names=[name for name in names if not name.startswith(excluded)]
    packed="\0".join(names).encode()
    return {"count":len(names),"sha256":hashlib.sha256(packed).hexdigest(),"excludes_evidence_package":excluded}
before=path_inventory()
argv=[python,"-B","scripts/security/public_content_policy_scan.py"]
p=subprocess.run(argv,cwd=root,env=env,text=True,capture_output=True,check=False)
after=path_inventory()
head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
summary=p.stdout.splitlines()[0] if p.stdout.splitlines() else ""
count=sum(1 for line in p.stdout.splitlines() if line.startswith("  - "))
result={"schema":"m7-public-content-policy-current-v1","date":"2026-10-03","git_head":head,"python":sys.version.split()[0],"command":argv,"exit_code":p.returncode,"summary":summary,"finding_count":count,"stdout_sha256":hashlib.sha256(p.stdout.encode()).hexdigest(),"stderr_sha256":hashlib.sha256(p.stderr.encode()).hexdigest(),"raw_output_retained":False,"path_inventory_before":before,"path_inventory_after":after,"path_inventory_unchanged":before==after}
(outdir/"RESULT.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
