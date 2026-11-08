import hashlib,json,pathlib,subprocess
repo=pathlib.Path('/home/GodOfAgents/code/VAMS-testnet')
bandit=pathlib.Path('/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/bandit')
cmd=[str(bandit),'-r','neuron/','gateway/','-ll','-ii','-f','json']
version=subprocess.run([str(bandit),'--version'],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
cp=subprocess.run(cmd,cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
combined=cp.stdout+'\n'+cp.stderr
report={}
decoder=json.JSONDecoder()
for pos,char in enumerate(combined):
 if char=='{':
  try:
   candidate,end=decoder.raw_decode(combined,pos)
   if isinstance(candidate,dict) and isinstance(candidate.get('results'),list):
    report=candidate
    break
  except json.JSONDecodeError:
   pass
results=report.get('results',[])
findings=[]
for item in results:
 findings.append({'filename':item.get('filename'),'test_id':item.get('test_id'),'issue_severity':item.get('issue_severity'),'issue_confidence':item.get('issue_confidence'),'line_number':item.get('line_number')})
findings.sort(key=lambda x:(str(x['filename']),int(x['line_number'] or 0),str(x['test_id'])))
result={'schema':'m7-bandit-sanitized-v1','command':'bandit -r neuron/ gateway/ -ll -ii -f json','bandit_exit_code':cp.returncode,'version':(version.stdout+version.stderr).strip(),'binary_sha256':hashlib.sha256(bandit.read_bytes()).hexdigest(),'raw_output_sha256':hashlib.sha256(combined.encode()).hexdigest(),'raw_output_retained':False,'report_parse_ok':bool(report),'stdout_length':len(cp.stdout),'stderr_length':len(cp.stderr),'result_count':len(results),'severity_counts':{name:sum(x.get('issue_severity')==name for x in results) for name in ('HIGH','MEDIUM','LOW','UNDEFINED')},'confidence_counts':{name:sum(x.get('issue_confidence')==name for x in results) for name in ('HIGH','MEDIUM','LOW','UNDEFINED')},'findings':findings}
out=repo/'docs/remediation/m7_bandit_local_r1/RESULT.json'
out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
