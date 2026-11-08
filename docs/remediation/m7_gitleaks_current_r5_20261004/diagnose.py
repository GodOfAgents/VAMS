import hashlib, json, pathlib, subprocess, sys, tempfile, shutil
ROOT = pathlib.Path('/home/GodOfAgents/code/VAMS-testnet')
OUT = pathlib.Path('/home/GodOfAgents/vams-evidence/m7_gitleaks_current_r5_20261004')
sys.path.insert(0, str(ROOT / 'scripts/security'))
import m0_4_vendor_baseline_gate as gate

def sha(data): return hashlib.sha256(data).hexdigest()
def git(args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True).stdout
def snapshot():
    return {
        'head': git(['rev-parse', 'HEAD']).decode().strip(),
        'branch': git(['branch', '--show-current']).decode().strip(),
        'dirty_status_sha256': sha(git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])),
    }
def source_manifest(sources):
    state = hashlib.sha256()
    file_hashes = {}
    for relative, source in sorted(sources.items()):
        value = gate.sha256_file(source)
        file_hashes[relative] = value
        state.update(f'{value}  {relative}\n'.encode('utf-8'))
    return file_hashes, state.hexdigest()

baseline, baseline_digest = gate.load_baseline(ROOT / 'scripts/security/m0_4_vendor_baseline.json')
if baseline_digest != gate.PINNED_BASELINE_SHA256:
    raise RuntimeError('baseline pin mismatch')
head = snapshot()['head']
subs = gate.parse_submodules(ROOT)
owner_states = gate.verify_owners(ROOT, subs, head)
owner_trees = gate.verify_baseline_blobs(ROOT, baseline, owner_states)
config = ROOT / '.gitleaks.toml'
config_hash = gate.sha256_file(config)
if config.is_symlink() or config_hash != gate.PINNED_CONFIG_SHA256:
    raise RuntimeError('Gitleaks configuration pin mismatch')
scanner = pathlib.Path('/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks')
scanner_hash = gate.sha256_file(scanner)
version_result = gate.run([str(scanner), 'version'], ROOT)
version = version_result.stdout.strip()
if version_result.returncode != 0 or version != gate.PINNED_GITLEAKS_VERSION or scanner_hash != gate.PINNED_GITLEAKS_SHA256:
    raise RuntimeError('scanner pin mismatch')
workflow = ROOT / '.github/workflows/security-gates.yml'
workflow_before = gate.sha256_file(workflow)
helpers = {
    'scripts/security/m0_4_vendor_baseline_gate.py': gate.sha256_file(ROOT / 'scripts/security/m0_4_vendor_baseline_gate.py'),
    'scripts/security/m0_4_vendor_baseline.json': gate.sha256_file(ROOT / 'scripts/security/m0_4_vendor_baseline.json'),
}
before = snapshot()
sources = gate.collect_sources(ROOT, subs)
hashes, manifest = source_manifest(sources)
tmp = pathlib.Path(tempfile.mkdtemp(prefix='vams-m7-gitleaks-r5-'))
try:
    staged = tmp / 'tree'
    staged.mkdir(mode=0o700)
    staged_hashes, staged_manifest = gate.stage_sources(sources, staged)
    if staged_hashes != hashes or staged_manifest != manifest:
        raise RuntimeError('staged source identity mismatch')
    report = tmp / 'report.json'
    command = [str(scanner), 'dir', '.', '--config', str(config), '--redact=100', '--report-format', 'json', '--report-path', str(report), '--exit-code', '1', '--no-banner']
    cp = subprocess.run(command, cwd=staged, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if cp.returncode not in (0, 1) or not report.is_file():
        raise RuntimeError('scanner failed to produce a parseable report')
    data = json.loads(report.read_bytes())
    observed, first_party, unknown = gate.sanitized_findings(data, hashes, subs, owner_trees)
    safe = []
    for item in data:
        raw = item.get('File')
        path = raw[2:] if isinstance(raw, str) and raw.startswith('./') else raw
        path = gate.canonical_path(path)
        if not any(path.startswith(prefix + '/') for prefix in subs):
            safe.append({'path': path, 'rule_id': item.get('RuleID'), 'start_line': item.get('StartLine'), 'end_line': item.get('EndLine'), 'file_sha256': hashes.get(path)})
    report_sha = sha(report.read_bytes())
    raw_stdout_sha, raw_stderr_sha = sha(cp.stdout.encode()), sha(cp.stderr.encode())
    report_count = len(data)
    expected_scanner_exit = 1 if report_count else 0
    scanner_exit_semantics_match = cp.returncode == expected_scanner_exit
    try:
        vendor_reconciliation = gate.reconcile(baseline, observed, first_party=first_party, unknown=unknown, scanner_version=version, scanner_sha256=scanner_hash, owner_states=owner_states)
        vendor_reconciliation_error = None
        vendor_reconciliation_pass = True
    except gate.GateError as exc:
        vendor_reconciliation = None
        vendor_reconciliation_error = str(exc)
        vendor_reconciliation_pass = False
finally:
    shutil.rmtree(tmp, ignore_errors=False)

sources_after = gate.collect_sources(ROOT, subs)
hashes_after, manifest_after = source_manifest(sources_after)
after = snapshot()
workflow_after = gate.sha256_file(workflow)
config_hash_after = gate.sha256_file(config)
baseline_digest_after = gate.sha256_file(ROOT / 'scripts/security/m0_4_vendor_baseline.json')
scanner_hash_after = gate.sha256_file(scanner)
helper_hashes_after = {
    'scripts/security/m0_4_vendor_baseline_gate.py': gate.sha256_file(ROOT / 'scripts/security/m0_4_vendor_baseline_gate.py'),
    'scripts/security/m0_4_vendor_baseline.json': gate.sha256_file(ROOT / 'scripts/security/m0_4_vendor_baseline.json'),
}
stable = before == after and manifest == manifest_after and hashes == hashes_after and workflow_before == workflow_after and config_hash == config_hash_after and baseline_digest == baseline_digest_after and scanner_hash == scanner_hash_after and helpers == helper_hashes_after
result = {
    'schema': 'm7-gitleaks-current-r5-result', 'gate_preflight': 'passed',
    'scan_scope': 'git ls-files --cached --others --exclude-standard for root and recursively pinned submodules; ignored files, Git history, and remote refs excluded',
    'superproject_before': before, 'superproject_after': after, 'git_stable': before == after,
    'source_count': len(sources), 'source_manifest_sha256_before': manifest, 'source_manifest_sha256_after': manifest_after,
    'source_stable': manifest == manifest_after and hashes == hashes_after,
    'workflow_sha256_before': workflow_before, 'workflow_sha256_after': workflow_after, 'workflow_stable': workflow_before == workflow_after,
    'config_sha256_before': config_hash, 'config_sha256_after': config_hash_after,
    'baseline_file_sha256_before': baseline_digest, 'baseline_file_sha256_after': baseline_digest_after,
    'scanner_sha256_after': scanner_hash_after,
    'helper_hashes_before': helpers, 'helper_hashes_after': helper_hashes_after,
    'baseline_sha256': baseline_digest, 'scanner_version': version, 'scanner_sha256': scanner_hash, 'config_sha256': config_hash,
    'scanner_exit_code': cp.returncode, 'scanner_stdout_sha256': raw_stdout_sha, 'scanner_stderr_sha256': raw_stderr_sha,
    'scanner_raw_streams_retained': False, 'all_matches_redacted_by_scanner': True, 'raw_report_retained': False,
    'report_sha256': report_sha, 'report_entry_count': report_count, 'source_manifest_for_scan': manifest,
    'first_party_count': first_party, 'vendor_identity_count': len(observed), 'unknown_ownership_count': unknown,
    'first_party_files': len({x['path'] for x in safe}), 'first_party_findings': safe,
    'scanner_exit_expected_from_report': expected_scanner_exit, 'scanner_exit_semantics_match': scanner_exit_semantics_match,
    'vendor_reconciliation_pass': vendor_reconciliation_pass, 'vendor_reconciliation_counts': vendor_reconciliation,
    'vendor_reconciliation_error': vendor_reconciliation_error,
    'capture_stable': stable, 'm0_4_gate_pass': first_party == 0 and unknown == 0 and vendor_reconciliation_pass and scanner_exit_semantics_match and stable,
    'scope_limit': 'Current unignored working-tree sources only; not T06/history or remote-ref evidence.'
}
result_bytes = (json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode()
(OUT / 'CURRENT-TREE-SANITIZED.json').write_bytes(result_bytes)
run = {
    'schema': 'm7-gitleaks-current-r5-run',
    'expected_outer_command': ['bwrap','--unshare-net','--ro-bind','/','/','--tmpfs','/tmp','--dev-bind','/dev','/dev','--proc','/proc','--bind',str(OUT),str(OUT),'--chdir',str(ROOT),'--clearenv','--setenv','PATH','/usr/bin:/bin','/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python','-B',str(OUT/'diagnose.py')],
    'outer_command_note': 'Expected outer command is wrapper-written metadata, not independent process telemetry.',
    'capture_script_sha256': gate.sha256_file(OUT / 'diagnose.py'), 'result_sha256': sha(result_bytes),
    'pinned_tool': {'path': str(scanner), 'version': version, 'sha256': scanner_hash},
    'scanner_command': command, 'scanner_exit_expected_from_report': expected_scanner_exit, 'scanner_exit_semantics_match': scanner_exit_semantics_match,
    'python': sys.version.split()[0], 'network': 'disabled by outer bwrap',
    'capture_stable': stable, 'source_manifest_sha256': manifest,
    'vendor_reconciliation_pass': vendor_reconciliation_pass, 'vendor_reconciliation_error': vendor_reconciliation_error,
    'scanner_raw_report_and_streams_retained': False, 'gate_pass': result['m0_4_gate_pass'],
}
(OUT / 'RUN.json').write_text(json.dumps(run, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'capture_stable': stable, 'scanner_exit_code': cp.returncode, 'report_entry_count': report_count, 'first_party_count': first_party, 'vendor_identity_count': len(observed), 'unknown_ownership_count': unknown, 'gate_pass': result['m0_4_gate_pass']}, sort_keys=True))
if not stable:
    raise SystemExit('source or Git state changed during scan')
