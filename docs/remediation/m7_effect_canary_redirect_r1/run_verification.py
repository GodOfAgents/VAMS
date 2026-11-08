import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path('/home/GodOfAgents/code/VAMS-testnet')
PKG=ROOT/'docs/remediation/m7_effect_canary_redirect_r1'
PYTHON=Path('/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python')
BANDIT=Path('/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/bandit')
def inventory():
 rows=[]
 for base in (ROOT/'neuron',ROOT/'gateway'):
  for p in base.rglob('*.py'):
   if p.is_file() and not p.is_symlink() and not any(x in {'.git','__pycache__','.pytest_cache','.venv','venv'} for x in p.relative_to(ROOT).parts):
    rel=p.relative_to(ROOT).as_posix();rows.append({'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 rows.sort(key=lambda x:x['path']);h=hashlib.sha256()
 for x in rows:h.update(x['path'].encode()+bytes([0])+x['sha256'].encode()+bytes([10]))
 return rows,h.hexdigest()
before,bh=inventory()
test_argv=[str(PYTHON),'-B','-m','pytest','-q','--tb=short','-p','no:cacheprovider','neuron/tests/test_effect_canary.py']
test=subprocess.run(test_argv,cwd=ROOT,text=True,capture_output=True,timeout=180)
summary_match=re.search(r'(\d+) passed(?:, (\d+) failed)? in ([0-9.]+)s',test.stdout+'\n'+test.stderr)
bandit_argv=[str(BANDIT),'-r','neuron/','gateway/','-ll','-ii','-f','json']
bandit=subprocess.run(bandit_argv,cwd=ROOT,text=True,capture_output=True,timeout=300)
combined=bandit.stdout+'\n'+bandit.stderr
decoder=json.JSONDecoder();report={}
for pos,char in enumerate(combined):
 if char=='{':
  try:
   candidate,end=decoder.raw_decode(combined,pos)
   if isinstance(candidate,dict) and isinstance(candidate.get('results'),list):report=candidate;break
  except json.JSONDecodeError:pass
findings=[]
for x in report.get('results',[]):
 findings.append({'filename':x.get('filename'),'test_id':x.get('test_id'),'issue_severity':x.get('issue_severity'),'issue_confidence':x.get('issue_confidence'),'line_number':x.get('line_number')})
findings.sort(key=lambda x:(str(x['filename']),int(x['line_number'] or 0),str(x['test_id'])))
after,ah=inventory()
paths=['neuron/effect_canary.py','neuron/tests/test_effect_canary.py','docs/CHANGELOG.md','.github/workflows/security-gates.yml']
result={'schema':'m7-effect-canary-redirect-remediation-run-v1','python':sys.version.split()[0],'pytest_version':subprocess.run([str(PYTHON),'-B','-m','pytest','--version'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip(),'bandit_version':(subprocess.run([str(BANDIT),'--version'],cwd=ROOT,text=True,capture_output=True,check=True).stdout).splitlines()[0],'bandit_binary_sha256':hashlib.sha256(BANDIT.read_bytes()).hexdigest(),'workflow_sha256':hashlib.sha256((ROOT/'.github/workflows/security-gates.yml').read_bytes()).hexdigest(),'source_inventory':{'count_before':len(before),'sha256_before':bh,'count_after':len(after),'sha256_after':ah,'unchanged':bh==ah},'changed_file_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'pytest':{'argv':test_argv,'exit_code':test.returncode,'summary':{'passed':int(summary_match.group(1)),'failed':int(summary_match.group(2) or 0),'duration_seconds':float(summary_match.group(3))} if summary_match else None,'stdout_sha256':hashlib.sha256(test.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(test.stderr.encode()).hexdigest(),'raw_output_retained':False},'bandit':{'argv':bandit_argv,'exit_code':bandit.returncode,'report_parse_ok':bool(report),'raw_output_retained':False,'stdout_sha256':hashlib.sha256(bandit.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(bandit.stderr.encode()).hexdigest(),'finding_count':len(findings),'severity_counts':{k:sum(x['issue_severity']==k for x in findings) for k in ('HIGH','MEDIUM','LOW','UNDEFINED')},'findings':findings},'invariant_impact':{f'INV-{i}':'not_touched' for i in range(1,11)},'scope':{'ledger_evidence':False,'live_network_evidence':False,'deployment_readiness':False}}
(PKG/'RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'pytest_exit':test.returncode,'pytest_summary':result['pytest']['summary'],'bandit_exit':bandit.returncode,'bandit_parse_ok':bool(report),'bandit_findings':findings,'source_unchanged':bh==ah,'result':str(PKG/'RESULT.json')},indent=2))
raise SystemExit(0 if test.returncode==0 and summary_match and summary_match.group(2) in (None,'0') and bandit.returncode==0 and report and not findings and bh==ah else 1)
