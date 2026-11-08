from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path("/home/GodOfAgents/code/VAMS-testnet")
outdir=root/"docs/remediation/m7_docs_reality_current_r1"
excluded=outdir.relative_to(root).as_posix()+"/"
python="/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
env={"PATH":"/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1"}
def inventory():
    listing=subprocess.check_output(["git","ls-files","-z","--cached","--others","--exclude-standard"],cwd=root)
    rows=[]
    for raw in listing.split(b"\0"):
        if not raw: continue
        name=raw.decode("utf-8","ignore")
        if name.startswith(excluded): continue
        p=root/name
        if p.is_file(): rows.append((name,hashlib.sha256(p.read_bytes()).hexdigest()))
    packed="".join(f"{n}\0{h}\n" for n,h in sorted(rows)).encode()
    return {"count":len(rows),"sha256":hashlib.sha256(packed).hexdigest(),"excludes_evidence_package":excluded}
before=inventory()
commands=[("validate_docs",[python,"-B","scripts/docs/validate_docs.py"]),("focused_unittest",[python,"-B","-m","unittest","scripts/docs/test_validate_docs.py"])]
results=[]
for label,argv in commands:
    p=subprocess.run(argv,cwd=root,env=env,text=True,capture_output=True,check=False)
    lines=(p.stdout+"\n"+p.stderr).splitlines()
    summaries=[line.strip() for line in lines if "passed." in line or line.strip()=="OK" or line.strip().startswith("Ran ")]
    results.append({"name":label,"argv":argv,"exit_code":p.returncode,"summary_lines":summaries,"stdout_sha256":hashlib.sha256(p.stdout.encode()).hexdigest(),"stderr_sha256":hashlib.sha256(p.stderr.encode()).hexdigest(),"raw_output_retained":False})
after=inventory()
head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
(outdir/"RESULT.json").write_text(json.dumps({"schema":"m7-docs-reality-current-v1","date":"2026-10-03","git_head":head,"python":sys.version.split()[0],"inventory_before":before,"inventory_after":after,"inventory_unchanged":before==after,"commands":results},indent=2,sort_keys=True)+"\n")
