import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path('/home/GodOfAgents/code/VAMS-testnet')
PKG=ROOT/'docs/remediation/m7_bandit_current_r2'
BANDIT=Path('/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/bandit')
def inventory():
    rows=[]
    for base in (ROOT/'neuron',ROOT/'gateway'):
        for p in base.rglob('*.py'):
            if p.is_file() and not p.is_symlink() and not any(x in {'.git','__pycache__','.pytest_cache','.venv','venv'} for x in p.relative_to(ROOT).parts):
                rel=p.relative_to(ROOT).as_posix()
                rows.append({'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    rows.sort(key=lambda r:r['path'])
    h=hashlib.sha256()
    for r in rows:h.update(r['path'].encode()+b'\\0'+r['sha256'].encode()+b'\\n')
    return rows,h.hexdigest()
before,bh=inventory()
version=subprocess.run([str(BANDIT),'--version'],cwd=ROOT,text=True,capture_output=True,check=False)
argv=[str(BANDIT),'-r','neuron/','gateway/','-ll','-ii','-f','json']
cp=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True,check=False)
combined=cp.stdout+'\\n'+cp.stderr
decoder=json.JSONDecoder();report={}
for pos,char in enumerate(combined):
    if char=='{':
        try:
            candidate,end=decoder.raw_decode(combined,pos)
            if isinstance(candidate,dict) and isinstance(candidate.get('results'),list):
                report=candidate;break
        except json.JSONDecodeError:pass
parsed=bool(report)
findings=[]
for x in report.get('results',[]):
    findings.append({'filename':x.get('filename'),'test_id':x.get('test_id'),'issue_severity':x.get('issue_severity'),'issue_confidence':x.get('issue_confidence'),'line_number':x.get('line_number')})
findings.sort(key=lambda x:(str(x['filename']),int(x['line_number'] or 0),str(x['test_id'])))
after,ah=inventory()
result={'schema':'m7-bandit-current-source-v1','python':sys.version.split()[0],'bandit_version':(version.stdout+version.stderr).strip(),'bandit_binary_sha256':hashlib.sha256(BANDIT.read_bytes()).hexdigest(),'workflow_sha256':hashlib.sha256((ROOT/'.github/workflows/security-gates.yml').read_bytes()).hexdigest(),'source_inventory':{'file_count_before':len(before),'sha256_before':bh,'file_count_after':len(after),'sha256_after':ah,'unchanged':bh==ah},'argv':argv,'exit_code':cp.returncode,'report_parse_ok':parsed,'raw_output_retained':False,'stdout_length':len(cp.stdout),'stderr_length':len(cp.stderr),'combined_sha256':hashlib.sha256(combined.encode()).hexdigest(),'summary':{'finding_count':len(findings),'severity_counts':{k:sum(x['issue_severity']==k for x in findings) for k in ('HIGH','MEDIUM','LOW','UNDEFINED')},'confidence_counts':{k:sum(x['issue_confidence']==k for x in findings) for k in ('HIGH','MEDIUM','LOW','UNDEFINED')}},'findings':findings}
(PKG/'RESULT.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps({'exit_code':cp.returncode,'report_parse_ok':parsed,'source_count':len(before),'source_unchanged':bh==ah,'summary':result['summary'],'result':str(PKG/'RESULT.json')},indent=2))
raise SystemExit(0 if parsed and bh==ah else 1)
