#!/usr/bin/env python3
"""Run one reviewed command and record local evidence; NOT a sandbox or release gate."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(root: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--cwd', type=Path, default=Path('.'))
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=int, default=3600)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == '--':
        command.pop(0)
    if not command or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', args.name):
        parser.error('Supply a command after -- and a bounded machine-readable name')
    if args.timeout_seconds <= 0:
        parser.error('--timeout-seconds must be positive')
    cwd = args.cwd.expanduser().resolve()
    repo = Path(git(cwd, 'rev-parse', '--show-toplevel')).resolve()
    output_root = args.output_root.expanduser().resolve()
    if output_root == repo or repo in output_root.parents:
        parser.error('Evidence output must be outside the source checkout')
    before = {
        'commit': git(repo, 'rev-parse', 'HEAD'),
        'tree': git(repo, 'rev-parse', 'HEAD^{tree}'),
        'dirty': bool(git(repo, 'status', '--porcelain', '--untracked-files=all')),
    }
    started = utc()
    unique = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    run_dir = output_root / f'{unique}-{args.name}'
    run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    log_path = run_dir / 'command.log'
    record = {
        'record_type': 'local-command-observation-v1',
        'release_evidence': False,
        'privacy_reviewed': False,
        'independently_observed': False,
        'name': args.name,
        'cwd': str(cwd),
        'repository': str(repo),
        'argv': command,
        'source_before': before,
        'started_at': started,
        'timeout_seconds': args.timeout_seconds,
        'note': 'Raw output and argv may contain sensitive data; review before sharing. '
                'Dirty-tree records need a separately captured source snapshot/diff for reproduction.',
    }
    tick = time.monotonic()
    timed_out = False
    execution_error = None
    returncode = 127
    with log_path.open('xb') as log:
        os.chmod(log_path, 0o600)
        try:
            proc = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=(os.name == 'posix'))
            try:
                returncode = proc.wait(timeout=args.timeout_seconds)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                timed_out = isinstance(exc, subprocess.TimeoutExpired)
                if os.name == 'posix':
                    os.killpg(proc.pid, signal.SIGTERM)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name == 'posix':
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                    proc.wait()
                returncode = 124 if timed_out else 130
        except OSError as exc:
            execution_error = f'{type(exc).__name__}: {exc}'
            log.write(execution_error.encode('utf-8', errors='replace') + b'\n')
    try:
        after = {
            'commit': git(repo, 'rev-parse', 'HEAD'),
            'tree': git(repo, 'rev-parse', 'HEAD^{tree}'),
            'dirty': bool(git(repo, 'status', '--porcelain', '--untracked-files=all')),
        }
    except subprocess.CalledProcessError:
        after = {'state': 'UNAVAILABLE'}
    with log_path.open('rb') as log_file:
        digest = hashlib.file_digest(log_file, 'sha256').hexdigest()
    record.update({
        'ended_at': utc(), 'duration_seconds': round(time.monotonic() - tick, 3),
        'returncode': returncode, 'timed_out': timed_out, 'execution_error': execution_error,
        'source_after': after, 'log_path': 'command.log', 'log_sha256': digest,
        'status': ('BLOCKED_ENVIRONMENT' if execution_error else 'TIMED_OUT' if timed_out else
                   'INTERRUPTED' if returncode == 130 else 'PASSED' if returncode == 0 else 'FAILED'),
    })
    record_path = run_dir / 'record.json'
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    os.chmod(record_path, 0o600)
    print(f'{record["status"]}: exit {returncode}; evidence: {record_path}')
    print('Local command observation only; not a deployment approval or complete release gate.')
    return returncode if 0 <= returncode <= 255 else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
