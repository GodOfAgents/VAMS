import hashlib,json,pathlib,subprocess
repo=pathlib.Path('/home/GodOfAgents/code/VAMS-testnet')
tool=pathlib.Path('/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pip-audit')
commands=[
 ['-r','neuron/requirements.txt','--format','json','--progress-spinner','off','--cache-dir','/tmp/vams-pip-audit-cache','--timeout','30'],
 ['-r','gateway/requirements.txt','--format','json','--progress-spinner','off','--cache-dir','/tmp/vams-pip-audit-cache','--timeout','30']
]
results=[]
for args in commands:
 cp=subprocess.run([str(tool),*args],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
 combined=cp.stdout+'\n'+cp.stderr
 parsed={}
 dec=json.JSONDecoder()
 for pos,char in enumerate(combined):
  if char=='{':
   try:
    candidate,end=dec.raw_decode(combined,pos)
    if isinstance(candidate,dict) and isinstance(candidate.get('dependencies'),list):
     parsed=candidate
     break
   except json.JSONDecodeError:
    pass
 deps=parsed.get('dependencies',[])
 vulnerable=[]
 for dep in deps:
  for vuln in dep.get('vulns',[]):
   vulnerable.append({'name':dep.get('name'),'version':dep.get('version'),'id':vuln.get('id'),'fix_versions':vuln.get('fix_versions',[])})
 results.append({'requirements':args[1],'command':['pip-audit',*args],'exit_code':cp.returncode,'raw_output_sha256':hashlib.sha256(combined.encode()).hexdigest(),'raw_output_retained':False,'report_parse_ok':bool(parsed),'dependency_count':len(deps),'vulnerability_count':len(vulnerable),'vulnerabilities':vulnerable,'stdout_length':len(cp.stdout),'stderr_length':len(cp.stderr)})
version=subprocess.run([str(tool),'--version'],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
result={'schema':'m7-pip-audit-sanitized-v1','tool_version':(version.stdout+version.stderr).strip(),'tool_sha256':hashlib.sha256(tool.read_bytes()).hexdigest(),'results':results}
out=repo/'docs/remediation/m7_pip_audit_local_r1/RESULT.json'
out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
