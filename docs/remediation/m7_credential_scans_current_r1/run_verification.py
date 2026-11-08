from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path("/home/GodOfAgents/code/VAMS-testnet")
outdir=root/"docs/remediation/m7_credential_scans_current_r1"
excluded=outdir.relative_to(root).as_posix()+"/"
python="/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python"
env={"PATH":"/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1"}
def source_inventory():
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
before=source_inventory()
commands=[("default_credential_scan","scripts/security/default_credential_scan.py"),("secret_history_prevention_scan","scripts/security/secret_history_prevention_scan.py")]
results=[]
for label,script_path in commands:
    argv=[python,"-B",script_path]
    p=subprocess.run(argv,cwd=root,env=env,text=True,capture_output=True,check=False)
    line=p.stdout.splitlines()[0] if p.stdout.splitlines() else ""
    findings=sum(1 for line in p.stdout.splitlines() if line.lstrip().startswith("- "))
    results.append({"name":label,"argv":argv,"exit_code":p.returncode,"summary":line,"finding_count":findings,"stdout_sha256":hashlib.sha256(p.stdout.encode()).hexdigest(),"stderr_sha256":hashlib.sha256(p.stderr.encode()).hexdigest(),"raw_output_retained":False})
after=source_inventory()
head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
result={"schema":"m7-current-credential-scans-v1","date":"2026-10-03","git_head":head,"python":sys.version.split()[0],"repository_inventory_excluding_evidence_package_before":before,"repository_inventory_excluding_evidence_package_after":after,"source_inventory_unchanged":before==after,"raw_scanner_output_retained":False,"runner_enforces_sandbox":False,"sandbox":"outer bwrap invocation enforces --unshare-net, root read-only, /tmp tmpfs, cleared environment, and only the evidence package writable","scans":results}
(outdir/"RESULT.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
