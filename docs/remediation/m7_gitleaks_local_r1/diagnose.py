import hashlib,json,pathlib,subprocess,sys,tempfile,shutil
repo=pathlib.Path('/home/GodOfAgents/code/VAMS-testnet')
sys.path.insert(0,str(repo/'scripts/security'))
import m0_4_vendor_baseline_gate as gate
baseline,baseline_digest=gate.load_baseline(repo/'scripts/security/m0_4_vendor_baseline.json')
if baseline_digest!=gate.PINNED_BASELINE_SHA256:
 raise RuntimeError('baseline pin mismatch')
head_result=gate.run(['git','rev-parse','HEAD'],repo)
if head_result.returncode!=0:
 raise RuntimeError('superproject HEAD unavailable')
head=gate.validate_hex(head_result.stdout.strip(),40,'superproject HEAD')
subs=gate.parse_submodules(repo)
owner_states=gate.verify_owners(repo,subs,head)
owner_trees=gate.verify_baseline_blobs(repo,baseline,owner_states)
config=repo/'.gitleaks.toml'
config_hash=gate.sha256_file(config)
if config.is_symlink() or config_hash!=gate.PINNED_CONFIG_SHA256:
 raise RuntimeError('Gitleaks configuration pin mismatch')
scanner=pathlib.Path('/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks')
scanner_hash=gate.sha256_file(scanner)
version_result=gate.run([str(scanner),'version'],repo)
version=version_result.stdout.strip()
if version_result.returncode!=0 or version!=gate.PINNED_GITLEAKS_VERSION or scanner_hash!=gate.PINNED_GITLEAKS_SHA256:
 raise RuntimeError('scanner pin mismatch')
sources=gate.collect_sources(repo,subs)
tmp=pathlib.Path(tempfile.mkdtemp(prefix='vams-m7-gitleaks-diag-'))
try:
 staged=tmp/'tree'
 staged.mkdir(mode=0o700)
 hashes,manifest=gate.stage_sources(sources,staged)
 report=tmp/'report.json'
 command=[str(scanner),'dir','.','--config',str(config),'--redact=100','--report-format','json','--report-path',str(report),'--exit-code','1','--no-banner']
 cp=subprocess.run(command,cwd=staged,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
 if cp.returncode!=1 or not report.is_file():
  raise RuntimeError('scanner did not return the expected finding report')
 data=json.loads(report.read_bytes())
 observed,first_party,unknown=gate.sanitized_findings(data,hashes,subs,owner_trees)
 safe=[]
 for item in data:
  raw=item.get('File')
  path=raw[2:] if isinstance(raw,str) and raw.startswith('./') else raw
  path=gate.canonical_path(path)
  if not any(path.startswith(p+'/') for p in subs):
   safe.append({'path':path,'rule_id':item.get('RuleID'),'start_line':item.get('StartLine'),'end_line':item.get('EndLine'),'file_sha256':hashes.get(path)})
 rawbytes=report.read_bytes()
 result={'gate_preflight':'passed','superproject_head':head,'baseline_sha256':baseline_digest,'scanner_version':version,'scanner_sha256':scanner_hash,'config_sha256':config_hash,'scanner_exit_code':cp.returncode,'all_redacted':True,'raw_report_retained':False,'report_sha256':hashlib.sha256(rawbytes).hexdigest(),'report_entry_count':len(data),'staged_source_count':len(sources),'source_manifest_sha256':manifest,'first_party_count':first_party,'vendor_identity_count':len(observed),'unknown_ownership_count':unknown,'first_party_files':len({x['path'] for x in safe}),'first_party_findings':safe}
 out=repo/'docs/remediation/m7_gitleaks_local_r1/CURRENT-TREE-SANITIZED.json'
 out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
finally:
 shutil.rmtree(tmp,ignore_errors=False)
