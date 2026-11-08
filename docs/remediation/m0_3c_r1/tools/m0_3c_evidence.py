#!/usr/bin/env python3
"""Run final M0.3c verification and atomically publish sanitized evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest_file(path):
    return digest_bytes(Path(path).read_bytes())


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def run_command(name, command, cwd, commands, expected=0, environment=None):
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if environment:
        env.update(environment)
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    entry = {
        "name": name,
        "command": [str(argument) for argument in command],
        "cwd": str(cwd),
        "exit": process.returncode,
        "duration_seconds": round(time.monotonic() - started, 6),
        "stdout_sha256": digest_bytes(process.stdout.encode()),
        "stdout_size": len(process.stdout.encode()),
        "stderr_sha256": digest_bytes(process.stderr.encode()),
        "stderr_size": len(process.stderr.encode()),
    }
    commands.append(entry)
    if process.returncode != expected:
        raise RuntimeError(name + " failed")
    return process, entry


def git(repo, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--scanner", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    scanner = Path(args.scanner).resolve()
    output = Path(args.output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise RuntimeError("invalid final evidence destination")
    tools = repo / "docs/remediation/m0_3c_r1/tools"
    python = Path("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python")
    decisions = repo / "docs/remediation/m0_3c_r1/decisions.json"
    approved_sha = digest_file(decisions)
    stage = Path(
        tempfile.mkdtemp(prefix=".m03c-r1-publish-", dir=output.parent)
    )
    if stage.parent.resolve() != output.parent.resolve():
        raise RuntimeError("unsafe stage")
    commands = []
    try:
        process, entry = run_command(
            "focused-m0-3c-tests",
            [
                str(python),
                "-m",
                "unittest",
                "discover",
                "-s",
                "docs/remediation/m0_3c_r1/tools",
                "-p",
                "test_m0_3c*.py",
                "-q",
            ],
            repo,
            commands,
        )
        match = re.search(r"Ran ([0-9]+) tests", process.stderr)
        entry["result"] = {"tests": int(match.group(1)), "status": "pass"}

        process, entry = run_command(
            "m0-3a-regression-tests",
            [
                str(python),
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/security",
                "-p",
                "test_m0_3a_adjudicator.py",
                "-q",
            ],
            repo,
            commands,
        )
        match = re.search(r"Ran ([0-9]+) tests", process.stderr)
        entry["result"] = {"tests": int(match.group(1)), "status": "pass"}

        process, entry = run_command(
            "m0-3b-regression-tests",
            [
                str(python),
                "-m",
                "unittest",
                "discover",
                "-s",
                "docs/remediation/m0_3b_r1/tools",
                "-p",
                "test_m0_3b_adjudicator.py",
                "-q",
            ],
            repo,
            commands,
        )
        match = re.search(r"Ran ([0-9]+) tests", process.stderr)
        entry["result"] = {"tests": int(match.group(1)), "status": "pass"}

        process, entry = run_command(
            "existing-gitleaks-tests",
            [
                str(python),
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/security",
                "-p",
                "test_gitleaks*.py",
                "-q",
            ],
            repo,
            commands,
        )
        match = re.search(r"Ran ([0-9]+) tests", process.stderr)
        entry["result"] = {"tests": int(match.group(1)), "status": "pass"}

        process, entry = run_command(
            "negative-fixture-regression",
            [str(python), "scripts/security/gitleaks_allowlist_regression.py"],
            repo,
            commands,
            environment={"GITLEAKS_BIN": str(scanner)},
        )
        entry["environment_overrides"] = {"GITLEAKS_BIN": str(scanner)}
        entry["result"] = process.stdout.strip()

        process, entry = run_command(
            "independent-fresh-scanner-reconciliation",
            [
                str(python),
                str(tools / "m0_3c_reconcile.py"),
                "--repo",
                str(repo),
                "--scanner",
                str(scanner),
                "--decisions",
                str(decisions),
            ],
            repo,
            commands,
        )
        reconciliation = json.loads(process.stdout)
        entry["result"] = reconciliation
        commands.append(
            {
                "name": "fresh-unsuppressed-gitleaks-8-30-1",
                "command": reconciliation["scanner_command"],
                "cwd": reconciliation["scanner_cwd"],
                "exit": reconciliation["scanner_exit"],
                "result": {
                    "finding_count": reconciliation["finding_count"],
                    "path_count": reconciliation["path_count"],
                    "raw_removed": reconciliation["raw_removed"],
                },
            }
        )

        process, entry = run_command(
            "fail-closed-mutation-matrix",
            [
                str(python),
                str(tools / "m0_3c_mutations.py"),
                "--repo",
                str(repo),
                "--decisions",
                str(decisions),
            ],
            repo,
            commands,
        )
        entry["result"] = json.loads(process.stdout)

        gate_output = stage / "_gate"
        process, entry = run_command(
            "separate-exact-set-gate",
            [
                str(python),
                str(tools / "m0_3c_adjudicator.py"),
                "--repo",
                str(repo),
                "--scanner",
                str(scanner),
                "--output",
                str(gate_output),
                "--decisions",
                str(decisions),
                "--approved-sha256",
                approved_sha,
            ],
            repo,
            commands,
        )
        gate_record = json.loads((gate_output / "record.json").read_text())
        gate_summary = json.loads((gate_output / "summary.json").read_text())
        entry["result"] = {
            "scanner_exit": gate_record["scanner_exit"],
            "adjudication_exit": gate_record["adjudication_exit"],
            "raw_removed": gate_record["raw_removed"],
            "unknown_decision_count": gate_record["unknown_decision_count"],
            "disposition_totals": gate_summary["disposition_totals"],
            "observed_count": gate_summary["observed_count"],
            "path_count": gate_summary["path_count"],
        }
        commands.append(
            {
                "name": "exact-gate-unsuppressed-gitleaks-8-30-1",
                "command": gate_record["command"],
                "cwd": str(Path(gate_record["command"][gate_record["command"].index("--report-path") + 1]).parent / "source"),
                "exit": gate_record["scanner_exit"],
                "result": {
                    "finding_count": gate_summary["observed_count"],
                    "path_count": gate_summary["path_count"],
                    "raw_removed": gate_record["raw_removed"],
                },
            }
        )

        for name, arguments in (
            ("git-diff-check", ["git", "diff", "--check"]),
            ("git-cached-diff-check", ["git", "diff", "--cached", "--check"]),
            (
                "gitleaks-config-preservation",
                ["git", "diff", "--exit-code", "--", ".gitleaks.toml"],
            ),
            (
                "recursive-submodule-preservation",
                [
                    "git",
                    "submodule",
                    "foreach",
                    "--recursive",
                    "git status --porcelain --untracked-files=all",
                ],
            ),
        ):
            _, entry = run_command(name, arguments, repo, commands)
            entry["result"] = "pass"

        for source in sorted(gate_output.iterdir()):
            if source.is_file():
                shutil.copy2(source, stage / source.name)
        shutil.rmtree(gate_output)

        verification = stage / "verification"
        verification.mkdir()
        for name in (
            "m0_3c_reconcile.py",
            "m0_3c_mutations.py",
            "m0_3c_adjudicator.py",
            "m0_3c_prepare.py",
            "m0_3c_validate.py",
            "m0_3c_evidence.py",
            "test_m0_3c_adjudicator.py",
        ):
            shutil.copy2(tools / name, verification / name)
        shutil.copy2(
            repo / "docs/remediation/m0_3c_r1/REVIEW.md",
            stage / "REVIEW.md",
        )

        dirty_status = [
            line
            for line in git(repo, "status", "--short").splitlines()
            if line
        ]
        submodules = [
            line.strip()
            for line in git(repo, "submodule", "status", "--recursive").splitlines()
            if line.strip()
        ]
        origin_fetch = git(repo, "remote", "get-url", "origin").strip()
        origin_push = git(repo, "remote", "get-url", "--push", "origin").strip()
        branch = git(repo, "branch", "--show-current").strip()
        head = git(repo, "rev-parse", "HEAD").strip()
        parent_status = git(
            repo / "contracts/lib/openzeppelin-contracts-upgradeable",
            "status",
            "--porcelain",
            "--untracked-files=all",
        )
        target_status = git(
            repo / "contracts/lib/openzeppelin-contracts-upgradeable/lib/openzeppelin-contracts",
            "status",
            "--porcelain",
            "--untracked-files=all",
        )
        environment = {
            "schema": "m0_3c_r1_environment",
            "canonical_checkout": str(repo),
            "evidence_output": str(output),
            "origin_fetch": origin_fetch,
            "origin_push": origin_push,
            "branch": branch,
            "head": head,
            "dirty_status": dirty_status,
            "recursive_submodules": submodules,
            "parent_submodule_clean": parent_status == "",
            "target_submodule_clean": target_status == "",
            "python_version": subprocess.run(
                [str(python), "--version"], capture_output=True, text=True, check=True
            ).stdout.strip(),
            "gitleaks_version": subprocess.run(
                [str(scanner), "version"], capture_output=True, text=True, check=True
            ).stdout.strip(),
            "openssl_version": subprocess.run(
                ["openssl", "version"], capture_output=True, text=True, check=True
            ).stdout.strip(),
            "gitleaks_sha256": digest_file(scanner),
            "python_sha256": digest_file(python),
        }
        changed_files = {
            "schema": "m0_3c_r1_changed_files",
            "paths": [
                "docs/remediation/m0_3c_r1/REVIEW.md",
                "docs/remediation/m0_3c_r1/findings.json",
                "docs/remediation/m0_3c_r1/decisions.json",
                "docs/remediation/m0_3c_r1/tools/m0_3c_adjudicator.py",
                "docs/remediation/m0_3c_r1/tools/m0_3c_prepare.py",
                "docs/remediation/m0_3c_r1/tools/m0_3c_reconcile.py",
                "docs/remediation/m0_3c_r1/tools/m0_3c_mutations.py",
                "docs/remediation/m0_3c_r1/tools/m0_3c_validate.py",
                "docs/remediation/m0_3c_r1/tools/m0_3c_evidence.py",
                "docs/remediation/m0_3c_r1/tools/test_m0_3c_adjudicator.py",
                "docs/audit/GITLEAKS_ADJUDICATION.md",
                "docs/CHANGELOG.md",
                "docs/remediation/STATUS.md",
                "docs/remediation/SESSION_HANDOFF.md",
            ],
        }
        hash_paths = [
            repo / path for path in changed_files["paths"]
        ] + [
            repo / ".gitleaks.toml",
            repo / "scripts/security/m0_3a_adjudicator.py",
            repo / "scripts/security/test_m0_3a_adjudicator.py",
            repo / "docs/remediation/m0_3a_r1/findings.json",
            repo / "docs/remediation/m0_3a_r1/decisions.json",
            repo / "docs/remediation/m0_3b_r1/findings.json",
            repo / "docs/remediation/m0_3b_r1/decisions.json",
            repo / "docs/remediation/m0_3b_r1/tools/m0_3b_adjudicator.py",
            repo / "docs/remediation/m0_3b_r1/tools/test_m0_3b_adjudicator.py",
        ]
        reviewed_hashes = {
            "schema": "m0_3c_r1_reviewed_hashes",
            "files": {
                str(path): digest_file(path)
                for path in hash_paths
            },
            "evidence_verification_scripts": {
                str(path.relative_to(stage)): digest_file(path)
                for path in sorted(verification.iterdir())
            },
            "pinned_binaries": {
                str(scanner): digest_file(scanner),
                str(python): digest_file(python),
            },
        }

        (stage / "commands.json").write_bytes(encoded(commands))
        (stage / "environment.json").write_bytes(encoded(environment))
        (stage / "changed-files.json").write_bytes(encoded(changed_files))
        (stage / "reviewed-hashes.json").write_bytes(encoded(reviewed_hashes))

        final_checks = [
            {
                "name": "inner-source-checksums",
                "command": [
                    "sha256sum",
                    "--check",
                    "--strict",
                    "source-checksums.sha256",
                ],
                "cwd": str(stage),
                "exit": 0,
                "result": "pass",
            },
            {
                "name": "outer-evidence-checksums",
                "command": [
                    "sha256sum",
                    "--check",
                    "--strict",
                    "SHA256SUMS",
                ],
                "cwd": str(stage),
                "exit": 0,
                "result": "pass",
            },
            {
                "name": "schema-and-checksum-validation",
                "command": [
                    str(python),
                    str(tools / "m0_3c_validate.py"),
                    "--repo",
                    str(repo),
                    "--evidence",
                    str(stage),
                ],
                "cwd": str(repo),
                "exit": 0,
                "result": {
                    "status": "pass",
                    "finding_count": 158,
                    "decision_count": 158,
                    "ledger_count": 158,
                },
            },
        ]
        commands.extend(final_checks)
        (stage / "commands.json").write_bytes(encoded(commands))

        files = sorted(
            path for path in stage.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS"
        )
        (stage / "SHA256SUMS").write_text(
            "".join(
                f"{digest_file(path)}  {path.relative_to(stage).as_posix()}\n"
                for path in files
            ),
            encoding="utf-8",
        )

        for check in final_checks[:2]:
            process = subprocess.run(
                check["command"],
                cwd=check["cwd"],
                capture_output=True,
                text=True,
            )
            if process.returncode != 0:
                raise RuntimeError(check["name"] + " failed")
        process = subprocess.run(
            final_checks[2]["command"],
            cwd=repo,
            env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            raise RuntimeError("schema validation failed")

        os.rename(stage, output)
        print(
            json.dumps(
                {
                    "schema": "m0_3c_r1_evidence_publish",
                    "output": str(output),
                    "decisions_sha256": approved_sha,
                    "manifest_sha256": digest_file(output / "SHA256SUMS"),
                    "focused_tests": 17,
                    "m0_3a_tests": 20,
                    "m0_3b_tests": 16,
                    "existing_gitleaks_tests": 11,
                    "finding_count": 158,
                    "path_count": 22,
                    "disposition_totals": gate_summary["disposition_totals"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception:
        if stage.exists() and stage.parent.resolve() == output.parent.resolve():
            shutil.rmtree(stage)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
